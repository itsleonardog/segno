'use client';

import type { ReactNode } from 'react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import type { ProfiloUtente } from '../dominio/utente';
import {
  accedi as accediApi,
  caricaProfilo,
  esci as esciApi,
  registra as registraApi,
} from '../servizi/autenticazione';
import type { DatiRegistrazione } from '../servizi/autenticazione';

type StatoAutenticazione = {
  token: string | null;
  profilo: ProfiloUtente | null;
  isCaricamento: boolean;
  accedi: (email: string, password: string) => Promise<void>;
  registra: (dati: DatiRegistrazione) => Promise<void>;
  esci: () => void;
};

const CHIAVE_TOKEN_ACCESSO = 'segno.token_accesso';
const CHIAVE_TOKEN_RINNOVO = 'segno.token_rinnovo';
const MESSAGGIO_CONTESTO_ASSENTE =
  'usaAutenticazione va chiamato dentro ProviderAutenticazione.';

const ContestoAutenticazione = createContext<StatoAutenticazione | null>(null);

export function ProviderAutenticazione({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [profilo, setProfilo] = useState<ProfiloUtente | null>(null);
  const [isCaricamento, setIsCaricamento] = useState(true);

  useEffect(() => {
    let isAnnullato = false;

    async function ripristinaSessione(): Promise<void> {
      const tokenSalvato = window.localStorage.getItem(CHIAVE_TOKEN_ACCESSO);
      if (!tokenSalvato) {
        setIsCaricamento(false);
        return;
      }
      try {
        const profiloCaricato = await caricaProfilo(tokenSalvato);
        if (isAnnullato) {
          return;
        }
        setToken(tokenSalvato);
        setProfilo(profiloCaricato);
      } catch {
        // Il token salvato non è più valido: si riparte da una sessione anonima.
        rimuoviSessioneSalvata();
      } finally {
        if (!isAnnullato) {
          setIsCaricamento(false);
        }
      }
    }

    void ripristinaSessione();
    return () => {
      isAnnullato = true;
    };
  }, []);

  const accedi = useCallback(async (email: string, password: string) => {
    const sessione = await accediApi(email, password);
    const profiloCaricato = await caricaProfilo(sessione.tokenAccesso);
    salvaSessione(sessione.tokenAccesso, sessione.tokenRinnovo);
    setToken(sessione.tokenAccesso);
    setProfilo(profiloCaricato);
  }, []);

  const registra = useCallback(
    async (dati: DatiRegistrazione) => {
      await registraApi(dati);
      await accedi(dati.email, dati.password);
    },
    [accedi],
  );

  const esci = useCallback(() => {
    const tokenRinnovo = window.localStorage.getItem(CHIAVE_TOKEN_RINNOVO);
    rimuoviSessioneSalvata();
    setToken(null);
    setProfilo(null);
    if (token && tokenRinnovo) {
      // La sessione locale è già chiusa: la revoca sul server resta un tentativo.
      void esciApi(token, tokenRinnovo).catch(() => {
        // Nessuna azione ulteriore: l'utente ha già perso l'accesso in locale.
      });
    }
  }, [token]);

  const valore = useMemo(
    () => ({ token, profilo, isCaricamento, accedi, registra, esci }),
    [token, profilo, isCaricamento, accedi, registra, esci],
  );

  return (
    <ContestoAutenticazione.Provider value={valore}>
      {children}
    </ContestoAutenticazione.Provider>
  );
}

export function usaAutenticazione(): StatoAutenticazione {
  const contesto = useContext(ContestoAutenticazione);
  if (contesto === null) {
    throw new Error(MESSAGGIO_CONTESTO_ASSENTE);
  }
  return contesto;
}

function salvaSessione(tokenAccesso: string, tokenRinnovo: string): void {
  window.localStorage.setItem(CHIAVE_TOKEN_ACCESSO, tokenAccesso);
  window.localStorage.setItem(CHIAVE_TOKEN_RINNOVO, tokenRinnovo);
}

function rimuoviSessioneSalvata(): void {
  window.localStorage.removeItem(CHIAVE_TOKEN_ACCESSO);
  window.localStorage.removeItem(CHIAVE_TOKEN_RINNOVO);
}
