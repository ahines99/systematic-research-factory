"""Engine creation and migrations."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

MIGRATIONS = Path(__file__).parent / "migrations"


def make_engine(url: str) -> Engine:
    """Create an engine. SQLite gets foreign keys, WAL and a busy timeout."""
    kwargs: dict[str, Any] = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            path = url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)
    if isinstance(engine.pool, StaticPool):
        # StaticPool deliberately shares one SQLite DBAPI connection. Without
        # serialization, a reader closing its Connection can roll back a late
        # model worker's accounting transaction on that same connection.
        connection_lock = threading.RLock()

        @event.listens_for(engine, "checkout")
        def _lock_checkout(_dbapi: Any, _record: Any, _proxy: Any) -> None:
            connection_lock.acquire()

        @event.listens_for(engine, "checkin")
        def _unlock_checkin(_dbapi: Any, _record: Any) -> None:
            connection_lock.release()

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn: Any, _record: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            if url not in ("sqlite://", "sqlite:///:memory:"):
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    return cfg


def upgrade(engine: Engine, revision: str = "head") -> None:
    cfg = alembic_config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, revision)


def downgrade(engine: Engine, revision: str = "base") -> None:
    cfg = alembic_config()
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, revision)
