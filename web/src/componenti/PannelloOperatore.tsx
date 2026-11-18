'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import type {
  DettaglioAmministrazione,
  FallimentoDispatch,
} from '../dominio/amministrazione';
import { formattaDataOra } from '../dominio/data';
import type { Segnalazione } from '../dominio/segnalazione';
import {
  COLORI_STATO,
  ETICHETTE_STATO,
  etichettaAttore,
} from '../dominio/segnalazione';
import {
  aggiungiNotaInterna,
  caricaDettaglioAmministrazione,
  caricaFallimentiDispatch,
  caricaSegnalazioniAmministrazione,
  riprovaDispatch,
} from '../servizi/amministrazione';
import { leggiMessaggioErrore } from '../servizi/clientApi';
import type { StatoApiSegnalazione } from '../servizi/segnalazioni';
import { cambiaStatoSegnalazione } from '../servizi/segnalazioni';

const FILTRI_STATO: { valore: StatoApiSegnalazione | ''; etichetta: string }[] = [
  { valore: '', etichetta: 'Tutte' },
  { valore: 'open', etichetta: 'Aperte' },
  { valore: 'in_progress', etichetta: 'In corso' },
  { valore: 'resolved', etichetta: 'Risolte' },
  { valore: 'closed', etichetta: 'Chiuse' },
];

const AZIONI_STATO: Partial<
  Record<StatoApiSegnalazione, { prossimo: StatoApiSegnalazione; etichetta: string }>
> = {
  open: { prossimo: 'in_progress', etichetta: 'Prendi in carico' },
  in_progress: { prossimo: 'resolved', etichetta: 'Risolvi' },
  resolved: { prossimo: 'closed', etichetta: 'Chiudi' },
};

const MESSAGGIO_ERRORE_CARICAMENTO =
  'Non è stato possibile caricare i dati del pannello. Riprova tra poco.';
const MESSAGGIO_ERRORE_AZIONE =
  'Non è stato possibile completare l’operazione. Controlla i dati e riprova.';
const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

