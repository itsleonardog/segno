from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from aiuto_dispatch import (
    CHIAVE_API_DI_PROVA,
    EMAIL_FALLBACK_DI_PROVA,
    RIFERIMENTO_PUBBLICO_DI_PROVA,
    AdattatoreOpen311Finto,
    InvioEmailFinto,
    RisolutoreChiaviFinto,
    cifrario_email_di_prova,
    costruisci_elaboratore,
    crea_scenario_segnalazione,
    leggi_segnalazione,
    leggi_tentativi,
    trasporto_che_fallisce,
    trasporto_con_risposta,
)
from aiuto_tenant import crea_segnalazione
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.dispatch import (
    STATO_FALLITA,
    STATO_INVIATA_EMAIL,
    STATO_INVIATA_OPEN311,
    STATO_PENDENTE,
    RisultatoOpen311,
)
from app.infrastruttura.adattatore_open311 import AdattatoreOpen311
from app.infrastruttura.database import transazione_con_contesto

ISTANTE_DI_PROVA = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
ENDPOINT_OPEN311 = "https://api.comune.test/v2/requests"
RIFERIMENTO_CHIAVE = "comune-test"


async def _elabora(
    motore: AsyncEngine,
    elaboratore,
    report_id,
):
    async with transazione_con_contesto(motore, scope="system") as connessione:
        return await elaboratore.elabora_evento_creazione_segnalazione(
            connessione,
            report_id,
        )


async def test_adattatore_open311_successo(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="open311",
        api_key_ref=RIFERIMENTO_CHIAVE,
        endpoint_open311=ENDPOINT_OPEN311,
    )
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311(
            trasporto=trasporto_con_risposta(
                [{"service_request_id": "SR-2026-1"}],
            )
        ),
        invio_email=InvioEmailFinto(),
        risolutore_chiavi=RisolutoreChiaviFinto(
            {RIFERIMENTO_CHIAVE: CHIAVE_API_DI_PROVA}
        ),
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == STATO_INVIATA_OPEN311
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_INVIATA_OPEN311
    tentativi = await leggi_tentativi(motore_amministratore, report_id)
    assert len(tentativi) == 1
    assert tentativi[0]["channel"] == "open311"
    assert tentativi[0]["status"] == "succeeded"
    assert tentativi[0]["provider_request_id"] == "SR-2026-1"


async def test_adattatore_open311_timeout(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="open311",
        endpoint_open311=ENDPOINT_OPEN311,
    )
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311(
            trasporto=trasporto_che_fallisce(httpx.ReadTimeout("timeout simulato"))
        ),
        invio_email=InvioEmailFinto(),
        istante=lambda: ISTANTE_DI_PROVA,
    )

    primo_esito = await _elabora(motore_applicazione, elaboratore, report_id)
    secondo_esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert primo_esito.richiede_ritentativo is True
    assert secondo_esito.richiede_ritentativo is True
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_PENDENTE
    tentativi = await leggi_tentativi(motore_amministratore, report_id)
    assert [tentativo["status"] for tentativo in tentativi] == [
        "failed_retryable",
        "failed_retryable",
    ]
    assert tentativi[0]["next_attempt_at"] == ISTANTE_DI_PROVA + timedelta(minutes=1)
    assert tentativi[1]["next_attempt_at"] == ISTANTE_DI_PROVA + timedelta(minutes=5)


async def test_adattatore_open311_400_attiva_fallback_email(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="open311_then_email",
        endpoint_open311=ENDPOINT_OPEN311,
    )
    invio_email = InvioEmailFinto()
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311(
            trasporto=trasporto_con_risposta(
                {"error": "payload non valido"},
                status_code=400,
            )
        ),
        invio_email=invio_email,
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == STATO_INVIATA_EMAIL
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_INVIATA_EMAIL
    tentativi = await leggi_tentativi(motore_amministratore, report_id)
    per_canale = {tentativo["channel"]: tentativo for tentativo in tentativi}
    assert per_canale["open311"]["status"] == "failed_permanent"
    assert per_canale["open311"]["error_code"] == "permanente"
    assert per_canale["email"]["status"] == "succeeded"
    assert invio_email.messaggi[0][0] == EMAIL_FALLBACK_DI_PROVA


async def test_adattatore_open311_2xx_senza_identificativo_e_ambiguo(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="open311_then_email",
        endpoint_open311=ENDPOINT_OPEN311,
    )
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311(
            trasporto=trasporto_con_risposta({"esito": "ok"}, status_code=200)
        ),
        invio_email=InvioEmailFinto(),
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == STATO_INVIATA_EMAIL
    tentativi = await leggi_tentativi(motore_amministratore, report_id)
    primo_tentativo = tentativi[0]
    assert primo_tentativo["channel"] == "open311"
    assert primo_tentativo["status"] == "failed_permanent"
    assert primo_tentativo["error_code"] == "ambiguo"


async def test_fallback_email(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="email",
    )
    invio_email = InvioEmailFinto()
    adattatore = AdattatoreOpen311Finto(risultato=RisultatoOpen311(None, None, None))
    elaboratore = costruisci_elaboratore(
        adattatore=adattatore,
        invio_email=invio_email,
        cifrario=cifrario_email_di_prova(),
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == STATO_INVIATA_EMAIL
    assert adattatore.chiamate == []
    destinatario, contenuto = invio_email.messaggi[0]
    assert destinatario == EMAIL_FALLBACK_DI_PROVA
    assert RIFERIMENTO_PUBBLICO_DI_PROVA in contenuto.oggetto
    assert (
        f"https://segnalazioni.test/reports/{RIFERIMENTO_PUBBLICO_DI_PROVA}"
        in contenuto.corpo
    )
    assert "45.050000, 9.050000" in contenuto.corpo
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_INVIATA_EMAIL
    tentativi = await leggi_tentativi(motore_amministratore, report_id)
    assert len(tentativi) == 1
    assert tentativi[0]["channel"] == "email"
    assert tentativi[0]["provider_request_id"] == invio_email.message_id


async def test_nessun_canale_configurato_chiude_in_fallita(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    _, report_id = await crea_scenario_segnalazione(
        motore_amministratore,
        category_id=categoria_altro,
        dispatch_mode="email",
        fallback_email=None,
        fallback_active=False,
    )
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311Finto(risultato=RisultatoOpen311(None, None, None)),
        invio_email=InvioEmailFinto(),
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == STATO_FALLITA
    segnalazione = await leggi_segnalazione(motore_amministratore, report_id)
    assert segnalazione["dispatch_state"] == STATO_FALLITA
    assert await leggi_tentativi(motore_amministratore, report_id) == []


async def test_segnalazione_fuori_copertura_non_viene_instradata(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        report_id = await crea_segnalazione(
            connessione,
            municipality_id=None,
            category_id=categoria_altro,
            public_ref="CR-2026-000999",
            posizione="SRID=4326;POINT(9.05 45.05)",
            dispatch_state="out_of_jurisdiction",
        )
    elaboratore = costruisci_elaboratore(
        adattatore=AdattatoreOpen311Finto(risultato=RisultatoOpen311(None, None, None)),
        invio_email=InvioEmailFinto(),
    )

    esito = await _elabora(motore_applicazione, elaboratore, report_id)

    assert esito.stato_dispatch == "out_of_jurisdiction"
    assert await leggi_tentativi(motore_amministratore, report_id) == []
