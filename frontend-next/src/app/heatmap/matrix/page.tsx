"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import SourcingOpportunityMatrix from "@/components/heatmap/SourcingOpportunityMatrix";

function rankOpportunities(rows: any[]) {
  return rows
    .filter((o) => o.status !== "Approved")
    .sort((a: any, b: any) => b.total_score - a.total_score);
}

export default function HeatmapMatrixPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const url = `${getApiBaseUrl()}/api/heatmap/opportunities`;
        const res = await apiFetch(url, { cache: "no-store" });
        const data = await res.json();
        if (data.opportunities) {
          setOpportunities(rankOpportunities(data.opportunities));
        }
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
              Back to Priority List
            </Link>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Sourcing Opportunity Matrix</h1>
            <p className="text-slate-500 mt-2 text-sm">
              KPI and KLI columns for all five Agentic Outcomes, aligned with the heatmap opportunity list.
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
          <SourcingOpportunityMatrix opportunities={opportunities} />
        )}
      </div>
    </div>
  );
}
