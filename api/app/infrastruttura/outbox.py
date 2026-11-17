from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.identificativo import genera_identificativo_uuid7

LUNGHEZZA_MASSIMA_ERRORE = 500

# Un evento di segnalazione resta in coda finché il backoff del suo dispatch
# non è scaduto: il worker riprova solo quando next_attempt_at è nel passato.
_SQL_EVENTI_NON_PROCESSATI = """
    SELECT id, aggregate_type, aggregate_id, event_type, payload, tenant_id,
           attempts
    FROM outbox_event
    WHERE processed_at IS NULL
      AND (
          aggregate_type <> 'report'
          OR NOT EXISTS (
              SELECT 1
              FROM report_dispatch AS dispatch
              WHERE dispatch.report_id = outbox_event.aggregate_id
                AND dispatch.status = CAST(
                    'failed_retryable' AS dispatch_attempt_status
                )
                AND dispatch.next_attempt_at IS NOT NULL
                AND dispatch.next_attempt_at > now()
          )
      )
    ORDER BY id
    LIMIT :limite
    FOR UPDATE SKIP LOCKED
"""


@dataclass(frozen=True, slots=True)
class EventoOutbox:
    id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    event_type: str
    payload: Mapping[str, object]
    tenant_id: uuid.UUID | None
    attempts: int


async def leggi_eventi_da_processare(
    connessione: AsyncConnection,
    *,
    limite: int,
) -> list[EventoOutbox]:
    """Restituisce gli eventi non processati bloccandoli con SKIP LOCKED."""
    esito = await connessione.execute(
        text(_SQL_EVENTI_NON_PROCESSATI),
        {"limite": limite},
    )
    return [
        EventoOutbox(
            id=riga["id"],
            aggregate_type=riga["aggregate_type"],
            aggregate_id=riga["aggregate_id"],
            event_type=riga["event_type"],
            payload=riga["payload"],
            tenant_id=riga["tenant_id"],
            attempts=riga["attempts"],
        )
        for riga in esito.mappings().all()
    ]


async def inserisci_evento_outbox(
    connessione: AsyncConnection,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: Mapping[str, object],
    tenant_id: uuid.UUID | None,
) -> uuid.UUID:
    """Accoda un evento nella stessa transazione che scrive l'aggregato."""
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO outbox_event (
                id, aggregate_type, aggregate_id, event_type, payload, tenant_id
            )
            VALUES (
                CAST(:id AS uuid), :aggregate_type, CAST(:aggregate_id AS uuid),
                :event_type, CAST(:payload AS jsonb), CAST(:tenant_id AS uuid)
            )
            """),
        {
            "id": str(identificativo),
            "aggregate_type": aggregate_type,
            "aggregate_id": str(aggregate_id),
            "event_type": event_type,
            "payload": _serializza_payload(payload),
            "tenant_id": str(tenant_id) if tenant_id else None,
        },
    )
    return identificativo


async def marca_evento_processato(
    connessione: AsyncConnection,
    evento_id: uuid.UUID,
) -> None:
    """Imposta processed_at sull'evento, rendendo il relay idempotente."""
    await connessione.execute(
        text("""
            UPDATE outbox_event SET processed_at = now()
            WHERE id = CAST(:evento_id AS uuid)
            """),
        {"evento_id": str(evento_id)},
    )


async def registra_errore_evento(
    connessione: AsyncConnection,
    *,
    evento_id: uuid.UUID,
    messaggio_errore: str,
) -> None:
    """Incrementa i tentativi e registra l'errore lasciando l'evento in coda."""
    await connessione.execute(
        text("""
            UPDATE outbox_event
            SET attempts = attempts + 1,
                last_error = :messaggio_errore
            WHERE id = CAST(:evento_id AS uuid)
            """),
        {
            "evento_id": str(evento_id),
            "messaggio_errore": messaggio_errore[:LUNGHEZZA_MASSIMA_ERRORE],
        },
    )


def _serializza_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False)
