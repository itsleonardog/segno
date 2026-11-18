from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastruttura.configurazione import (
    leggi_configurazione_database,
    leggi_origini_consentite,
)
from app.infrastruttura.database import crea_motore
from app.infrastruttura.errori import registra_gestori_errori
from app.infrastruttura.middleware_auth import MiddlewareAutenticazione
from app.presentazione import admin, auth, categorie, geo, me, notifiche, segnalazioni

DESCRIZIONE_APPLICAZIONE = "API della piattaforma di segnalazione civica multi-comune."
METODI_CORS_CONSENTITI = ["GET", "POST", "PATCH", "OPTIONS"]
INTESTAZIONI_CORS_CONSENTITE = ["Authorization", "Content-Type", "Idempotency-Key"]


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
    applicazione.add_middleware(
        CORSMiddleware,
        allow_origins=list(leggi_origini_consentite()),
        allow_methods=METODI_CORS_CONSENTITI,
        allow_headers=INTESTAZIONI_CORS_CONSENTITE,
    )
    applicazione.include_router(auth.router, prefix="/v1")
    applicazione.include_router(me.router, prefix="/v1")
    applicazione.include_router(categorie.router, prefix="/v1")
    applicazione.include_router(geo.router, prefix="/v1")
    applicazione.include_router(segnalazioni.router, prefix="/v1")
    applicazione.include_router(notifiche.router, prefix="/v1")
    applicazione.include_router(admin.router, prefix="/v1")
    return applicazione


app = crea_app()
