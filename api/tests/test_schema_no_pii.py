from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

COLONNE_VIETATE = {
    "full_name",
    "first_name",
    "last_name",
    "phone",
    "telefono",
    "codice_fiscale",
    "birth_date",
    "address_residenza",
}


async def _colonne_schema(motore: AsyncEngine) -> list[tuple[str, str, str]]:
    async with motore.connect() as connessione:
        esito = await connessione.execute(text("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """))
        return [tuple(riga) for riga in esito.all()]


async def test_schema_non_contiene_colonne_personali_vietate(
    motore_amministratore: AsyncEngine,
    database_migrato: None,
) -> None:
    colonne = await _colonne_schema(motore_amministratore)
    nomi_presenti = {nome_colonna.lower() for _, nome_colonna, _ in colonne}

    assert not (nomi_presenti & COLONNE_VIETATE)


async def test_email_persistita_solo_come_cifrato_e_hash(
    motore_amministratore: AsyncEngine,
    database_migrato: None,
) -> None:
    colonne = await _colonne_schema(motore_amministratore)
    colonne_utente = {
        nome_colonna: tipo_dato
        for nome_tabella, nome_colonna, tipo_dato in colonne
        if nome_tabella == "user"
    }
    colonne_servizio = {
        nome_colonna: tipo_dato
        for nome_tabella, nome_colonna, tipo_dato in colonne
        if nome_tabella == "municipality_service"
    }

    assert "email" not in colonne_utente
    assert colonne_utente["email_enc"] == "bytea"
    assert colonne_utente["email_lookup_hash"] == "text"
    assert colonne_servizio["fallback_email_enc"] == "bytea"
