'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FormEvent } from 'react';
import { useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import { ErroreApi, leggiMessaggioErrore } from '../servizi/clientApi';

const MESSAGGIO_DATI_GIA_IN_USO =
  'Email o nickname già in uso. Accedi oppure scegli dati diversi.';
const MESSAGGIO_ERRORE_REGISTRAZIONE =
  'Non è stato possibile completare la registrazione. Controlla i dati e riprova.';

const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

export function PaginaRegistrazione() {
  const router = useRouter();
  const { registra, profilo } = usaAutenticazione();
  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [isInvioInCorso, setIsInvioInCorso] = useState(false);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  async function invia(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setMessaggioErrore(null);
    setIsInvioInCorso(true);
    try {
      await registra({ email, nickname, password });
      router.push('/');
      router.refresh();
    } catch (errore) {
      if (errore instanceof ErroreApi && errore.stato === 409) {
        setMessaggioErrore(MESSAGGIO_DATI_GIA_IN_USO);
      } else {
        setMessaggioErrore(
          leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_REGISTRAZIONE),
        );
      }
    } finally {
      setIsInvioInCorso(false);
    }
  }

  if (profilo) {
    return (
      <section className="mx-auto max-w-md space-y-4">
        <h1 className="text-2xl font-semibold">Registrazione</h1>
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
        <h1 className="text-2xl font-semibold">Registrati</h1>
        <p className="text-sm text-slate-600">
          Crea un account per inviare segnalazioni e seguirne lo stato.
        </p>
      </header>

      <form onSubmit={invia} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="nickname" className="text-sm font-medium">
            Nickname
          </label>
          <input
            id="nickname"
            type="text"
            autoComplete="username"
            required
            minLength={3}
            maxLength={30}
            pattern="[a-zA-Z0-9_-]{3,30}"
            value={nickname}
            onChange={(evento) => setNickname(evento.target.value)}
            className={STILE_CAMPO}
          />
          <p className="text-xs text-slate-500">
            Da 3 a 30 caratteri tra lettere, numeri, trattino e trattino basso.
          </p>
        </div>
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
            autoComplete="new-password"
            required
            minLength={12}
            value={password}
            onChange={(evento) => setPassword(evento.target.value)}
            className={STILE_CAMPO}
          />
          <p className="text-xs text-slate-500">Almeno 12 caratteri.</p>
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
          {isInvioInCorso ? 'Registrazione in corso…' : "Crea l'account"}
        </button>
      </form>

      <p className="text-sm text-slate-600">
        Hai già un account?{' '}
        <Link href="/login" className="font-medium text-brand-700 underline">
          Accedi
        </Link>
        .
      </p>
    </section>
  );
}
