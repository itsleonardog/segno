# Aggiunta di un nuovo comune

Questa guida descrive i passaggi per rendere operativo un nuovo comune sulla
piattaforma. L'ordine è vincolante: prima si importa il confine, poi si
configura il dispatch, infine si verificano routing e invio con una
segnalazione di prova.

L'implementazione attuale non espone ancora endpoint di piattaforma per la
gestione dei comuni e non prevede un'interfaccia amministrativa dedicata. Le
operazioni di questa guida si eseguono sul database con il ruolo
`civic_migrator` e sulle variabili d'ambiente del worker. La gestione via API è
descritta in [`roadmap.md`](roadmap.md).

## Prerequisiti

- Database migrato con `alembic upgrade head`.
- Accesso a PostgreSQL con un ruolo che possa scrivere sul registro
  `municipality` e su `municipality_service`.
- File GeoJSON del confine amministrativo.
- Codice ISTAT del comune, regione, fuso orario e locale.
- Decisione sulla modalità di dispatch: Open311, email o Open311 con fallback
  email.
- Per Open311: endpoint GeoReport v2, `jurisdiction_id` se richiesto e
  riferimento alla chiave API.
- Per l'email: indirizzo del protocollo del comune e chiave di cifratura
  `CIVIC_EMAIL_KEK` con cui cifrarlo.

## 1. Scegliere la fonte del confine

Il confine deve essere un'area amministrativa ufficiale, non un poligono
disegnato a mano. Le fonti ammesse sono:

- confini amministrativi ISTAT, nella versione più recente disponibile;
- portali open data regionali o provinciali, se pubblicano il confine del
  comune con licenza compatibile;
- geometrie fornite direttamente dal comune, se accompagnate da una fonte e da
  una data di riferimento.

Prima di importare, annota sempre:

- la fonte (`boundary_source`);
- la versione o la data della fonte (`boundary_version`);
- il checksum del file (`boundary_checksum`);
- la data di import (`boundary_imported_at`, impostata a `now()`).

La licenza e l'attribuzione della fonte vanno verificate. Non usare geometrie
di cui non è chiara la provenienza.

## 2. Preparare il GeoJSON

Il database accetta un `geography(MultiPolygon, 4326)`. Il file deve quindi
contenere un poligono o una multipoligono in coordinate WGS84 (EPSG:4326).

Regole di preparazione:

- un `Polygon` va convertito in `MultiPolygon` con `ST_Multi`;
- il SRID va forzato a 4326;
- la geometria deve essere valida;
- il bounding box deve essere plausibile per il comune;
- le isole e gli eventuali exclavi devono essere inclusi nello stesso
  `MultiPolygon`.

Controllo preliminare con `psql` o con un client SQL, sostituendo il segnaposto
con il GeoJSON compatto:

```sql
WITH geometria AS (
  SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) AS g
)
SELECT
  ST_IsValid(g) AS valido,
  ST_GeometryType(g) AS tipo,
  ST_SRID(g) AS srid,
  ST_Area(g::geography) / 1000000 AS area_km2,
  ST_AsText(ST_Envelope(g)) AS bounding_box
FROM geometria;
```

Se `valido` è `false`, correggi la fonte. Se non è possibile, usa
`ST_CollectionExtract(ST_MakeValid(g), 3)` per estrarre i poligoni validi dalla
geometria riparata. Non importare una geometria non valida senza averla
verificata.

## 3. Importare il comune

Lo script seguente è un esempio operativo da eseguire una sola volta, dentro
`api/`, con le variabili d'ambiente del database di destinazione. Non è codice
applicativo e non va aggiunto al repository.

