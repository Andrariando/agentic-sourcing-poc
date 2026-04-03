"use client";

import React from "react";
import Link from "next/link";
import { HEATMAP_GLOSSARY } from "@/lib/heatmap-glossary";
import { getS2CExecutionMetricsForCase } from "@/lib/s2c-execution-metrics";

export interface S2CCaseRow {
  case_id: string;
  name: string;
  category_id?: string;
  dtp_stage: string;
  status?: string;
}

export interface S2CExecutionMatrixProps {
  cases: S2CCaseRow[];
}

/**
 * Classic procurement focus: SLA, cycle time, and cost savings — each with KPI (blue) / KLI (red).
 */
export default function S2CExecutionMatrix({ cases }: S2CExecutionMatrixProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Classic procurement — SLA, cycle time & savings</h2>
          <p className="text-sm text-slate-500 mt-1">
            Three pillars: each <strong className="font-medium text-slate-700">KPI</strong> is an outcome metric; each{" "}
            <strong className="font-medium text-slate-700">KLI</strong> (
            <abbr title={HEATMAP_GLOSSARY.kli} className="cursor-help underline decoration-dotted decoration-slate-400">
              Key Learning Indicator
            </abbr>
            ) captures human trust and friction — edits, rework, and adjustments — not just “being late.” Demo values are
            seeded per case.
          </p>
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
        <table className="w-full text-left border-collapse text-sm min-w-[820px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th
                rowSpan={2}
                className="px-4 py-3 border-r border-slate-200 font-syne text-[11px] font-bold uppercase tracking-widest text-slate-500 align-bottom w-56"
              >
                Case
              </th>
              <th
                rowSpan={2}
                className="px-3 py-3 border-r border-slate-200 font-syne text-[11px] font-bold uppercase tracking-widest text-slate-500 align-bottom text-center w-24"
                title="Current DTP stage"
              >
                Stage
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-blue-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-sponsor-blue text-center"
              >
                SLA & on-time governance
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-r border-slate-200 border-b border-slate-200 bg-blue-50/30 font-syne text-[10px] font-bold uppercase tracking-widest text-sponsor-blue text-center"
              >
                Cycle time
              </th>
              <th
                colSpan={2}
                className="px-3 py-2 border-b border-slate-200 bg-emerald-50/40 font-syne text-[10px] font-bold uppercase tracking-widest text-emerald-800 text-center"
              >
                Cost savings
              </th>
            </tr>
            <tr className="bg-slate-50 border-b-2 border-slate-800">
              <th
                className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title="% of gated activities inside policy SLA"
              >
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>
                SLA adherence
              </th>
              <th
                className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title={HEATMAP_GLOSSARY.kli}
              >
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>
                Gov. edit burden
              </th>
              <th
                className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title="Elapsed business days on S2C path"
              >
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>
                Cycle time (d)
              </th>
              <th
                className="px-2 py-2 text-center border-r border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title={HEATMAP_GLOSSARY.kli}
              >
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>
                Plan rework #
              </th>
              <th
                className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title="Identified savings vs baseline — demo in $K"
              >
                <span className="block text-sponsor-blue mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kpi}>
                  KPI
                </span>
                Savings ($K)
              </th>
              <th
                className="px-2 py-2 text-center text-[10px] font-bold uppercase tracking-wider text-slate-700 leading-tight"
                title={HEATMAP_GLOSSARY.kli}
              >
                <span className="block text-mit-red mb-0.5 cursor-help" title={HEATMAP_GLOSSARY.kli}>
                  KLI
                </span>
                Savings adj. #
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {cases.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500 text-sm">
                  No cases to display. Approve a prioritization row or open a case from the S2C Case Dashboard.
                </td>
              </tr>
            ) : (
              cases.slice(0, 15).map((c) => {
                const m = getS2CExecutionMetricsForCase({
                  caseId: c.case_id,
                  name: c.name,
                  dtpStage: c.dtp_stage,
                  status: c.status,
                });
                return (
                  <tr key={c.case_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 border-r border-slate-100">
                      <Link
                        href={`/cases/${c.case_id}/copilot`}
                        className="font-semibold text-slate-800 hover:text-sponsor-blue truncate max-w-[200px] block"
                      >
                        {c.name}
                      </Link>
                      <div className="font-mono text-[10px] text-slate-400 font-normal">{c.case_id}</div>
                    </td>
                    <td className="px-3 py-3 text-center border-r border-slate-100">
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700">
                        {c.dtp_stage}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-center font-mono text-xs text-slate-700">{m.stageSlaAdherencePct}%</td>
                    <td
                      className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-mit-red"
                      title="Edits to governance / gate content — higher may mean policy or assistant needs tuning"
                    >
                      {m.governanceEditBurden}
                    </td>
                    <td className="px-3 py-3 text-center font-mono text-xs text-slate-800 font-semibold leading-tight">
                      <div>{m.cycleTimeBusinessDays}d</div>
                      <div
                        className={`text-[10px] font-normal ${
                          m.cycleTimeVsTargetDays > 0
                            ? "text-mit-red/90"
                            : m.cycleTimeVsTargetDays < 0
                              ? "text-emerald-700"
                              : "text-slate-400"
                        }`}
                        title="Operational slip vs benchmark (shown with KPI, not the learning column)"
                      >
                        {m.cycleTimeVsTargetDays > 0 ? "+" : ""}
                        {m.cycleTimeVsTargetDays} vs tgt
                      </div>
                    </td>
                    <td
                      className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-mit-red"
                      title="Times milestone plan was reworked after review — signal for template or forecast trust"
                    >
                      {m.planReworkEventCount}
                    </td>
                    <td className="px-3 py-3 text-center font-mono text-xs text-emerald-800 font-semibold">
                      ${m.identifiedSavingsKUsd}K
                    </td>
                    <td
                      className="px-3 py-3 text-center font-mono text-xs text-mit-red"
                      title="Human changes to savings scenarios or challenged assumptions"
                    >
                      {m.savingsHumanAdjustmentCount}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * Demo KLIs approximate <strong className="text-slate-600">edit density, rework, and human adjustments</strong>{" "}
        (trust / calibration). Production: version diffs on artifacts, audit accept-reject-adjust events, playbook edit
        logs, and savings model change history.
      </div>
    </div>
  );
}
