'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import { formattaDataOra } from '../dominio/data';
import type { Notifica } from '../dominio/notifica';
import {
  etichettaStatoNotifica,
  linkSegnalazioneNotifica,
  riferimentoPubblicoNotifica,
} from '../dominio/notifica';
import { leggiMessaggioErrore } from '../servizi/clientApi';
import {
  caricaNotifiche,
  segnaNotificaLetta,
  segnaTutteNotificheLette,
} from '../servizi/notifiche';

const MESSAGGIO_ERRORE_NOTIFICHE =
  'Non è stato possibile caricare le notifiche. Riprova tra poco.';

export function ElencoNotifiche() {
  const { token, isCaricamento } = usaAutenticazione();
  const [notifiche, setNotifiche] = useState<Notifica[]>([]);
  const [conteggioNonLette, setConteggioNonLette] = useState(0);
  const [isAttesa, setIsAttesa] = useState(true);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  const carica = useCallback(async () => {
    if (!token) {
      setNotifiche([]);
      setConteggioNonLette(0);
      setIsAttesa(false);
      return;
    }
    try {
      const elenco = await caricaNotifiche(token, 50);
      setNotifiche(elenco.notifiche);
      setConteggioNonLette(elenco.conteggioNonLette);
      setMessaggioErrore(null);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_NOTIFICHE));
    } finally {
      setIsAttesa(false);
    }
  }, [token]);

  useEffect(() => {
    if (!isCaricamento) {
      void carica();
    }
  }, [isCaricamento, carica]);

  async function segnaLetta(notifica: Notifica): Promise<void> {
    if (!token || notifica.lettaIl) {
      return;
    }
    try {
      await segnaNotificaLetta(token, notifica.id);
      setNotifiche((correnti) =>
        correnti.map((voce) =>
          voce.id === notifica.id
            ? { ...voce, lettaIl: new Date().toISOString() }
            : voce,
        ),
      );
      setConteggioNonLette((conteggio) => Math.max(0, conteggio - 1));
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_NOTIFICHE));
    }
  }

  async function segnaTutte(): Promise<void> {
    if (!token) {
      return;
    }
    try {
      await segnaTutteNotificheLette(token);
      const istante = new Date().toISOString();
      setNotifiche((correnti) =>
        correnti.map((voce) => ({ ...voce, lettaIl: voce.lettaIl ?? istante })),
      );
      setConteggioNonLette(0);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_NOTIFICHE));
    }
  }

  if (isCaricamento || isAttesa) {
    return <p className="text-sm text-slate-600">Caricamento delle notifiche…</p>;
  }

  if (!token) {
    return (
      <section className="space-y-3">
        <h1 className="text-2xl font-semibold">Notifiche</h1>
        <p className="text-sm text-slate-600">
          Accedi per vedere gli aggiornamenti sulle tue segnalazioni.
        </p>
        <Link href="/login" className="text-sm font-medium text-brand-700 underline">
          Vai all'accesso
        </Link>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Notifiche</h1>
        {conteggioNonLette > 0 ? (
          <button
            type="button"
            onClick={segnaTutte}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            Segna tutte come lette
          </button>
        ) : null}
      </div>
      {messaggioErrore ? (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {messaggioErrore}
        </p>
      ) : null}
      {notifiche.length === 0 ? (
        <p className="text-sm text-slate-600">Non hai notifiche.</p>
      ) : (
        <ul className="space-y-3">
          {notifiche.map((notifica) => {
            const collegamento = linkSegnalazioneNotifica(notifica);
            const riferimento = riferimentoPubblicoNotifica(notifica);
            return (
              <li
                key={notifica.id}
                className={`rounded-md border px-4 py-3 ${
                  notifica.lettaIl
                    ? 'border-slate-200 bg-white'
                    : 'border-brand-200 bg-brand-50'
                }`}
              >
                <p className="text-sm font-medium">
                  {riferimento ? `${riferimento}: ` : ''}
                  {etichettaStatoNotifica(notifica.dati.to_status)}
                </p>
                <p className="text-xs text-slate-500">
                  {formattaDataOra(notifica.creataIl)}
                </p>
                {typeof notifica.dati.note_public === 'string' &&
                notifica.dati.note_public ? (
                  <p className="mt-1 text-sm text-slate-700">
                    {notifica.dati.note_public}
                  </p>
                ) : null}
                <div className="mt-2 flex items-center gap-3 text-sm">
                  {collegamento ? (
                    <Link
                      href={collegamento}
                      className="font-medium text-brand-700 underline"
                    >
                      Apri la segnalazione
                    </Link>
                  ) : null}
                  {notifica.lettaIl ? null : (
                    <button
                      type="button"
                      onClick={() => void segnaLetta(notifica)}
                      className="font-medium text-slate-700 underline"
                    >
                      Segna come letta
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
