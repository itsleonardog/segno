from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.dominio.dispatch import EVENTO_SEGNALAZIONE_CREATA, EsitoElaborazione
from app.dominio.elaboratore_eventi import ElaboratoreEventi
from app.infrastruttura.adattatore_open311 import (
    AdattatoreOpen311,
    SegretiOpen311DaAmbiente,
)
from app.infrastruttura.configurazione import (
    ConfigurazioneDispatch,
    leggi_configurazione_database,
    leggi_configurazione_dispatch,
)
from app.infrastruttura.database import crea_motore, transazione_con_contesto
from app.infrastruttura.dipendenze import get_cifrario_email, get_email_sender
from app.infrastruttura.outbox import (
    EventoOutbox,
    leggi_eventi_da_processare,
    marca_evento_processato,
    registra_errore_evento,
)

logger = logging.getLogger(__name__)

LIMITE_EVENTI_PER_CICLO = 10
STATO_EVENTO_IGNORATO = "ignored"


class GestoreEventi(Protocol):
    async def __call__(
        self,
        connessione: AsyncConnection,
        evento: EventoOutbox,
    ) -> EsitoElaborazione: ...


class GestoreEventiPredefinito:
    """Instrada gli eventi di segnalazione verso l'elaboratore di dominio."""

    def __init__(self, elaboratore: ElaboratoreEventi) -> None:
        self._elaboratore = elaboratore

    async def __call__(
        self,
        connessione: AsyncConnection,
        evento: EventoOutbox,
    ) -> EsitoElaborazione:
        if evento.event_type != EVENTO_SEGNALAZIONE_CREATA:
            logger.warning(
                "outbox_event_type_ignored",
                extra={
                    "event_id": str(evento.id),
                    "event_type": evento.event_type,
                    "aggregate_type": evento.aggregate_type,
                },
            )
            return EsitoElaborazione(stato_dispatch=STATO_EVENTO_IGNORATO)
        return await self._elaboratore.elabora_evento_creazione_segnalazione(
            connessione,
            evento.aggregate_id,
        )


async def elabora_eventi_in_sospeso(
    motore: AsyncEngine,
    gestore: GestoreEventi,
    *,
    limite: int = LIMITE_EVENTI_PER_CICLO,
) -> int:
    """Elabora al massimo limite eventi e restituisce quanti sono stati chiusi."""
    elaborati = 0
    for _ in range(limite):
        async with transazione_con_contesto(motore, scope="system") as connessione:
            eventi = await leggi_eventi_da_processare(connessione, limite=1)
            if not eventi:
                break
            if await _elabora_singolo_evento(connessione, eventi[0], gestore):
                elaborati += 1
    return elaborati


async def _elabora_singolo_evento(
    connessione: AsyncConnection,
    evento: EventoOutbox,
    gestore: GestoreEventi,
) -> bool:
    try:
        esito = await gestore(connessione, evento)
    except Exception as errore:
        # L'evento resta in coda: un guasto transitorio deve poter riprovare.
        logger.error(
            "outbox_event_failed",
            extra={
                "event_id": str(evento.id),
                "event_type": evento.event_type,
                "error_type": type(errore).__name__,
            },
        )
        await registra_errore_evento(
            connessione,
            evento_id=evento.id,
            messaggio_errore=f"{type(errore).__name__}: {errore}",
        )
        return False
    if esito.richiede_ritentativo:
        logger.warning(
            "outbox_event_retry_scheduled",
            extra={
                "event_id": str(evento.id),
                "event_type": evento.event_type,
            },
        )
        await registra_errore_evento(
            connessione,
            evento_id=evento.id,
            messaggio_errore=esito.messaggio_errore or "retryable dispatch failure",
        )
        return False
    await marca_evento_processato(connessione, evento.id)
    return True


async def ciclo_worker(
    motore: AsyncEngine,
    gestore: GestoreEventi,
    *,
    pausa_secondi: float,
    limite: int = LIMITE_EVENTI_PER_CICLO,
) -> None:
    """Esegue il polling dell'outbox finché il processo non viene fermato."""
    logger.info("worker_started", extra={"pausa_secondi": pausa_secondi})
    while True:
        try:
            elaborati = await elabora_eventi_in_sospeso(
                motore,
                gestore,
                limite=limite,
            )
        except SQLAlchemyError as errore:
            logger.error(
                "worker_batch_failed",
                extra={"error_type": type(errore).__name__},
            )
            await asyncio.sleep(pausa_secondi)
            continue
        if elaborati == 0:
            await asyncio.sleep(pausa_secondi)


def crea_gestore_predefinito(
    configurazione_dispatch: ConfigurazioneDispatch,
) -> GestoreEventiPredefinito:
    elaboratore = ElaboratoreEventi(
        adattatore_open311=AdattatoreOpen311(),
        invio_email=get_email_sender(),
        cifrario_email=get_cifrario_email(),
        risolutore_chiavi=SegretiOpen311DaAmbiente(
            configurazione_dispatch.prefisso_segreto_open311
        ),
        url_pubblica_base=configurazione_dispatch.url_pubblica_base,
    )
    return GestoreEventiPredefinito(elaboratore)


async def esegui_worker() -> None:
    configurazione_database = leggi_configurazione_database()
    configurazione_dispatch = leggi_configurazione_dispatch()
    motore = crea_motore(configurazione_database.url_applicazione)
    try:
        await ciclo_worker(
            motore,
            crea_gestore_predefinito(configurazione_dispatch),
            pausa_secondi=configurazione_dispatch.pausa_worker_secondi,
        )
    finally:
        await motore.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(esegui_worker())


if __name__ == "__main__":
    main()
