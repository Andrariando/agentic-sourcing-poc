"use client";

import Link from "next/link";
import React, { useMemo, useState } from "react";
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

export default function System1UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedCount = useMemo(
    () => Object.values(selected).filter(Boolean).length,
    [selected]
  );

  const validSelectableIds = useMemo(
    () => (preview?.candidates ?? []).filter((c) => c.valid_for_approval).map((c) => c.row_id),
    [preview]
  );

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
      const defaults: Record<string, boolean> = {};
      for (const id of p.candidates.filter((c) => c.valid_for_approval).map((c) => c.row_id)) defaults[id] = true;
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
        const d = (await st.json()) as JobStatus;
        setStatus(d);
      }
    } catch {
      setError(`Network error. ${apiConnectivityHint()}`);
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold text-slate-900">System 1 Upload (Staged)</h1>
          <p className="text-sm text-slate-600 mt-2 leading-relaxed">
            Upload renewal/new-business source files, preview extracted opportunities, approve selected rows, then trigger
            scoring refresh. Nothing is persisted until approval.
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
                  Select rows to persist and score. Non-selected rows are ignored.
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
              <table className="w-full text-left text-sm min-w-[1000px]">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Approve</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Supplier</th>
                    <th className="px-3 py-2">Spend</th>
                    <th className="px-3 py-2">Timeline/Expiry</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Warnings</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.candidates.map((r) => (
                    <tr key={r.row_id} className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          disabled={!r.valid_for_approval}
                          checked={Boolean(selected[r.row_id])}
                          onChange={(e) =>
                            setSelected((prev) => ({ ...prev, [r.row_id]: e.target.checked }))
                          }
                        />
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${r.row_type === "renewal" ? "bg-blue-50 text-blue-700" : "bg-emerald-50 text-emerald-700"}`}>
                          {r.row_type === "renewal" ? "Renewal" : "New business"}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-800">{r.category}</p>
                        <p className="text-xs text-slate-500">{r.subcategory || "General"}</p>
                      </td>
                      <td className="px-3 py-2">
                        <p className="text-slate-700">{r.supplier_name || "—"}</p>
                        <p className="text-xs text-slate-500">{r.contract_id || r.request_title || "—"}</p>
                      </td>
                      <td className="px-3 py-2 font-mono text-slate-700">{money(r.estimated_spend_usd || 0)}</td>
                      <td className="px-3 py-2 text-slate-700 text-xs">
                        {r.row_type === "renewal"
                          ? `${r.months_to_expiry ?? "?"} mo to expiry`
                          : `${r.implementation_timeline_months ?? "?"} mo implementation`}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {r.source_kind} · {r.source_filename}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {r.warnings.length === 0 ? (
                          <span className="text-emerald-700">No issues</span>
                        ) : (
                          <span className="text-amber-700">{r.warnings.join("; ")}</span>
                        )}
                      </td>
                    </tr>
                  ))}
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

