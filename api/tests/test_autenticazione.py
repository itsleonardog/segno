from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

import httpx
import pytest
from aiuto_autenticazione import (
    EMAIL_DI_PROVA,
    NICKNAME_DI_PROVA,
    NUOVA_PASSWORD_DI_PROVA,
    PASSWORD_DI_PROVA,
    EmailSenderFinto,
    effettua_login,
    estrai_token,
    intestazione_bearer,
    registra_utente,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.autenticazione import genera_token_opaco, hash_token_opaco
from app.main import crea_app

RADICE_APP = Path(__file__).resolve().parents[1] / "app"
PATTERN_AMBITO_SISTEMA = re.compile(
    r"access_scope\s*=\s*['\"]system['\"]|scope\s*=\s*['\"]system['\"]"
)
# L'ambito system è ammesso solo fuori dal ciclo di richiesta: autenticazione
# (lookup prima del tenant) e worker dell'outbox (legge tutti gli eventi).
FILE_CON_AMBITO_SISTEMA_AMMESSI = {
    "app/presentazione/auth.py",
    "app/worker.py",
}


class HandlerCatturaLog(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.registrazioni: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registrazioni.append(record)


async def _leggi_utente(motore: AsyncEngine):
    async with motore.connect() as connessione:
        esito = await connessione.execute(text('SELECT * FROM "user"'))
        return esito.mappings().one()


async def _crea_token_reset_scaduto(motore: AsyncEngine) -> str:
    token = genera_token_opaco()
    async with motore.begin() as connessione:
        utente_id = (
            await connessione.execute(text('SELECT id FROM "user"'))
        ).scalar_one()
        await connessione.execute(
            text("""
                INSERT INTO password_reset_token (
                    id, user_id, token_hash, expires_at
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:user_id AS uuid), :token_hash,
                    now() - interval '1 minute'
                )
                """),
            {
                "id": str(uuid.uuid4()),
                "user_id": str(utente_id),
                "token_hash": hash_token_opaco(token),
            },
        )
    return token


async def test_registrazione_email_cifrata(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
) -> None:
    risposta = await registra_utente(client_auth)

    assert risposta.status_code == 201
    riga = await _leggi_utente(motore_amministratore)
    assert riga["email_enc"]
    assert riga["email_key_id"] == "dev-v1"
    assert len(riga["email_lookup_hash"]) == 64
    assert EMAIL_DI_PROVA not in str(dict(riga))


async def test_registrazione_email_duplicata(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth, nickname="nickname_uno")

    risposta = await registra_utente(client_auth, nickname="nickname_due")

    assert risposta.status_code == 409


async def test_registrazione_nickname_duplicato(
    client_auth: httpx.AsyncClient,
) -> None:
    await registra_utente(client_auth, email="uno@example.com")

    risposta = await registra_utente(client_auth, email="due@example.com")

    assert risposta.status_code == 409


async def test_messaggi_duplicati_registrazione_identici(
    client_auth: httpx.AsyncClient,
) -> None:
    await registra_utente(client_auth, email="uno@example.com", nickname="nick_uno")

    duplicato_email = await registra_utente(
        client_auth,
        email="uno@example.com",
        nickname="nick_due",
    )
    duplicato_nickname = await registra_utente(
        client_auth,
        email="due@example.com",
        nickname="nick_uno",
    )

    assert duplicato_email.status_code == 409
    assert duplicato_nickname.status_code == 409
    assert duplicato_email.json()["detail"] == duplicato_nickname.json()["detail"]


async def test_login_riuscito(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)

    risposta = await effettua_login(client_auth)

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["expires_in"] == 900
    assert corpo["access_token"]
    assert corpo["refresh_token"]

    profilo = await client_auth.get(
        "/v1/me",
        headers=intestazione_bearer(corpo["access_token"]),
    )
    assert profilo.status_code == 200
    assert profilo.json()["nickname"] == NICKNAME_DI_PROVA


async def test_login_password_errata(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)

    risposta = await effettua_login(client_auth, password="PasswordSbagliata123")

    assert risposta.status_code == 401


async def test_login_utente_inesistente(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)
    password_errata = await effettua_login(
        client_auth,
        password="PasswordSbagliata123",
    )
    utente_inesistente = await effettua_login(
        client_auth,
        email="nessuno@example.com",
        password=PASSWORD_DI_PROVA,
    )

    assert utente_inesistente.status_code == 401
    assert utente_inesistente.json()["detail"] == password_errata.json()["detail"]


async def test_refresh_ruota_token(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)
    login = await effettua_login(client_auth)
    primo_refresh = login.json()["refresh_token"]

    prima_rotazione = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": primo_refresh},
    )
    secondo_refresh = prima_rotazione.json()["refresh_token"]

    seconda_rotazione = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": secondo_refresh},
    )
    riuso_primo = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": primo_refresh},
    )

    assert prima_rotazione.status_code == 200
    assert secondo_refresh != primo_refresh
    assert seconda_rotazione.status_code == 200
    assert riuso_primo.status_code == 401


