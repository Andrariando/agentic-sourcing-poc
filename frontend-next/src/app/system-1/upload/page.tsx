"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api-fetch";
import { apiConnectivityHint, getApiBaseUrl } from "@/lib/api-base";
import {
  buildExportRows,
  exportPreviewCsv,
  exportPreviewDocx,
  exportPreviewPdf,
  exportPreviewXlsx,
  type ExportScope,
} from "@/lib/system1-export";
import DecisionActionBar from "@/components/workflow/DecisionActionBar";

type PreviewRow = {
  row_id: string;
  row_type: "renewal" | "new_business";
  source_filename: string;
  source_kind: "structured" | "document";
  confidence: number;
  category: string;
  subcategory?: string | null;
  supplier_name?: string | null;
  contract_id?: string | null;
  request_title?: string | null;
  estimated_spend_usd: number;
  implementation_timeline_months?: number | null;
  months_to_expiry?: number | null;
  preferred_supplier_status?: string | null;
  score_components?: Record<string, {
    value: number;
    confidence: number;
    source_type: "provided" | "derived" | "defaulted";
    evidence_refs: string[];
    explanation: string;
  }>;
  weights_used?: Record<string, number>;
  computed_total_score?: number | null;
  computed_tier?: string | null;
  computed_confidence?: number | null;
  readiness_status?: "ready" | "ready_with_warnings" | "needs_review";
  readiness_warnings?: string[];
  recommended_action_window?: string | null;
  completeness_score?: number;
  defaulted_components?: string[];
  low_confidence_components?: string[];
  missing_critical_fields?: string[];
  suggested_actions?: Array<{ action: string; reason: string }>;
  warnings: string[];
  valid_for_approval: boolean;
};

type RowEdit = Partial<{
  row_type: "renewal" | "new_business";
  category: string;
  subcategory: string;
  supplier_name: string;
  contract_id: string;
  request_title: string;
  estimated_spend_usd: number;
  implementation_timeline_months: number | null;
  months_to_expiry: number | null;
}>;

type PreviewResponse = {
  job_id: string;
  status: string;
  total_candidates: number;
  valid_candidates: number;
  candidates: PreviewRow[];
  parsing_notes: string[];
  analysis?: {
    total_rows_analyzed?: number;
    scoreable_rows?: number;
    readiness_breakdown?: Record<string, number>;
    defaulted_component_counts?: Record<string, number>;
    imputation_action_candidates?: Array<{ action: string; rows: number }>;
    returned_rows?: number;
    top_n_applied?: number | null;
    rank_by_applied?: "completeness" | "score" | "hybrid" | string;
    execution_trace?: string[];
  };
};

type ApproveResponse = {
  success: boolean;
  job_id: string;
  approved_count: number;
  created_opportunity_ids: number[];
  run_triggered: boolean;
  message: string;
};

type JobStatus = {
  job_id: string;
  status: string;
  created_at: string;
  total_candidates: number;
  approved_count: number;
  created_opportunity_ids: number[];
  run_triggered: boolean;
  parsing_notes: string[];
  warning_rows_count?: number;
};

function mergeRow(base: PreviewRow, edit?: RowEdit): PreviewRow {
  if (!edit) return base;
  const spend =
    edit.estimated_spend_usd !== undefined && edit.estimated_spend_usd !== null
      ? Number(edit.estimated_spend_usd)
      : base.estimated_spend_usd;
  const impl =
    edit.implementation_timeline_months !== undefined
      ? edit.implementation_timeline_months
      : base.implementation_timeline_months;
  const exp =
    edit.months_to_expiry !== undefined ? edit.months_to_expiry : base.months_to_expiry;
  const warnings: string[] = [];
  if (!(Number.isFinite(spend) && spend > 0)) warnings.push("Missing or non-positive spend");
  const rt = edit.row_type ?? base.row_type;
  if (rt === "renewal" && (exp === null || exp === undefined)) {
    warnings.push("Renewal row missing months_to_expiry (will default conservatively)");
  }
  if (rt === "new_business" && (impl === null || impl === undefined)) {
    warnings.push("New business row missing implementation_timeline_months (will default to 6)");
  }
  if (rt === "renewal" && !(edit.supplier_name ?? base.supplier_name ?? "").trim()) {
    warnings.push("Supplier name missing");
  }
  const valid = Number.isFinite(spend) && spend > 0;
  return {
    ...base,
    row_type: rt,
    category: edit.category ?? base.category,
    subcategory: edit.subcategory !== undefined ? edit.subcategory || null : base.subcategory,
    supplier_name: edit.supplier_name !== undefined ? edit.supplier_name || null : base.supplier_name,
    contract_id: edit.contract_id !== undefined ? edit.contract_id || null : base.contract_id,
    request_title: edit.request_title !== undefined ? edit.request_title || null : base.request_title,
    estimated_spend_usd: spend,
    implementation_timeline_months:
      impl === undefined ? base.implementation_timeline_months : impl,
    months_to_expiry: exp === undefined ? base.months_to_expiry : exp,
    warnings,
    valid_for_approval: valid,
  };
}

