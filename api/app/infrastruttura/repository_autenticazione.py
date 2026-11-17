from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.identificativo import genera_identificativo_uuid7


@dataclass(frozen=True, slots=True)
class UtentePersistito:
    id: uuid.UUID
    nickname: str
    email_enc: bytes
    email_key_id: str
    email_lookup_hash: str
    password_hash: str
    email_verified_at: datetime | None
    status: str
    created_at: datetime
    last_login_at: datetime | None
    locale: str
    privacy_policy_version: str
    tos_version: str


@dataclass(frozen=True, slots=True)
class RefreshTokenPersistito:
    id: uuid.UUID
    user_id: uuid.UUID
    family_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by_id: uuid.UUID | None
    created_at: datetime
    last_used_at: datetime | None
    user_agent_summary: str | None


@dataclass(frozen=True, slots=True)
class SessioneAttiva:
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    user_agent_summary: str | None


_SQL_UTENTE = """
    SELECT id, nickname, email_enc, email_key_id, email_lookup_hash,
           password_hash, email_verified_at, status, created_at, last_login_at,
           locale, privacy_policy_version, tos_version
    FROM "user"
"""


async def trova_utente_per_email_lookup_hash(
    connessione: AsyncConnection,
    lookup_hash: str,
) -> UtentePersistito | None:
    esito = await connessione.execute(
        text(f"{_SQL_UTENTE} WHERE email_lookup_hash = :lookup_hash"),
        {"lookup_hash": lookup_hash},
    )
    riga = esito.mappings().one_or_none()
    return _mappa_utente(riga) if riga else None


