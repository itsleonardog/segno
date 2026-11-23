from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

CANALE_OPEN311 = "open311"
CANALE_EMAIL = "email"
CANALE_NESSUNO = "nessuno"

MODALITA_OPEN311 = "open311"
MODALITA_EMAIL = "email"
MODALITA_OPEN311_POI_EMAIL = "open311_then_email"

EVENTO_SEGNALAZIONE_CREATA = "report.created"
EVENTO_DISPATCH_RITENTATIVO = "report.dispatch_retry"

STATO_INVIATA_OPEN311 = "sent_open311"
STATO_INVIATA_EMAIL = "sent_email"
STATO_FALLITA = "failed"
STATO_PENDENTE = "pending"

# 1, 5, 15, 60 minuti: quattro attese prima del fallback email definitivo.
ATTESE_RITENTATIVO_MINUTI: tuple[int, ...] = (1, 5, 15, 60)

TESTO_DESTINATARIO_PREDEFINITO = "it"


class EsitoDispatch(StrEnum):
    """Le categorie di esito di una chiamata verso un servizio esterno."""

    RITENTABILE = "ritentabile"
    PERMANENTE = "permanente"
    AMBIGUO = "ambiguo"


class CausaErroreTrasporto(StrEnum):
    """Le cause di rete che rendono un tentativo Open311 ritentabile."""

    TIMEOUT = "timeout"
    DNS = "dns"
    CONNESSIONE = "connessione"


class ErroreTrasportoOpen311(Exception):  # noqa: N818
    """Trasporta un errore di rete dell'adapter con la causa già classificata."""

    def __init__(self, causa: CausaErroreTrasporto, dettaglio: str) -> None:
        self.causa = causa
        super().__init__(dettaglio)


class ErroreInvioEmailSegnalazione(Exception):  # noqa: N818
    """Segnala che il provider email non ha consegnato la segnalazione."""


class ModalitaDispatchSconosciuta(ValueError):  # noqa: N818
    """Segnala un dispatch_mode non previsto dal modello dati."""


class SegnalazioneNonTrovata(Exception):  # noqa: N818
    """Segnala un evento outbox che punta a una segnalazione inesistente."""


@dataclass(frozen=True, slots=True)
class Comune:
    id: uuid.UUID
    nome: str
    dispatch_mode: str
    open311_endpoint_url: str | None
    open311_jurisdiction_id: str | None
    open311_api_key_ref: str | None
    locale: str = TESTO_DESTINATARIO_PREDEFINITO


@dataclass(frozen=True, slots=True)
class ServizioComunale:
    open311_service_code: str | None
    open311_extra_fields: Mapping[str, object] | None
    fallback_email_enc: bytes | None
    fallback_active: bool

    @property
    def ha_fallback_email(self) -> bool:
        return self.fallback_active and self.fallback_email_enc is not None


@dataclass(frozen=True, slots=True)
class SegnalazioneDaInviare:
    id: uuid.UUID
    public_ref: str
    municipality_id: uuid.UUID | None
    category_id: uuid.UUID
    titolo: str
    descrizione: str
    latitudine: float
    longitudine: float
    address_label: str | None
    dispatch_state: str


@dataclass(frozen=True, slots=True)
class RisultatoOpen311:
    service_request_id: str | None
    status_code: int | None
    errore: Exception | None

    @property
    def is_riuscito(self) -> bool:
        return self.service_request_id is not None


@dataclass(frozen=True, slots=True)
class ContenutoEmail:
    oggetto: str
    corpo: str


@dataclass(frozen=True, slots=True)
class VoceConfigurazioneDispatch:
    comune: Comune
    servizio: ServizioComunale | None


@dataclass(frozen=True, slots=True)
class EsitoElaborazione:
    stato_dispatch: str
    richiede_ritentativo: bool = False
    messaggio_errore: str | None = None


class AdattatoreOpen311(Protocol):
    async def invia_segnalazione(
        self,
        endpoint_url: str,
        api_key: str | None,
        payload: Mapping[str, str],
    ) -> RisultatoOpen311:
        """Invia il payload form-encoded e restituisce l'esito normalizzato."""
        ...

    async def recupera_stato_richiesta(
        self,
        endpoint_url: str,
        api_key: str | None,
        service_request_id: str,
    ) -> str | None:
        """Restituisce lo stato esterno della richiesta o None se non leggibile."""
        ...


class InvioEmailSegnalazione(Protocol):
    def invia_segnalazione(
        self,
        destinatario: str,
        contenuto: ContenutoEmail,
    ) -> str:
        """Consegna il messaggio e restituisce il Message-ID del provider."""
        ...


class CifrarioEmailDispatch(Protocol):
    @property
    def key_id_corrente(self) -> str: ...

    def decifra(self, ciphertext: bytes, key_id: str) -> str:
        """Restituisce l'indirizzo in chiaro o solleva un errore di decifratura."""
        ...


class RisolutoreChiaviOpen311(Protocol):
    def chiave_per_riferimento(self, riferimento: str | None) -> str | None:
        """Restituisce la chiave API associata al riferimento, se configurata."""
        ...


