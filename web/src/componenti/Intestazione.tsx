'use client';

import Link from 'next/link';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';

import { CampanellaNotifiche } from './CampanellaNotifiche';

const STILE_COLLEGAMENTO_NEUTRO =
  'rounded-md px-3 py-2 text-slate-700 hover:bg-slate-100';

export function Intestazione() {
  const { profilo, isCaricamento, esci } = usaAutenticazione();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="text-lg font-semibold tracking-tight text-brand-700">
          Segno
        </Link>
        <nav className="flex flex-wrap items-center gap-2 text-sm">
          <Link
            href="/report"
            className="rounded-md bg-brand-600 px-3 py-2 font-medium text-white hover:bg-brand-700"
          >
            Segnala un problema
          </Link>
          {isCaricamento ? null : profilo ? (
            <>
              <CampanellaNotifiche />
              {profilo.isOperatore ? (
                <Link href="/admin" className={STILE_COLLEGAMENTO_NEUTRO}>
                  Pannello operatore
                </Link>
              ) : null}
              <span className="px-2 text-slate-600">{profilo.nickname}</span>
              <button
                type="button"
                onClick={esci}
                className={STILE_COLLEGAMENTO_NEUTRO}
              >
                Esci
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className={STILE_COLLEGAMENTO_NEUTRO}>
                Accedi
              </Link>
              <Link href="/register" className={STILE_COLLEGAMENTO_NEUTRO}>
                Registrati
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