```python
import asyncio
import hashlib
import json
import pathlib

from sqlalchemy import text

from app.infrastruttura.database import crea_motore

PERCORSO_GEOJSON = pathlib.Path("confine.geojson")
URL_MIGRATORE = "postgresql+asyncpg://civic_migrator:password@localhost:5432/civic"


async def main() -> None:
    contenuto = PERCORSO_GEOJSON.read_text(encoding="utf-8")
    documento = json.loads(contenuto)
    if documento.get("type") == "FeatureCollection":
        geometria = documento["features"][0]["geometry"]
    elif documento.get("type") == "Feature":
        geometria = documento["geometry"]
    else:
        geometria = documento

    checksum = hashlib.sha256(contenuto.encode("utf-8")).hexdigest()
    motore = crea_motore(URL_MIGRATORE)
    try:
        async with motore.begin() as connessione:
            await connessione.execute(
                text("""
                    INSERT INTO municipality (
                        id, slug, name, istat_code, region, timezone, locale,
                        boundary, boundary_source, boundary_version,
                        boundary_imported_at, boundary_checksum, dispatch_mode,
                        open311_endpoint_url, open311_jurisdiction_id,
                        open311_api_key_ref, priority
                    )
                    VALUES (
                        gen_random_uuid(), :slug, :nome, :istat, :regione,
                        :timezone, :locale,
                        ST_Multi(
                            ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)
                        )::geography,
                        :fonte, :versione, now(), :checksum,
                        CAST(:modalita AS dispatch_mode),
                        :endpoint_open311, :jurisdiction_id,
                        :chiave_open311_ref, 0
                    )
                    """),
                {
                    "slug": "nome-comune",
                    "nome": "Nome del comune",
                    "istat": "012345",
                    "regione": "Lombardia",
                    "timezone": "Europe/Rome",
                    "locale": "it",
                    "geojson": json.dumps(geometria),
                    "fonte": "ISTAT - confini amministrativi",
                    "versione": "2026-01-01",
                    "checksum": checksum,
                    "modalita": "email",
                    "endpoint_open311": None,
                    "jurisdiction_id": None,
                    "chiave_open311_ref": None,
                },
            )
    finally:
        await motore.dispose()


asyncio.run(main())
```

Esecuzione:

```bash
cd api
CIVIC_DATABASE_URL="postgresql+asyncpg://civic_migrator:password@localhost:5432/civic" \
  uv run python nome_dello_script.py
```

Il campo `priority` serve quando due confini si sovrappongono: vince il valore
più alto. A parità di priorità vince il comune con area minore. La risposta
`/v1/geo/resolve` segnala `is_ambiguo=true` quando più di un comune copre il
punto.

Il campo `coverage_bbox` è opzionale e non è richiesto per il routing. Il campo
`settings` è un JSONB riservato a configurazioni future: non inserire segreti.

### Aggiornare un confine esistente

Un aggiornamento si esegue con `UPDATE municipality`, aggiornando insieme
`boundary`, `boundary_source`, `boundary_version`, `boundary_imported_at` e
`boundary_checksum`.

L'aggiornamento del confine non riassegna automaticamente le segnalazioni già
create: `report.municipality_id` resta quello risolto al momento della
creazione. Non esiste ancora un job di ri-risoluzione non retroattiva. Se il
nuovo confine cambia l'assegnazione di segnalazioni esistenti, la differenza va
verificata e gestita manualmente, tracciando l'operazione.

## 4. Configurare il routing

La modalità si imposta su `municipality.dispatch_mode`:

| Modalità | Comportamento | Campi necessari |
|---|---|---|
| `open311` | invia solo via Open311 | `open311_endpoint_url` e un `open311_service_code` per ogni categoria |
| `email` | invia solo via email | `fallback_active=true` e `fallback_email_enc` per ogni categoria |
| `open311_then_email` | prova Open311 e usa l'email come fallback | endpoint e service code, più fallback email |

Per Open311 compila anche:

- `open311_endpoint_url`: URL dell'endpoint GeoReport v2 del comune;
- `open311_jurisdiction_id`: solo se il comune lo richiede;
- `open311_api_key_ref`: riferimento logico alla chiave, non la chiave.

La chiave API non viene salvata nel database. Il worker la risolve
dall'ambiente con la variabile `CIVIC_OPEN311_KEY_<RIFERIMENTO>`, dove
`<RIFERIMENTO>` è `open311_api_key_ref` convertito in maiuscolo. Se il
riferimento è `comune_x`, la variabile è `CIVIC_OPEN311_KEY_COMUNE_X`.

Dopo aver cambiato una chiave o un endpoint, riavvia il worker. La
configurazione di dispatch è memorizzata in una cache in memoria con durata di
60 secondi per processo; senza riavvio una modifica al database può richiedere
fino a un minuto per essere letta.

### Esempio di configurazione Open311

```sql
UPDATE municipality
SET dispatch_mode = CAST('open311' AS dispatch_mode),
    open311_endpoint_url = 'https://api.comune.example/v2/requests',
    open311_jurisdiction_id = 'comune.example',
    open311_api_key_ref = 'comune_x'
WHERE slug = 'nome-comune';
```

```bash
# Variabile letta dal worker, non dal database.
export CIVIC_OPEN311_KEY_COMUNE_X="chiave-fornita-dal-comune"
```

### Esempio di configurazione solo email

```sql
UPDATE municipality
SET dispatch_mode = CAST('email' AS dispatch_mode),
    open311_endpoint_url = NULL,
    open311_jurisdiction_id = NULL,
    open311_api_key_ref = NULL
WHERE slug = 'nome-comune';
```

## 5. Mappare le categorie

