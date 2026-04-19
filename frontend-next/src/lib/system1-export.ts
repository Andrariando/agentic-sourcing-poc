/**
 * Client-side export for System 1 upload preview (CSV / Excel / PDF / Word).
 * Uses merged preview rows (after inline edits) when provided.
 */

export type ExportScope = "all" | "renewal_showcase";

export type PreviewRowLike = {
  row_id: string;
  row_type: string;
  source_filename: string;
  category: string;
  subcategory?: string | null;
  supplier_name?: string | null;
  contract_id?: string | null;
  request_title?: string | null;
  estimated_spend_usd: number;
  implementation_timeline_months?: number | null;
  months_to_expiry?: number | null;
  computed_total_score?: number | null;
  computed_tier?: string | null;
  computed_confidence?: number | null;
  readiness_status?: string | null;
  valid_for_approval: boolean;
};

function normContractId(raw: string | null | undefined): string {
  return (raw || "").trim().replace(/`/g, "").toLowerCase();
}

/** Top renewal opportunities: ready status, deduped by contract, highest score first. */
export function pickShowcaseRenewals(rows: PreviewRowLike[], limit: number): PreviewRowLike[] {
  const renewals = rows.filter(
    (r) => r.row_type === "renewal" && r.readiness_status === "ready"
  );
  const best = new Map<string, PreviewRowLike>();
  for (const r of renewals) {
    const key = normContractId(r.contract_id) || r.row_id;
    const prev = best.get(key);
    const score = Number(r.computed_total_score ?? 0);
    const spend = Number(r.estimated_spend_usd ?? 0);
    if (!prev) {
      best.set(key, r);
      continue;
    }
    const ps = Number(prev.computed_total_score ?? 0);
    if (score > ps || (score === ps && spend > Number(prev.estimated_spend_usd ?? 0))) {
      best.set(key, r);
    }
  }
  return Array.from(best.values())
    .sort((a, b) => {
      const ds =
        Number(b.computed_total_score ?? 0) - Number(a.computed_total_score ?? 0);
      if (ds !== 0) return ds;
      return Number(b.estimated_spend_usd ?? 0) - Number(a.estimated_spend_usd ?? 0);
    })
    .slice(0, limit);
}

export function flattenPreviewRow(r: PreviewRowLike): Record<string, string | number | boolean | null> {
  return {
    row_id: r.row_id,
    row_type: r.row_type,
    supplier_name: r.supplier_name ?? "",
    category: r.category ?? "",
    subcategory: r.subcategory ?? "",
    contract_id: r.contract_id ?? "",
    request_title: r.request_title ?? "",
    estimated_spend_usd: r.estimated_spend_usd ?? 0,
    months_to_expiry: r.months_to_expiry ?? "",
    implementation_timeline_months: r.implementation_timeline_months ?? "",
    computed_total_score: r.computed_total_score ?? "",
    computed_tier: r.computed_tier ?? "",
    computed_confidence: r.computed_confidence ?? "",
    readiness_status: r.readiness_status ?? "",
    valid_for_approval: r.valid_for_approval,
    source_filename: r.source_filename ?? "",
  };
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toCsv(rows: Record<string, string | number | boolean | null>[]): string {
  if (rows.length === 0) return "";
  const cols = Object.keys(rows[0]);
  const esc = (v: string | number | boolean | null) => {
    const s = v === null || v === undefined ? "" : String(v);
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const lines = [cols.join(",")];
  for (const row of rows) {
    lines.push(cols.map((c) => esc(row[c] as string | number | boolean | null)).join(","));
  }
  return lines.join("\r\n");
}

export function exportPreviewCsv(
  rows: PreviewRowLike[],
  filenameBase: string
): void {
  const flat = rows.map(flattenPreviewRow);
  const csv = toCsv(flat);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, `${filenameBase}.csv`);
}

export async function exportPreviewXlsx(
  rows: PreviewRowLike[],
  filenameBase: string
): Promise<void> {
  const XLSX = await import("xlsx");
  const flat = rows.map(flattenPreviewRow);
  const ws = XLSX.utils.json_to_sheet(flat);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Preview");
  XLSX.writeFile(wb, `${filenameBase}.xlsx`);
}

/** Compact columns for PDF / Word tables. */
function summaryRows(rows: PreviewRowLike[]): string[][] {
  const head = [
    "Type",
    "Supplier",
    "Contract / request",
    "Category",
    "Spend (USD)",
    "Tier",
    "Score",
    "Readiness",
  ];
  const body: string[][] = [head];
  for (const r of rows) {
    body.push([
      r.row_type,
      r.supplier_name ?? "",
      (r.contract_id || r.request_title || "").toString(),
      r.category ?? "",
      String(r.estimated_spend_usd ?? 0),
      r.computed_tier ?? "",
      r.computed_total_score != null ? String(r.computed_total_score) : "",
      r.readiness_status ?? "",
    ]);
  }
  return body;
}

export async function exportPreviewPdf(
  rows: PreviewRowLike[],
  filenameBase: string,
  title: string
): Promise<void> {
  const [{ default: jsPDF }, { default: autoTable }] = await Promise.all([
    import("jspdf"),
    import("jspdf-autotable"),
  ]);
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  doc.setFontSize(11);
  doc.text(title, 14, 12);
  const table = summaryRows(rows);
  const head = table[0];
  const body = table.slice(1);
  autoTable(doc, {
    startY: 16,
    head: [head],
    body,
    styles: { fontSize: 7 },
    headStyles: { fillColor: [71, 85, 105] },
  });
  doc.save(`${filenameBase}.pdf`);
}

export async function exportPreviewDocx(
  rows: PreviewRowLike[],
  filenameBase: string,
  title: string
): Promise<void> {
  const docx = await import("docx");
  const { Document, Packer, Paragraph, Table, TableCell, TableRow, TextRun, WidthType, AlignmentType } = docx;

  const tableRows = [];
  const headerCells = summaryRows(rows)[0].map(
    (text) =>
      new TableCell({
        width: { size: 14, type: WidthType.PERCENTAGE },
        children: [
          new Paragraph({
            children: [new TextRun({ text, bold: true })],
            alignment: AlignmentType.CENTER,
          }),
        ],
      })
  );
  tableRows.push(new TableRow({ children: headerCells }));

  for (const r of rows) {
    const line = [
      r.row_type,
      r.supplier_name ?? "",
      (r.contract_id || r.request_title || "").toString(),
      r.category ?? "",
      String(r.estimated_spend_usd ?? 0),
      r.computed_tier ?? "",
      r.computed_total_score != null ? String(r.computed_total_score) : "",
      r.readiness_status ?? "",
    ];
    tableRows.push(
      new TableRow({
        children: line.map(
          (text) =>
            new TableCell({
              children: [new Paragraph({ children: [new TextRun(String(text))] })],
            })
        ),
      })
    );
  }

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            children: [new TextRun({ text: title, bold: true, size: 28 })],
          }),
          new Paragraph({ text: "" }),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: tableRows,
          }),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  downloadBlob(blob, `${filenameBase}.docx`);
}

export function buildExportRows(
  candidates: PreviewRowLike[],
  mergedById: Record<string, PreviewRowLike>,
  scope: ExportScope,
  showcaseLimit: number
): PreviewRowLike[] {
  const merged = candidates.map((c) => mergedById[c.row_id] ?? c);
  if (scope === "renewal_showcase") {
    return pickShowcaseRenewals(merged, showcaseLimit);
  }
  return merged;
}
