'use client';

import type { LatLngExpression } from 'leaflet';
import { MapContainer, Marker, TileLayer } from 'react-leaflet';

import type { StatoSegnalazione } from '../dominio/segnalazione';

import { creaIconaMarker } from './iconaMarker';

type Props = {
  latitudine: number;
  longitudine: number;
  stato: StatoSegnalazione;
};

const ZOOM_DETTAGLIO = 16;

export function MappaPosizione({ latitudine, longitudine, stato }: Props) {
  const centro: LatLngExpression = [latitudine, longitudine];

  return (
    <MapContainer
      center={centro}
      zoom={ZOOM_DETTAGLIO}
      className="mappa-leaflet"
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Marker position={centro} icon={creaIconaMarker(stato)} />
    </MapContainer>
  );
}