async def trova_utente_per_id(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> UtentePersistito | None:
    esito = await connessione.execute(
        text(f"{_SQL_UTENTE} WHERE id = CAST(:user_id AS uuid)"),
        {"user_id": str(user_id)},
    )
    riga = esito.mappings().one_or_none()
    return _mappa_utente(riga) if riga else None


async def trova_stato_utente(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> str | None:
    esito = await connessione.execute(
        text('SELECT status FROM "user" WHERE id = CAST(:user_id AS uuid)'),
        {"user_id": str(user_id)},
    )
    return esito.scalar_one_or_none()


async def rileva_conflitti_registrazione(
    connessione: AsyncConnection,
    *,
    lookup_hash: str,
    nickname: str,
) -> tuple[bool, bool]:
    esito = await connessione.execute(
        text("""
            SELECT
                EXISTS(
                    SELECT 1 FROM "user" WHERE email_lookup_hash = :lookup_hash
                ) AS email_presente,
                EXISTS(
                    SELECT 1 FROM "user" WHERE lower(nickname) = lower(:nickname)
                ) AS nickname_presente
            """),
        {"lookup_hash": lookup_hash, "nickname": nickname},
    )
    riga = esito.mappings().one()
    return bool(riga["email_presente"]), bool(riga["nickname_presente"])


async def crea_utente(
    connessione: AsyncConnection,
    *,
    nickname: str,
    email_enc: bytes,
    email_key_id: str,
    email_lookup_hash: str,
    password_hash: str,
    privacy_policy_version: str,
    tos_version: str,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO "user" (
                id, nickname, nickname_normalized, email_enc, email_key_id,
                email_lookup_hash, password_hash, privacy_policy_version,
                tos_version
            )
            VALUES (
                CAST(:id AS uuid), :nickname, lower(:nickname), :email_enc,
                :email_key_id, :email_lookup_hash, :password_hash,
                :privacy_policy_version, :tos_version
            )
            """),
        {
            "id": str(identificativo),
            "nickname": nickname,
            "email_enc": email_enc,
            "email_key_id": email_key_id,
            "email_lookup_hash": email_lookup_hash,
            "password_hash": password_hash,
            "privacy_policy_version": privacy_policy_version,
            "tos_version": tos_version,
        },
    )
    return identificativo


async def aggiorna_nickname(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    nickname: str,
) -> bool:
    esito = await connessione.execute(
        text("""
            UPDATE "user"
            SET nickname = :nickname, nickname_normalized = lower(:nickname)
            WHERE id = CAST(:user_id AS uuid)
            """),
        {"user_id": str(user_id), "nickname": nickname},
    )
    return esito.rowcount == 1


async def aggiorna_locale(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    locale: str,
) -> bool:
    esito = await connessione.execute(
        text("""
            UPDATE "user" SET locale = :locale
            WHERE id = CAST(:user_id AS uuid)
            """),
        {"user_id": str(user_id), "locale": locale},
    )
    return esito.rowcount == 1


async def aggiorna_last_login(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> None:
    await connessione.execute(
        text("""
            UPDATE "user" SET last_login_at = now()
            WHERE id = CAST(:user_id AS uuid)
            """),
        {"user_id": str(user_id)},
    )


async def marca_email_verificata(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> None:
    await connessione.execute(
        text("""
            UPDATE "user" SET email_verified_at = now()
            WHERE id = CAST(:user_id AS uuid)
            """),
        {"user_id": str(user_id)},
    )


async def aggiorna_password_hash(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    password_hash: str,
) -> None:
    await connessione.execute(
        text("""
            UPDATE "user" SET password_hash = :password_hash
            WHERE id = CAST(:user_id AS uuid)
            """),
        {"user_id": str(user_id), "password_hash": password_hash},
    )


async def crea_refresh_token(
    connessione: AsyncConnection,
    *,
    identificativo: uuid.UUID,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    user_agent_summary: str | None,
) -> None:
    await connessione.execute(
        text("""
            INSERT INTO refresh_token (
                id, user_id, token_hash, family_id, expires_at,
                user_agent_summary
            )
            VALUES (
                CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash,
                CAST(:family_id AS uuid), :expires_at, :user_agent_summary
            )
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "token_hash": token_hash,
            "family_id": str(family_id),
            "expires_at": expires_at,
            "user_agent_summary": user_agent_summary,
        },
    )


async def trova_refresh_token_per_hash(
    connessione: AsyncConnection,
    token_hash: str,
    *,
    blocca_riga: bool = False,
) -> RefreshTokenPersistito | None:
    query = """
        SELECT id, user_id, family_id, token_hash, expires_at, revoked_at,
               replaced_by_id, created_at, last_used_at, user_agent_summary
        FROM refresh_token
        WHERE token_hash = :token_hash
    """
    if blocca_riga:
        # Il lock serializza due refresh concorrenti sullo stesso token: il
        # secondo vede la revoca del primo e ricade nel rilevamento di riuso.
        query += " FOR UPDATE"
    esito = await connessione.execute(text(query), {"token_hash": token_hash})
    riga = esito.mappings().one_or_none()
    return _mappa_refresh_token(riga) if riga else None


async def revoca_refresh_token(
    connessione: AsyncConnection,
    *,
    token_id: uuid.UUID,
    replaced_by: uuid.UUID | None = None,
) -> None:
    await connessione.execute(
        text("""
            UPDATE refresh_token
            SET revoked_at = now(),
                replaced_by_id = CAST(:replaced_by AS uuid)
            WHERE id = CAST(:token_id AS uuid) AND revoked_at IS NULL
            """),
        {
            "token_id": str(token_id),
            "replaced_by": str(replaced_by) if replaced_by else None,
        },
    )


async def revoca_famiglia(
    connessione: AsyncConnection,
    family_id: uuid.UUID,
) -> None:
    await connessione.execute(
        text("""
            UPDATE refresh_token SET revoked_at = now()
            WHERE family_id = CAST(:family_id AS uuid) AND revoked_at IS NULL
            """),
        {"family_id": str(family_id)},
    )


async def revoca_tutte_le_famiglie(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> None:
    await connessione.execute(
        text("""
            UPDATE refresh_token SET revoked_at = now()
            WHERE user_id = CAST(:user_id AS uuid) AND revoked_at IS NULL
            """),
        {"user_id": str(user_id)},
    )


async def revoca_sessione(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    sessione_id: uuid.UUID,
) -> bool:
    esito = await connessione.execute(
        text("""
            UPDATE refresh_token SET revoked_at = now()
            WHERE id = CAST(:sessione_id AS uuid)
              AND user_id = CAST(:user_id AS uuid)
              AND revoked_at IS NULL
            """),
        {"sessione_id": str(sessione_id), "user_id": str(user_id)},
    )
    return esito.rowcount == 1


async def lista_sessioni_attive(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> list[SessioneAttiva]:
    esito = await connessione.execute(
        text("""
            SELECT id, created_at, last_used_at, user_agent_summary
            FROM refresh_token
            WHERE user_id = CAST(:user_id AS uuid)
              AND revoked_at IS NULL
              AND expires_at > now()
            ORDER BY created_at DESC
            """),
        {"user_id": str(user_id)},
    )
    return [
        SessioneAttiva(
            id=riga["id"],
            created_at=riga["created_at"],
            last_used_at=riga["last_used_at"],
            user_agent_summary=riga["user_agent_summary"],
        )
        for riga in esito.mappings().all()
    ]


async def crea_token_verifica(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO email_verification_token (
                id, user_id, token_hash, expires_at
            )
            VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash, :expires_at)
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "token_hash": token_hash,
            "expires_at": expires_at,
        },
    )
    return identificativo


async def consuma_token_verifica(
    connessione: AsyncConnection,
    token_hash: str,
) -> uuid.UUID | None:
    esito = await connessione.execute(
        text("""
            UPDATE email_verification_token SET used_at = now()
            WHERE token_hash = :token_hash
              AND used_at IS NULL
              AND expires_at > now()
            RETURNING user_id
            """),
        {"token_hash": token_hash},
    )
    return esito.scalar_one_or_none()


async def crea_token_reset(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
) -> uuid.UUID:
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO password_reset_token (
                id, user_id, token_hash, expires_at
            )
            VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash, :expires_at)
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "token_hash": token_hash,
            "expires_at": expires_at,
        },
    )
    return identificativo


