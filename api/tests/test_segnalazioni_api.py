from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from aiuto_autenticazione import intestazione_bearer
from aiuto_segnalazioni import (
    conta_righe_per_report,
    corpo_creazione,
    crea_segnalazione_api,
    crea_utente_autenticato,
    intestazioni_creazione,
    ottieni_id_categoria,
)
from aiuto_tenant import CONFINE_COMUNE_A, crea_comune
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.esempio_segnalazione import StatoSegnalazione


async def test_crea_segnalazione_fuori_copertura(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)

    risposta = await crea_segnalazione_api(
        client_auth,
        token,
        categoria_altro,
        lat=0.0,
        lng=0.0,
    )

    assert risposta.status_code == 201, risposta.text
    corpo = risposta.json()
    assert corpo["municipality_id"] is None
    assert corpo["dispatch_state"] == "out_of_jurisdiction"
    assert corpo["public_ref"].startswith(f"CR-{datetime.now(UTC).year}-")


async def test_crea_segnalazione_transazione(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)

    risposta = await crea_segnalazione_api(client_auth, token, categoria_altro)

    assert risposta.status_code == 201, risposta.text
    report_id = uuid.UUID(risposta.json()["id"])
    assert (
        await conta_righe_per_report(
            motore_amministratore,
            "report",
            "id",
            report_id,
        )
        == 1
    )
    assert (
        await conta_righe_per_report(
            motore_amministratore,
            "report_status_event",
            "report_id",
            report_id,
        )
        == 1
    )
    assert (
        await conta_righe_per_report(
            motore_amministratore,
            "outbox_event",
            "aggregate_id",
            report_id,
        )
        == 1
    )
    evento_outbox = await _leggi_evento_outbox(motore_amministratore, report_id)
    assert evento_outbox["event_type"] == "report.created"


async def test_idempotenza(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)
    chiave = f"chiave-{uuid.uuid4()}"
    intestazioni = intestazioni_creazione(token, chiave)
    corpo = corpo_creazione(categoria_altro)

    prima = await client_auth.post("/v1/reports", json=corpo, headers=intestazioni)
    seconda = await client_auth.post("/v1/reports", json=corpo, headers=intestazioni)

    assert prima.status_code == 201, prima.text
    assert seconda.status_code == 201, seconda.text
    assert prima.json()["id"] == seconda.json()["id"]
    assert prima.json()["public_ref"] == seconda.json()["public_ref"]
    assert await _conta_record_idempotenza(motore_amministratore) == 1
    assert await _conta_totale(motore_amministratore, "report") == 1


async def test_get_segnalazioni_filtri(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    categoria_strade = await ottieni_id_categoria(motore_amministratore, "strade")
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)
    prima = await crea_segnalazione_api(
        client_auth,
        token,
        categoria_altro,
        lat=45.05,
        lng=9.05,
        title="Prima",
    )
    seconda = await crea_segnalazione_api(
        client_auth,
        token,
        categoria_altro,
        lat=45.06,
        lng=9.06,
        title="Seconda",
    )
    terza = await crea_segnalazione_api(
        client_auth,
        token,
        categoria_strade,
        lat=46.0,
        lng=10.0,
        title="Terza",
    )
    assert prima.status_code == 201, prima.text
    assert seconda.status_code == 201, seconda.text
    assert terza.status_code == 201, terza.text
    await _imposta_stato(motore_amministratore, seconda.json()["id"], "in_progress")

    per_riquadro = await client_auth.get(
        "/v1/reports",
        params={
            "lat_min": 45.0,
            "lat_max": 45.1,
            "lng_min": 9.0,
            "lng_max": 9.1,
        },
    )
    per_categoria = await client_auth.get(
        "/v1/reports",
        params={"category": "altro"},
    )
    per_categoria_strade = await client_auth.get(
        "/v1/reports",
        params={"category": "strade"},
    )
    per_stato = await client_auth.get(
        "/v1/reports",
        params={"status": StatoSegnalazione.IN_CORSO.value},
    )

    assert per_riquadro.status_code == 200, per_riquadro.text
    assert len(per_riquadro.json()["items"]) == 2
    assert len(per_categoria.json()["items"]) == 2
    assert len(per_categoria_strade.json()["items"]) == 1
    assert len(per_stato.json()["items"]) == 1
    assert per_stato.json()["items"][0]["id"] == seconda.json()["id"]

    prima_pagina = await client_auth.get("/v1/reports", params={"limit": 1})
    assert len(prima_pagina.json()["items"]) == 1
    assert prima_pagina.json()["next_cursor"] is not None
    seconda_pagina = await client_auth.get(
        "/v1/reports",
        params={"limit": 1, "cursor": prima_pagina.json()["next_cursor"]},
    )
    assert len(seconda_pagina.json()["items"]) == 1
    assert (
        seconda_pagina.json()["items"][0]["id"] != prima_pagina.json()["items"][0]["id"]
    )


