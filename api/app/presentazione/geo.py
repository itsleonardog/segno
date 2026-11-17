from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.geografia import risolvi_comune_competente
from app.infrastruttura.dipendenze import connessione_pubblica
from app.presentazione.schemi_segnalazioni import (
    ComuneRisoltoRisposta,
    RispostaRisoluzioneGeo,
)

router = APIRouter(prefix="/geo", tags=["geografia"])

ConnessionePubblica = Annotated[AsyncConnection, Depends(connessione_pubblica)]


@router.get("/resolve", response_model=RispostaRisoluzioneGeo)
async def risolvi(
    connessione: ConnessionePubblica,
    lat: Annotated[float, Query(ge=-90.0, le=90.0)],
    lng: Annotated[float, Query(ge=-180.0, le=180.0)],
) -> RispostaRisoluzioneGeo:
    comune_competente = await risolvi_comune_competente(connessione, lat, lng)
    if comune_competente is None:
        return RispostaRisoluzioneGeo(comune=None, fuori_copertura=True)
    return RispostaRisoluzioneGeo(
        comune=ComuneRisoltoRisposta(
            id=comune_competente.id,
            slug=comune_competente.slug,
            name=comune_competente.name,
            priority=comune_competente.priority,
            is_ambiguo=comune_competente.is_ambiguo,
        ),
        fuori_copertura=False,
    )
