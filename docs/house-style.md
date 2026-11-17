# Stile del codice

Questo documento è la fonte estesa delle regole di stile del repository. È
scritto per chi fa review: per ogni gruppo spiega la motivazione e mostra un
esempio positivo e uno negativo. L'estratto operativo per gli assistenti è in
[`../.github/copilot-instructions.md`](../.github/copilot-instructions.md); se
le due versioni divergono, la divergenza va corretta, non ignorata.

Le regole valgono per Python e TypeScript, salvo dove indicato. Il dominio è
in italiano perché il prodotto è in italiano: chi revisiona deve poter
collegare il codice al piano architetturale senza un dizionario. I termini
tecnici standard restano in inglese, perché tradurli renderebbe il codice
meno riconoscibile per chi arriva da fuori.

## Naming

**Regola.** Nomi di dominio in italiano, verbi espliciti per le funzioni,
prefissi `is_`, `has_`, `puo_`, `deve_` per i booleani, costanti in maiuscolo
con underscore, file che descrivono la responsabilità. I nomi generici sono
vietati.

**Perché.** Un nome generico costringe chi legge a ricostruire il contesto
dalla chiamata. In un dominio con `segnalazione`, `comune`, `confine`,
`dispatch` e `ambiguita`, il nome giusto riduce il carico cognitivo e rende
riconoscibili gli errori di concetto. `data` e `result` non dicono nulla: il
tipo lo dice già il compilatore, il dominio lo deve dire il nome.

Positivo:

```python
def risolvi_comune_competente(posizione: Point) -> Comune | None:
    """Restituisce il comune che copre la posizione."""
    ...


def marca_come_risolta(segnalazione: Segnalazione) -> Segnalazione:
    ...


puo_essere_modificata = segnalazione.stato is StatoSegnalazione.APERTA
```

Negativo:

```python
def handle_data(data, obj):
    result = process(data)
    return result
```

Il nome del file segue la stessa regola: `risoluzione_confine.py` dice cosa
contiene, `helpers.py` non dice nulla.

## Commenti

**Regola.** Il commento spiega il perché, non il cosa. Niente commenti che
ripetono il codice, niente commenti di sezione che ripetono la firma, niente
`TODO` senza riferimento a un problema tracciato.

**Perché.** Un commento ovvio invecchia insieme al codice e diventa rumore.
Un commento che spiega una scelta non ovvia conserva il motivo di quella
scelta anche quando il codice cambia forma. Nel routing dei confini, per
esempio, la differenza tra `ST_Covers` e `ST_Contains` è una decisione di
prodotto che va tramandata, non dedotta.

Positivo:

```python
# ST_Covers e non ST_Contains: un punto sul bordo va assegnato.
comune_competente = risolvi_confine(posizione)
```

Negativo:

```python
# incrementa il contatore
contatore += 1

# funzione che valida la transizione
def valida_transizione_stato(stato_precedente, stato_successivo):
    ...
```

Un `TODO` ammesso ha un riferimento verificabile:

```python
# TODO(#142): il mapping Open311 per questo comune è ancora parziale.
```

## Docstring

**Regola.** Solo sulle funzioni e classi pubbliche dei moduli di dominio. Una
riga, in italiano, che dice cosa fa e cosa restituisce. Niente elenco dei
parametri già presenti nella firma, niente esempi decorativi, niente
docstring su test, DTO o funzioni banali.

**Perché.** La docstring di dominio è una promessa verso chi usa il modulo.
Se ripete la firma diventa una seconda documentazione da mantenere allineata
e, quando divergono, nessuna delle due è affidabile. Una riga costringe a
scegliere l'informazione che conta.

Positivo:

```python
def valida_transizione_stato(
    stato_precedente: StatoSegnalazione,
    stato_successivo: StatoSegnalazione,
) -> StatoSegnalazione:
    """Restituisce lo stato successivo o solleva TransizioneNonAmmessa."""
    ...
```

Negativo:

```python
def valida_transizione_stato(stato_precedente, stato_successivo):
    """
    Valida una transizione di stato.

    :param stato_precedente: lo stato precedente
    :param stato_successivo: lo stato successivo
    :return: lo stato successivo
    """
    ...
```

## Struttura

