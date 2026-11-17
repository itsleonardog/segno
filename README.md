# Segnalazione civica multi-comune

Piattaforma per raccogliere le segnalazioni dei cittadini, risolvere il comune
competente dal punto geografico e tracciare il dispatch verso l'ente.

Il repository contiene due applicazioni deployabili separatamente:

- `api/` — backend FastAPI e dominio Python.
- `web/` — frontend Next.js e componenti React.

La documentazione architetturale di riferimento è il piano in
[`civic-reporting-plan.md`](civic-reporting-plan.md).

## Prerequisiti

- Python 3.12 e uv.
- Node.js 20 e npm.
- make.

## Avvio

```bash
make setup
```

Il comando crea l'ambiente uv, installa le dipendenze del workspace npm e
registra gli hook di pre-commit. L'API si avvia con
`cd api && uv run uvicorn app.main:app --reload`; il worker di dispatch è
descritto più sotto.

## Comandi

| Comando | Effetto |
|---|---|
| `make setup` | Installa dipendenze Python e Node e registra pre-commit |
| `make format` | Applica ruff, black, prettier ed eslint --fix |
| `make lint` | Verifica ruff, black, eslint e prettier senza modificare i file |
| `make test` | Esegue pytest; i test di database si saltano se PostGIS non è attivo |
| `make test-db-up` | Avvia PostgreSQL 16 con PostGIS su `localhost:55432` |
| `make test-database` | Avvia il database di test ed esegue pytest |
| `make test-db-down` | Ferma il database di test e rimuove i volumi |

## Database di test

I test di migrazione, RLS e indici spaziali richiedono PostgreSQL 16 con
PostGIS. Avvia il servizio con `make test-db-up` e poi esegui `make test`, oppure
usa `make test-database` per fare entrambe le cose.

Le migrazioni usano `CIVIC_DATABASE_URL`. I ruoli `civic_migrator` e `civic_app`
sono creati dalla prima migrazione; le password predefinite di sviluppo sono
`civic_migrator` e `civic_app` e si sovrascrivono con
`CIVIC_MIGRATOR_PASSWORD` e `CIVIC_APP_PASSWORD`.

Per applicare lo schema:

```bash
cd api && CIVIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:55432/civic_test uv run alembic upgrade head
```

## Worker di dispatch

Il relay dell'outbox gira come processo separato dal server HTTP:

```bash
cd api && uv run python -m app.worker
```

Il polling legge `outbox_event` con `FOR UPDATE SKIP LOCKED` in ambito di
sistema, applica la regola di dispatch del comune e rispetta il backoff
registrato in `report_dispatch.next_attempt_at`. Le variabili di ambiente
rilevanti sono `CIVIC_DATABASE_URL_APP`, `CIVIC_WORKER_PAUSA_SECONDI`,
`CIVIC_URL_PUBBLICA_BASE`, `CIVIC_EMAIL_MITTENTE`, `CIVIC_EMAIL_KEK` e
`CIVIC_OPEN311_KEY_<RIFERIMENTO>` per le API key dei comuni.

## Stile del codice

Le regole di naming, commenti, docstring, struttura, gestione degli errori,
log, test, messaggi all'utente e documentazione sono in
[`docs/house-style.md`](docs/house-style.md). L'estratto operativo usato dagli
assistenti è in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

Ogni contributo, scritto da una persona o assistito da uno strumento, passa
dalla stessa review e dagli stessi controlli automatici. Non esiste un
percorso di review separato per il codice generato.

## Contribuire

Esegui `make format` prima di aprire una modifica, verifica con `make lint` e
`make test`, e non aggirare gli hook di pre-commit. Le eccezioni allo stile
vanno motivate in review, non nascoste con una modifica alla configurazione.
