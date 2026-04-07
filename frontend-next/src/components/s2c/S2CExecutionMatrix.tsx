"use client";

import React from "react";
import Link from "next/link";

export interface S2CCaseRow {
  case_id: string;
  name: string;
  category_id?: string;
  dtp_stage: string;
  status?: string;
}

export interface S2CExecutionMatrixProps {
  cases: S2CCaseRow[];
  metrics?: {
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
  };
}

/**
 * S2C performance split into global and detailed KPIs.
 */
export default function S2CExecutionMatrix({ cases, metrics }: S2CExecutionMatrixProps) {
  const detailMap = new Map((metrics?.detailed || []).map((d) => [d.case_id, d]));
  const rows = cases.map((c) => ({
    case: c,
    detail: detailMap.get(c.case_id),
  }));
  const overall = metrics?.overall;
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">S2C performance overview</h2>
          <p className="text-sm text-slate-500 mt-1">
            Global KPI and detailed KPI for AI reliability plus signal attribution quality.
          </p>
        </div>
      </div>

      <div className="px-5 py-4 border-b border-slate-200 bg-white">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">1. Overall Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">AI Reliability Score</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {overall?.ai_reliability_score_pct == null ? "—" : `${overall.ai_reliability_score_pct}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">Average of all case-level AI reliability scores.</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Signal Attribution Accuracy
            </p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {overall?.signal_attribution_accuracy_pct == null
                ? "—"
                : `${overall.signal_attribution_accuracy_pct.toFixed(1)}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              ProcuraBot thumbs up / total thumbs ({overall?.thumbs_up ?? 0}/{overall?.thumbs_total ?? 0}).
            </p>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="px-5 py-3 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">2. Detailed Performance</h3>
          <p className="text-xs text-slate-500 mt-1">
            AI reliability by case, derived from human change events in decisions/review flow.
          </p>
        </div>
        <table className="w-full text-left border-collapse text-sm min-w-[760px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold uppercase tracking-widest text-slate-500">
              <th className="px-4 py-3 border-r border-slate-200 w-64">
                Case
              </th>
              <th className="px-3 py-3 border-r border-slate-200 text-center w-24" title="Current DTP stage">
                Stage
              </th>
              <th className="px-3 py-3 text-center border-r border-slate-200">AI Reliability</th>
              <th className="px-3 py-3 text-center border-r border-slate-200">Human Changes</th>
              <th className="px-3 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {cases.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-500 text-sm">
                  No cases to display. Approve a prioritization row or open a case from the S2C Case Dashboard.
                </td>
              </tr>
            ) : (
              rows.slice(0, 25).map(({ case: c, detail }) => {
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
                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs font-semibold text-slate-800">
                      {detail?.ai_reliability_pct != null ? `${detail.ai_reliability_pct}%` : "—"}
                    </td>
                    <td className="px-3 py-3 text-center border-r border-slate-100 font-mono text-xs text-slate-700">
                      {detail?.human_change_count ?? 0}
                    </td>
                    <td className="px-3 py-3 text-center text-xs text-slate-600">{c.status || "In Progress"}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * Detailed reliability is derived from human change events in decision/activity logs. Signal attribution uses
        thumbs feedback recorded from ProcuraBot responses.
      </div>
    </div>
  );
}