async def consuma_token_reset(
    connessione: AsyncConnection,
    token_hash: str,
) -> uuid.UUID | None:
    esito = await connessione.execute(
        text("""
            UPDATE password_reset_token SET used_at = now()
            WHERE token_hash = :token_hash
              AND used_at IS NULL
              AND expires_at > now()
            RETURNING user_id
            """),
        {"token_hash": token_hash},
    )
    return esito.scalar_one_or_none()


async def invalida_token_reset_pendenti(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> None:
    await connessione.execute(
        text("""
            UPDATE password_reset_token SET used_at = now()
            WHERE user_id = CAST(:user_id AS uuid) AND used_at IS NULL
            """),
        {"user_id": str(user_id)},
    )


async def registra_audit(
    connessione: AsyncConnection,
    *,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
) -> None:
    await connessione.execute(
        text("""
            INSERT INTO audit_log (
                id, actor_type, actor_id, action, entity_type, entity_id
            )
            VALUES (
                CAST(:id AS uuid), :actor_type, CAST(:actor_id AS uuid),
                :action, :entity_type, CAST(:entity_id AS uuid)
            )
            """),
        {
            "id": str(genera_identificativo_uuid7()),
            "actor_type": actor_type,
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
        },
    )


def _mappa_utente(riga: Mapping[str, object]) -> UtentePersistito:
    return UtentePersistito(
        id=riga["id"],
        nickname=riga["nickname"],
        email_enc=bytes(riga["email_enc"]),
        email_key_id=riga["email_key_id"],
        email_lookup_hash=riga["email_lookup_hash"],
        password_hash=riga["password_hash"],
        email_verified_at=riga["email_verified_at"],
        status=riga["status"],
        created_at=riga["created_at"],
        last_login_at=riga["last_login_at"],
        locale=riga["locale"],
        privacy_policy_version=riga["privacy_policy_version"],
        tos_version=riga["tos_version"],
    )


def _mappa_refresh_token(riga: Mapping[str, object]) -> RefreshTokenPersistito:
    return RefreshTokenPersistito(
        id=riga["id"],
        user_id=riga["user_id"],
        family_id=riga["family_id"],
        token_hash=riga["token_hash"],
        expires_at=riga["expires_at"],
        revoked_at=riga["revoked_at"],
        replaced_by_id=riga["replaced_by_id"],
        created_at=riga["created_at"],
        last_used_at=riga["last_used_at"],
        user_agent_summary=riga["user_agent_summary"],
    )
