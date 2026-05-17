import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Utah County Election Map',
  description: 'Interactive Utah county precinct map with election vote trends.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-sA+4mxvoS3Ue3w5r1GNJd7Wb4UhoB7XQquVxQtzvLu8="
          crossOrigin=""
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
