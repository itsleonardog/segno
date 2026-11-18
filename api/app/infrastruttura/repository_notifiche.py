from __future__ import annotations

import json
import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.notifica import Notifica, NotificaDaInviare
from app.infrastruttura.identificativo import genera_identificativo_uuid7


async def inserisci_notifica(
    connessione: AsyncConnection,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID | None,
    tipo: str,
    canale: str,
    payload: Mapping[str, object],
    dedupe_key: str,
) -> uuid.UUID:
    """Inserisce la notifica in-app e ne restituisce l'identificativo."""
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO notification (
                id, user_id, report_id, type, channel, payload, dedupe_key
            )
            VALUES (
                CAST(:id AS uuid), CAST(:user_id AS uuid),
                CAST(:report_id AS uuid), :tipo, :canale,
                CAST(:payload AS jsonb), :dedupe_key
            )
            """),
        {
            "id": str(identificativo),
            "user_id": str(user_id),
            "report_id": str(report_id) if report_id else None,
            "tipo": tipo,
            "canale": canale,
            "payload": json.dumps(payload, ensure_ascii=False),
            "dedupe_key": dedupe_key,
        },
    )
    return identificativo


async def elenca_notifiche_utente(
    connessione: AsyncConnection,
    *,
    cursore: uuid.UUID | None,
    limite: int,
) -> list[Notifica]:
    """Restituisce una pagina di notifiche dell'utente autenticato."""
    condizioni = ["user_id = app_user_id()"]
    parametri: dict[str, object] = {"limite": limite}
    if cursore is not None:
        condizioni.append("id < CAST(:cursore AS uuid)")
        parametri["cursore"] = str(cursore)
    esito = await connessione.execute(
        text(f"""
            SELECT id, user_id, report_id, type, channel, payload, read_at,
                   sent_at, created_at
            FROM notification
            WHERE {' AND '.join(condizioni)}
            ORDER BY id DESC
            LIMIT :limite
            """),
        parametri,
    )
    return [_mappa_notifica(riga) for riga in esito.mappings().all()]


async def conta_notifiche_non_lette(
    connessione: AsyncConnection,
) -> int:
    """Restituisce il numero di notifiche non lette dell'utente autenticato."""
    esito = await connessione.execute(text("""
            SELECT count(*) FROM notification
            WHERE user_id = app_user_id() AND read_at IS NULL
            """))
    return int(esito.scalar_one())


async def marca_notifica_letta(
    connessione: AsyncConnection,
    *,
    notifica_id: uuid.UUID,
) -> bool:
    """Imposta read_at sulla notifica dell'utente e indica se esisteva."""
    esito = await connessione.execute(
        text("""
            UPDATE notification
            SET read_at = COALESCE(read_at, now())
            WHERE id = CAST(:notifica_id AS uuid) AND user_id = app_user_id()
            """),
        {"notifica_id": str(notifica_id)},
    )
    return esito.rowcount == 1


async def marca_tutte_notifiche_lette(
    connessione: AsyncConnection,
) -> int:
    """Imposta read_at su tutte le notifiche non lette e restituisce il totale."""
    esito = await connessione.execute(text("""
            UPDATE notification
            SET read_at = now()
            WHERE user_id = app_user_id() AND read_at IS NULL
            """))
    return int(esito.rowcount)


async def carica_notifica_da_inviare(
    connessione: AsyncConnection,
    notifica_id: uuid.UUID,
) -> NotificaDaInviare | None:
    """Restituisce la notifica con i dati cifrati dell'autore da contattare."""
    esito = await connessione.execute(
        text("""
            SELECT n.id, n.user_id, n.report_id, n.payload, n.sent_at,
                   u.email_enc, u.email_key_id, r.public_ref
            FROM notification AS n
            JOIN "user" AS u ON u.id = n.user_id
            LEFT JOIN report AS r ON r.id = n.report_id
            WHERE n.id = CAST(:notifica_id AS uuid)
            """),
        {"notifica_id": str(notifica_id)},
    )
    riga = esito.mappings().one_or_none()
    if riga is None:
        return None
    payload = riga["payload"] or {}
    return NotificaDaInviare(
        id=riga["id"],
        user_id=riga["user_id"],
        report_id=riga["report_id"],
        public_ref=riga["public_ref"],
        to_status=_stringa_o_none(payload.get("to_status")),
        note_public=_stringa_o_none(payload.get("note_public")),
        email_enc=bytes(riga["email_enc"]),
        email_key_id=riga["email_key_id"],
        sent_at=riga["sent_at"],
    )


async def marca_notifica_inviata(
    connessione: AsyncConnection,
    notifica_id: uuid.UUID,
) -> None:
    """Registra l'avvenuto invio email sulla notifica."""
    await connessione.execute(
        text("""
            UPDATE notification SET sent_at = COALESCE(sent_at, now())
            WHERE id = CAST(:notifica_id AS uuid)
            """),
        {"notifica_id": str(notifica_id)},
    )


def _mappa_notifica(riga: Mapping[str, object]) -> Notifica:
    return Notifica(
        id=riga["id"],
        user_id=riga["user_id"],
        report_id=riga["report_id"],
        tipo=riga["type"],
        canale=riga["channel"],
        payload=riga["payload"] or {},
        read_at=riga["read_at"],
        sent_at=riga["sent_at"],
        created_at=riga["created_at"],
    )


def _stringa_o_none(valore: object) -> str | None:
    return valore if isinstance(valore, str) else None
