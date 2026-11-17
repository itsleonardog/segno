from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastruttura.dipendenze import get_email_sender
from app.main import crea_app

EMAIL_DI_PROVA = "mario.rossi@example.com"
NICKNAME_DI_PROVA = "mario_rossi"
PASSWORD_DI_PROVA = "PasswordSicura123!"
NUOVA_PASSWORD_DI_PROVA = "PasswordAncoraPiuSicura456!"

PATTERN_TOKEN = re.compile(r"token=([A-Za-z0-9_\-]+)")


@dataclass
class EmailSenderFinto:
    messaggi: list[tuple[str, str, str]] = field(default_factory=list)

    def invia(self, destinatario: str, oggetto: str, corpo: str) -> None:
        self.messaggi.append((destinatario, oggetto, corpo))


def crea_app_di_test(
    motore: AsyncEngine,
    invio_email: EmailSenderFinto,
) -> FastAPI:
    applicazione = crea_app(motore=motore)
    applicazione.dependency_overrides[get_email_sender] = lambda: invio_email
    return applicazione


def estrai_token(messaggio: tuple[str, str, str]) -> str:
    corrispondenza = PATTERN_TOKEN.search(messaggio[2])
    assert corrispondenza is not None, "Il messaggio non contiene un token."
    return corrispondenza.group(1)


def intestazione_bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def registra_utente(
    client: httpx.AsyncClient,
    *,
    email: str = EMAIL_DI_PROVA,
    nickname: str = NICKNAME_DI_PROVA,
    password: str = PASSWORD_DI_PROVA,
) -> httpx.Response:
    return await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "nickname": nickname,
            "password": password,
            "privacy_policy_version": "2026-01",
            "tos_version": "2026-01",
        },
    )


async def effettua_login(
    client: httpx.AsyncClient,
    *,
    email: str = EMAIL_DI_PROVA,
    password: str = PASSWORD_DI_PROVA,
) -> httpx.Response:
    return await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
