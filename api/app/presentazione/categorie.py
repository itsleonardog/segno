from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncConnection

from app.infrastruttura.dipendenze import connessione_pubblica
from app.infrastruttura.repository_categorie import elenca_categorie_attive
from app.presentazione.schemi_categorie import CategoriaRisposta

router = APIRouter(tags=["categorie"])

ConnessionePubblica = Annotated[AsyncConnection, Depends(connessione_pubblica)]


@router.get("/categories", response_model=list[CategoriaRisposta])
async def elenca_categorie(
    connessione: ConnessionePubblica,
) -> list[CategoriaRisposta]:
    categorie = await elenca_categorie_attive(connessione)
    return [
        CategoriaRisposta(
            id=categoria.id,
            slug=categoria.slug,
            name_i18n=categoria.name_i18n,
            icon=categoria.icon,
        )
        for categoria in categorie
    ]
