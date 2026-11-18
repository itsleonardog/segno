from __future__ import annotations

import uuid
from typing import Any

import httpx
from aiuto_autenticazione import intestazione_bearer
from aiuto_segnalazioni import crea_segnalazione_api, crea_utente_autenticato
from aiuto_tenant import CONFINE_COMUNE_A, crea_comune
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.esempio_segnalazione import StatoSegnalazione
from app.dominio.notifica import TIPO_CAMBIO_STATO


async def test_notifica_creata_al_cambio_stato(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_autore, autore_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
    )
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
    )
    creata = await crea_segnalazione_api(client_auth, token_autore, categoria_altro)
    report_id = creata.json()["id"]

    cambio = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={"status": StatoSegnalazione.IN_CORSO.value},
        headers=intestazione_bearer(token_operatore),
    )
    notifica = await _leggi_notifica(motore_amministratore, uuid.UUID(report_id))
    elenco = await client_auth.get(
        "/v1/notifications",
        headers=intestazione_bearer(token_autore),
    )

    assert cambio.status_code == 200, cambio.text
    assert notifica["user_id"] == autore_id
    assert notifica["type"] == TIPO_CAMBIO_STATO
    assert notifica["read_at"] is None
    assert elenco.status_code == 200, elenco.text
    assert elenco.json()["unread_count"] == 1
    assert len(elenco.json()["items"]) == 1
    assert elenco.json()["items"][0]["payload"]["to_status"] == "in_progress"


async def test_notifica_segnata_come_letta(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_autore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        municipality_id=comune,
    )
    token_operatore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
        municipality_id=comune,
    )
    creata = await crea_segnalazione_api(client_auth, token_autore, categoria_altro)
    report_id = creata.json()["id"]
    await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={"status": StatoSegnalazione.IN_CORSO.value},
        headers=intestazione_bearer(token_operatore),
    )
    elenco = await client_auth.get(
        "/v1/notifications",
        headers=intestazione_bearer(token_autore),
    )
    notifica_id = elenco.json()["items"][0]["id"]

    lettura = await client_auth.patch(
        f"/v1/notifications/{notifica_id}/read",
        headers=intestazione_bearer(token_autore),
    )
    dopo_lettura = await client_auth.get(
        "/v1/notifications",
        headers=intestazione_bearer(token_autore),
    )

    assert lettura.status_code == 200, lettura.text
    assert lettura.json()["letta"] is True
    assert dopo_lettura.json()["unread_count"] == 0


async def test_segna_tutte_notifiche_lette(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token_autore, autore_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        municipality_id=comune,
    )
    async with motore_amministratore.begin() as connessione:
        await connessione.execute(
            text("""
                INSERT INTO notification (
                    id, user_id, type, channel, dedupe_key
                )
                VALUES (
                    gen_random_uuid(), CAST(:user_id AS uuid),
                    'status_changed', 'inapp', 'chiave-unica-test'
                )
                """),
            {"user_id": str(autore_id)},
        )

    lettura = await client_auth.post(
        "/v1/notifications/read-all",
        headers=intestazione_bearer(token_autore),
    )
    elenco = await client_auth.get(
        "/v1/notifications",
        headers=intestazione_bearer(token_autore),
    )

    assert lettura.status_code == 200, lettura.text
    assert lettura.json()["aggiornate"] == 1
    assert elenco.json()["unread_count"] == 0


async def _leggi_notifica(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> dict[str, Any]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT user_id, type, channel, read_at
                FROM notification
                WHERE report_id = CAST(:report_id AS uuid)
                """),
            {"report_id": str(report_id)},
        )
    return dict(esito.mappings().one())
