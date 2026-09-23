"""Alembic environment. Driven programmatically by ``research_factory.persistence.db.upgrade``."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from research_factory.persistence.schema import metadata

config = context.config
target_metadata = metadata


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("no connection or sqlalchemy.url configured")
    engine = create_engine(url)
    with engine.begin() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported")
run_migrations_online()
