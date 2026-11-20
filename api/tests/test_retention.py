from __future__ import annotations

import uuid

from aiuto_tenant import crea_utente
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.worker import esegui_retention


async def test_retention_elimina_dati_scaduti(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
) -> None:
    async with motore_amministratore.begin() as connessione:
        utente_id = await crea_utente(connessione)
        await _inserisci_dati_scaduti(connessione, utente_id)

    esito = await esegui_retention(motore_applicazione)

    assert esito.refresh_token_rimossi == 1
    assert esito.token_verifica_rimossi == 1
    assert esito.token_reset_rimossi == 1
    assert esito.notifiche_rimosse == 1
    assert esito.idempotenze_rimosse == 1
    assert await _conta(motore_amministratore, "refresh_token") == 0
    assert await _conta(motore_amministratore, "email_verification_token") == 0
    assert await _conta(motore_amministratore, "password_reset_token") == 0
    assert await _conta(motore_amministratore, "idempotency_record") == 0
    # La notifica non letta resta: la retention copre solo quelle lette da oltre
    # dodici mesi.
    assert await _conta(motore_amministratore, "notification") == 1


async def _inserisci_dati_scaduti(connessione, utente_id: uuid.UUID) -> None:
    await connessione.execute(
        text("""
            INSERT INTO refresh_token (
                id, user_id, token_hash, family_id, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid), :token_hash,
                CAST(:family_id AS uuid), now() - interval '1 day'
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "token_hash": f"refresh-{uuid.uuid4()}",
            "family_id": str(uuid.uuid4()),
        },
    )
    await connessione.execute(
        text("""
            INSERT INTO email_verification_token (
                id, user_id, token_hash, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid), :token_hash,
                now() - interval '1 day'
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "token_hash": f"verifica-{uuid.uuid4()}",
        },
    )
    await connessione.execute(
        text("""
            INSERT INTO password_reset_token (
                id, user_id, token_hash, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid), :token_hash,
                now() - interval '1 day'
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "token_hash": f"reset-{uuid.uuid4()}",
        },
    )
    await connessione.execute(
        text("""
            INSERT INTO notification (
                id, user_id, type, channel, dedupe_key, read_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid),
                'status_changed', 'inapp', :dedupe_key,
                now() - interval '13 months'
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "dedupe_key": f"letta-{uuid.uuid4()}",
        },
    )
    await connessione.execute(
        text("""
            INSERT INTO notification (
                id, user_id, type, channel, dedupe_key
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid),
                'status_changed', 'inapp', :dedupe_key
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "dedupe_key": f"non-letta-{uuid.uuid4()}",
        },
    )
    await connessione.execute(
        text("""
            INSERT INTO idempotency_record (
                id, actor_id, endpoint, idempotency_key, request_hash, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:utente_id AS uuid), '/v1/reports',
                :chiave, :request_hash, now() - interval '1 hour'
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "utente_id": str(utente_id),
            "chiave": f"chiave-{uuid.uuid4()}",
            "request_hash": str(uuid.uuid4()),
        },
    )


async def _conta(motore: AsyncEngine, tabella: str) -> int:
    async with motore.connect() as connessione:
        esito = await connessione.execute(text(f'SELECT count(*) FROM "{tabella}"'))
        return int(esito.scalar_one())
