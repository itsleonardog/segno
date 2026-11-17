'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FormEvent } from 'react';
import { useEffect, useRef, useState } from 'react';

import { usaAutenticazione } from '../contesti/ContestoAutenticazione';
import type { CategoriaSegnalazione } from '../dominio/segnalazione';
import { caricaCategorie } from '../servizi/categorie';
import { leggiMessaggioErrore } from '../servizi/clientApi';
import type { EsitoRisoluzioneComune } from '../servizi/geografia';
import { risolviComune } from '../servizi/geografia';
import { inviaSegnalazione } from '../servizi/segnalazioni';

import type { PosizioneMappa } from './MappaSelezionePunto';
import { MappaSelezionePuntoDinamica } from './MappaSelezionePuntoDinamica';

const MESSAGGIO_PUNTO_MANCANTE =
  'Seleziona un punto sulla mappa prima di inviare la segnalazione.';
const MESSAGGIO_CATEGORIA_MANCANTE = 'Scegli una categoria per la segnalazione.';
const MESSAGGIO_TITOLO_MANCANTE = 'Indica un titolo per la segnalazione.';
const MESSAGGIO_DESCRIZIONE_MANCANTE = 'Descrivi il problema che vuoi segnalare.';
const MESSAGGIO_ERRORE_INVIO =
  'Non è stato possibile inviare la segnalazione. Controlla i dati e riprova.';
const MESSAGGIO_ERRORE_VERIFICA =
  'Non è stato possibile verificare il comune del punto scelto. Puoi riprovare oppure inviare comunque la segnalazione.';
const MESSAGGIO_ERRORE_CATEGORIE =
  'Non è stato possibile caricare le categorie. Aggiorna la pagina per riprovare.';

const STILE_CAMPO =
  'w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600';

