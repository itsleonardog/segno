# Informativa privacy (bozza)

Questa è una bozza di lavoro. Prima della pubblicazione va validata dal
titolare del trattamento e dal responsabile della protezione dei dati. I
segnaposto tra parentesi quadre vanno sostituiti con i dati effettivi. La
versione pubblicata deve essere coerente con il valore di
`privacy_policy_version` inviato alla registrazione.

## Informativa breve per la registrazione

**Titolare del trattamento.** [Comune di ...], [indirizzo], [email privacy].

**Finalità.** Creare e gestire l'account, pubblicare la segnalazione, inviarla
al comune competente e inviarti aggiornamenti sullo stato.

**Dati trattati.** Indirizzo email, nickname, password, posizione geografica,
testo e categoria della segnalazione, stato e cronologia della segnalazione,
notifiche.

**La segnalazione è pubblica.** Titolo, descrizione, categoria, stato,
cronologia e punto sulla mappa sono visibili a chiunque. Non inserire dati
personali tuoi o di altre persone nel testo. Scegli un punto vicino al problema
e non la tua abitazione, se non è necessario.

**Email.** L'indirizzo email è cifrato e non viene mai mostrato ad altri utenti
né trasmesso al comune. Il comune riceve il contenuto della segnalazione, la
categoria, la posizione e il riferimento pubblico, non la tua email.

**Base giuridica.** Esecuzione del servizio per account e notifiche; interesse
pubblico per la pubblicazione della segnalazione e l'invio al comune.

**Diritti.** Puoi scaricare i tuoi dati e cancellare l'account dalla pagina
profilo. La cancellazione anonimizza l'account e scollega le segnalazioni dal
tuo nome, ma le segnalazioni pubbliche restano visibili per finalità di
trasparenza civica.

**Conservazione.** L'account è conservato fino alla cancellazione. Le
segnalazioni pubbliche sono conservate per finalità di trasparenza civica. Gli
altri dati seguono i termini indicati nell'informativa estesa.

**Reclamo.** Puoi proporre reclamo al Garante per la protezione dei dati
personali.

## Informativa estesa

### 1. Titolare del trattamento e contatti

Il titolare del trattamento è [Comune di ...], con sede in [indirizzo], nella
persona del [legale rappresentante o dirigente delegato].

Contatti:

- email per la privacy: [email privacy];
- responsabile della protezione dei dati (DPO), se nominato: [nome e email];
- indirizzo postale: [indirizzo].

La piattaforma [denominazione] è gestita da [fornitore]. I ruoli di titolare,
responsabile e contitolare tra il comune e il fornitore sono definiti nel
contratto e nel registro dei trattamenti.

### 2. Quali dati trattiamo

**Dati dell'account.**

- indirizzo email;
- nickname scelto dall'utente;
- password, conservata solo come hash Argon2id;
- lingua preferita;
- data di creazione, data di verifica dell'email, ultimo accesso;
- stato dell'account;
- eventuale ruolo di operatore e comune associato.

Non chiediamo nome, cognome, numero di telefono, codice fiscale, data di
nascita o indirizzo di residenza. Non è previsto il caricamento di fotografie
nella versione attuale.

**Dati della segnalazione.**

- titolo e descrizione;
- categoria;
- coordinate del punto scelto sulla mappa;
- eventuale indirizzo testuale;
- stato e cronologia degli eventi;
- riferimento pubblico nel formato `CR-YYYY-NNNNNN`;
- note pubbliche del comune.

**Dati delle notifiche.**

- tipo e canale della notifica;
- contenuto della notifica;
- data di invio e di lettura.

**Dati tecnici di sessione.**

- hash del refresh token, famiglia di appartenenza e scadenza;
- riepilogo del dispositivo o browser (user agent) associato alla sessione;
- indirizzo di rete e dati di sicurezza gestiti dall'infrastruttura secondo le
  politiche del fornitore.

**Dati di dispatch.**

- canale usato, numero di tentativi, esito, codice HTTP e dettaglio dell'errore
  già ripulito da dati personali;
- identificativo restituito dal servizio del comune.

**Log.**

I log applicativi contengono identificativi tecnici, come `request_id`,
`tenant_id` e un identificativo pseudonimo dell'utente. Non contengono
l'indirizzo email, i token, le chiavi API o le coordinate precise.

### 3. Finalità e basi giuridiche

Trattiamo i dati per queste finalità:

| Finalità | Base giuridica |
|---|---|
| Creare e gestire l'account, autenticare l'utente, gestire le sessioni | esecuzione del servizio, art. 6, par. 1, lett. b, GDPR |
| Pubblicare la segnalazione e mostrarne lo stato | interesse pubblico o esercizio di pubblici poteri, art. 6, par. 1, lett. e, GDPR |
| Inviare la segnalazione al comune competente e gestire il dispatch | interesse pubblico o esecuzione del servizio, da formalizzare nel contratto con il comune |
| Inviare notifiche di aggiornamento all'autore | esecuzione del servizio; la disattivazione può essere richiesta ai contatti del titolare |
| Sicurezza, prevenzione di abusi, audit e adempimenti di legge | obblighi di legge e legittimo interesse alla sicurezza, art. 6, par. 1, lett. c e f, GDPR |