function buildRowOverrides(
  base: PreviewRow,
  edit: RowEdit | undefined
): Record<string, unknown> | null {
  if (!edit || Object.keys(edit).length === 0) return null;
  const o: Record<string, unknown> = {};
  if (edit.row_type !== undefined) o.row_type = edit.row_type;
  if (edit.category !== undefined) o.category = edit.category;
  if (edit.subcategory !== undefined) o.subcategory = edit.subcategory;
  if (edit.supplier_name !== undefined) o.supplier_name = edit.supplier_name;
  if (edit.contract_id !== undefined) o.contract_id = edit.contract_id;
  if (edit.request_title !== undefined) o.request_title = edit.request_title;
  if (edit.estimated_spend_usd !== undefined) o.estimated_spend_usd = edit.estimated_spend_usd;
  if (edit.implementation_timeline_months !== undefined) {
    o.implementation_timeline_months = edit.implementation_timeline_months;
  }
  if (edit.months_to_expiry !== undefined) o.months_to_expiry = edit.months_to_expiry;
  return Object.keys(o).length ? o : null;
}

const PREVIEW_PAGE_SIZE = 20;

function normalizeWarnings(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((entry) => {
      if (typeof entry === "string") return entry.trim();
      if (entry == null) return "";
      try {
        return JSON.stringify(entry);
      } catch {
        return String(entry).trim();
      }
    })
    .filter((entry) => entry.length > 0);
}

