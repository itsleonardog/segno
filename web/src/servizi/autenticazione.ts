import type { ProfiloUtente } from '../dominio/utente';

import { richiediApi } from './clientApi';

export type Sessione = {
  tokenAccesso: string;
  tokenRinnovo: string;
  secondiAllaScadenza: number;
};

export type DatiRegistrazione = {
  email: string;
  nickname: string;
  password: string;
};

type SessioneApi = {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
};

type ProfiloApi = {
  id: string;
  nickname: string;
  email_masked: string;
};

type RegistrazioneApi = {
  id: string;
  nickname: string;
  email_masked: string;
  email_verified_at: string | null;
};

const VERSIONE_PRIVACY = '1';
const VERSIONE_TERMINI = '1';

export async function accedi(email: string, password: string): Promise<Sessione> {
  const sessioneApi = await richiediApi<SessioneApi>('/v1/auth/login', {
    metodo: 'POST',
    corpo: { email, password },
  });
  return {
    tokenAccesso: sessioneApi.access_token,
    tokenRinnovo: sessioneApi.refresh_token,
    secondiAllaScadenza: sessioneApi.expires_in,
  };
}

export async function registra(dati: DatiRegistrazione): Promise<void> {
  await richiediApi<RegistrazioneApi>('/v1/auth/register', {
    metodo: 'POST',
    corpo: {
      email: dati.email,
      nickname: dati.nickname,
      password: dati.password,
      privacy_policy_version: VERSIONE_PRIVACY,
      tos_version: VERSIONE_TERMINI,
    },
  });
}

export async function caricaProfilo(token: string): Promise<ProfiloUtente> {
  const profiloApi = await richiediApi<ProfiloApi>('/v1/me', { token });
  return mappaProfilo(profiloApi);
}

export async function esci(token: string, tokenRinnovo: string): Promise<void> {
  await richiediApi<void>('/v1/auth/logout', {
    metodo: 'POST',
    token,
    corpo: { refresh_token: tokenRinnovo },
  });
}

function mappaProfilo(profiloApi: ProfiloApi): ProfiloUtente {
  return {
    id: profiloApi.id,
    nickname: profiloApi.nickname,
    emailMascherata: profiloApi.email_masked,
  };
}
