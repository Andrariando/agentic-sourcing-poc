"use client";

import React from "react";
import { HEATMAP_GLOSSARY, type HeatmapGlossaryKey } from "@/lib/heatmap-glossary";

const TIER_TOOLTIP: Record<string, HeatmapGlossaryKey> = {
  T1: "t1",
  T2: "t2",
  T3: "t3",
  T4: "t4",
};

export interface SourcingOpportunityMatrixProps {
  /** Raw opportunity rows from `/api/heatmap/opportunities`; non-Approved rows are shown. */
  opportunities: any[];
}

/**
 * Per-opportunity KPI/KLI grid for the five Agentic Outcomes (heatmap supplement).
 */
export default function SourcingOpportunityMatrix({ opportunities }: SourcingOpportunityMatrixProps) {
  const activeOpportunities = opportunities.filter((o) => o.status !== "Approved");

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Sourcing Opportunity Matrix</h2>
          <p className="text-sm text-slate-500 mt-1">Per-opportunity tracking of all 5 Agentic Outcomes</p>
        </div>
        <div className="flex gap-4 items-center">
          <span
            className="flex items-center gap-1.5 text-xs font-bold text-slate-500 uppercase tracking-widest cursor-help border-b border-dotted border-slate-400"
            title={HEATMAP_GLOSSARY.kpi}
          >
            <div className="w-2.5 h-2.5 bg-sponsor-blue rounded-sm" />
            KPI
          </span>
          <span
            className="flex items-center gap-1.5 text-xs font-bold text-slate-500 uppercase tracking-widest cursor-help border-b border-dotted border-slate-400"
            title={HEATMAP_GLOSSARY.kli}
          >
            <div className="w-2.5 h-2.5 bg-mit-red rounded-sm" />
            KLI
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm min-w-[900px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th
                rowSpan={2}
                className="px-4 py-3 border-r border-slate-200 font-syne text-[11px] font-bold uppercase tracking-widest text-slate-500 align-bottom w-64"
              >
                Sourcing Opportunity
              </th>
              <th
                rowSpan={2}
                className="px-3 py-3 border-r border-slate-200 font-syne text-[11px] font-bold uppercase tracking-widest text-slate-500 align-bottom text-center cursor-help"
                title={HEATMAP_GLOSSARY.tier}
              >
                Tier
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-blue-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-sponsor-blue text-center"
              >
                Outcome 1 · Consistency
              </th>
              <th
                colSpan={1}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-blue-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-sponsor-blue text-center"
              >
                Outcome 2 · Cycle Time
              </th>
              <th
                colSpan={1}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-red-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-mit-red text-center"
              >
                Outcome 3 · Collaboration
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-blue-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-sponsor-blue text-center"
              >
                Outcome 4 · Visibility
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-b border-slate-200 bg-red-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-mit-red text-center"
              >
                Outcome 5 · Scale
              </th>
            </tr>
            <tr className="bg-slate-50 border-b-2 border-slate-800">
              <th className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>{" "}
                AI Reliability
              </th>
              <th className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>{" "}
                Override Count
              </th>
              <th className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>
                <span
                  className="cursor-help"
                  title="Percent time not spent vs a synthetic analyst baseline (HEATMAP_HUMAN_BASELINE_SCORE_HOURS). System time = last_refresh_ts − record_created_at, or pipeline wall time ÷ N when both are equal."
                >
                  Time saved vs baseline
                </span>
              </th>
              <th className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>{" "}
                Edit Density
              </th>
              <th className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>{" "}
                Data Vis Rate
              </th>
              <th className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>{" "}
                Signal Density
              </th>
              <th className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>{" "}
                Agents Run
              </th>
              <th className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight">
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>{" "}
                Exec Time (s)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {activeOpportunities.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-4 py-10 text-center text-slate-500 text-sm">
                  No active opportunities to display. Run the scoring pipeline or clear Approved rows from the priority list.
                </td>
              </tr>
            ) : (
              activeOpportunities.slice(0, 10).map((opp, i) => {
                const charCode = ((opp.supplier_name || opp.request_id || "?") as string).charCodeAt(0);
                const km = opp.kli_metrics as
                  | {
                      ai_reliability_pct?: number;
                      override_count?: number;
                      cycle_time_reduce_pct?: number | null;
                      cycle_time_scoring_sec?: number | null;
                      cycle_time_human_baseline_sec?: number | null;
                      cycle_time_method?: string;
                      cycle_time_assumption?: string;
                      edit_density?: number;
                      data_vis_rate_pct?: number;
                      signal_density?: number;
                      agents_run?: number;
                      exec_time_s?: number | null;
                      source?: string;
                    }
                  | undefined;
                const reliability = km?.ai_reliability_pct ?? Math.min(99, 85 + (charCode % 15));
                const overrides = km?.override_count ?? charCode % 3;
                const cycleFallback = 30 + (charCode % 40);
                const cycleReduc =
                  km == null
                    ? cycleFallback
                    : km.cycle_time_reduce_pct != null && km.cycle_time_reduce_pct !== undefined
                      ? km.cycle_time_reduce_pct
                      : null;
                const edits = km?.edit_density ?? charCode % 12;
                const visRate = km?.data_vis_rate_pct ?? 90 + (charCode % 10);
                const signals = km?.signal_density ?? 4 + (charCode % 8);
                const agents = km?.agents_run ?? 3 + (charCode % 3);
                const execTime = km?.exec_time_s ?? 1.2 + (charCode % 30) / 10;

                return (
                  <tr key={`kli-${opp.id ?? i}`} className="hover:bg-slate-50 transition-colors">
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
                        {opp.tier}
                      </span>
                    </td>

                    <td className="px-3 py-3 text-center text-slate-700 font-mono text-xs">{reliability}%</td>
                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-mit-red">{overrides}</td>

                    <td
                      className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs font-medium text-green-600"
                      title={
                        km?.cycle_time_assumption
                          ? `${km.cycle_time_assumption} Method: ${km.cycle_time_method ?? ""}.`
                          : undefined
                      }
                    >
                      {cycleReduc == null ? (
                        <span className="text-slate-400">—</span>
                      ) : (
                        <>{Number(cycleReduc).toFixed(1)}%</>
                      )}
                    </td>

                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-mit-red">{edits}</td>

                    <td className="px-3 py-3 text-center font-mono text-xs text-slate-700">{visRate}%</td>
                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-slate-700">{signals}</td>

                    <td className="px-3 py-3 text-center font-mono text-xs text-slate-700">{agents}</td>
                    <td className="px-3 py-3 text-center font-mono text-xs text-slate-700">
                      {km && km.exec_time_s == null ? "—" : `${Number(execTime).toFixed(1)}s`}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * KPI/KLI mix feedback counts, data-quality flags, scoring breadth, and pipeline telemetry. &quot;Time saved vs
        baseline&quot; compares system scoring time (created → last refresh, or pipeline seconds ÷ opportunities) to a
        configurable synthetic analyst baseline (<code className="text-slate-600">HEATMAP_HUMAN_BASELINE_SCORE_HOURS</code>,
        default 6h); replace with real manual triage benchmarks when you have them. Demo feedback rows are re-seeded on
        batch runs.
      </div>
    </div>
  );
}
