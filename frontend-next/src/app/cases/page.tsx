import React from "react";
import Link from "next/link";

export default function LegacyCaseDashboard() {
  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Active Sourcing Cases</h1>
            <p className="text-slate-500 mt-2 text-sm">Legacy DTP Management System.</p>
          </div>
        </header>

        {/* The Data Table */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200 text-left">
                  <th className="px-6 py-4 font-medium">Case ID</th>
                  <th className="px-6 py-4 font-medium">Case Name / Supplier</th>
                  <th className="px-6 py-4 font-medium">Category</th>
                  <th className="px-6 py-4 font-medium">Stage (DTP)</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                <tr className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 text-sm font-medium text-slate-900">CASE-2026-001</td>
                  <td className="px-6 py-4 font-semibold text-slate-900">TechGlobal Inc Renewal</td>
                  <td className="px-6 py-4 text-sm text-slate-600">IT Infrastructure</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      DTP02 (Supplier Eval)
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">In Progress</td>
                  <td className="px-6 py-4 text-right">
                    <Link href="/cases/CASE-2026-001/copilot" className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">Open Copilot</Link>
                  </td>
                </tr>
                <tr className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 text-sm font-medium text-slate-900">CASE-2026-002</td>
                  <td className="px-6 py-4 font-semibold text-slate-900">AWS Expansion</td>
                  <td className="px-6 py-4 text-sm text-slate-600">IT Infrastructure</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      DTP01 (Triage)
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-slate-600">Pending Agent</td>
                  <td className="px-6 py-4 text-right">
                    <Link href="/cases/CASE-2026-002/copilot" className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">Open Copilot</Link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
