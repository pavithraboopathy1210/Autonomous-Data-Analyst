"""Shared PostgreSQL configuration loaded from the project .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def get_db_config():
    """Return PostgreSQL connection settings without embedding credentials."""
    load_dotenv(ENV_FILE)

    names = {
        "host": "DB_HOST",
        "database": "DB_NAME",
        "user": "DB_USER",
        "password": "DB_PASSWORD",
        "port": "DB_PORT",
    }
    values = {key: os.getenv(env_name) for key, env_name in names.items()}
    missing = [names[key] for key, value in values.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing PostgreSQL settings in .env: " + ", ".join(missing)
        )

    try:
        values["port"] = int(values["port"])
    except ValueError as error:
        raise RuntimeError("DB_PORT must be a valid integer.") from error

    return values
