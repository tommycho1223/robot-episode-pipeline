"""Database connection and schema setup (plain SQL with psycopg 3)."""
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


@contextmanager
def connect():
    """Open a connection that commits on success and rolls back on error."""
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        yield conn


def init_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_PATH.read_text())