class CacheConfigurazioneDispatch(Protocol):
    def leggi(
        self,
        municipality_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> VoceConfigurazioneDispatch | None: ...

    def scrivi(
        self,
        municipality_id: uuid.UUID,
        category_id: uuid.UUID,
        voce: VoceConfigurazioneDispatch,
    ) -> None: ...

    def invalida_comune(self, municipality_id: uuid.UUID) -> None: ...


def seleziona_canale(comune: Comune, servizio: ServizioComunale | None) -> str:
    """Restituisce il canale di dispatch iniziale per il comune e il servizio."""
    if comune.dispatch_mode == MODALITA_OPEN311:
        if servizio is not None and servizio.open311_service_code:
            return CANALE_OPEN311
        return CANALE_NESSUNO
    if comune.dispatch_mode == MODALITA_OPEN311_POI_EMAIL:
        if servizio is not None and servizio.open311_service_code:
            return CANALE_OPEN311
        if servizio is not None and servizio.ha_fallback_email:
            return CANALE_EMAIL
        return CANALE_NESSUNO
    if comune.dispatch_mode == MODALITA_EMAIL:
        if servizio is not None and servizio.ha_fallback_email:
            return CANALE_EMAIL
        return CANALE_NESSUNO
    raise ModalitaDispatchSconosciuta(
        f"Modalità di dispatch non gestita: {comune.dispatch_mode}."
    )


def is_fallback_email_previsto(
    comune: Comune,
    servizio: ServizioComunale | None,
) -> bool:
    """Indica se un errore Open311 può proseguire con l'email al comune."""
    return (
        comune.dispatch_mode in (MODALITA_OPEN311_POI_EMAIL, MODALITA_EMAIL)
        and servizio is not None
        and servizio.ha_fallback_email
    )


def classifica_errore_open311(
    http_status: int | None,
    exception: Exception | None,
) -> EsitoDispatch:
    """Classifica un tentativo Open311 fallito in ritentabile, permanente o ambiguo."""
    if exception is not None:
        if isinstance(exception, ErroreTrasportoOpen311):
            return EsitoDispatch.RITENTABILE
        return EsitoDispatch.PERMANENTE
    if http_status is None:
        return EsitoDispatch.AMBIGUO
    if 200 <= http_status < 300:
        # Un 2xx senza service_request_id è un falso successo: fallback email.
        return EsitoDispatch.AMBIGUO
    if http_status == 429 or 500 <= http_status < 600:
        return EsitoDispatch.RITENTABILE
    if 400 <= http_status < 500:
        # 400/422 payload errato, 401/403 configurazione errata: non ritentabili.
        return EsitoDispatch.PERMANENTE
    return EsitoDispatch.RITENTABILE


def calcola_next_attempt_at(
    numero_tentativo: int,
    istante: datetime,
) -> datetime | None:
    """Restituisce il prossimo tentativo con backoff, o None a finestra esaurita."""
    if numero_tentativo < 1 or numero_tentativo > len(ATTESE_RITENTATIVO_MINUTI):
        return None
    attesa = ATTESE_RITENTATIVO_MINUTI[numero_tentativo - 1]
    return istante + timedelta(minutes=attesa)


def componi_payload_open311(
    segnalazione: SegnalazioneDaInviare,
    comune: Comune,
    servizio: ServizioComunale,
) -> dict[str, str]:
    """Restituisce i campi GeoReport v2, senza dati personali dell'autore."""
    payload = {
        "service_code": servizio.open311_service_code or "",
        "description": f"{segnalazione.titolo}\n\n{segnalazione.descrizione}",
        "lat": f"{segnalazione.latitudine:.6f}",
        "long": f"{segnalazione.longitudine:.6f}",
        "external_reference": segnalazione.public_ref,
    }
    if segnalazione.address_label:
        payload["address_string"] = segnalazione.address_label
    if comune.open311_jurisdiction_id:
        payload["jurisdiction_id"] = comune.open311_jurisdiction_id
    for nome_campo, valore in (servizio.open311_extra_fields or {}).items():
        payload[nome_campo] = str(valore)
    return payload


def componi_contenuto_email(
    segnalazione: SegnalazioneDaInviare,
    nome_categoria: str,
    url_pubblico: str,
) -> ContenutoEmail:
    """Restituisce oggetto e corpo dell'email di segnalazione al comune."""
    oggetto = f"[{segnalazione.public_ref}] {nome_categoria}"
    corpo = "\n".join(
        (
            f"Riferimento pubblico: {segnalazione.public_ref}",
            f"Categoria: {nome_categoria}",
            f"Descrizione: {segnalazione.descrizione}",
            f"Posizione: {segnalazione.latitudine:.6f}, "
            f"{segnalazione.longitudine:.6f}",
            f"Pagina pubblica: {url_pubblico}",
        )
    )
    return ContenutoEmail(oggetto=oggetto, corpo=corpo)


def componi_url_pubblica(url_pubblica_base: str, public_ref: str) -> str:
    """Restituisce il link permanente alla pagina pubblica della segnalazione."""
    return f"{url_pubblica_base.rstrip('/')}/reports/{public_ref}"
