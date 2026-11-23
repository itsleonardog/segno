# Segnalazione civica multi-comune

Piattaforma per raccogliere le segnalazioni dei cittadini, risolvere il comune
competente dal punto geografico e tracciare il dispatch verso l'ente.

Il repository contiene due applicazioni deployabili separatamente:

- `api/` — backend FastAPI e dominio Python.
- `web/` — frontend Next.js e componenti React.

## Architettura

Lo stack è composto da:

- API: FastAPI su Python 3.12, SQLAlchemy async, PostgreSQL 16 con PostGIS e
  Alembic per le migrazioni.
- Worker: processo Python separato che legge l'outbox, esegue il dispatch
  Open311 o email, sincronizza gli stati e applica la retention.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS e Leaflet con
  OpenStreetMap.
- Sicurezza: JWT di accesso a breve durata, refresh token con rotazione,
  Argon2id per le password, cifratura AES-256-GCM delle email a riposo e Row
  Level Security su PostgreSQL.
- Deploy: Docker Compose con i servizi `db`, `migrate`, `api`, `worker` e
  `web`.

Il piano architetturale di riferimento è
[`civic-reporting-plan.md`](civic-reporting-plan.md).

## Documentazione

- [`docs/guida-aggiunta-comune.md`](docs/guida-aggiunta-comune.md): import del
  confine, routing, mapping delle categorie e checklist di configurazione.
- [`docs/guida-dispatch-falliti.md`](docs/guida-dispatch-falliti.md): lettura
  dei fallimenti, classificazione degli errori e retry manuale.
- [`docs/roadmap.md`](docs/roadmap.md): prossime iterazioni, prerequisiti e
  criteri di accettazione.
- [`docs/informativa-privacy.md`](docs/informativa-privacy.md): bozza
  dell'informativa breve ed estesa.
- [`docs/house-style.md`](docs/house-style.md): regole di stile del codice e
  della documentazione.

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
| `make test-e2e` | Avvia il database, applica le migrazioni ed esegue Playwright |
| `make test-db-down` | Ferma il database di test e rimuove i volumi |
| `make prod-up` | Costruisce e avvia lo stack con `docker-compose.prod.yml` |
| `make prod-down` | Ferma lo stack di produzione e rimuove i volumi |
| `make prod-logs` | Segue i log dello stack di produzione |

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
registrato in `report_dispatch.next_attempt_at`. Nello stesso processo girano
la sincronizzazione periodica degli stati Open311 e il job di retention. Le
variabili di ambiente sono descritte in "Chiavi API e variabili d'ambiente";
le principali per il worker sono `CIVIC_DATABASE_URL_APP`,
`CIVIC_WORKER_PAUSA_SECONDI`, `CIVIC_OPEN311_SYNC_SECONDI`,
`CIVIC_RETENTION_SECONDI`, `CIVIC_URL_PUBBLICA_BASE`, `CIVIC_EMAIL_MITTENTE`,
`CIVIC_EMAIL_KEK` e `CIVIC_OPEN311_KEY_<RIFERIMENTO>`.

## Chiavi API e variabili d'ambiente

### Chiavi Open311

La chiave API di un comune non è salvata nel database. In
`municipality.open311_api_key_ref` si conserva solo un riferimento; il worker
risolve la chiave dall'ambiente con:

```bash
CIVIC_OPEN311_KEY_<RIFERIMENTO>=...
```

Il riferimento viene convertito in maiuscolo. Se
`open311_api_key_ref = 'comune_x'`, la variabile è
`CIVIC_OPEN311_KEY_COMUNE_X`. La chiave viene rilasciata dal comune o dal
gestore del servizio Open311: non si genera dalla piattaforma. Dopo la modifica
riavvia il worker. La procedura completa è in
[`docs/guida-aggiunta-comune.md`](docs/guida-aggiunta-comune.md). Il prefisso è
configurabile con `CIVIC_OPEN311_KEY_PREFISSO`.

### Segreti applicativi

In produzione `CIVIC_JWT_SECRET`, `CIVIC_EMAIL_KEK` e
`CIVIC_EMAIL_LOOKUP_PEPPER` devono essere generati casualmente e conservati in
un secret manager, non nel repository.

```bash
openssl rand -hex 32    # CIVIC_JWT_SECRET
openssl rand -base64 32 # CIVIC_EMAIL_KEK
openssl rand -base64 32 # CIVIC_EMAIL_LOOKUP_PEPPER
```

`CIVIC_EMAIL_KEK` e `CIVIC_EMAIL_LOOKUP_PEPPER` devono essere base64 validi e
decodificare almeno 32 byte. Cambiare la KEK rende indecifrabili le email già
salvate: la rotazione richiede una procedura di ri-cifratura.

### Variabili principali

