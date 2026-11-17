from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.dispatch import (
    Comune,
    SegnalazioneDaInviare,
    ServizioComunale,
)
from app.infrastruttura.identificativo import genera_identificativo_uuid7

LINGUA_PREDEFINITA_CATEGORIA = "it"

_SQL_SEGNALAZIONE = """
    SELECT id, public_ref, municipality_id, category_id, title, description,
           ST_X(location::geometry) AS longitudine,
           ST_Y(location::geometry) AS latitudine,
           address_label, dispatch_state
    FROM report
    WHERE id = CAST(:report_id AS uuid)
"""

_SQL_COMUNE = """
    SELECT id, name, dispatch_mode, open311_endpoint_url,
           open311_jurisdiction_id, open311_api_key_ref, locale
    FROM municipality
    WHERE id = CAST(:municipality_id AS uuid) AND is_active = true
"""

_SQL_SERVIZIO = """
    SELECT open311_service_code, open311_extra_fields, fallback_email_enc,
           fallback_active
    FROM municipality_service
    WHERE municipality_id = CAST(:municipality_id AS uuid)
      AND category_id = CAST(:category_id AS uuid)
"""


async def carica_segnalazione(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> SegnalazioneDaInviare | None:
    """Restituisce la segnalazione da instradare o None se non esiste."""
    esito = await connessione.execute(
        text(_SQL_SEGNALAZIONE),
        {"report_id": str(report_id)},
    )
    riga = esito.mappings().one_or_none()
    if riga is None:
        return None
    return SegnalazioneDaInviare(
        id=riga["id"],
        public_ref=riga["public_ref"],
        municipality_id=riga["municipality_id"],
        category_id=riga["category_id"],
        titolo=riga["title"],
        descrizione=riga["description"],
        latitudine=riga["latitudine"],
        longitudine=riga["longitudine"],
        address_label=riga["address_label"],
        dispatch_state=riga["dispatch_state"],
    )


async def carica_comune(
    connessione: AsyncConnection,
    municipality_id: uuid.UUID,
) -> Comune | None:
    """Restituisce il comune attivo con la configurazione di dispatch."""
    esito = await connessione.execute(
        text(_SQL_COMUNE),
        {"municipality_id": str(municipality_id)},
    )
    riga = esito.mappings().one_or_none()
    if riga is None:
        return None
    return Comune(
        id=riga["id"],
        nome=riga["name"],
        dispatch_mode=riga["dispatch_mode"],
        open311_endpoint_url=riga["open311_endpoint_url"],
        open311_jurisdiction_id=riga["open311_jurisdiction_id"],
        open311_api_key_ref=riga["open311_api_key_ref"],
        locale=riga["locale"],
    )


async def carica_servizio(
    connessione: AsyncConnection,
    *,
    municipality_id: uuid.UUID,
    category_id: uuid.UUID,
) -> ServizioComunale | None:
    """Restituisce il mapping categoria-servizio del comune, se configurato."""
    esito = await connessione.execute(
        text(_SQL_SERVIZIO),
        {
            "municipality_id": str(municipality_id),
            "category_id": str(category_id),
        },
    )
    riga = esito.mappings().one_or_none()
    if riga is None:
        return None
    email_cifrata = riga["fallback_email_enc"]
    return ServizioComunale(
        open311_service_code=riga["open311_service_code"],
        open311_extra_fields=riga["open311_extra_fields"],
        fallback_email_enc=bytes(email_cifrata) if email_cifrata else None,
        fallback_active=riga["fallback_active"],
    )


async def carica_nome_categoria(
    connessione: AsyncConnection,
    category_id: uuid.UUID,
) -> str:
    """Restituisce il nome italiano della categoria per il messaggio al comune."""
    esito = await connessione.execute(
        text("SELECT name_i18n FROM category WHERE id = CAST(:category_id AS uuid)"),
        {"category_id": str(category_id)},
    )
    nomi_tradotti = esito.scalar_one()
    return (
        nomi_tradotti.get(LINGUA_PREDEFINITA_CATEGORIA)
        or next(iter(nomi_tradotti.values()))
        or LINGUA_PREDEFINITA_CATEGORIA
    )


async def conta_tentativi_dispatch(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    canale: str,
) -> int:
    """Restituisce il numero di tentativi già registrati per canale."""
    esito = await connessione.execute(
        text("""
            SELECT COALESCE(MAX(attempt_no), 0) AS ultimo_tentativo
            FROM report_dispatch
            WHERE report_id = CAST(:report_id AS uuid)
              AND channel = CAST(:canale AS dispatch_channel)
            """),
        {"report_id": str(report_id), "canale": canale},
    )
    return int(esito.scalar_one())


async def registra_tentativo_dispatch(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID,
    canale: str,
    numero_tentativo: int,
    stato: str,
    http_status: int | None = None,
    provider_request_id: str | None = None,
    error_code: str | None = None,
    error_detail_redacted: str | None = None,
    next_attempt_at: datetime | None = None,
    succeeded_at: datetime | None = None,
) -> uuid.UUID:
    """Scrive una riga di audit per il tentativo e ne restituisce l'identificativo."""
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO report_dispatch (
                id, report_id, municipality_id, channel, attempt_no, status,
                provider_request_id, http_status, error_code,
                error_detail_redacted, next_attempt_at, succeeded_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid),
                CAST(:canale AS dispatch_channel), :numero_tentativo,
                CAST(:stato AS dispatch_attempt_status), :provider_request_id,
                :http_status, :error_code, :error_detail_redacted,
                :next_attempt_at, :succeeded_at
            )
            """),
        {
            "id": str(identificativo),
            "report_id": str(report_id),
            "municipality_id": str(municipality_id),
            "canale": canale,
            "numero_tentativo": numero_tentativo,
            "stato": stato,
            "provider_request_id": provider_request_id,
            "http_status": http_status,
            "error_code": error_code,
            "error_detail_redacted": error_detail_redacted,
            "next_attempt_at": next_attempt_at,
            "succeeded_at": succeeded_at,
        },
    )
    return identificativo


async def aggiorna_stato_dispatch_segnalazione(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    stato: str,
) -> None:
    """Aggiorna la proiezione dello stato di dispatch sulla segnalazione."""
    await connessione.execute(
        text("""
            UPDATE report
            SET dispatch_state = CAST(:stato AS report_dispatch_state),
                updated_at = now()
            WHERE id = CAST(:report_id AS uuid)
            """),
        {"report_id": str(report_id), "stato": stato},
    )
