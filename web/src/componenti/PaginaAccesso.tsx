'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FormEvent } from 'react';
import { useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import { ErroreApi, leggiMessaggioErrore } from '../servizi/clientApi';

const MESSAGGIO_CREDENZIALI_NON_VALIDE =
  'Credenziali non valide. Controlla email e password.';
const MESSAGGIO_ERRORE_ACCESSO =
  'Non è stato possibile accedere. Riprova tra qualche istante.';

const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

export function PaginaAccesso() {
  const router = useRouter();
  const { accedi, profilo } = usaAutenticazione();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isInvioInCorso, setIsInvioInCorso] = useState(false);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  async function invia(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setMessaggioErrore(null);
    setIsInvioInCorso(true);
    try {
      await accedi(email, password);
      router.push('/');
      router.refresh();
    } catch (errore) {
      if (errore instanceof ErroreApi && errore.stato === 401) {
        setMessaggioErrore(MESSAGGIO_CREDENZIALI_NON_VALIDE);
      } else {
        setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_ACCESSO));
      }
    } finally {
      setIsInvioInCorso(false);
    }
  }

  if (profilo) {
    return (
      <section className="mx-auto max-w-md space-y-4">
        <h1 className="text-2xl font-semibold">Accesso</h1>
        <p className="text-sm text-slate-700">
          Hai già effettuato l'accesso come {profilo.nickname}.
        </p>
        <Link
          href="/"
          className="inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          Torna alla mappa
        </Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-md space-y-5">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Accedi</h1>
        <p className="text-sm text-slate-600">
          Inserisci email e password per inviare e seguire le segnalazioni.
        </p>
      </header>

      <form onSubmit={invia} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(evento) => setEmail(evento.target.value)}
            className={STILE_CAMPO}
          />
        </div>
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

        <button
          type="submit"
          disabled={isInvioInCorso}
          className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isInvioInCorso ? 'Accesso in corso…' : 'Accedi'}
        </button>
      </form>

      <p className="text-sm text-slate-600">
        Non hai un account?{' '}
        <Link href="/register" className="font-medium text-brand-700 underline">
          Registrati
        </Link>
        .
      </p>
    </section>
  );
}
