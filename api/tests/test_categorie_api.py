from __future__ import annotations

import httpx

SLUG_CATEGORIE_ATTESE = {"strade", "illuminazione", "rifiuti", "altro"}
NUMERO_CATEGORIE_ATTESE = 4


async def test_elenco_categorie_restituisce_quattro_categorie_attive(
    client_auth: httpx.AsyncClient,
) -> None:
    risposta = await client_auth.get("/v1/categories")

    assert risposta.status_code == 200, risposta.text
    categorie = risposta.json()
    assert len(categorie) == NUMERO_CATEGORIE_ATTESE
    assert {categoria["slug"] for categoria in categorie} == SLUG_CATEGORIE_ATTESE
    assert all(categoria["name_i18n"]["it"] for categoria in categorie)
    assert all(categoria["icon"] for categoria in categorie)
