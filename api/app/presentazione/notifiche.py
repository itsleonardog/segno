from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.notifica import Notifica
from app.infrastruttura import repository_notifiche
from app.infrastruttura.errori import ErroreApi
from app.infrastruttura.middleware_auth import connessione_tenant
from app.presentazione.schemi_notifiche import (
    RispostaElencoNotifiche,
    RispostaLetteraNotifica,
    RispostaLetturaCompleta,
    RispostaNotifica,
)

router = APIRouter(tags=["notifiche"])

ConnessioneTenant = Annotated[AsyncConnection, Depends(connessione_tenant)]


@router.get("/notifications", response_model=RispostaElencoNotifiche)
async def elenca_notifiche(
    connessione: ConnessioneTenant,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RispostaElencoNotifiche:
    notifiche = await repository_notifiche.elenca_notifiche_utente(
        connessione,
        cursore=_uuid_da_cursore(cursor),
        limite=limit + 1,
    )
    ha_altre_pagine = len(notifiche) > limit
    pagina = notifiche[:limit]
    conteggio = await repository_notifiche.conta_notifiche_non_lette(connessione)
    return RispostaElencoNotifiche(
        items=[_risposta_notifica(notifica) for notifica in pagina],
        next_cursor=(str(pagina[-1].id) if ha_altre_pagine and pagina else None),
        unread_count=conteggio,
    )


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=RispostaLetteraNotifica,
)
async def segna_notifica_letta(
    notification_id: uuid.UUID,
    connessione: ConnessioneTenant,
) -> RispostaLetteraNotifica:
    letta = await repository_notifiche.marca_notifica_letta(
        connessione,
        notifica_id=notification_id,
    )
    if not letta:
        raise _notifica_non_trovata()
    return RispostaLetteraNotifica(letta=True)


@router.post(
    "/notifications/read-all",
    response_model=RispostaLetturaCompleta,
)
async def segna_tutte_lette(
    connessione: ConnessioneTenant,
) -> RispostaLetturaCompleta:
    aggiornate = await repository_notifiche.marca_tutte_notifiche_lette(connessione)
    return RispostaLetturaCompleta(aggiornate=aggiornate)


def _risposta_notifica(notifica: Notifica) -> RispostaNotifica:
    return RispostaNotifica(
        id=notifica.id,
        report_id=notifica.report_id,
        type=notifica.tipo,
        channel=notifica.canale,
        payload=dict(notifica.payload),
        read_at=notifica.read_at,
        created_at=notifica.created_at,
    )


def _uuid_da_cursore(cursore: str | None) -> uuid.UUID | None:
    if cursore is None:
        return None
    try:
        return uuid.UUID(cursore)
    except ValueError as errore:
        raise ErroreApi(
            status=422,
            titolo="Cursore non valido",
            dettaglio=(
                "Il cursore di paginazione non è valido. " "Riparti dalla prima pagina."
            ),
        ) from errore


def _notifica_non_trovata() -> ErroreApi:
    return ErroreApi(
        status=404,
        titolo="Notifica non trovata",
        dettaglio="La notifica richiesta non esiste o non ti appartiene.",
    )
