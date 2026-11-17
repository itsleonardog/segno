const FORMATO_DATA_ORA = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formattaDataOra(valore: string): string {
  const istante = new Date(valore);
  if (Number.isNaN(istante.getTime())) {
    return valore;
  }
  return FORMATO_DATA_ORA.format(istante);
}
