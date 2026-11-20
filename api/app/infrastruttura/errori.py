from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.dominio.autenticazione import ErroreRiusoToken

logger = logging.getLogger(__name__)

TIPO_PROBLEMA_PREDEFINITO = "about:blank"
DETTAGLIO_RIUSO_REFRESH = "La sessione non è più valida. Effettua di nuovo l'accesso."
DETTAGLIO_ERRORE_INTERNO = (
    "Il servizio non è riuscito a completare la richiesta. Riprova più tardi."
)

MESSAGGI_HTTP: dict[int, tuple[str, str]] = {
    HTTPStatus.NOT_FOUND: (
        "Risorsa non trovata",
        "La risorsa richiesta non esiste.",
    ),
    HTTPStatus.METHOD_NOT_ALLOWED: (
        "Metodo non consentito",
        "Il metodo HTTP usato non è previsto per questa risorsa.",
    ),
    HTTPStatus.CONFLICT: (
        "Conflitto",
        "La richiesta è in conflitto con lo stato attuale della risorsa.",
    ),
}

MESSAGGIO_HTTP_PREDEFINITO = (
    "Richiesta non valida",
    "La richiesta non può essere elaborata. Controlla i dati inviati.",
)


class ErroreApi(Exception):  # noqa: N818
    """Trasporta un errore utente da rendere in formato RFC 7807."""

    def __init__(
        self,
        *,
        status: int,
        titolo: str,
        dettaglio: str,
        tipo: str = TIPO_PROBLEMA_PREDEFINITO,
    ) -> None:
        self.status = status
        self.titolo = titolo
        self.dettaglio = dettaglio
        self.tipo = tipo
        super().__init__(dettaglio)


def corpo_problema(
    *,
    status: int,
    titolo: str,
    dettaglio: str,
    instance: str,
    tipo: str = TIPO_PROBLEMA_PREDEFINITO,
) -> dict[str, object]:
    """Restituisce il corpo RFC 7807 per la risposta di errore."""
    return {
        "type": tipo,
        "title": titolo,
        "status": status,
        "detail": dettaglio,
        "instance": instance,
    }


def registra_gestori_errori(applicazione: FastAPI) -> None:
    """Registra gli handler che rendono ogni errore utente in RFC 7807."""
    applicazione.add_exception_handler(ErroreApi, _gestisci_errore_api)
    applicazione.add_exception_handler(ErroreRiusoToken, _gestisci_riuso_refresh)
    applicazione.add_exception_handler(RequestValidationError, _gestisci_validazione)
    applicazione.add_exception_handler(StarletteHTTPException, _gestisci_errore_http)
    applicazione.add_exception_handler(Exception, _gestisci_errore_interno)


async def _gestisci_errore_api(request: Request, errore: ErroreApi) -> JSONResponse:
    return JSONResponse(
        status_code=errore.status,
        media_type="application/problem+json",
        content=corpo_problema(
            status=errore.status,
            titolo=errore.titolo,
            dettaglio=errore.dettaglio,
            instance=request.url.path,
            tipo=errore.tipo,
        ),
    )


async def _gestisci_riuso_refresh(
    request: Request,
    errore: ErroreRiusoToken,
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        media_type="application/problem+json",
        content=corpo_problema(
            status=401,
            titolo="Autenticazione richiesta",
            dettaglio=DETTAGLIO_RIUSO_REFRESH,
            instance=request.url.path,
        ),
    )


async def _gestisci_validazione(
    request: Request,
    errore: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        media_type="application/problem+json",
        content=corpo_problema(
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
            titolo="Dati non validi",
            dettaglio=(
                "I dati inviati non rispettano il formato richiesto. "
                "Controlla i campi e riprova."
            ),
            instance=request.url.path,
        ),
    )


async def _gestisci_errore_interno(
    request: Request,
    errore: Exception,
) -> JSONResponse:
    # Il dettaglio tecnico resta nei log, la risposta espone solo il problema.
    logger.error(
        "unhandled_request_error",
        extra={"error_type": type(errore).__name__, "path": request.url.path},
        exc_info=errore,
    )
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        media_type="application/problem+json",
        content=corpo_problema(
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            titolo="Errore interno",
            dettaglio=DETTAGLIO_ERRORE_INTERNO,
            instance=request.url.path,
        ),
    )


async def _gestisci_errore_http(
    request: Request,
    errore: StarletteHTTPException,
) -> JSONResponse:
    titolo, dettaglio = MESSAGGI_HTTP.get(
        errore.status_code,
        MESSAGGIO_HTTP_PREDEFINITO,
    )
    return JSONResponse(
        status_code=errore.status_code,
        media_type="application/problem+json",
        content=corpo_problema(
            status=errore.status_code,
            titolo=titolo,
            dettaglio=dettaglio,
            instance=request.url.path,
        ),
    )
