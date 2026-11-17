from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncConnection

from app.dominio.dispatch import (
    CANALE_EMAIL,
    CANALE_NESSUNO,
    CANALE_OPEN311,
    STATO_FALLITA,
    STATO_INVIATA_EMAIL,
    STATO_INVIATA_OPEN311,
    AdattatoreOpen311,
    CacheConfigurazioneDispatch,
    CifrarioEmailDispatch,
    Comune,
    ErroreInvioEmailSegnalazione,
    EsitoDispatch,
    EsitoElaborazione,
    InvioEmailSegnalazione,
    RisolutoreChiaviOpen311,
    SegnalazioneDaInviare,
    SegnalazioneNonTrovata,
    ServizioComunale,
    VoceConfigurazioneDispatch,
    calcola_next_attempt_at,
    classifica_errore_open311,
    componi_contenuto_email,
    componi_payload_open311,
    componi_url_pubblica,
    is_fallback_email_previsto,
    seleziona_canale,
)
from app.infrastruttura import repository_dispatch
from app.infrastruttura.cache_dispatch import cache_configurazione_dispatch

logger = logging.getLogger(__name__)

LIMITE_DETTAGLIO_ERRORE = 500
STATO_TENTATIVO_RIUSCITO = "succeeded"
STATO_TENTATIVO_RITENTABILE = "failed_retryable"
STATO_TENTATIVO_PERMANENTE = "failed_permanent"
MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE = "Invio email al comune non riuscito."
MESSAGGIO_CANALE_ASSENTE = "Nessun canale di dispatch configurato per il comune."
MESSAGGIO_ENDPOINT_ASSENTE = "Endpoint Open311 assente nella configurazione del comune."
MESSAGGIO_FALLBACK_ASSENTE = "Fallback email non configurato per il comune."


