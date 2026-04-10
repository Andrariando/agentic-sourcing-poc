"use client";

import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api-fetch";
import { apiConnectivityHint, getApiBaseUrl } from "@/lib/api-base";

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
};

function money(v: number): string {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);
  } catch {
    return `$${v.toFixed(0)}`;
  }
}

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
  if (!(edit.supplier_name ?? base.supplier_name ?? "").trim()) {
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

export default function System1UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [edits, setEdits] = useState<Record<string, RowEdit>>({});
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const validSelectableIds = useMemo(() => {
    if (!preview) return [];
    return preview.candidates.filter((c) => mergedById[c.row_id]?.valid_for_approval).map((c) => c.row_id);
  }, [preview, mergedById]);

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

  const handlePreview = async () => {
    setError(null);
    setMessage(null);
    if (files.length === 0) {
      setError("Choose at least one file first.");
      return;
    }
    const body = new FormData();
    for (const f of files) body.append("files", f);
    setUploading(true);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/system1/upload/preview`, {
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
      const defaults: Record<string, boolean> = {};
      for (const c of p.candidates) {
        const merged = mergeRow(c, undefined);
        if (merged.valid_for_approval) defaults[c.row_id] = true;
      }
      setSelected(defaults);
      setMessage(`Preview ready: ${p.valid_candidates}/${p.total_candidates} rows can be approved.`);
      setStatus(null);
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
        }),
      });
      const data = (await res.json().catch(() => ({}))) as Partial<ApproveResponse> & { detail?: string };
      if (!res.ok) {
        setError(data.detail || "Approve failed.");
        return;
      }
      const ok = data as ApproveResponse;
      setMessage(ok.message);
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
        const { [rowId]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [rowId]: next };
    });
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold text-slate-900">Sourcing Opportunity Data Upload</h1>
          <p className="text-sm text-slate-600 mt-2 leading-relaxed">
            Upload renewal/new-business source files, preview extracted opportunities, edit cells if anything looks
            wrong, approve selected rows, then trigger scoring refresh. Nothing is persisted until approval.
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
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handlePreview}
              disabled={uploading || files.length === 0}
              className="px-4 py-2 bg-sponsor-blue text-white rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {uploading ? "Building preview…" : "Preview extracted rows"}
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
                  onClick={handleApprove}
                  disabled={approving || selectedCount === 0}
                  className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {approving ? "Approving…" : `Approve ${selectedCount} row(s)`}
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

            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-sm min-w-[1100px]">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-2 py-2 w-10">OK</th>
                    <th className="px-2 py-2">Type</th>
                    <th className="px-2 py-2">Category</th>
                    <th className="px-2 py-2">Supplier</th>
                    <th className="px-2 py-2">Spend (USD)</th>
                    <th className="px-2 py-2">Contract / Request</th>
                    <th className="px-2 py-2">Timeline / Expiry (mo)</th>
                    <th className="px-2 py-2">Source</th>
                    <th className="px-2 py-2">Warnings</th>
                    <th className="px-2 py-2 w-16" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.candidates.map((r) => {
                    const m = mergedById[r.row_id] || r;
                    const e = edits[r.row_id];
                    const canSelect = m.valid_for_approval;
                    return (
                      <tr key={r.row_id} className="hover:bg-slate-50 align-top">
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            disabled={!canSelect}
                            title={!canSelect ? "Fix spend (must be &gt; 0) to approve" : undefined}
                            checked={Boolean(selected[r.row_id])}
                            onChange={(ev) =>
                              setSelected((prev) => ({ ...prev, [r.row_id]: ev.target.checked }))
                            }
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
                            value={
                              e?.supplier_name !== undefined ? e.supplier_name ?? "" : r.supplier_name || ""
                            }
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
                              e?.estimated_spend_usd !== undefined
                                ? e.estimated_spend_usd
                                : r.estimated_spend_usd || ""
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
                              value={
                                e?.contract_id !== undefined ? e.contract_id ?? "" : r.contract_id || ""
                              }
                              onChange={(ev) => updateEdit(r.row_id, { contract_id: ev.target.value })}
                            />
                          ) : (
                            <input
                              className="w-full min-w-[7rem] text-xs border border-slate-200 rounded px-1.5 py-1"
                              placeholder="Request title"
                              value={
                                e?.request_title !== undefined
                                  ? e.request_title ?? ""
                                  : r.request_title || ""
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
                                e?.months_to_expiry !== undefined
                                  ? e.months_to_expiry ?? ""
                                  : r.months_to_expiry ?? ""
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
                          <span className="break-all">{r.source_filename}</span>
                        </td>
                        <td className="px-2 py-2 text-xs">
                          {m.warnings.length === 0 ? (
                            <span className="text-emerald-700">No issues</span>
                          ) : (
                            <span className="text-amber-700">{m.warnings.join("; ")}</span>
                          )}
                        </td>
                        <td className="px-2 py-2">
                          <button
                            type="button"
                            className="text-xs text-sponsor-blue hover:underline"
                            onClick={() =>
                              setEdits((prev) => {
                                const { [r.row_id]: _, ...rest } = prev;
                                return rest;
                              })
                            }
                          >
                            Reset
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
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
