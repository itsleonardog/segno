from __future__ import annotations

import httpx
from aiuto_dispatch import (
    InvioEmailFinto,
    costruisci_elaboratore,
    crea_scenario_segnalazione,
    leggi_evento_outbox,
    leggi_segnalazione,
    trasporto_che_fallisce,
)
from aiuto_tenant import crea_evento_outbox
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.dispatch import STATO_INVIATA_EMAIL
from app.infrastruttura.adattatore_open311 import AdattatoreOpen311
from app.worker import GestoreEventiPredefinito, elabora_eventi_in_sospeso

ENDPOINT_OPEN311 = "https://api.comune.test/v2/requests"


async def test_worker_legge_e_processa_evento(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="email",
    )
    async with motore_amministratore.begin() as connessione:
        evento_id = await crea_evento_outbox(
            connessione,
            tenant_id=comune,
            aggregate_id=report_id,
        )
    gestore = GestoreEventiPredefinito(
        costruisci_elaboratore(
            adattatore=AdattatoreOpen311(),
            invio_email=InvioEmailFinto(),
        )
    )

    elaborati = await elabora_eventi_in_sospeso(
        motore_applicazione,
        gestore,
        limite=5,
    )

    assert elaborati == 1
    evento = await leggi_evento_outbox(motore_amministratore, evento_id)
    assert evento["processed_at"] is not None
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_INVIATA_EMAIL


async def test_worker_rispetta_il_backoff_del_tentativo(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="open311",
        endpoint_open311=ENDPOINT_OPEN311,
    )
    async with motore_amministratore.begin() as connessione:
        evento_id = await crea_evento_outbox(
            connessione,
            tenant_id=comune,
            aggregate_id=report_id,
        )
    gestore = GestoreEventiPredefinito(
        costruisci_elaboratore(
            adattatore=AdattatoreOpen311(
                trasporto=trasporto_che_fallisce(httpx.ReadTimeout("timeout simulato"))
            ),
            invio_email=InvioEmailFinto(),
        )
    )

    primo_ciclo = await elabora_eventi_in_sospeso(
        motore_applicazione,
        gestore,
        limite=5,
    )
    dopo_primo_ciclo = await leggi_evento_outbox(motore_amministratore, evento_id)
    secondo_ciclo = await elabora_eventi_in_sospeso(
        motore_applicazione,
        gestore,
        limite=5,
    )
    dopo_secondo_ciclo = await leggi_evento_outbox(
        motore_amministratore,
        evento_id,
    )

    assert primo_ciclo == 0
    assert dopo_primo_ciclo["processed_at"] is None
    assert dopo_primo_ciclo["attempts"] == 1
    assert secondo_ciclo == 0
    # Il backoff è ancora in corso: il worker non consuma un nuovo tentativo.
    assert dopo_secondo_ciclo["attempts"] == 1
