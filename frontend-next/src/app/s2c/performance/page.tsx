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

interface S2CPerformanceMetrics {
  overall?: {
    ai_reliability_score_pct?: number | null;
    signal_attribution_accuracy_pct?: number | null;
    thumbs_up?: number;
    thumbs_down?: number;
    thumbs_total?: number;
  };
  detailed?: Array<{
    case_id: string;
    name: string;
    dtp_stage: string;
    status: string;
    ai_reliability_pct: number;
    human_change_count: number;
  }>;
}

export default function S2CPerformanceDashboardPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [metrics, setMetrics] = useState<S2CPerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchCases() {
      try {
        const base = getApiBaseUrl();
        const [caseRes, metricsRes] = await Promise.all([
          apiFetch(`${base}/api/cases`, { cache: "no-store" }),
          apiFetch(`${base}/api/s2c/performance/metrics`, { cache: "no-store" }),
        ]);
        const caseData = await caseRes.json();
        if (caseData.cases) setCases(caseData.cases);
        if (metricsRes.ok) setMetrics(await metricsRes.json());
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
              Global and detailed KPI view focused on AI reliability and copilot signal attribution quality.
            </p>
          </div>
        </header>

        <details className="bg-white rounded-xl border border-slate-200 p-4 text-sm text-slate-600 max-w-3xl">
          <summary className="cursor-pointer font-semibold text-slate-800 select-none">
            KPI definitions for this dashboard
          </summary>
          <div className="mt-3 space-y-3 leading-relaxed">
            <p>
              <strong className="text-slate-800">AI Reliability Score (global):</strong> average of all per-case AI
              reliability scores.
            </p>
            <p>
              <strong className="text-slate-800">Signal Attribution Accuracy:</strong> copilot thumbs-up rate
              (thumbs up / total thumbs responses).
            </p>
            <p>
              <strong className="text-slate-800">Detailed AI reliability (per case):</strong> derived from human change
              count in governance decisions/activity logs.
            </p>
            <p className="text-xs text-slate-500">
              Thumbs feedback is captured from case copilot response cards (up/down).
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
          <S2CExecutionMatrix cases={cases} metrics={metrics || undefined} />
        )}
      </div>
    </div>
  );
}
