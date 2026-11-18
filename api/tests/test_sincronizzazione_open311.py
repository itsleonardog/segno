from __future__ import annotations

from aiuto_dispatch import (
    RisolutoreChiaviFinto,
    crea_scenario_segnalazione,
    leggi_segnalazione,
    trasporto_con_risposta,
)
from aiuto_tenant import crea_dispatch
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.esempio_segnalazione import StatoSegnalazione
from app.dominio.sincronizzazione_open311 import (
    SincronizzatoreOpen311,
    mappa_stato_open311,
    sincronizza_open311,
)
from app.infrastruttura.adattatore_open311 import AdattatoreOpen311
from app.infrastruttura.database import transazione_con_contesto

ENDPOINT_OPEN311 = "https://api.comune.test/v2/requests"
IDENTIFICATIVO_RICHIESTA = "SR-2026-42"


async def test_sync_open311_mock_aggiorna_stato_interno(
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
        await crea_dispatch(
            connessione,
            report_id=report_id,
            municipality_id=comune,
            channel="open311",
            status="succeeded",
            provider_request_id=IDENTIFICATIVO_RICHIESTA,
        )
    sincronizzatore = SincronizzatoreOpen311(
        adattatore_open311=AdattatoreOpen311(
            trasporto=trasporto_con_risposta(
                {
                    "service_request_id": IDENTIFICATIVO_RICHIESTA,
                    "status": "in_progress",
                }
            )
        ),
        risolutore_chiavi=RisolutoreChiaviFinto(),
    )

    aggiornati = await sincronizza_open311(
        lambda: transazione_con_contesto(motore_applicazione, scope="system"),
        sincronizzatore,
    )
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)

    assert aggiornati == 1
    assert segnalazione["status"] == StatoSegnalazione.IN_CORSO.value


async def test_sync_open311_ignora_stato_non_riconosciuto(
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
        await crea_dispatch(
            connessione,
            report_id=report_id,
            municipality_id=comune,
            channel="open311",
            status="succeeded",
            provider_request_id=IDENTIFICATIVO_RICHIESTA,
        )
    sincronizzatore = SincronizzatoreOpen311(
        adattatore_open311=AdattatoreOpen311(
            trasporto=trasporto_con_risposta({"status": "unknown_external_state"})
        ),
        risolutore_chiavi=RisolutoreChiaviFinto(),
    )

    aggiornati = await sincronizza_open311(
        lambda: transazione_con_contesto(motore_applicazione, scope="system"),
        sincronizzatore,
    )
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)

    assert aggiornati == 0
    assert segnalazione["status"] == StatoSegnalazione.APERTA.value


def test_mappa_stato_open311_normalizza_le_varianti() -> None:
    assert mappa_stato_open311("Closed") == StatoSegnalazione.CHIUSA
    assert mappa_stato_open311("in-progress") == StatoSegnalazione.IN_CORSO
    assert mappa_stato_open311(None) is None
