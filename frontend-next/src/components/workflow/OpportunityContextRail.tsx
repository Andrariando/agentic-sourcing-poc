"use client";

import React from "react";

type OpportunityContextRailProps = {
  typeLabel: string;
  opportunityLabel: string;
  opportunityRef: string;
  spendUsd: number;
  monthsToExpiry: string;
  implementationMonths: string;
  preferredSupplierStatus: string;
  artifactCount: number;
  hasReview: boolean;
  isApproved: boolean;
};

export default function OpportunityContextRail(props: OpportunityContextRailProps) {
  const {
    typeLabel,
    opportunityLabel,
    opportunityRef,
    spendUsd,
    monthsToExpiry,
    implementationMonths,
    preferredSupplierStatus,
    artifactCount,
    hasReview,
    isApproved,
  } = props;

  const handoffComplete = artifactCount > 0 && (monthsToExpiry !== "—" || implementationMonths !== "—");

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Current opportunity</p>
        <p className="mt-1 text-sm font-semibold text-slate-900">{opportunityLabel}</p>
        <p className="mt-1 text-xs font-mono text-slate-500">{opportunityRef}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
            {typeLabel}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
            Spend ${Number(spendUsd || 0).toLocaleString()}
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Relevant info</p>
        <ul className="mt-2 space-y-2 text-xs text-slate-700">
          <li>Months to expiry: <span className="font-semibold">{monthsToExpiry}</span></li>
          <li>Implementation timeline: <span className="font-semibold">{implementationMonths}</span></li>
          <li>Preferred supplier: <span className="font-semibold">{preferredSupplierStatus || "—"}</span></li>
          <li>Supporting artifacts: <span className="font-semibold">{artifactCount}</span></li>
        </ul>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">S2C handoff readiness</p>
        <ul className="mt-2 space-y-1.5 text-xs text-slate-700">
          <li>{hasReview ? "Yes" : "No"} · Review captured</li>
          <li>{isApproved ? "Yes" : "No"} · Approved to execution</li>
          <li>{handoffComplete ? "Yes" : "Partial"} · Data package complete</li>
        </ul>
      </div>
    </div>
  );
}
