"use client";

import React from "react";

export type DtpStage = {
  id: string;
  label: string;
  shortLabel?: string;
};

type DtpStepperProps = {
  stages: DtpStage[];
  currentStageId: string;
  completedStageIds?: string[];
  className?: string;
};

export default function DtpStepper({
  stages,
  currentStageId,
  completedStageIds = [],
  className = "",
}: DtpStepperProps) {
  const completed = new Set(completedStageIds);
  const activeIdx = Math.max(
    0,
    stages.findIndex((s) => s.id === currentStageId)
  );

  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-3 shadow-sm ${className}`}>
      <ol className="grid gap-2 md:grid-cols-6">
        {stages.map((stage, idx) => {
          const isActive = stage.id === currentStageId;
          const isDone = completed.has(stage.id) || idx < activeIdx;
          return (
            <li
              key={stage.id}
              className={`rounded-lg border px-3 py-2 transition ${
                isActive
                  ? "border-sponsor-blue bg-blue-50"
                  : isDone
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-slate-200 bg-slate-50"
              }`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                {stage.id}
              </p>
              <p
                className={`mt-0.5 text-xs font-semibold ${
                  isActive ? "text-sponsor-blue" : isDone ? "text-emerald-700" : "text-slate-600"
                }`}
              >
                {stage.shortLabel || stage.label}
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
