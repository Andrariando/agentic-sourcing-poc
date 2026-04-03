/**
 * Classic procurement S2C — KPI vs KLI (Key Learning Indicator).
 *
 * KPIs: operational outcomes (SLA adherence, cycle time, savings).
 * KLIs: human-in-the-loop learning signals — edits, rework, overrides, mistrust of drafts — for demo use hash seeding.
 * Production: wire to document versioning, audit log (accept/reject/adjust), CRM of playbook edits, etc.
 */
export type S2CExecutionMetrics = {
  /** KPI · SLA — % of gated checkpoints completed inside policy window. */
  stageSlaAdherencePct: number;
  /**
   * KLI · SLA — governance edit burden: substantive edits to SLA/gate packs or automated checklist lines
   * (proxy for mistrust or policy mismatch). Higher → more teaching / clearer rules.
   */
  governanceEditBurden: number;

  /** KPI · Cycle — elapsed business days on path. */
  cycleTimeBusinessDays: number;
  /** Shown with KPI: slip vs benchmark (operational, not the KLI). */
  cycleTimeVsTargetDays: number;
  /**
   * KLI · Cycle — how often the milestone plan was sent back for rework after human review
   * (learning signal on forecasting / template quality).
   */
  planReworkEventCount: number;

  /** KPI · Savings — identified savings vs baseline, $ thousands. */
  identifiedSavingsKUsd: number;
  /**
   * KLI · Savings — count of human adjustments to savings model lines, challenged should-cost,
   * or rejected auto-built scenarios (trust / calibration on commercial analytics).
   */
  savingsHumanAdjustmentCount: number;
};

function stableHash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function getS2CExecutionMetricsForCase(params: {
  caseId: string;
  name?: string;
  dtpStage?: string;
  status?: string;
}): S2CExecutionMetrics {
  const raw = `${params.caseId}|${params.name ?? ""}|${params.dtpStage ?? ""}|${params.status ?? ""}`;
  const h = stableHash(raw);
  const n = (a: number, b: number) => a + (h % (b - a + 1));
  const f = (base: number, span: number, dec = 1) =>
    Math.round((base + ((h % 1000) / 1000) * span) * 10 ** dec) / 10 ** dec;

  const stage = (params.dtpStage ?? "").toUpperCase();
  const stageBoost = stage.includes("03") || stage.includes("3") ? 25 : stage.includes("02") || stage.includes("2") ? 12 : 0;
  const targetBand = 28 + (h % 40) + Math.floor(stageBoost / 2);
  const slip = (h % 27) - 8;
  const cycleTimeBusinessDays = Math.max(8, targetBand + slip);
  const cycleTimeVsTargetDays = cycleTimeBusinessDays - targetBand;

  const savingsBase = 95 + (h % 520);
  const identifiedSavingsKUsd = Math.round(savingsBase + (h % 77) / 10);

  return {
    stageSlaAdherencePct: f(84, 14),
    governanceEditBurden: n(2, 24),
    cycleTimeBusinessDays,
    cycleTimeVsTargetDays,
    planReworkEventCount: n(0, 5),
    identifiedSavingsKUsd,
    savingsHumanAdjustmentCount: n(0, 8),
  };
}
