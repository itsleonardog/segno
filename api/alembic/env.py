from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

configurazione_alembic = context.config

if configurazione_alembic.config_file_name is not None:
    fileConfig(configurazione_alembic.config_file_name)

url_database = os.environ.get(
    "CIVIC_DATABASE_URL"
) or configurazione_alembic.get_main_option("sqlalchemy.url")
configurazione_alembic.set_main_option(
    "sqlalchemy.url", url_database.replace("%", "%%")
)

target_metadata = None


def esegui_migrazioni_offline() -> None:
    context.configure(
        url=configurazione_alembic.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def esegui_migrazioni(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def esegui_migrazioni_online() -> None:
    motore = async_engine_from_config(
        configurazione_alembic.get_section(
            configurazione_alembic.config_ini_section, {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with motore.connect() as connessione:
        await connessione.run_sync(esegui_migrazioni)
    await motore.dispose()


if context.is_offline_mode():
    esegui_migrazioni_offline()
else:
    asyncio.run(esegui_migrazioni_online())
