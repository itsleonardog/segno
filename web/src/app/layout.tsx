import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import 'leaflet/dist/leaflet.css';
import { Intestazione } from '../componenti/Intestazione';
import { ProviderAutenticazione } from '../contesti/ContestoAutenticazione';

import './globals.css';

export const metadata: Metadata = {
  title: 'Segnalazione civica',
  description: 'Segnala un problema urbano e segui lo stato della segnalazione.',
};

export default function LayoutRadice({ children }: { children: ReactNode }) {
  return (
    <html lang="it">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <ProviderAutenticazione>
          <Intestazione />
          <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">{children}</main>
        </ProviderAutenticazione>
      </body>
    </html>
  );
}
