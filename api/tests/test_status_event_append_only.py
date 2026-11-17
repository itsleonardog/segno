from __future__ import annotations

import pytest
from aiuto_tenant import (
    CONFINE_COMUNE_A,
    POSIZIONE_COMUNE_A,
    crea_comune,
    crea_evento_stato,
    crea_segnalazione,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastruttura.database import transazione_con_contesto


async def test_evento_stato_non_e_modificabile_ne_cancellabile(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
        segnalazione = await crea_segnalazione(
            connessione,
            municipality_id=comune,
            category_id=categoria_altro,
            public_ref="CR-2026-000101",
            posizione=POSIZIONE_COMUNE_A,
        )
        evento = await crea_evento_stato(
            connessione,
            report_id=segnalazione,
            municipality_id=comune,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune),
    ) as connessione:
        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE report_status_event
                        SET note_public = 'modifica non ammessa'
                        WHERE id = CAST(:id AS uuid)
                        """),
                    {"id": str(evento)},
                )

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        DELETE FROM report_status_event
                        WHERE id = CAST(:id AS uuid)
                        """),
                    {"id": str(evento)},
                )

        nuovo_evento = await crea_evento_stato(
            connessione,
            report_id=segnalazione,
            municipality_id=comune,
        )

        esito = await connessione.execute(
            text("""
                SELECT count(*) FROM report_status_event
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(nuovo_evento)},
        )
        assert esito.scalar_one() == 1
