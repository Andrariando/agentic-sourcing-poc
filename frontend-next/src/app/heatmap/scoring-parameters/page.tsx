"use client";

import React, { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl } from "@/lib/api-base";

type ScoringConfigVersion = {
  id: number;
  version: number;
  status: "draft" | "active" | "archived" | string;
  title: string;
  config: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  published_at?: string | null;
};

export default function ScoringParametersPage() {
  const [active, setActive] = useState<ScoringConfigVersion | null>(null);
  const [versions, setVersions] = useState<ScoringConfigVersion[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [title, setTitle] = useState("Scoring Config Draft");
  const [configJson, setConfigJson] = useState("{}");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const selectedDraft = useMemo(
    () => versions.find((v) => v.id === selectedDraftId) || null,
    [versions, selectedDraftId]
  );

  const refresh = async () => {
    setLoading(true);
    try {
      const base = getApiBaseUrl();
      const [aRes, vRes] = await Promise.all([
        apiFetch(`${base}/api/heatmap/scoring-config/active`, { cache: "no-store" }),
        apiFetch(`${base}/api/heatmap/scoring-config/versions`, { cache: "no-store" }),
      ]);
      if (!aRes.ok || !vRes.ok) {
        throw new Error(`Failed to load config endpoints (${aRes.status}/${vRes.status})`);
      }
      const a = (await aRes.json()) as ScoringConfigVersion;
      const v = (await vRes.json()) as ScoringConfigVersion[];
      setActive(a);
      setVersions(Array.isArray(v) ? v : []);
      const latestDraft = (Array.isArray(v) ? v : []).find((x) => x.status === "draft") || null;
      if (latestDraft) {
        setSelectedDraftId(latestDraft.id);
        setTitle(latestDraft.title);
        setConfigJson(JSON.stringify(latestDraft.config || {}, null, 2));
      } else {
        setSelectedDraftId(null);
        setTitle("Scoring Config Draft");
        setConfigJson(JSON.stringify(a?.config || {}, null, 2));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load scoring config.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const saveDraft = async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    let payloadConfig: Record<string, unknown>;
    try {
      payloadConfig = JSON.parse(configJson);
    } catch (e) {
      setError(`Invalid JSON: ${e instanceof Error ? e.message : "parse error"}`);
      setSaving(false);
      return;
    }
    try {
      const base = getApiBaseUrl();
      const endpoint = selectedDraft ? `/api/heatmap/scoring-config/draft/${selectedDraft.id}` : "/api/heatmap/scoring-config/draft";
      const method = selectedDraft ? "PUT" : "POST";
      const res = await apiFetch(`${base}${endpoint}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, config: payloadConfig, created_by: "human-manager" }),
      });
      const body = await res.json().catch(() => ({} as { detail?: string }));
      if (!res.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : `Save failed (${res.status})`);
      }
      setMessage("Draft saved.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save draft.");
    } finally {
      setSaving(false);
    }
  };

  const validateDraft = async () => {
    if (!selectedDraft) return;
    setMessage(null);
    setError(null);
    try {
      const base = getApiBaseUrl();
      const res = await apiFetch(`${base}/api/heatmap/scoring-config/draft/${selectedDraft.id}/validate`, {
        method: "POST",
      });
      const body = (await res.json().catch(() => ({}))) as { valid?: boolean; errors?: string[]; detail?: string };
      if (!res.ok) throw new Error(body.detail || `Validate failed (${res.status})`);
      if (body.valid) setMessage("Validation passed.");
      else setError((body.errors || ["Validation failed."]).join(" | "));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed.");
    }
  };

  const publishDraft = async () => {
    if (!selectedDraft) return;
    setMessage(null);
    setError(null);
    try {
      const base = getApiBaseUrl();
      const res = await apiFetch(`${base}/api/heatmap/scoring-config/draft/${selectedDraft.id}/publish`, {
        method: "POST",
      });
      const body = await res.json().catch(() => ({} as { detail?: string }));
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `Publish failed (${res.status})`);
      setMessage("Draft published and activated.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Publish failed.");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
          <h1 className="text-2xl font-bold text-slate-900">Scoring Parameters</h1>
          <p className="text-sm text-slate-600 mt-2">
            Manage structured scoring parameters, prompts, and explanations with draft/validate/publish workflow.
          </p>
        </header>

        <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Active Configuration</h2>
          {loading ? (
            <p className="text-sm text-slate-500">Loading...</p>
          ) : active ? (
            <div className="text-sm text-slate-700 space-y-1">
              <p>Version: <strong>{active.version}</strong></p>
              <p>Title: <strong>{active.title}</strong></p>
              <p>Status: <strong>{active.status}</strong></p>
              <p>Parameters: <strong>{Array.isArray(active.config?.parameters) ? (active.config.parameters as unknown[]).length : 0}</strong></p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No active config found.</p>
          )}
        </section>

        <section className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Draft Editor</h2>
          <div className="flex flex-wrap gap-3 items-center">
            <label className="text-xs text-slate-600">
              Select draft:
              <select
                className="ml-2 border border-slate-200 rounded px-2 py-1 bg-white"
                value={selectedDraftId ?? ""}
                onChange={(e) => {
                  const nextId = Number(e.target.value || 0) || null;
                  setSelectedDraftId(nextId);
                  const found = versions.find((v) => v.id === nextId) || null;
                  if (found) {
                    setTitle(found.title);
                    setConfigJson(JSON.stringify(found.config || {}, null, 2));
                  }
                }}
              >
                <option value="">(new draft)</option>
                {versions
                  .filter((v) => v.status === "draft")
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      v{v.version} - {v.title}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Draft title
            <input
              className="mt-1 w-full border border-slate-200 rounded px-3 py-2 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Config JSON
            <textarea
              rows={18}
              className="mt-1 w-full border border-slate-200 rounded p-3 text-xs font-mono"
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void saveDraft()}
              disabled={saving}
              className="px-4 py-2 bg-sponsor-blue text-white rounded text-sm font-medium disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Draft"}
            </button>
            <button
              type="button"
              onClick={() => void validateDraft()}
              disabled={!selectedDraft}
              className="px-4 py-2 border border-slate-200 bg-white text-slate-700 rounded text-sm font-medium disabled:opacity-50"
            >
              Validate Draft
            </button>
            <button
              type="button"
              onClick={() => void publishDraft()}
              disabled={!selectedDraft}
              className="px-4 py-2 border border-emerald-300 bg-emerald-50 text-emerald-700 rounded text-sm font-medium disabled:opacity-50"
            >
              Publish Draft
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              className="px-4 py-2 border border-slate-200 bg-white text-slate-700 rounded text-sm font-medium"
            >
              Refresh
            </button>
          </div>
          {message && <p className="text-sm text-emerald-700">{message}</p>}
          {error && <p className="text-sm text-rose-700">{error}</p>}
        </section>
      </div>
    </div>
  );
}
