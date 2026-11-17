from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

type ScopeAccesso = Literal["tenant", "public", "platform", "system"]


def crea_motore(url_database: str) -> AsyncEngine:
    """Crea il motore async SQLAlchemy per la connessione indicata."""
    return create_async_engine(url_database, pool_pre_ping=True)


@asynccontextmanager
async def transazione_con_contesto(
    motore: AsyncEngine,
    *,
    scope: ScopeAccesso,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> AsyncIterator[AsyncConnection]:
    """Apre una transazione con il contesto RLS impostato con SET LOCAL."""
    async with motore.connect() as connessione, connessione.begin():
        await _imposta_contesto(connessione, scope, tenant_id, user_id)
        yield connessione


async def _imposta_contesto(
    connessione: AsyncConnection,
    scope: ScopeAccesso,
    tenant_id: str | None,
    user_id: str | None,
) -> None:
    contesto = {
        "app.access_scope": scope,
        "app.tenant_id": tenant_id or "",
        "app.user_id": user_id or "",
    }
    for nome_impostazione, valore in contesto.items():
        await connessione.execute(
            text("SELECT set_config(:nome, :valore, true)"),
            {"nome": nome_impostazione, "valore": valore},
        )