async def test_riuso_refresh_token_revocato_revoca_famiglia(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
) -> None:
    await registra_utente(client_auth)
    login = await effettua_login(client_auth)
    primo_refresh = login.json()["refresh_token"]
    rotazione = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": primo_refresh},
    )
    secondo_refresh = rotazione.json()["refresh_token"]

    riuso = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": primo_refresh},
    )
    nuovo_dopo_riuso = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": secondo_refresh},
    )

    async with motore_amministratore.connect() as connessione:
        azioni_audit = (await connessione.execute(text("""
                    SELECT action FROM audit_log
                    WHERE action = 'refresh_token_reuse'
                    """))).scalars().all()

    assert riuso.status_code == 401
    assert nuovo_dopo_riuso.status_code == 401
    assert "refresh_token_reuse" in azioni_audit


async def test_logout_revoca_solo_corrente(
    client_auth: httpx.AsyncClient,
) -> None:
    await registra_utente(client_auth)
    sessione_a = (await effettua_login(client_auth)).json()
    sessione_b = (await effettua_login(client_auth)).json()

    logout = await client_auth.post(
        "/v1/auth/logout",
        headers=intestazione_bearer(sessione_a["access_token"]),
        json={"refresh_token": sessione_a["refresh_token"]},
    )
    refresh_revocato = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": sessione_a["refresh_token"]},
    )
    refresh_valido = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": sessione_b["refresh_token"]},
    )

    assert logout.status_code == 204
    assert refresh_revocato.status_code == 401
    assert refresh_valido.status_code == 200


async def test_logout_all_revoca_tutte_le_famiglie(
    client_auth: httpx.AsyncClient,
) -> None:
    await registra_utente(client_auth)
    sessione_a = (await effettua_login(client_auth)).json()
    sessione_b = (await effettua_login(client_auth)).json()

    logout = await client_auth.post(
        "/v1/auth/logout-all",
        headers=intestazione_bearer(sessione_a["access_token"]),
    )
    refresh_a = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": sessione_a["refresh_token"]},
    )
    refresh_b = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": sessione_b["refresh_token"]},
    )

    assert logout.status_code == 204
    assert refresh_a.status_code == 401
    assert refresh_b.status_code == 401


async def test_password_forgot_email_inesistente_202(
    client_auth: httpx.AsyncClient,
    invio_email_finto: EmailSenderFinto,
) -> None:
    email_inesistente = await client_auth.post(
        "/v1/auth/password/forgot",
        json={"email": "nessuno@example.com"},
    )
    await registra_utente(client_auth)
    email_esistente = await client_auth.post(
        "/v1/auth/password/forgot",
        json={"email": EMAIL_DI_PROVA},
    )

    assert email_inesistente.status_code == 202
    assert email_esistente.status_code == 202
    assert email_inesistente.content == email_esistente.content
    assert email_inesistente.headers == email_esistente.headers
    assert len(invio_email_finto.messaggi) == 2


async def test_password_reset_valido_revoca_sessioni(
    client_auth: httpx.AsyncClient,
    invio_email_finto: EmailSenderFinto,
) -> None:
    await registra_utente(client_auth)
    login = await effettua_login(client_auth)
    refresh_token = login.json()["refresh_token"]
    await client_auth.post(
        "/v1/auth/password/forgot",
        json={"email": EMAIL_DI_PROVA},
    )
    token_reset = estrai_token(invio_email_finto.messaggi[-1])

    reset = await client_auth.post(
        "/v1/auth/password/reset",
        json={"token": token_reset, "new_password": NUOVA_PASSWORD_DI_PROVA},
    )
    refresh_vecchio = await client_auth.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    login_vecchia_password = await effettua_login(client_auth)
    login_nuova_password = await effettua_login(
        client_auth,
        password=NUOVA_PASSWORD_DI_PROVA,
    )

    assert reset.status_code == 204
    assert refresh_vecchio.status_code == 401
    assert login_vecchia_password.status_code == 401
    assert login_nuova_password.status_code == 200


