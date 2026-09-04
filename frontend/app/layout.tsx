import type { Metadata } from 'next';
import React from 'react';
import { Header } from '../components/Header';
import './globals.css';

export const metadata: Metadata = {
  title: 'Receivables Resolution Agent',
  description: 'AI-assisted B2B receivables resolution platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main className="app-main">{children}</main>
      </body>
    </html>
  );
}
