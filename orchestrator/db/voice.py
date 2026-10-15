from psycopg_pool import ConnectionPool
from .config import get_dsn

pool = ConnectionPool(get_dsn(), min_size=1, max_size=10, open=True)


def get_account_id_for_did(e164_number):
    with pool.connection() as conn:
        cur = conn.execute(
            "SELECT account_id from dids WHERE e164_number = %s AND status = 'active'",
            (e164_number,),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None

def create_call(call_id, caller_number, destination_number, account_id=None):
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO calls (id, caller_number, destination_number, account_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (call_id, caller_number, destination_number, account_id),
        )


def close_call(call_id, hangup_cause):
    with pool.connection() as conn:
        conn.execute(
            "UPDATE calls SET ended_at = now(), hangup_cause = %s WHERE id = %s",
            (hangup_cause, call_id),
        )


def set_session_recording(call_id, path):
    with pool.connection() as conn:
        conn.execute(
            "UPDATE calls SET session_recording_path = %s WHERE id = %s",
            (path, call_id),
        )


def create_turn(call_id, turn_number, caller_audio_path):
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO call_turns (call_id, turn_number, caller_audio_path)
            VALUES (%s, %s, %s)
            ON CONFLICT (call_id, turn_number) DO NOTHING
            """,
            (call_id, turn_number, caller_audio_path),
        )


def complete_turn(call_id, turn_number, caller_transcript, ai_reply_text, ai_audio_path):
    with pool.connection() as conn:
        conn.execute(
            """
            UPDATE call_turns
            SET caller_transcript = %s, ai_reply_text = %s,
                ai_audio_path = %s, ended_at = now()
            WHERE call_id = %s AND turn_number = %s
            """,
            (caller_transcript, ai_reply_text, ai_audio_path, call_id, turn_number),
        )
