import type { CategoriaSegnalazione } from '../dominio/segnalazione';

import { richiediApi } from './clientApi';

type CategoriaApi = {
  id: string;
  slug: string;
  name_i18n: Record<string, string>;
  icon: string | null;
};

const NOME_CATEGORIA_PREDEFINITO = 'Categoria non disponibile';

export async function caricaCategorie(): Promise<CategoriaSegnalazione[]> {
  const categorieApi = await richiediApi<CategoriaApi[]>('/v1/categories');
  return categorieApi.map(mappaCategoria);
}

export function nomeCategoria(
  categorie: CategoriaSegnalazione[],
  idCategoria: string,
): string {
  return (
    categorie.find((categoria) => categoria.id === idCategoria)?.nome ??
    NOME_CATEGORIA_PREDEFINITO
  );
}

function mappaCategoria(categoriaApi: CategoriaApi): CategoriaSegnalazione {
  return {
    id: categoriaApi.id,
    slug: categoriaApi.slug,
    nome: categoriaApi.name_i18n.it ?? categoriaApi.slug,
    icona: categoriaApi.icon,
  };
}