La base giuridica per la pubblicazione e per l'invio al comune va confermata
dal comune titolare del servizio pubblico. Non è un consenso implicito nella
registrazione.

### 4. Natura del conferimento

Il conferimento dei dati dell'account è necessario per registrarsi e inviare
una segnalazione. Senza email e nickname non è possibile creare l'account.
Senza la posizione non è possibile individuare il comune competente.

Puoi consultare la mappa e le segnalazioni pubbliche senza registrarti.

### 5. Cosa è pubblico e cosa non lo è

Quando invii una segnalazione, rendi pubblici:

- titolo e descrizione;
- categoria;
- stato e cronologia degli eventi pubblici;
- punto sulla mappa e eventuale indirizzo testuale;
- riferimento pubblico;
- note pubbliche inserite dal comune.

La segnalazione è visibile a chiunque acceda alla piattaforma e può essere
indicizzata dai motori di ricerca. Non inserire nel testo dati personali tuoi o
di altre persone, numeri di documento, targhe, dati sanitari o informazioni che
non vuoi rendere pubbliche.

Non sono pubblici:

- il tuo indirizzo email;
- la tua password e i token di sessione;
- le note interne del comune;
- i dati tecnici di dispatch e di sicurezza.

L'indirizzo email non viene mai mostrato ad altri utenti e non viene trasmesso
al comune. Il comune riceve il contenuto della segnalazione, la categoria, la
posizione e il riferimento pubblico. Le note pubbliche sono aggiunte dal comune
e restano visibili nella cronologia della segnalazione. L'eventuale fallback
email del comune è un indirizzo di protocollo del comune, non il tuo.

Nella versione attuale la pagina pubblica della segnalazione non mostra il
nickname dell'autore. Le risposte tecniche dell'API possono contenere un
identificativo pseudonimo dell'autore, necessario per il funzionamento del
servizio; non contengono l'email.

### 6. Destinatari dei dati

I dati possono essere comunicati a:

- il comune competente, per la presa in carico e la lavorazione della
  segnalazione;
- il fornitore della piattaforma e i suoi subfornitori tecnici, per hosting,
  manutenzione, sicurezza e supporto;
- il fornitore del servizio email, quando configurato, per l'invio delle
  comunicazioni di servizio;
- il fornitore delle mappe, per la visualizzazione delle tile nella pagina;
- autorità pubbliche, quando previsto dalla legge.

I dati non sono venduti e non sono usati per marketing o profilazione
commerciale.

Il browser dell'utente carica le tile cartografiche da OpenStreetMap. Il
fornitore delle tile può vedere l'indirizzo IP e i parametri tecnici della
richiesta secondo la propria informativa.

### 7. Trasferimenti fuori dallo Spazio economico europeo

Se un fornitore tratta dati fuori dallo Spazio economico europeo, il
trasferimento avviene sulla base di clausole contrattuali standard o di un'altra
garanzia prevista dal GDPR, dopo una valutazione del rischio. I fornitori
coinvolti e le garanzie adottate sono indicati nel registro dei trattamenti.

### 8. Tempo di conservazione

| Dato | Periodo previsto | Cosa succede alla scadenza |
|---|---|---|
| Account e email cifrata | fino alla cancellazione; anonimizzazione dopo 24 mesi di inattività, con avviso preventivo, se attivata dal titolare | cancellazione dei recapiti e anonimizzazione |
| Segnalazioni pubbliche | conservate per finalità di trasparenza civica | resta il contenuto, viene rimosso il collegamento all'autore |
| Eventi di stato | conservati con la segnalazione | restano come cronologia pubblica o interna |
| Note interne | conservate con la segnalazione | restano visibili solo agli operatori |
| Notifiche lette | 12 mesi dalla lettura | cancellazione |
| Notifiche non lette | fino a 12 mesi dalla creazione o al termine definito dal titolare | cancellazione |
| Refresh token | durata della sessione, al massimo 30 giorni | cancellazione o revoca |
| Token di verifica email | 24 ore | cancellazione |
| Token di reset password | 1 ora | cancellazione |
| Record di idempotenza | 24 ore | cancellazione |
| Dettagli dei dispatch | 24 mesi per rendicontazione verso il comune | aggregazione o cancellazione |
| Log applicativi | 30-90 giorni, secondo la configurazione | cancellazione |
| Audit log | 24 mesi, salvo obblighi diversi | cancellazione |

I termini sono indicativi e vanno confermati nel registro dei trattamenti. Se
la legge impone un termine diverso, prevale il termine di legge.

### 9. Diritti dell'interessato

Hai diritto di:

- accedere ai tuoi dati e ottenere una copia;
- rettificare i dati inesatti, per esempio il nickname;
- cancellare l'account;
- limitare o opporti al trattamento, nei casi previsti dal GDPR;
- ricevere i dati in un formato strutturato e leggibile;
- proporre reclamo al Garante per la protezione dei dati personali.

