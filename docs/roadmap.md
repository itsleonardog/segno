# Roadmap

Questo documento elenca le prossime iterazioni consigliate. Le priorità
riflettono il valore per i comuni e i cittadini, i rischi di go-live e le
dipendenze tecniche. Non è un impegno di calendario: ogni voce va confermata
con il titolare del servizio prima di diventare un piano di lavoro.

## Stato attuale

La piattaforma copre oggi:

- registrazione, accesso, refresh token e profilo;
- mappa pubblica e dettaglio della segnalazione;
- creazione della segnalazione con risoluzione del comune dal punto;
- dispatch Open311 GeoReport v2 con retry e fallback email;
- sincronizzazione periodica dello stato Open311;
- pannello operatore con cambio stato, note interne e retry dei fallimenti;
- notifiche in-app e per email all'autore;
- export dei dati personali e cancellazione con anonimizzazione;
- retention di token, notifiche lette, record di idempotenza, dettagli dei
  dispatch e audit log;
- test di dominio, API, database, end-to-end e controlli di stile.

I limiti noti che condizionano le prossime iterazioni sono:

- l'invio email è uno stub: in ambienti diversi da `dev` non viene consegnato;
- comuni, confini e mapping delle categorie si gestiscono via database, non da
  interfaccia o API di piattaforma;
- il confine aggiornato non riassegna le segnalazioni esistenti;
- lo stato Open311 si legge con polling, non con notifiche del comune;
- l'interfaccia è solo in italiano;
- non esiste un'autenticazione forte per operatori e cittadini;
- l'`author_id` compare nelle risposte pubbliche dell'API, anche se
  l'interfaccia non lo mostra;
- le notifiche non lette non hanno un termine di conservazione automatico.

## Prerequisiti trasversali

Queste voci non sono una priorità di prodotto, ma vanno chiuse prima di un go-live
con comuni reali.

- Provider email reale, con verifica del dominio mittente, gestione dei bounce
  e delle suppressions. Senza questo, i comuni in modalità `email` e le
  notifiche agli autori non funzionano in produzione.
- API o interfaccia di piattaforma per creare comuni, importare confini,
  mappare categorie e abilitare operatori. Oggi la procedura è manuale ed è
  descritta in [`guida-aggiunta-comune.md`](guida-aggiunta-comune.md).
- Gestione delle chiavi con KMS o secret manager e rotazione della KEK. Oggi
  la cifratura usa una chiave singola e un `key_id` fisso.
- Log strutturati in JSON, metriche e alert su coda outbox, fallimenti
  permanenti e latenza dei dispatch.
- Backup e restore verificati, con prova periodica di ripristino.
- Valutazione d'impatto sulla protezione dei dati e nomina dei ruoli
  titolare/responsabile tra piattaforma e comuni.
- Rimozione o giustificazione dell'`author_id` dalle risposte pubbliche.
- Regola di conservazione per le notifiche non lette e per gli account
  inattivi.

## Priorità 1: integrazione SPID e CIE

**Obiettivo.** Offrire un'autenticazione forte agli operatori comunali e,
opzionalmente, ai cittadini che vogliono un'identità verificata.

**Perché.** L'area operatore oggi si basa su email e password. Per un servizio
pubblico che cambia lo stato di una segnalazione e scrive note visibili, SPID o
CIE riducono il rischio di account condivisi o credenziali deboli. Per i
cittadini l'accesso forte è facoltativo, ma utile per ridurre spam e abusi.

**Ambito minimo.**

- Integrazione OIDC o SAML con un Identity Provider SPID/CIE.
- Login operatore solo tramite identità forte, con associazione al comune
  gestita dall'amministratore di piattaforma.
- Collegamento tra identità digitale e account esistente, senza perdere lo
  storico delle segnalazioni.
- Audit dei login e delle operazioni sensibili.
- Fallback documentato per operatori che non hanno ancora un'identità
  digitale, con deroga esplicita e temporanea.

**Criteri di accettazione.**

- Un operatore accede all'area `/admin` con SPID o CIE e vede solo il proprio
  comune.
- Un utente senza identità forte può continuare a usare il flusso attuale, se
  il titolare lo consente.
- La revoca dell'identità digitale blocca l'accesso senza cancellare i dati.
- I test coprono associazione, revoca e tentativo di accesso a un altro
  comune.

**Dipendenze.** Convenzione con il gestore dell'identità, definizione degli
attributi, valutazione GDPR, aggiornamento dell'informativa.

## Priorità 2: app mobile

**Obiettivo.** Consentire la segnalazione da smartphone con un'app dedicata,
riusando le API esistenti.

**Perché.** La maggior parte delle segnalazioni nasce sul posto. Un'app può
semplificare l'acquisizione della posizione, il caricamento di una foto e le
notifiche push. Il frontend web resta il canale principale per la consultazione
e per i comuni.

**Ambito minimo.**

- App React Native o Flutter con login, mappa, creazione segnalazione,
  dettaglio e notifiche.
- Archiviazione dei token nel Keychain o nel Keystore, non in storage non
  protetto.
- Gestione del refresh token e logout remoto.
- Bozza locale della segnalazione in caso di rete assente, con invio
  idempotente al ritorno della connessione.
- Notifiche push opzionali, con preferenza esplicita.

