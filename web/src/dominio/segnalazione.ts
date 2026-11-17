export type StatoSegnalazione =
  'aperta' | 'in_corso' | 'risolta' | 'chiusa' | 'sconosciuto';

export type CategoriaSegnalazione = {
  id: string;
  slug: string;
  nome: string;
  icona: string | null;
};

export type Segnalazione = {
  id: string;
  riferimentoPubblico: string;
  idComune: string | null;
  idAutore: string | null;
  idCategoria: string;
  titolo: string;
  descrizione: string;
  latitudine: number;
  longitudine: number;
  indirizzo: string | null;
  stato: StatoSegnalazione;
  visibilita: string;
  statoDispatch: string;
  isConfineAmbiguo: boolean;
  creataIl: string;
};

export type EventoStatoSegnalazione = {
  id: string;
  statoPrecedente: StatoSegnalazione | null;
  statoSuccessivo: StatoSegnalazione;
  tipoAttore: string;
  notaPubblica: string | null;
  creatoIl: string;
};

export type DettaglioSegnalazione = Segnalazione & {
  eventiStato: EventoStatoSegnalazione[];
};

export type DatiNuovaSegnalazione = {
  titolo: string;
  descrizione: string;
  idCategoria: string;
  latitudine: number;
  longitudine: number;
  indirizzo: string | null;
};

export type DatiModificaSegnalazione = {
  titolo?: string;
  descrizione?: string;
  idCategoria?: string;
};

const STATI_SEGNALAZIONE_PER_API: Record<string, StatoSegnalazione> = {
  open: 'aperta',
  in_progress: 'in_corso',
  resolved: 'risolta',
  closed: 'chiusa',
};

export const ETICHETTE_STATO: Record<StatoSegnalazione, string> = {
  aperta: 'Aperta',
  in_corso: 'In corso',
  risolta: 'Risolta',
  chiusa: 'Chiusa',
  sconosciuto: 'Non riconosciuto',
};

export const COLORI_STATO: Record<StatoSegnalazione, string> = {
  aperta: '#dc2626',
  in_corso: '#eab308',
  risolta: '#16a34a',
  chiusa: '#6b7280',
  sconosciuto: '#6b7280',
};

const ETICHETTE_ATTORE: Record<string, string> = {
  citizen: 'Cittadino',
  municipality: 'Comune',
  moderator: 'Moderazione',
  system: 'Sistema',
  open311_sync: 'Sincronizzazione Open311',
};

export function mappaStatoApi(statoApi: string): StatoSegnalazione {
  return STATI_SEGNALAZIONE_PER_API[statoApi] ?? 'sconosciuto';
}

export function etichettaAttore(tipoAttore: string): string {
  return ETICHETTE_ATTORE[tipoAttore] ?? 'Attore non riconosciuto';
}
