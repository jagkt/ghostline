import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_dsn():
    return (
        f"postgresql://{os.environ['POSTGRES_USER']}:"
        f"{os.environ['POSTGRES_PASSWORD']}@localhost:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{os.environ['POSTGRES_DB']}"
    )
