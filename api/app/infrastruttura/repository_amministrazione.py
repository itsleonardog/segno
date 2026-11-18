from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.identificativo import genera_identificativo_uuid7


@dataclass(frozen=True, slots=True)
class EventoStatoAmministrazione:
    id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_type: str
    note_public: str | None
    is_public: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TentativoDispatch:
    id: uuid.UUID
    channel: str
    attempt_no: int
    status: str
    provider_request_id: str | None
    http_status: int | None
    error_code: str | None
    error_detail_redacted: str | None
    next_attempt_at: datetime | None
    succeeded_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NotaInterna:
    id: uuid.UUID
    author_id: uuid.UUID | None
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FallimentoDispatch:
    report_id: uuid.UUID
    public_ref: str
    title: str
    dispatch: TentativoDispatch


async def elenca_eventi_stato_completi(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> list[EventoStatoAmministrazione]:
    """Restituisce tutti gli eventi di stato, inclusi quelli non pubblici."""
    esito = await connessione.execute(
        text("""
            SELECT id, from_status, to_status, actor_type, note_public, is_public,
                   created_at
            FROM report_status_event
            WHERE report_id = CAST(:report_id AS uuid)
            ORDER BY created_at ASC, id ASC
            """),
        {"report_id": str(report_id)},
    )
    return [
        EventoStatoAmministrazione(
            id=riga["id"],
            from_status=riga["from_status"],
            to_status=riga["to_status"],
            actor_type=riga["actor_type"],
            note_public=riga["note_public"],
            is_public=riga["is_public"],
            created_at=riga["created_at"],
        )
        for riga in esito.mappings().all()
    ]


async def elenca_tentativi_dispatch(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> list[TentativoDispatch]:
    """Restituisce lo storico dei tentativi di invio della segnalazione."""
    esito = await connessione.execute(
        text("""
            SELECT id, channel, attempt_no, status, provider_request_id,
                   http_status, error_code, error_detail_redacted,
                   next_attempt_at, succeeded_at, created_at
            FROM report_dispatch
            WHERE report_id = CAST(:report_id AS uuid)
            ORDER BY created_at ASC, attempt_no ASC
            """),
        {"report_id": str(report_id)},
    )
    return [_mappa_tentativo(riga) for riga in esito.mappings().all()]


async def elenca_note_interne(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> list[NotaInterna]:
    """Restituisce le note interne della segnalazione in ordine cronologico."""
    esito = await connessione.execute(
        text("""
            SELECT id, author_id, body, created_at
            FROM report_internal_note
            WHERE report_id = CAST(:report_id AS uuid)
            ORDER BY created_at ASC, id ASC
            """),
        {"report_id": str(report_id)},
    )
    return [
        NotaInterna(
            id=riga["id"],
            author_id=riga["author_id"],
            body=riga["body"],
            created_at=riga["created_at"],
        )
        for riga in esito.mappings().all()
    ]


async def inserisci_nota_interna(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID,
    author_id: uuid.UUID,
    body: str,
) -> NotaInterna:
    """Inserisce una nota visibile solo agli operatori del comune."""
    identificativo = genera_identificativo_uuid7()
    esito = await connessione.execute(
        text("""
            INSERT INTO report_internal_note (
                id, report_id, municipality_id, author_id, body
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid), CAST(:author_id AS uuid), :body
            )
            RETURNING id, author_id, body, created_at
            """),
        {
            "id": str(identificativo),
            "report_id": str(report_id),
            "municipality_id": str(municipality_id),
            "author_id": str(author_id),
            "body": body,
        },
    )
    riga = esito.mappings().one()
    return NotaInterna(
        id=riga["id"],
        author_id=riga["author_id"],
        body=riga["body"],
        created_at=riga["created_at"],
    )


async def elenca_fallimenti_permanenti(
    connessione: AsyncConnection,
    *,
    municipality_id: uuid.UUID,
    limite: int,
) -> list[FallimentoDispatch]:
    """Restituisce i dispatch falliti in modo permanente per il comune."""
    esito = await connessione.execute(
        text("""
            SELECT dispatch.id, dispatch.channel, dispatch.attempt_no,
                   dispatch.status, dispatch.provider_request_id,
                   dispatch.http_status, dispatch.error_code,
                   dispatch.error_detail_redacted, dispatch.next_attempt_at,
                   dispatch.succeeded_at, dispatch.created_at,
                   report.id AS report_id, report.public_ref, report.title
            FROM report_dispatch AS dispatch
            JOIN report ON report.id = dispatch.report_id
            WHERE dispatch.municipality_id = CAST(:municipality_id AS uuid)
              AND dispatch.status = CAST(
                  'failed_permanent' AS dispatch_attempt_status
              )
              AND report.deleted_at IS NULL
            ORDER BY dispatch.created_at DESC
            LIMIT :limite
            """),
        {
            "municipality_id": str(municipality_id),
            "limite": limite,
        },
    )
    return [
        FallimentoDispatch(
            report_id=riga["report_id"],
            public_ref=riga["public_ref"],
            title=riga["title"],
            dispatch=_mappa_tentativo(riga),
        )
        for riga in esito.mappings().all()
    ]


def _mappa_tentativo(riga: Mapping[str, object]) -> TentativoDispatch:
    return TentativoDispatch(
        id=riga["id"],
        channel=riga["channel"],
        attempt_no=riga["attempt_no"],
        status=riga["status"],
        provider_request_id=riga["provider_request_id"],
        http_status=riga["http_status"],
        error_code=riga["error_code"],
        error_detail_redacted=riga["error_detail_redacted"],
        next_attempt_at=riga["next_attempt_at"],
        succeeded_at=riga["succeeded_at"],
        created_at=riga["created_at"],
    )
