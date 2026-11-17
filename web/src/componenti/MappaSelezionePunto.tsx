'use client';

import type { LatLngExpression } from 'leaflet';
import { useEffect } from 'react';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';

import type { StatoSegnalazione } from '../dominio/segnalazione';

import { creaIconaMarker } from './iconaMarker';

export type PosizioneMappa = {
  latitudine: number;
  longitudine: number;
};

type Props = {
  posizione: PosizioneMappa | null;
  statoMarker?: StatoSegnalazione;
  onSeleziona: (latitudine: number, longitudine: number) => void;
};

const CENTRO_ITALIA: LatLngExpression = [42.5, 12.5];
const ZOOM_ITALIA = 6;
const ZOOM_SELEZIONE = 15;

export function MappaSelezionePunto({
  posizione,
  statoMarker = 'aperta',
  onSeleziona,
}: Props) {
  const centro: LatLngExpression = posizione
    ? [posizione.latitudine, posizione.longitudine]
    : CENTRO_ITALIA;

  return (
    <MapContainer
      center={centro}
      zoom={posizione ? ZOOM_SELEZIONE : ZOOM_ITALIA}
      className="mappa-leaflet"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CatturaClicMappa onSeleziona={onSeleziona} />
      <InseguiPosizione posizione={posizione} />
      {posizione ? (
        <Marker
          position={[posizione.latitudine, posizione.longitudine]}
          icon={creaIconaMarker(statoMarker)}
        />
      ) : null}
    </MapContainer>
  );
}

function CatturaClicMappa({
  onSeleziona,
}: {
  onSeleziona: (latitudine: number, longitudine: number) => void;
}) {
  useMapEvents({
    click(evento) {
      onSeleziona(evento.latlng.lat, evento.latlng.lng);
    },
  });
  return null;
}

function InseguiPosizione({ posizione }: { posizione: PosizioneMappa | null }) {
  const mappa = useMap();

  useEffect(() => {
    if (posizione) {
      mappa.flyTo([posizione.latitudine, posizione.longitudine], ZOOM_SELEZIONE);
    }
  }, [mappa, posizione]);

  return null;
}
