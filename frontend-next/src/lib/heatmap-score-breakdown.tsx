import type { HeatmapGlossaryKey } from "@/lib/heatmap-glossary";
import { HEATMAP_GLOSSARY } from "@/lib/heatmap-glossary";

export type HeatmapOpportunityLike = {
  justification_summary?: string | null;
  total_score?: number | null;
  contract_id?: string | null;
  request_id?: string | null;
  eus_score?: number | null;
  ius_score?: number | null;
  fis_score?: number | null;
  es_score?: number | null;
  rss_score?: number | null;
  scs_score?: number | null;
  csis_score?: number | null;
  sas_score?: number | null;
};

const METRIC_META: Record<
  string,
  { label: string; glossaryKey: HeatmapGlossaryKey }
> = {
  EUS: { label: "Expiry urgency", glossaryKey: "eus" },
  FIS: { label: "Financial impact", glossaryKey: "fis" },
  RSS: { label: "Supplier risk", glossaryKey: "rss" },
  SCS: { label: "Spend concentration", glossaryKey: "scs" },
  SAS: { label: "Strategic alignment", glossaryKey: "sas" },
  IUS: { label: "Implementation urgency", glossaryKey: "ius" },
  ES: { label: "Estimated spend", glossaryKey: "es" },
  CSIS: { label: "Category importance", glossaryKey: "csis" },
};

/** Defaults aligned with `backend/heatmap/agents/supervisor_agent.py` */
const DEFAULT_W_CONTRACT: Record<string, number> = {
  EUS: 0.3,
  FIS: 0.25,
  RSS: 0.2,
  SCS: 0.15,
  SAS: 0.1,
};
const DEFAULT_W_NEW: Record<string, number> = {
  IUS: 0.3,
  ES: 0.3,
  CSIS: 0.25,
  SAS: 0.15,
};

export type ScoreBreakdownRow = {
  code: string;
  label: string;
  glossaryKey: HeatmapGlossaryKey;
  score: number;
  weight: number;
  points: number;
};

function isNewRequestOpp(o: HeatmapOpportunityLike): boolean {
  return Boolean(o.request_id) && !o.contract_id;
}

