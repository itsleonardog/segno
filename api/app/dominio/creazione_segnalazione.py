from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.geografia import risolvi_comune_competente, valida_coordinate
from app.dominio.segnalazione import DatiNuovaSegnalazione, Segnalazione
from app.infrastruttura import repository_segnalazioni
from app.infrastruttura.identificativo import genera_identificativo_uuid7
from app.infrastruttura.outbox import inserisci_evento_outbox

EVENTO_SEGNALAZIONE_CREATA = "report.created"
STATO_FUORI_COPERTURA = "out_of_jurisdiction"
STATO_INSTRADATA = "routed"


class CategoriaNonValida(ValueError):  # noqa: N818
    """Segnala una categoria inesistente o non più attiva."""


def componi_public_ref(anno: int, progressivo: int) -> str:
    """Restituisce il riferimento pubblico nel formato CR-YYYY-NNNNNN."""
    return f"CR-{anno:04d}-{progressivo:06d}"


async def crea_segnalazione(
    connessione: AsyncConnection,
    utente_id: uuid.UUID,
    dati: DatiNuovaSegnalazione,
) -> Segnalazione:
    """Crea segnalazione, evento di stato ed evento outbox in una transazione."""
    valida_coordinate(dati.lat, dati.lng)
    if not await repository_segnalazioni.categoria_e_attiva(
        connessione,
        dati.category_id,
    ):
        raise CategoriaNonValida(
            "La categoria scelta non è disponibile. Scegline un'altra."
        )

    comune_competente = await risolvi_comune_competente(
        connessione,
        dati.lat,
        dati.lng,
    )
    progressivo = await repository_segnalazioni.preleva_progressivo_public_ref(
        connessione
    )
    public_ref = componi_public_ref(datetime.now(UTC).year, progressivo)
    segnalazione = await repository_segnalazioni.inserisci_segnalazione(
        connessione,
        identificativo=genera_identificativo_uuid7(),
        public_ref=public_ref,
        municipality_id=(
            comune_competente.id if comune_competente is not None else None
        ),
        author_id=utente_id,
        category_id=dati.category_id,
        title=dati.title,
        description=dati.description,
        lat=dati.lat,
        lng=dati.lng,
        address_label=dati.address_text,
        dispatch_state=(
            STATO_FUORI_COPERTURA if comune_competente is None else STATO_INSTRADATA
        ),
        boundary_ambiguous=(
            comune_competente.is_ambiguo if comune_competente is not None else False
        ),
    )
    await repository_segnalazioni.inserisci_evento_stato(
        connessione,
        report_id=segnalazione.id,
        municipality_id=segnalazione.municipality_id,
        from_status=None,
        to_status="open",
        actor_type="citizen",
        actor_id=utente_id,
        is_public=True,
    )
    await inserisci_evento_outbox(
        connessione,
        aggregate_type="report",
        aggregate_id=segnalazione.id,
        event_type=EVENTO_SEGNALAZIONE_CREATA,
        payload={
            "report_id": str(segnalazione.id),
            "public_ref": segnalazione.public_ref,
            "municipality_id": (
                str(segnalazione.municipality_id)
                if segnalazione.municipality_id
                else None
            ),
            "category_id": str(segnalazione.category_id),
            "photo_url": dati.photo_url,
            "address_text": dati.address_text,
        },
        tenant_id=segnalazione.municipality_id,
    )
    return segnalazione
