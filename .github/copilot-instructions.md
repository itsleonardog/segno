# Istruzioni per lo stile del codice

Queste regole valgono per tutto il repository. In caso di conflitto con le
preferenze di default, prevalgono queste. La fonte di verità estesa è in
`docs/house-style.md`; questo file ne è l'estratto operativo.

## Lingua e naming

- Il dominio è in italiano: `segnalazione`, `comune`, `categoria`, `stato`,
  `dispatch`, `confine`, `ambiguita`. I termini tecnici standard restano in
  inglese: `report` è accettato solo se è il nome dell'entità nel modello dati,
  altrimenti si usa `segnalazione`.
- I nomi delle variabili e delle funzioni descrivono il dominio, non il tipo.
  Vietati: `data`, `result`, `item`, `obj`, `handle`, `process`, `manage`,
  `doSomething`, `utils`, `helpers`, `misc`.
  Preferiti: `segnalazione`, `comune_competente`, `stato_precedente`,
  `risolvi_confine`, `marca_come_risolta`.
- Le funzioni si chiamano con un verbo che dice cosa fanno: `risolvi_comune`,
  `invia_dispatch`, `anonimizza_autore`, `valida_confine`.
- I booleani si chiamano con `is_`, `has_`, `puo_`, `deve_`: `is_attivo`,
  `has_foto`, `puo_essere_modificata`, `deve_notificare`.
- Le costanti sono in maiuscolo con underscore: `MAX_TENTATIVI_DISPATCH`,
  `FINESTRA_DEDUPLICA_ORE`.
- I nomi dei file seguono lo stesso criterio: `risoluzione_confine.py`,
  `invio_dispatch.py`, non `helpers.py` o `service.py`.

## Commenti

- Nessun commento che narra l'ovvio. `# incrementa il contatore` sopra
  `contatore += 1` è vietato.
- I commenti spiegano il *perché*, non il *cosa*. Ammessi quando c'è una
  scelta non ovvia, un compromesso, un riferimento a un requisito o a un bug
  noto: `# ST_Covers e non ST_Contains: un punto sul bordo va assegnato`.
- Niente commenti "di sezione" che ripetono la firma della funzione.
- Niente `TODO` senza un riferimento a un problema tracciato.

## Docstring

- Solo sulle funzioni e classi pubbliche dei moduli di dominio. Una riga,
  in italiano, che dice cosa fa e cosa restituisce. Niente elenchi di
  parametri ridondanti con la firma, niente esempi decorativi.
- Vietate le docstring su funzioni banali, sui test, sui DTO.

## Struttura

- Un modulo per responsabilità di dominio. Nessun file "contenitore" che
  raccoglie funzioni non correlate.
- Ordine fisso nei moduli Python: import, costanti, tipi, funzioni pure,
  classi di servizio, funzioni di I/O. Ordine fisso nei moduli TypeScript:
  import, tipi, costanti, componenti o funzioni, export.
- Le dipendenze si iniettano, non si importano dentro le funzioni, tranne
  per i logger e i client HTTP già configurati a livello di modulo.

## Gestione degli errori

- Niente difensivismo sistematico. Un `try/except` o un `try/catch` esiste
  solo se c'è un'azione concreta da fare nell'handler: log con contesto,
  retry, fallback, trasformazione in errore di dominio.
- Gli errori destinati all'utente sono in italiano e in formato RFC 7807
  (`type`, `title`, `status`, `detail`, `instance`). Il `detail` non espone
  dettagli interni.
- Gli errori nei log sono in inglese, strutturati in JSON, senza PII.
- I messaggi di errore sono specifici. Vietato `Errore generico`,
  `Qualcosa è andato storto`, `Errore imprevisto`.

## Log

- Strutturati, con `request_id`, `tenant_id`, `user_id` pseudonimo.
- Mai email, token, API key, coordinate precise dell'utente nei log.
- Livello e messaggio scelti con intenzione: `info` per gli eventi di
  dominio, `warning` per i degradi recuperabili, `error` per quelli che
  richiedono intervento.

## Test

- I test descrivono il comportamento osservabile, non l'implementazione.
  Vietati i test che verificano che una funzione interna sia stata chiamata
  con certi argomenti, se non è un confine di integrazione.
- Nome del test in italiano, forma `test_<comportamento>_<condizione>`:
  `test_crea_segnalazione_fuori_copertura_resta_pubblica`.
- Un test per ogni criterio di convalida del piano, non un test per ogni
  riga di codice.

## Messaggi all'utente

- In italiano, sobri, senza punti esclamativi, senza emoji, senza "Ciao!".
- Dicono cosa è successo e cosa può fare l'utente, in quest'ordine.
- Nessun gergo tecnico: "il comune competente non è ancora coperto", non
  "out_of_jurisdiction".

## Documentazione e README

- Niente emoji, niente intestazioni decorative, niente elenchi puntati usati
  come riempitivo.
- Il README dice cosa fa il progetto, come si avvia, come si testa, come si
  contribuisce. Niente sezioni "Features" con checklist.
- I documenti di architettura stanno in `docs/` e sono versionati.

## Pattern vietati esplicitamente

- Funzioni che restituiscono `None` in caso di errore e un valore in caso di
  successo: si usa un'eccezione di dominio o un risultato esplicito.
- `print` in produzione: si usa il logger configurato.
- Accesso diretto al database dal frontend o dai componenti UI.
- Chiamate HTTP sincrone verso servizi esterni nel ciclo di richiesta.
- `except Exception` senza rilancio o log contestualizzato.
- Codice commentato lasciato in repository.
- Nomi di variabili con numeri progressivi: `utente1`, `temp2`, `valore3`.

## Esempi

Cattivo:

```python
def handle_data(data):
    # processa i dati
    try:
        result = do_something(data)
        return result
    except Exception:
        return None
```

Buono:

```python
def risolvi_comune_competente(posizione: Point) -> Comune | None:
    """Restituisce il comune che copre la posizione, o None se fuori copertura."""
    ...
```

Cattivo:

```typescript
const handleClick = (e: any) => {
  // gestisce il click
  processData(e.target.value);
};
```

Buono:

```typescript
function confermaPosizioneSegnalazione(coordinate: Coordinate): void {
  ...
}
```
