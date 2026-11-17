from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.dominio.autenticazione import TokenNonValido, valida_access_token
from app.infrastruttura.database import transazione_con_contesto
from app.infrastruttura.errori import ErroreApi, corpo_problema
from app.infrastruttura.repository_autenticazione import trova_stato_utente

PREFISSO_BEARER = "bearer "
STATO_UTENTE_ATTIVO = "active"

DETTAGLIO_SESSIONE_NON_VALIDA = "La sessione non è valida. Effettua di nuovo l'accesso."


class MiddlewareAutenticazione(BaseHTTPMiddleware):
    """Valida il Bearer token e popola request.state.user_id quando è presente."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        intestazione = request.headers.get("authorization")
        if not intestazione:
            return await call_next(request)

        token = _estrai_token_bearer(intestazione)
        if token is None:
            return _risposta_non_autenticato(request)
        try:
            accesso = valida_access_token(token)
        except TokenNonValido:
            return _risposta_non_autenticato(request)

        async with transazione_con_contesto(
            request.app.state.motore,
            scope="tenant",
            user_id=str(accesso.user_id),
        ) as connessione:
            stato = await trova_stato_utente(connessione, accesso.user_id)

        if stato != STATO_UTENTE_ATTIVO:
            return _risposta_non_autenticato(request)

        request.state.user_id = accesso.user_id
        return await call_next(request)


def get_utente_autenticato(request: Request) -> uuid.UUID:
    """Restituisce l'utente autenticato o solleva un 401 RFC 7807."""
    utente_id = getattr(request.state, "user_id", None)
    if utente_id is None:
        raise ErroreApi(
            status=401,
            titolo="Autenticazione richiesta",
            dettaglio=DETTAGLIO_SESSIONE_NON_VALIDA,
        )
    return utente_id


async def connessione_tenant(request: Request) -> AsyncIterator[AsyncConnection]:
    utente_id = get_utente_autenticato(request)
    async with transazione_con_contesto(
        request.app.state.motore,
        scope="tenant",
        user_id=str(utente_id),
    ) as connessione:
        yield connessione


def _estrai_token_bearer(intestazione: str) -> str | None:
    if not intestazione.lower().startswith(PREFISSO_BEARER):
        return None
    token = intestazione[len(PREFISSO_BEARER) :].strip()
    return token or None


def _risposta_non_autenticato(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        media_type="application/problem+json",
        content=corpo_problema(
            status=401,
            titolo="Autenticazione richiesta",
            dettaglio=DETTAGLIO_SESSIONE_NON_VALIDA,
            instance=request.url.path,
        ),
    )
