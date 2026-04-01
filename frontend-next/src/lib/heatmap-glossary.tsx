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
    "Tier — Priority band from the total score: T1 most urgent through T4 lowest; drives review and approval routing.",
  t1: "Tier 1 — Critical (score ≥ 8.0): immediate sourcing action.",
  t2: "Tier 2 — High (6.0–7.99): plan within the quarter.",
  t3: "Tier 3 — Medium (4.0–5.99): monitor.",
  t4: "Tier 4 — Low (score < 4.0): defer unless capacity allows.",
  kpi: "KPI — Key Performance Indicator: pipeline efficiency metric in the outcomes matrix.",
  kli: "KLI — Learning / intervention lens: tracks overrides, edits, and similar human-in-the-loop signals.",
  chartAxisX:
    "Horizontal axis: renewals blend FIS with SCS; new requests blend ES with CSIS (all 0–10 sub-scores).",
  chartAxisY:
    "Vertical axis: renewals blend EUS and RSS; new requests use IUS (implementation urgency).",
  agenticScore:
    "Total weighted score (0–10) from the scoring engine before human tier override; combines the visible sub-scores.",
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