export function ModuloSegnalazione() {
  const router = useRouter();
  const { token, isCaricamento } = usaAutenticazione();
  const [posizione, setPosizione] = useState<PosizioneMappa | null>(null);
  const [esitoComune, setEsitoComune] = useState<EsitoRisoluzioneComune | null>(null);
  const [isVerificaComune, setIsVerificaComune] = useState(false);
  const [messaggioErroreComune, setMessaggioErroreComune] = useState<string | null>(
    null,
  );
  const [categorie, setCategorie] = useState<CategoriaSegnalazione[]>([]);
  const [messaggioErroreCategorie, setMessaggioErroreCategorie] = useState<
    string | null
  >(null);
  const [titolo, setTitolo] = useState('');
  const [descrizione, setDescrizione] = useState('');
  const [idCategoria, setIdCategoria] = useState('');
  const [isInvio, setIsInvio] = useState(false);
  const [messaggioErroreInvio, setMessaggioErroreInvio] = useState<string | null>(null);
  const ultimaVerificaComune = useRef(0);

  useEffect(() => {
    let isAnnullato = false;

    async function caricaElencoCategorie(): Promise<void> {
      try {
        const categorieCaricate = await caricaCategorie();
        if (!isAnnullato) {
          setCategorie(categorieCaricate);
        }
      } catch {
        if (!isAnnullato) {
          setMessaggioErroreCategorie(MESSAGGIO_ERRORE_CATEGORIE);
        }
      }
    }

    void caricaElencoCategorie();
    return () => {
      isAnnullato = true;
    };
  }, []);

  async function selezionaPunto(
    latitudine: number,
    longitudine: number,
  ): Promise<void> {
    const identificativoVerifica = ultimaVerificaComune.current + 1;
    ultimaVerificaComune.current = identificativoVerifica;
    setPosizione({ latitudine, longitudine });
    setEsitoComune(null);
    setMessaggioErroreComune(null);
    setIsVerificaComune(true);
    try {
      const esito = await risolviComune(latitudine, longitudine);
      if (ultimaVerificaComune.current === identificativoVerifica) {
        setEsitoComune(esito);
      }
    } catch {
      if (ultimaVerificaComune.current === identificativoVerifica) {
        setMessaggioErroreComune(MESSAGGIO_ERRORE_VERIFICA);
      }
    } finally {
      if (ultimaVerificaComune.current === identificativoVerifica) {
        setIsVerificaComune(false);
      }
    }
  }

  async function invia(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setMessaggioErroreInvio(null);
    if (!token) {
      setMessaggioErroreInvio(
        'Per inviare una segnalazione devi accedere con il tuo account.',
      );
      return;
    }
    if (!posizione) {
      setMessaggioErroreInvio(MESSAGGIO_PUNTO_MANCANTE);
      return;
    }
    if (!titolo.trim()) {
      setMessaggioErroreInvio(MESSAGGIO_TITOLO_MANCANTE);
      return;
    }
    if (!descrizione.trim()) {
      setMessaggioErroreInvio(MESSAGGIO_DESCRIZIONE_MANCANTE);
      return;
    }
    if (!idCategoria) {
      setMessaggioErroreInvio(MESSAGGIO_CATEGORIA_MANCANTE);
      return;
    }

    setIsInvio(true);
    try {
      const segnalazione = await inviaSegnalazione(
        {
          titolo: titolo.trim(),
          descrizione: descrizione.trim(),
          idCategoria,
          latitudine: posizione.latitudine,
          longitudine: posizione.longitudine,
          indirizzo: null,
        },
        token,
      );
      router.push(`/reports/${segnalazione.riferimentoPubblico}`);
    } catch (errore) {
      setMessaggioErroreInvio(leggiMessaggioErrore(errore, MESSAGGIO_ERRORE_INVIO));
    } finally {
      setIsInvio(false);
    }
  }

  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Segnala un problema</h1>
        <p className="text-sm text-slate-600">
          Seleziona il punto sulla mappa, indica la categoria e descrivi il problema. La
          segnalazione resta pubblica e sarà inviata al comune competente.
        </p>
      </header>

      {!isCaricamento && !token ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Per inviare una segnalazione devi accedere.{' '}
          <Link href="/login" className="font-medium underline">
            Accedi
          </Link>{' '}
          oppure{' '}
          <Link href="/register" className="font-medium underline">
            registrati
          </Link>
          .
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-[420px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:h-[640px]">
          <MappaSelezionePuntoDinamica
            posizione={posizione}
            onSeleziona={selezionaPunto}
          />
        </div>

        <form onSubmit={invia} className="space-y-4">
          <div className="min-h-[68px] rounded-md border border-slate-200 bg-white px-4 py-3 text-sm">
            {isVerificaComune ? (
              <p className="text-slate-600">Verifica del comune competente in corso…</p>
            ) : esitoComune?.isFuoriCopertura ? (
              <p className="font-medium text-amber-800">
                Questo punto non è ancora coperto da un comune. La segnalazione resta
                pubblica e sarà assegnata manualmente.
              </p>
            ) : esitoComune?.comune ? (
              <p className="text-slate-700">
                Comune competente:{' '}
                <span className="font-medium">{esitoComune.comune.nome}</span>
              </p>
            ) : messaggioErroreComune ? (
              <p className="font-medium text-amber-800">{messaggioErroreComune}</p>
            ) : (
              <p className="text-slate-600">
                Clicca sulla mappa per scegliere il punto da segnalare.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label htmlFor="titolo" className="text-sm font-medium">
              Titolo
            </label>
            <input
              id="titolo"
              type="text"
              value={titolo}
              onChange={(evento) => setTitolo(evento.target.value)}
              maxLength={200}
              className={STILE_CAMPO}
              placeholder="Lampione spento in via Roma"
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="descrizione" className="text-sm font-medium">
              Descrizione
            </label>
            <textarea
              id="descrizione"
              value={descrizione}
              onChange={(evento) => setDescrizione(evento.target.value)}
              rows={5}
              maxLength={5000}
              className={STILE_CAMPO}
              placeholder="Descrivi il problema e il punto in cui si trova."
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="categoria" className="text-sm font-medium">
              Categoria
            </label>
            <select
              id="categoria"
              value={idCategoria}
              onChange={(evento) => setIdCategoria(evento.target.value)}
              className={STILE_CAMPO}
            >
              <option value="">Scegli una categoria</option>
              {categorie.map((categoria) => (
                <option key={categoria.id} value={categoria.id}>
                  {categoria.nome}
                </option>
              ))}
            </select>
            {messaggioErroreCategorie ? (
              <p className="text-sm text-amber-800">{messaggioErroreCategorie}</p>
            ) : null}
          </div>

          {messaggioErroreInvio ? (
            <p
              role="alert"
              className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {messaggioErroreInvio}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={isInvio || !token}
            className="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isInvio ? 'Invio in corso…' : 'Invia la segnalazione'}
          </button>
        </form>
      </div>
    </section>
  );
}
