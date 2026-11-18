from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.identificativo import genera_identificativo_uuid7

CONFINE_COMUNE_A = "SRID=4326;MULTIPOLYGON(((9 45, 9 45.1, 9.1 45.1, 9.1 45, 9 45)))"
CONFINE_COMUNE_B = (
    "SRID=4326;MULTIPOLYGON(((10 45, 10 45.1, 10.1 45.1, 10.1 45, 10 45)))"
)
POSIZIONE_COMUNE_A = "SRID=4326;POINT(9.05 45.05)"
POSIZIONE_COMUNE_B = "SRID=4326;POINT(10.05 45.05)"


async def crea_comune(
    connessione: AsyncConnection,
    *,
    confine: str,
    priorita: int = 0,
    dispatch_mode: str = "email",
    open311_endpoint_url: str | None = None,
    open311_api_key_ref: str | None = None,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    suffisso = identificativo.hex[:12]
    await connessione.execute(
        text("""
            INSERT INTO municipality (
                id, slug, name, istat_code, region, timezone, locale,
                boundary, dispatch_mode, open311_endpoint_url,
                open311_api_key_ref, priority
            )
            VALUES (
                CAST(:id AS uuid), :slug, :nome, :istat, 'Lombardia',
                'Europe/Rome', 'it', ST_GeogFromText(:confine),
                CAST(:dispatch_mode AS dispatch_mode), :endpoint_open311,
                :chiave_open311_ref, :priorita
            )
            """),
        {
            "id": str(identificativo),
            "slug": f"comune-{suffisso}",
            "nome": f"Comune {suffisso}",
            "istat": f"ISTAT-{suffisso}",
            "confine": confine,
            "priorita": priorita,
            "dispatch_mode": dispatch_mode,
            "endpoint_open311": open311_endpoint_url,
            "chiave_open311_ref": open311_api_key_ref,
        },
    )
    return identificativo


async def crea_utente(
    connessione: AsyncConnection,
    *,
    nickname: str | None = None,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    soprannome = nickname or f"utente-{identificativo.hex[:10]}"
    await connessione.execute(
        text("""
            INSERT INTO "user" (
                id, nickname, nickname_normalized, email_enc, email_key_id,
                email_lookup_hash, password_hash, privacy_policy_version,
                tos_version
            )
            VALUES (
                CAST(:id AS uuid), :nickname, lower(:nickname), decode('00', 'hex'),
                'chiave-test', :email_lookup_hash, 'argon2id-test', '1', '1'
            )
            """),
        {
            "id": str(identificativo),
            "nickname": soprannome,
            "email_lookup_hash": f"hash-{identificativo}",
        },
    )
    return identificativo


async def crea_servizio(
    connessione: AsyncConnection,
    *,
    municipality_id: uuid.UUID,
    category_id: str,
    codice_open311: str | None = "SERVIZIO-1",
    fallback_email_enc: bytes | None = None,
    fallback_active: bool = False,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO municipality_service (
                id, municipality_id, category_id, open311_service_code,
                fallback_email_enc, fallback_active
            )
            VALUES (
                CAST(:id AS uuid), CAST(:municipality_id AS uuid),
                CAST(:category_id AS uuid), :codice_open311,
                :fallback_email_enc, :fallback_active
            )
            """),
        {
            "id": str(identificativo),
            "municipality_id": str(municipality_id),
            "category_id": category_id,
            "codice_open311": codice_open311,
            "fallback_email_enc": fallback_email_enc,
            "fallback_active": fallback_active,
        },
    )
    return identificativo


async def crea_segnalazione(
    connessione: AsyncConnection,
    *,
    municipality_id: uuid.UUID | None,
    category_id: str,
    public_ref: str,
    posizione: str,
    author_id: uuid.UUID | None = None,
    visibility: str = "public",
    dispatch_state: str = "pending",
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO report (
                id, public_ref, municipality_id, author_id, category_id,
                title, description, location, visibility, dispatch_state
            )
            VALUES (
                CAST(:id AS uuid), :public_ref, CAST(:municipality_id AS uuid),
                CAST(:author_id AS uuid), CAST(:category_id AS uuid),
                'Titolo di prova', 'Descrizione di prova',
                ST_GeogFromText(:posizione),
                CAST(:visibility AS report_visibility),
                CAST(:dispatch_state AS report_dispatch_state)
            )
            """),
        {
            "id": str(identificativo),
            "public_ref": public_ref,
            "municipality_id": str(municipality_id) if municipality_id else None,
            "author_id": str(author_id) if author_id else None,
            "category_id": category_id,
            "posizione": posizione,
            "visibility": visibility,
            "dispatch_state": dispatch_state,
        },
    )
    return identificativo


async def crea_evento_stato(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID | None,
    is_public: bool = True,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO report_status_event (
                id, report_id, municipality_id, from_status, to_status,
                actor_type, is_public
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid), NULL,
                CAST('open' AS report_status), CAST('citizen' AS actor_type),
                :is_public
            )
            """),
        {
            "id": str(identificativo),
            "report_id": str(report_id),
            "municipality_id": (str(municipality_id) if municipality_id else None),
            "is_public": is_public,
        },
    )
    return identificativo


async def crea_dispatch(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID,
    attempt_no: int = 1,
    channel: str = "email",
    status: str = "queued",
    provider_request_id: str | None = None,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO report_dispatch (
                id, report_id, municipality_id, channel, attempt_no, status,
                provider_request_id
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid),
                CAST(:channel AS dispatch_channel),
                :attempt_no,
                CAST(:status AS dispatch_attempt_status),
                :provider_request_id
            )
            """),
        {
            "id": str(identificativo),
            "report_id": str(report_id),
            "municipality_id": str(municipality_id),
            "attempt_no": attempt_no,
            "channel": channel,
            "status": status,
            "provider_request_id": provider_request_id,
        },
    )
    return identificativo


async def crea_evento_outbox(
    connessione: AsyncConnection,
    *,
    tenant_id: uuid.UUID | None,
    event_type: str = "report.created",
    aggregate_id: uuid.UUID | None = None,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO outbox_event (
                id, aggregate_type, aggregate_id, event_type, payload, tenant_id
            )
            VALUES (
                CAST(:id AS uuid), 'report', CAST(:aggregate_id AS uuid),
                :event_type, '{}'::jsonb, CAST(:tenant_id AS uuid)
            )
            """),
        {
            "id": str(identificativo),
            "aggregate_id": str(aggregate_id or identificativo),
            "event_type": event_type,
            "tenant_id": str(tenant_id) if tenant_id else None,
        },
    )
    return identificativo


async def crea_notifica(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    dedupe_key: str,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO notification (
                id, user_id, type, channel, dedupe_key
            )
            VALUES (
                CAST(:id AS uuid), CAST(:user_id AS uuid),
                'status_changed', 'inapp', :dedupe_key
            )
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "dedupe_key": dedupe_key,
        },
    )
    return identificativo


async def crea_preferenza_notifica(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO notification_preference (
                id, user_id, type, channel, enabled
            )
            VALUES (
                CAST(:id AS uuid), CAST(:user_id AS uuid),
                'status_changed', 'inapp', true
            )
            """),
        {"id": str(identificativo), "user_id": str(user_id)},
    )
    return identificativo


async def crea_refresh_token(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO refresh_token (
                id, user_id, token_hash, family_id, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash,
                CAST(:family_id AS uuid), now() + interval '30 days'
            )
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "token_hash": f"token-{identificativo}",
            "family_id": str(identificativo),
        },
    )
    return identificativo