**Regola.** Un modulo per responsabilità di dominio. Ordine dei moduli
Python: import, tipi, costanti che dipendono dai tipi, eccezioni di dominio,
funzioni pure, classi di servizio, funzioni di I/O. Ordine dei moduli
TypeScript: import, tipi, costanti, componenti o funzioni, export. Le
dipendenze si iniettano; fanno eccezione logger e client HTTP già configurati
a livello di modulo.

**Perché.** La posizione stabile delle parti di un modulo permette di
trovare subito ciò che si cerca durante una review. Un file "contenitore"
nasconde le responsabilità e trasforma ogni modifica in un rischio di
accoppiamento. L'iniezione delle dipendenze rende i confini espliciti e
testabili senza dover simulare l'intero processo.

Positivo:

```python
from __future__ import annotations

from app.dominio.segnalazione import StatoSegnalazione

MAX_TENTATIVI_DISPATCH = 5


class TransizioneNonAmmessa(Exception):
    ...


def valida_transizione_stato(...):
    ...


class ServizioDispatch:
    def __init__(self, client_open311: ClientOpen311) -> None:
        self._client_open311 = client_open311
```

Negativo:

```python
# helpers.py
def leggi_config(): ...
def calcola_sla(): ...
def invia_email(): ...
def formatta_data(): ...
```

Lo stesso vale per un modulo che importa il database dentro una funzione:
la dipendenza non è visibile dalla firma e il test diventa più costoso.

## Gestione degli errori

**Regola.** Un `try/except` o un `try/catch` esiste solo se l'handler fa
qualcosa di concreto: log con contesto, retry, fallback, trasformazione in
errore di dominio. Gli errori utente sono in italiano e in formato RFC 7807;
gli errori nei log sono in inglese e strutturati; i messaggi sono specifici.
Non si restituisce `None` per segnalare un errore.

**Perché.** Il difensivismo sistematico nasconde i guasti e sposta
l'informazione dove nessuno la vede. Un errore di dominio esplicito
interrompe il flusso nel punto giusto e conserva il contesto. `None` va usato
solo quando l'assenza è un esito legittimo del dominio, per esempio un punto
fuori da ogni confine conosciuto.

Positivo:

```python
if (stato_precedente, stato_successivo) not in TRANSAZIONI_AMMESSE:
    raise TransizioneNonAmmessa(stato_precedente, stato_successivo)
```

Positivo, assenza legittima distinta dall'errore:

```python
comune_competente = risolvi_comune_competente(posizione)
if comune_competente is None:
    segnalazione = marca_fuori_copertura(segnalazione)
```

Negativo:

```python
try:
    return esegui_dispatch(segnalazione)
except Exception:
    return None
```

Un errore utente conforme ha un `detail` comprensibile e nessun dettaglio
interno:

```json
{
  "type": "https://example.invalid/errori/comune-non-coperto",
  "title": "Comune non coperto",
  "status": 422,
  "detail": "Il comune competente non è ancora coperto.",
  "instance": "/v1/reports"
}
```

## Log

**Regola.** Log strutturati, con `request_id`, `tenant_id` e `user_id`
pseudonimo. Mai email, token, API key o coordinate precise dell'utente.
Livello scelto con intenzione: `info` per gli eventi di dominio, `warning`
per i degradi recuperabili, `error` per ciò che richiede intervento.

**Perché.** Un log è un artefatto operativo e, quando contiene dati
personali, anche un trattamento. La struttura rende le ricerche possibili
senza leggere testo libero; la redazione evita che la piattaforma diventi una
seconda copia dei dati che il modello vuole minimizzare.

Positivo:

```python
logger.warning(
    "dispatch_retry_scheduled",
    extra={"request_id": request_id, "tenant_id": tenant_id},
)
```

Negativo:

```python
print(f"Invio fallito per {email}, token {token}, coordinate {lat},{lon}")
```

Il secondo esempio viola tre regole insieme: usa `print`, espone PII e
mescola livelli e informazioni in un messaggio non strutturato.

## Test

**Regola.** I test descrivono il comportamento osservabile, non
l'implementazione. Il nome è in italiano nella forma
`test_<comportamento>_<condizione>`. Un test per ogni criterio di convalida
del piano, non un test per ogni riga. I test che verificano una chiamata
interna sono ammessi solo su un confine di integrazione.

**Perché.** Un test legato all'implementazione si rompe quando il codice
migliora senza che il comportamento sia cambiato. Un test di comportamento
documenta il requisito e protegge ciò che il piano considera non
negoziabile, per esempio che una segnalazione fuori copertura resti
pubblica.

