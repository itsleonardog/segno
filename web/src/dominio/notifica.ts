export type Notifica = {
  id: string;
  idSegnalazione: string | null;
  tipo: string;
  canale: string;
  dati: Record<string, unknown>;
  lettaIl: string | null;
  creataIl: string;
};

const ETICHETTE_STATO: Record<string, string> = {
  open: 'Aperta',
  in_progress: 'In corso',
  resolved: 'Risolta',
  closed: 'Chiusa',
};

export function etichettaStatoNotifica(valore: unknown): string {
  return typeof valore === 'string'
    ? (ETICHETTE_STATO[valore] ?? 'Aggiornata')
    : 'Aggiornata';
}

export function riferimentoPubblicoNotifica(notifica: Notifica): string | null {
  const riferimento = notifica.dati.public_ref;
  return typeof riferimento === 'string' ? riferimento : null;
}

export function linkSegnalazioneNotifica(notifica: Notifica): string | null {
  const riferimento = riferimentoPubblicoNotifica(notifica);
  return riferimento === null ? null : `/reports/${encodeURIComponent(riferimento)}`;
}
