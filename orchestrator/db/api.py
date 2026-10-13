from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from .config import get_dsn

pool = AsyncConnectionPool(get_dsn(), min_size=1, max_size=10, open=False, kwargs={"row_factory": dict_row})


async def create_account(account_id, name, slug):
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO accounts (id, name, slug) VALUES (%s, %s, %s)",
            (account_id, name, slug),
        )


async def create_account_user(user_id, account_id, email, password_hash, role="owner"):
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO account_users (id, account_id, email, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, account_id, email, password_hash, role),
        )


async def get_account_user_by_email(email):
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, account_id, email, password_hash, role FROM account_users WHERE email = %s",
            (email,),
        )
        return await cur.fetchone()