**Criteri di accettazione.**

- L'app crea una segnalazione con lo stesso contratto di `/v1/reports`.
- Il token non è mai scritto in chiaro su storage non protetto.
- Un invio ripetuto per un errore di rete non crea duplicati.
- Le notifiche push possono essere disattivate dall'utente.

**Dipendenze.** API versionate, gestione delle foto lato storage, provider push,
pubblicazione sugli store e aggiornamento dell'informativa.

## Priorità 3: integrazione bidirezionale con i comuni

**Obiettivo.** Ricevere dal comune gli aggiornamenti di stato tramite webhook,
invece di interrogare periodicamente l'endpoint Open311.

**Perché.** Il polling introduce latenza e carico inutile. Un webhook firmato
riduce il ritardo tra il cambio di stato nel gestionale del comune e la
visualizzazione pubblica, e permette di ricevere eventi che Open311 non espone
in modo uniforme.

**Ambito minimo.**

- Endpoint di ricezione per ciascun comune, con segreto di firma distinto.
- Verifica della firma, timestamp e idempotenza dell'evento.
- Mappatura degli stati esterni su `open_status`, `in_progress`, `resolved`,
  `closed`, con scarto esplicito degli stati non riconosciuti.
- Registrazione dell'evento in `report_status_event` con attore
  `open311_sync` o un nuovo attore dedicato.
- Retry e dead letter queue per gli eventi non consegnati.
- Polling di fallback per i comuni che non supportano i webhook.

**Criteri di accettazione.**

- Un evento firmato aggiorna lo stato della segnalazione una sola volta.
- Una firma non valida viene rifiutata e registrata senza modificare i dati.
- Un evento duplicato non produce due cambi di stato.
- Un comune senza webhook continua a funzionare con il polling.

**Dipendenze.** Accordo tecnico con i fornitori dei gestionali comunali,
definizione del formato dell'evento, gestione dei segreti per comune.

## Priorità 4: internazionalizzazione

**Obiettivo.** Rendere utilizzabile la piattaforma in inglese, per turisti e
cittadini stranieri, e predisporre altre lingue.

**Perché.** Le segnalazioni urbane non riguardano solo i residenti. Una
interfaccia inglese riduce la barriera per chi non parla italiano e rende il
servizio più accessibile. Le categorie hanno già `name_i18n` con italiano e
inglese; manca l'uso sistematico della lingua nella UI, nelle email e nei
messaggi di errore.

**Ambito minimo.**

- Estrazione delle stringhe della UI in un catalogo di traduzioni.
- Selettore di lingua e salvataggio della preferenza in `user.locale`.
- Traduzione di categorie, stati, messaggi di errore e testi email.
- Lingua negoziata dalla richiesta, con italiano come predefinito.
- Documenti legali tradotti o con una versione inglese chiaramente
  identificata.

**Criteri di accettazione.**

- Un utente con `locale='en'` vede la UI, le categorie e le email in inglese.
- Le stringhe non tradotte ricadono sull'italiano senza rompere il layout.
- Le date e i numeri rispettano la lingua scelta.
- I test coprono almeno italiano e inglese.

**Dipendenze.** Catalogo di traduzioni, revisione dei testi legali, decisione
sulle lingue ufficiali del servizio.

## Priorità 5: analytics e dashboard per l'assessore

**Obiettivo.** Fornire una vista aggregata su tempi di risoluzione, categorie
più frequenti, carico per ufficio e rispetto degli SLA.

**Perché.** I comuni hanno bisogno di dati per programmare gli interventi e
rendicontare il servizio. Una dashboard sola lettura, con dati aggregati,
riduce le richieste manuali e rende misurabile il miglioramento.

**Ambito minimo.**

- Metriche aggregate per comune e periodo: segnalazioni aperte, chiuse,
  tempo medio e mediano di risoluzione, distribuzione per categoria e stato.
- Rispetto degli SLA quando `sla_days` è configurato.
- Esportazione CSV o JSON dei dati aggregati.
- Ruolo dedicato con accesso sola lettura, distinto dall'operatore.
- Esclusione dei dati personali e delle segnalazioni nascoste dalle metriche
  pubbliche.

**Criteri di accettazione.**

- La dashboard non espone email, nickname o coordinate precise.
- I totali coincidono con le query di riferimento su `report` e
  `report_status_event`.
- Il periodo e il comune sono filtri obbligatori o espliciti.
- L'esportazione è riproducibile e documentata.

**Dipendenze.** Definizione degli indicatori con il titolare, eventuale
estensione del modello dati per gli SLA, ruolo di sola lettura.

## Ordine consigliato

1. Chiudere i prerequisiti trasversali, a partire dal provider email e dalla
   gestione dei comuni.
2. SPID/CIE per gli operatori.
3. Webhook bidirezionali, perché riducono il carico operativo e migliorano la
   qualità dei dati.
4. Internazionalizzazione, se il territorio o il flusso turistico la
   giustificano.
5. App mobile, dopo la stabilizzazione delle API e delle notifiche push.
6. Dashboard analytics, quando i dati sono sufficientemente puliti e
   omogenei tra comuni.

L'ordine può cambiare se un comune finanzia una voce specifica. In quel caso
la voce finanziata va comunque confrontata con i prerequisiti tecnici e con i
rischi GDPR.
