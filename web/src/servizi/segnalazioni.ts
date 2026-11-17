import type {
  DatiModificaSegnalazione,
  DatiNuovaSegnalazione,
  DettaglioSegnalazione,
  EventoStatoSegnalazione,
  Segnalazione,
} from '../dominio/segnalazione';
import { mappaStatoApi } from '../dominio/segnalazione';

import { richiediApi } from './clientApi';

type SegnalazioneApi = {
  id: string;
  public_ref: string;
  municipality_id: string | null;
  author_id: string | null;
  category_id: string;
  title: string;
  description: string;
  lat: number;
  lng: number;
  address_text: string | null;
  status: string;
  visibility: string;
  dispatch_state: string;
  boundary_ambiguous: boolean;
  created_at: string;
};

type EventoStatoApi = {
  id: string;
  from_status: string | null;
  to_status: string;
  actor_type: string;
  note_public: string | null;
  created_at: string;
};

type ElencoSegnalazioniApi = {
  items: SegnalazioneApi[];
  next_cursor: string | null;
};

export async function caricaSegnalazioniPubbliche(): Promise<Segnalazione[]> {
  const elencoApi = await richiediApi<ElencoSegnalazioniApi>('/v1/reports?limit=100');
  return elencoApi.items.map(mappaSegnalazione);
}

export async function caricaDettaglioSegnalazione(
  riferimentoPubblico: string,
): Promise<DettaglioSegnalazione> {
  const segnalazioneApi = await richiediApi<SegnalazioneApi>(
    `/v1/reports/${encodeURIComponent(riferimentoPubblico)}`,
  );
  const eventiApi = await richiediApi<EventoStatoApi[]>(
    `/v1/reports/${segnalazioneApi.id}/status-events`,
  );
  return {
    ...mappaSegnalazione(segnalazioneApi),
    eventiStato: eventiApi.map(mappaEventoStato),
  };
}

export async function inviaSegnalazione(
  dati: DatiNuovaSegnalazione,
  token: string,
): Promise<Segnalazione> {
  const segnalazioneApi = await richiediApi<SegnalazioneApi>('/v1/reports', {
    metodo: 'POST',
    token,
    intestazioni: { 'Idempotency-Key': crypto.randomUUID() },
    corpo: {
      title: dati.titolo,
      description: dati.descrizione,
      category_id: dati.idCategoria,
      lat: dati.latitudine,
      lng: dati.longitudine,
      address_text: dati.indirizzo,
    },
  });
  return mappaSegnalazione(segnalazioneApi);
}

export async function modificaSegnalazione(
  id: string,
  dati: DatiModificaSegnalazione,
  token: string,
): Promise<Segnalazione> {
  const corpo: Record<string, string> = {};
  if (dati.titolo !== undefined) {
    corpo.title = dati.titolo;
  }
  if (dati.descrizione !== undefined) {
    corpo.description = dati.descrizione;
  }
  if (dati.idCategoria !== undefined) {
    corpo.category_id = dati.idCategoria;
  }
  const segnalazioneApi = await richiediApi<SegnalazioneApi>(`/v1/reports/${id}`, {
    metodo: 'PATCH',
    token,
    corpo,
  });
  return mappaSegnalazione(segnalazioneApi);
}

function mappaSegnalazione(segnalazioneApi: SegnalazioneApi): Segnalazione {
  return {
    id: segnalazioneApi.id,
    riferimentoPubblico: segnalazioneApi.public_ref,
    idComune: segnalazioneApi.municipality_id,
    idAutore: segnalazioneApi.author_id,
    idCategoria: segnalazioneApi.category_id,
    titolo: segnalazioneApi.title,
    descrizione: segnalazioneApi.description,
    latitudine: segnalazioneApi.lat,
    longitudine: segnalazioneApi.lng,
    indirizzo: segnalazioneApi.address_text,
    stato: mappaStatoApi(segnalazioneApi.status),
    visibilita: segnalazioneApi.visibility,
    statoDispatch: segnalazioneApi.dispatch_state,
    isConfineAmbiguo: segnalazioneApi.boundary_ambiguous,
    creataIl: segnalazioneApi.created_at,
  };
}

function mappaEventoStato(eventoApi: EventoStatoApi): EventoStatoSegnalazione {
  return {
    id: eventoApi.id,
    statoPrecedente: eventoApi.from_status
      ? mappaStatoApi(eventoApi.from_status)
      : null,
    statoSuccessivo: mappaStatoApi(eventoApi.to_status),
    tipoAttore: eventoApi.actor_type,
    notaPubblica: eventoApi.note_public,
    creatoIl: eventoApi.created_at,
  };
}
