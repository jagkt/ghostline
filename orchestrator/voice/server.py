from gevent import monkey
monkey.patch_all()

import os
import subprocess
import logging
import greenswitch
import gevent
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from ai.core import ask_ollama
from db import voice as db

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger("ghostline.loop")

FS_HOST = os.environ["FS_HOST"]
FS_PORT = int(os.environ["FS_PORT"])
FS_PASSWORD = os.environ["FS_PASSWORD"]

HOST_DIR = os.environ["HOST_RECORDINGS_DIR"]
CONTAINER_DIR = os.environ["CONTAINER_RECORDINGS_DIR"]

PIPER_VOICE = os.environ["PIPER_VOICE"]
WHISPER_MODEL_SIZE = os.environ["WHISPER_MODEL"]

logger.info("Loading Whisper model (%s)...", WHISPER_MODEL_SIZE)
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
logger.info("Whisper model loaded.")

turn_counters = {}
conversation_history = {}
empty_turn_counters = {}


def transcribe(host_path):
    segments, info = whisper_model.transcribe(host_path, beam_size=5)
    text = " ".join(s.text.strip() for s in segments).strip()
    logger.info("Transcribed (lang=%s, p=%.2f, duration=%.2fs): %r", info.language, info.language_probability, info.duration, text)
    return text, info.duration


def synthesize(text, host_path):
    subprocess.run(
        ["piper", "--model", PIPER_VOICE, "--output_file", host_path],
        input=text.encode("utf-8"),
        check=True,
    )


def on_channel_create(fs, event):
    try:
        call_id = event.headers.get("Unique-ID")
        caller = event.headers.get("Caller-Caller-ID-Number")
        dest = event.headers.get("Caller-Destination-Number")
        logger.info("Call started: %s (%s -> %s)", call_id, caller, dest)
        db.create_call(call_id, caller, dest)
        turn_counters[call_id] = 1
        conversation_history[call_id] = []
        empty_turn_counters[call_id] = 0

        fs.send(f"api uuid_setvar {call_id} ghostline_turn 1")

        session_path = f"{CONTAINER_DIR}/sessions/ghostline_session_{call_id}.wav"
        result = fs.send(f"api uuid_record {call_id} start {session_path}")
        logger.info("Session recording start result: %s", result.data if result else None)
        db.set_session_recording(call_id, session_path)

    except Exception:
        logger.exception("Error in on_channel_create")


def on_channel_hangup(event):
    try:
        call_id = event.headers.get("Unique-ID")
        cause = event.headers.get("Hangup-Cause")
        logger.info("Call ended: %s (cause=%s)", call_id, cause)
        db.close_call(call_id, cause)
        turn_counters.pop(call_id, None)
        conversation_history.pop(call_id, None)
        empty_turn_counters.pop(call_id, None)
        
    except Exception:
        logger.exception("Error in on_channel_hangup")


