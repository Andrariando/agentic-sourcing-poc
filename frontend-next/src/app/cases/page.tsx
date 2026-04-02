"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl } from "@/lib/api-base";
import { getMockCasePerformanceInsight } from "@/lib/mock-case-performance";

interface CaseSummary {
  case_id: string;
  name: string;
  category_id: string;
  dtp_stage: string;
  status: string;
  supplier_id?: string | null;
  trigger_source?: string;
}

export default function CaseDashboardPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchCases() {
      try {
        const url = `${getApiBaseUrl()}/api/cases`;
        const res = await apiFetch(url);
        const data = await res.json();
        if (data.cases) {
          setCases(data.cases);
        }
      } catch (err) {
        console.error("Failed to fetch cases:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchCases();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Active Sourcing Cases</h1>
            <p className="text-slate-500 mt-2 text-sm">Case management workflow.</p>
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
                  <th className="px-6 py-4 font-medium min-w-[200px]">Performance snapshot</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                        <p className="text-slate-400 font-medium">Synchronizing with Intelligence Engine...</p>
                      </div>
                    </td>
                  </tr>
                ) : cases.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-400 font-medium">No active cases found in the DTP pipeline.</td>
                  </tr>
                ) : (
                  cases.map((c) => {
                    const perf = getMockCasePerformanceInsight({
                      caseId: c.case_id,
                      name: c.name,
                      categoryId: c.category_id,
                      dtpStage: c.dtp_stage,
                      triggerSource: c.trigger_source || "",
                      supplierId: c.supplier_id || undefined,
                    });
                    const k0 = perf.kpis[0];
                    const k1 = perf.kpis[1];
                    return (
                    <tr key={c.case_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 text-sm font-medium text-slate-900">{c.case_id}</td>
                      <td className="px-6 py-4 font-semibold text-slate-900">{c.name}</td>
                      <td className="px-6 py-4 text-sm text-slate-600">{c.category_id}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          c.dtp_stage.includes("01") ? "bg-blue-100 text-blue-800" :
                          c.dtp_stage.includes("02") ? "bg-indigo-100 text-indigo-800" :
                          "bg-emerald-100 text-emerald-800"
                        }`}>
                          {c.dtp_stage}
                        </span>
                      </td>
                      <td
                        className="px-6 py-4 text-xs text-slate-600 max-w-[260px]"
                        title={`${perf.bullets[0]} ${perf.sourceNote}`}
                      >
                        {perf.handoffTag && (
                          <span className="mb-1 inline-block rounded bg-amber-100 text-amber-900 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide">
                            {perf.handoffTag}
                          </span>
                        )}
                        <div className="mt-1 space-y-0.5">
                          <div>
                            <span className="font-semibold text-slate-700">{k0.label}:</span> {k0.value}
                          </div>
                          <div>
                            <span className="font-semibold text-slate-700">{k1.label}:</span> {k1.value}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600">{c.status}</td>
                      <td className="px-6 py-4 text-right">
                        <Link href={`/cases/${c.case_id}/copilot`} className="text-sponsor-blue hover:text-blue-800 text-sm font-medium">
                          Open Copilot
                        </Link>
                      </td>
                    </tr>
                  );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
