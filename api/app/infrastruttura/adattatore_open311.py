from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import httpx

from app.dominio.dispatch import (
    CausaErroreTrasporto,
    ErroreTrasportoOpen311,
    RisultatoOpen311,
)
from app.infrastruttura.configurazione import (
    PREFISSO_SEGRETO_OPEN311_PREDEFINITO,
)

logger = logging.getLogger(__name__)

TIMEOUT_CONNESSIONE_SECONDI = 3.0
TIMEOUT_LETTURA_SECONDI = 10.0

INDICATORI_ERRORE_DNS = (
    "name or service not known",
    "nodename nor servname",
    "temporary failure in name resolution",
    "getaddrinfo failed",
)

MESSAGGI_CAUSA = {
    CausaErroreTrasporto.TIMEOUT: "Open311 request timed out.",
    CausaErroreTrasporto.DNS: "Open311 host name could not be resolved.",
    CausaErroreTrasporto.CONNESSIONE: "Open311 connection failed.",
}


class AdattatoreOpen311:
    """Adapter GeoReport v2 con timeout aggressivi e log senza segreti."""

    def __init__(
        self,
        *,
        trasporto: httpx.AsyncBaseTransport | None = None,
        timeout_connessione: float = TIMEOUT_CONNESSIONE_SECONDI,
        timeout_lettura: float = TIMEOUT_LETTURA_SECONDI,
    ) -> None:
        self._trasporto = trasporto
        self._timeout_connessione = timeout_connessione
        self._timeout_lettura = timeout_lettura

    async def invia_segnalazione(
        self,
        endpoint_url: str,
        api_key: str | None,
        payload: Mapping[str, str],
    ) -> RisultatoOpen311:
        url_richiesta, chiave_effettiva = _separa_api_key_dalla_query(
            endpoint_url,
            api_key,
        )
        campi = dict(payload)
        if chiave_effettiva:
            # La chiave viaggia nel corpo form-encoded, mai nella query string.
            campi["api_key"] = chiave_effettiva
        descrittore_endpoint = _descrittore_endpoint(endpoint_url)
        timeout = httpx.Timeout(
            self._timeout_lettura,
            connect=self._timeout_connessione,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self._trasporto,
            ) as client:
                risposta = await client.post(url_richiesta, data=campi)
        except httpx.HTTPError as errore:
            return _risultato_errore_trasporto(errore, descrittore_endpoint)
        logger.info(
            "open311_response_received",
            extra={**descrittore_endpoint, "status_code": risposta.status_code},
        )
        return RisultatoOpen311(
            service_request_id=_estrai_service_request_id(risposta),
            status_code=risposta.status_code,
            errore=None,
        )

    async def recupera_stato_richiesta(
        self,
        endpoint_url: str,
        api_key: str | None,
        service_request_id: str,
    ) -> str | None:
        """Restituisce lo stato esterno della richiesta o None se non leggibile."""
        url_richiesta = (
            f"{endpoint_url.rstrip('/')}/{quote(service_request_id, safe='')}"
        )
        parametri = {"api_key": api_key} if api_key else None
        descrittore_endpoint = _descrittore_endpoint(endpoint_url)
        timeout = httpx.Timeout(
            self._timeout_lettura,
            connect=self._timeout_connessione,
        )
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self._trasporto,
            ) as client:
                risposta = await client.get(url_richiesta, params=parametri)
        except httpx.HTTPError as errore:
            logger.warning(
                "open311_status_transport_error",
                extra={
                    **descrittore_endpoint,
                    "error_type": type(errore).__name__,
                },
            )
            return None
        if not 200 <= risposta.status_code < 300:
            logger.warning(
                "open311_status_response_not_ok",
                extra={
                    **descrittore_endpoint,
                    "status_code": risposta.status_code,
                },
            )
            return None
        return _estrai_stato_richiesta(risposta)


class SegretiOpen311DaAmbiente:
    """Risolve le API key dal secret store d'ambiente, non dal database."""

    def __init__(
        self,
        prefisso: str = PREFISSO_SEGRETO_OPEN311_PREDEFINITO,
    ) -> None:
        self._prefisso = prefisso

    def chiave_per_riferimento(self, riferimento: str | None) -> str | None:
        if not riferimento:
            return None
        return os.environ.get(f"{self._prefisso}{riferimento.upper()}")


