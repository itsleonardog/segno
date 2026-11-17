from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.identificativo import genera_identificativo_uuid7

DURATA_RECORD_ORE = 24


@dataclass(frozen=True, slots=True)
class RispostaIdempotente:
    status: int
    corpo: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EsitoAvvioIdempotenza:
    record_id: uuid.UUID | None
    risposta_salvata: RispostaIdempotente | None


class ChiaveIdempotenzaInConflitto(Exception):  # noqa: N818
    """Segnala il riuso della stessa chiave con una richiesta diversa."""


class ElaborazioneIdempotenteInCorso(Exception):  # noqa: N818
    """Segnala una risposta non ancora disponibile per la chiave richiesta."""


def calcola_hash_richiesta(corpo: Mapping[str, object]) -> str:
    """Restituisce l'impronta stabile del corpo della richiesta."""
    serializzato = json.dumps(
        corpo,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serializzato.encode("utf-8")).hexdigest()


async def avvia_idempotenza(
    connessione: AsyncConnection,
    *,
    utente_id: uuid.UUID,
    endpoint: str,
    chiave: str,
    request_hash: str,
) -> EsitoAvvioIdempotenza:
    """Registra la chiave o restituisce la risposta già salvata."""
    identificativo = genera_identificativo_uuid7()
    scadenza = datetime.now(UTC) + timedelta(hours=DURATA_RECORD_ORE)
    esito_inserimento = await connessione.execute(
        text("""
            INSERT INTO idempotency_record (
                id, actor_id, endpoint, idempotency_key, request_hash, expires_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:actor_id AS uuid), :endpoint,
                :idempotency_key, :request_hash, :expires_at
            )
            ON CONFLICT (actor_id, endpoint, idempotency_key) DO NOTHING
            RETURNING id
            """),
        {
            "id": str(identificativo),
            "actor_id": str(utente_id),
            "endpoint": endpoint,
            "idempotency_key": chiave,
            "request_hash": request_hash,
            "expires_at": scadenza,
        },
    )
    riga_inserita = esito_inserimento.mappings().one_or_none()
    if riga_inserita is not None:
        return EsitoAvvioIdempotenza(
            record_id=riga_inserita["id"], risposta_salvata=None
        )

    record_esistente = await _carica_record(
        connessione,
        utente_id=utente_id,
        endpoint=endpoint,
        chiave=chiave,
    )
    if record_esistente is None:
        raise ElaborazioneIdempotenteInCorso(
            "La richiesta con questa chiave non è più disponibile."
        )
    if record_esistente["request_hash"] != request_hash:
        raise ChiaveIdempotenzaInConflitto(
            "La chiave di idempotenza è già stata usata con dati diversi."
        )
    if (
        record_esistente["response_status"] is None
        or record_esistente["response_body"] is None
    ):
        raise ElaborazioneIdempotenteInCorso(
            "La richiesta con questa chiave è ancora in elaborazione."
        )
    return EsitoAvvioIdempotenza(
        record_id=None,
        risposta_salvata=RispostaIdempotente(
            status=int(record_esistente["response_status"]),
            corpo=record_esistente["response_body"],
        ),
    )


async def completa_idempotenza(
    connessione: AsyncConnection,
    *,
    record_id: uuid.UUID,
    status: int,
    corpo: Mapping[str, object],
) -> None:
    """Salva la risposta da riprodurre per la stessa chiave."""
    await connessione.execute(
        text("""
            UPDATE idempotency_record
            SET response_status = :response_status,
                response_body = CAST(:response_body AS jsonb)
            WHERE id = CAST(:record_id AS uuid)
            """),
        {
            "record_id": str(record_id),
            "response_status": status,
            "response_body": json.dumps(corpo, ensure_ascii=False),
        },
    )


async def _carica_record(
    connessione: AsyncConnection,
    *,
    utente_id: uuid.UUID,
    endpoint: str,
    chiave: str,
) -> Mapping[str, object] | None:
    esito = await connessione.execute(
        text("""
            SELECT id, request_hash, response_status, response_body
            FROM idempotency_record
            WHERE actor_id = CAST(:actor_id AS uuid)
              AND endpoint = :endpoint
              AND idempotency_key = :idempotency_key
            """),
        {
            "actor_id": str(utente_id),
            "endpoint": endpoint,
            "idempotency_key": chiave,
        },
    )
    return esito.mappings().one_or_none()