Positivo:

```python
def test_crea_segnalazione_fuori_copertura_resta_pubblica() -> None:
    esito = crea_segnalazione(posizione_fuori_da_ogni_confine)

    assert esito.visibilita == "public"
    assert esito.dispatch_state == "out_of_jurisdiction"
```

Negativo:

```python
def test_risolvi_comune() -> None:
    crea_segnalazione(posizione)

    risolvi_comune.assert_called_once()
```

Il secondo test verifica che una funzione interna sia stata chiamata, non che
il cittadino veda il risultato corretto.

## Messaggi all'utente

**Regola.** Italiano sobrio, senza punti esclamativi, emoji o saluti. Prima
cosa è successo, poi cosa può fare l'utente. Niente gergo tecnico o nomi di
stati interni.

**Perché.** L'utente non deve conoscere il modello dati per capire se la sua
segnalazione è stata presa in carico. Un messaggio che espone
`out_of_jurisdiction` trasferisce su di lui un dettaglio implementativo e
peggiora la fiducia nel servizio.

Positivo:

```text
Il comune competente non è ancora coperto. La segnalazione resta pubblica e
sarà assegnata manualmente.
```

Negativo:

```text
Errore: out_of_jurisdiction
```

Anche un messaggio generico è vietato perché non dice all'utente cosa può
fare:

```text
Qualcosa è andato storto.
```

## Documentazione e README

**Regola.** Niente emoji, intestazioni decorative o elenchi usati come
riempitivo. Il README dice cosa fa il progetto, come si avvia, come si testa
e come si contribuisce. I documenti di architettura stanno in `docs/` e sono
versionati. Niente sezione "Features" con checklist promozionale.

**Perché.** La documentazione è materiale di lavoro, non una pagina di
vendita. Chi arriva al repository deve trovare le informazioni che gli
servono nell'ordine in cui gli servono. Una checklist di funzionalità
invecchia e non spiega né l'avvio né i vincoli.

Positivo:

```markdown
# Segnalazione civica multi-comune

Piattaforma per raccogliere segnalazioni e instradarle al comune competente.

## Avvio

Esegui `make setup`.

## Verifiche

Esegui `make lint` e `make test`.

## Stile del codice

Le regole sono in `docs/house-style.md`.
```

Negativo:

```markdown
# Progetto

## Features

- [x] Mappa
- [ ] Notifiche
- [ ] Integrazione Open311
```

Il secondo README non spiega come avviare il progetto e non rimanda alle
regole condivise.

## Pattern vietati trasversali

| Pattern | Motivo |
|---|---|
| `None` come segnale di errore | L'assenza legittima e il guasto diventano indistinguibili |
| `print` in produzione | Non ha struttura, non ha livelli e non è redatto |
| Accesso al database dal frontend | Rompe l'isolamento e la minimizzazione dei dati |
| HTTP sincrono verso servizi esterni nel ciclo di richiesta | Un guasto esterno degrada l'esperienza del cittadino |
| `except Exception` senza rilancio o log contestualizzato | Nasconde il guasto senza lasciare traccia |
| Codice commentato | Diventa codice morto non testato e non aggiornato |
| Nomi con numeri progressivi (`utente1`, `temp2`) | Non descrivono il ruolo e favoriscono la copia meccanica |

Il test [`../api/tests/test_schema_stile.py`](../api/tests/test_schema_stile.py)
controlla in modo volutamente grossolano quattro di questi divieti: `print`
fuori dai test, `except Exception` senza azione, `TODO` senza riferimento e
nomi generici. Serve a rendere visibile la deriva, non a sostituire la
review.

## Checklist per la review

1. I nomi descrivono il dominio e non il tipo.
2. Le funzioni hanno un verbo e i booleani hanno il prefisso corretto.
3. I commenti spiegano scelte non ovvie e i `TODO` hanno un riferimento.
4. Le docstring sono solo dove servono e stanno in una riga.
5. Ogni modulo ha una responsabilità riconoscibile.
6. Gli handler di errore fanno qualcosa di concreto.
7. I log sono strutturati e non contengono PII.
8. I test verificano comportamento osservabile e hanno un nome italiano.
9. I messaggi all'utente dicono cosa è successo e cosa può fare.
10. Il README e i documenti in `docs/` sono aggiornati e coerenti con il
    codice.
