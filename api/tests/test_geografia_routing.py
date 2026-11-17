from __future__ import annotations

from aiuto_tenant import CONFINE_COMUNE_A, crea_comune
from sqlalchemy.ext.asyncio import AsyncEngine

from app.dominio.geografia import risolvi_comune_competente
from app.infrastruttura.database import transazione_con_contesto

CONFINE_GRANDE = "SRID=4326;MULTIPOLYGON(((10 45, 10 45.2, 10.2 45.2, 10.2 45, 10 45)))"
CONFINE_PICCOLO = (
    "SRID=4326;MULTIPOLYGON(((10.05 45.05, 10.05 45.1, 10.1 45.1, "
    "10.1 45.05, 10.05 45.05)))"
)


async def test_geografia_risoluzione(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
) -> None:
    async with motore_amministratore.begin() as connessione:
        comune = await crea_comune(connessione, confine=CONFINE_COMUNE_A)

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
    ) as connessione:
        punto_interno = await risolvi_comune_competente(connessione, 45.05, 9.05)
        punto_fuori = await risolvi_comune_competente(connessione, 44.0, 8.0)
        punto_sul_confine = await risolvi_comune_competente(connessione, 45.0, 9.05)
        punto_sul_vertice = await risolvi_comune_competente(connessione, 45.0, 9.0)

    assert punto_interno is not None
    assert punto_interno.id == comune
    assert punto_interno.is_ambiguo is False
    assert punto_fuori is None
    assert punto_sul_confine is not None
    assert punto_sul_confine.id == comune
    assert punto_sul_vertice is not None
    assert punto_sul_vertice.id == comune


async def test_geografia_sovrapposizione(
    motore_amministratore: AsyncEngine,
    motore_applicazione: AsyncEngine,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await crea_comune(connessione, confine=CONFINE_GRANDE, priorita=0)
        comune_piccolo = await crea_comune(
            connessione,
            confine=CONFINE_PICCOLO,
            priorita=0,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
    ) as connessione:
        risolto_per_area = await risolvi_comune_competente(
            connessione,
            45.07,
            10.07,
        )

    assert risolto_per_area is not None
    assert risolto_per_area.id == comune_piccolo
    assert risolto_per_area.is_ambiguo is True

    async with motore_amministratore.begin() as connessione:
        comune_prioritario = await crea_comune(
            connessione,
            confine=CONFINE_GRANDE,
            priorita=10,
        )

    async with transazione_con_contesto(
        motore_applicazione,
        scope="public",
    ) as connessione:
        risolto_per_priorita = await risolvi_comune_competente(
            connessione,
            45.07,
            10.07,
        )

    assert risolto_per_priorita is not None
    assert risolto_per_priorita.id == comune_prioritario
    assert risolto_per_priorita.is_ambiguo is True
