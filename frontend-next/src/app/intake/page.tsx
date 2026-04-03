"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import { HeatmapAbbr, HEATMAP_GLOSSARY, type HeatmapGlossaryKey } from "@/lib/heatmap-glossary";
import { heatmapTierLabel } from "@/lib/heatmap-tier-display";

const TIER_GLOSS: Record<string, HeatmapGlossaryKey> = {
  T1: "t1",
  T2: "t2",
  T3: "t3",
  T4: "t4",
};

type PreviewResponse = {
  meta: {
    max_estimated_spend_pipeline?: number;
    category_spend_used?: number;
    fis_field_note?: string;
    feedback_memory_delta?: number;
  };
  scores: Record<string, number | null | undefined>;
  total_score: number;
  tier: string;
  justification: string;
};

const DEFAULT_CATEGORIES = ["IT Infrastructure", "Software", "Hardware"];

export default function SourcingIntakePage() {
  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES);
  const [formData, setFormData] = useState({
    title: "",
    category: "IT Infrastructure",
    subcategory: "",
    supplier_name: "",
    justification: "",
    estimated_spend: 250_000,
    implementation_timeline_months: 6,
  });
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const url = `${getApiBaseUrl()}/api/heatmap/intake/categories`;
        const res = await apiFetch(url, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data.categories) && data.categories.length > 0) {
          setCategories(data.categories);
          setFormData((prev) =>
            data.categories.includes(prev.category)
              ? prev
              : { ...prev, category: data.categories[0] }
          );
        }
      } catch {
        /* keep defaults */
      }
    };
    load();
  }, []);

  const runPreview = useCallback(async () => {
    const base = getApiBaseUrl();
    const url = `${base}/api/heatmap/intake/preview`;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: formData.category,
          subcategory: formData.subcategory || null,
          supplier_name: formData.supplier_name || null,
          estimated_spend_usd: formData.estimated_spend,
          implementation_timeline_months: formData.implementation_timeline_months,
          preferred_supplier_status: null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail =
          typeof err.detail === "string"
            ? err.detail
            : Array.isArray(err.detail)
              ? err.detail.map((d: { msg?: string }) => d.msg).join("; ")
              : "Preview failed";
        setPreviewError(detail);
        setPreview(null);
        return;
      }
      const data = (await res.json()) as PreviewResponse;
      setPreview(data);
    } catch {
      setPreviewError(`Could not reach API. Base: ${base}${apiConnectivityHint()}`);
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [
    formData.category,
    formData.subcategory,
    formData.supplier_name,
    formData.estimated_spend,
    formData.implementation_timeline_months,
  ]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      void runPreview();
    }, 450);
    return () => window.clearTimeout(t);
  }, [runPreview]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitMessage(null);
    setSubmitLoading(true);
    const base = getApiBaseUrl();
    try {
      const res = await apiFetch(`${base}/api/heatmap/intake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_title: formData.title || null,
          category: formData.category,
          subcategory: formData.subcategory || null,
          supplier_name: formData.supplier_name || null,
          estimated_spend_usd: formData.estimated_spend,
          implementation_timeline_months: formData.implementation_timeline_months,
          preferred_supplier_status: null,
          justification_summary_text: formData.justification || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail =
          typeof err.detail === "string"
            ? err.detail
            : "Submit failed";
        setSubmitMessage(detail);
        return;
      }
      const data = await res.json();
      const id = data.opportunity?.id;
      const reqId = data.opportunity?.request_id;
      setSubmitMessage(
        id != null
          ? `Saved as opportunity #${id}${reqId ? ` (${reqId})` : ""}. It appears on the heatmap alongside batch rows.`
          : "Requirement saved."
      );
      void runPreview();
    } catch {
      setSubmitMessage(`Network error. API base: ${getApiBaseUrl()}${apiConnectivityHint()}`);
    } finally {
      setSubmitLoading(false);
    }
  };

  const s = preview?.scores;

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full flex justify-center">
      <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-3 gap-8">
        <form
          className="md:col-span-2 space-y-6 bg-white p-8 rounded-xl border border-slate-200 shadow-sm"
          onSubmit={handleSubmit}
        >
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Sourcing Intake Form (New Request)</h1>
            <p className="text-slate-500 text-sm mt-1 leading-relaxed">
              Submit a new sourcing requirement. Scores use the same{" "}
              <HeatmapAbbr term="psNew">PS_new</HeatmapAbbr> framework as the heatmap (
              <HeatmapAbbr term="ius">IUS</HeatmapAbbr>, <HeatmapAbbr term="es">ES</HeatmapAbbr>,{" "}
              <HeatmapAbbr term="csis">CSIS</HeatmapAbbr>, <HeatmapAbbr term="sas">SAS</HeatmapAbbr>) with pipeline max
              spend from existing intake rows plus this request.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-slate-100">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Requirement Title</label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none"
                placeholder="e.g. AWS Multi-Region Expansion"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Category</label>
                <select
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none bg-white"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                >
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Subcategory (optional)</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none"
                  value={formData.subcategory}
                  onChange={(e) => setFormData({ ...formData, subcategory: e.target.value })}
                  placeholder="e.g. Cloud Hosting"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Supplier (optional)</label>
              <input
                type="text"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none"
                value={formData.supplier_name}
                onChange={(e) => setFormData({ ...formData, supplier_name: e.target.value })}
                placeholder="e.g. CloudServe Group"
              />
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                <HeatmapAbbr term="sas">SAS</HeatmapAbbr> (strategic alignment) uses{" "}
                <code className="text-[11px] bg-slate-100 px-1 rounded">category_cards.json</code> for this category: supplier
                name matches a preferred tier when listed; otherwise the category default applies.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Estimated Spend (USD)</label>
                <input
                  type="number"
                  min={0}
                  step={1000}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none"
                  value={formData.estimated_spend}
                  onChange={(e) =>
                    setFormData({ ...formData, estimated_spend: Number(e.target.value) || 0 })
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Implementation timeline (months)</label>
                <input
                  type="number"
                  min={0.25}
                  step={0.25}
                  max={120}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none"
                  value={formData.implementation_timeline_months}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      implementation_timeline_months: Math.max(0.25, Number(e.target.value) || 0.25),
                    })
                  }
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Business Justification</label>
              <textarea
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-1 focus:ring-sponsor-blue outline-none min-h-32"
                placeholder="Why is this required?"
                value={formData.justification}
                onChange={(e) => setFormData({ ...formData, justification: e.target.value })}
              />
            </div>

            {submitMessage && (
              <p
                className={`text-sm ${submitMessage.startsWith("Saved") || submitMessage.includes("saved") ? "text-emerald-700" : "text-red-600"}`}
              >
                {submitMessage}
              </p>
            )}

            <div className="pt-4 flex justify-end">
              <button
                type="submit"
                disabled={submitLoading}
                className="px-6 py-2 bg-sponsor-blue text-white rounded-md font-medium shadow-sm hover:bg-blue-700 transition disabled:opacity-60"
              >
                {submitLoading ? "Submitting…" : "Submit Requirement"}
              </button>
            </div>
          </div>
        </form>

        <div className="md:col-span-1 space-y-4">
          <div className="bg-slate-900 text-white p-6 rounded-xl shadow-lg sticky top-8">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
                Live <HeatmapAbbr term="psNew">PS_new</HeatmapAbbr> score
              </h3>
              {previewLoading && <span className="text-xs text-slate-500">Updating…</span>}
            </div>

            {previewError && (
              <p className="text-sm text-amber-200 mb-4 border border-amber-800/50 rounded p-2">{previewError}</p>
            )}

            {preview ? (
              <>
                <div className="flex items-end gap-2 mb-2 flex-wrap">
                  <span className="text-5xl font-bold tabular-nums">{preview.total_score.toFixed(2)}</span>
                  <span className="text-slate-400 mb-1">weighted</span>
                  {typeof preview.meta?.feedback_memory_delta === "number" &&
                    Math.abs(preview.meta.feedback_memory_delta) >= 0.01 && (
                      <span
                        className="text-xs font-medium px-2 py-1 rounded bg-emerald-900/60 text-emerald-200 border border-emerald-700/50 mb-1"
                        title="Small adjustment from similar past reviewer feedback (Chroma + optional LLM). Sub-scores shown are pre-adjustment."
                      >
                        Review memory Δ{preview.meta.feedback_memory_delta >= 0 ? "+" : ""}
                        {preview.meta.feedback_memory_delta.toFixed(2)}
                      </span>
                    )}
                </div>
                <p className="text-sm text-sponsor-orange font-semibold mb-4">
                  <span title={HEATMAP_GLOSSARY.tier} className="cursor-help border-b border-dotted border-orange-400/60">
                    Priority
                  </span>{" "}
                  <HeatmapAbbr term={TIER_GLOSS[preview.tier] ?? "tier"}>{heatmapTierLabel(preview.tier)}</HeatmapAbbr>
                  {" · "}
                  <span title="Max of estimated spend across intake requests (no contract) used as the ES denominator.">
                    Pipeline max est. spend
                  </span>
                  : ${Math.round(preview.meta?.max_estimated_spend_pipeline ?? 0).toLocaleString()}
                </p>

                <div className="space-y-3 pt-4 border-t border-slate-700 text-sm">
                  <div className="flex justify-between items-baseline gap-2">
                    <span className="text-slate-300">
                      <HeatmapAbbr term="ius">IUS</HeatmapAbbr>
                    </span>
                    <span className="font-mono tabular-nums">{s?.ius_score?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div className="flex justify-between items-baseline gap-2">
                    <span className="text-slate-300">
                      <HeatmapAbbr term="es">ES</HeatmapAbbr>
                    </span>
                    <span className="font-mono tabular-nums">{s?.es_score?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div className="flex justify-between items-baseline gap-2">
                    <span className="text-slate-300">
                      <HeatmapAbbr term="csis">CSIS</HeatmapAbbr>
                    </span>
                    <span className="font-mono tabular-nums">{s?.csis_score?.toFixed(2) ?? "—"}</span>
                  </div>
                  <div className="flex justify-between items-baseline gap-2">
                    <span className="text-slate-300">
                      <HeatmapAbbr term="sas">SAS</HeatmapAbbr>
                    </span>
                    <span className="font-mono tabular-nums">{s?.sas_score?.toFixed(2) ?? "—"}</span>
                  </div>
                </div>

                {preview.meta?.fis_field_note && (
                  <p className="mt-4 text-xs text-slate-500 border-t border-slate-700 pt-3 leading-relaxed">
                    Batch <HeatmapAbbr term="fis">FIS</HeatmapAbbr> uses {preview.meta.fis_field_note} (set{" "}
                    <code className="text-slate-400">HEATMAP_FIS_USE_ACV=1</code> for{" "}
                    <HeatmapAbbr term="acv">ACV</HeatmapAbbr> instead of <HeatmapAbbr term="tcv">TCV</HeatmapAbbr>).
                  </p>
                )}

                <div className="mt-6 p-3 bg-slate-800 rounded-lg text-xs leading-relaxed text-slate-300 border border-slate-700">
                  <span className="text-sponsor-orange font-semibold block mb-1">Framework note</span>
                  {preview.justification}
                </div>
              </>
            ) : (
              !previewError && (
                <p className="text-sm text-slate-400">Adjust the form to preview scores from the API.</p>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
