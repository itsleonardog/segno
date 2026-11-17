from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from aiuto_autenticazione import EmailSenderFinto, crea_app_di_test
from ambiente_database import (
    PASSWORD_APPLICAZIONE,
    PASSWORD_MIGRATORE,
    RUOLO_APPLICAZIONE,
    RUOLO_MIGRATORE,
    URL_AMMINISTRATORE,
    URL_APPLICAZIONE,
    esegui_alembic,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

TABELLE_DA_SVUOTARE = (
    "report_status_event",
    "report_dispatch",
    "outbox_event",
    "notification",
    "notification_preference",
    "refresh_token",
    "email_verification_token",
    "password_reset_token",
    "report",
    "municipality_service",
    "user",
    "municipality",
    "audit_log",
)


@pytest_asyncio.fixture(scope="session")
async def motore_amministratore() -> AsyncIterator[AsyncEngine]:
    motore = create_async_engine(URL_AMMINISTRATORE, poolclass=NullPool)
    try:
        async with motore.connect() as connessione:
            await connessione.execute(text("SELECT 1"))
    except (OSError, DBAPIError) as errore:
        await motore.dispose()
        pytest.skip(
            "Database PostgreSQL/PostGIS di test non raggiungibile: "
            "avvia il servizio con make test-db-up. "
            f"Dettaglio: {errore}"
        )
    yield motore
    await motore.dispose()


@pytest_asyncio.fixture(scope="session")
async def database_migrato(
    motore_amministratore: AsyncEngine,
) -> AsyncIterator[None]:
    esegui_alembic(("upgrade", "head"), URL_AMMINISTRATORE)
    await _allinea_ruoli(motore_amministratore)
    yield


@pytest_asyncio.fixture(scope="session")
async def motore_applicazione(database_migrato: None) -> AsyncIterator[AsyncEngine]:
    motore = create_async_engine(URL_APPLICAZIONE, poolclass=NullPool)
    async with motore.connect() as connessione:
        await connessione.execute(text("SELECT 1"))
    yield motore
    await motore.dispose()


@pytest_asyncio.fixture
async def invio_email_finto() -> EmailSenderFinto:
    return EmailSenderFinto()


@pytest_asyncio.fixture
async def client_auth(
    motore_applicazione: AsyncEngine,
    invio_email_finto: EmailSenderFinto,
) -> AsyncIterator[httpx.AsyncClient]:
    applicazione = crea_app_di_test(motore_applicazione, invio_email_finto)
    trasporto = httpx.ASGITransport(app=applicazione)
    async with httpx.AsyncClient(
        transport=trasporto,
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def database_pulito(
    motore_amministratore: AsyncEngine,
    database_migrato: None,
) -> AsyncIterator[None]:
    elenco_tabelle = ", ".join(f'"{nome}"' for nome in TABELLE_DA_SVUOTARE)
    async with motore_amministratore.begin() as connessione:
        await connessione.execute(
            text(f"TRUNCATE TABLE {elenco_tabelle} RESTART IDENTITY CASCADE")
        )
    yield


@pytest_asyncio.fixture
async def categoria_altro(
    motore_amministratore: AsyncEngine,
    database_migrato: None,
) -> str:
    async with motore_amministratore.connect() as connessione:
        identificativo = await connessione.execute(
            text("SELECT id FROM category WHERE slug = 'altro'")
        )
    return str(identificativo.scalar_one())


async def _allinea_ruoli(motore: AsyncEngine) -> None:
    password_app = PASSWORD_APPLICAZIONE.replace("'", "''")
    password_migratore = PASSWORD_MIGRATORE.replace("'", "''")
    async with motore.begin() as connessione:
        await connessione.execute(
            text(f"ALTER ROLE {RUOLO_APPLICAZIONE} LOGIN NOBYPASSRLS NOINHERIT")
        )
        await connessione.execute(
            text(f"ALTER ROLE {RUOLO_APPLICAZIONE} " f"PASSWORD '{password_app}'")
        )
        await connessione.execute(
            text(f"ALTER ROLE {RUOLO_MIGRATORE} LOGIN BYPASSRLS NOINHERIT")
        )
        await connessione.execute(
            text(f"ALTER ROLE {RUOLO_MIGRATORE} " f"PASSWORD '{password_migratore}'")
        )
