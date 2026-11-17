from __future__ import annotations

import uuid

import pytest
from aiuto_tenant import (
    CONFINE_COMUNE_A,
    CONFINE_COMUNE_B,
    POSIZIONE_COMUNE_A,
    POSIZIONE_COMUNE_B,
    crea_comune,
    crea_dispatch,
    crea_evento_outbox,
    crea_evento_stato,
    crea_notifica,
    crea_preferenza_notifica,
    crea_refresh_token,
    crea_segnalazione,
    crea_servizio,
    crea_utente,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastruttura.database import transazione_con_contesto


async def _crea_due_comuni(
    motore: AsyncEngine,
) -> tuple[uuid.UUID, uuid.UUID]:
    async with motore.begin() as connessione:
        comune_a = await crea_comune(connessione, confine=CONFINE_COMUNE_A)
        comune_b = await crea_comune(connessione, confine=CONFINE_COMUNE_B)
    return comune_a, comune_b


async def _leggi_id(connessione, tabella: str) -> set[uuid.UUID]:
    esito = await connessione.execute(text(f'SELECT id FROM "{tabella}"'))
    return set(esito.scalars().all())


async def test_report_isola_tenant_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        report_a = await crea_segnalazione(
            connessione,
            municipality_id=comune_a,
            category_id=categoria_altro,
            public_ref="CR-2026-000001",
            posizione=POSIZIONE_COMUNE_A,
        )
        report_b = await crea_segnalazione(
            connessione,
            municipality_id=comune_b,
            category_id=categoria_altro,
            public_ref="CR-2026-000002",
            posizione=POSIZIONE_COMUNE_B,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune_a),
    ) as connessione:
        assert await _leggi_id(connessione, "report") == {report_a}

        diretto = await connessione.execute(
            text("SELECT id FROM report WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_b)},
        )
        assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_segnalazione(
                    connessione,
                    municipality_id=comune_b,
                    category_id=categoria_altro,
                    public_ref="CR-2026-000003",
                    posizione=POSIZIONE_COMUNE_B,
                )

        modifica = await connessione.execute(
            text("""
                UPDATE report SET title = 'modificata'
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(report_b)},
        )
        assert modifica.rowcount == 0

        cancellazione = await connessione.execute(
            text("DELETE FROM report WHERE id = CAST(:id AS uuid)"),
            {"id": str(report_b)},
        )
        assert cancellazione.rowcount == 0

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE report
                        SET municipality_id = CAST(:comune_b AS uuid)
                        WHERE id = CAST(:report_a AS uuid)
                        """),
                    {"comune_b": str(comune_b), "report_a": str(report_a)},
                )


async def test_report_pubblico_visibile_anche_senza_comune(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    async with motore_amministratore.begin() as connessione:
        fuori_copertura = await crea_segnalazione(
            connessione,
            municipality_id=None,
            category_id=categoria_altro,
            public_ref="CR-2026-000011",
            posizione=POSIZIONE_COMUNE_A,
        )
        await crea_segnalazione(
            connessione,
            municipality_id=None,
            category_id=categoria_altro,
            public_ref="CR-2026-000012",
            posizione=POSIZIONE_COMUNE_A,
            visibility="hidden_by_moderation",
        )
        cancellato = await crea_segnalazione(
            connessione,
            municipality_id=None,
            category_id=categoria_altro,
            public_ref="CR-2026-000013",
            posizione=POSIZIONE_COMUNE_A,
        )
        await connessione.execute(
            text("""
                UPDATE report SET deleted_at = now()
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(cancellato)},
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
    ) as connessione:
        assert await _leggi_id(connessione, "report") == {fuori_copertura}


async def test_municipality_service_isola_tenant_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        servizio_a = await crea_servizio(
            connessione,
            municipality_id=comune_a,
            category_id=categoria_altro,
        )
        servizio_b = await crea_servizio(
            connessione,
            municipality_id=comune_b,
            category_id=categoria_altro,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune_a),
    ) as connessione:
        assert await _leggi_id(connessione, "municipality_service") == {servizio_a}

        diretto = await connessione.execute(
            text("SELECT id FROM municipality_service WHERE id = CAST(:id AS uuid)"),
            {"id": str(servizio_b)},
        )
        assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_servizio(
                    connessione,
                    municipality_id=comune_b,
                    category_id=categoria_altro,
                    codice_open311="SERVIZIO-B",
                )

        modifica = await connessione.execute(
            text("""
                UPDATE municipality_service SET sla_days = 3
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(servizio_b)},
        )
        assert modifica.rowcount == 0

        cancellazione = await connessione.execute(
            text("DELETE FROM municipality_service WHERE id = CAST(:id AS uuid)"),
            {"id": str(servizio_b)},
        )
        assert cancellazione.rowcount == 0

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE municipality_service
                        SET municipality_id = CAST(:comune_b AS uuid)
                        WHERE id = CAST(:servizio_a AS uuid)
                        """),
                    {"comune_b": str(comune_b), "servizio_a": str(servizio_a)},
                )


async def test_report_status_event_isola_tenant_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        report_a = await crea_segnalazione(
            connessione,
            municipality_id=comune_a,
            category_id=categoria_altro,
            public_ref="CR-2026-000021",
            posizione=POSIZIONE_COMUNE_A,
        )
        report_b = await crea_segnalazione(
            connessione,
            municipality_id=comune_b,
            category_id=categoria_altro,
            public_ref="CR-2026-000022",
            posizione=POSIZIONE_COMUNE_B,
        )
        evento_a = await crea_evento_stato(
            connessione,
            report_id=report_a,
            municipality_id=comune_a,
        )
        evento_b = await crea_evento_stato(
            connessione,
            report_id=report_b,
            municipality_id=comune_b,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune_a),
    ) as connessione:
        assert await _leggi_id(connessione, "report_status_event") == {evento_a}

        diretto = await connessione.execute(
            text("""
                SELECT id FROM report_status_event
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(evento_b)},
        )
        assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_evento_stato(
                    connessione,
                    report_id=report_b,
                    municipality_id=comune_b,
                )

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE report_status_event SET note_public = 'tentativo'
                        WHERE id = CAST(:id AS uuid)
                        """),
                    {"id": str(evento_b)},
                )

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        DELETE FROM report_status_event
                        WHERE id = CAST(:id AS uuid)
                        """),
                    {"id": str(evento_b)},
                )


