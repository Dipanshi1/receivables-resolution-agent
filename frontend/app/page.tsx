"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchCases, formatCurrency, PaginatedCasesResponse } from '@/lib/api';

export default function DashboardPage() {
  const [data, setData] = useState<PaginatedCasesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCases()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-10 animate-pulse text-slate-400">Loading dashboard...</div>;
  if (error) return <div className="bg-red-900/20 text-red-400 p-4 rounded border border-red-900">Error: {error}</div>;
  if (!data) return null;

  const totalAtRisk = data.data.reduce((sum, c) => sum + c.remaining_amount_minor, 0);
  const totalRecovered = data.data.reduce((sum, c) => sum + c.recovered_amount_minor, 0);
  const activeCases = data.data.filter(c => !["CLOSED", "FULLY_RECOVERED", "CANCELLED", "EXECUTION_FAILED"].includes(c.status));
  const reviewRequired = data.data.filter(c => c.status === "HUMAN_REVIEW");

  return (
    <div className="space-y-8">
      <div>

        <h2 className="text-2xl font-bold mb-2">
          Merchant Recovery Dashboard
          {data.data.some((c) => c.is_demo) && (
            <span className="ml-3 inline-block bg-amber-900/50 text-amber-500 text-xs px-2 py-1 rounded border border-amber-800 align-middle">
              DEMO DATA
            </span>
          )}
        </h2>

        <p className="text-slate-400">Overview of your active revenue recovery operations.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 p-6 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-sm mb-1">Total at Risk</div>
          <div className="text-3xl font-bold text-red-400">{formatCurrency(totalAtRisk)}</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-sm mb-1">Recovered (Verified)</div>
          <div className="text-3xl font-bold text-emerald-400">{formatCurrency(totalRecovered)}</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-sm mb-1">Active Cases</div>
          <div className="text-3xl font-bold text-blue-400">{activeCases.length}</div>
        </div>
        <div className="bg-slate-900 p-6 rounded-lg border border-slate-800">
          <div className="text-slate-400 text-sm mb-1">Needs Review</div>
          <div className="text-3xl font-bold text-amber-400">{reviewRequired.length}</div>
        </div>
      </div>

      <div>
        <div className="flex justify-between items-end mb-4">
          <h3 className="text-xl font-semibold">Recent Active Cases</h3>
          <Link href="/cases" className="text-blue-500 hover:text-blue-400 text-sm">View all cases &rarr;</Link>
        </div>

        {activeCases.length === 0 ? (
          <div className="text-center py-12 bg-slate-900/50 border border-slate-800 rounded-lg text-slate-500">
            No active recovery cases.
          </div>
        ) : (
          <div className="overflow-hidden border border-slate-800 rounded-lg">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-4 font-medium">Case ID</th>
                  <th className="p-4 font-medium">Status</th>
                  <th className="p-4 font-medium text-right">Remaining Risk</th>
                  <th className="p-4 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-900">
                {activeCases.slice(0, 5).map((c) => (
                  <tr key={c.id} className="hover:bg-slate-800/50 transition-colors">
                    <td className="p-4 font-mono text-xs">{c.id}</td>
                    <td className="p-4">
                      <span className="bg-slate-800 px-2 py-1 rounded text-xs font-semibold">{c.status}</span>
                    </td>
                    <td className="p-4 text-right text-red-400 font-medium">
                      {formatCurrency(c.remaining_amount_minor)}
                    </td>
                    <td className="p-4 text-right">
                      <Link href={`/cases/${c.id}`} className="text-blue-400 hover:text-blue-300 text-xs font-semibold">
                        Resolve &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
