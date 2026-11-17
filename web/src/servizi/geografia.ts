import { richiediApi } from './clientApi';

export type ComuneRisolto = {
  id: string;
  slug: string;
  nome: string;
  priorita: number;
  isAmbiguo: boolean;
};

export type EsitoRisoluzioneComune = {
  comune: ComuneRisolto | null;
  isFuoriCopertura: boolean;
};

type ComuneApi = {
  id: string;
  slug: string;
  name: string;
  priority: number;
  is_ambiguo: boolean;
};

type RisoluzioneApi = {
  comune: ComuneApi | null;
  fuori_copertura: boolean;
};

export async function risolviComune(
  latitudine: number,
  longitudine: number,
): Promise<EsitoRisoluzioneComune> {
  const parametri = new URLSearchParams({
    lat: String(latitudine),
    lng: String(longitudine),
  });
  const risoluzioneApi = await richiediApi<RisoluzioneApi>(
    `/v1/geo/resolve?${parametri.toString()}`,
  );
  return {
    comune: risoluzioneApi.comune ? mappaComune(risoluzioneApi.comune) : null,
    isFuoriCopertura: risoluzioneApi.fuori_copertura,
  };
}

function mappaComune(comuneApi: ComuneApi): ComuneRisolto {
  return {
    id: comuneApi.id,
    slug: comuneApi.slug,
    nome: comuneApi.name,
    priorita: comuneApi.priority,
    isAmbiguo: comuneApi.is_ambiguo,
  };
}
