import os
from sqlalchemy.engine import URL


def get_postgres_url() -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "admin"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "p2_rag"),
    )
