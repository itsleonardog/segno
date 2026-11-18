import type { Notifica } from '../dominio/notifica';

import { richiediApi } from './clientApi';

type NotificaApi = {
  id: string;
  report_id: string | null;
  type: string;
  channel: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
};

type ElencoNotificheApi = {
  items: NotificaApi[];
  next_cursor: string | null;
  unread_count: number;
};

type EsitoLetturaApi = {
  aggiornate: number;
};

export type ElencoNotifiche = {
  notifiche: Notifica[];
  cursoreSuccessivo: string | null;
  conteggioNonLette: number;
};

export async function caricaNotifiche(
  token: string,
  limite = 20,
): Promise<ElencoNotifiche> {
  const elencoApi = await richiediApi<ElencoNotificheApi>(
    `/v1/notifications?limit=${limite}`,
    { token },
  );
  return {
    notifiche: elencoApi.items.map(mappaNotifica),
    cursoreSuccessivo: elencoApi.next_cursor,
    conteggioNonLette: elencoApi.unread_count,
  };
}

export async function segnaNotificaLetta(
  token: string,
  notificaId: string,
): Promise<void> {
  await richiediApi<{ letta: boolean }>(`/v1/notifications/${notificaId}/read`, {
    metodo: 'PATCH',
    token,
  });
}

export async function segnaTutteNotificheLette(token: string): Promise<number> {
  const esito = await richiediApi<EsitoLetturaApi>('/v1/notifications/read-all', {
    metodo: 'POST',
    token,
  });
  return esito.aggiornate;
}

function mappaNotifica(notificaApi: NotificaApi): Notifica {
  return {
    id: notificaApi.id,
    idSegnalazione: notificaApi.report_id,
    tipo: notificaApi.type,
    canale: notificaApi.channel,
    dati: notificaApi.payload,
    lettaIl: notificaApi.read_at,
    creataIl: notificaApi.created_at,
  };
}
