"use client";

import React from "react";
import { stageSchema, type DtpFieldSchema } from "@/lib/dtp-stage-schema";
import type { DtpStage } from "@/components/workflow/DtpStepper";

type Props = {
  stages: DtpStage[];
  currentStageId: string;
  stageValuesByStage?: Record<string, Record<string, string>>;
};

function fieldBadgeClass(field: DtpFieldSchema): string {
  if (field.critical) return "bg-red-50 text-red-700 border-red-200";
  if (field.required) return "bg-amber-50 text-amber-800 border-amber-200";
  return "bg-slate-50 text-slate-700 border-slate-200";
}

function fieldBadgeLabel(field: DtpFieldSchema): string {
  if (field.critical) return "critical";
  if (field.required) return "required";
  return "optional";
}

export default function FutureStageRequirements({
  stages,
  currentStageId,
  stageValuesByStage = {},
}: Props) {
  const stageIndex = Math.max(0, stages.findIndex((s) => s.id === currentStageId));
  const futureStages = stages.slice(stageIndex + 1);
  if (futureStages.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 p-4">
        <h3 className="text-slate-800 font-bold text-sm">Future DTP Requirements Preview</h3>
        <p className="text-xs text-slate-500 mt-1">
          Read-only preview so users can prepare data early. Editing unlocks when a stage becomes active.
        </p>
      </div>
      <div className="p-4 space-y-3">
        {futureStages.map((stage) => {
          const schema = stageSchema(stage.id);
          const vals = stageValuesByStage[stage.id] || {};
          const filled = schema.filter((f) => String(vals[f.key] || "").trim().length > 0).length;
          return (
            <details key={stage.id} className="rounded-lg border border-slate-200 bg-white group">
              <summary className="list-none cursor-pointer px-3 py-2 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{stage.id}</p>
                  <p className="text-sm font-semibold text-slate-800">{stage.label}</p>
                </div>
                <div className="text-right text-xs">
                  <p className="text-slate-600">{filled}/{schema.length} prefilled</p>
                  <p className="text-slate-400">locked until active</p>
                </div>
              </summary>
              <div className="px-3 pb-3 space-y-2">
                {schema.map((field) => (
                  <div key={`${stage.id}-${field.key}`} className="rounded border border-slate-100 bg-slate-50/80 px-2.5 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold text-slate-800">{field.label}</p>
                      <span className={`text-[10px] border px-1.5 py-0.5 rounded ${fieldBadgeClass(field)}`}>
                        {fieldBadgeLabel(field)}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      {field.document_dependency ? `depends on ${field.document_dependency} document` : "manual input or extraction"}
                    </p>
                    {String(vals[field.key] || "").trim() ? (
                      <p className="text-[11px] text-emerald-700 mt-1">prefilled: {String(vals[field.key]).slice(0, 90)}</p>
                    ) : (
                      <p className="text-[11px] text-slate-400 mt-1">not filled yet</p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}

