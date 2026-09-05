import type { Metadata } from 'next';
import React from 'react';
import { Header } from '../components/Header';
import './globals.css';

export const metadata: Metadata = {
  title: 'Receivables Resolution Agent',
  description: 'AI-assisted B2B receivables resolution platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-200 min-h-screen">
        <Header />
        <main className="max-w-6xl mx-auto py-8 px-4">{children}</main>
      </body>
    </html>
  );
}
