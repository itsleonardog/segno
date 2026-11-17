'use client';

import type { LatLngExpression } from 'leaflet';
import Link from 'next/link';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';

import type { CategoriaSegnalazione, Segnalazione } from '../dominio/segnalazione';
import { ETICHETTE_STATO } from '../dominio/segnalazione';
import { nomeCategoria } from '../servizi/categorie';

import { creaIconaMarker } from './iconaMarker';

type Props = {
  segnalazioni: Segnalazione[];
  categorie: CategoriaSegnalazione[];
};

const CENTRO_ITALIA: LatLngExpression = [42.5, 12.5];
const ZOOM_ITALIA = 6;

export function MappaSegnalazioni({ segnalazioni, categorie }: Props) {
  return (
    <MapContainer
      center={CENTRO_ITALIA}
      zoom={ZOOM_ITALIA}
      className="mappa-leaflet"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {segnalazioni.map((segnalazione) => (
        <Marker
          key={segnalazione.id}
          position={[segnalazione.latitudine, segnalazione.longitudine]}
          icon={creaIconaMarker(segnalazione.stato)}
        >
          <Popup>
            <div className="space-y-1">
              <p className="font-semibold text-slate-900">{segnalazione.titolo}</p>
              <p className="text-xs text-slate-600">
                {nomeCategoria(categorie, segnalazione.idCategoria)}
              </p>
              <p className="text-xs text-slate-600">
                Stato: {ETICHETTE_STATO[segnalazione.stato]}
              </p>
              <Link
                href={`/reports/${segnalazione.riferimentoPubblico}`}
                className="text-sm font-medium text-brand-700 underline"
              >
                Apri la segnalazione
              </Link>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
