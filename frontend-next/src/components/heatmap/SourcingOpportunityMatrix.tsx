"use client";

import React from "react";

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
  activePreviewSummary?: {
    job_id?: string | null;
    status?: string;
    total_rows?: number;
    covered_rows?: number;
    ready_rows?: number;
    ready_with_warnings_rows?: number;
    needs_review_rows?: number;
  };
}

export default function SourcingOpportunityMatrix({
  opportunities,
  summary,
  activePreviewSummary,
}: SourcingOpportunityMatrixProps) {
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

  // Combined coverage:
  // numerator   = covered staged upload rows + covered rows in main table
  // denominator = total staged upload rows + total rows in main table
  // Main table rows are already approved/scored, so they count as covered.
  const mainTotal = rows.length;
  const mainCovered = mainTotal;
  const stagedTotal = Number(activePreviewSummary?.total_rows ?? 0);
  const stagedCovered = Number(activePreviewSummary?.covered_rows ?? 0);
  const combinedTotal = mainTotal + stagedTotal;
  const combinedCovered = mainCovered + stagedCovered;
  const coveragePct = combinedTotal > 0 ? Number(((combinedCovered / combinedTotal) * 100).toFixed(1)) : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="p-5 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">Performance Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">
            Three high-level metrics for reliability, explanation acceptance, and signal coverage.
          </p>
        </div>
      </div>

      <div className="px-5 py-4 bg-white">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">Overall Metrics</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">KPI: AI Reliability Rate</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {avgReliability == null ? "—" : `${avgReliability}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Overall level based on how many human edits happen across opportunities.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              KLI - Signal Attribution Accuracy
            </p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {signalAcc == null ? "—" : `${signalAcc.toFixed(1)}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Acceptance rate of ProcuraBot explanations ({thumbsUp}/{thumbsTotal} thumbs up).
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">KPI - Signal Coverage Rate</p>
            <p className="text-3xl font-bold text-slate-900 mt-2">
              {coveragePct == null ? "—" : `${coveragePct}%`}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Combined staged + main table coverage ({combinedCovered}/{combinedTotal}).
            </p>
          </div>
        </div>
      </div>
      <div className="bg-slate-50 px-5 py-3 border-t border-slate-200 text-[11px] text-slate-500 text-center leading-snug">
        * Formula: (covered staged upload rows + main table rows) / (total staged upload rows + main table rows) x 100.
      </div>
    </div>
  );
}