| Variabile | Uso |
|---|---|
| `CIVIC_ENV` | `production` fuori dallo sviluppo |
| `CIVIC_DATABASE_URL` | connessione del ruolo migratore, usata da Alembic |
| `CIVIC_DATABASE_URL_APP` | connessione del ruolo applicativo, usata da API e worker |
| `CIVIC_DB_USER`, `CIVIC_DB_PASSWORD`, `CIVIC_DB_NAME` | credenziali del database nello stack Docker |
| `CIVIC_APP_PASSWORD`, `CIVIC_MIGRATOR_PASSWORD` | password dei ruoli `civic_app` e `civic_migrator` |
| `CIVIC_JWT_SECRET` | firma dei token di accesso |
| `CIVIC_EMAIL_KEK` | cifratura delle email a riposo |
| `CIVIC_EMAIL_LOOKUP_PEPPER` | HMAC per il lookup dell'email al login |
| `CIVIC_URL_PUBBLICA_BASE` | base degli URL nelle email e nei link pubblici |
| `CIVIC_EMAIL_MITTENTE` | mittente delle email di servizio |
| `CIVIC_CORS_ORIGINS` | origini ammesse dal browser, separate da virgola |
| `CIVIC_API_PUBBLICA_URL` | URL dell'API usato durante la build del frontend |
| `CIVIC_OPEN311_KEY_<RIFERIMENTO>` | chiave API del comune |
| `CIVIC_OPEN311_KEY_PREFISSO` | prefisso delle variabili delle chiavi Open311 |
| `CIVIC_WORKER_PAUSA_SECONDI` | pausa del ciclo del worker |
| `CIVIC_OPEN311_SYNC_SECONDI` | intervallo della sincronizzazione Open311 |
| `CIVIC_RETENTION_SECONDI` | intervallo del job di retention |
| `CIVIC_RATE_LIMIT_LOGIN`, `CIVIC_RATE_LIMIT_REGISTRAZIONE`, `CIVIC_RATE_LIMIT_SEGNALAZIONI`, `CIVIC_RATE_LIMIT_GEOCODING` | limiti di frequenza al minuto |

### Stato del provider email

Nell'implementazione attuale l'invio email è uno stub. Con `CIVIC_ENV`
diverso da `dev` i messaggi non vengono consegnati: il dispatch email verso i
comuni fallisce con l'evento `dispatch_email_provider_not_configured` e le
email di verifica e notifica non partono. Il collegamento di un provider reale
è un prerequisito di go-live ed è elencato in
[`docs/roadmap.md`](docs/roadmap.md).

## Produzione con Docker

Lo stack completo è descritto in `docker-compose.prod.yml`: PostgreSQL con
PostGIS, applicazione delle migrazioni, API, worker e frontend Next.js in
modalità `standalone`. Copia `.env.example` in `.env` e sostituisci i segreti
prima di avviare lo stack:

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
```

I valori predefiniti di `.env.example` servono solo allo stack locale. In
produzione `CIVIC_JWT_SECRET`, `CIVIC_EMAIL_KEK` e
`CIVIC_EMAIL_LOOKUP_PEPPER` vanno forniti dall'ambiente e non versionati.

Prima di esporre il servizio verifica che i comuni siano configurati secondo
[`docs/guida-aggiunta-comune.md`](docs/guida-aggiunta-comune.md) e che il
provider email sia collegato. Nello stato attuale l'invio email è uno stub:
con `CIVIC_ENV=production` le email non vengono consegnate.

L'API espone `GET /health` per la liveness e `GET /health/ready` per la
readiness; il secondo verifica la connessione al database.

## Test end-to-end

I test Playwright stanno in `web/e2e/` e simulano il flusso del cittadino:
registrazione, accesso, selezione del punto sulla mappa, invio della
segnalazione e apertura del dettaglio. Dopo aver avviato il database con
`make test-db-up` e applicato le migrazioni, esegui:

```bash
cd web && npm run test:e2e
```

La prima volta installa il browser Chromium con
`cd web && npx playwright install chromium`. In alternativa `make test-e2e`
esegue in sequenza database, migrazioni e test. Playwright avvia API e frontend
come processi di supporto; imposta `PLAYWRIGHT_BASE_URL` per usare servizi già
in esecuzione.

## Integrazione continua

La pipeline in `.github/workflows/ci.yml` gira su push e pull request verso
`main`. Il job `test-backend` esegue migrazioni, `ruff check` e `pytest` con un
database PostGIS; `test-frontend` esegue `typecheck`, `lint` e `build`;
`test-e2e` avvia lo stack di test ed esegue Playwright. I segreti usati in CI
sono valori fittizi passati come variabili d'ambiente.

## Stile del codice

Le regole di naming, commenti, docstring, struttura, gestione degli errori,
log, test, messaggi all'utente e documentazione sono in
[`docs/house-style.md`](docs/house-style.md). L'estratto operativo usato dagli
assistenti è in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

Ogni contributo, scritto da una persona o assistito da uno strumento, passa
dalla stessa review e dagli stessi controlli automatici. Non esiste un
percorso di review separato per il codice generato.

## Come contribuire

Prima di aprire una modifica esegui `make format`, verifica con `make lint` e
`make test` e non aggirare gli hook di pre-commit. Le eccezioni allo stile
vanno motivate in review, non nascoste con una modifica alla configurazione.

Le regole di naming, commenti, docstring, struttura, errori, log, test,
messaggi e documentazione sono in
[`docs/house-style.md`](docs/house-style.md). Ogni contributo, anche se
assistito da uno strumento, passa dalla stessa review e dagli stessi controlli:
non esiste un percorso separato per il codice generato. Se una modifica cambia
il comportamento operativo, aggiorna nello stesso cambio i documenti in `docs/`
e il README.
