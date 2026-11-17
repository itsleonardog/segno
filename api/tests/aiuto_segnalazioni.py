from __future__ import annotations

import uuid
from typing import Any

import httpx
from aiuto_autenticazione import effettua_login, intestazione_bearer, registra_utente
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LATITUDINE_COMUNE_A = 45.05
LONGITUDINE_COMUNE_A = 9.05


async def crea_utente_autenticato(
    client: httpx.AsyncClient,
    motore: AsyncEngine,
    *,
    operatore: bool = False,
) -> tuple[str, uuid.UUID]:
    suffisso = uuid.uuid4().hex[:10]
    email = f"utente.{suffisso}@example.com"
    nickname = f"utente_{suffisso}"
    registrazione = await registra_utente(
        client,
        email=email,
        nickname=nickname,
    )
    assert registrazione.status_code == 201, registrazione.text
    utente_id = uuid.UUID(registrazione.json()["id"])
    if operatore:
        async with motore.begin() as connessione:
            await connessione.execute(
                text("""
                    UPDATE "user" SET is_operatore = true
                    WHERE id = CAST(:utente_id AS uuid)
                    """),
                {"utente_id": str(utente_id)},
            )
    accesso = await effettua_login(client, email=email)
    assert accesso.status_code == 200, accesso.text
    return accesso.json()["access_token"], utente_id


def intestazioni_creazione(access_token: str, chiave: str) -> dict[str, str]:
    return {
        **intestazione_bearer(access_token),
        "Idempotency-Key": chiave,
    }


def corpo_creazione(
    category_id: str,
    *,
    lat: float = LATITUDINE_COMUNE_A,
    lng: float = LONGITUDINE_COMUNE_A,
    title: str = "Lampione spento",
    description: str = "Il lampione davanti al civico 12 non si accende.",
    address_text: str | None = "Via Roma 12",
    photo_url: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "category_id": category_id,
        "lat": lat,
        "lng": lng,
        "address_text": address_text,
        "photo_url": photo_url,
    }


async def crea_segnalazione_api(
    client: httpx.AsyncClient,
    access_token: str,
    category_id: str,
    *,
    chiave: str | None = None,
    lat: float = LATITUDINE_COMUNE_A,
    lng: float = LONGITUDINE_COMUNE_A,
    title: str = "Lampione spento",
) -> httpx.Response:
    return await client.post(
        "/v1/reports",
        json=corpo_creazione(category_id, lat=lat, lng=lng, title=title),
        headers=intestazioni_creazione(
            access_token,
            chiave or f"chiave-{uuid.uuid4()}",
        ),
    )


async def ottieni_id_categoria(motore: AsyncEngine, slug: str) -> str:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("SELECT id FROM category WHERE slug = :slug"),
            {"slug": slug},
        )
    return str(esito.scalar_one())


async def conta_righe_per_report(
    motore: AsyncEngine,
    tabella: str,
    colonna: str,
    report_id: uuid.UUID,
) -> int:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text(
                f'SELECT count(*) FROM "{tabella}" WHERE {colonna} = CAST(:id AS uuid)'
            ),
            {"id": str(report_id)},
        )
    return int(esito.scalar_one())
