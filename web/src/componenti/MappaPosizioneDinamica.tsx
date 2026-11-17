'use client';

import dynamic from 'next/dynamic';

export const MappaPosizioneDinamica = dynamic(
  () => import('./MappaPosizione').then((modulo) => modulo.MappaPosizione),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center bg-slate-100 text-sm text-slate-600">
        Caricamento della mappa…
      </div>
    ),
  },
);
