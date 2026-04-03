"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import S2CExecutionMatrix from "@/components/s2c/S2CExecutionMatrix";

interface CaseSummary {
  case_id: string;
  name: string;
  category_id: string;
  dtp_stage: string;
  status: string;
  supplier_id?: string | null;
  trigger_source?: string;
}

export default function S2CPerformanceDashboardPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCases() {
      try {
        const url = `${getApiBaseUrl()}/api/cases`;
        const res = await apiFetch(url, { cache: "no-store" });
        const data = await res.json();
        if (data.cases) setCases(data.cases);
        setError(null);
      } catch {
        setError("Could not load cases.");
      } finally {
        setLoading(false);
      }
    }
    fetchCases();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <header className="flex flex-wrap items-center gap-4 justify-between">
          <div>
            <Link
              href="/cases"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-sponsor-blue hover:text-blue-800 mb-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to S2C Case Dashboard
            </Link>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">S2C Performance Dashboard</h1>
            <p className="text-slate-500 mt-2 text-sm max-w-3xl leading-relaxed">
              Classic procurement view: each active case shows{" "}
              <strong className="text-slate-700">SLA</strong> (adherence vs breaches),{" "}
              <strong className="text-slate-700">cycle time</strong> (elapsed days vs benchmark), and{" "}
              <strong className="text-slate-700">cost savings</strong> (identified $K vs baseline and open commercial gaps).
              Every pillar pairs a <strong className="text-slate-700">KPI</strong> with a <strong className="text-slate-700">KLI</strong>.
            </p>
          </div>
        </header>

        <details className="bg-white rounded-xl border border-slate-200 p-4 text-sm text-slate-600 max-w-3xl">
          <summary className="cursor-pointer font-semibold text-slate-800 select-none">
            How these KPIs / KLIs are defined (production)
          </summary>
          <div className="mt-3 space-y-3 leading-relaxed">
            <p>
              <strong className="text-slate-800">KLI = Key Learning Indicator:</strong> signals where humans are pushing
              back on drafts or processes — edit burden, rework loops, overrides — so you improve models, templates, and
              policy clarity (not only chase latencies).
            </p>
            <p>
              <strong className="text-slate-800">SLA:</strong> KPI = on-time gate adherence; KLI = governance{" "}
              <em>edit burden</em> (tracked changes to pack/checklist).
            </p>
            <p>
              <strong className="text-slate-800">Cycle time:</strong> KPI = elapsed days (+ slip vs benchmark in the same
              cell); KLI = <em>plan rework count</em> after human review.
            </p>
            <p>
              <strong className="text-slate-800">Savings:</strong> KPI = identified savings ($K); KLI ={" "}
              <em>savings adjustment count</em> (analyst changed scenarios or challenged assumptions).
            </p>
            <p className="text-xs text-slate-500">
              Current numbers are demo-seeded per <code className="text-slate-600">case_id</code>. Extend with more pillars
              (quality, risk) when needed.
            </p>
          </div>
        </details>

        {loading ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">Loading cases…</div>
        ) : error ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-amber-900 text-sm">
            {error} Check the API base: {getApiBaseUrl()}
            {apiConnectivityHint()}
          </div>
        ) : (
          <S2CExecutionMatrix cases={cases} />
        )}
      </div>
    </div>
  );
}
