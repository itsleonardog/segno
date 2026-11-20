import path from 'node:path';
import { fileURLToPath } from 'node:url';

const directoryRadice = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // L'immagine di produzione contiene solo il server e i file tracciati.
  output: 'standalone',
  outputFileTracingRoot: directoryRadice,
};

export default nextConfig;
