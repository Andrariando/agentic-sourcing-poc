"use client";

import React from "react";

export type DtpStage = {
  id: string;
  label: string;
  shortLabel?: string;
};

type DtpStepperProps = {
  stages: DtpStage[];
  /** Stage the case is actually in (from server / workflow). */
  workflowStageId: string;
  /** Stage the user is viewing (form + right rail). */
  selectedStageId: string;
  /** Stages that are complete or before the current workflow index. */
  completedStageIds?: string[];
  onSelectStage: (stageId: string) => void;
  className?: string;
};

export default function DtpStepper({
  stages,
  workflowStageId,
  selectedStageId,
  completedStageIds = [],
  onSelectStage,
  className = "",
}: DtpStepperProps) {
  const completed = new Set(completedStageIds);
  const activeIdx = Math.max(0, stages.findIndex((s) => s.id === workflowStageId));

  return (
    <div className={`relative z-10 rounded-xl border border-slate-200 bg-white p-2 shadow-sm ${className}`}>
      <p className="px-1.5 pb-2 text-[10px] font-medium uppercase tracking-wide text-slate-400">
        Workflow · tap a stage · only <span className="text-slate-600">Active</span> edits
      </p>
      <ol
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6 touch-manipulation"
        role="tablist"
        aria-label="DTP stages"
      >
        {stages.map((stage, idx) => {
          const isWorkflowHere = stage.id === workflowStageId;
          const isSelected = stage.id === selectedStageId;
          const isDone = completed.has(stage.id) || idx < activeIdx;
          const tabLabel = `${stage.id} ${stage.shortLabel || stage.label}${isWorkflowHere ? " (active case stage)" : ""}${isSelected ? " — selected" : ""}`;
          return (
            <li key={stage.id} className="min-w-0">
              <button
                type="button"
                role="tab"
                aria-selected={isSelected}
                title={tabLabel}
                onClick={() => onSelectStage(stage.id)}
                className={`w-full min-h-[3.75rem] cursor-pointer text-left rounded-lg border px-2.5 py-2.5 transition active:scale-[0.99] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sponsor-blue ${
                  isSelected
                    ? "border-sponsor-blue bg-blue-50 ring-2 ring-sponsor-blue/30 shadow-sm"
                    : isDone
                      ? "border-emerald-200 bg-emerald-50/80 hover:border-emerald-400 hover:bg-emerald-50"
                      : "border-slate-200 bg-slate-50 hover:border-slate-400 hover:bg-white"
                }`}
              >
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 flex items-center justify-between gap-1">
                  {stage.id}
                  {isWorkflowHere ? (
                    <span className="rounded bg-sponsor-blue/10 px-1.5 text-[8px] font-extrabold uppercase tracking-tight text-sponsor-blue">Active</span>
                  ) : null}
                </p>
                <p
                  className={`mt-0.5 text-[11px] font-semibold leading-tight ${
                    isSelected ? "text-sponsor-blue" : isDone ? "text-emerald-800" : "text-slate-600"
                  }`}
                >
                  {stage.shortLabel || stage.label}
                </p>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
