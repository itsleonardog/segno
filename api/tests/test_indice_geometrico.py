from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_ricerca_point_in_polygon_usa_indice_gist(
    motore_amministratore: AsyncEngine,
    database_migrato: None,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await connessione.execute(text("""
                INSERT INTO municipality (
                    id, slug, name, istat_code, region, timezone, locale,
                    boundary, dispatch_mode, priority, is_active, settings
                )
                SELECT
                    gen_random_uuid(),
                    'comune-' || numero,
                    'Comune ' || numero,
                    'ISTAT-' || numero,
                    'Lombardia',
                    'Europe/Rome',
                    'it',
                    ST_Multi(
                        ST_MakeEnvelope(
                            (numero % 100) * 0.02,
                            (numero / 100) * 0.02,
                            (numero % 100) * 0.02 + 0.01,
                            (numero / 100) * 0.02 + 0.01,
                            4326
                        )
                    )::geography,
                    CAST('email' AS dispatch_mode),
                    0,
                    true,
                    '{}'::jsonb
                FROM generate_series(0, 999) AS numero
                """))
        await connessione.execute(text("ANALYZE municipality"))

        esito = await connessione.execute(text("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id
                FROM municipality
                WHERE ST_Covers(
                    boundary,
                    ST_GeogFromText('SRID=4326;POINT(0.005 0.005)')
                )
                """))
        piano = "\n".join(esito.scalars().all())

    assert "ix_municipality_boundary_gist" in piano


async def test_bbox_mappa_usa_indice_gist_su_report(
    motore_amministratore: AsyncEngine,
    categoria_altro: str,
    database_migrato: None,
) -> None:
    async with motore_amministratore.begin() as connessione:
        await connessione.execute(
            text("""
                INSERT INTO report (
                    id, public_ref, category_id, title, description, location
                )
                SELECT
                    gen_random_uuid(),
                    'CR-2026-' || lpad(numero::text, 6, '0'),
                    CAST(:category_id AS uuid),
                    'Segnalazione ' || numero,
                    'Descrizione ' || numero,
                    ST_SetSRID(
                        ST_MakePoint(
                            (numero % 100) * 0.01,
                            (numero / 100) * 0.01
                        ),
                        4326
                    )::geography
                FROM generate_series(0, 1999) AS numero
                """),
            {"category_id": categoria_altro},
        )
        await connessione.execute(text("ANALYZE report"))

        esito = await connessione.execute(text("""
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT id
                FROM report
                WHERE location && ST_MakeEnvelope(
                    0.0, 0.0, 0.1, 0.1, 4326
                )::geography
                """))
        piano = "\n".join(esito.scalars().all())

    assert "ix_report_location_gist" in piano
