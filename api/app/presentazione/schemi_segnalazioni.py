from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.dominio.esempio_segnalazione import StatoSegnalazione

LATITUDINE_MINIMA = -90.0
LATITUDINE_MASSIMA = 90.0
LONGITUDINE_MINIMA = -180.0
LONGITUDINE_MASSIMA = 180.0


class RichiestaCreazioneSegnalazione(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    category_id: uuid.UUID
    lat: float = Field(ge=LATITUDINE_MINIMA, le=LATITUDINE_MASSIMA)
    lng: float = Field(ge=LONGITUDINE_MINIMA, le=LONGITUDINE_MASSIMA)
    address_text: str | None = Field(default=None, max_length=500)
    photo_url: str | None = Field(default=None, max_length=2000)


class RichiestaModificaSegnalazione(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    category_id: uuid.UUID | None = None


class RichiestaCambioStato(BaseModel):
    status: StatoSegnalazione
    note_public: str | None = Field(default=None, max_length=1000)


class RispostaSegnalazione(BaseModel):
    id: uuid.UUID
    public_ref: str
    municipality_id: uuid.UUID | None
    author_id: uuid.UUID | None
    category_id: uuid.UUID
    title: str
    description: str
    lat: float
    lng: float
    address_text: str | None
    status: str
    visibility: str
    dispatch_state: str
    boundary_ambiguous: bool
    created_at: datetime


class EventoStatoPubblico(BaseModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_type: str
    note_public: str | None
    created_at: datetime


class RispostaDettaglioSegnalazione(RispostaSegnalazione):
    status_events: list[EventoStatoPubblico]


class RispostaElencoSegnalazioni(BaseModel):
    items: list[RispostaSegnalazione]
    next_cursor: str | None


class ComuneRisoltoRisposta(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    priority: int
    is_ambiguo: bool


class RispostaRisoluzioneGeo(BaseModel):
    comune: ComuneRisoltoRisposta | None
    fuori_copertura: bool
