from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

LATITUDINE_MINIMA = -90.0
LATITUDINE_MASSIMA = 90.0
LONGITUDINE_MINIMA = -180.0
LONGITUDINE_MASSIMA = 180.0


@dataclass(frozen=True, slots=True)
class ComuneRisolto:
    id: uuid.UUID
    slug: str
    name: str
    priority: int
    is_ambiguo: bool


class CoordinateNonValide(ValueError):  # noqa: N818
    """Segnala coordinate fuori dall'intervallo geografico ammesso."""


def valida_coordinate(lat: float, lng: float) -> None:
    """Solleva CoordinateNonValide se latitudine o longitudine non sono valide."""
    if not math.isfinite(lat) or not LATITUDINE_MINIMA <= lat <= LATITUDINE_MASSIMA:
        raise CoordinateNonValide(
            f"La latitudine deve essere compresa tra {LATITUDINE_MINIMA} e "
            f"{LATITUDINE_MASSIMA}."
        )
    if not math.isfinite(lng) or not LONGITUDINE_MINIMA <= lng <= LONGITUDINE_MASSIMA:
        raise CoordinateNonValide(
            f"La longitudine deve essere compresa tra {LONGITUDINE_MINIMA} e "
            f"{LONGITUDINE_MASSIMA}."
        )


async def risolvi_comune_competente(
    connessione: AsyncConnection,
    lat: float,
    lng: float,
) -> ComuneRisolto | None:
    """Restituisce il comune che copre il punto o None se nessuno lo copre."""
    valida_coordinate(lat, lng)
    # ST_Covers e non ST_Contains: un punto sul confine amministrativo va
    # assegnato. Il predicato esatto usa la geometria perché sulla geography
    # gli spigoli sono archi geodetici e un punto sul bordo planare risulterebbe
    # appena esterno; l'operatore && mantiene l'uso dell'indice GiST.
    esito = await connessione.execute(
        text("""
            SELECT id, slug, name, priority
            FROM municipality
            WHERE is_active = true
              AND boundary && ST_SetSRID(
                  ST_MakePoint(:lng, :lat), 4326
              )::geography
              AND ST_Covers(
                  boundary::geometry,
                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
              )
            ORDER BY priority DESC, ST_Area(boundary) ASC, id ASC
            LIMIT 2
            """),
        {"lat": lat, "lng": lng},
    )
    righe = esito.mappings().all()
    if not righe:
        return None
    prima_riga = righe[0]
    return ComuneRisolto(
        id=prima_riga["id"],
        slug=prima_riga["slug"],
        name=prima_riga["name"],
        priority=prima_riga["priority"],
        is_ambiguo=len(righe) > 1,
    )
