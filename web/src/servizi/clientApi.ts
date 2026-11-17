type MetodoHttp = 'GET' | 'POST' | 'PATCH';

type OpzioniRichiesta = {
  metodo?: MetodoHttp;
  corpo?: unknown;
  token?: string | null;
  intestazioni?: Record<string, string>;
};

type CorpoProblema = {
  title?: string;
  detail?: string;
};

export const URL_BASE_API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const TITOLO_ERRORE_PREDEFINITO = 'Richiesta non riuscita';
const DETTAGLIO_ERRORE_COMUNICAZIONE =
  'Il servizio non ha risposto come previsto. Riprova tra qualche istante.';

export class ErroreApi extends Error {
  readonly stato: number;
  readonly titolo: string;

  constructor(stato: number, titolo: string, dettaglio: string) {
    super(dettaglio);
    this.name = 'ErroreApi';
    this.stato = stato;
    this.titolo = titolo;
  }
}

export function leggiMessaggioErrore(
  errore: unknown,
  messaggioPredefinito: string,
): string {
  return errore instanceof ErroreApi ? errore.message : messaggioPredefinito;
}

export async function richiediApi<TRisposta>(
  percorso: string,
  opzioni: OpzioniRichiesta = {},
): Promise<TRisposta> {
  const intestazioni: Record<string, string> = {
    Accept: 'application/json',
    ...opzioni.intestazioni,
  };
  if (opzioni.corpo !== undefined) {
    intestazioni['Content-Type'] = 'application/json';
  }
  if (opzioni.token) {
    intestazioni.Authorization = `Bearer ${opzioni.token}`;
  }

  const risposta = await fetch(`${URL_BASE_API}${percorso}`, {
    method: opzioni.metodo ?? 'GET',
    headers: intestazioni,
    body: opzioni.corpo === undefined ? undefined : JSON.stringify(opzioni.corpo),
    cache: 'no-store',
  });

  if (!risposta.ok) {
    throw await costruisciErroreApi(risposta);
  }
  if (risposta.status === 204) {
    return undefined as TRisposta;
  }
  return (await risposta.json()) as TRisposta;
}

async function costruisciErroreApi(risposta: Response): Promise<ErroreApi> {
  const testo = await risposta.text();
  if (!testo) {
    return new ErroreApi(
      risposta.status,
      TITOLO_ERRORE_PREDEFINITO,
      DETTAGLIO_ERRORE_COMUNICAZIONE,
    );
  }
  try {
    const problema = JSON.parse(testo) as CorpoProblema;
    return new ErroreApi(
      risposta.status,
      problema.title ?? TITOLO_ERRORE_PREDEFINITO,
      problema.detail ?? DETTAGLIO_ERRORE_COMUNICAZIONE,
    );
  } catch {
    return new ErroreApi(
      risposta.status,
      TITOLO_ERRORE_PREDEFINITO,
      DETTAGLIO_ERRORE_COMUNICAZIONE,
    );
  }
}
