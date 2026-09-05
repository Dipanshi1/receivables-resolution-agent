import React from 'react';
import Link from 'next/link';

export function Header() {
  return (
    <header className="bg-slate-900 border-b border-slate-800 p-4">
      <div className="max-w-6xl mx-auto flex justify-between items-center">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-blue-500">Track 03 — AI Revenue Recovery</span>
          <h1 className="text-xl font-bold text-slate-100">Receivables Resolution Agent</h1>
        </div>
        <nav className="flex gap-4">
          <Link href="/" className="text-sm px-3 py-1 rounded text-slate-400 hover:text-slate-100">Dashboard</Link>
          <Link href="/cases" className="text-sm px-3 py-1 rounded text-slate-400 hover:text-slate-100">Recovery Cases</Link>
        </nav>
      </div>
    </header>
  );
}
