from __future__ import annotations

from app.infrastruttura.cifratura_email import (
    CifrarioEmailEnvelope,
    EmailCipher,
)
from app.infrastruttura.configurazione import (
    decodifica_segreto_base64,
    leggi_configurazione_dispatch,
    leggi_configurazione_sicurezza,
)
from app.infrastruttura.email_sender import EmailSender, LoggingEmailSender

NOME_SEGRETO_KEK = "CIVIC_EMAIL_KEK"
NOME_SEGRETO_PEPPER = "CIVIC_EMAIL_LOOKUP_PEPPER"


def get_cifrario_email() -> EmailCipher:
    configurazione = leggi_configurazione_sicurezza()
    chiave = decodifica_segreto_base64(
        configurazione.chiave_cifratura_base64,
        NOME_SEGRETO_KEK,
    )
    return CifrarioEmailEnvelope(chiave)


def get_pepper_lookup_email() -> bytes:
    configurazione = leggi_configurazione_sicurezza()
    return decodifica_segreto_base64(
        configurazione.pepper_lookup_base64,
        NOME_SEGRETO_PEPPER,
    )


def get_email_sender() -> EmailSender:
    configurazione = leggi_configurazione_sicurezza()
    configurazione_dispatch = leggi_configurazione_dispatch()
    return LoggingEmailSender(
        ambiente=configurazione.ambiente,
        indirizzo_mittente=configurazione_dispatch.indirizzo_mittente,
    )
