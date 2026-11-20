'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FormEvent } from 'react';
import { useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import { eliminaAccount, scaricaDatiPersonali } from '../servizi/autenticazione';
import { ErroreApi, leggiMessaggioErrore } from '../servizi/clientApi';

const NOME_FILE_DATI = 'segno-dati-personali.json';
const MESSAGGIO_ERRORE_SCARICAMENTO =
  'Non è stato possibile preparare il file dei tuoi dati. Riprova tra qualche istante.';
const MESSAGGIO_ERRORE_CANCELLAZIONE =
  'Non è stato possibile eliminare l’account. Riprova tra qualche istante.';
const MESSAGGIO_PASSWORD_ERRATA =
  'La password indicata non è corretta. Controlla e riprova.';
const AVVISO_CANCELLAZIONE =
  'Le tue segnalazioni resteranno visibili a tutti, ma non saranno più collegate a te. L’operazione non può essere annullata.';

const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';
const STILE_PULSANTE_PRINCIPALE =
  'rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60';
const STILE_PULSANTE_SECONDARIO =
  'rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100';

export function PaginaProfilo() {
  const router = useRouter();
  const { token, profilo, isCaricamento } = usaAutenticazione();
  const [isScaricamentoInCorso, setIsScaricamentoInCorso] = useState(false);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);
  const [isModaleAperto, setIsModaleAperto] = useState(false);

  async function scaricaDati(): Promise<void> {
    if (!token) {
      return;
    }
    setMessaggioErrore(null);
    setIsScaricamentoInCorso(true);
    try {
      const file = await scaricaDatiPersonali(token);
      scaricaFile(file, NOME_FILE_DATI);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_SCARICAMENTO));
    } finally {
      setIsScaricamentoInCorso(false);
    }
  }

  function chiudiDopoCancellazione(): void {
    setIsModaleAperto(false);
    router.push('/');
    router.refresh();
  }

  if (isCaricamento) {
    return (
      <section className="mx-auto max-w-md space-y-4">
        <h1 className="text-2xl font-semibold">Profilo</h1>
        <p className="text-sm text-slate-600">Caricamento del profilo…</p>
      </section>
    );
  }

  if (!profilo) {
    return (
      <section className="mx-auto max-w-md space-y-4">
        <h1 className="text-2xl font-semibold">Profilo</h1>
        <p className="text-sm text-slate-700">
          Accedi per gestire il tuo profilo e i tuoi dati personali.
        </p>
        <Link
          href="/login"
          className="inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Accedi
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-md space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Profilo</h1>
        <p className="text-sm text-slate-600">
          {profilo.nickname} · {profilo.emailMascherata}
        </p>
      </header>

      <div className="space-y-2 rounded-md border border-slate-200 bg-white p-4">
        <h2 className="text-base font-semibold">I tuoi dati</h2>
        <p className="text-sm text-slate-600">
          Scarica una copia di profilo, segnalazioni, eventi e notifiche in formato
          JSON.
        </p>
        <button
          type="button"
          onClick={scaricaDati}
          disabled={isScaricamentoInCorso}
          className={STILE_PULSANTE_PRINCIPALE}
        >
          {isScaricamentoInCorso ? 'Preparazione del file…' : 'Scarica i tuoi dati'}
        </button>
      </div>

      <div className="space-y-2 rounded-md border border-red-200 bg-red-50 p-4">
        <h2 className="text-base font-semibold text-red-900">Elimina account</h2>
        <p className="text-sm text-red-800">{AVVISO_CANCELLAZIONE}</p>
        <button
          type="button"
          onClick={() => setIsModaleAperto(true)}
          className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800"
        >
          Elimina account
        </button>
      </div>

      {messaggioErrore ? (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {messaggioErrore}
        </p>
      ) : null}

      {isModaleAperto ? (
        <ModaleCancellazione
          onAnnulla={() => setIsModaleAperto(false)}
          onAccountEliminato={chiudiDopoCancellazione}
        />
      ) : null}
    </section>
  );
}

function ModaleCancellazione({
  onAnnulla,
  onAccountEliminato,
}: {
  onAnnulla: () => void;
  onAccountEliminato: () => void;
}) {
  const { token, esci } = usaAutenticazione();
  const [password, setPassword] = useState('');
  const [isInvioInCorso, setIsInvioInCorso] = useState(false);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  async function conferma(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    if (!token) {
      onAnnulla();
      return;
    }
    setMessaggioErrore(null);
    setIsInvioInCorso(true);
    try {
      await eliminaAccount(token, password);
      esci();
      onAccountEliminato();
    } catch (errore) {
      if (errore instanceof ErroreApi && errore.stato === 403) {
        setMessaggioErrore(MESSAGGIO_PASSWORD_ERRATA);
      } else {
        setMessaggioErrore(
          leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_CANCELLAZIONE),
        );
      }
    } finally {
      setIsInvioInCorso(false);
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-slate-900/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titolo-cancellazione"
        className="w-full max-w-md space-y-4 rounded-lg bg-white p-5 shadow-xl"
      >
        <h2 id="titolo-cancellazione" className="text-lg font-semibold">
          Conferma l’eliminazione
        </h2>
        <p className="text-sm text-slate-700">{AVVISO_CANCELLAZIONE}</p>
        <form onSubmit={conferma} className="space-y-4">
          <div className="space-y-1">
            <label htmlFor="password" className="text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(evento) => setPassword(evento.target.value)}
              className={STILE_CAMPO}
            />
          </div>

          {messaggioErrore ? (
            <p
              role="alert"
              className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {messaggioErrore}
            </p>
          ) : null}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onAnnulla}
              className={STILE_PULSANTE_SECONDARIO}
            >
              Annulla
            </button>
            <button
              type="submit"
              disabled={isInvioInCorso}
              className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isInvioInCorso ? 'Eliminazione in corso…' : 'Elimina account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function scaricaFile(file: Blob, nomeFile: string): void {
  const indirizzo = window.URL.createObjectURL(file);
  const collegamento = document.createElement('a');
  collegamento.href = indirizzo;
  collegamento.download = nomeFile;
  collegamento.click();
  window.URL.revokeObjectURL(indirizzo);
}
