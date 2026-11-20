from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

PATTERN_NICKNAME = r"^[a-zA-Z0-9_-]{3,30}$"
PATTERN_LOCALE = r"^[a-z]{2}$"


class RichiestaRegistrazione(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=3, max_length=30, pattern=PATTERN_NICKNAME)
    password: str
    privacy_policy_version: str = Field(min_length=1)
    tos_version: str = Field(min_length=1)


class RispostaRegistrazione(BaseModel):
    id: uuid.UUID
    nickname: str
    email_masked: str
    email_verified_at: datetime | None


class RichiestaVerificaEmail(BaseModel):
    token: str = Field(min_length=1)


class RichiestaLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RispostaToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class RichiestaRefresh(BaseModel):
    refresh_token: str = Field(min_length=1)


class RichiestaLogout(BaseModel):
    refresh_token: str = Field(min_length=1)


class RichiestaPasswordDimenticata(BaseModel):
    email: EmailStr


class RichiestaResetPassword(BaseModel):
    token: str = Field(min_length=1)
    new_password: str


class RispostaSessione(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    user_agent_summary: str | None


class RispostaMe(BaseModel):
    id: uuid.UUID
    nickname: str
    email_masked: str
    email_verified_at: datetime | None
    status: str
    created_at: datetime
    last_login_at: datetime | None
    locale: str
    privacy_policy_version: str
    tos_version: str
    is_operatore: bool
    municipality_id: uuid.UUID | None


class RichiestaAggiornamentoMe(BaseModel):
    nickname: str | None = Field(
        default=None,
        min_length=3,
        max_length=30,
        pattern=PATTERN_NICKNAME,
    )
    locale: str | None = Field(default=None, pattern=PATTERN_LOCALE)


class RichiestaCancellazioneAccount(BaseModel):
    password: str = Field(min_length=1)
