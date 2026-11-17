from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.segnalazione import EventoStatoSegnalazione, Segnalazione
from app.infrastruttura.identificativo import genera_identificativo_uuid7

_CAMPI_SEGNALAZIONE = """
    id, public_ref, municipality_id, author_id, category_id, title,
    description, ST_Y(location::geometry) AS latitudine,
    ST_X(location::geometry) AS longitudine, address_label, status,
    visibility, dispatch_state, boundary_ambiguous, created_at
"""

_SQL_SEGNALAZIONE = f"SELECT {_CAMPI_SEGNALAZIONE} FROM report"


@dataclass(frozen=True, slots=True)
class FiltriElencoSegnalazioni:
    lat_min: float | None = None
    lat_max: float | None = None
    lng_min: float | None = None
    lng_max: float | None = None
    category: str | None = None
    status: str | None = None
    municipality_id: uuid.UUID | None = None


async def preleva_progressivo_public_ref(connessione: AsyncConnection) -> int:
    """Restituisce il prossimo progressivo della sequenza dei riferimenti pubblici."""
    esito = await connessione.execute(text("SELECT nextval('seq_report_public_ref')"))
    return int(esito.scalar_one())


async def categoria_e_attiva(
    connessione: AsyncConnection,
    category_id: uuid.UUID,
) -> bool:
    """Indica se la categoria esiste ed è attiva."""
    esito = await connessione.execute(
        text("""
            SELECT EXISTS(
                SELECT 1 FROM category
                WHERE id = CAST(:category_id AS uuid) AND is_active = true
            )
            """),
        {"category_id": str(category_id)},
    )
    return bool(esito.scalar_one())


async def utente_e_operatore(
    connessione: AsyncConnection,
    user_id: uuid.UUID,
) -> bool:
    """Indica se l'utente ha il ruolo di operatore comunale."""
    esito = await connessione.execute(
        text("""
            SELECT COALESCE(
                (SELECT is_operatore FROM "user" WHERE id = CAST(:user_id AS uuid)),
                false
            )
            """),
        {"user_id": str(user_id)},
    )
    return bool(esito.scalar_one())


async def inserisci_segnalazione(
    connessione: AsyncConnection,
    *,
    identificativo: uuid.UUID,
    public_ref: str,
    municipality_id: uuid.UUID | None,
    author_id: uuid.UUID,
    category_id: uuid.UUID,
    title: str,
    description: str,
    lat: float,
    lng: float,
    address_label: str | None,
    dispatch_state: str,
    boundary_ambiguous: bool,
) -> Segnalazione:
    """Inserisce la riga della segnalazione e restituisce il record creato."""
    esito = await connessione.execute(
        text(f"""
            INSERT INTO report (
                id, public_ref, municipality_id, author_id, category_id,
                title, description, location, address_label, status,
                visibility, dispatch_state, boundary_ambiguous,
                jurisdiction_resolved_at
            )
            VALUES (
                CAST(:id AS uuid), :public_ref, CAST(:municipality_id AS uuid),
                CAST(:author_id AS uuid), CAST(:category_id AS uuid),
                :title, :description,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :address_label, CAST('open' AS report_status),
                CAST('public' AS report_visibility),
                CAST(:dispatch_state AS report_dispatch_state),
                :boundary_ambiguous, now()
            )
            RETURNING {_CAMPI_SEGNALAZIONE}
            """),
        {
            "id": str(identificativo),
            "public_ref": public_ref,
            "municipality_id": str(municipality_id) if municipality_id else None,
            "author_id": str(author_id),
            "category_id": str(category_id),
            "title": title,
            "description": description,
            "lat": lat,
            "lng": lng,
            "address_label": address_label,
            "dispatch_state": dispatch_state,
            "boundary_ambiguous": boundary_ambiguous,
        },
    )
    return _mappa_segnalazione(esito.mappings().one())