def on_record_stop(fs, event):
    try:
        call_id = event.headers.get("Unique-ID")
        container_record_path = event.headers.get("Record-File-Path")
        if not call_id or not container_record_path:
            logger.warning("Missing expected headers, skipping.")
            return
        
        if "/sessions/" in container_record_path:
            logger.info("Ignoring RECORD_STOP for QA session recording: %s", container_record_path)
            return

        turn_number = turn_counters.get(call_id, 1)
        host_record_path = container_record_path.replace(CONTAINER_DIR, HOST_DIR)
        logger.info("Call %s turn %s recorded -> %s", call_id, turn_number, host_record_path)

        db.create_turn(call_id, turn_number, container_record_path)

        caller_text, duration = transcribe(host_record_path)
        MIN_REAL_SPEECH_SECONDS = 2.0
        
        if not caller_text or duration < MIN_REAL_SPEECH_SECONDS:
            if caller_text:
                logger.info(
                    "Calls %s: treating short transcript %r (%.2fs) as silence, below %.1fs threshold",
                    call_id, caller_text, duration, MIN_REAL_SPEECH_SECONDS,
                )
            empty_count = empty_turn_counters.get(call_id, 0) + 1
            empty_turn_counters[call_id] = empty_count
            logger.info("Call %s: empty transcript (%d consecutive)", call_id, empty_count)
            
            if empty_count >= 4:
                logger.info("Call %s: silence threshold exceeded, ending call.", call_id)
                goodbye_path = os.path.join(HOST_DIR, f"goodbye_{call_id}.wav")
                synthesize("I haven't heard anything for a while, so I'll end the call here. Goodbye.", goodbye_path)
                container_goodbye_path = os.path.join(CONTAINER_DIR, f"goodbye_{call_id}.wav")
                result = fs.send(f"api uuid_broadcast {call_id} {container_goodbye_path} aleg")
                logger.info("Goodbye broadcast result: %s", result.data if result else None)
                return
            
            if empty_count == 2:
                checkin_path = os.path.join(HOST_DIR, f"checkin_{call_id}_turn{turn_number}.wav")
                synthesize("Are you still there?", checkin_path)
                container_checkin_path = os.path.join(CONTAINER_DIR, f"checkin_{call_id}_turn{turn_number}.wav")
                fs.send(f"api uuid_broadcast {call_id} {container_checkin_path} aleg")
                return
            
            next_turn = turn_counters.get(call_id, 1) + 1
            turn_counters[call_id] = next_turn
            cmd = f"uuid_transfer {call_id} 'set:ghostline_turn={next_turn},transfer:7000 XML default' inline"
            fs.send(f"api {cmd}")
            return
            # logger.info("Empty transcript, skipping this turn.")
            # return
            
            
        next_turn = turn_counters.get(call_id, 1) + 1
        history = conversation_history.get(call_id, [])
        reply_text = ask_ollama(
            history,
            caller_text,
            system_prompt=(
                "You are a concise phone assistant having an ongoing call. "
                "Reply in one short sentence, considering the conversation so far."
            ),
        )
        conversation_history.setdefault(call_id, []).append((caller_text, reply_text))

        response_filename = f"response_{call_id}_turn{turn_number}.wav"
        host_response_path = os.path.join(HOST_DIR, response_filename)
        synthesize(reply_text, host_response_path)
        container_response_path = os.path.join(CONTAINER_DIR, response_filename)

        db.complete_turn(call_id, turn_number, caller_text, reply_text, container_response_path)

        result = fs.send(f"api uuid_broadcast {call_id} {container_response_path} aleg")
        logger.info("uuid_broadcast result: %s", result.data if result else None)

    except Exception:
        logger.exception("Error processing RECORD_STOP event")


def on_playback_stop(fs, event):
    try:
        call_id = event.headers.get("Unique-ID")
        played_path = event.headers.get("Playback-File-Path", "")
        
        if "goodbye_" in played_path:
            logger.info("Goodbye message finished for call %s, ending call.", call_id)
            fs.send(f"api uuid_kill {call_id} NORMAL CLEARING")
            return
        
        if "response_" not in played_path and "checkin_" not in played_path:
            return #ignore the beep and the holding tone

        next_turn = turn_counters.get(call_id, 1) + 1
        turn_counters[call_id] = next_turn
        logger.info("Response finished for call %s, transferring back for turn %s", call_id, next_turn)

        cmd = f"uuid_transfer {call_id} 'set:ghostline_turn={next_turn},transfer:7000 XML default' inline"
        result = fs.send(f"api {cmd}")
        logger.info("uuid_transfer result: %s", result.data if result else None)

    except Exception:
        logger.exception("Error processing PLAYBACK_STOP event")


def main():
    fs = greenswitch.InboundESL(host=FS_HOST, port=FS_PORT, password=FS_PASSWORD)
    fs.connect()
    logger.info("Connected to FreeSWITCH ESL")

    fs.register_handle("CHANNEL_CREATE", lambda event: on_channel_create(fs, event))
    fs.register_handle("CHANNEL_HANGUP_COMPLETE", lambda event: on_channel_hangup(event))
    fs.register_handle("RECORD_STOP", lambda event: on_record_stop(fs, event))
    fs.register_handle("PLAYBACK_STOP", lambda event: on_playback_stop(fs, event))

    fs.send("event plain CHANNEL_CREATE CHANNEL_HANGUP_COMPLETE RECORD_STOP PLAYBACK_STOP")
    logger.info("Ready. Call 7000, have a back-and-forth conversation.")

    while True:
        gevent.sleep(1)


if __name__ == "__main__":
    main()
