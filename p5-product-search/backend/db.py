"""Builds the Postgres connection URL from individual env vars."""

import os
from urllib.parse import quote_plus

def get_db_url() -> str:
    user     = os.environ["DB_USER"]
    password = quote_plus(os.environ["DB_PASSWORD"])  # encodes @ → %40, etc.
    host     = os.environ.get("DB_HOST", "localhost")
    port     = os.environ.get("DB_PORT", "5432")
    name     = os.environ["DB_NAME"]
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"
