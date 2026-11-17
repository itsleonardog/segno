from __future__ import annotations

import uuid

from ambiente_database import URL_AMMINISTRATORE, esegui_alembic
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool


def _url_con_database(nome_database: str) -> str:
    return (
        make_url(URL_AMMINISTRATORE)
        .set(database=nome_database)
        .render_as_string(hide_password=False)
    )


async def _crea_database(nome_database: str) -> None:
    motore = create_async_engine(
        URL_AMMINISTRATORE,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        async with motore.connect() as connessione:
            await connessione.execute(
                text(f'CREATE DATABASE "{nome_database}" TEMPLATE template0')
            )
    finally:
        await motore.dispose()


async def _elimina_database(nome_database: str) -> None:
    motore = create_async_engine(
        URL_AMMINISTRATORE,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        async with motore.connect() as connessione:
            await connessione.execute(
                text("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :nome_database
                      AND pid <> pg_backend_pid()
                    """),
                {"nome_database": nome_database},
            )
            await connessione.execute(
                text(f'DROP DATABASE IF EXISTS "{nome_database}"')
            )
    finally:
        await motore.dispose()


async def _regista_report_presente(url_database: str) -> bool:
    motore = create_async_engine(url_database, poolclass=NullPool)
    try:
        async with motore.connect() as connessione:
            esito = await connessione.execute(
                text("SELECT to_regclass('public.report')")
            )
            return esito.scalar_one() is not None
    finally:
        await motore.dispose()


async def test_migrazione_da_zero(
    motore_amministratore: AsyncEngine,
) -> None:
    nome_database = f"civic_zero_{uuid.uuid4().hex[:10]}"
    await _crea_database(nome_database)
    url_database = _url_con_database(nome_database)
    try:
        esegui_alembic(("upgrade", "head"), url_database)
        assert await _regista_report_presente(url_database)

        esegui_alembic(("downgrade", "base"), url_database)
        assert not await _regista_report_presente(url_database)
    finally:
        await _elimina_database(nome_database)
