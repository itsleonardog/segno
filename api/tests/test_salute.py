from __future__ import annotations

import httpx


async def test_health_liveness_risponde_sempre_200(
    client_auth: httpx.AsyncClient,
) -> None:
    risposta = await client_auth.get("/health")

    assert risposta.status_code == 200
    assert risposta.json() == {"stato": "ok"}


async def test_health_readiness_con_database_disponibile_risponde_200(
    client_auth: httpx.AsyncClient,
) -> None:
    risposta = await client_auth.get("/health/ready")

    assert risposta.status_code == 200
    assert risposta.json() == {"stato": "pronto"}