async def test_patch_segnalazione_non_autore_403(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token_autore, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
    )
    token_altro, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
    )
    creata = await crea_segnalazione_api(client_auth, token_autore, categoria_altro)
    assert creata.status_code == 201, creata.text

    risposta = await client_auth.patch(
        f"/v1/reports/{creata.json()['id']}",
        json={"title": "Titolo modificato"},
        headers=intestazione_bearer(token_altro),
    )

    assert risposta.status_code == 403


async def test_patch_segnalazione_scaduta_400(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    report_id = creata.json()["id"]
    async with motore_amministratore.begin() as connessione:
        await connessione.execute(
            text("""
                UPDATE report SET created_at = now() - interval '25 hours'
                WHERE id = CAST(:report_id AS uuid)
                """),
            {"report_id": report_id},
        )

    risposta = await client_auth.patch(
        f"/v1/reports/{report_id}",
        json={"title": "Titolo modificato"},
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 400


async def test_cambio_stato_operatore(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await crea_comune(connessione, confine=CONFINE_COMUNE_A)
    token, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
    )
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    report_id = uuid.UUID(creata.json()["id"])

    risposta = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={
            "status": StatoSegnalazione.IN_CORSO.value,
            "note_public": "Presa in carico dall'ufficio tecnico.",
        },
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["status"] == StatoSegnalazione.IN_CORSO.value
    assert (
        await conta_righe_per_report(
            motore_amministratore,
            "report_status_event",
            "report_id",
            report_id,
        )
        == 2
    )
    assert (
        await conta_righe_per_report(
            motore_amministratore,
            "outbox_event",
            "aggregate_id",
            report_id,
        )
        == 2
    )
    evento = await _leggi_ultimo_evento_stato(motore_amministratore, report_id)
    assert evento["from_status"] == StatoSegnalazione.APERTA.value
    assert evento["to_status"] == StatoSegnalazione.IN_CORSO.value
    assert evento["actor_type"] == "municipality"
    assert evento["note_public"] == "Presa in carico dall'ufficio tecnico."
    assert evento["is_public"] is True
    evento_outbox = await _leggi_evento_outbox_per_tipo(
        motore_amministratore,
        report_id,
        "report.status_changed",
    )
    assert evento_outbox is not None


async def test_cambio_stato_non_operatore_403(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, _ = await crea_utente_autenticato(client_auth, motore_amministratore)
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    report_id = creata.json()["id"]

    risposta = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={"status": StatoSegnalazione.IN_CORSO.value},
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 403
    assert await _leggi_stato(motore_amministratore, report_id) == "open"


async def test_cambio_stato_transizione_non_valida(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, _ = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        operatore=True,
    )
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    report_id = creata.json()["id"]

    risposta = await client_auth.patch(
        f"/v1/reports/{report_id}/status",
        json={"status": StatoSegnalazione.RISOLTA.value},
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 400
    assert await _leggi_stato(motore_amministratore, report_id) == "open"


async def _imposta_stato(
    motore: AsyncEngine,
    report_id: str,
    stato: str,
) -> None:
    async with motore.begin() as connessione:
        await connessione.execute(
            text("""
                UPDATE report SET status = CAST(:stato AS report_status)
                WHERE id = CAST(:report_id AS uuid)
                """),
            {"stato": stato, "report_id": report_id},
        )


async def _leggi_stato(motore: AsyncEngine, report_id: str) -> str:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("SELECT status FROM report WHERE id = CAST(:report_id AS uuid)"),
            {"report_id": report_id},
        )
    return str(esito.scalar_one())


async def _leggi_evento_outbox(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> dict[str, Any]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT event_type FROM outbox_event
                WHERE aggregate_id = CAST(:report_id AS uuid)
                """),
            {"report_id": str(report_id)},
        )
    return dict(esito.mappings().one())


async def _leggi_evento_outbox_per_tipo(
    motore: AsyncEngine,
    report_id: uuid.UUID,
    event_type: str,
) -> dict[str, Any] | None:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT event_type FROM outbox_event
                WHERE aggregate_id = CAST(:report_id AS uuid)
                  AND event_type = :event_type
                """),
            {"report_id": str(report_id), "event_type": event_type},
        )
    riga = esito.mappings().one_or_none()
    return dict(riga) if riga else None


async def _leggi_ultimo_evento_stato(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> dict[str, Any]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT from_status, to_status, actor_type, note_public, is_public
                FROM report_status_event
                WHERE report_id = CAST(:report_id AS uuid)
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """),
            {"report_id": str(report_id)},
        )
    return dict(esito.mappings().one())


async def _conta_record_idempotenza(motore: AsyncEngine) -> int:
    return await _conta_totale(motore, "idempotency_record")


async def _conta_totale(motore: AsyncEngine, tabella: str) -> int:
    async with motore.connect() as connessione:
        esito = await connessione.execute(text(f'SELECT count(*) FROM "{tabella}"'))
    return int(esito.scalar_one())
