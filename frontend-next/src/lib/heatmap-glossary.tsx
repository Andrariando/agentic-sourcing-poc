import type { ReactNode } from "react";

/**
 * Hover (native tooltip) copy for heatmap scoring acronyms — used with <abbr> or title=.
 */
export const HEATMAP_GLOSSARY = {
  psNew:
    "PS_new — Prioritization score for new sourcing requests: weighted IUS + ES + CSIS + SAS (0–10). Used on the intake flow.",
  psContract:
    "PS_contract — Score for existing contracts: weighted EUS + FIS + RSS + SCS + SAS (0–10). Used for renewals in the batch pipeline.",
  ius: "IUS — Implementation Urgency Score: how urgent the go-live or delivery timeline is (0–10).",
  es: "ES — Estimated Spend Score: size of this request versus the largest estimated intakes in the pipeline (0–10).",
  csis: "CSIS — Category Spend Importance Score: how important spend in this category is relative to peer categories (0–10).",
  sas: "SAS — Strategic Alignment Score: alignment with category strategy and preferred-supplier status (0–10).",
  eus: "EUS — Expiry Urgency Score: how soon the contract expires; higher means act sooner on renewal (0–10).",
  fis: "FIS — Financial Impact Score: financial scale of the contract (TCV or ACV) versus other deals in the same category (0–10).",
  rss: "RSS — Supplier Risk Score: risk signal from supplier health and performance metrics (0–10).",
  scs: "SCS — Spend Concentration Score: how concentrated spend is with this supplier in the category (0–10).",
  acv: "ACV — Annual Contract Value: yearly value of the agreement (optional config via HEATMAP_FIS_USE_ACV).",
  tcv: "TCV — Total Contract Value: full value over the contract term (default for FIS in batch scoring).",
  tier:
    "Priority band from total score: High is most urgent through Lowest; drives review and approval routing.",
  t1: "High priority — score ≥ 8.0: immediate / critical sourcing action.",
  t2: "Medium priority — 6.0–7.99: benchmark / plan within the quarter.",
  t3: "Low priority — 4.0–5.99: monitor.",
  t4: "Lowest priority — score < 4.0: defer unless capacity allows.",
  kpi: "KPI — Key Performance Indicator: how well the process or model is performing on outcomes (time, quality, savings, etc.).",
  kli:
    "KLI — Key Learning Indicator: signals about human trust, calibration, and friction — e.g. edit density on AI/draft outputs, override rate, rework loops, and how often people change recommended numbers or gates. High friction often means teach the model, fix the playbook, or clarify policy — not only that something was “late.”",
  chartAxisX:
    "Horizontal axis: renewals blend FIS with SCS; new requests blend ES with CSIS (all 0–10 sub-scores).",
  chartAxisY:
    "Vertical axis: renewals blend EUS and RSS; new requests use IUS (implementation urgency).",
  agenticScore:
    "Total weighted score (0–10) from the scoring engine before human priority override; combines the visible sub-scores.",
} as const;

export type HeatmapGlossaryKey = keyof typeof HEATMAP_GLOSSARY;

/** Abbreviation with native browser tooltip on hover (underline hints that more info exists). */
export function HeatmapAbbr({ term, children }: { term: HeatmapGlossaryKey; children: ReactNode }) {
  return (
    <abbr
      title={HEATMAP_GLOSSARY[term]}
      className="cursor-help underline decoration-dotted decoration-slate-500/70 underline-offset-[3px]"
    >
      {children}
    </abbr>
  );
}
