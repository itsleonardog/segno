import { SchedaDettaglioSegnalazione } from '../../../componenti/SchedaDettaglioSegnalazione';

type Props = {
  params: Promise<{ public_ref: string }>;
};

export default async function PaginaDettaglioSegnalazione({ params }: Props) {
  const { public_ref } = await params;
  return <SchedaDettaglioSegnalazione riferimentoPubblico={public_ref} />;
}