Le categorie sono globali e vengono create dalla migrazione iniziale:
`strade`, `illuminazione`, `rifiuti`, `altro`. Per ogni categoria che il comune
deve ricevere serve una riga in `municipality_service`.

I campi principali sono:

- `open311_service_code`: codice del servizio presso il comune;
- `open311_extra_fields`: oggetto JSONB con campi aggiuntivi richiesti
  dall'endpoint;
- `fallback_email_enc`: indirizzo email cifrato del protocollo;
- `fallback_active`: abilita l'uso dell'email;
- `sla_days`: giorni previsti per la lavorazione, se concordati.

Esempio per la categoria `strade`:

```sql
INSERT INTO municipality_service (
    id, municipality_id, category_id, open311_service_code,
    open311_extra_fields, fallback_active, fallback_email_enc, sla_days
)
SELECT
    gen_random_uuid(), m.id, c.id, '123',
    '{"department": "lavori-pubblici"}'::jsonb,
    false, NULL, 30
FROM municipality AS m
JOIN category AS c ON c.slug = 'strade'
WHERE m.slug = 'nome-comune'
ON CONFLICT (municipality_id, category_id) DO UPDATE
SET open311_service_code = EXCLUDED.open311_service_code,
    open311_extra_fields = EXCLUDED.open311_extra_fields,
    sla_days = EXCLUDED.sla_days;
```

Se una categoria non ha una riga in `municipality_service`, il worker non ha
un canale per quella categoria e la segnalazione finisce in
`dispatch_state=failed` con il messaggio "Nessun canale di dispatch configurato
per il comune". Non è un errore di rete: manca la configurazione.

### Cifrare l'indirizzo email di fallback

