"""Pulizia periodica dei dati oltre il periodo di conservazione."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MESI_CONSERVAZIONE_NOTIFICHE_LETTE = 12
MESI_CONSERVAZIONE_DISPATCH = 24
MESI_CONSERVAZIONE_AUDIT_LOG = 24


@dataclass(frozen=True, slots=True)
class EsitoRetention:
    refresh_token_rimossi: int
    token_verifica_rimossi: int
    token_reset_rimossi: int
    notifiche_rimosse: int
    idempotenze_rimosse: int
    dispatch_rimossi: int
    audit_log_rimossi: int


async def pulisci_dati_scaduti(connessione: AsyncConnection) -> EsitoRetention:
    """Elimina i dati scaduti e restituisce quante righe sono state rimosse."""
    refresh_token = await connessione.execute(
        text("DELETE FROM refresh_token WHERE expires_at < now()")
    )
    token_verifica = await connessione.execute(
        text("DELETE FROM email_verification_token WHERE expires_at < now()")
    )
    token_reset = await connessione.execute(
        text("DELETE FROM password_reset_token WHERE expires_at < now()")
    )
    limite_notifiche = f"now() - interval '{MESI_CONSERVAZIONE_NOTIFICHE_LETTE} months'"
    notifiche = await connessione.execute(text(f"""
            DELETE FROM notification
            WHERE read_at IS NOT NULL
              AND read_at < {limite_notifiche}
            """))
    idempotenze = await connessione.execute(
        text("DELETE FROM idempotency_record WHERE expires_at < now()")
    )
    limite_dispatch = f"now() - interval '{MESI_CONSERVAZIONE_DISPATCH} months'"
    dispatch = await connessione.execute(
        text(f"DELETE FROM report_dispatch WHERE created_at < {limite_dispatch}")
    )
    limite_audit_log = f"now() - interval '{MESI_CONSERVAZIONE_AUDIT_LOG} months'"
    audit_log = await connessione.execute(
        text(f"DELETE FROM audit_log WHERE created_at < {limite_audit_log}")
    )
    return EsitoRetention(
        refresh_token_rimossi=refresh_token.rowcount,
        token_verifica_rimossi=token_verifica.rowcount,
        token_reset_rimossi=token_reset.rowcount,
        notifiche_rimosse=notifiche.rowcount,
        idempotenze_rimosse=idempotenze.rowcount,
        dispatch_rimossi=dispatch.rowcount,
        audit_log_rimossi=audit_log.rowcount,
    )
