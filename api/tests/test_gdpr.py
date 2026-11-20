from __future__ import annotations

import uuid

import httpx
from aiuto_autenticazione import (
    PASSWORD_DI_PROVA,
    effettua_login,
    intestazione_bearer,
)
from aiuto_segnalazioni import crea_segnalazione_api, crea_utente_autenticato
from aiuto_tenant import crea_notifica
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

EMAIL_ESPORTATA = "export.utente@example.com"
NICKNAME_ESPORTATO = "export_utente"
EMAIL_CANCELLATA = "cancella.utente@example.com"
NICKNAME_CANCELLATO = "cancella_utente"


async def test_export_dati_utente(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, utente_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        email=EMAIL_ESPORTATA,
        nickname=NICKNAME_ESPORTATO,
    )
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    public_ref = creata.json()["public_ref"]
    async with motore_amministratore.begin() as connessione:
        await crea_notifica(
            connessione,
            user_id=utente_id,
            dedupe_key=f"export-{uuid.uuid4()}",
        )

    risposta = await client_auth.get(
        "/v1/me/export",
        headers=intestazione_bearer(token),
    )

    assert risposta.status_code == 200, risposta.text
    assert "attachment" in risposta.headers["content-disposition"]
    contenuto = risposta.json()
    assert contenuto["profilo"]["id"] == str(utente_id)
    assert contenuto["profilo"]["nickname"] == NICKNAME_ESPORTATO
    assert contenuto["profilo"]["email"] == EMAIL_ESPORTATA
    assert [voce["public_ref"] for voce in contenuto["segnalazioni"]] == [public_ref]
    assert len(contenuto["notifiche"]) == 1


async def test_cancellazione_account_anonimizza(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
) -> None:
    token, utente_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        email=EMAIL_CANCELLATA,
        nickname=NICKNAME_CANCELLATO,
    )
    creata = await crea_segnalazione_api(client_auth, token, categoria_altro)
    assert creata.status_code == 201, creata.text
    public_ref = creata.json()["public_ref"]

    risposta = await client_auth.request(
        "DELETE",
        "/v1/me",
        headers=intestazione_bearer(token),
        json={"password": PASSWORD_DI_PROVA},
    )

    assert risposta.status_code == 204, risposta.text
    utente = await _leggi_utente(motore_amministratore, utente_id)
    assert utente["status"] == "anonymized"
    assert utente["nickname"].startswith("UtenteCancellato_")
    assert utente["email_enc"] is None
    assert utente["email_lookup_hash"] is None
    assert utente["password_hash"] is None
    autore = await _leggi_autore_segnalazione(motore_amministratore, public_ref)
    assert autore is None
    assert await _conta_sessioni_attive(motore_amministratore, utente_id) == 0

    dettaglio = await client_auth.get(f"/v1/reports/{public_ref}")
    assert dettaglio.status_code == 200
    assert dettaglio.json()["author_id"] is None

    login = await effettua_login(
        client_auth,
        email=EMAIL_CANCELLATA,
        password=PASSWORD_DI_PROVA,
    )
    assert login.status_code == 401


async def test_cancellazione_password_errata_non_anonimizza(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
) -> None:
    token, utente_id = await crea_utente_autenticato(
        client_auth,
        motore_amministratore,
        email=EMAIL_CANCELLATA,
        nickname=NICKNAME_CANCELLATO,
    )

    risposta = await client_auth.request(
        "DELETE",
        "/v1/me",
        headers=intestazione_bearer(token),
        json={"password": "PasswordSbagliata123!"},
    )

    assert risposta.status_code == 403
    utente = await _leggi_utente(motore_amministratore, utente_id)
    assert utente["status"] == "active"
    assert utente["password_hash"] is not None


async def _leggi_utente(motore: AsyncEngine, utente_id: uuid.UUID) -> dict[str, object]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT nickname, status, email_enc, email_lookup_hash, password_hash
                FROM "user" WHERE id = CAST(:utente_id AS uuid)
                """),
            {"utente_id": str(utente_id)},
        )
        return dict(esito.mappings().one())


async def _leggi_autore_segnalazione(
    motore: AsyncEngine,
    public_ref: str,
) -> uuid.UUID | None:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("SELECT author_id FROM report WHERE public_ref = :public_ref"),
            {"public_ref": public_ref},
        )
        return esito.scalar_one()


async def _conta_sessioni_attive(
    motore: AsyncEngine,
    utente_id: uuid.UUID,
) -> int:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT count(*) FROM refresh_token
                WHERE user_id = CAST(:utente_id AS uuid) AND revoked_at IS NULL
                """),
            {"utente_id": str(utente_id)},
        )
        return int(esito.scalar_one())
