'use client';

import Link from 'next/link';
import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import { formattaDataOra } from '../dominio/data';
import type {
  CategoriaSegnalazione,
  DettaglioSegnalazione,
} from '../dominio/segnalazione';
import {
  COLORI_STATO,
  ETICHETTE_STATO,
  etichettaAttore,
} from '../dominio/segnalazione';
import { caricaCategorie, nomeCategoria } from '../servizi/categorie';
import { leggiMessaggioErrore } from '../servizi/clientApi';
import {
  caricaDettaglioSegnalazione,
  modificaSegnalazione,
} from '../servizi/segnalazioni';

import { MappaPosizioneDinamica } from './MappaPosizioneDinamica';

type Props = {
  riferimentoPubblico: string;
};

const MESSAGGIO_ERRORE_CARICAMENTO =
  'Non è stato possibile caricare la segnalazione. Aggiorna la pagina o riprova tra poco.';
const MESSAGGIO_ERRORE_MODIFICA =
  'Non è stato possibile salvare le modifiche. Controlla i dati e riprova.';
const MESSAGGIO_CAMPI_MODIFICA =
  'Titolo, descrizione e categoria sono obbligatori per salvare le modifiche.';

const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

export function SchedaDettaglioSegnalazione({ riferimentoPubblico }: Props) {
  const { token, profilo } = usaAutenticazione();
  const [segnalazione, setSegnalazione] = useState<DettaglioSegnalazione | null>(null);
  const [categorie, setCategorie] = useState<CategoriaSegnalazione[]>([]);
  const [isCaricamento, setIsCaricamento] = useState(true);
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);
  const [isModificaAperta, setIsModificaAperta] = useState(false);
  const [titoloModifica, setTitoloModifica] = useState('');
  const [descrizioneModifica, setDescrizioneModifica] = useState('');
  const [idCategoriaModifica, setIdCategoriaModifica] = useState('');
  const [isSalvataggio, setIsSalvataggio] = useState(false);
  const [messaggioErroreModifica, setMessaggioErroreModifica] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let isAnnullato = false;

    async function caricaContenuti(): Promise<void> {
      try {
        const [dettaglioCaricato, categorieCaricate] = await Promise.all([
          caricaDettaglioSegnalazione(riferimentoPubblico),
          caricaCategorie(),
        ]);
        if (isAnnullato) {
          return;
        }
        setSegnalazione(dettaglioCaricato);
        setCategorie(categorieCaricate);
      } catch (errore) {
        if (!isAnnullato) {
          setMessaggioErrore(
            leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_CARICAMENTO),
          );
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
  }, [riferimentoPubblico]);

  function apriModifica(): void {
    if (!segnalazione) {
      return;
    }
    setTitoloModifica(segnalazione.titolo);
    setDescrizioneModifica(segnalazione.descrizione);
    setIdCategoriaModifica(segnalazione.idCategoria);
    setMessaggioErroreModifica(null);
    setIsModificaAperta(true);
  }

  async function salvaModifica(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    if (!segnalazione || !token) {
      return;
    }
    if (!titoloModifica.trim() || !descrizioneModifica.trim() || !idCategoriaModifica) {
      setMessaggioErroreModifica(MESSAGGIO_CAMPI_MODIFICA);
      return;
    }
    setIsSalvataggio(true);
    setMessaggioErroreModifica(null);
    try {
      const aggiornata = await modificaSegnalazione(
        segnalazione.id,
        {
          titolo: titoloModifica.trim(),
          descrizione: descrizioneModifica.trim(),
          idCategoria: idCategoriaModifica,
        },
        token,
      );
      setSegnalazione({ ...segnalazione, ...aggiornata });
      setIsModificaAperta(false);
    } catch (errore) {
      setMessaggioErroreModifica(
        leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_MODIFICA),
      );
    } finally {
      setIsSalvataggio(false);
    }
  }

  if (isCaricamento) {
    return <p className="text-sm text-slate-600">Caricamento della segnalazione…</p>;
  }

  if (!segnalazione) {
    return (
      <section className="space-y-4">
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {messaggioErrore ?? MESSAGGIO_ERRORE_CARICAMENTO}
        </p>
        <Link href="/" className="text-sm font-medium text-brand-700 underline">
          Torna alla mappa
        </Link>
      </section>
    );
  }

  const puoModificare =
    profilo !== null &&
    segnalazione.idAutore === profilo.id &&
    segnalazione.stato === 'aperta';

  return (
    <article className="space-y-5">
      <Link href="/" className="text-sm font-medium text-brand-700 underline">
        Torna alla mappa
      </Link>

      <header className="space-y-2">
        <p className="text-sm text-slate-500">
          Segnalazione {segnalazione.riferimentoPubblico}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{segnalazione.titolo}</h1>
          <span
            className="rounded-full px-3 py-1 text-xs font-medium text-white"
            style={{ backgroundColor: COLORI_STATO[segnalazione.stato] }}
          >
            {ETICHETTE_STATO[segnalazione.stato]}
          </span>
        </div>
        <p className="text-sm text-slate-600">
          Categoria: {nomeCategoria(categorie, segnalazione.idCategoria)} · Creata il{' '}
          {formattaDataOra(segnalazione.creataIl)}
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Descrizione</h2>
        <p className="whitespace-pre-line text-sm text-slate-700">
          {segnalazione.descrizione}
        </p>
      </section>

      {segnalazione.idComune === null ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Il comune competente non è ancora coperto. La segnalazione resta pubblica e
          sarà assegnata manualmente.
        </p>
      ) : (
        <p className="text-sm text-slate-600">
          La segnalazione è assegnata al comune competente.
        </p>
      )}

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Posizione</h2>
        <div className="h-80 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <MappaPosizioneDinamica
            latitudine={segnalazione.latitudine}
            longitudine={segnalazione.longitudine}
            stato={segnalazione.stato}
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Cronologia</h2>
        {segnalazione.eventiStato.length === 0 ? (
          <p className="text-sm text-slate-600">
            La cronologia degli eventi non è ancora disponibile.
          </p>
        ) : (
          <ol className="space-y-3">
            {segnalazione.eventiStato.map((evento) => (
              <li
                key={evento.id}
                className="rounded-md border border-slate-200 bg-white px-4 py-3"
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
                </p>
                {evento.notaPubblica ? (
                  <p className="mt-1 text-sm text-slate-700">{evento.notaPubblica}</p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </section>

      {puoModificare ? (
        <section className="space-y-3">
          {isModificaAperta ? (
            <form
              onSubmit={salvaModifica}
              className="space-y-3 rounded-md border border-slate-200 bg-white px-4 py-4"
            >
              <h2 className="text-lg font-semibold">Modifica la segnalazione</h2>
              <div className="space-y-1">
                <label htmlFor="titolo-modifica" className="text-sm font-medium">
                  Titolo
                </label>
                <input
                  id="titolo-modifica"
                  type="text"
                  value={titoloModifica}
                  onChange={(evento) => setTitoloModifica(evento.target.value)}
                  maxLength={200}
                  className={STILE_CAMPO}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="descrizione-modifica" className="text-sm font-medium">
                  Descrizione
                </label>
                <textarea
                  id="descrizione-modifica"
                  value={descrizioneModifica}
                  onChange={(evento) => setDescrizioneModifica(evento.target.value)}
                  rows={5}
                  maxLength={5000}
                  className={STILE_CAMPO}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="categoria-modifica" className="text-sm font-medium">
                  Categoria
                </label>
                <select
                  id="categoria-modifica"
                  value={idCategoriaModifica}
                  onChange={(evento) => setIdCategoriaModifica(evento.target.value)}
                  className={STILE_CAMPO}
                >
                  {categorie.map((categoria) => (
                    <option key={categoria.id} value={categoria.id}>
                      {categoria.nome}
                    </option>
                  ))}
                </select>
              </div>
              {messaggioErroreModifica ? (
                <p
                  role="alert"
                  className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                >
                  {messaggioErroreModifica}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={isSalvataggio}
                  className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSalvataggio ? 'Salvataggio…' : 'Salva le modifiche'}
                </button>
                <button
                  type="button"
                  onClick={() => setIsModificaAperta(false)}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
                >
                  Annulla
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={apriModifica}
              className="rounded-md border border-brand-600 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
            >
              Modifica la segnalazione
            </button>
          )}
        </section>
      ) : null}
    </article>
  );
}
