from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.dominio.dispatch import (
    CANALE_EMAIL,
    CANALE_NESSUNO,
    CANALE_OPEN311,
    CausaErroreTrasporto,
    Comune,
    ErroreTrasportoOpen311,
    EsitoDispatch,
    ModalitaDispatchSconosciuta,
    SegnalazioneDaInviare,
    ServizioComunale,
    calcola_next_attempt_at,
    classifica_errore_open311,
    componi_contenuto_email,
    seleziona_canale,
)

ISTANTE_DI_PROVA = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

CASI_SELEZIONE_CANALE = (
    ("open311", "SERVIZIO-1", True, CANALE_OPEN311),
    ("open311", None, True, CANALE_NESSUNO),
    ("open311_then_email", "SERVIZIO-1", True, CANALE_OPEN311),
    ("open311_then_email", None, True, CANALE_EMAIL),
    ("open311_then_email", None, False, CANALE_NESSUNO),
    ("email", None, True, CANALE_EMAIL),
    ("email", None, False, CANALE_NESSUNO),
    ("email", "SERVIZIO-1", False, CANALE_NESSUNO),
)

CASI_CLASSIFICAZIONE = (
    (429, EsitoDispatch.RITENTABILE),
    (500, EsitoDispatch.RITENTABILE),
    (503, EsitoDispatch.RITENTABILE),
    (400, EsitoDispatch.PERMANENTE),
    (422, EsitoDispatch.PERMANENTE),
    (401, EsitoDispatch.PERMANENTE),
    (403, EsitoDispatch.PERMANENTE),
    (404, EsitoDispatch.PERMANENTE),
    (201, EsitoDispatch.AMBIGUO),
    (204, EsitoDispatch.AMBIGUO),
)


def _comune(dispatch_mode: str) -> Comune:
    return Comune(
        id=uuid.uuid4(),
        nome="Comune di prova",
        dispatch_mode=dispatch_mode,
        open311_endpoint_url="https://api.comune.test/v2/requests",
        open311_jurisdiction_id="comune-test",
        open311_api_key_ref=None,
    )


def _servizio(
    codice_open311: str | None,
    *,
    con_fallback_email: bool,
) -> ServizioComunale:
    return ServizioComunale(
        open311_service_code=codice_open311,
        open311_extra_fields=None,
        fallback_email_enc=b"cifrato" if con_fallback_email else None,
        fallback_active=con_fallback_email,
    )


@pytest.mark.parametrize(
    ("dispatch_mode", "codice_open311", "con_fallback_email", "canale_atteso"),
    CASI_SELEZIONE_CANALE,
)
def test_seleziona_canale(
    dispatch_mode: str,
    codice_open311: str | None,
    con_fallback_email: bool,
    canale_atteso: str,
) -> None:
    canale = seleziona_canale(
        _comune(dispatch_mode),
        _servizio(codice_open311, con_fallback_email=con_fallback_email),
    )

    assert canale == canale_atteso


@pytest.mark.parametrize("dispatch_mode", ("open311", "email", "open311_then_email"))
def test_seleziona_canale_senza_servizio(dispatch_mode: str) -> None:
    assert seleziona_canale(_comune(dispatch_mode), None) == CANALE_NESSUNO


def test_seleziona_canale_modalita_sconosciuta() -> None:
    with pytest.raises(ModalitaDispatchSconosciuta):
        seleziona_canale(_comune("canale-futuro"), None)


@pytest.mark.parametrize(("http_status", "esito_atteso"), CASI_CLASSIFICAZIONE)
def test_classifica_errore_open311(
    http_status: int,
    esito_atteso: EsitoDispatch,
) -> None:
    assert classifica_errore_open311(http_status, None) is esito_atteso


@pytest.mark.parametrize(
    "causa",
    (
        CausaErroreTrasporto.TIMEOUT,
        CausaErroreTrasporto.DNS,
        CausaErroreTrasporto.CONNESSIONE,
    ),
)
def test_classifica_errore_open311_errore_di_rete(
    causa: CausaErroreTrasporto,
) -> None:
    esito = classifica_errore_open311(
        None,
        ErroreTrasportoOpen311(causa, "errore simulato"),
    )

    assert esito is EsitoDispatch.RITENTABILE


def test_classifica_errore_open311_eccezione_non_prevista() -> None:
    esito = classifica_errore_open311(None, ValueError("errore inatteso"))

    assert esito is EsitoDispatch.PERMANENTE


def test_calcola_next_attempt_at_rispetta_la_sequenza_di_backoff() -> None:
    attese = [
        calcola_next_attempt_at(numero, ISTANTE_DI_PROVA) - ISTANTE_DI_PROVA
        for numero in range(1, 5)
    ]

    assert attese == [
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(minutes=60),
    ]
    assert calcola_next_attempt_at(5, ISTANTE_DI_PROVA) is None


def test_componi_contenuto_email_contiene_link_e_coordinate() -> None:
    segnalazione = SegnalazioneDaInviare(
        id=uuid.uuid4(),
        public_ref="CR-2026-000123",
        municipality_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        titolo="Lampione spento",
        descrizione="Il lampione davanti al civico 4 non si accende.",
        latitudine=45.05,
        longitudine=9.05,
        address_label="Via Roma 4",
        dispatch_state="pending",
    )

    contenuto = componi_contenuto_email(
        segnalazione,
        "Illuminazione",
        "https://segnalazioni.test/reports/CR-2026-000123",
    )

    assert "CR-2026-000123" in contenuto.oggetto
    assert "Illuminazione" in contenuto.corpo
    assert "Il lampione davanti al civico 4" in contenuto.corpo
    assert "https://segnalazioni.test/reports/CR-2026-000123" in contenuto.corpo
    assert "45.050000, 9.050000" in contenuto.corpo