async def test_password_reset_token_scaduto_400(
    client_auth: httpx.AsyncClient,
    motore_amministratore: AsyncEngine,
) -> None:
    await registra_utente(client_auth)
    token_scaduto = await _crea_token_reset_scaduto(motore_amministratore)

    risposta = await client_auth.post(
        "/v1/auth/password/reset",
        json={"token": token_scaduto, "new_password": NUOVA_PASSWORD_DI_PROVA},
    )

    assert risposta.status_code == 400


async def test_verify_email_valido_setta_email_verified_at(
    client_auth: httpx.AsyncClient,
    invio_email_finto: EmailSenderFinto,
    motore_amministratore: AsyncEngine,
) -> None:
    await registra_utente(client_auth)
    token_verifica = estrai_token(invio_email_finto.messaggi[0])

    verifica = await client_auth.post(
        "/v1/auth/verify-email",
        json={"token": token_verifica},
    )
    riga = await _leggi_utente(motore_amministratore)
    login = await effettua_login(client_auth)
    profilo = await client_auth.get(
        "/v1/me",
        headers=intestazione_bearer(login.json()["access_token"]),
    )

    assert verifica.status_code == 204
    assert riga["email_verified_at"] is not None
    assert profilo.json()["email_verified_at"] is not None


async def test_me_senza_token_401(client_auth: httpx.AsyncClient) -> None:
    risposta = await client_auth.get("/v1/me")

    assert risposta.status_code == 401


async def test_me_email_masked(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)
    login = await effettua_login(client_auth)

    risposta = await client_auth.get(
        "/v1/me",
        headers=intestazione_bearer(login.json()["access_token"]),
    )

    assert risposta.status_code == 200
    assert "*" in risposta.json()["email_masked"]


async def test_me_email_mai_in_chiaro(client_auth: httpx.AsyncClient) -> None:
    await registra_utente(client_auth)
    login = await effettua_login(client_auth)

    risposta = await client_auth.get(
        "/v1/me",
        headers=intestazione_bearer(login.json()["access_token"]),
    )

    assert EMAIL_DI_PROVA not in json.dumps(risposta.json())
    assert EMAIL_DI_PROVA not in risposta.text


async def test_patch_me_nickname_duplicato_409(
    client_auth: httpx.AsyncClient,
) -> None:
    await registra_utente(client_auth, email="uno@example.com", nickname="nick_uno")
    await registra_utente(client_auth, email="due@example.com", nickname="nick_due")
    login = await effettua_login(client_auth, email="due@example.com")

    risposta = await client_auth.patch(
        "/v1/me",
        headers=intestazione_bearer(login.json()["access_token"]),
        json={"nickname": "nick_uno"},
    )

    assert risposta.status_code == 409


async def test_nessuna_email_in_log(
    motore_applicazione: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIVIC_ENV", "dev")
    handler = HandlerCatturaLog()
    logger_radice = logging.getLogger()
    logger_radice.addHandler(handler)
    logger_radice.setLevel(logging.INFO)
    try:
        applicazione = crea_app(motore=motore_applicazione)
        trasporto = httpx.ASGITransport(app=applicazione)
        async with httpx.AsyncClient(
            transport=trasporto,
            base_url="http://test",
        ) as client:
            risposta = await registra_utente(client)
            await client.post(
                "/v1/auth/password/forgot",
                json={"email": EMAIL_DI_PROVA},
            )
    finally:
        logger_radice.removeHandler(handler)

    assert risposta.status_code == 201
    assert (
        sum(
            "email_dev_inviata" in registrazione.getMessage()
            for registrazione in handler.registrazioni
        )
        == 2
    )
    assert all(
        EMAIL_DI_PROVA not in registrazione.getMessage()
        for registrazione in handler.registrazioni
    )


def test_scope_system_solo_nei_punti_previsti() -> None:
    file_con_ambito_sistema = {
        percorso.relative_to(RADICE_APP.parent).as_posix()
        for percorso in RADICE_APP.rglob("*.py")
        if any(
            PATTERN_AMBITO_SISTEMA.search(riga)
            for riga in percorso.read_text(encoding="utf-8").splitlines()
        )
    }

    assert file_con_ambito_sistema == FILE_CON_AMBITO_SISTEMA_AMMESSI
