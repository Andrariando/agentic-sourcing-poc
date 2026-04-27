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

type ScoringParameter = {
  key?: string;
  label?: string;
  applies_to?: string[];
  input_fields?: string[];
  rule_type?: string;
  rule_config?: Record<string, unknown>;
  default_policy?: Record<string, unknown>;
  weight_key?: string;
  prompt_template?: string;
  explanation_template?: string;
};

const KNOWN_WEIGHT_KEYS = [
  "w_eus",
  "w_fis",
  "w_rss",
  "w_scs",
  "w_sas_contract",
  "w_ius",
  "w_es",
  "w_csis",
  "w_sas_new",
] as const;

const PARAM_TEMPLATES: Array<{ key: string; label: string; applies_to: string[]; weight_key: string; rule_type: string }> = [
  { key: "eus_score", label: "Expiry Urgency Score", applies_to: ["renewal"], weight_key: "w_eus", rule_type: "banded_score" },
  { key: "fis_score", label: "Financial Impact Score", applies_to: ["renewal"], weight_key: "w_fis", rule_type: "normalized" },
  { key: "rss_score", label: "Supplier Risk Score", applies_to: ["renewal"], weight_key: "w_rss", rule_type: "lookup_map" },
  { key: "scs_score", label: "Spend Concentration Score", applies_to: ["renewal"], weight_key: "w_scs", rule_type: "normalized" },
  { key: "sas_score", label: "Strategic Alignment Score (Renewal)", applies_to: ["renewal"], weight_key: "w_sas_contract", rule_type: "lookup_map" },
  { key: "ius_score", label: "Implementation Urgency Score", applies_to: ["new_business"], weight_key: "w_ius", rule_type: "banded_score" },
  { key: "es_score", label: "Estimated Spend Score", applies_to: ["new_business"], weight_key: "w_es", rule_type: "normalized" },
  { key: "csis_score", label: "Category Spend Impact Score", applies_to: ["new_business"], weight_key: "w_csis", rule_type: "formula" },
  { key: "sas_score_new", label: "Strategic Alignment Score (New)", applies_to: ["new_business"], weight_key: "w_sas_new", rule_type: "lookup_map" },
];