class ElaboratoreEventi:
    """Instrada una segnalazione al comune applicando retry e fallback email."""

    def __init__(
        self,
        *,
        adattatore_open311: AdattatoreOpen311,
        invio_email: InvioEmailSegnalazione,
        cifrario_email: CifrarioEmailDispatch,
        risolutore_chiavi: RisolutoreChiaviOpen311,
        url_pubblica_base: str,
        cache_configurazione: CacheConfigurazioneDispatch | None = None,
        orologio: Callable[[], datetime] | None = None,
    ) -> None:
        self._adattatore_open311 = adattatore_open311
        self._invio_email = invio_email
        self._cifrario_email = cifrario_email
        self._risolutore_chiavi = risolutore_chiavi
        self._url_pubblica_base = url_pubblica_base
        self._cache = cache_configurazione or cache_configurazione_dispatch
        self._orologio = orologio or _istante_corrente

    async def elabora_evento_creazione_segnalazione(
        self,
        connessione: AsyncConnection,
        report_id: uuid.UUID,
    ) -> EsitoElaborazione:
        """Elabora l'evento di creazione applicando la regola di dispatch."""
        segnalazione = await repository_dispatch.carica_segnalazione(
            connessione,
            report_id,
        )
        if segnalazione is None:
            raise SegnalazioneNonTrovata(f"Segnalazione {report_id} inesistente.")
        if segnalazione.municipality_id is None:
            logger.info(
                "dispatch_skipped_no_municipality",
                extra={"report_id": str(report_id)},
            )
            return EsitoElaborazione(stato_dispatch=segnalazione.dispatch_state)
        comune, servizio = await self._carica_configurazione(
            connessione,
            segnalazione,
        )
        if comune is None:
            logger.error(
                "dispatch_municipality_missing",
                extra={
                    "report_id": str(report_id),
                    "municipality_id": str(segnalazione.municipality_id),
                },
            )
            await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
                connessione,
                report_id=report_id,
                stato=STATO_FALLITA,
            )
            return EsitoElaborazione(
                stato_dispatch=STATO_FALLITA,
                messaggio_errore="Comune non disponibile o non attivo.",
            )
        canale = seleziona_canale(comune, servizio)
        if canale == CANALE_NESSUNO:
            return await self._registra_canale_assente(
                connessione,
                comune,
                segnalazione,
            )
        if canale == CANALE_OPEN311:
            return await self._invia_a_open311(
                connessione,
                segnalazione,
                comune,
                servizio,
            )
        return await self._invia_email(connessione, segnalazione, comune, servizio)

    async def _carica_configurazione(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
    ) -> tuple[Comune | None, ServizioComunale | None]:
        municipality_id = segnalazione.municipality_id
        if municipality_id is None:
            return None, None
        voce = self._cache.leggi(municipality_id, segnalazione.category_id)
        if voce is not None:
            return voce.comune, voce.servizio
        comune = await repository_dispatch.carica_comune(connessione, municipality_id)
        if comune is None:
            return None, None
        servizio = await repository_dispatch.carica_servizio(
            connessione,
            municipality_id=municipality_id,
            category_id=segnalazione.category_id,
        )
        self._cache.scrivi(
            municipality_id,
            segnalazione.category_id,
            VoceConfigurazioneDispatch(comune=comune, servizio=servizio),
        )
        return comune, servizio

    async def _registra_canale_assente(
        self,
        connessione: AsyncConnection,
        comune: Comune,
        segnalazione: SegnalazioneDaInviare,
    ) -> EsitoElaborazione:
        await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
            connessione,
            report_id=segnalazione.id,
            stato=STATO_FALLITA,
        )
        self._cache.invalida_comune(comune.id)
        logger.warning(
            "dispatch_no_channel_configured",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
            },
        )
        return EsitoElaborazione(
            stato_dispatch=STATO_FALLITA,
            messaggio_errore=MESSAGGIO_CANALE_ASSENTE,
        )

    async def _invia_a_open311(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        servizio: ServizioComunale | None,
    ) -> EsitoElaborazione:
        if not comune.open311_endpoint_url or servizio is None:
            return await self._fallback_o_fallimento(
                connessione,
                segnalazione,
                comune,
                servizio,
                MESSAGGIO_ENDPOINT_ASSENTE,
            )
        numero_tentativo = (
            await repository_dispatch.conta_tentativi_dispatch(
                connessione,
                report_id=segnalazione.id,
                canale=CANALE_OPEN311,
            )
            + 1
        )
        api_key = self._risolutore_chiavi.chiave_per_riferimento(
            comune.open311_api_key_ref
        )
        risultato = await self._adattatore_open311.invia_segnalazione(
            comune.open311_endpoint_url,
            api_key,
            componi_payload_open311(segnalazione, comune, servizio),
        )
        istante = self._orologio()
        if risultato.is_riuscito:
            return await self._registra_successo_open311(
                connessione,
                segnalazione,
                comune,
                numero_tentativo,
                risultato.status_code,
                risultato.service_request_id or "",
                istante,
            )
        esito = classifica_errore_open311(risultato.status_code, risultato.errore)
        dettaglio = _dettaglio_errore_open311(risultato.status_code, risultato.errore)
        if esito is EsitoDispatch.RITENTABILE:
            ritorno = await self._pianifica_ritentativo(
                connessione,
                segnalazione,
                comune,
                numero_tentativo=numero_tentativo,
                http_status=risultato.status_code,
                dettaglio=dettaglio,
                istante=istante,
            )
            if ritorno is not None:
                return ritorno
        await repository_dispatch.registra_tentativo_dispatch(
            connessione,
            report_id=segnalazione.id,
            municipality_id=comune.id,
            canale=CANALE_OPEN311,
            numero_tentativo=numero_tentativo,
            stato=STATO_TENTATIVO_PERMANENTE,
            http_status=risultato.status_code,
            error_code=esito.value,
            error_detail_redacted=dettaglio,
        )
        logger.warning(
            "dispatch_open311_permanent_failure",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
                "esito": esito.value,
            },
        )
        return await self._fallback_o_fallimento(
            connessione,
            segnalazione,
            comune,
            servizio,
            dettaglio,
        )

    async def _registra_successo_open311(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        numero_tentativo: int,
        http_status: int | None,
        service_request_id: str,
        istante: datetime,
    ) -> EsitoElaborazione:
        await repository_dispatch.registra_tentativo_dispatch(
            connessione,
            report_id=segnalazione.id,
            municipality_id=comune.id,
            canale=CANALE_OPEN311,
            numero_tentativo=numero_tentativo,
            stato=STATO_TENTATIVO_RIUSCITO,
            http_status=http_status,
            provider_request_id=service_request_id,
            succeeded_at=istante,
        )
        await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
            connessione,
            report_id=segnalazione.id,
            stato=STATO_INVIATA_OPEN311,
        )
        self._cache.invalida_comune(comune.id)
        logger.info(
            "dispatch_open311_succeeded",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
                "attempt_no": numero_tentativo,
            },
        )
        return EsitoElaborazione(stato_dispatch=STATO_INVIATA_OPEN311)

    async def _pianifica_ritentativo(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        *,
        numero_tentativo: int,
        http_status: int | None,
        dettaglio: str,
        istante: datetime,
    ) -> EsitoElaborazione | None:
        prossimo_tentativo = calcola_next_attempt_at(numero_tentativo, istante)
        if prossimo_tentativo is None:
            return None
        await repository_dispatch.registra_tentativo_dispatch(
            connessione,
            report_id=segnalazione.id,
            municipality_id=comune.id,
            canale=CANALE_OPEN311,
            numero_tentativo=numero_tentativo,
            stato=STATO_TENTATIVO_RITENTABILE,
            http_status=http_status,
            error_code=EsitoDispatch.RITENTABILE.value,
            error_detail_redacted=dettaglio,
            next_attempt_at=prossimo_tentativo,
        )
        logger.warning(
            "dispatch_retry_scheduled",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
                "attempt_no": numero_tentativo,
                "next_attempt_at": prossimo_tentativo.isoformat(),
            },
        )
        return EsitoElaborazione(
            stato_dispatch=segnalazione.dispatch_state,
            richiede_ritentativo=True,
            messaggio_errore=dettaglio,
        )

    async def _fallback_o_fallimento(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        servizio: ServizioComunale | None,
        dettaglio: str,
    ) -> EsitoElaborazione:
        if is_fallback_email_previsto(comune, servizio):
            logger.warning(
                "dispatch_email_fallback_started",
                extra={
                    "report_id": str(segnalazione.id),
                    "municipality_id": str(comune.id),
                },
            )
            return await self._invia_email(
                connessione,
                segnalazione,
                comune,
                servizio,
            )
        await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
            connessione,
            report_id=segnalazione.id,
            stato=STATO_FALLITA,
        )
        self._cache.invalida_comune(comune.id)
        return EsitoElaborazione(
            stato_dispatch=STATO_FALLITA,
            messaggio_errore=dettaglio,
        )

    async def _invia_email(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        servizio: ServizioComunale | None,
    ) -> EsitoElaborazione:
        if servizio is None or servizio.fallback_email_enc is None:
            await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
                connessione,
                report_id=segnalazione.id,
                stato=STATO_FALLITA,
            )
            self._cache.invalida_comune(comune.id)
            return EsitoElaborazione(
                stato_dispatch=STATO_FALLITA,
                messaggio_errore=MESSAGGIO_FALLBACK_ASSENTE,
            )
        destinatario = self._cifrario_email.decifra(
            servizio.fallback_email_enc,
            self._cifrario_email.key_id_corrente,
        )
        nome_categoria = await repository_dispatch.carica_nome_categoria(
            connessione,
            segnalazione.category_id,
        )
        contenuto = componi_contenuto_email(
            segnalazione,
            nome_categoria,
            componi_url_pubblica(self._url_pubblica_base, segnalazione.public_ref),
        )
        numero_tentativo = (
            await repository_dispatch.conta_tentativi_dispatch(
                connessione,
                report_id=segnalazione.id,
                canale=CANALE_EMAIL,
            )
            + 1
        )
        istante = self._orologio()
        try:
            message_id = self._invio_email.invia_segnalazione(
                destinatario,
                contenuto,
            )
        except (ErroreInvioEmailSegnalazione, OSError) as errore:
            return await self._registra_email_fallita(
                connessione,
                segnalazione,
                comune,
                numero_tentativo,
                errore,
                istante,
            )
        await repository_dispatch.registra_tentativo_dispatch(
            connessione,
            report_id=segnalazione.id,
            municipality_id=comune.id,
            canale=CANALE_EMAIL,
            numero_tentativo=numero_tentativo,
            stato=STATO_TENTATIVO_RIUSCITO,
            provider_request_id=message_id,
            succeeded_at=istante,
        )
        await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
            connessione,
            report_id=segnalazione.id,
            stato=STATO_INVIATA_EMAIL,
        )
        self._cache.invalida_comune(comune.id)
        logger.info(
            "dispatch_email_succeeded",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
                "attempt_no": numero_tentativo,
            },
        )
        return EsitoElaborazione(stato_dispatch=STATO_INVIATA_EMAIL)

    async def _registra_email_fallita(
        self,
        connessione: AsyncConnection,
        segnalazione: SegnalazioneDaInviare,
        comune: Comune,
        numero_tentativo: int,
        errore: Exception,
        istante: datetime,
    ) -> EsitoElaborazione:
        prossimo_tentativo = calcola_next_attempt_at(numero_tentativo, istante)
        await repository_dispatch.registra_tentativo_dispatch(
            connessione,
            report_id=segnalazione.id,
            municipality_id=comune.id,
            canale=CANALE_EMAIL,
            numero_tentativo=numero_tentativo,
            stato=(
                STATO_TENTATIVO_RITENTABILE
                if prossimo_tentativo is not None
                else STATO_TENTATIVO_PERMANENTE
            ),
            error_code=type(errore).__name__,
            error_detail_redacted=MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE,
            next_attempt_at=prossimo_tentativo,
        )
        logger.warning(
            "dispatch_email_failed",
            extra={
                "report_id": str(segnalazione.id),
                "municipality_id": str(comune.id),
                "attempt_no": numero_tentativo,
                "ritentabile": prossimo_tentativo is not None,
            },
        )
        if prossimo_tentativo is not None:
            return EsitoElaborazione(
                stato_dispatch=segnalazione.dispatch_state,
                richiede_ritentativo=True,
                messaggio_errore=MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE,
            )
        await repository_dispatch.aggiorna_stato_dispatch_segnalazione(
            connessione,
            report_id=segnalazione.id,
            stato=STATO_FALLITA,
        )
        self._cache.invalida_comune(comune.id)
        return EsitoElaborazione(
            stato_dispatch=STATO_FALLITA,
            messaggio_errore=MESSAGGIO_PROVIDER_EMAIL_NON_DISPONIBILE,
        )


def _dettaglio_errore_open311(
    http_status: int | None,
    errore: Exception | None,
) -> str:
    if errore is not None:
        return str(errore)[:LIMITE_DETTAGLIO_ERRORE]
    if http_status is not None:
        return f"Risposta HTTP {http_status} senza service_request_id."
    return "Risposta Open311 senza esito riconoscibile."


def _istante_corrente() -> datetime:
    return datetime.now(UTC)
