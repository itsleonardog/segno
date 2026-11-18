from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RispostaNotifica(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    type: str
    channel: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class RispostaElencoNotifiche(BaseModel):
    items: list[RispostaNotifica]
    next_cursor: str | None
    unread_count: int


class RispostaLetteraNotifica(BaseModel):
    letta: bool


class RispostaLetturaCompleta(BaseModel):
    aggiornate: int