def _risultato_errore_trasporto(
    errore: httpx.HTTPError,
    descrittore_endpoint: dict[str, str],
) -> RisultatoOpen311:
    causa = _classifica_causa_trasporto(errore)
    livello = (
        logging.WARNING
        if causa is not CausaErroreTrasporto.CONNESSIONE
        else logging.ERROR
    )
    logger.log(
        livello,
        "open311_transport_error",
        extra={
            **descrittore_endpoint,
            "causa": causa.value,
            "tipo_errore": type(errore).__name__,
        },
    )
    return RisultatoOpen311(
        service_request_id=None,
        status_code=None,
        errore=ErroreTrasportoOpen311(causa, MESSAGGI_CAUSA[causa]),
    )


def _classifica_causa_trasporto(errore: httpx.HTTPError) -> CausaErroreTrasporto:
    if isinstance(errore, httpx.TimeoutException):
        return CausaErroreTrasporto.TIMEOUT
    if isinstance(errore, httpx.ConnectError):
        messaggio = str(errore).lower()
        if any(indicatore in messaggio for indicatore in INDICATORI_ERRORE_DNS):
            return CausaErroreTrasporto.DNS
        return CausaErroreTrasporto.CONNESSIONE
    return CausaErroreTrasporto.CONNESSIONE


def _estrai_stato_richiesta(risposta: httpx.Response) -> str | None:
    try:
        contenuto = risposta.json()
    except ValueError:
        logger.error(
            "open311_status_response_not_json",
            extra={"status_code": risposta.status_code},
        )
        return None
    if isinstance(contenuto, list):
        return _stato_da_elenco(contenuto)
    if isinstance(contenuto, dict):
        return _stato_valido(contenuto.get("status"))
    return None


def _stato_da_elenco(contenuto: list[object]) -> str | None:
    if not contenuto or not isinstance(contenuto[0], dict):
        return None
    return _stato_valido(contenuto[0].get("status"))


def _stato_valido(valore: object) -> str | None:
    if isinstance(valore, str) and valore.strip():
        return valore.strip()
    return None


def _estrai_service_request_id(risposta: httpx.Response) -> str | None:
    try:
        contenuto = risposta.json()
    except ValueError:
        # Una risposta non JSON non prova l'avvenuta creazione: esito ambiguo.
        logger.error(
            "open311_response_not_json",
            extra={"status_code": risposta.status_code},
        )
        return None
    if isinstance(contenuto, list):
        return _estrai_da_elenco(contenuto)
    if isinstance(contenuto, dict):
        return _identificativo_valido(contenuto.get("service_request_id"))
    return None


def _estrai_da_elenco(contenuto: list[object]) -> str | None:
    if not contenuto or not isinstance(contenuto[0], dict):
        return None
    return _identificativo_valido(contenuto[0].get("service_request_id"))


def _identificativo_valido(valore: object) -> str | None:
    if isinstance(valore, str) and valore.strip():
        return valore.strip()
    return None


def _separa_api_key_dalla_query(
    endpoint_url: str,
    api_key: str | None,
) -> tuple[str, str | None]:
    # Se il comune ha configurato la chiave nella query, la si sposta nel form:
    # httpx logga l'URL completo e la chiave non deve comparire nei log.
    parti = urlsplit(endpoint_url)
    if not parti.query:
        return endpoint_url, api_key
    parametri = parse_qsl(parti.query, keep_blank_values=True)
    chiave_in_query: str | None = None
    parametri_sicuri: list[tuple[str, str]] = []
    for nome, valore in parametri:
        if nome == "api_key":
            chiave_in_query = valore
        else:
            parametri_sicuri.append((nome, valore))
    if chiave_in_query is None:
        return endpoint_url, api_key
    url_pulita = urlunsplit(parti._replace(query=urlencode(parametri_sicuri)))
    return url_pulita, api_key or chiave_in_query


def _descrittore_endpoint(endpoint_url: str) -> dict[str, str]:
    # Solo host e path: la query string può contenere la chiave API del comune.
    parti = urlsplit(endpoint_url)
    return {"host": parti.hostname or "", "path": parti.path}
