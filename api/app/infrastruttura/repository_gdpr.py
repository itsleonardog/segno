from __future__ import annotations

import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.gdpr import (
    EventoEsportato,
    NotificaEsportata,
    SegnalazioneEsportata,
    componi_nickname_anonimo,
)

STATO_UTENTE_ANONIMIZZATO = "anonymized"


async def elenca_segnalazioni_autore(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> list[SegnalazioneEsportata]:
    """Restituisce le segnalazioni scritte dall'utente, comprese quelle chiuse."""
    esito = await connessione.execute(
        text("""
            SELECT id, public_ref, title, description, category_id,
                   municipality_id, status, visibility, dispatch_state,
                   ST_Y(location::geometry) AS latitudine,
                   ST_X(location::geometry) AS longitudine,
                   address_label, created_at
            FROM report
            WHERE author_id = CAST(:utente_id AS uuid)
            ORDER BY id ASC
            """),
        {"utente_id": str(utente_id)},
    )
    return [
        SegnalazioneEsportata(
            id=riga["id"],
            public_ref=riga["public_ref"],
            title=riga["title"],
            description=riga["description"],
            category_id=riga["category_id"],
            municipality_id=riga["municipality_id"],
            status=riga["status"],
            visibility=riga["visibility"],
            dispatch_state=riga["dispatch_state"],
            lat=riga["latitudine"],
            lng=riga["longitudine"],
            address_text=riga["address_label"],
            created_at=riga["created_at"],
        )
        for riga in esito.mappings().all()
    ]


async def elenca_eventi_autore(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> list[EventoEsportato]:
    """Restituisce gli eventi di stato che l'utente ha prodotto come cittadino."""
    esito = await connessione.execute(
        text("""
            SELECT id, report_id, to_status, note_public, created_at
            FROM report_status_event
            WHERE actor_type = CAST('citizen' AS actor_type)
              AND actor_id = CAST(:utente_id AS uuid)
            ORDER BY id ASC
            """),
        {"utente_id": str(utente_id)},
    )
    return [
        EventoEsportato(
            id=riga["id"],
            report_id=riga["report_id"],
            to_status=riga["to_status"],
            note_public=riga["note_public"],
            created_at=riga["created_at"],
        )
        for riga in esito.mappings().all()
    ]


async def elenca_notifiche_autore(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> list[NotificaEsportata]:
    """Restituisce tutte le notifiche dell'utente, lette e non lette."""
    esito = await connessione.execute(
        text("""
            SELECT id, report_id, type, channel, payload, read_at, created_at
            FROM notification
            WHERE user_id = CAST(:utente_id AS uuid)
            ORDER BY id ASC
            """),
        {"utente_id": str(utente_id)},
    )
    return [_mappa_notifica(riga) for riga in esito.mappings().all()]


async def anonimizza_utente(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> None:
    """Svuota i dati personali dell'utente e ne marca lo stato."""
    nickname = componi_nickname_anonimo(utente_id)
    await connessione.execute(
        text("""
            UPDATE "user"
            SET nickname = :nickname,
                nickname_normalized = lower(:nickname),
                email_enc = NULL,
                email_key_id = NULL,
                email_lookup_hash = NULL,
                password_hash = NULL,
                email_verified_at = NULL,
                status = CAST(:status AS user_status)
            WHERE id = CAST(:utente_id AS uuid)
            """),
        {
            "utente_id": str(utente_id),
            "nickname": nickname,
            "status": STATO_UTENTE_ANONIMIZZATO,
        },
    )


async def azzera_riferimenti_autore(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> None:
    """Stacca l'autore dalle segnalazioni, che restano pubbliche e anonime."""
    # report_status_event è append-only per scelta di dominio: gli eventi
    # conservano l'identificativo pseudonimo e non vengono riscritti.
    await connessione.execute(
        text("""
            UPDATE report SET author_id = NULL
            WHERE author_id = CAST(:utente_id AS uuid)
            """),
        {"utente_id": str(utente_id)},
    )


async def invalida_token_pendenti(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
) -> None:
    """Consuma i token di verifica e di reset ancora aperti dell'utente."""
    parametri = {"utente_id": str(utente_id)}
    await connessione.execute(
        text("""
            UPDATE email_verification_token SET used_at = now()
            WHERE user_id = CAST(:utente_id AS uuid) AND used_at IS NULL
            """),
        parametri,
    )
    await connessione.execute(
        text("""
            UPDATE password_reset_token SET used_at = now()
            WHERE user_id = CAST(:utente_id AS uuid) AND used_at IS NULL
            """),
        parametri,
    )


def _mappa_notifica(riga: Mapping[str, object]) -> NotificaEsportata:
    return NotificaEsportata(
        id=riga["id"],
        report_id=riga["report_id"],
        tipo=riga["type"],
        canale=riga["channel"],
        payload=dict(riga["payload"] or {}),
        read_at=riga["read_at"],
        created_at=riga["created_at"],
    )
