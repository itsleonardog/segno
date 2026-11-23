# Gestione dei dispatch falliti

Questa guida spiega come leggere un fallimento di invio, distinguere un errore
temporaneo da un errore di configurazione e forzare un nuovo tentativo. Il
punto di partenza è il pannello operatore, sezione "Fallimenti di invio", o
l'endpoint `GET /v1/admin/dispatch-failures`.

Il pannello mostra solo i dispatch in stato `failed_permanent`, cioè quelli che
non verranno ritentati automaticamente. Un dispatch ancora in backoff non
compare nell'elenco: il worker lo riproverà da solo.

## 1. Cosa contiene un fallimento

Ogni riga di `report_dispatch` descrive un tentativo:

| Campo | Significato |
|---|---|
| `channel` | `open311` oppure `email` |
| `attempt_no` | numero progressivo del tentativo per canale |
| `status` | `queued`, `sending`, `succeeded`, `failed_retryable`, `failed_permanent`, `suppressed` |
| `http_status` | codice HTTP restituito dal comune, se presente |
| `error_code` | categoria dell'errore, per esempio `permanente`, `ritentabile`, `ambiguo` o il nome dell'eccezione email |
| `error_detail_redacted` | dettaglio già ripulito da dati personali e segreti |
| `next_attempt_at` | prossimo tentativo pianificato, se il guasto è ritentabile |
| `succeeded_at` | istante del successo |
| `provider_request_id` | `service_request_id` Open311 oppure Message-ID email |

Il campo `report.dispatch_state` riassume lo stato della segnalazione:
`routed` durante i tentativi, `sent_open311` o `sent_email` dopo il successo,
`failed` dopo un fallimento permanente o a finestra di retry esaurita.

## 2. Errore di rete o errore di configurazione

La classificazione è nel dominio, in
[`../api/app/dominio/dispatch.py`](../api/app/dominio/dispatch.py). Il worker
applica questa regola:

| Situazione | Esito | Cosa fare |
|---|---|---|
| Timeout, DNS non risolto, connessione rifiutata | ritentabile | attendere il retry automatico; verificare rete, DNS e disponibilità del comune |
| HTTP 429 | ritentabile | attendere il retry automatico; verificare i limiti del comune |
| HTTP 5xx | ritentabile | attendere il retry automatico; il comune è temporaneamente indisponibile |
| HTTP 400 o 422 | permanente | correggere `service_code`, `open311_extra_fields` o il payload |
| HTTP 401 o 403 | permanente | correggere la chiave API o i permessi del comune |
| HTTP 2xx senza `service_request_id` | ambiguo | verificare se il comune ha creato la richiesta; se previsto, scatta il fallback email |
| Risposta non JSON | ambiguo | come sopra: non prova l'avvenuta creazione |
| Eccezione non di trasporto | permanente | leggere il tipo di errore e correggere la configurazione |
| Canale assente, endpoint assente, fallback assente | permanente | completare `municipality` o `municipality_service` |

I tentativi Open311 seguono un backoff di 1, 5, 15 e 60 minuti. Il worker
esegue al massimo cinque tentativi: dopo l'ultimo, il dispatch diventa
`failed_permanent`. Lo stesso schema si applica alle email in errore.

Un errore di rete non si corregge con un nuovo tentativo manuale: il worker lo
sta già gestendo. Un errore di configurazione non si corregge con un nuovo
tentativo: va prima modificata la configurazione.

## 3. Leggere il dettaglio nel pannello

1. Apri `/admin` con un account operatore del comune.
2. Individua la segnalazione nella sezione "Fallimenti di invio".
3. Apri il dettaglio della segnalazione e leggi "Storico invii".
4. Annota `channel`, `attempt_no`, `status` e `error_code`.

Il pannello mostra canale, numero del tentativo, stato, data e codice errore.
Il dettaglio ripulito (`error_detail_redacted`) e il codice HTTP sono presenti
nella risposta API e nella tabella `report_dispatch`, ma non sono visualizzati
nel pannello. Per leggerli usa la query della sezione successiva.

## 4. Ispezionare il database

Sostituisci il riferimento pubblico con quello della segnalazione.

```sql
SELECT
  r.id,
  r.public_ref,
  r.dispatch_state,
  d.channel,
  d.attempt_no,
  d.status,
  d.http_status,
  d.error_code,
  d.error_detail_redacted,
  d.next_attempt_at,
  d.succeeded_at,
  d.created_at
FROM report AS r
LEFT JOIN report_dispatch AS d ON d.report_id = r.id
WHERE r.public_ref = 'CR-2026-000123'
ORDER BY d.created_at ASC, d.attempt_no ASC;
```

Per capire se l'evento è ancora in coda:

```sql
SELECT
  e.id,
  e.event_type,
  e.attempts,
  e.last_error,
  e.processed_at,
  e.created_at
FROM outbox_event AS e
WHERE e.aggregate_id = (
  SELECT id FROM report WHERE public_ref = 'CR-2026-000123'
)
ORDER BY e.id DESC;
```

Se `processed_at` è nullo e `attempts` continua a crescere, il worker sta
riprovando. Se `processed_at` è valorizzato e il dispatch è
`failed_permanent`, il ciclo è concluso e serve un intervento.

## 5. Leggere i log del worker

In produzione:

```bash
docker compose -f docker-compose.prod.yml logs -f worker
```

In sviluppo:

```bash
cd api
uv run python -m app.worker
```

Eventi utili:

