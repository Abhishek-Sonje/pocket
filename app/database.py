"""SQLite connections with explicit transactions on every supported Python version."""

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool


def make_engine(url=None, busy_ms=None):
    if url is None:
        directory = Path(os.getenv("POCKET_DATA_DIR", "data"))
        directory.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{directory / 'pocket.db'}"
    timeout = int(os.getenv("POCKET_BUSY_MS", "5000")) if busy_ms is None else busy_ms
    engine = create_engine(url, poolclass=NullPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(timeout)}")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin(connection):
        mode = " IMMEDIATE" if connection.get_execution_options().get("write") else ""
        connection.exec_driver_sql("BEGIN" + mode)

    return engine


@contextmanager
def transaction(engine, *, write=False):
    with engine.connect() as connection:
        connection = connection.execution_options(write=write)
        with connection.begin():
            yield connection