function parseJsonObject(raw: string): { value: Record<string, unknown> | null; error: string | null } {
  try {
    const p = JSON.parse(raw);
    if (!p || typeof p !== "object" || Array.isArray(p)) {
      return { value: null, error: "Config must be a JSON object." };
    }
    return { value: p as Record<string, unknown>, error: null };
  } catch (e) {
    return { value: null, error: e instanceof Error ? e.message : "Invalid JSON" };
  }
}

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
  const [editorMode, setEditorMode] = useState<"builder" | "json">("builder");

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

  const parsedDraft = useMemo(() => parseJsonObject(configJson), [configJson]);
  const parameters = useMemo(
    () => (Array.isArray(parsedDraft.value?.parameters) ? (parsedDraft.value?.parameters as ScoringParameter[]) : []),
    [parsedDraft.value]
  );
  const formulas = useMemo(
    () => ((parsedDraft.value?.formulas && typeof parsedDraft.value.formulas === "object")
      ? (parsedDraft.value.formulas as Record<string, any>)
      : {}),
    [parsedDraft.value]
  );
  const localValidationErrors = useMemo(() => {
    const errs: string[] = [];
    if (parsedDraft.error) errs.push(`JSON error: ${parsedDraft.error}`);
    const seen = new Set<string>();
    for (const p of parameters) {
      const key = String(p?.key || "").trim();
      if (!key) errs.push("Every parameter needs a key.");
      if (key && seen.has(key)) errs.push(`Duplicate parameter key: ${key}`);
      if (key) seen.add(key);
      if (!String(p?.label || "").trim()) errs.push(`Parameter '${key || "(unnamed)"}' is missing a label.`);
      if (!String(p?.weight_key || "").trim()) errs.push(`Parameter '${key || "(unnamed)"}' is missing weight key.`);
    }
    const groups: Array<"renewal" | "new_business"> = ["renewal", "new_business"];
    for (const g of groups) {
      const cfg = formulas[g] || {};
      const vals = (cfg.weight_values && typeof cfg.weight_values === "object") ? cfg.weight_values as Record<string, unknown> : {};
      const nums = Object.values(vals)
        .map((v) => Number(v))
        .filter((n) => Number.isFinite(n));
      if (nums.length > 0) {
        const sum = nums.reduce((a, b) => a + b, 0);
        if (Math.abs(sum - 1) > 0.001) errs.push(`${g} weight_values should sum to 1.0 (current ${sum.toFixed(3)}).`);
      }
    }
    return errs;
  }, [parsedDraft.error, parameters, formulas]);

  const updateDraftConfig = (updater: (draft: Record<string, unknown>) => void) => {
    const parsed = parseJsonObject(configJson).value || {};
    const next = JSON.parse(JSON.stringify(parsed)) as Record<string, unknown>;
    updater(next);
    setConfigJson(JSON.stringify(next, null, 2));
  };

  const updateParameter = (idx: number, patch: Partial<ScoringParameter>) => {
    updateDraftConfig((draft) => {
      const params = Array.isArray(draft.parameters) ? [...(draft.parameters as ScoringParameter[])] : [];
      const curr = (params[idx] && typeof params[idx] === "object") ? params[idx] : {};
      params[idx] = { ...curr, ...patch };
      draft.parameters = params;
    });
  };

  const removeParameter = (idx: number) => {
    updateDraftConfig((draft) => {
      const params = Array.isArray(draft.parameters) ? [...(draft.parameters as ScoringParameter[])] : [];
      params.splice(idx, 1);
      draft.parameters = params;
    });
  };

  const addParameterFromTemplate = (templateKey: string) => {
    const tpl = PARAM_TEMPLATES.find((t) => t.key === templateKey);
    if (!tpl) return;
    updateDraftConfig((draft) => {
      const params = Array.isArray(draft.parameters) ? [...(draft.parameters as ScoringParameter[])] : [];
      params.push({
        key: tpl.key,
        label: tpl.label,
        applies_to: tpl.applies_to,
        input_fields: [],
        rule_type: tpl.rule_type,
        rule_config: {},
        default_policy: { strategy: "constant", value: 5 },
        weight_key: tpl.weight_key,
      });
      draft.parameters = params;
    });
  };

  const updateWeight = (group: "renewal" | "new_business", key: string, value: string) => {
    updateDraftConfig((draft) => {
      const formulasObj =
        draft.formulas && typeof draft.formulas === "object" ? { ...(draft.formulas as Record<string, unknown>) } : {};
      const groupCfg = formulasObj[group] && typeof formulasObj[group] === "object" ? { ...(formulasObj[group] as Record<string, unknown>) } : {};
      const weightValues =
        groupCfg.weight_values && typeof groupCfg.weight_values === "object"
          ? { ...(groupCfg.weight_values as Record<string, unknown>) }
          : {};
      const n = Number(value);
      weightValues[key] = Number.isFinite(n) ? n : 0;
      groupCfg.weight_values = weightValues;
      const existingKeys = Array.isArray(groupCfg.weight_keys) ? [...(groupCfg.weight_keys as string[])] : [];
      if (!existingKeys.includes(key)) existingKeys.push(key);
      groupCfg.weight_keys = existingKeys;
      formulasObj[group] = groupCfg;
      draft.formulas = formulasObj;
    });
  };

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
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setEditorMode("builder")}
              className={`px-3 py-1.5 rounded text-xs font-semibold border ${editorMode === "builder" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200"}`}
            >
              Builder
            </button>
            <button
              type="button"
              onClick={() => setEditorMode("json")}
              className={`px-3 py-1.5 rounded text-xs font-semibold border ${editorMode === "json" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-200"}`}
            >
              Raw JSON (Advanced)
            </button>
          </div>

          {editorMode === "builder" ? (
            <div className="space-y-5">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Parameter Builder</p>
                <p className="text-xs text-slate-500 mt-1">Edit parameters with forms. JSON updates automatically.</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-600">Add parameter:</span>
                  {PARAM_TEMPLATES.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => addParameterFromTemplate(t.key)}
                      className="px-2.5 py-1 rounded border border-slate-200 bg-white text-xs text-slate-700 hover:bg-slate-100"
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                {parameters.length === 0 ? (
                  <p className="text-sm text-slate-500 italic">No parameters found in this draft yet.</p>
                ) : (
                  parameters.map((p, idx) => (
                    <div key={`${p.key || "param"}-${idx}`} className="rounded-lg border border-slate-200 p-4 bg-white space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-800">Parameter {idx + 1}</p>
                        <button
                          type="button"
                          onClick={() => removeParameter(idx)}
                          className="text-xs px-2 py-1 border border-rose-200 text-rose-700 bg-rose-50 rounded"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <label className="text-xs text-slate-600">
                          Key
                          <input
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
                            value={String(p.key || "")}
                            onChange={(e) => updateParameter(idx, { key: e.target.value })}
                          />
                        </label>
                        <label className="text-xs text-slate-600">
                          Label
                          <input
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
                            value={String(p.label || "")}
                            onChange={(e) => updateParameter(idx, { label: e.target.value })}
                          />
                        </label>
                        <label className="text-xs text-slate-600">
                          Applies to
                          <select
                            multiple
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm min-h-[70px]"
                            value={Array.isArray(p.applies_to) ? p.applies_to : []}
                            onChange={(e) => {
                              const opts = Array.from(e.target.selectedOptions).map((o) => o.value);
                              updateParameter(idx, { applies_to: opts });
                            }}
                          >
                            <option value="renewal">renewal</option>
                            <option value="new_business">new_business</option>
                          </select>
                        </label>
                        <label className="text-xs text-slate-600">
                          Rule type
                          <select
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
                            value={String(p.rule_type || "lookup_map")}
                            onChange={(e) => updateParameter(idx, { rule_type: e.target.value })}
                          >
                            <option value="direct_numeric">direct_numeric</option>
                            <option value="banded_score">banded_score</option>
                            <option value="lookup_map">lookup_map</option>
                            <option value="normalized">normalized</option>
                            <option value="formula">formula</option>
                          </select>
                        </label>
                        <label className="text-xs text-slate-600">
                          Weight key
                          <select
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
                            value={String(p.weight_key || "")}
                            onChange={(e) => updateParameter(idx, { weight_key: e.target.value })}
                          >
                            <option value="">(select weight key)</option>
                            {KNOWN_WEIGHT_KEYS.map((k) => (
                              <option key={k} value={k}>{k}</option>
                            ))}
                          </select>
                        </label>
                        <label className="text-xs text-slate-600">
                          Input fields (comma-separated)
                          <input
                            className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
                            value={Array.isArray(p.input_fields) ? p.input_fields.join(", ") : ""}
                            onChange={(e) =>
                              updateParameter(idx, {
                                input_fields: e.target.value
                                  .split(",")
                                  .map((x) => x.trim())
                                  .filter(Boolean),
                              })
                            }
                          />
                        </label>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Weight Values</p>
                <p className="text-xs text-slate-500 mt-1">Use decimals (e.g. 0.30). Target sum per group: 1.0.</p>
                <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {(["renewal", "new_business"] as const).map((group) => {
                    const cfg = formulas[group] || {};
                    const vals = (cfg.weight_values && typeof cfg.weight_values === "object") ? cfg.weight_values as Record<string, unknown> : {};
                    const entries = Object.entries(vals);
                    return (
                      <div key={group} className="rounded border border-slate-200 bg-white p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">{group}</p>
                        {entries.length === 0 ? (
                          <p className="text-xs text-slate-500 italic">No weights found for this group yet.</p>
                        ) : (
                          <div className="space-y-2">
                            {entries.map(([k, v]) => (
                              <label key={`${group}-${k}`} className="flex items-center justify-between gap-2 text-xs text-slate-700">
                                <span className="font-mono">{k}</span>
                                <input
                                  type="number"
                                  step="0.01"
                                  className="w-24 border border-slate-200 rounded px-2 py-1 text-xs"
                                  value={Number(v)}
                                  onChange={(e) => updateWeight(group, k, e.target.value)}
                                />
                              </label>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <label className="block text-sm font-medium text-slate-700">
              Config JSON
              <textarea
                rows={18}
                className="mt-1 w-full border border-slate-200 rounded p-3 text-xs font-mono"
                value={configJson}
                onChange={(e) => setConfigJson(e.target.value)}
              />
            </label>
          )}
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
          {localValidationErrors.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-900 mb-1">Live validation</p>
              <ul className="text-xs text-amber-900 list-disc pl-4 space-y-0.5">
                {localValidationErrors.slice(0, 8).map((err, i) => (
                  <li key={`${err}-${i}`}>{err}</li>
                ))}
              </ul>
            </div>
          )}
          {message && <p className="text-sm text-emerald-700">{message}</p>}
          {error && <p className="text-sm text-rose-700">{error}</p>}
        </section>
      </div>
    </div>
  );
}
