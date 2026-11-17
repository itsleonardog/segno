from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

import httpx
from aiuto_tenant import (
    CONFINE_COMUNE_A,
    POSIZIONE_COMUNE_A,
    crea_comune,
    crea_segnalazione,
    crea_servizio,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.dispatch import ContenutoEmail, RisultatoOpen311
from app.dominio.elaboratore_eventi import ElaboratoreEventi
from app.infrastruttura.cache_dispatch import CacheConfigurazioneDispatch
from app.infrastruttura.cifratura_email import CifrarioEmailEnvelope
from app.infrastruttura.configurazione import (
    CHIAVE_CIFRATURA_PREDEFINITA,
    decodifica_segreto_base64,
)

URL_PUBBLICA_DI_PROVA = "https://segnalazioni.test"
CHIAVE_API_DI_PROVA = "chiave-open311-segreta"
EMAIL_FALLBACK_DI_PROVA = "protocollo@comune.test"
RIFERIMENTO_PUBBLICO_DI_PROVA = "CR-2026-000123"
ADATTATORE_NON_USATO = "https://api.comune.test/v2/requests"


@dataclass
class InvioEmailFinto:
    message_id: str = "<dispatch-test@segnalazioni.test>"
    messaggi: list[tuple[str, ContenutoEmail]] = field(default_factory=list)
    errore_da_sollevare: Exception | None = None

    def invia_segnalazione(
        self,
        destinatario: str,
        contenuto: ContenutoEmail,
    ) -> str:
        if self.errore_da_sollevare is not None:
            raise self.errore_da_sollevare
        self.messaggi.append((destinatario, contenuto))
        return self.message_id


@dataclass
class RisolutoreChiaviFinto:
    chiavi: dict[str, str] = field(default_factory=dict)

    def chiave_per_riferimento(self, riferimento: str | None) -> str | None:
        if not riferimento:
            return None
        return self.chiavi.get(riferimento)


@dataclass
class AdattatoreOpen311Finto:
    risultato: RisultatoOpen311
    chiamate: list[tuple[str, str | None, dict[str, str]]] = field(
        default_factory=list,
    )

    async def invia_segnalazione(
        self,
        endpoint_url: str,
        api_key: str | None,
        payload: Mapping[str, str],
    ) -> RisultatoOpen311:
        self.chiamate.append((endpoint_url, api_key, dict(payload)))
        return self.risultato


def cifrario_email_di_prova() -> CifrarioEmailEnvelope:
    return CifrarioEmailEnvelope(
        decodifica_segreto_base64(
            CHIAVE_CIFRATURA_PREDEFINITA,
            "CIVIC_EMAIL_KEK",
        )
    )


def cifra_email_fallback(email: str) -> bytes:
    ciphertext, _ = cifrario_email_di_prova().cifra(email)
    return ciphertext


def costruisci_elaboratore(
    *,
    adattatore,
    invio_email: InvioEmailFinto,
    risolutore_chiavi: RisolutoreChiaviFinto | None = None,
    cifrario: CifrarioEmailEnvelope | None = None,
    istante=None,
) -> ElaboratoreEventi:
    return ElaboratoreEventi(
        adattatore_open311=adattatore,
        invio_email=invio_email,
        cifrario_email=cifrario or cifrario_email_di_prova(),
        risolutore_chiavi=risolutore_chiavi or RisolutoreChiaviFinto(),
        url_pubblica_base=URL_PUBBLICA_DI_PROVA,
        cache_configurazione=CacheConfigurazioneDispatch(),
        orologio=istante,
    )


def trasporto_con_risposta(
    contenuto: object,
    status_code: int = 201,
) -> httpx.MockTransport:
    def gestore(richiesta: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=contenuto)

    return httpx.MockTransport(gestore)


def trasporto_che_fallisce(errore: httpx.HTTPError) -> httpx.MockTransport:
    def gestore(richiesta: httpx.Request) -> httpx.Response:
        raise errore

    return httpx.MockTransport(gestore)


async def crea_scenario_segnalazione(
    motore: AsyncEngine,
    *,
    category_id: str,
    dispatch_mode: str = "email",
    fallback_email: str | None = EMAIL_FALLBACK_DI_PROVA,
    fallback_active: bool = True,
    codice_open311: str | None = "STRADE-1",
    endpoint_open311: str = ADATTATORE_NON_USATO,
    api_key_ref: str | None = None,
    public_ref: str = RIFERIMENTO_PUBBLICO_DI_PROVA,
) -> tuple[uuid.UUID, uuid.UUID]:
    async with motore.begin() as connessione:
        comune = await crea_comune(
            connessione,
            confine=CONFINE_COMUNE_A,
            dispatch_mode=dispatch_mode,
            open311_endpoint_url=endpoint_open311,
            open311_api_key_ref=api_key_ref,
        )
        await crea_servizio(
            connessione,
            municipality_id=comune,
            category_id=category_id,
            codice_open311=codice_open311,
            fallback_email_enc=(
                cifra_email_fallback(fallback_email) if fallback_email else None
            ),
            fallback_active=fallback_active,
        )
        segnalazione = await crea_segnalazione(
            connessione,
            municipality_id=comune,
            category_id=category_id,
            public_ref=public_ref,
            posizione=POSIZIONE_COMUNE_A,
        )
    return comune, segnalazione


async def leggi_segnalazione(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> Mapping[str, object]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("SELECT * FROM report WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_id)},
        )
        return esito.mappings().one()


async def leggi_tentativi(
    motore: AsyncEngine,
    report_id: uuid.UUID,
) -> list[Mapping[str, object]]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT channel, attempt_no, status, provider_request_id,
                       http_status, error_code, next_attempt_at
                FROM report_dispatch
                WHERE report_id = CAST(:id AS uuid)
                ORDER BY created_at, channel
                """),
            {"id": str(report_id)},
        )
        return list(esito.mappings().all())


async def leggi_evento_outbox(
    motore: AsyncEngine,
    evento_id: uuid.UUID,
) -> Mapping[str, object]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(
            text("""
                SELECT processed_at, attempts, last_error
                FROM outbox_event
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(evento_id)},
        )
        return esito.mappings().one()
