from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.ciclo_vita_segnalazione import registra_cambio_stato
from app.dominio.dispatch import AdattatoreOpen311, RisolutoreChiaviOpen311
from app.dominio.esempio_segnalazione import (
    StatoSegnalazione,
    TransizioneNonAmmessa,
    valida_transizione_stato,
)
from app.infrastruttura import repository_dispatch, repository_segnalazioni

logger = logging.getLogger(__name__)

LIMITE_DISPATCH_PER_CICLO = 50
ATTORE_SINCRONIZZAZIONE = "open311_sync"

type ApriTransazione = Callable[[], AbstractAsyncContextManager[AsyncConnection]]

STATI_OPEN311: dict[str, StatoSegnalazione] = {
    "open": StatoSegnalazione.APERTA,
    "in_progress": StatoSegnalazione.IN_CORSO,
    "resolved": StatoSegnalazione.RISOLTA,
    "closed": StatoSegnalazione.CHIUSA,
}


def mappa_stato_open311(stato_esterno: str | None) -> StatoSegnalazione | None:
    """Restituisce lo stato interno corrispondente o None se non riconosciuto."""
    if stato_esterno is None:
        return None
    chiave = "_".join(stato_esterno.strip().lower().replace("-", " ").split())
    return STATI_OPEN311.get(chiave)


class SincronizzatoreOpen311:
    """Riallinea lo stato delle segnalazioni inviate via Open311."""

    def __init__(
        self,
        *,
        adattatore_open311: AdattatoreOpen311,
        risolutore_chiavi: RisolutoreChiaviOpen311,
    ) -> None:
        self._adattatore_open311 = adattatore_open311
        self._risolutore_chiavi = risolutore_chiavi

    async def recupera_stato(
        self,
        voce: repository_dispatch.DispatchDaSincronizzare,
    ) -> str | None:
        """Restituisce lo stato esterno del dispatch, se leggibile."""
        api_key = self._risolutore_chiavi.chiave_per_riferimento(voce.api_key_ref)
        return await self._adattatore_open311.recupera_stato_richiesta(
            voce.endpoint_open311,
            api_key,
            voce.provider_request_id,
        )


async def sincronizza_open311(
    apri_transazione: ApriTransazione,
    sincronizzatore: SincronizzatoreOpen311,
    *,
    limite: int = LIMITE_DISPATCH_PER_CICLO,
) -> int:
    """Sincronizza i dispatch Open311 e restituisce quante segnalazioni cambiano."""
    async with apri_transazione() as connessione:
        dispatch_da_sincronizzare = (
            await repository_dispatch.elenca_dispatch_open311_sincronizzabili(
                connessione,
                limite=limite,
            )
        )
    aggiornati = 0
    for voce in dispatch_da_sincronizzare:
        try:
            aggiornati += await _sincronizza_dispatch(
                apri_transazione,
                sincronizzatore,
                voce,
            )
        except SQLAlchemyError as errore:
            logger.error(
                "open311_sync_database_error",
                extra={
                    "report_id": str(voce.report_id),
                    "error_type": type(errore).__name__,
                },
            )
    return aggiornati


async def _sincronizza_dispatch(
    apri_transazione: ApriTransazione,
    sincronizzatore: SincronizzatoreOpen311,
    voce: repository_dispatch.DispatchDaSincronizzare,
) -> int:
    stato_esterno = await sincronizzatore.recupera_stato(voce)
    stato_successivo = mappa_stato_open311(stato_esterno)
    if stato_successivo is None:
        logger.warning(
            "open311_sync_status_not_mapped",
            extra={
                "report_id": str(voce.report_id),
                "stato_esterno": stato_esterno,
            },
        )
        return 0
    if stato_successivo.value == voce.stato_interno:
        return 0
    async with apri_transazione() as connessione:
        segnalazione = await repository_segnalazioni.carica_segnalazione_per_id(
            connessione,
            voce.report_id,
        )
        if segnalazione is None:
            return 0
        stato_corrente = StatoSegnalazione(segnalazione.status)
        if stato_corrente == stato_successivo:
            return 0
        try:
            valida_transizione_stato(stato_corrente, stato_successivo)
        except TransizioneNonAmmessa as errore:
            logger.warning(
                "open311_sync_transition_rejected",
                extra={
                    "report_id": str(voce.report_id),
                    "stato_precedente": stato_corrente.value,
                    "stato_successivo": stato_successivo.value,
                    "errore": str(errore),
                },
            )
            return 0
        await registra_cambio_stato(
            connessione,
            segnalazione,
            stato_successivo,
            actor_type=ATTORE_SINCRONIZZAZIONE,
            actor_id=None,
            note_public=None,
        )
    logger.info(
        "open311_sync_status_updated",
        extra={
            "report_id": str(voce.report_id),
            "stato_precedente": voce.stato_interno,
            "stato_successivo": stato_successivo.value,
        },
    )
    return 1