function UploadPreviewTableRow({
  r,
  m,
  e,
  canSelect,
  selected,
  onToggleSelect,
  updateEdit,
}: {
  r: PreviewRow;
  m: PreviewRow;
  e: RowEdit | undefined;
  canSelect: boolean;
  selected: boolean;
  onToggleSelect: (checked: boolean) => void;
  updateEdit: (rowId: string, patch: RowEdit) => void;
}) {
  const rowType = (e?.row_type ?? m.row_type) as "renewal" | "new_business";
  const warnings = normalizeWarnings(m.warnings).filter(
    (w) => rowType === "renewal" || !w.toLowerCase().includes("supplier name missing")
  );
  return (
    <tr className="hover:bg-slate-50 align-top">
      <td className="px-2 py-2">
        <input
          type="checkbox"
          disabled={!canSelect}
          title={!canSelect ? "Fix spend (must be > 0) to approve" : undefined}
          checked={selected}
          onChange={(ev) => onToggleSelect(ev.target.checked)}
        />
      </td>
      <td className="px-2 py-2">
        <select
          className="w-full min-w-[7.5rem] text-xs border border-slate-200 rounded px-1.5 py-1 bg-white"
          value={e?.row_type ?? r.row_type}
          onChange={(ev) =>
            updateEdit(r.row_id, {
              row_type: ev.target.value as "renewal" | "new_business",
            })
          }
        >
          <option value="renewal">Renewal</option>
          <option value="new_business">New business</option>
        </select>
      </td>
      <td className="px-2 py-2">
        <input
          className="w-full min-w-[8rem] text-xs border border-slate-200 rounded px-1.5 py-1"
          value={e?.category ?? r.category}
          onChange={(ev) => updateEdit(r.row_id, { category: ev.target.value })}
        />
        <input
          className="w-full min-w-[8rem] text-xs border border-dashed border-slate-200 rounded px-1.5 py-0.5 mt-1 text-slate-500"
          placeholder="Subcategory"
          value={e?.subcategory !== undefined ? e.subcategory ?? "" : r.subcategory || ""}
          onChange={(ev) => updateEdit(r.row_id, { subcategory: ev.target.value })}
        />
      </td>
      <td className="px-2 py-2">
        <input
          className="w-full min-w-[7rem] text-xs border border-slate-200 rounded px-1.5 py-1"
          value={e?.supplier_name !== undefined ? e.supplier_name ?? "" : r.supplier_name || ""}
          onChange={(ev) => updateEdit(r.row_id, { supplier_name: ev.target.value })}
        />
      </td>
      <td className="px-2 py-2">
        <input
          type="number"
          min={0}
          step={1}
          className="w-full min-w-[6rem] text-xs font-mono border border-slate-200 rounded px-1.5 py-1"
          value={
            e?.estimated_spend_usd !== undefined ? e.estimated_spend_usd : r.estimated_spend_usd || ""
          }
          onChange={(ev) => {
            const v = ev.target.value;
            if (v === "") {
              updateEdit(r.row_id, { estimated_spend_usd: 0 });
              return;
            }
            const n = parseFloat(v);
            updateEdit(r.row_id, {
              estimated_spend_usd: Number.isFinite(n) ? n : 0,
            });
          }}
        />
      </td>
      <td className="px-2 py-2">
        {(e?.row_type ?? r.row_type) === "renewal" ? (
          <input
            className="w-full min-w-[7rem] text-xs border border-slate-200 rounded px-1.5 py-1"
            placeholder="Contract ID"
            value={e?.contract_id !== undefined ? e.contract_id ?? "" : r.contract_id || ""}
            onChange={(ev) => updateEdit(r.row_id, { contract_id: ev.target.value })}
          />
        ) : (
          <input
            className="w-full min-w-[7rem] text-xs border border-slate-200 rounded px-1.5 py-1"
            placeholder="Request title"
            value={
              e?.request_title !== undefined ? e.request_title ?? "" : r.request_title || ""
            }
            onChange={(ev) => updateEdit(r.row_id, { request_title: ev.target.value })}
          />
        )}
      </td>
      <td className="px-2 py-2">
        {(e?.row_type ?? r.row_type) === "renewal" ? (
          <input
            type="number"
            min={0}
            step={0.5}
            className="w-full min-w-[5rem] text-xs border border-slate-200 rounded px-1.5 py-1"
            placeholder="Months to expiry"
            value={
              e?.months_to_expiry !== undefined ? e.months_to_expiry ?? "" : r.months_to_expiry ?? ""
            }
            onChange={(ev) => {
              const v = ev.target.value;
              if (v === "") {
                updateEdit(r.row_id, { months_to_expiry: null });
                return;
              }
              const n = parseFloat(v);
              updateEdit(r.row_id, {
                months_to_expiry: Number.isFinite(n) ? n : null,
              });
            }}
          />
        ) : (
          <input
            type="number"
            min={0}
            step={0.5}
            className="w-full min-w-[5rem] text-xs border border-slate-200 rounded px-1.5 py-1"
            placeholder="Implementation (mo)"
            value={
              e?.implementation_timeline_months !== undefined
                ? e.implementation_timeline_months ?? ""
                : r.implementation_timeline_months ?? ""
            }
            onChange={(ev) => {
              const v = ev.target.value;
              if (v === "") {
                updateEdit(r.row_id, { implementation_timeline_months: null });
                return;
              }
              const n = parseFloat(v);
              updateEdit(r.row_id, {
                implementation_timeline_months: Number.isFinite(n) ? n : null,
              });
            }}
          />
        )}
      </td>
      <td className="px-2 py-2 text-xs text-slate-500">
        {r.source_kind}
        <br />
        <span className="break-all line-clamp-3 block">{r.source_filename}</span>
      </td>
      <td className="px-2 py-2 text-xs">
        <div className="font-semibold text-slate-700">
          {m.computed_total_score != null ? `${m.computed_total_score.toFixed(2)} / 10` : "—"}
        </div>
        <div className="text-[11px] text-slate-500">{m.computed_tier || "—"}</div>
        <div className="text-[11px] text-slate-500">
          Completeness: {m.completeness_score != null ? `${m.completeness_score.toFixed(1)}%` : "—"}
        </div>
      </td>
      <td className="px-2 py-2 text-xs">
        <span
          className={`inline-flex px-2 py-0.5 rounded-full border ${
            (m.readiness_status || "ready") === "ready"
              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
              : (m.readiness_status || "ready") === "ready_with_warnings"
                ? "bg-amber-50 text-amber-800 border-amber-200"
                : "bg-rose-50 text-rose-700 border-rose-200"
          }`}
        >
          {m.readiness_status || "ready"}
        </span>
      </td>
      <td className="px-2 py-2 text-xs w-[16rem] min-w-[16rem]">
        {warnings.length === 0 ? (
          <span className="text-emerald-700">No issues</span>
        ) : (
          <div className="space-y-1 max-h-20 overflow-y-auto pr-1">
            <span className="text-amber-700 break-words whitespace-normal block">
              {warnings.join("; ")}
            </span>
            {m.score_components && Object.keys(m.score_components).length > 0 && (
              <details>
                <summary className="cursor-pointer text-sponsor-blue">Evidence</summary>
                <div className="mt-1 space-y-1 text-[11px] text-slate-600">
                  {Object.entries(m.score_components).map(([k, v]) => (
                    <p key={k}>
                      <strong>{k}</strong>: {v.value} ({v.source_type})
                    </p>
                  ))}
                </div>
              </details>
            )}
            {m.suggested_actions && m.suggested_actions.length > 0 && (
              <details>
                <summary className="cursor-pointer text-sponsor-blue">Suggested actions</summary>
                <div className="mt-1 space-y-1 text-[11px] text-slate-600">
                  {m.suggested_actions.slice(0, 4).map((a, idx) => (
                    <p key={`${r.row_id}-action-${idx}`}>
                      <strong>{a.action}</strong>: {a.reason}
                    </p>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

export default function System1UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [edits, setEdits] = useState<Record<string, RowEdit>>({});
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [columnMappingJson, setColumnMappingJson] = useState("");
  const [ackWarnings, setAckWarnings] = useState(false);
  const [bundleScanMode, setBundleScanMode] = useState(true);
  const [topN, setTopN] = useState(100);
  const [topNInput, setTopNInput] = useState("100");
  const [rankBy, setRankBy] = useState<"completeness" | "score" | "hybrid">("completeness");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportScope, setExportScope] = useState<ExportScope>("all");
  const [exporting, setExporting] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(PREVIEW_PAGE_SIZE);

  const tableScrollRef = useRef<HTMLDivElement>(null);

  const selectedCount = useMemo(
    () => Object.entries(selected).filter(([, v]) => v).length,
    [selected]
  );

  const mergedById = useMemo(() => {
    const m: Record<string, PreviewRow> = {};
    if (!preview) return m;
    for (const c of preview.candidates) {
      m[c.row_id] = mergeRow(c, edits[c.row_id]);
    }
    return m;
  }, [preview, edits]);

  const sortedCandidates = useMemo(() => {
    if (!preview) return [];
    const ranked = [...preview.candidates];
    ranked.sort((a, b) => {
      const ma = mergedById[a.row_id] || a;
      const mb = mergedById[b.row_id] || b;
      const scoreDelta =
        Number(mb.computed_total_score ?? 0) - Number(ma.computed_total_score ?? 0);
      if (scoreDelta !== 0) return scoreDelta;
      return Number(mb.estimated_spend_usd ?? 0) - Number(ma.estimated_spend_usd ?? 0);
    });
    return ranked;
  }, [preview, mergedById]);
  const candidateCount = sortedCandidates.length;
  const visibleCandidates = useMemo(
    () => sortedCandidates.slice(0, visibleCount),
    [sortedCandidates, visibleCount]
  );
  const visibleCandidateCount = visibleCandidates.length;

  const validSelectableIds = useMemo(() => {
    return visibleCandidates
      .filter((c) => mergedById[c.row_id]?.valid_for_approval)
      .map((c) => c.row_id);
  }, [visibleCandidates, mergedById]);

  const exportRows = useMemo(() => {
    if (!preview) return [];
    return buildExportRows(preview.candidates, mergedById, exportScope, 10);
  }, [preview, mergedById, exportScope]);

  useEffect(() => {
    if (!preview) return;
    setSelected((sel) => {
      let changed = false;
      const next = { ...sel };
      for (const id of Object.keys(sel)) {
        if (!sel[id]) continue;
        const c = preview.candidates.find((x) => x.row_id === id);
        if (!c) continue;
        const m = mergeRow(c, edits[id]);
        if (!m.valid_for_approval) {
          next[id] = false;
          changed = true;
        }
      }
      return changed ? next : sel;
    });
  }, [edits, preview]);

  useEffect(() => {
    if (!preview) return;
    setVisibleCount(PREVIEW_PAGE_SIZE);
    tableScrollRef.current?.scrollTo({ top: 0 });
  }, [preview?.job_id, preview]);

  const runExport = async (kind: "csv" | "xlsx" | "pdf" | "docx") => {
    if (!preview || exportRows.length === 0) {
      setError(
        exportScope === "renewal_showcase"
          ? "No renewal rows with readiness “ready” to export. Try “Full preview” or adjust data."
          : "Nothing to export."
      );
      return;
    }
    setError(null);
    setExporting(kind);
    const slug = exportScope === "renewal_showcase" ? "renewal-showcase-10" : "full-preview";
    const base = `system1-${preview.job_id}-${slug}`;
    const title =
      exportScope === "renewal_showcase"
        ? `Top renewal opportunities (export of ${exportRows.length})`
        : `Sourcing preview export (${exportRows.length} rows)`;
    try {
      if (kind === "csv") exportPreviewCsv(exportRows, base);
      else if (kind === "xlsx") await exportPreviewXlsx(exportRows, base);
      else if (kind === "pdf") await exportPreviewPdf(exportRows, base, title);
      else await exportPreviewDocx(exportRows, base, title);
      setMessage(`Downloaded ${kind.toUpperCase()} (${exportRows.length} row(s)).`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setExporting(null);
    }
  };

  const handlePreview = async () => {
    setError(null);
    setMessage(null);
    if (files.length === 0) {
      setError("Choose at least one file first.");
      return;
    }
    const body = new FormData();
    for (const f of files) body.append("files", f);
    if (columnMappingJson.trim()) body.append("column_mapping_json", columnMappingJson.trim());
    const parsedTopN = Number.parseInt(topNInput.trim(), 10);
    const effectiveTopN =
      Number.isFinite(parsedTopN) && parsedTopN > 0 ? Math.min(Math.max(parsedTopN, 1), 5000) : 100;
    setTopN(effectiveTopN);
    setTopNInput(String(effectiveTopN));
    body.append("top_n", String(effectiveTopN));
    body.append("rank_by", rankBy);
    setUploading(true);
    try {
      const endpoint = bundleScanMode
        ? `${getApiBaseUrl()}/api/system1/upload/scan-bundle`
        : `${getApiBaseUrl()}/api/system1/upload/preview`;
      const res = await apiFetch(endpoint, {
        method: "POST",
        body,
      });
      const data = (await res.json().catch(() => ({}))) as Partial<PreviewResponse> & { detail?: string };
      if (!res.ok) {
        setError(data.detail || "Preview failed.");
        return;
      }
      const p = data as PreviewResponse;
      setPreview(p);
      setEdits({});
      setSelected({});
      setMessage(
        `${bundleScanMode ? "Bundle scan" : "Preview"} ready: ` +
          `${p.valid_candidates}/${p.total_candidates} rows can be approved.`
      );
      setStatus(null);
      setAckWarnings(false);
    } catch {
      setError(`Network error. ${apiConnectivityHint()}`);
    } finally {
      setUploading(false);
    }
  };

  const handleApprove = async () => {
    if (!preview) return;
    const approvedIds = Object.entries(selected).filter(([, v]) => v).map(([k]) => k);
    if (approvedIds.length === 0) {
      setError("Select at least one row to approve.");
      return;
    }
    const invalid = approvedIds.filter((id) => !mergedById[id]?.valid_for_approval);
    if (invalid.length > 0) {
      setError("Uncheck or fix rows with invalid spend (must be greater than zero).");
      return;
    }
    const row_overrides: Record<string, Record<string, unknown>> = {};
    for (const id of approvedIds) {
      const o = buildRowOverrides(
        preview.candidates.find((c) => c.row_id === id)!,
        edits[id]
      );
      if (o) row_overrides[id] = o;
    }
    const warningRowIds = approvedIds.filter(
      (id) => (mergedById[id]?.readiness_status || "ready") === "ready_with_warnings"
    );
    if (warningRowIds.length > 0 && !ackWarnings) {
      setError("Some selected rows have warning-level scoring. Check acknowledgment to proceed.");
      return;
    }
    setApproving(true);
    setError(null);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/system1/upload/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: preview.job_id,
          approved_row_ids: approvedIds,
          approver_id: "human-user",
          row_overrides: Object.keys(row_overrides).length ? row_overrides : undefined,
          acknowledge_warning_row_ids: warningRowIds,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as Partial<ApproveResponse> & { detail?: string };
      if (!res.ok) {
        setError(data.detail || "Approve failed.");
        return;
      }
      const ok = data as ApproveResponse;
      const approvedSet = new Set(approvedIds);
      setPreview((prev) => {
        if (!prev) return prev;
        const remaining = prev.candidates.filter((c) => !approvedSet.has(c.row_id));
        return {
          ...prev,
          candidates: remaining,
          total_candidates: remaining.length,
          valid_candidates: remaining.filter((c) => (mergedById[c.row_id] || c).valid_for_approval).length,
        };
      });
      setSelected((prev) => {
        const next = { ...prev };
        for (const id of approvedIds) delete next[id];
        return next;
      });
      setEdits((prev) => {
        const next = { ...prev };
        for (const id of approvedIds) delete next[id];
        return next;
      });
      setMessage(`${ok.message} Removed ${approvedIds.length} approved row(s) from the preview list.`);
      const st = await apiFetch(`${getApiBaseUrl()}/api/system1/upload/jobs/${preview.job_id}`);
      if (st.ok) {
        setStatus((await st.json()) as JobStatus);
      }
    } catch {
      setError(`Network error. ${apiConnectivityHint()}`);
    } finally {
      setApproving(false);
    }
  };

  const updateEdit = (rowId: string, patch: RowEdit) => {
    setEdits((prev) => {
      const cur = prev[rowId] || {};
      const next = { ...cur, ...patch };
      const keys = Object.keys(next);
      if (keys.length === 0) {
        const rest = { ...prev };
        delete rest[rowId];
        return rest;
      }
      return { ...prev, [rowId]: next };
    });
  };

  const commitTopNInput = () => {
    const parsed = Number.parseInt(topNInput.trim(), 10);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setTopN(100);
      setTopNInput("100");
      return;
    }
    const clamped = Math.min(Math.max(parsed, 1), 5000);
    setTopN(clamped);
    setTopNInput(String(clamped));
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold text-slate-900">Sourcing Opportunity Data Upload</h1>
          <p className="text-sm text-slate-600 mt-2 leading-relaxed">
            Optional path for pilots: upload renewal/new-business source files, preview extracted opportunities, edit cells if
            anything looks wrong, approve selected rows, then trigger scoring refresh. Nothing is persisted until approval. System
            integration (for example ERP APIs) is the intended primary feed over time.
          </p>
          <p className="text-xs text-slate-500 mt-3">
            Download templates:{" "}
            <a
              href={`${getApiBaseUrl()}/api/system1/upload/templates/renewals_template.csv`}
              className="text-sponsor-blue hover:underline"
            >
              renewals
            </a>
            {" · "}
            <a
              href={`${getApiBaseUrl()}/api/system1/upload/templates/new_business_template.csv`}
              className="text-sponsor-blue hover:underline"
            >
              new business
            </a>
          </p>
        </header>

        <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Upload files</label>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.csv,.xls,.xlsx"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
              className="block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700"
            />
            <p className="text-xs text-slate-500 mt-2">
              Supported: PDF, DOCX, TXT, CSV, XLS, XLSX. Structured files provide the most reliable extraction.
            </p>
            <label className="inline-flex items-center gap-2 text-xs text-slate-600 mt-3">
              <input
                type="checkbox"
                checked={bundleScanMode}
                onChange={(e) => setBundleScanMode(e.target.checked)}
              />
              Bundle scan mode (fuse contract + spend + metrics into deduplicated candidates)
            </label>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
              <label htmlFor="top-n-input">Top rows</label>
              <input
                id="top-n-input"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                value={topNInput}
                onChange={(e) => setTopNInput(e.target.value)}
                onBlur={commitTopNInput}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commitTopNInput();
                  }
                }}
                className="w-24 border border-slate-200 rounded px-2 py-1 text-xs"
              />
              <button
                type="button"
                onClick={() => {
                  setTopN(50);
                  setTopNInput("50");
                }}
                className="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
              >
                50
              </button>
              <button
                type="button"
                onClick={() => {
                  setTopN(100);
                  setTopNInput("100");
                }}
                className="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
              >
                100
              </button>
              <button
                type="button"
                onClick={() => {
                  setTopN(200);
                  setTopNInput("200");
                }}
                className="px-2 py-1 rounded border border-slate-200 bg-white hover:bg-slate-50"
              >
                200
              </button>
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
              <label htmlFor="rank-by-select">Rank by</label>
              <select
                id="rank-by-select"
                value={rankBy}
                onChange={(e) => setRankBy(e.target.value as "completeness" | "score" | "hybrid")}
                className="border border-slate-200 rounded px-2 py-1 text-xs bg-white"
              >
                <option value="completeness">Completeness</option>
                <option value="score">Score</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Optional column mapping (JSON)</label>
            <textarea
              rows={3}
              value={columnMappingJson}
              onChange={(e) => setColumnMappingJson(e.target.value)}
              className="w-full border border-slate-200 rounded-lg p-2 text-xs font-mono"
              placeholder='{"supplier":"supplier_name","spend":"estimated_spend_usd","expiry_months":"months_to_expiry"}'
            />
            <p className="text-xs text-slate-500 mt-1">
              Map sponsor-specific headers to canonical fields for bulk upload.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handlePreview}
              disabled={uploading || files.length === 0}
              className="px-4 py-2 bg-sponsor-blue text-white rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {uploading
                ? bundleScanMode
                  ? "Scanning bundle…"
                  : "Building preview…"
                : bundleScanMode
                ? "Scan files and fuse opportunities"
                : "Preview extracted rows"}
            </button>
            {preview && (
              <span className="text-xs text-slate-500">
                Job: <code className="text-slate-700">{preview.job_id}</code>
              </span>
            )}
          </div>
          {message && <p className="text-sm text-emerald-700">{message}</p>}
          {error && <p className="text-sm text-rose-700">{error}</p>}
        </section>

        {preview && (
          <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Preview & approval</h2>
                <p className="text-xs text-slate-500 mt-1">
                  Edit cells inline if extraction is wrong. Only rows with positive spend can be approved. Non-selected
                  rows are ignored.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    const next: Record<string, boolean> = {};
                    for (const id of validSelectableIds) next[id] = true;
                    setSelected(next);
                  }}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 bg-white"
                >
                  Select all valid
                </button>
                <button
                  type="button"
                  onClick={() => setSelected({})}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 bg-white"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setEdits((prev) => {
                      const next = { ...prev };
                      for (const [id, isSelected] of Object.entries(selected)) {
                        if (isSelected) delete next[id];
                      }
                      return next;
                    })
                  }
                  disabled={selectedCount === 0}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 bg-white disabled:opacity-50"
                  title="Undo edits on selected rows"
                >
                  Reset selected edits
                </button>
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={approving || selectedCount === 0}
                  className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {approving ? "Approving…" : `Approve ${selectedCount} row(s)`}
                </button>
              </div>
            </div>
            <label className="inline-flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={ackWarnings}
                onChange={(e) => setAckWarnings(e.target.checked)}
              />
              I acknowledge warning rows (defaulted/derived components) before approval.
            </label>
            <DecisionActionBar
              statusText={`Selected ${selectedCount} row(s). Approval writes opportunities and clears approved rows from preview.`}
              primaryLabel={`Approve ${selectedCount} row(s)`}
              primaryBusy={approving}
              primaryDisabled={selectedCount === 0}
              onPrimary={handleApprove}
              secondaryLabel="Reset selected edits"
              onSecondary={() =>
                setEdits((prev) => {
                  const next = { ...prev };
                  for (const [id, isSelected] of Object.entries(selected)) {
                    if (isSelected) delete next[id];
                  }
                  return next;
                })
              }
              secondaryDisabled={selectedCount === 0}
            />

            <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-4 space-y-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Export preview</h3>
                <p className="text-xs text-slate-600 mt-1">
                  Download what you see (including inline edits) as CSV or Excel with all columns. PDF and Word use a
                  compact summary table. For sponsor demos, use{" "}
                  <strong>Top renewals (ready)</strong> — highest-scoring renewal rows, deduplicated by contract (up to
                  10).
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-xs text-slate-600">
                  Scope:{" "}
                  <select
                    value={exportScope}
                    onChange={(e) => setExportScope(e.target.value as ExportScope)}
                    className="ml-1 border border-slate-200 rounded-md px-2 py-1 bg-white text-slate-800"
                  >
                    <option value="all">Full preview (all rows)</option>
                    <option value="renewal_showcase">Top renewals (ready, up to 10)</option>
                  </select>
                </label>
                <span className="text-xs text-slate-500">
                  {exportRows.length.toLocaleString()} row(s) in this export
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!!exporting}
                  onClick={() => void runExport("csv")}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  {exporting === "csv" ? "Working…" : "CSV"}
                </button>
                <button
                  type="button"
                  disabled={!!exporting}
                  onClick={() => void runExport("xlsx")}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  {exporting === "xlsx" ? "Working…" : "Excel (.xlsx)"}
                </button>
                <button
                  type="button"
                  disabled={!!exporting}
                  onClick={() => void runExport("pdf")}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  {exporting === "pdf" ? "Working…" : "PDF"}
                </button>
                <button
                  type="button"
                  disabled={!!exporting}
                  onClick={() => void runExport("docx")}
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  {exporting === "docx" ? "Working…" : "Word (.docx)"}
                </button>
              </div>
            </div>

            {preview.parsing_notes.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
                {preview.parsing_notes.map((n, idx) => (
                  <p key={`note-${idx}`}>{n}</p>
                ))}
              </div>
            )}
            {preview.analysis && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 space-y-2">
                <p className="text-sm font-semibold text-slate-800">Agentic completeness analysis</p>
                <div className="text-xs text-slate-700 flex flex-wrap gap-4">
                  <span>
                    Total analyzed: <strong>{preview.analysis.total_rows_analyzed ?? preview.total_candidates}</strong>
                  </span>
                  <span>
                    Scoreable: <strong>{preview.analysis.scoreable_rows ?? preview.valid_candidates}</strong>
                  </span>
                  <span>
                    Returned: <strong>{preview.analysis.returned_rows ?? preview.candidates.length}</strong>
                  </span>
                  <span>
                    Top N: <strong>{preview.analysis.top_n_applied ?? "all"}</strong>
                  </span>
                  <span>
                    Rank by: <strong>{preview.analysis.rank_by_applied ?? rankBy}</strong>
                  </span>
                </div>
                {preview.analysis.execution_trace && preview.analysis.execution_trace.length > 0 && (
                  <p className="text-xs text-slate-600">
                    Flow: {preview.analysis.execution_trace.join(" -> ")}
                  </p>
                )}
                {preview.analysis.imputation_action_candidates &&
                  preview.analysis.imputation_action_candidates.length > 0 && (
                    <div className="text-xs text-slate-700">
                      <p className="font-medium">Suggested actions (most common)</p>
                      <p>
                        {preview.analysis.imputation_action_candidates
                          .slice(0, 5)
                          .map((a) => `${a.action} (${a.rows})`)
                          .join(", ")}
                      </p>
                    </div>
                  )}
                {preview.analysis.readiness_breakdown && (
                  <div className="text-xs text-slate-700">
                    <p className="font-medium">Readiness breakdown</p>
                    <p>
                      {Object.entries(preview.analysis.readiness_breakdown)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" | ")}
                    </p>
                  </div>
                )}
              </div>
            )}

            <p className="text-xs text-slate-500">
              Showing top {visibleCandidateCount.toLocaleString()} of {candidateCount.toLocaleString()} row(s), ranked by
              score. Use Load more to continue.
            </p>
            <div className="rounded-lg border border-slate-200">
              <div ref={tableScrollRef} className="overflow-auto max-h-[min(70vh,720px)]">
                <table className="w-full text-left text-sm min-w-[1200px] table-auto">
                  <thead className="sticky top-0 z-20 bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 shadow-sm">
                    <tr>
                      <th className="px-2 py-2 w-10">OK</th>
                      <th className="px-2 py-2">Type</th>
                      <th className="px-2 py-2">Category</th>
                      <th className="px-2 py-2">Supplier</th>
                      <th className="px-2 py-2">Spend (USD)</th>
                      <th className="px-2 py-2">Contract / Request</th>
                      <th className="px-2 py-2">Timeline / Expiry (mo)</th>
                      <th className="px-2 py-2">Source</th>
                      <th className="px-2 py-2">Computed</th>
                      <th className="px-2 py-2">Readiness</th>
                      <th className="px-2 py-2 w-[16rem] min-w-[16rem]">Warnings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCandidates.map((r) => {
                      const m = mergedById[r.row_id] || r;
                      const e = edits[r.row_id];
                      const canSelect = m.valid_for_approval;
                      return (
                        <UploadPreviewTableRow
                          key={r.row_id}
                          r={r}
                          m={m}
                          e={e}
                          canSelect={canSelect}
                          selected={Boolean(selected[r.row_id])}
                          onToggleSelect={(checked) =>
                            setSelected((prev) => ({ ...prev, [r.row_id]: checked }))
                          }
                          updateEdit={updateEdit}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            {visibleCandidateCount < candidateCount && (
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  {candidateCount - visibleCandidateCount} row(s) hidden for performance.
                </p>
                <button
                  type="button"
                  onClick={() =>
                    setVisibleCount((n) => Math.min(n + PREVIEW_PAGE_SIZE, candidateCount))
                  }
                  className="text-xs px-3 py-1.5 rounded-md border border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
                >
                  Load more (+{PREVIEW_PAGE_SIZE})
                </button>
              </div>
            )}
          </section>
        )}

        {status && (
          <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
            <h3 className="text-sm font-semibold text-slate-800">Run status</h3>
            <p className="text-xs text-slate-500 mt-1">Job {status.job_id}</p>
            <p className="text-sm text-slate-700 mt-2">
              Approved: <strong>{status.approved_count}</strong> / {status.total_candidates}. Created opportunities:{" "}
              <strong>{status.created_opportunity_ids.length}</strong>.
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Scoring refresh triggered: {status.run_triggered ? "Yes" : "No"}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Warning rows approved: {status.warning_rows_count ?? 0}
            </p>
            <div className="mt-3 flex gap-3">
              <Link
                href="/heatmap"
                className="inline-flex items-center px-3 py-1.5 rounded-md bg-sponsor-blue text-white text-sm font-medium"
              >
                Open heatmap
              </Link>
              <button
                type="button"
                onClick={async () => {
                  const res = await apiFetch(`${getApiBaseUrl()}/api/system1/upload/jobs/${status.job_id}`);
                  if (res.ok) {
                    setStatus((await res.json()) as JobStatus);
                  }
                }}
                className="inline-flex items-center px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 text-sm font-medium bg-white"
              >
                Refresh status
              </button>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
