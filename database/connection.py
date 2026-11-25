from functools import lru_cache

from sqlalchemy import URL, create_engine, text

from database.config import get_db_config


@lru_cache(maxsize=1)
def get_engine():
    """Create the shared SQLAlchemy engine from the common DB settings."""
    config = get_db_config()
    url = URL.create(
        "postgresql+psycopg2",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )
    return create_engine(url)


def test_connection():
    """Return True when PostgreSQL responds to a simple query."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
