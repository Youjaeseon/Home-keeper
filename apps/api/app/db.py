import atexit
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

try:  # Optional: falls back to one connection per request when psycopg-pool is not installed.
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - depends on the local environment
    ConnectionPool = None

from app.config import get_settings

# Reuse connections instead of opening one per request. A new TLS connection to
# the Supabase pooler costs ~1.8s from the dev Mac, which made every API call ~3s.
_pools: dict = {}
_KWARGS = {"row_factory": dict_row, "connect_timeout": 5, "application_name": "career-pair-api"}
_lock = threading.Lock()


def _pool():
    url = get_settings().database_url
    pool = _pools.get(url)
    if pool is not None:
        return pool
    with _lock:
        pool = _pools.get(url)
        if pool is None:
            kwargs = dict(_KWARGS)
            # Supabase transaction-mode pooler (port 6543) does not support prepared statements.
            if ":6543/" in url:
                kwargs["prepare_threshold"] = None
            pool = ConnectionPool(
                url,
                kwargs=kwargs,
                min_size=1,
                max_size=10,
                max_idle=300,
                # Drop connections the pooler closed while idle before handing them out.
                check=ConnectionPool.check_connection,
                open=True,
            )
            _pools[url] = pool
    return pool


@atexit.register
def _close_pools() -> None:
    for pool in _pools.values():
        pool.close()


@contextmanager
def _connection():
    if ConnectionPool is None:
        with psycopg.connect(get_settings().database_url, **_KWARGS) as conn:
            yield conn
    else:
        with _pool().connection() as conn:
            yield conn


@contextmanager
def transaction():
    """One connection and one transaction per request; rolls back on any exception."""
    with _connection() as conn:
        with conn.transaction():
            yield conn


@contextmanager
def read_transaction():
    """Consistent snapshot for multi-query reads."""
    with _connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            yield conn
