import os
import psycopg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_DSN = (
    f"postgresql://{os.environ['POSTGRES_USER']}:"
    f"{os.environ['POSTGRES_PASSWORD']}@localhost:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ['POSTGRES_DB']}"
)


def get_conn():
    return psycopg.connect(DB_DSN, autocommit=True)


def create_call(conn, call_id, caller_number, destination_number):
    conn.execute(
        """
        INSERT INTO calls (id, caller_number, destination_number)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (call_id, caller_number, destination_number),
    )


def close_call(conn, call_id, hangup_cause):
    conn.execute(
        """
        UPDATE calls
        SET ended_at = now(), hangup_cause = %s
        WHERE id = %s
        """,
        (hangup_cause, call_id),
    )
    
    
def create_turn(conn, call_id, turn_number, caller_audio_path):
    conn.execute(
        """
        INSERT INTO call_turns (call_id, turn_number, caller_audio_path)
        VALUES (%s, %s, %s)
        ON CONFLICT (call_id, turn_number) DO NOTHING
        """,
        (call_id, turn_number, caller_audio_path),
    )


def complete_turn(conn, call_id, turn_number, caller_transcript, ai_reply_text, ai_audio_path):
    conn.execute(
        """
        UPDATE call_turns
        SET caller_transcript = %s,
            ai_reply_text = %s,
            ai_audio_path = %s,
            ended_at = now()
        WHERE call_id = %s AND turn_number = %s
        """,
        (caller_transcript, ai_reply_text, ai_audio_path, call_id, turn_number),
    )

def set_session_recording(conn, call_id, path):
    conn.execute(
        """
        UPDATE calls
        SET session_recording_path = %s
        WHERE id = %s
        """,
        (path, call_id),
    )