"""Limite di frequenza delle richieste per IP e per utente autenticato.

Il backend predefinito è in memoria e basta a un singolo processo: quando
l'API sarà replicata, la stessa interfaccia accetterà un backend Redis senza
cambiare le regole applicate agli endpoint.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from math import ceil
from typing import Protocol

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.infrastruttura.configurazione import ConfigurazioneRateLimit
from app.infrastruttura.errori import corpo_problema

FINESTRA_PREDEFINITA_SECONDI = 60.0
AMBITO_IP = "ip"
AMBITO_UTENTE = "utente"
INTESTAZIONE_IP_REALE = "x-forwarded-for"
IP_SCONOSCIUTO = "sconosciuto"

DETTAGLIO_TROPPE_RICHIESTE = (
    "Hai effettuato troppe richieste in poco tempo. "
    "Attendi qualche secondo e riprova."
)


@dataclass(frozen=True, slots=True)
class RegolaRateLimit:
    metodo: str
    percorso: str
    ambito: str
    limite: int
    finestra_secondi: float = FINESTRA_PREDEFINITA_SECONDI


class ProtocolloLimitatore(Protocol):
    async def registra(
        self,
        chiave: str,
        *,
        limite: int,
        finestra_secondi: float,
    ) -> int:
        """Registra la richiesta e restituisce i secondi di attesa, zero se ammessa."""
        ...


class LimitatoreInMemoria:
    """Finestra scorrevole per processo, adatta allo sviluppo e ai test."""

    def __init__(self) -> None:
        self._finestre: dict[str, deque[float]] = {}

    async def registra(
        self,
        chiave: str,
        *,
        limite: int,
        finestra_secondi: float,
    ) -> int:
        adesso = time.monotonic()
        finestra = self._finestre.setdefault(chiave, deque())
        while finestra and adesso - finestra[0] >= finestra_secondi:
            finestra.popleft()
        if len(finestra) >= limite:
            # Il contatore riparte quando la richiesta più vecchia esce dalla
            # finestra: Retry-After indica esattamente quel momento.
            return max(1, ceil(finestra_secondi - (adesso - finestra[0])))
        finestra.append(adesso)
        return 0


def componi_regole(
    configurazione: ConfigurazioneRateLimit,
) -> tuple[RegolaRateLimit, ...]:
    """Restituisce le regole di frequenza applicate agli endpoint pubblici."""
    return (
        RegolaRateLimit(
            metodo="POST",
            percorso="/v1/auth/login",
            ambito=AMBITO_IP,
            limite=configurazione.login_per_minuto,
        ),
        RegolaRateLimit(
            metodo="POST",
            percorso="/v1/auth/register",
            ambito=AMBITO_IP,
            limite=configurazione.registrazione_per_minuto,
        ),
        RegolaRateLimit(
            metodo="POST",
            percorso="/v1/reports",
            ambito=AMBITO_UTENTE,
            limite=configurazione.segnalazioni_per_minuto,
        ),
        RegolaRateLimit(
            metodo="GET",
            percorso="/v1/geo/resolve",
            ambito=AMBITO_IP,
            limite=configurazione.geocoding_per_minuto,
        ),
    )


def crea_limitatore() -> ProtocolloLimitatore:
    """Restituisce il limitatore da collegare all'applicazione."""
    return LimitatoreInMemoria()


class MiddlewareRateLimit(BaseHTTPMiddleware):
    """Applica le regole di frequenza e risponde 429 con Retry-After."""

    def __init__(
        self,
        applicazione: ASGIApp,
        *,
        limitatore: ProtocolloLimitatore,
        regole: tuple[RegolaRateLimit, ...],
    ) -> None:
        super().__init__(applicazione)
        self._limitatore = limitatore
        self._regole = regole

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        regola = _regola_applicabile(self._regole, request)
        if regola is None:
            return await call_next(request)
        chiave = f"{regola.percorso}:{_identificativo_chiamante(request, regola)}"
        attesa = await self._limitatore.registra(
            chiave,
            limite=regola.limite,
            finestra_secondi=regola.finestra_secondi,
        )
        if attesa > 0:
            return _risposta_troppe_richieste(request, attesa)
        return await call_next(request)


def _regola_applicabile(
    regole: tuple[RegolaRateLimit, ...],
    request: Request,
) -> RegolaRateLimit | None:
    for regola in regole:
        if regola.metodo == request.method and regola.percorso == request.url.path:
            return regola
    return None


def _identificativo_chiamante(request: Request, regola: RegolaRateLimit) -> str:
    if regola.ambito == AMBITO_UTENTE:
        utente_id = getattr(request.state, "user_id", None)
        if utente_id is not None:
            return f"utente:{utente_id}"
    return f"ip:{_indirizzo_client(request)}"


def _indirizzo_client(request: Request) -> str:
    inoltro = request.headers.get(INTESTAZIONE_IP_REALE)
    if inoltro:
        return inoltro.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return IP_SCONOSCIUTO


def _risposta_troppe_richieste(request: Request, attesa: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        media_type="application/problem+json",
        headers={"Retry-After": str(attesa)},
        content=corpo_problema(
            status=429,
            titolo="Troppe richieste",
            dettaglio=DETTAGLIO_TROPPE_RICHIESTE,
            instance=request.url.path,
        ),
    )