async def carica_segnalazione_per_id(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> Segnalazione | None:
    """Restituisce la segnalazione per identificativo o None se non esiste."""
    esito = await connessione.execute(
        text(f"{_SQL_SEGNALAZIONE} WHERE id = CAST(:report_id AS uuid)"),
        {"report_id": str(report_id)},
    )
    riga = esito.mappings().one_or_none()
    return _mappa_segnalazione(riga) if riga else None


async def carica_segnalazione_per_public_ref(
    connessione: AsyncConnection,
    public_ref: str,
) -> Segnalazione | None:
    """Restituisce la segnalazione per riferimento pubblico o None se non esiste."""
    esito = await connessione.execute(
        text(f"{_SQL_SEGNALAZIONE} WHERE public_ref = :public_ref"),
        {"public_ref": public_ref},
    )
    riga = esito.mappings().one_or_none()
    return _mappa_segnalazione(riga) if riga else None


async def inserisci_evento_stato(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    municipality_id: uuid.UUID | None,
    from_status: str | None,
    to_status: str,
    actor_type: str,
    actor_id: uuid.UUID | None,
    note_public: str | None = None,
    is_public: bool = True,
) -> uuid.UUID:
    """Accoda un evento di stato append-only e restituisce il suo identificativo."""
    identificativo = genera_identificativo_uuid7()
    await connessione.execute(
        text("""
            INSERT INTO report_status_event (
                id, report_id, municipality_id, from_status, to_status,
                actor_type, actor_id, note_public, is_public
            )
            VALUES (
                CAST(:id AS uuid), CAST(:report_id AS uuid),
                CAST(:municipality_id AS uuid),
                CAST(:from_status AS report_status),
                CAST(:to_status AS report_status),
                CAST(:actor_type AS actor_type), CAST(:actor_id AS uuid),
                :note_public, :is_public
            )
            """),
        {
            "id": str(identificativo),
            "report_id": str(report_id),
            "municipality_id": str(municipality_id) if municipality_id else None,
            "from_status": from_status,
            "to_status": to_status,
            "actor_type": actor_type,
            "actor_id": str(actor_id) if actor_id else None,
            "note_public": note_public,
            "is_public": is_public,
        },
    )
    return identificativo


async def elenca_eventi_pubblici(
    connessione: AsyncConnection,
    report_id: uuid.UUID,
) -> list[EventoStatoSegnalazione]:
    """Restituisce gli eventi di stato pubblici in ordine cronologico."""
    esito = await connessione.execute(
        text("""
            SELECT id, report_id, from_status, to_status, actor_type,
                   note_public, is_public, created_at
            FROM report_status_event
            WHERE report_id = CAST(:report_id AS uuid) AND is_public = true
            ORDER BY created_at ASC, id ASC
            """),
        {"report_id": str(report_id)},
    )
    return [
        EventoStatoSegnalazione(
            id=riga["id"],
            report_id=riga["report_id"],
            from_status=riga["from_status"],
            to_status=riga["to_status"],
            actor_type=riga["actor_type"],
            note_public=riga["note_public"],
            is_public=riga["is_public"],
            created_at=riga["created_at"],
        )
        for riga in esito.mappings().all()
    ]


async def aggiorna_contenuti(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    title: str | None,
    description: str | None,
    category_id: uuid.UUID | None,
) -> None:
    """Aggiorna i campi modificabili della segnalazione."""
    await connessione.execute(
        text("""
            UPDATE report
            SET title = COALESCE(:title, title),
                description = COALESCE(:description, description),
                category_id = COALESCE(
                    CAST(:category_id AS uuid),
                    category_id
                ),
                updated_at = now(),
                version = version + 1
            WHERE id = CAST(:report_id AS uuid)
            """),
        {
            "report_id": str(report_id),
            "title": title,
            "description": description,
            "category_id": str(category_id) if category_id else None,
        },
    )


async def aggiorna_stato(
    connessione: AsyncConnection,
    *,
    report_id: uuid.UUID,
    stato: str,
) -> None:
    """Proietta il nuovo stato civico sulla riga della segnalazione."""
    await connessione.execute(
        text("""
            UPDATE report
            SET status = CAST(:stato AS report_status),
                status_changed_at = now(),
                updated_at = now(),
                version = version + 1,
                resolved_at = CASE
                    WHEN CAST(:stato AS text) = 'resolved' THEN now()
                    ELSE resolved_at
                END,
                closed_at = CASE
                    WHEN CAST(:stato AS text) = 'closed' THEN now()
                    ELSE closed_at
                END
            WHERE id = CAST(:report_id AS uuid)
            """),
        {"report_id": str(report_id), "stato": stato},
    )


async def elenca_segnalazioni_pubbliche(
    connessione: AsyncConnection,
    *,
    filtri: FiltriElencoSegnalazioni,
    cursore: uuid.UUID | None,
    limite: int,
) -> list[Segnalazione]:
    """Restituisce una pagina di segnalazioni pubbliche filtrate."""
    condizioni = [
        "deleted_at IS NULL",
        "visibility = CAST('public' AS report_visibility)",
    ]
    parametri: dict[str, object] = {"limite": limite}
    _applica_filtri(condizioni, parametri, filtri)
    if cursore is not None:
        condizioni.append("id > CAST(:cursore AS uuid)")
        parametri["cursore"] = str(cursore)
    esito = await connessione.execute(
        text(
            f"{_SQL_SEGNALAZIONE} WHERE {' AND '.join(condizioni)} "
            "ORDER BY id ASC LIMIT :limite"
        ),
        parametri,
    )
    return [_mappa_segnalazione(riga) for riga in esito.mappings().all()]


def _applica_filtri(
    condizioni: list[str],
    parametri: dict[str, object],
    filtri: FiltriElencoSegnalazioni,
) -> None:
    if filtri.lat_min is not None:
        condizioni.append(
            "location && ST_MakeEnvelope("
            ":lng_min, :lat_min, :lng_max, :lat_max, 4326)::geography"
        )
        parametri.update(
            {
                "lat_min": filtri.lat_min,
                "lat_max": filtri.lat_max,
                "lng_min": filtri.lng_min,
                "lng_max": filtri.lng_max,
            }
        )
    if filtri.category is not None:
        _applica_filtro_categoria(condizioni, parametri, filtri.category)
    if filtri.status is not None:
        condizioni.append("status = CAST(:status AS report_status)")
        parametri["status"] = filtri.status
    if filtri.municipality_id is not None:
        condizioni.append("municipality_id = CAST(:municipality_id AS uuid)")
        parametri["municipality_id"] = str(filtri.municipality_id)


def _applica_filtro_categoria(
    condizioni: list[str],
    parametri: dict[str, object],
    categoria: str,
) -> None:
    try:
        categoria_id = uuid.UUID(categoria)
    except ValueError:
        condizioni.append(
            "category_id IN (SELECT id FROM category WHERE slug = :categoria_slug)"
        )
        parametri["categoria_slug"] = categoria
        return
    condizioni.append("category_id = CAST(:categoria_id AS uuid)")
    parametri["categoria_id"] = str(categoria_id)


def _mappa_segnalazione(riga: Mapping[str, object]) -> Segnalazione:
    return Segnalazione(
        id=riga["id"],
        public_ref=riga["public_ref"],
        municipality_id=riga["municipality_id"],
        author_id=riga["author_id"],
        category_id=riga["category_id"],
        title=riga["title"],
        description=riga["description"],
        lat=riga["latitudine"],
        lng=riga["longitudine"],
        address_text=riga["address_label"],
        status=riga["status"],
        visibility=riga["visibility"],
        dispatch_state=riga["dispatch_state"],
        boundary_ambiguous=riga["boundary_ambiguous"],
        created_at=riga["created_at"],
    )