**Accesso ed export.** Dalla pagina profilo puoi usare "Scarica i tuoi dati".
Il file JSON contiene profilo, segnalazioni, eventi di stato e notifiche.

**Cancellazione.** Dalla pagina profilo puoi usare "Elimina account" e
confermare con la password. La cancellazione:

- elimina email, password e recapiti dall'account;
- sostituisce il nickname con un identificativo pseudonimo;
- scollega le segnalazioni dall'autore;
- revoca le sessioni attive.

Le segnalazioni pubbliche restano visibili senza il collegamento all'autore,
per finalità di trasparenza civica. La cronologia degli eventi di stato può
conservare un identificativo pseudonimo dell'autore, perché è un registro
append-only necessario alla trasparenza del procedimento.

Per esercitare gli altri diritti scrivi a [email privacy]. Il titolare risponde
di norma entro un mese.

### 10. Misure di sicurezza

Adottiamo misure tecniche e organizzative proporzionate al rischio:

- TLS per le comunicazioni;
- cifratura AES-256-GCM dell'email a riposo e degli indirizzi di fallback;
- hash Argon2id delle password;
- token di accesso a breve durata e refresh token con rotazione e revoca;
- isolamento dei dati per comune con Row Level Security su PostgreSQL;
- minimo privilegio dei ruoli applicativi;
- log senza email, token, chiavi API o coordinate precise;
- limiti di frequenza sulle operazioni sensibili;
- backup e procedure di ripristino.

Nessuna misura è infallibile. In caso di violazione dei dati personali, il
titolare adotta la procedura prevista dagli articoli 33 e 34 del GDPR.

### 11. Minori

Il servizio non è destinato a minori senza l'autorizzazione di chi esercita la
responsabilità genitoriale. Non raccogliamo consapevolmente dati di minori. Se
ritieni che siano stati inseriti dati di un minore, contatta il titolare per la
rimozione.

### 12. Modifiche all'informativa

L'informativa è versionata. La versione accettata alla registrazione è
conservata nell'account. Le modifiche sostanziali sono comunicate agli utenti
con un avviso e, se necessario, con una nuova richiesta di presa visione.

Versione: [versione]. Data: [data].

### 13. Reclamo

Puoi proporre reclamo al Garante per la protezione dei dati personali, Piazza
Venezia 11, 00187 Roma, oppure tramite il sito del Garante. Puoi anche rivolgerti
all'autorità di controllo del tuo Stato di residenza.

## Note interne per il titolare

Questa sezione non fa parte dell'informativa pubblicata e va rimossa prima
della pubblicazione.

**Copertura rispetto all'implementazione.**

- Export: `GET /v1/me/export`, disponibile dalla pagina profilo.
- Cancellazione: `DELETE /v1/me` con password; l'account viene anonimizzato e
  l'autore viene scollegato dalle segnalazioni.
- Email cifrata: `user.email_enc` con AES-256-GCM e `user.email_lookup_hash`
  come HMAC-SHA256 per il login. La chiave è `CIVIC_EMAIL_KEK`.
- Indirizzi di fallback dei comuni: `municipality_service.fallback_email_enc`,
  cifrati con la stessa KEK.
- Notifiche lette: il job di retention le elimina dopo 12 mesi.
- Token scaduti e record di idempotenza scaduti: eliminati dal job di
  retention.
- Dettagli dei dispatch e audit log: eliminati dal job di retention dopo 24
  mesi.
- Il job di retention non copre ancora gli account inattivi e le notifiche non
  lette; i relativi termini restano obiettivi da implementare prima del
  go-live.
- Log: il formato predefinito del worker non stampa i campi `extra`; per
  rendere operativi gli alert sui dettagli serve un formatter JSON.

**Punti da chiudere prima della pubblicazione.**

- Sostituire tutti i segnaposto e validare il testo con il DPO.
- Formalizzare la base giuridica e i ruoli titolare/responsabile/contitolare
  nel contratto con i comuni.
- Attivare un provider email reale: con `CIVIC_ENV` diverso da `dev` l'invio è
  ancora uno stub e le notifiche non vengono consegnate.
- Definire e attivare la regola di anonimizzazione degli account inattivi dopo
  24 mesi.
- Definire un termine per le notifiche non lette. Oggi il job elimina solo le
  notifiche lette dopo 12 mesi; le notifiche non lette e quelle collegate a un
  account cancellato restano nel sistema. La cancellazione dell'account non le
  rimuove.
- Verificare se l'`author_id` nelle risposte pubbliche dell'API è necessario;
  se non lo è, rimuoverlo o documentarne la natura pseudonima.
- Verificare la gestione di `photo_url`: oggi il campo è accettato dalla
  richiesta ma non è mostrato nella pagina pubblica e non è previsto un
  caricamento immagini.
- Aggiornare `privacy_policy_version` nel frontend quando cambia il testo.
- Verificare i tempi di conservazione di log, audit log e dettagli di dispatch
  con l'infrastruttura effettiva.
- Nominare il DPO, se l'attività lo richiede, e pubblicare i contatti.
