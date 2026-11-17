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
descritto più sotto. Il frontend si avvia con `npm run dev --workspace web` e
risponde su `http://localhost:3000`. Per impostazione predefinita chiama
`http://localhost:8000`; imposta `NEXT_PUBLIC_API_URL` in `web/.env.local` per
puntare a un'altra API. Le origini ammesse dal backend si configurano con
`CIVIC_CORS_ORIGINS`.

## Comandi

| Comando | Effetto |
|---|---|
| `make setup` | Installa dipendenze Python e Node e registra pre-commit |
| `make format` | Applica ruff, black, prettier ed eslint --fix |
| `make lint` | Verifica ruff, black, eslint e prettier senza modificare i file |
| `make test` | Esegue pytest; i test di database si saltano se PostGIS non è attivo |
| `make web-dev` | Avvia Next.js in sviluppo su `localhost:3000` |
| `make web-build` | Compila il frontend per la produzione |
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

## Frontend

Il frontend usa Next.js App Router, TypeScript, Tailwind CSS e Leaflet con
OpenStreetMap. Le pagine sono la mappa pubblica (`/`), il form di segnalazione
(`/report`), il dettaglio (`/reports/[public_ref]`), l'accesso (`/login`) e la
registrazione (`/register`). Lo stato di autenticazione è gestito da un
`AuthContext` che conserva i token in `localStorage` e ricarica il profilo da
`GET /v1/me`.

Variabili di ambiente rilevanti:

- `NEXT_PUBLIC_API_URL`: URL base dell'API, predefinito
  `http://localhost:8000`.
- `CIVIC_CORS_ORIGINS`: origini ammesse dal backend, separate da virgola,
  predefinito `http://localhost:3000`.

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