async def test_evento_fuori_copertura_visibile_solo_in_scope_pubblico(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        report_fuori_copertura = await crea_segnalazione(
            connessione,
            municipality_id=None,
            category_id=categoria_altro,
            public_ref="CR-2026-000041",
            posizione=POSIZIONE_COMUNE_A,
            dispatch_state="out_of_jurisdiction",
        )
        evento_fuori_copertura = await crea_evento_stato(
            connessione,
            report_id=report_fuori_copertura,
            municipality_id=None,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
    ) as connessione:
        visibile = await connessione.execute(
            text("""
                SELECT id FROM report_status_event
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(evento_fuori_copertura)},
        )
        assert visibile.scalar_one() == evento_fuori_copertura
        assert await _leggi_id(connessione, "report_status_event") == {
            evento_fuori_copertura
        }

    for comune in (comune_a, comune_b):
        async with transazione_con_contesto(
            motore_applicazione,
            scope="tenant",
            tenant_id=str(comune),
        ) as connessione:
            nascosto = await connessione.execute(
                text("""
                    SELECT id FROM report_status_event
                    WHERE id = CAST(:id AS uuid)
                    """),
                {"id": str(evento_fuori_copertura)},
            )
            assert nascosto.scalar_one_or_none() is None
            assert await _leggi_id(connessione, "report_status_event") == set()


async def test_report_dispatch_isola_tenant_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
    categoria_altro: str,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        report_a = await crea_segnalazione(
            connessione,
            municipality_id=comune_a,
            category_id=categoria_altro,
            public_ref="CR-2026-000031",
            posizione=POSIZIONE_COMUNE_A,
        )
        report_b = await crea_segnalazione(
            connessione,
            municipality_id=comune_b,
            category_id=categoria_altro,
            public_ref="CR-2026-000032",
            posizione=POSIZIONE_COMUNE_B,
        )
        dispatch_a = await crea_dispatch(
            connessione,
            report_id=report_a,
            municipality_id=comune_a,
        )
        dispatch_b = await crea_dispatch(
            connessione,
            report_id=report_b,
            municipality_id=comune_b,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune_a),
    ) as connessione:
        assert await _leggi_id(connessione, "report_dispatch") == {dispatch_a}

        diretto = await connessione.execute(
            text("SELECT id FROM report_dispatch WHERE id = CAST(:id AS uuid)"),
            {"id": str(dispatch_b)},
        )
        assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_dispatch(
                    connessione,
                    report_id=report_b,
                    municipality_id=comune_b,
                    attempt_no=2,
                )

        modifica = await connessione.execute(
            text("""
                UPDATE report_dispatch SET error_code = 'tentativo'
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(dispatch_b)},
        )
        assert modifica.rowcount == 0

        cancellazione = await connessione.execute(
            text("DELETE FROM report_dispatch WHERE id = CAST(:id AS uuid)"),
            {"id": str(dispatch_b)},
        )
        assert cancellazione.rowcount == 0

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE report_dispatch
                        SET municipality_id = CAST(:comune_b AS uuid)
                        WHERE id = CAST(:dispatch_a AS uuid)
                        """),
                    {"comune_b": str(comune_b), "dispatch_a": str(dispatch_a)},
                )


async def test_outbox_event_isola_tenant_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
) -> None:
    comune_a, comune_b = await _crea_due_comuni(motore_amministratore)
    async with motore_amministratore.begin() as connessione:
        evento_a = await crea_evento_outbox(connessione, tenant_id=comune_a)
        evento_b = await crea_evento_outbox(connessione, tenant_id=comune_b)

    async with transazione_con_contesto(
        motore_applicazione,
        scope="tenant",
        tenant_id=str(comune_a),
    ) as connessione:
        assert await _leggi_id(connessione, "outbox_event") == {evento_a}

        diretto = await connessione.execute(
            text("SELECT id FROM outbox_event WHERE id = CAST(:id AS uuid)"),
            {"id": str(evento_b)},
        )
        assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_evento_outbox(connessione, tenant_id=comune_b)

        modifica = await connessione.execute(
            text("""
                UPDATE outbox_event SET last_error = 'tentativo'
                WHERE id = CAST(:id AS uuid)
                """),
            {"id": str(evento_b)},
        )
        assert modifica.rowcount == 0

        cancellazione = await connessione.execute(
            text("DELETE FROM outbox_event WHERE id = CAST(:id AS uuid)"),
            {"id": str(evento_b)},
        )
        assert cancellazione.rowcount == 0

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await connessione.execute(
                    text("""
                        UPDATE outbox_event
                        SET tenant_id = CAST(:comune_b AS uuid)
                        WHERE id = CAST(:evento_a AS uuid)
                        """),
                    {"comune_b": str(comune_b), "evento_a": str(evento_a)},
                )


async def test_tabelle_utente_isolano_utente_diverso(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
) -> None:
    async with motore_amministratore.begin() as connessione:
        utente_a = await crea_utente(connessione, nickname="cittadino-a")
        utente_b = await crea_utente(connessione, nickname="cittadino-b")
        token_a = await crea_refresh_token(connessione, user_id=utente_a)
        token_b = await crea_refresh_token(connessione, user_id=utente_b)
        notifica_a = await crea_notifica(
            connessione,
            user_id=utente_a,
            dedupe_key="notifica-a",
        )
        notifica_b = await crea_notifica(
            connessione,
            user_id=utente_b,
            dedupe_key="notifica-b",
        )
        preferenza_a = await crea_preferenza_notifica(
            connessione,
            user_id=utente_a,
        )
        preferenza_b = await crea_preferenza_notifica(
            connessione,
            user_id=utente_b,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
        user_id=str(utente_a),
    ) as connessione:
        assert await _leggi_id(connessione, "user") == {utente_a}
        assert await _leggi_id(connessione, "refresh_token") == {token_a}
        assert await _leggi_id(connessione, "notification") == {notifica_a}
        assert await _leggi_id(connessione, "notification_preference") == {preferenza_a}

        for tabella, identificativo in (
            ("user", utente_b),
            ("refresh_token", token_b),
            ("notification", notifica_b),
            ("notification_preference", preferenza_b),
        ):
            diretto = await connessione.execute(
                text(f'SELECT id FROM "{tabella}" WHERE id = CAST(:id AS uuid)'),
                {"id": str(identificativo)},
            )
            assert diretto.scalar_one_or_none() is None

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_utente(connessione, nickname="intruso")

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_refresh_token(connessione, user_id=utente_b)

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_notifica(
                    connessione,
                    user_id=utente_b,
                    dedupe_key="notifica-intrusa",
                )

        with pytest.raises(DBAPIError):
            async with connessione.begin_nested():
                await crea_preferenza_notifica(connessione, user_id=utente_b)

        for tabella, identificativo in (
            ("user", utente_b),
            ("refresh_token", token_b),
            ("notification", notifica_b),
            ("notification_preference", preferenza_b),
        ):
            modifica = await connessione.execute(
                text(f'UPDATE "{tabella}" SET id = id WHERE id = CAST(:id AS uuid)'),
                {"id": str(identificativo)},
            )
            assert modifica.rowcount == 0

            cancellazione = await connessione.execute(
                text(f'DELETE FROM "{tabella}" WHERE id = CAST(:id AS uuid)'),
                {"id": str(identificativo)},
            )
            assert cancellazione.rowcount == 0
