from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.presentazione.schemi_segnalazioni import RispostaSegnalazione

LUNGHEZZA_MASSIMA_NOTA_INTERNA = 2000


class RichiestaNotaInterna(BaseModel):
    body: str = Field(min_length=1, max_length=LUNGHEZZA_MASSIMA_NOTA_INTERNA)


class EventoStatoAmministrazioneRisposta(BaseModel):
    id: uuid.UUID
    from_status: str | None
    to_status: str
    actor_type: str
    note_public: str | None
    is_public: bool
    created_at: datetime


class TentativoDispatchRisposta(BaseModel):
    id: uuid.UUID
    channel: str
    attempt_no: int
    status: str
    provider_request_id: str | None
    http_status: int | None
    error_code: str | None
    error_detail_redacted: str | None
    next_attempt_at: datetime | None
    succeeded_at: datetime | None
    created_at: datetime


class NotaInternaRisposta(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID | None
    body: str
    created_at: datetime


class RispostaDettaglioAmministrazione(RispostaSegnalazione):
    status_events: list[EventoStatoAmministrazioneRisposta]
    dispatch_history: list[TentativoDispatchRisposta]
    internal_notes: list[NotaInternaRisposta]


class RispostaElencoAmministrazione(BaseModel):
    items: list[RispostaSegnalazione]
    next_cursor: str | None


class RispostaFallimentoDispatch(BaseModel):
    report_id: uuid.UUID
    public_ref: str
    title: str
    dispatch: TentativoDispatchRisposta


class RispostaElencoFallimenti(BaseModel):
    items: list[RispostaFallimentoDispatch]


class RispostaRiprogrammazioneDispatch(BaseModel):
    event_id: uuid.UUID
