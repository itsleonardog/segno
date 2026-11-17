export type StatoSegnalazione = 'aperta' | 'in_corso' | 'risolta' | 'chiusa';

export type RiepilogoSegnalazione = {
  riferimentoPubblico: string;
  stato: string;
  comuneCompetente: string | null;
};

export type DescrizioneStato =
  | { riconosciuto: true; stato: StatoSegnalazione; testo: string }
  | { riconosciuto: false; testo: string };

// Lo stato arriva dall'API come stringa: un valore sconosciuto è un esito
// previsto, non un'eccezione da gestire nel render.
export function descriviStatoSegnalazione(stato: string): DescrizioneStato {
  switch (stato) {
    case 'aperta':
      return { riconosciuto: true, stato, testo: 'Aperta' };
    case 'in_corso':
      return { riconosciuto: true, stato, testo: 'In corso' };
    case 'risolta':
      return { riconosciuto: true, stato, testo: 'Risolta' };
    case 'chiusa':
      return { riconosciuto: true, stato, testo: 'Chiusa' };
    default:
      return {
        riconosciuto: false,
        testo:
          'Lo stato della segnalazione non è riconosciuto. Aggiorna la pagina; se il problema persiste, contatta il comune competente.',
      };
  }
}

type PropsSchedaStato = {
  segnalazione: RiepilogoSegnalazione;
};

export function SchedaStatoSegnalazione({ segnalazione }: PropsSchedaStato) {
  const descrizioneStato = descriviStatoSegnalazione(segnalazione.stato);
  const messaggioComune =
    segnalazione.comuneCompetente === null
      ? 'Il comune competente non è ancora coperto. La segnalazione resta pubblica e sarà assegnata manualmente.'
      : `Segnalazione assegnata a ${segnalazione.comuneCompetente}.`;

  return (
    <article>
      <h2>Segnalazione {segnalazione.riferimentoPubblico}</h2>
      <p aria-live="polite">Stato: {descrizioneStato.testo}</p>
      <p>{messaggioComune}</p>
    </article>
  );
}
