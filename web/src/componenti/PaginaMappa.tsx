'use client';

import { useEffect, useState } from 'react';

import type { CategoriaSegnalazione, Segnalazione } from '../dominio/segnalazione';
import { caricaCategorie } from '../servizi/categorie';
import { caricaSegnalazioniPubbliche } from '../servizi/segnalazioni';

import { MappaSegnalazioniDinamica } from './MappaSegnalazioniDinamica';

const MESSAGGIO_ERRORE_CARICAMENTO =
  'Non è stato possibile caricare le segnalazioni. Aggiorna la pagina o riprova tra poco.';

export function PaginaMappa() {
  const [segnalazioni, setSegnalazioni] = useState<Segnalazione[]>([]);
  const [categorie, setCategorie] = useState<CategoriaSegnalazione[]>([]);
  const [isCaricamento, setIsCaricamento] = useState(true);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);

  useEffect(() => {
    let isAnnullato = false;

    async function caricaContenuti(): Promise<void> {
      try {
        const [segnalazioniCaricate, categorieCaricate] = await Promise.all([
          caricaSegnalazioniPubbliche(),
          caricaCategorie(),
        ]);
        if (isAnnullato) {
          return;
        }
        setSegnalazioni(segnalazioniCaricate);
        setCategorie(categorieCaricate);
      } catch {
        if (!isAnnullato) {
          setMessaggioErrore(MESSAGGIO_ERRORE_CARICAMENTO);
        }
      } finally {
        if (!isAnnullato) {
          setIsCaricamento(false);
        }
      }
    }

    void caricaContenuti();
    return () => {
      isAnnullato = true;
    };
  }, []);

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Segnalazioni dei cittadini</h1>
        <p className="text-sm text-slate-600">
          Esplora la mappa e apri una segnalazione per seguirne lo stato. I marker rossi
          indicano segnalazioni aperte, quelli gialli in corso e quelli verdi risolte.
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
      <div className="h-[70vh] min-h-[420px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        {isCaricamento ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-600">
            Caricamento delle segnalazioni…
          </div>
        ) : (
          <MappaSegnalazioniDinamica
            segnalazioni={segnalazioni}
            categorie={categorie}
          />
        )}
      </div>
    </section>
  );
}
