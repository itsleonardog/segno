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

const INTERVALLO_AGGIORNAMENTO_MS = 60000;
const MESSAGGIO_ERRORE_NOTIFICHE =
  'Non è stato possibile aggiornare le notifiche. Riprova tra poco.';

export function CampanellaNotifiche() {
  const { token } = usaAutenticazione();
  const [isAperta, setIsAperta] = useState(false);
  const [notifiche, setNotifiche] = useState<Notifica[]>([]);
  const [conteggioNonLette, setConteggioNonLette] = useState(0);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setNotifiche([]);
      setConteggioNonLette(0);
      return;
    }
    const tokenUso = token;
    let isAnnullato = false;

    async function aggiornaConteggio(): Promise<void> {
      try {
        const elenco = await caricaNotifiche(tokenUso, 1);
        if (!isAnnullato) {
          setConteggioNonLette(elenco.conteggioNonLette);
        }
      } catch (errore) {
        if (!isAnnullato) {
          setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_NOTIFICHE));
        }
      }
    }

    void aggiornaConteggio();
    const intervallo = window.setInterval(() => {
      void aggiornaConteggio();
    }, INTERVALLO_AGGIORNAMENTO_MS);
    return () => {
      isAnnullato = true;
      window.clearInterval(intervallo);
    };
  }, [token]);

  const caricaElenco = useCallback(async () => {
    if (!token) {
      return;
    }
    try {
      const elenco = await caricaNotifiche(token);
      setNotifiche(elenco.notifiche);
      setConteggioNonLette(elenco.conteggioNonLette);
      setMessaggioErrore(null);
    } catch (errore) {
      setMessaggioErrore(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_NOTIFICHE));
    }
  }, [token]);

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

  function apriCampanella(): void {
    void caricaElenco();
    setIsAperta((aperta) => !aperta);
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={apriCampanella}
        aria-label="Notifiche"
        className="relative rounded-md px-3 py-2 text-slate-700 hover:bg-slate-100"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5m6 0a3 3 0 1 1-6 0"
          />
        </svg>
        {conteggioNonLette > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-600 px-1 text-center text-[11px] font-semibold text-white">
            {conteggioNonLette > 99 ? '99+' : conteggioNonLette}
          </span>
        ) : null}
      </button>

      {isAperta ? (
        <div className="absolute right-0 z-20 mt-2 w-80 rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold">Notifiche</p>
            {conteggioNonLette > 0 ? (
              <button
                type="button"
                onClick={segnaTutte}
                className="text-xs font-medium text-brand-700 underline"
              >
                Segna tutte come lette
              </button>
            ) : null}
          </div>
          {messaggioErrore ? (
            <p role="alert" className="text-sm text-red-700">
              {messaggioErrore}
            </p>
          ) : null}
          {notifiche.length === 0 && !messaggioErrore ? (
            <p className="text-sm text-slate-600">Non hai notifiche.</p>
          ) : (
            <ul className="max-h-80 space-y-2 overflow-y-auto">
              {notifiche.map((notifica) => {
                const collegamento = linkSegnalazioneNotifica(notifica);
                const riferimento = riferimentoPubblicoNotifica(notifica);
                return (
                  <li
                    key={notifica.id}
                    className={`rounded-md border px-3 py-2 ${
                      notifica.lettaIl
                        ? 'border-slate-200 bg-white'
                        : 'border-brand-200 bg-brand-50'
                    }`}
                  >
                    <p className="text-sm">
                      {riferimento ? `${riferimento}: ` : ''}
                      {etichettaStatoNotifica(notifica.dati.to_status)}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formattaDataOra(notifica.creataIl)}
                    </p>
                    <div className="mt-1 flex items-center gap-3 text-xs">
                      {collegamento ? (
                        <Link
                          href={collegamento}
                          className="font-medium text-brand-700 underline"
                        >
                          Apri
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
          <Link
            href="/notifications"
            className="mt-3 block text-center text-xs font-medium text-brand-700 underline"
          >
            Vedi tutte le notifiche
          </Link>
        </div>
      ) : null}
    </div>
  );
}
