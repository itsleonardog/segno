import type { Segnalazione, StatoSegnalazione } from './segnalazione';

export type EventoStatoAmministrazione = {
  id: string;
  statoPrecedente: StatoSegnalazione | null;
  statoSuccessivo: StatoSegnalazione;
  tipoAttore: string;
  notaPubblica: string | null;
  isPubblica: boolean;
  creatoIl: string;
};

export type TentativoDispatch = {
  id: string;
  canale: string;
  numeroTentativo: number;
  stato: string;
  identificativoProvider: string | null;
  statoHttp: number | null;
  codiceErrore: string | null;
  dettaglioErrore: string | null;
  prossimoTentativoIl: string | null;
  riuscitoIl: string | null;
  creatoIl: string;
};

export type NotaInterna = {
  id: string;
  idAutore: string | null;
  testo: string;
  creataIl: string;
};

export type DettaglioAmministrazione = Segnalazione & {
  eventiStato: EventoStatoAmministrazione[];
  storicoDispatch: TentativoDispatch[];
  noteInterne: NotaInterna[];
};

export type FallimentoDispatch = {
  idSegnalazione: string;
  riferimentoPubblico: string;
  titolo: string;
  dispatch: TentativoDispatch;
};
