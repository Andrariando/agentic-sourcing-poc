"use client";

import React from "react";

export interface S2CExecutionMatrixProps {
  metrics?: {
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
  };
}

export default function S2CExecutionMatrix({ metrics }: S2CExecutionMatrixProps) {
  const overall = metrics?.overall;
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">S2C performance overview</h2>
          <p className="text-sm text-slate-500 mt-1">
            Three high-level metrics for reliability, explanation acceptance, and scoring input completeness.
          </p>
        </div>
      </div>

      <div className="px-5 py-4 bg-white">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">Overall Metrics</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">AI Reliability Score</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {overall?.ai_reliability_score_pct == null ? "—" : `${overall.ai_reliability_score_pct}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Overall score based on human edits across opportunities.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">KLI - Signal Attribution Accuracy</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {overall?.signal_attribution_accuracy_pct == null
                ? "—"
                : `${overall.signal_attribution_accuracy_pct.toFixed(1)}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              ProcuraBot explanation acceptance ({overall?.thumbs_up ?? 0}/{overall?.thumbs_total ?? 0} thumbs up).
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">KPI - Signal Coverage Rate</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {overall?.signal_coverage_rate_pct == null ? "—" : `${overall.signal_coverage_rate_pct.toFixed(1)}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Cases with all four required signals (
              {overall?.signal_coverage_cases_with_all_inputs ?? 0}/{overall?.signal_coverage_active_cases_total ?? 0} active cases).
            </p>
          </div>
        </div>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * Signal coverage requires contract expiry, spend, category strategy, and supplier risk input availability.
      </div>
    </div>
  );
}
