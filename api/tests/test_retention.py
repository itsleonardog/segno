from __future__ import annotations

import uuid

from aiuto_tenant import (
    CONFINE_COMUNE_A,
    POSIZIONE_COMUNE_A,
    crea_comune,
    crea_segnalazione,
    crea_utente,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.worker import esegui_retention


async def test_retention_elimina_dati_scaduti(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        utente_id = await crea_utente(connessione)
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
        report_id = await crea_segnalazione(
            connessione,
            municipality_id=comune,
            category_id=categoria_altro,
            public_ref="CR-2026-000901",
            posizione=POSIZIONE_COMUNE_A,
        )
        await _inserisci_dati_scaduti(
            connessione,
            utente_id,
            municipality_id=comune,
            report_id=report_id,
        )

    esito = await esegui_retention(motore_applicazione)

    assert esito.refresh_token_rimossi == 1
    assert esito.token_verifica_rimossi == 1
    assert esito.token_reset_rimossi == 1
    assert esito.notifiche_rimosse == 1
    assert esito.idempotenze_rimosse == 1
    assert esito.dispatch_rimossi == 1
    assert esito.audit_log_rimossi == 1
    assert await _conta(motore_amministratore, "refresh_token") == 0
    assert await _conta(motore_amministratore, "email_verification_token") == 0
    assert await _conta(motore_amministratore, "password_reset_token") == 0
    assert await _conta(motore_amministratore, "idempotency_record") == 0
    # La notifica non letta resta: la retention copre solo quelle lette da oltre
    # dodici mesi.
    assert await _conta(motore_amministratore, "notification") == 1
    assert await _conta(motore_amministratore, "report_dispatch") == 1
    assert await _conta(motore_amministratore, "audit_log") == 1


async def _inserisci_dati_scaduti(
    connessione,
    utente_id: uuid.UUID,
    *,
    municipality_id: uuid.UUID,
    report_id: uuid.UUID,
) -> None:
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
    await _inserisci_dispatch(
        connessione,
        report_id=report_id,
        municipality_id=municipality_id,
        attempt_no=1,
        created_at="now() - interval '25 months'",
    )
    await _inserisci_dispatch(
        connessione,
        report_id=report_id,
        municipality_id=municipality_id,
        attempt_no=2,
        created_at="now() - interval '1 month'",
    )
    await _inserisci_audit_log(
        connessione,
        report_id=report_id,
        created_at="now() - interval '25 months'",
    )
    await _inserisci_audit_log(
        connessione,
        report_id=report_id,
        created_at="now() - interval '1 month'",
    )


async def _inserisci_dispatch(
    connessione,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID,
    attempt_no: int,
    created_at: str,
) -> None:
    await connessione.execute(
        text(f"""
            INSERT INTO report_dispatch (
                id, report_id, municipality_id, channel, attempt_no, status,
                created_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid),
                CAST('email' AS dispatch_channel), :attempt_no,
                CAST('succeeded' AS dispatch_attempt_status), {created_at}
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "report_id": str(report_id),
            "municipality_id": str(municipality_id),
            "attempt_no": attempt_no,
        },
    )


async def _inserisci_audit_log(
    connessione,
    *,
    report_id: uuid.UUID,
    created_at: str,
) -> None:
    await connessione.execute(
        text(f"""
            INSERT INTO audit_log (
                id, actor_type, action, entity_type, entity_id, created_at
            )
            VALUES (
                CAST(:id AS uuid), 'system', 'retention-test', 'report',
                CAST(:report_id AS uuid), {created_at}
            )
            """),
        {
            "id": str(uuid.uuid4()),
            "report_id": str(report_id),
        },
    )


async def _conta(motore: AsyncEngine, tabella: str) -> int:
    async with motore.connect() as connessione:
        esito = await connessione.execute(text(f'SELECT count(*) FROM "{tabella}"'))
        return int(esito.scalar_one())
