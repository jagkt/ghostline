import os
import subprocess
import logging
import greenswitch
import gevent
import requests
import time
from dotenv import load_dotenv
from faster_whisper import WhisperModel
import db

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger("ghostline.loop")

FS_HOST = os.environ["FS_HOST"]
FS_PORT = int(os.environ["FS_PORT"])
FS_PASSWORD = os.environ["FS_PASSWORD"]

HOST_DIR = os.environ["HOST_RECORDINGS_DIR"]
CONTAINER_DIR = os.environ["CONTAINER_RECORDINGS_DIR"]

OLLAMA_URL = os.environ["OLLAMA_URL"]
OLLAMA_MODEL = os.environ["OLLAMA_MODEL"]
PIPER_VOICE = os.environ["PIPER_VOICE"]
WHISPER_MODEL_SIZE = os.environ["WHISPER_MODEL"]

logger.info("Loading Whisper model (%s)...", WHISPER_MODEL_SIZE)
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
logger.info("Whisper model loaded.")

# Per-call in-memory state. Lost if the orchestrator restarts mid-call,
# a known, acceptable simplification for this stage.
turn_counters = {}       # call_id -> current turn number
conversation_history = {}  # call_id -> list of (caller_text, ai_reply) tuples


def transcribe(host_path):
    segments, info = whisper_model.transcribe(host_path, beam_size=5)
    text = " ".join(s.text.strip() for s in segments).strip()
    logger.info("Transcribed (lang=%s, p=%.2f): %r", info.language, info.language_probability, text)
    return text


def ask_ollama(call_id, caller_text):
    history = conversation_history.get(call_id, [])
    convo_lines = []
    for prior_caller, prior_reply in history:
        convo_lines.append(f"Caller: {prior_caller}")
        convo_lines.append(f"You: {prior_reply}")
    convo_lines.append(f"Caller: {caller_text}")
    convo_text = "\n".join(convo_lines)

    prompt = (
        "You are a concise phone assistant having an ongoing call. "
        "Reply in one short sentence, considering the conversation so far.\n\n"
        f"{convo_text}\nYou:"
    )
    t0 = time.time()
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    reply = resp.json()["response"].strip()
    logger.info("Ollama reply (%.1fs): %r", time.time() - t0, reply)
    return reply


def synthesize(text, host_path):
    subprocess.run(
        ["piper", "--model", PIPER_VOICE, "--output_file", host_path],
        input=text.encode("utf-8"),
        check=True,
    )


def on_channel_create(fs, pg_conn, event):
    try:
        call_id = event.headers.get("Unique-ID")
        caller = event.headers.get("Caller-Caller-ID-Number")
        dest = event.headers.get("Caller-Destination-Number")
        logger.info("Call started: %s (%s -> %s)", call_id, caller, dest)
        db.create_call(pg_conn, call_id, caller, dest)
        turn_counters[call_id] = 1
        conversation_history[call_id] = []
        
        fs.send(f"api uuid_setvar {call_id} ghostline_turn 1")
        
        session_path = f"{CONTAINER_DIR}/sessions/ghostline_session_{call_id}.wav"
        result = fs.send(f"api uuid_record {call_id} start {session_path}")
        logger.info("Session recording start result: %s", result.data if result else None)
        db.set_session_recording(pg_conn, call_id, session_path)
        
    except Exception:
        logger.exception("Error in on_channel_create")


def on_channel_hangup(pg_conn, event):
    try:
        call_id = event.headers.get("Unique-ID")
        cause = event.headers.get("Hangup-Cause")
        logger.info("Call ended: %s (cause=%s)", call_id, cause)
        db.close_call(pg_conn, call_id, cause)
        turn_counters.pop(call_id, None)
        conversation_history.pop(call_id, None)
    except Exception:
        logger.exception("Error in on_channel_hangup")


def on_record_stop(fs, pg_conn, event):
    try:
        call_id = event.headers.get("Unique-ID")
        container_record_path = event.headers.get("Record-File-Path")
        if not call_id or not container_record_path:
            logger.warning("Missing expected headers, skipping.")
            return

        turn_number = turn_counters.get(call_id, 1)
        host_record_path = container_record_path.replace(CONTAINER_DIR, HOST_DIR)
        logger.info("Call %s turn %s recorded -> %s", call_id, turn_number, host_record_path)

        db.create_turn(pg_conn, call_id, turn_number, container_record_path)

        caller_text = transcribe(host_record_path)
        if not caller_text:
            logger.info("Empty transcript, skipping this turn.")
            return

        reply_text = ask_ollama(call_id, caller_text)
        conversation_history.setdefault(call_id, []).append((caller_text, reply_text))

        response_filename = f"response_{call_id}_turn{turn_number}.wav"
        host_response_path = os.path.join(HOST_DIR, response_filename)
        synthesize(reply_text, host_response_path)
        container_response_path = os.path.join(CONTAINER_DIR, response_filename)

        db.complete_turn(pg_conn, call_id, turn_number, caller_text, reply_text, container_response_path)

        result = fs.send(f"api uuid_broadcast {call_id} {container_response_path} aleg")
        logger.info("uuid_broadcast result: %s", result.data if result else None)

    except Exception:
        logger.exception("Error processing RECORD_STOP event")


def on_playback_stop(fs, event):
    try:
        call_id = event.headers.get("Unique-ID")
        played_path = event.headers.get("Playback-File-Path", "")
        if "response_" not in played_path:
            return  # ignore the beep and the holding tone

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

    pg_conn = db.get_conn()

    fs.register_handle("CHANNEL_CREATE", lambda event: on_channel_create(fs, pg_conn, event))
    fs.register_handle("CHANNEL_HANGUP_COMPLETE", lambda event: on_channel_hangup(pg_conn, event))
    fs.register_handle("RECORD_STOP", lambda event: on_record_stop(fs, pg_conn, event))
    fs.register_handle("PLAYBACK_STOP", lambda event: on_playback_stop(fs, event))

    fs.send("event plain CHANNEL_CREATE CHANNEL_HANGUP_COMPLETE RECORD_STOP PLAYBACK_STOP")
    logger.info("Ready. Call 7000, have a back-and-forth conversation.")

    while True:
        gevent.sleep(1)


if __name__ == "__main__":
    main()