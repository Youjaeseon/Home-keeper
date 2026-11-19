from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings


def _connect():
    return psycopg.connect(
        get_settings().database_url,
        row_factory=dict_row,
        connect_timeout=5,
        application_name="career-pair-api",
    )


@contextmanager
def transaction():
    """One connection and one transaction per request; rolls back on any exception."""
    with _connect() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def read_transaction():
    """Consistent snapshot for multi-query reads."""
    with _connect() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            yield conn
