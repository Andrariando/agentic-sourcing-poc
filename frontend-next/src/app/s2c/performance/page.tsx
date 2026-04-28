"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import S2CExecutionMatrix from "@/components/s2c/S2CExecutionMatrix";

interface S2CPerformanceMetrics {
  overall?: {
    ai_reliability_score_pct?: number | null;
    signal_attribution_accuracy_pct?: number | null;
    signal_coverage_rate_pct?: number | null;
    thumbs_up?: number;
    thumbs_down?: number;
    thumbs_total?: number;
    signal_coverage_cases_with_all_inputs?: number;
    signal_coverage_active_cases_total?: number;
  };
}

export default function S2CPerformanceDashboardPage() {
  const [metrics, setMetrics] = useState<S2CPerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMetrics() {
      try {
        const base = getApiBaseUrl();
        const metricsRes = await apiFetch(`${base}/api/s2c/performance/metrics`, { cache: "no-store" });
        if (metricsRes.ok) setMetrics(await metricsRes.json());
        setError(null);
      } catch {
        setError("Could not load metrics.");
      } finally {
        setLoading(false);
      }
    }
    fetchMetrics();
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
              High-level KPI view for AI reliability, explanation acceptance, and scoring input coverage.
            </p>
          </div>
        </header>

        <details className="bg-white rounded-xl border border-slate-200 p-4 text-sm text-slate-600 max-w-3xl">
          <summary className="cursor-pointer font-semibold text-slate-800 select-none">
            KPI definitions for this dashboard
          </summary>
          <div className="mt-3 space-y-3 leading-relaxed">
            <p>
              <strong className="text-slate-800">AI Reliability Score:</strong> overall score based on how many human
              edits are made across opportunities.
            </p>
            <p>
              <strong className="text-slate-800">KLI - Signal Attribution Accuracy:</strong> acceptance rate of
              ProcuraBot explanations (thumbs up / total feedback).
            </p>
            <p>
              <strong className="text-slate-800">KPI - Signal Coverage Rate:</strong> active cases with all four
              required scoring inputs available before scoring begins.
            </p>
            <p className="text-xs text-slate-500">
              Required inputs: contract expiry, spend, category strategy, and supplier risk.
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
          <S2CExecutionMatrix metrics={metrics || undefined} />
        )}
      </div>
    </div>
  );
}
