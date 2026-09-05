"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchCases, formatCurrency, PaginatedCasesResponse } from '@/lib/api';

export default function CasesPage() {
  const [data, setData] = useState<PaginatedCasesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCases(1, 100)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-10 animate-pulse text-slate-400">Loading cases...</div>;
  if (error) return <div className="bg-red-900/20 text-red-400 p-4 rounded border border-red-900">Error: {error}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>

          <h2 className="text-2xl font-bold mb-2">
            Recovery Cases
            {data.data.some((c) => c.is_demo) && (
              <span className="ml-3 inline-block bg-amber-900/50 text-amber-500 text-xs px-2 py-1 rounded border border-amber-800 align-middle">
                DEMO DATA
              </span>
            )}
          </h2>

          <p className="text-slate-400">All identified outstanding invoices currently managed by the agent.</p>
        </div>
        <div className="text-sm text-slate-500">
          Total cases: {data.total}
        </div>
      </div>

      <div className="overflow-hidden border border-slate-800 rounded-lg shadow-xl bg-slate-900">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="p-4 font-medium">Case ID</th>
              <th className="p-4 font-medium">Status</th>
              <th className="p-4 font-medium">Remaining</th>
              <th className="p-4 font-medium">Recovered</th>
              <th className="p-4 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {data.data.map((c) => (
              <tr key={c.id} className="hover:bg-slate-800/50 transition-colors">
                <td className="p-4">
                  <div className="font-mono text-xs">{c.id}</div>
                  <div className="text-[10px] text-slate-500 mt-1 uppercase">INV: {c.invoice_id.substring(0, 8)}</div>
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    c.status === 'FULLY_RECOVERED' ? 'bg-emerald-900/50 text-emerald-400' :
                    c.status === 'HUMAN_REVIEW' ? 'bg-amber-900/50 text-amber-400' :
                    c.status === 'OVERDUE' ? 'bg-slate-800 text-slate-300' :
                    'bg-blue-900/50 text-blue-400'
                  }`}>
                    {c.status}
                  </span>
                </td>
                <td className="p-4 font-medium text-red-400">{formatCurrency(c.remaining_amount_minor)}</td>
                <td className="p-4 font-medium text-emerald-400">{formatCurrency(c.recovered_amount_minor)}</td>
                <td className="p-4 text-right">
                  <Link href={`/cases/${c.id}`} className="inline-flex items-center justify-center px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded transition-colors">
                    View
                  </Link>
                </td>
              </tr>
            ))}
            {data.data.length === 0 && (
              <tr>
                <td colSpan={5} className="p-8 text-center text-slate-500">No cases found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