export function PannelloOperatore() {
  const router = useRouter();
  const { token, profilo, isCaricamento } = usaAutenticazione();
  const [filtroStato, setFiltroStato] = useState<StatoApiSegnalazione | ''>('');
  const [segnalazioni, setSegnalazioni] = useState<Segnalazione[]>([]);
  const [fallimenti, setFallimenti] = useState<FallimentoDispatch[]>([]);
  const [idSelezionato, setIdSelezionato] = useState<string | null>(null);
  const [dettaglio, setDettaglio] = useState<DettaglioAmministrazione | null>(null);
  const [notaPubblica, setNotaPubblica] = useState('');
  const [notaInterna, setNotaInterna] = useState('');
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);
  const [isAttesa, setIsAttesa] = useState(false);

  useEffect(() => {
    if (!isCaricamento && (!profilo || !profilo.isOperatore)) {
      router.replace('/');
    }
  }, [isCaricamento, profilo, router]);

  const caricaElenco = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const elenco = await caricaSegnalazioniAmministrazione(
        token,
        filtroStato || null,
      );
      setSegnalazioni(elenco);
      setMessaggioErrore(null);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_CARICAMENTO));
    }
  }, [token, filtroStato]);

  const caricaFallimenti = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const elenco = await caricaFallimentiDispatch(token);
      setFallimenti(elenco);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_CARICAMENTO));
    }
  }, [token]);

  useEffect(() => {
    if (token && profilo?.isOperatore) {
      void caricaElenco();
      void caricaFallimenti();
    }
  }, [token, profilo, caricaElenco, caricaFallimenti]);

  async function apriDettaglio(id: string): Promise<void> {
    if (!token) {
      return;
    }
    setIdSelezionato(id);
    setNotaPubblica('');
    setNotaInterna('');
    try {
      const caricato = await caricaDettaglioAmministrazione(token, id);
      setDettaglio(caricato);
      setMessaggioErrore(null);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_CARICAMENTO));
    }
  }

  async function cambiaStato(stato: StatoApiSegnalazione): Promise<void> {
    if (!token || !dettaglio) {
      return;
    }
    setIsAttesa(true);
    try {
      await cambiaStatoSegnalazione(
        dettaglio.id,
        stato,
        notaPubblica.trim() || null,
        token,
      );
      await apriDettaglio(dettaglio.id);
      await caricaElenco();
      setNotaPubblica('');
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_AZIONE));
    } finally {
      setIsAttesa(false);
    }
  }

  async function salvaNotaInterna(): Promise<void> {
    if (!token || !dettaglio || !notaInterna.trim()) {
      return;
    }
    setIsAttesa(true);
    try {
      await aggiungiNotaInterna(token, dettaglio.id, notaInterna.trim());
      await apriDettaglio(dettaglio.id);
      setNotaInterna('');
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_AZIONE));
    } finally {
      setIsAttesa(false);
    }
  }

  async function riprova(idSegnalazione: string): Promise<void> {
    if (!token) {
      return;
    }
    setIsAttesa(true);
    try {
      await riprovaDispatch(token, idSegnalazione);
      await caricaFallimenti();
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_AZIONE));
    } finally {
      setIsAttesa(false);
    }
  }

  if (isCaricamento) {
    return <p className="text-sm text-slate-600">Verifica dell’accesso…</p>;
  }

  if (!profilo || !profilo.isOperatore) {
    return (
      <p className="text-sm text-slate-600">
        Questa area è riservata agli operatori comunali. Reindirizzamento alla mappa…
      </p>
    );
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Pannello operatore</h1>
        <p className="text-sm text-slate-600">
          Segnalazioni del comune e stato degli invii.
        </p>
      </header>

      {messaggioErrore ? (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {messaggioErrore}
        </p>
      ) : null}

      <section className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {FILTRI_STATO.map((filtro) => (
            <button
              key={filtro.etichetta}
              type="button"
              onClick={() => setFiltroStato(filtro.valore)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                filtroStato === filtro.valore
                  ? 'border-brand-600 bg-brand-600 text-white'
                  : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
              }`}
            >
              {filtro.etichetta}
            </button>
          ))}
        </div>
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Riferimento</th>
                <th className="px-4 py-3">Titolo</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Creata il</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {segnalazioni.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-4 text-slate-600">
                    Nessuna segnalazione per il filtro scelto.
                  </td>
                </tr>
              ) : (
                segnalazioni.map((segnalazione) => (
                  <tr
                    key={segnalazione.id}
                    onClick={() => void apriDettaglio(segnalazione.id)}
                    className={`cursor-pointer hover:bg-slate-50 ${
                      idSelezionato === segnalazione.id ? 'bg-brand-50' : ''
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">
                      {segnalazione.riferimentoPubblico}
                    </td>
                    <td className="px-4 py-3">{segnalazione.titolo}</td>
                    <td className="px-4 py-3">
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium text-white"
                        style={{ backgroundColor: COLORI_STATO[segnalazione.stato] }}
                      >
                        {ETICHETTE_STATO[segnalazione.stato]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {formattaDataOra(segnalazione.creataIl)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {dettaglio ? (
        <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
          <header className="space-y-1">
            <p className="text-sm text-slate-500">{dettaglio.riferimentoPubblico}</p>
            <h2 className="text-xl font-semibold">{dettaglio.titolo}</h2>
            <p className="text-sm text-slate-700">{dettaglio.descrizione}</p>
          </header>

          <div className="space-y-2">
            <label htmlFor="nota-pubblica" className="text-sm font-medium">
              Nota pubblica
            </label>
            <textarea
              id="nota-pubblica"
              value={notaPubblica}
              onChange={(evento) => setNotaPubblica(evento.target.value)}
              rows={3}
              maxLength={1000}
              className={STILE_CAMPO}
              placeholder="La nota sarà visibile nella pagina pubblica della segnalazione."
            />
            <div className="flex flex-wrap gap-2">
              {Object.entries(AZIONI_STATO).map(([statoCorrente, azione]) =>
                dettaglio.stato === mappaEtichettaStato(statoCorrente) && azione ? (
                  <button
                    key={azione.etichetta}
                    type="button"
                    disabled={isAttesa}
                    onClick={() => void cambiaStato(azione.prossimo)}
                    className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {azione.etichetta}
                  </button>
                ) : null,
              )}
            </div>
          </div>

          <section className="space-y-2">
            <h3 className="text-base font-semibold">Cronologia</h3>
            <ol className="space-y-2">
              {dettaglio.eventiStato.map((evento) => (
                <li
                  key={evento.id}
                  className="rounded-md border border-slate-200 px-3 py-2"
                >
                  <p className="text-sm font-medium">
                    {evento.statoPrecedente
                      ? `${ETICHETTE_STATO[evento.statoPrecedente]} → `
                      : ''}
                    {ETICHETTE_STATO[evento.statoSuccessivo]}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formattaDataOra(evento.creatoIl)} ·{' '}
                    {etichettaAttore(evento.tipoAttore)}
                    {evento.isPubblica ? '' : ' · nota interna'}
                  </p>
                  {evento.notaPubblica ? (
                    <p className="mt-1 text-sm text-slate-700">{evento.notaPubblica}</p>
                  ) : null}
                </li>
              ))}
            </ol>
          </section>

          <section className="space-y-2">
            <h3 className="text-base font-semibold">Storico invii</h3>
            {dettaglio.storicoDispatch.length === 0 ? (
              <p className="text-sm text-slate-600">Nessun tentativo registrato.</p>
            ) : (
              <ul className="space-y-2">
                {dettaglio.storicoDispatch.map((tentativo) => (
                  <li
                    key={tentativo.id}
                    className="rounded-md border border-slate-200 px-3 py-2 text-sm"
                  >
                    <p className="font-medium">
                      {tentativo.canale} · tentativo {tentativo.numeroTentativo} ·{' '}
                      {tentativo.stato}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formattaDataOra(tentativo.creatoIl)}
                      {tentativo.codiceErrore ? ` · ${tentativo.codiceErrore}` : ''}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-base font-semibold">Note interne</h3>
            {dettaglio.noteInterne.length === 0 ? (
              <p className="text-sm text-slate-600">Nessuna nota interna.</p>
            ) : (
              <ul className="space-y-2">
                {dettaglio.noteInterne.map((nota) => (
                  <li
                    key={nota.id}
                    className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm"
                  >
                    <p>{nota.testo}</p>
                    <p className="text-xs text-slate-500">
                      {formattaDataOra(nota.creataIl)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            <textarea
              value={notaInterna}
              onChange={(evento) => setNotaInterna(evento.target.value)}
              rows={2}
              maxLength={2000}
              className={STILE_CAMPO}
              placeholder="Aggiungi una nota visibile solo agli operatori."
            />
            <button
              type="button"
              disabled={isAttesa || !notaInterna.trim()}
              onClick={() => void salvaNotaInterna()}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Salva nota interna
            </button>
          </section>
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Fallimenti di invio</h2>
        {fallimenti.length === 0 ? (
          <p className="text-sm text-slate-600">Nessun invio fallito.</p>
        ) : (
          <ul className="space-y-2">
            {fallimenti.map((fallimento) => (
              <li
                key={fallimento.dispatch.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {fallimento.riferimentoPubblico} · {fallimento.titolo}
                  </p>
                  <p className="text-xs text-slate-600">
                    {fallimento.dispatch.canale} ·{' '}
                    {fallimento.dispatch.codiceErrore ?? 'errore permanente'}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={isAttesa}
                  onClick={() => void riprova(fallimento.idSegnalazione)}
                  className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Riprova
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

function mappaEtichettaStato(stato: string): string {
  const corrispondenze: Record<string, string> = {
    open: 'aperta',
    in_progress: 'in_corso',
    resolved: 'risolta',
    closed: 'chiusa',
  };
  return corrispondenze[stato] ?? stato;
}
