"use client";

import React from "react";
import { HEATMAP_GLOSSARY, type HeatmapGlossaryKey } from "@/lib/heatmap-glossary";
import { heatmapTierLabel } from "@/lib/heatmap-tier-display";

const TIER_TOOLTIP: Record<string, HeatmapGlossaryKey> = {
  T1: "t1",
  T2: "t2",
  T3: "t3",
  T4: "t4",
};

export interface SourcingOpportunityMatrixProps {
  /** Raw opportunity rows from `/api/heatmap/opportunities`. */
  opportunities: any[];
  summary?: {
    copilot_feedback?: {
      thumbs_up?: number;
      thumbs_down?: number;
      thumbs_total?: number;
      signal_attribution_accuracy_pct?: number | null;
    };
  };
}

/**
 * Performance dashboard split into:
 * 1) Overall performance
 * 2) Detailed performance per opportunity
 */
export default function SourcingOpportunityMatrix({ opportunities, summary }: SourcingOpportunityMatrixProps) {
  const rows = opportunities;
  const reliabilities = rows
    .map((o) => Number(o?.kli_metrics?.ai_reliability_pct))
    .filter((v) => !Number.isNaN(v));
  const avgReliability =
    reliabilities.length > 0
      ? Number((reliabilities.reduce((a, b) => a + b, 0) / reliabilities.length).toFixed(1))
      : null;
  const cf = summary?.copilot_feedback;
  const thumbsTotal = Number(cf?.thumbs_total ?? 0);
  const thumbsUp = Number(cf?.thumbs_up ?? 0);
  const signalAcc =
    cf?.signal_attribution_accuracy_pct != null
      ? Number(cf.signal_attribution_accuracy_pct)
      : thumbsTotal > 0
        ? Number(((thumbsUp / thumbsTotal) * 100).toFixed(1))
        : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Performance Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">
            Overall performance plus detailed AI reliability tracking for each sourcing opportunity.
          </p>
        </div>
      </div>

      <div className="px-5 py-4 border-b border-slate-200 bg-white">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">1. Overall Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">AI Reliability Score</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {avgReliability == null ? "—" : `${avgReliability}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Average of per-opportunity AI reliability scores.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Signal Attribution Accuracy
            </p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {signalAcc == null ? "—" : `${signalAcc.toFixed(1)}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              ProcuraBot thumbs up / total thumbs responses ({thumbsUp}/{thumbsTotal}).
            </p>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto px-0">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">2. Detailed Performance</h3>
          <p className="text-xs text-slate-500 mt-1">
            AI reliability decreases as humans edit/override more during review.
          </p>
        </div>
        <table className="w-full text-left border-collapse text-sm min-w-[760px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-widest text-slate-500">
              <th className="px-4 py-3 border-r border-slate-200 w-72">
                Sourcing Opportunity
              </th>
              <th className="px-3 py-3 border-r border-slate-200 text-center cursor-help" title={HEATMAP_GLOSSARY.tier}>
                Priority
              </th>
              <th className="px-3 py-3 text-center border-r border-slate-200">
                AI Reliability
              </th>
              <th className="px-3 py-3 text-center border-r border-slate-200">
                Human Score Changes
              </th>
              <th className="px-3 py-3 text-center">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500 text-sm">
                  No opportunities to display.
                </td>
              </tr>
            ) : (
              rows.slice(0, 25).map((opp, i) => {
                const km = opp.kli_metrics as { ai_reliability_pct?: number; override_count?: number } | undefined;
                const reliability = Number(km?.ai_reliability_pct ?? 0);
                const humanChanges = Number(km?.override_count ?? 0);
                return (
                  <tr key={`perf-${opp.id ?? i}`} className="hover:bg-slate-50 transition-colors">
                    <td
                      className="px-4 py-3 font-semibold text-slate-800 border-r border-slate-100 truncate max-w-[200px]"
                      title={opp.supplier_name || "New Request"}
                    >
                      {opp.supplier_name || "New Sourcing Request"}
                      <div className="font-mono text-[10px] text-slate-400 font-normal">{opp.contract_id || opp.request_id}</div>
                    </td>
                    <td className="px-3 py-3 text-center border-r border-slate-100">
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold cursor-help ${
                          opp.tier === "T1"
                            ? "bg-red-100 text-mit-red"
                            : opp.tier === "T2"
                              ? "bg-orange-100 text-orange-700"
                              : "bg-slate-100 text-slate-600"
                        }`}
                        title={HEATMAP_GLOSSARY[TIER_TOOLTIP[opp.tier] ?? "tier"]}
                      >
                        {heatmapTierLabel(opp.tier)}
                      </span>
                    </td>
                    <td
                      className={`px-3 py-3 text-center font-mono text-xs font-semibold border-r border-slate-100 ${
                        reliability >= 90
                          ? "text-emerald-700"
                          : reliability >= 75
                            ? "text-amber-700"
                            : "text-rose-700"
                      }`}
                    >
                      {Number.isFinite(reliability) && reliability > 0 ? `${reliability.toFixed(0)}%` : "—"}
                    </td>
                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-slate-700">
                      {humanChanges}
                    </td>
                    <td className="px-3 py-3 text-center text-xs text-slate-600">
                      {opp.status || "Pending"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * AI Reliability uses feedback-derived metrics (<code className="text-slate-600">kli_metrics.ai_reliability_pct</code>);
        Human Score Changes uses review override count per opportunity. Signal Attribution Accuracy uses thumbs up / total
        thumbs responses from Heatmap ProcuraBot feedback.
      </div>
    </div>
  );
}
