import type {
  DettaglioAmministrazione,
  EventoStatoAmministrazione,
  FallimentoDispatch,
  NotaInterna,
  TentativoDispatch,
} from '../dominio/amministrazione';
import type { Segnalazione } from '../dominio/segnalazione';
import { mappaStatoApi } from '../dominio/segnalazione';

import { richiediApi } from './clientApi';
import type { SegnalazioneApi } from './segnalazioni';
import { mappaSegnalazione } from './segnalazioni';

type EventoStatoAmministrazioneApi = {
  id: string;
  from_status: string | null;
  to_status: string;
  actor_type: string;
  note_public: string | null;
  is_public: boolean;
  created_at: string;
};

type TentativoDispatchApi = {
  id: string;
  channel: string;
  attempt_no: number;
  status: string;
  provider_request_id: string | null;
  http_status: number | null;
  error_code: string | null;
  error_detail_redacted: string | null;
  next_attempt_at: string | null;
  succeeded_at: string | null;
  created_at: string;
};

type NotaInternaApi = {
  id: string;
  author_id: string | null;
  body: string;
  created_at: string;
};

type DettaglioAmministrazioneApi = SegnalazioneApi & {
  status_events: EventoStatoAmministrazioneApi[];
  dispatch_history: TentativoDispatchApi[];
  internal_notes: NotaInternaApi[];
};

type ElencoAmministrazioneApi = {
  items: SegnalazioneApi[];
  next_cursor: string | null;
};

type FallimentoDispatchApi = {
  report_id: string;
  public_ref: string;
  title: string;
  dispatch: TentativoDispatchApi;
};

type ElencoFallimentiApi = {
  items: FallimentoDispatchApi[];
};

export async function caricaSegnalazioniAmministrazione(
  token: string,
  stato: string | null,
): Promise<Segnalazione[]> {
  const parametri = new URLSearchParams({ limit: '100' });
  if (stato) {
    parametri.set('status', stato);
  }
  const elenco = await richiediApi<ElencoAmministrazioneApi>(
    `/v1/admin/reports?${parametri.toString()}`,
    { token },
  );
  return elenco.items.map(mappaSegnalazione);
}

export async function caricaDettaglioAmministrazione(
  token: string,
  idSegnalazione: string,
): Promise<DettaglioAmministrazione> {
  const dettaglioApi = await richiediApi<DettaglioAmministrazioneApi>(
    `/v1/admin/reports/${idSegnalazione}`,
    { token },
  );
  return {
    ...mappaSegnalazione(dettaglioApi),
    eventiStato: dettaglioApi.status_events.map(mappaEventoStato),
    storicoDispatch: dettaglioApi.dispatch_history.map(mappaTentativo),
    noteInterne: dettaglioApi.internal_notes.map(mappaNota),
  };
}

export async function aggiungiNotaInterna(
  token: string,
  idSegnalazione: string,
  testo: string,
): Promise<NotaInterna> {
  const notaApi = await richiediApi<NotaInternaApi>(
    `/v1/admin/reports/${idSegnalazione}/comments`,
    {
      metodo: 'POST',
      token,
      corpo: { body: testo },
    },
  );
  return mappaNota(notaApi);
}

export async function caricaFallimentiDispatch(
  token: string,
): Promise<FallimentoDispatch[]> {
  const elenco = await richiediApi<ElencoFallimentiApi>('/v1/admin/dispatch-failures', {
    token,
  });
  return elenco.items.map((fallimento) => ({
    idSegnalazione: fallimento.report_id,
    riferimentoPubblico: fallimento.public_ref,
    titolo: fallimento.title,
    dispatch: mappaTentativo(fallimento.dispatch),
  }));
}

export async function riprovaDispatch(
  token: string,
  idSegnalazione: string,
): Promise<void> {
  await richiediApi<{ event_id: string }>(
    `/v1/admin/reports/${idSegnalazione}/dispatch/retry`,
    {
      metodo: 'POST',
      token,
    },
  );
}

function mappaEventoStato(
  eventoApi: EventoStatoAmministrazioneApi,
): EventoStatoAmministrazione {
  return {
    id: eventoApi.id,
    statoPrecedente: eventoApi.from_status
      ? mappaStatoApi(eventoApi.from_status)
      : null,
    statoSuccessivo: mappaStatoApi(eventoApi.to_status),
    tipoAttore: eventoApi.actor_type,
    notaPubblica: eventoApi.note_public,
    isPubblica: eventoApi.is_public,
    creatoIl: eventoApi.created_at,
  };
}

function mappaTentativo(tentativoApi: TentativoDispatchApi): TentativoDispatch {
  return {
    id: tentativoApi.id,
    canale: tentativoApi.channel,
    numeroTentativo: tentativoApi.attempt_no,
    stato: tentativoApi.status,
    identificativoProvider: tentativoApi.provider_request_id,
    statoHttp: tentativoApi.http_status,
    codiceErrore: tentativoApi.error_code,
    dettaglioErrore: tentativoApi.error_detail_redacted,
    prossimoTentativoIl: tentativoApi.next_attempt_at,
    riuscitoIl: tentativoApi.succeeded_at,
    creatoIl: tentativoApi.created_at,
  };
}

function mappaNota(notaApi: NotaInternaApi): NotaInterna {
  return {
    id: notaApi.id,
    idAutore: notaApi.author_id,
    testo: notaApi.body,
    creataIl: notaApi.created_at,
  };
}
