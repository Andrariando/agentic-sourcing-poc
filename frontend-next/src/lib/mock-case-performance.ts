/**
 * Illustrative supplier / case performance KPIs for demos.
 * Not sourced from live ERP — deterministic per case id so UX review is stable.
 */
export type MockPerformanceKpi = { label: string; value: string; hint?: string };
export type MockPerformanceInsight = {
  period: string;
  kpis: MockPerformanceKpi[];
  bullets: string[];
  sourceNote: string;
  handoffTag: string | null;
};

function simpleHash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function getMockCasePerformanceInsight(params: {
  caseId: string;
  name?: string;
  categoryId?: string;
  dtpStage?: string;
  triggerSource?: string;
  supplierId?: string;
}): MockPerformanceInsight {
  const { caseId, name = "", categoryId = "", dtpStage = "", triggerSource = "", supplierId = "" } = params;
  const raw = `${caseId}|${name}|${categoryId}|${supplierId}`;
  const h = simpleHash(raw);
  const isHeatmapHandoff =
    /heatmap|opportunity/i.test(triggerSource) || /opportunityheatmap/i.test(triggerSource);

  const n = (base: number, span: number) => base + (h % (span + 1));

  const cat = categoryId.toUpperCase();
  const nameU = name.toUpperCase();
  const cloudish = cat.includes("CLOUD") || nameU.includes("CLOUD") || nameU.includes("AWS") || nameU.includes("AZURE");
  const secish = cat.includes("SECURITY") || cat.includes("SEC") || nameU.includes("SECURITY");

  const kpis: MockPerformanceKpi[] = cloudish
    ? [
        { label: "Workload uptime (90d)", value: `${(99.2 + (h % 8) / 10).toFixed(1)}%`, hint: "pilot regions" },
        { label: "P1 incidents (90d)", value: String(n(0, 3)), hint: "supplier-attributed" },
        { label: "Mean ticket resolution", value: `${n(2, 8)}h`, hint: "severity 2–3" },
        { label: "Forecast vs actual spend", value: `${-3 + (h % 7)}%`, hint: "YTD cloud run-rate" },
      ]
    : secish
      ? [
          { label: "Patch SLA met", value: `${92 + (h % 7)}%`, hint: "critical CVE window" },
          { label: "Open findings", value: String(n(0, 4)), hint: "assessment + pen test" },
          { label: "Users covered (seat sync)", value: `${96 + (h % 4)}%`, hint: "IdP reconciliation" },
          { label: "Renewal price delta vs index", value: `+${(3 + (h % 5)).toFixed(1)}%`, hint: "vs peer basket" },
        ]
      : [
          { label: "On-time delivery (90d)", value: `${93 + (h % 6)}%`, hint: "PO lines" },
          { label: "Invoice match rate", value: `${97 + (h % 3)}%`, hint: "3-way match" },
          { label: "Open disputes", value: String(n(0, 3)), hint: "active" },
          { label: "NPS (business owners)", value: `${36 + (h % 15)}`, hint: "last pulse" },
        ];

  const bullets: string[] = cloudish
    ? [
        `Migration runway: ${6 + (h % 6)} critical apps still on legacy networking; pilot exit target Q${1 + (h % 4)}.`,
        `${name ? "Stakeholder" : "Category"} read: dual-vendor posture (AWS/Azure) remains valid; watch egress cost variance on last bill cycle.`,
        `One vendor missed DR tabletop evidence deadline — flagged for DTP-01 governance, not blocking monitor posture.`,
      ]
    : secish
      ? [
          "Control evidence pack 90% complete; two SOC2 sub-controls pending vendor attestation.",
          "No Sev1 in trailing quarter; degradation risk concentrated in legacy agent estate.",
        ]
      : [
          "Spend mix stable; top SKU concentration unchanged versus prior quarter.",
          "Delivery performance within SLA; two carriers driving 80% of delays on inbound leg.",
        ];

  return {
    period: "Trailing 90 days · illustrative demo data",
    kpis,
    bullets,
    sourceNote:
      "Synthetic snapshot for demo storytelling. Connect to spend / ITSM / contract warehouse to replace with production metrics.",
    handoffTag: isHeatmapHandoff ? "Opportunity prioritization handoff" : dtpStage.startsWith("DTP-01") ? "Early-stage — baseline signals" : null,
  };
}
