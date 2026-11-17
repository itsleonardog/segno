from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastruttura.configurazione import leggi_configurazione_database
from app.infrastruttura.database import crea_motore
from app.infrastruttura.errori import registra_gestori_errori
from app.infrastruttura.middleware_auth import MiddlewareAutenticazione
from app.presentazione import auth, me

DESCRIZIONE_APPLICAZIONE = "API della piattaforma di segnalazione civica multi-comune."


def crea_app(*, motore: AsyncEngine | None = None) -> FastAPI:
    """Restituisce l'applicazione FastAPI configurata per il servizio API."""

    @asynccontextmanager
    async def ciclo_vita(applicazione: FastAPI) -> AsyncIterator[None]:
        motore_uso = motore or crea_motore(
            leggi_configurazione_database().url_applicazione
        )
        applicazione.state.motore = motore_uso
        try:
            yield
        finally:
            if motore is None:
                await motore_uso.dispose()

    applicazione = FastAPI(
        title="Segnalazione civica",
        version="0.1.0",
        description=DESCRIZIONE_APPLICAZIONE,
        lifespan=ciclo_vita,
    )
    if motore is not None:
        applicazione.state.motore = motore

    registra_gestori_errori(applicazione)
    applicazione.add_middleware(MiddlewareAutenticazione)
    applicazione.include_router(auth.router, prefix="/v1")
    applicazione.include_router(me.router, prefix="/v1")
    return applicazione


app = crea_app()
