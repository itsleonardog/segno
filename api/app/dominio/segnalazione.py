from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DatiNuovaSegnalazione:
    title: str
    description: str
    category_id: uuid.UUID
    lat: float
    lng: float
    address_text: str | None = None
    photo_url: str | None = None


@dataclass(frozen=True, slots=True)
class DatiModificaSegnalazione:
    title: str | None = None
    description: str | None = None
    category_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class Segnalazione:
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


@dataclass(frozen=True, slots=True)
class EventoStatoSegnalazione:
    id: uuid.UUID
    report_id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_type: str
    note_public: str | None
    is_public: bool
    created_at: datetime
