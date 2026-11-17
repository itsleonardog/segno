import { divIcon } from 'leaflet';

import type { StatoSegnalazione } from '../dominio/segnalazione';
import { COLORI_STATO } from '../dominio/segnalazione';

const DIMENSIONE_MARKER = 18;

export function creaIconaMarker(stato: StatoSegnalazione) {
  const colore = COLORI_STATO[stato];
  return divIcon({
    className: '',
    html: `<span style="display:block;width:${DIMENSIONE_MARKER}px;height:${DIMENSIONE_MARKER}px;border-radius:9999px;border:2px solid #ffffff;background:${colore};box-shadow:0 1px 3px rgba(15,23,42,0.45)"></span>`,
    iconSize: [DIMENSIONE_MARKER, DIMENSIONE_MARKER],
    iconAnchor: [DIMENSIONE_MARKER / 2, DIMENSIONE_MARKER / 2],
  });
}
