from __future__ import annotations

import httpx
from aiuto_autenticazione import effettua_login, registra_utente

INTESTAZIONI_ATTESE = (
    "x-content-type-options",
    "x-frame-options",
    "content-security-policy",
    "strict-transport-security",
)


async def test_middleware_sicurezza_header(client_auth: httpx.AsyncClient) -> None:
    risposta = await client_auth.get("/v1/me")

    assert risposta.status_code == 401
    for intestazione in INTESTAZIONI_ATTESE:
        assert risposta.headers.get(intestazione), intestazione
    assert risposta.headers["x-content-type-options"] == "nosniff"
    assert risposta.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in risposta.headers["content-security-policy"]
    assert risposta.headers["strict-transport-security"].startswith("max-age=")


async def test_rate_limit_login(client_auth: httpx.AsyncClient) -> None:
    registrazione = await registra_utente(client_auth)
    assert registrazione.status_code == 201, registrazione.text

    stati = []
    ultima_risposta: httpx.Response | None = None
    for _ in range(6):
        ultima_risposta = await effettua_login(client_auth)
        stati.append(ultima_risposta.status_code)

    assert stati[:5] == [200, 200, 200, 200, 200]
    assert stati[5] == 429
    assert ultima_risposta is not None
    assert int(ultima_risposta.headers["retry-after"]) >= 1


async def test_rate_limit_registrazione(client_auth: httpx.AsyncClient) -> None:
    for indice in range(5):
        risposta = await registra_utente(
            client_auth,
            email=f"utente.{indice}@example.com",
            nickname=f"utente_{indice}",
        )
        assert risposta.status_code == 201, risposta.text

    sesta = await registra_utente(
        client_auth,
        email="utente.sesta@example.com",
        nickname="utente_sesta",
    )

    assert sesta.status_code == 429
    assert "retry-after" in sesta.headers