| Evento | Significato |
|---|---|
| `dispatch_open311_succeeded` | invio Open311 riuscito |
| `dispatch_open311_permanent_failure` | errore non ritentabile o finestra esaurita |
| `dispatch_retry_scheduled` | nuovo tentativo pianificato |
| `dispatch_email_fallback_started` | fallback email avviato |
| `dispatch_email_succeeded` | email al comune consegnata |
| `dispatch_email_failed` | invio email fallito |
| `dispatch_no_channel_configured` | nessuna configurazione utile per la categoria |
| `dispatch_municipality_missing` | comune assente o `is_active=false` |
| `dispatch_skipped_no_municipality` | segnalazione fuori copertura: non è un errore |
| `open311_transport_error` | errore di rete verso l'endpoint |
| `open311_response_received` | risposta HTTP ricevuta dal comune |
| `open311_response_not_json` | risposta non interpretabile |
| `outbox_event_failed` | eccezione imprevista durante l'elaborazione |
| `outbox_event_retry_scheduled` | evento lasciato in coda per un retry |
| `worker_batch_failed` | errore database nel ciclo del worker |
| `open311_sync_status_not_mapped` | stato esterno non riconosciuto dalla sincronizzazione |

Il formato testuale predefinito del worker stampa il nome dell'evento. I campi
strutturati (`report_id`, `municipality_id`, `http_status`, `causa`) sono
presenti nel record di log ma non nel formato. Per un'analisi puntuale usa le
query su `report_dispatch` e `outbox_event`, oppure configura un formatter JSON
nel processo del worker.

## 6. Casi frequenti

### `dispatch_no_channel_configured`

Manca una riga in `municipality_service` per la categoria, oppure la modalità
non ha i campi necessari. Verifica:

```sql
SELECT c.slug, s.open311_service_code, s.fallback_active,
       s.fallback_email_enc IS NOT NULL AS ha_email
FROM municipality_service AS s
JOIN category AS c ON c.id = s.category_id
JOIN municipality AS m ON m.id = s.municipality_id
WHERE m.slug = 'nome-comune'
ORDER BY c.slug;
```

Per `open311` serve `open311_service_code`. Per `email` serve
`fallback_active=true` e `fallback_email_enc` non nullo.

### Errore 401 o 403 su Open311

La chiave API è assente, scaduta o non abilitata. Controlla che
`municipality.open311_api_key_ref` corrisponda alla variabile d'ambiente
`CIVIC_OPEN311_KEY_<RIFERIMENTO>` e che il worker sia stato riavviato dopo la
modifica.

### Errore 400 o 422 su Open311

Il payload non è accettato: `service_code` inesistente, campo obbligatorio
mancante o `open311_extra_fields` non valido. Correggi la riga di
`municipality_service` e riprova.

### Errore di rete

Controlla che l'endpoint sia raggiungibile dal container del worker. Un DNS
non risolto o un timeout non si risolvono con un retry manuale: il worker sta
già riprovando. Intervieni sull'infrastruttura o sull'endpoint del comune.

### `dispatch_email_provider_not_configured`

Nell'implementazione attuale l'invio email è uno stub. Con `CIVIC_ENV`
diverso da `dev`, il provider non è configurato e l'invio fallisce con questo
evento. Il dispatch email non è quindi operativo in produzione finché non viene
collegato un provider reale. La voce è riportata in
[`roadmap.md`](roadmap.md).

### `dispatch_municipality_missing`

La segnalazione punta a un comune non più presente o con `is_active=false`.
Riattiva il comune o verifica l'identificativo. Non è un errore del cittadino.

### `dispatch_skipped_no_municipality`

La segnalazione è fuori copertura: `municipality_id` è nullo per scelta. Non
esiste un dispatch da fare. La segnalazione resta pubblica e va gestita
manualmente secondo la procedura del titolare.

## 7. Forzare un nuovo tentativo

### Dal pannello

Nella sezione "Fallimenti di invio" premi "Riprova". L'operazione accoda un
evento `report.dispatch_retry` e restituisce `202 Accepted`. Il worker lo
elabora al ciclo successivo.

### Da API

```bash
curl -X POST \
  "http://localhost:8000/v1/admin/reports/REPORT_ID/dispatch/retry" \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

La risposta contiene `event_id`. Il nuovo tentativo non cancella lo storico: la
riga precedente resta in `report_dispatch` per rendicontazione.

### Prima di riprovare

- Correggi la causa. Un retry su una configurazione ancora errata produce solo
  un nuovo fallimento.
- Se l'errore era ambiguo (timeout o 2xx senza identificativo), verifica sul
  sistema del comune se esiste già una richiesta con
  `external_reference=public_ref`. Un retry può creare un duplicato.
- Non forzare il retry mentre `next_attempt_at` è nel futuro: il worker sta già
  gestendo il backoff.

## 8. Verifica dopo il retry

```sql
SELECT d.channel, d.attempt_no, d.status, d.http_status, d.error_code,
       d.next_attempt_at, d.succeeded_at
FROM report_dispatch AS d
JOIN report AS r ON r.id = d.report_id
WHERE r.public_ref = 'CR-2026-000123'
ORDER BY d.created_at DESC;
```

Attesi: una nuova riga con `attempt_no` maggiore, `status='succeeded'` e
`report.dispatch_state` aggiornato a `sent_open311` o `sent_email`.

Se il nuovo tentativo fallisce di nuovo, il problema è ancora nella
configurazione o nel servizio esterno. Non ripetere il retry senza aver
cambiato qualcosa.
