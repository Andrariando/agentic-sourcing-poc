"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import { HeatmapAbbr } from "@/lib/heatmap-glossary";

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
    } catch {
      setSubmitMessage(`Network error. API base: ${getApiBaseUrl()}${apiConnectivityHint()}`);
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full flex justify-center">
      <div className="max-w-4xl w-full">
        <form
          className="space-y-6 bg-white p-8 rounded-xl border border-slate-200 shadow-sm"
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
      </div>
    </div>
  );
}
