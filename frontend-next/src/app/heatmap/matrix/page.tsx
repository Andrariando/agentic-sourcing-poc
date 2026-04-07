"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import SourcingOpportunityMatrix from "@/components/heatmap/SourcingOpportunityMatrix";

function rankOpportunities(rows: any[]) {
  return rows
    .sort((a: any, b: any) => b.total_score - a.total_score);
}

type HeatmapPerformanceSummary = {
  copilot_feedback?: {
    thumbs_up?: number;
    thumbs_down?: number;
    thumbs_total?: number;
    signal_attribution_accuracy_pct?: number | null;
  };
};

export default function HeatmapMatrixPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [summary, setSummary] = useState<HeatmapPerformanceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const base = getApiBaseUrl();
        const [oppRes, sumRes] = await Promise.all([
          apiFetch(`${base}/api/heatmap/opportunities`, { cache: "no-store" }),
          apiFetch(`${base}/api/heatmap/metrics/dashboard`, { cache: "no-store" }),
        ]);
        const oppData = await oppRes.json();
        if (oppData.opportunities) {
          setOpportunities(rankOpportunities(oppData.opportunities));
        }
        if (sumRes.ok) setSummary(await sumRes.json());
        setError(null);
      } catch (err) {
        console.error(err);
        setError("Could not load opportunities.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <header className="flex flex-wrap items-center gap-4 justify-between">
          <div>
            <Link
              href="/heatmap"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-sponsor-blue hover:text-blue-800 mb-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sourcing Priority List
            </Link>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Performance Dashboard</h1>
            <p className="text-slate-500 mt-2 text-sm">
              Overall and detailed performance for sourcing prioritization quality.
            </p>
          </div>
        </header>

        {loading ? (
          <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">Loading matrix…</div>
        ) : error ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-amber-900 text-sm">
            {error} Check the API base: {getApiBaseUrl()}
            {apiConnectivityHint()}
          </div>
        ) : (
          <SourcingOpportunityMatrix opportunities={opportunities} summary={summary || undefined} />
        )}
      </div>
    </div>
  );
}
