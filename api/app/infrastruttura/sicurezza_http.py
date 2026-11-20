"""Intestazioni di sicurezza applicate a ogni risposta HTTP."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

INTESTAZIONI_SICUREZZA: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    # L'API non serve pagine né asset: il browser non deve caricare nulla.
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "no-referrer",
}


class MiddlewareIntestazioniSicurezza(BaseHTTPMiddleware):
    """Aggiunge le intestazioni di sicurezza, anche alle risposte di errore."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        risposta = await call_next(request)
        for nome, valore in INTESTAZIONI_SICUREZZA.items():
            risposta.headers.setdefault(nome, valore)
        return risposta