`fallback_email_enc` non è testo in chiaro. Va cifrato con la stessa chiave
`CIVIC_EMAIL_KEK` usata dall'applicazione, con AES-256-GCM, nel formato
`nonce(12 byte) + ciphertext`. Il cifrario usa il `key_id` corrente
(`dev-v1` nell'implementazione attuale) come dato associato.

Esempio operativo da eseguire una sola volta, dentro `api/`:

```python
import asyncio
import os

from sqlalchemy import text

from app.infrastruttura.cifratura_email import CifrarioEmailEnvelope
from app.infrastruttura.configurazione import (
    decodifica_segreto_base64,
    leggi_configurazione_sicurezza,
)
from app.infrastruttura.database import crea_motore

SLUG_COMUNE = "nome-comune"
SLUG_CATEGORIA = "strade"
EMAIL_PROTOCOLLO = "protocollo@comune.example"


async def main() -> None:
    configurazione = leggi_configurazione_sicurezza()
    chiave = decodifica_segreto_base64(
        configurazione.chiave_cifratura_base64,
        "CIVIC_EMAIL_KEK",
    )
    cifrario = CifrarioEmailEnvelope(chiave)
    email_cifrata, _ = cifrario.cifra(EMAIL_PROTOCOLLO)

    motore = crea_motore(os.environ["CIVIC_DATABASE_URL"])
    try:
        async with motore.begin() as connessione:
            esito = await connessione.execute(
                text("""
                    UPDATE municipality_service AS s
                    SET fallback_email_enc = :email_cifrata,
                        fallback_active = true
                    FROM municipality AS m, category AS c
                    WHERE s.municipality_id = m.id
                      AND s.category_id = c.id
                      AND m.slug = :slug_comune
                      AND c.slug = :slug_categoria
                    """),
                {
                    "email_cifrata": email_cifrata,
                    "slug_comune": SLUG_COMUNE,
                    "slug_categoria": SLUG_CATEGORIA,
                },
            )
            if esito.rowcount != 1:
                raise RuntimeError(
                    "Configurazione non trovata: verificare comune e categoria."
                )
    finally:
        await motore.dispose()


asyncio.run(main())
```

Esecuzione:

```bash
cd api
CIVIC_DATABASE_URL="postgresql+asyncpg://civic_migrator:password@localhost:5432/civic" \
CIVIC_EMAIL_KEK="la-stessa-chiave-usata-dall-api" \
  uv run python nome_dello_script.py
```

La riga non memorizza il `key_id`. Se la KEK viene ruotata, gli indirizzi di
fallback già cifrati vanno ri-cifrati con la nuova chiave. La rotazione delle
chiavi è descritta in [`roadmap.md`](roadmap.md).

## 6. Creare l'account operatore

L'area `/admin` è riservata agli utenti con `is_operatore=true` e
`municipality_id` valorizzato. L'account va creato prima con la normale
registrazione, poi abilitato con una query eseguita dal ruolo migratore:

```sql
UPDATE "user"
SET is_operatore = true,
    municipality_id = (
        SELECT id FROM municipality WHERE slug = 'nome-comune'
    )
WHERE lower(nickname) = lower('nickname-operatore');
```

L'operatore vede nel pannello solo le segnalazioni del proprio comune, può
cambiare stato, aggiungere note interne e riprovare i dispatch falliti. Non vede
l'email dei cittadini.

L'isolamento multi-comune è applicato sia agli endpoint `/v1/admin/*` sia a
`PATCH /v1/reports/{id}/status`: un operatore di un altro comune riceve
`403 Forbidden` e la segnalazione non viene modificata.

## 7. Checklist di verifica

Esegui i controlli nell'ordine. Se un controllo fallisce, non passare al
successivo.

### 7.1 Confine e routing

```sql
SELECT
  slug,
  name,
  ST_IsValid(boundary::geometry) AS valido,
  ST_GeometryType(boundary::geometry) AS tipo,
  ST_Area(boundary::geography) / 1000000 AS area_km2,
  dispatch_mode,
  is_active
FROM municipality
WHERE slug = 'nome-comune';
```

Attesi: `valido=true`, `tipo=ST_MultiPolygon`, area plausibile,
`is_active=true`.

```bash
curl -s "http://localhost:8000/v1/geo/resolve?lat=45.05&lng=9.05" | jq
```

Attesi: `fuori_copertura=false`, `comune.slug` uguale allo slug importato. Se
`is_ambiguo=true`, verifica i confini sovrapposti e la priorità.

### 7.2 Configurazione delle categorie

```sql
SELECT
  c.slug,
  s.open311_service_code,
  s.fallback_active,
  s.fallback_email_enc IS NOT NULL AS ha_email_cifrata
FROM municipality_service AS s
JOIN category AS c ON c.id = s.category_id
JOIN municipality AS m ON m.id = s.municipality_id
WHERE m.slug = 'nome-comune'
ORDER BY c.slug;
```

Attesi: una riga per ogni categoria gestita. Per `open311` il service code non
è nullo. Per `email` `fallback_active=true` e `ha_email_cifrata=true`.

### 7.3 Chiave API Open311

```bash
test -n "$CIVIC_OPEN311_KEY_COMUNE_X" && echo "chiave presente"
```

La variabile deve essere visibile al processo del worker, non solo alla shell
da cui è stato avviato l'API. Dopo la modifica riavvia il worker.

### 7.4 Account operatore

```sql
SELECT u.nickname, u.is_operatore, m.slug AS comune
FROM "user" AS u
LEFT JOIN municipality AS m ON m.id = u.municipality_id
WHERE lower(u.nickname) = lower('nickname-operatore');
```

Attesi: `is_operatore=true` e `comune='nome-comune'`.

### 7.5 Test di pre-check

Apri il frontend, accedi con un account cittadino, seleziona un punto dentro
il confine e invia una segnalazione di prova. La pagina di dettaglio deve
mostrare la segnalazione e il comune assegnato.

Poi verifica il dispatch:

```sql
SELECT
  r.public_ref,
  r.dispatch_state,
  d.channel,
  d.attempt_no,
  d.status,
  d.http_status,
  d.error_code,
  d.error_detail_redacted,
  d.next_attempt_at,
  d.succeeded_at
FROM report AS r
LEFT JOIN report_dispatch AS d ON d.report_id = r.id
WHERE r.public_ref = 'CR-2026-000123'
ORDER BY d.created_at ASC, d.attempt_no ASC;
```

Attesi:

- `r.dispatch_state` diventa `sent_open311` o `sent_email`;
- esiste una riga `report_dispatch` con `status='succeeded'` e
  `succeeded_at` valorizzato;
- per Open311 è presente `provider_request_id` con l'identificativo restituito
  dal comune;
- per email è presente `provider_request_id` con il Message-ID del provider.

### 7.6 Log del worker

```bash
docker compose -f docker-compose.prod.yml logs -f worker
```

Cerca gli eventi `dispatch_open311_succeeded`, `dispatch_email_succeeded`,
`dispatch_open311_permanent_failure` o `dispatch_no_channel_configured`. Il
formato testuale predefinito stampa il nome dell'evento; i campi strutturati
sono nel record di log ma non nel formato. Per il dettaglio usa la query su
`report_dispatch`.

### 7.7 Pulizia del test

Non lasciare segnalazioni di prova sulla mappa pubblica. Nascondile con:

```sql
UPDATE report
SET visibility = CAST('hidden_by_moderation' AS report_visibility)
WHERE public_ref = 'CR-2026-000123';
```

Questa operazione non cancella lo storico del dispatch, che resta utile come
prova della configurazione.
