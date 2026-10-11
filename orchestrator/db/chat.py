from psycopg_pool import AsyncConnectionPool
from .config import get_dsn

pool = AsyncConnectionPool(get_dsn(), min_size=1, max_size=10, open=False)


async def create_chat_session(session_id):
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO chat_sessions (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
            (session_id,),
        )


async def close_chat_session(session_id):
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE chat_sessions SET ended_at = now() WHERE id = %s",
            (session_id,),
        )


async def log_chat_message(session_id, turn_number, user_message, ai_reply):
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO chat_messages (session_id, turn_number, user_message, ai_reply)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (session_id, turn_number) DO NOTHING
            """,
            (session_id, turn_number, user_message, ai_reply),
        )