function num(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Parse engine strings like:
 * `Contract scored 6.96. EUS(10.0)*0.3 + FIS(6.88)*0.25 + ...`
 */
export function parseJustificationSummary(summary: string): {
  rows: ScoreBreakdownRow[];
  learningNote?: string;
} | null {
  if (!summary?.trim()) return null;
  const [main, rest] = summary.split(/\s*\|\s*Learning:\s*/i);
  const learningNote = rest?.trim() || undefined;

  const rowRegex = /(\w+)\(([\d.]+)\)\*([\d.]+)/g;
  const rows: ScoreBreakdownRow[] = [];
  let m: RegExpExecArray | null;
  while ((m = rowRegex.exec(main)) !== null) {
    const code = m[1];
    const score = parseFloat(m[2]);
    const weight = parseFloat(m[3]);
    if (!Number.isFinite(score) || !Number.isFinite(weight)) continue;
    const meta = METRIC_META[code];
    rows.push({
      code,
      label: meta?.label ?? code,
      glossaryKey: meta?.glossaryKey ?? "agenticScore",
      score,
      weight,
      points: score * weight,
    });
  }
  if (rows.length === 0) return null;
  return { rows, learningNote };
}

function fallbackRows(o: HeatmapOpportunityLike): ScoreBreakdownRow[] {
  const isNew = isNewRequestOpp(o);
  const w = isNew ? DEFAULT_W_NEW : DEFAULT_W_CONTRACT;
  const entries: [string, number | null | undefined][] = isNew
    ? [
        ["IUS", o.ius_score],
        ["ES", o.es_score],
        ["CSIS", o.csis_score],
        ["SAS", o.sas_score],
      ]
    : [
        ["EUS", o.eus_score],
        ["FIS", o.fis_score],
        ["RSS", o.rss_score],
        ["SCS", o.scs_score],
        ["SAS", o.sas_score],
      ];
  const rows: ScoreBreakdownRow[] = [];
  for (const [code, raw] of entries) {
    const weight = w[code];
    if (weight == null) continue;
    const score = num(raw);
    const meta = METRIC_META[code];
    rows.push({
      code,
      label: meta?.label ?? code,
      glossaryKey: meta?.glossaryKey ?? "agenticScore",
      score,
      weight,
      points: score * weight,
    });
  }
  return rows;
}

function getBreakdownRows(o: HeatmapOpportunityLike): {
  rows: ScoreBreakdownRow[];
  learningNote?: string;
  fromParse: boolean;
} {
  const parsed = parseJustificationSummary(String(o.justification_summary ?? ""));
  if (parsed?.rows?.length) {
    return { rows: parsed.rows, learningNote: parsed.learningNote, fromParse: true };
  }
  return { rows: fallbackRows(o), learningNote: undefined, fromParse: false };
}

export function HeatmapScoreBreakdown({
  opportunity,
  compact = false,
}: {
  opportunity: HeatmapOpportunityLike;
  compact?: boolean;
}) {
  const { rows, learningNote, fromParse } = getBreakdownRows(opportunity);
  const sorted = [...rows].sort((a, b) => b.points - a.points);
  const total = num(opportunity.total_score);
  const sumPoints = rows.reduce((s, r) => s + r.points, 0);

  const tableCls = compact
    ? "text-[11px] leading-tight"
    : "text-sm";
  const headCls = compact ? "text-[9px]" : "text-xs";

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      {!compact && (
        <p className="text-xs text-slate-600 leading-relaxed">
          Total score is a <span className="font-medium text-slate-700">weighted blend</span> of the metrics below (each
          is 0–10). Rows are sorted by how many points each metric added so you can see what drove the priority.
        </p>
      )}
      {compact && (
        <p className="text-[10px] uppercase tracking-wide text-slate-400 font-medium">Weighted score mix</p>
      )}

      <div className={`rounded-lg border border-slate-200 overflow-hidden bg-white ${compact ? "" : "shadow-sm"}`}>
        <table className={`w-full ${tableCls}`}>
          <thead>
            <tr className="bg-slate-50 text-slate-500 text-left border-b border-slate-200">
              <th className={`${headCls} font-semibold uppercase tracking-wide px-2 py-1.5 ${compact ? "pl-2" : "px-3 py-2"}`}>
                Metric
              </th>
              <th className={`${headCls} font-semibold uppercase tracking-wide px-2 py-1.5 text-right`} title="Sub-score">
                /10
              </th>
              <th className={`${headCls} font-semibold uppercase tracking-wide px-2 py-1.5 text-right`} title="Weight in formula">
                Wt
              </th>
              <th className={`${headCls} font-semibold uppercase tracking-wide px-2 py-1.5 text-right`} title="Contribution">
                Pts
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((r) => (
              <tr key={r.code} className="text-slate-700">
                <td className={`px-2 py-1.5 ${compact ? "" : "px-3 py-2"}`}>
                  <span className="font-mono text-slate-500 mr-1">{r.code}</span>
                  <span
                    className="text-slate-700 border-b border-dotted border-slate-300 cursor-help"
                    title={HEATMAP_GLOSSARY[r.glossaryKey]}
                  >
                    {r.label}
                  </span>
                </td>
                <td className="font-mono text-right px-2 py-1.5 tabular-nums">{r.score.toFixed(1)}</td>
                <td className="font-mono text-right px-2 py-1.5 tabular-nums text-slate-500">
                  {(r.weight * 100).toFixed(0)}%
                </td>
                <td className="font-mono text-right px-2 py-1.5 tabular-nums font-semibold text-slate-900">
                  {r.points.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!compact && (
        <div className="flex justify-between items-baseline gap-2 text-sm text-slate-600">
          <span>
            Sum of contributions:{" "}
            <span className="font-mono font-medium text-slate-800">{sumPoints.toFixed(2)}</span>
          </span>
          <span className="text-right">
            Reported total:{" "}
            <span className="font-bold text-sponsor-blue tabular-nums">{total.toFixed(1)}</span>
            <span className="text-slate-400">/10</span>
          </span>
        </div>
      )}

      {compact && Math.abs(sumPoints - total) > 0.08 && (
        <p className="text-[10px] text-slate-500 leading-snug">
          Weighted sum {sumPoints.toFixed(2)} vs stored {total.toFixed(1)} — rounding or calibration.
        </p>
      )}

      {!compact && Math.abs(sumPoints - total) > 0.15 && (
        <p className="text-[11px] text-slate-500 leading-snug">
          Small gaps are normal: the headline total is the stored score (rounding and optional calibration may differ
          slightly from the raw weighted sum shown in the engine line{fromParse ? "" : " (weights are defaults here)"}).
        </p>
      )}

      {learningNote && (
        <p className={`text-slate-600 ${compact ? "text-[10px] leading-snug" : "text-xs leading-snug"} border-l-2 border-amber-200 bg-amber-50/80 pl-2 py-1 rounded-r`}>
          <span className="font-semibold text-amber-900">Learning adjustment: </span>
          {learningNote}
        </p>
      )}
    </div>
  );
}
