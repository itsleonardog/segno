from __future__ import annotations

import logging

import httpx
from aiuto_dispatch import (
    CHIAVE_API_DI_PROVA,
    trasporto_che_fallisce,
    trasporto_con_risposta,
)

from app.dominio.dispatch import CausaErroreTrasporto, ErroreTrasportoOpen311
from app.infrastruttura.adattatore_open311 import AdattatoreOpen311

ENDPOINT_OPEN311 = "https://api.comune.test/v2/requests"


async def test_adattatore_open311_successo() -> None:
    richieste: list[httpx.Request] = []

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        richieste.append(richiesta)
        return httpx.Response(201, json=[{"service_request_id": "SR-2026-1"}])

    adattatore = AdattatoreOpen311(trasporto=httpx.MockTransport(gestore))

    risultato = await adattatore.invia_segnalazione(
        ENDPOINT_OPEN311,
        CHIAVE_API_DI_PROVA,
        {"service_code": "STRADE-1", "description": "Lampione spento"},
    )

    assert risultato.service_request_id == "SR-2026-1"
    assert risultato.status_code == 201
    assert risultato.errore is None
    richiesta = richieste[0]
    assert richiesta.headers["content-type"].startswith(
        "application/x-www-form-urlencoded"
    )
    corpo = richiesta.content.decode()
    assert "service_code=STRADE-1" in corpo
    assert f"api_key={CHIAVE_API_DI_PROVA}" in corpo
    assert CHIAVE_API_DI_PROVA not in str(richiesta.url)


async def test_adattatore_open311_timeout() -> None:
    adattatore = AdattatoreOpen311(
        trasporto=trasporto_che_fallisce(httpx.ReadTimeout("timeout simulato"))
    )

    risultato = await adattatore.invia_segnalazione(
        ENDPOINT_OPEN311,
        CHIAVE_API_DI_PROVA,
        {"service_code": "STRADE-1"},
    )

    assert risultato.service_request_id is None
    assert risultato.status_code is None
    assert isinstance(risultato.errore, ErroreTrasportoOpen311)
    assert risultato.errore.causa is CausaErroreTrasporto.TIMEOUT


async def test_adattatore_open311_dns_non_risolto() -> None:
    errore_dns = httpx.ConnectError(
        "[Errno -2] Name or service not known",
    )
    adattatore = AdattatoreOpen311(
        trasporto=trasporto_che_fallisce(errore_dns),
    )

    risultato = await adattatore.invia_segnalazione(
        ENDPOINT_OPEN311,
        None,
        {"service_code": "STRADE-1"},
    )

    assert isinstance(risultato.errore, ErroreTrasportoOpen311)
    assert risultato.errore.causa is CausaErroreTrasporto.DNS


async def test_adattatore_open311_risposta_senza_identificativo() -> None:
    adattatore = AdattatoreOpen311(
        trasporto=trasporto_con_risposta({"esito": "ok"}, status_code=200)
    )

    risultato = await adattatore.invia_segnalazione(
        ENDPOINT_OPEN311,
        None,
        {"service_code": "STRADE-1"},
    )

    assert risultato.service_request_id is None
    assert risultato.status_code == 200


async def test_nessuna_api_key_nei_log(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    endpoint_con_chiave = (
        f"{ENDPOINT_OPEN311}?api_key={CHIAVE_API_DI_PROVA}&jurisdiction_id=comune"
    )
    adattatore = AdattatoreOpen311(
        trasporto=trasporto_con_risposta({"service_request_id": "SR-2026-1"})
    )

    await adattatore.invia_segnalazione(
        endpoint_con_chiave,
        CHIAVE_API_DI_PROVA,
        {"service_code": "STRADE-1"},
    )

    assert CHIAVE_API_DI_PROVA not in caplog.text
