from __future__ import annotations

import uuid
from typing import Any

import httpx
from aiuto_autenticazione import intestazione_bearer
from aiuto_segnalazioni import crea_segnalazione_api, crea_utente_autenticato
from aiuto_tenant import (
    CONFINE_COMUNE_A,
    POSIZIONE_COMUNE_A,
    crea_comune,
    crea_dispatch,
    crea_segnalazione,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.esempio_segnalazione import StatoSegnalazione


async def test_api_admin_accesso_negato(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
) -> None:
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)

    risposta = await client_auth.get(
        "/v1/admin/reports",
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 403, risposta.text


async def test_api_admin_cambio_stato(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_autore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
    )
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
        municipality_id=comune,
    )
    creata = await crea_segnalazione_api(client_auth, token_autore, categoria_altro)
    report_id = creata.json()["id"]

    elenco = await client_auth.get(
        "/v1/admin/reports",
        headers=intestazione_bearer(token_operatore),
    )
    cambio = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={
            "status": StatoSegnalazione.IN_CORSO.value,
            "note_public": "Presa in carico.",
        },
        headers=intestazione_bearer(token_operatore),
    )
    dettaglio = await client_auth.get(
        f"/v1/admin/reports/{report_id}",
        headers=intestazione_bearer(token_operatore),
    )

    assert elenco.status_code == 200, elenco.text
    assert [voce["id"] for voce in elenco.json()["items"]] == [report_id]
    assert cambio.status_code == 200, cambio.text
    assert dettaglio.status_code == 200, dettaglio.text
    assert dettaglio.json()["status"] == StatoSegnalazione.IN_CORSO.value
    assert len(dettaglio.json()["status_events"]) == 2


async def test_admin_aggiunge_nota_interna(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_autore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
    )
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
        municipality_id=comune,
    )
    creata = await crea_segnalazione_api(client_auth, token_autore, categoria_altro)
    report_id = creata.json()["id"]

    nota = await client_auth.post(
        f"/v1/admin/reports/{report_id}/comments",
        json={"body": "Verificare il palo prima dell'intervento."},
        headers=intestazione_bearer(token_operatore),
    )
    dettaglio = await client_auth.get(
        f"/v1/admin/reports/{report_id}",
        headers=intestazione_bearer(token_operatore),
    )
    pubblico = await client_auth.get(
        f"/v1/reports/{creata.json()['public_ref']}",
    )

    assert nota.status_code == 201, nota.text
    assert dettaglio.json()["internal_notes"][0]["body"].startswith("Verificare")
    assert "Verificare il palo" not in pubblico.text


async def test_admin_fallimenti_e_riprova(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
        municipality_id=comune,
    )
    async with motore_amministratore.begin() as connessione:
        report_id = await crea_segnalazione(
            connessione,
            municipality_id=comune,
            category_id=categoria_altro,
            public_ref="CR-2026-000888",
            posizione=POSIZIONE_COMUNE_A,
        )
        await crea_dispatch(
            connessione,
            report_id=report_id,
            municipality_id=comune,
            channel="open311",
            status="failed_permanent",
        )

    fallimenti = await client_auth.get(
        "/v1/admin/dispatch-failures",
        headers=intestazione_bearer(token_operatore),
    )
    riprova = await client_auth.post(
        f"/v1/admin/reports/{report_id}/dispatch/retry",
        headers=intestazione_bearer(token_operatore),
    )
    evento = await _leggi_evento_dispatch(motore_amministratore, report_id)

    assert fallimenti.status_code == 200, fallimenti.text
    assert len(fallimenti.json()["items"]) == 1
    assert fallimenti.json()["items"][0]["public_ref"] == "CR-2026-000888"
    assert riprova.status_code == 202, riprova.text
    assert evento["event_type"] == "report.dispatch_retry"


async def _leggi_evento_dispatch(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> dict[str, Any]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT event_type FROM outbox_event
                WHERE aggregate_id = CAST(:report_id AS uuid)
                  AND event_type = 'report.dispatch_retry'
                """),
            {"report_id": str(report_id)},
        )
    return dict(esito.mappings().one())
