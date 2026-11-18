from __future__ import annotations

import httpx
from aiuto_autenticazione import intestazione_bearer
from aiuto_dispatch import (
    URL_PUBBLICA_DI_PROVA,
    InvioEmailFinto,
    cifrario_email_di_prova,
    costruisci_elaboratore,
    crea_scenario_segnalazione,
    leggi_evento_outbox,
    leggi_segnalazione,
    trasporto_che_fallisce,
)
from aiuto_segnalazioni import crea_utente_autenticato
from aiuto_tenant import (
    CONFINE_COMUNE_A,
    POSIZIONE_COMUNE_A,
    crea_comune,
    crea_evento_outbox,
    crea_segnalazione,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.dispatch import STATO_INVIATA_EMAIL
from app.dominio.elaboratore_notifiche import ElaboratoreNotifiche
from app.dominio.esempio_segnalazione import StatoSegnalazione
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


async def test_worker_invia_email_notifica(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    _, autore_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        email="autore.notifica@example.com",
        nickname="autore_notifica",
    )
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
    )
    async with motore_amministratore.begin() as connessione:
        report_id = await crea_segnalazione(
            connessione,
            municipality_id=comune,
            category_id=categoria_altro,
            public_ref="CR-2026-000777",
            posizione=POSIZIONE_COMUNE_A,
            author_id=autore_id,
        )
    cambio = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={"status": StatoSegnalazione.IN_CORSO.value},
        headers=intestazione_bearer(token_operatore),
    )
    invio_email = InvioEmailFinto()
    gestore = GestoreEventiPredefinito(
        costruisci_elaboratore(
            adattatore=AdattatoreOpen311(),
            invio_email=invio_email,
        ),
        elaboratore_notifiche=ElaboratoreNotifiche(
            invio_email=invio_email,
            cifrario_email=cifrario_email_di_prova(),
            url_pubblica_base=URL_PUBBLICA_DI_PROVA,
        ),
    )

    elaborati = await elabora_eventi_in_sospeso(
        motore_applicazione,
        gestore,
        limite=5,
    )

    assert cambio.status_code == 200, cambio.text
    assert elaborati == 1
    assert len(invio_email.notifiche_inviate) == 1
    destinatario, oggetto, corpo = invio_email.notifiche_inviate[0]
    assert destinatario == "autore.notifica@example.com"
    assert "CR-2026-000777" in oggetto
    assert "In corso" in corpo
