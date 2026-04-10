"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  LayoutGrid,
  List,
  X,
  MessageCircle,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import { HeatmapAbbr, HEATMAP_GLOSSARY, type HeatmapGlossaryKey } from "@/lib/heatmap-glossary";
import { heatmapTierLabel } from "@/lib/heatmap-tier-display";
import ProcuraBotIdentity from "@/components/branding/ProcuraBotIdentity";
import { PROCURABOT_BRAND } from "@/lib/procurabot-brand";
import { HeatmapScoreBreakdown, type HeatmapOpportunityLike } from "@/lib/heatmap-score-breakdown";

const TIER_TOOLTIP: Record<string, HeatmapGlossaryKey> = {
  T1: "t1",
  T2: "t2",
  T3: "t3",
  T4: "t4",
};

function isHeatmapNewRequest(o: { request_id?: string | null; contract_id?: string | null }): boolean {
  return Boolean(o.request_id) && !o.contract_id;
}

function formatScore(n: unknown): string {
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  return v.toFixed(1);
}

function matrixScatterFillForTier(tier: string | undefined): string {
  if (tier === "T1") return "#ef4444";
  if (tier === "T2") return "#f97316";
  if (tier === "T3") return "#3b82f6";
  return "#64748b";
}

/** Scatter dot: radius from total priority score (0–10); fill from tier. Bypasses ZAxis so size is never stuck uniform. */
function HeatmapMatrixScatterDot(props: {
  cx?: number;
  cy?: number;
  payload?: { total_score?: number; tier?: string };
  onClick?: React.MouseEventHandler<SVGCircleElement>;
}) {
  const { cx, cy, payload, onClick } = props;
  if (cx == null || cy == null) return null;
  const raw = Number(payload?.total_score);
  const score = Number.isFinite(raw) ? Math.max(0, Math.min(10, raw)) : 0;
  // Wider radius range + slight curve so nearby scores (e.g. 8.2 vs 9.1) still read differently on the chart.
  const t = score / 10;
  const r = 5 + t ** 1.35 * 22;
  const fill = matrixScatterFillForTier(payload?.tier);
  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill={fill}
      fillOpacity={0.7}
      stroke={fill}
      strokeWidth={2}
      className="cursor-pointer transition-all hover:fill-opacity-100"
      onClick={onClick}
    />
  );
}

const PS_NEW_WEIGHT_KEYS = ["w_ius", "w_es", "w_csis", "w_sas_new"] as const;
const PS_CONTRACT_WEIGHT_KEYS = ["w_eus", "w_fis", "w_rss", "w_scs", "w_sas_contract"] as const;

const WEIGHT_LABELS: Record<string, string> = {
  w_ius: "IUS — implementation urgency",
  w_es: "ES — estimated spend",
  w_csis: "CSIS — category spend importance",
  w_sas_new: "SAS — strategic alignment (new)",
  w_eus: "EUS — expiry urgency",
  w_fis: "FIS — financial impact",
  w_rss: "RSS — supplier risk",
  w_scs: "SCS — spend concentration",
  w_sas_contract: "SAS — strategic alignment (renewal)",
};

function parseInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let key = 0;
  const re = /(\*\*[\s\S]+?\*\*|\*[^*\n]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const full = m[1];
    if (full.startsWith("**")) {
      parts.push(
        <strong key={`md-${key++}`} className="font-semibold text-slate-900">
          {full.slice(2, -2)}
        </strong>
      );
    } else {
      parts.push(
        <em key={`md-${key++}`} className="italic text-slate-800">
          {full.slice(1, -1)}
        </em>
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 0 ? text : <>{parts}</>;
}

function parseSimpleMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, idx) => (
        <React.Fragment key={`ln-${idx}`}>
          {idx > 0 ? <br /> : null}
          {parseInlineMarkdown(line)}
        </React.Fragment>
      ))}
    </>
  );
}

/** Common override reasons — map to PS_new / PS_contract components and governance. */
const PRIORITY_OVERRIDE_REASONS: { id: string; label: string }[] = [
  { id: "ius_eus", label: "Urgency / timing (IUS or EUS) doesn’t match business reality" },
  { id: "es_fis", label: "Spend or financial scale (ES or FIS) is understated or overstated" },
  { id: "csis_scs_rss", label: "Category importance, risk, or concentration (CSIS, RSS, SCS) feels wrong" },
  { id: "sas", label: "Strategic alignment (SAS) doesn’t reflect supplier or category strategy" },
  { id: "weighted_total", label: "Weighted total (PS_new or PS_contract) doesn’t reflect holistic risk / priority" },
  { id: "category_policy", label: "Category card / preferred-supplier policy should override the numeric rank" },
  { id: "data_quality", label: "Input data quality issue (stale fields, wrong supplier context, etc.)" },
  { id: "strategic_exception", label: "Executive or strategic exception not captured by the model" },
  { id: "other", label: "Others (explain below)" },
];

function buildPriorityOverrideNotes(reasonKeys: string[], freeText: string): string {
  const labels = reasonKeys
    .map((id) => PRIORITY_OVERRIDE_REASONS.find((r) => r.id === id)?.label)
    .filter(Boolean) as string[];
  const head =
    labels.length > 0
      ? `Reasons for priority adjustment:\n${labels.map((l) => `• ${l}`).join("\n")}\n\n`
      : "";
  const tail = freeText.trim();
  if (!head && !tail) return "(No rationale provided)";
  if (!tail) return head.trimEnd();
  if (!head) return tail;
  return `${head}Additional notes:\n${tail}`;
}

function normalizeWeightGroup(w: Record<string, number>, keys: readonly string[]) {
  const copy = { ...w };
  let s = 0;
  for (const k of keys) s += Math.max(0, copy[k] ?? 0);
  if (s < 1e-9) return copy;
  for (const k of keys) copy[k] = Math.max(0.01, (copy[k] ?? 0) / s);
  return copy;
}

/** Maps a 0–1 weight to horizontal position on a range input with min=1, max=99. */
function weightToSliderTrackPercent(weight: number | undefined): number {
  const sliderVal = Math.min(99, Math.max(1, Math.round((weight ?? 0.2) * 100)));
  return ((sliderVal - 1) / 98) * 100;
}

/** Match backend tier bands (intake_scoring / learned_weights). */
function tierFromMathTotal(total: number): string {
  if (total >= 8) return "T1";
  if (total >= 6) return "T2";
  if (total >= 4) return "T3";
  return "T4";
}

/**
 * Weighted PS_new / PS_contract total from component scores × normalized slider weights.
 * Same linear formula as the supervisor; does not include category-card overlay or learning nudge.
 */
function previewScoreFromWeights(
  opp: Record<string, unknown>,
  weights: Record<string, number> | null,
  isNewRequest: boolean
): { total: number; mathTier: string } | null {
  if (!weights || !opp) return null;
  const keys = isNewRequest ? PS_NEW_WEIGHT_KEYS : PS_CONTRACT_WEIGHT_KEYS;
  const w = normalizeWeightGroup({ ...weights }, keys);
  let raw = 0;
  if (isNewRequest) {
    raw =
      (w.w_ius ?? 0) * Number(opp.ius_score ?? 0) +
      (w.w_es ?? 0) * Number(opp.es_score ?? 0) +
      (w.w_csis ?? 0) * Number(opp.csis_score ?? 0) +
      (w.w_sas_new ?? 0) * Number(opp.sas_score ?? 0);
  } else {
    raw =
      (w.w_eus ?? 0) * Number(opp.eus_score ?? 0) +
      (w.w_fis ?? 0) * Number(opp.fis_score ?? 0) +
      (w.w_rss ?? 0) * Number(opp.rss_score ?? 0) +
      (w.w_scs ?? 0) * Number(opp.scs_score ?? 0) +
      (w.w_sas_contract ?? 0) * Number(opp.sas_score ?? 0);
  }
  const total = Math.round(Math.min(10, Math.max(0, raw)) * 100) / 100;
  return { total, mathTier: tierFromMathTotal(total) };
}

export default function HeatmapPriorityPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'heatmap'>('table');
  
  // Review Modal State
  const [reviewOpp, setReviewOpp] = useState<any | null>(null);
  const [feedbackTier, setFeedbackTier] = useState<string>("T1");
  /** Selected reason ids from PRIORITY_OVERRIDE_REASONS (multi-select). */
  const [feedbackReasonKeys, setFeedbackReasonKeys] = useState<string[]>([]);
  const [feedbackReason, setFeedbackReason] = useState<string>("");
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackHistory, setFeedbackHistory] = useState<
    | {
        id: number;
        reviewer_id: string;
        timestamp: string;
        adjustment_type: string;
        adjustment_value: number;
        reason_code: string;
        comment_text?: string | null;
        component_affected: string;
      }[]
    | null
  >(null);
  const [feedbackHistoryLoading, setFeedbackHistoryLoading] = useState(false);
  const [scoringWeights, setScoringWeights] = useState<Record<string, number> | null>(null);
  /** Snapshot of API weights for this review session — anchor for the red benchmark markers. */
  const [baselineScoringWeights, setBaselineScoringWeights] = useState<Record<string, number> | null>(null);
  const [reviewSaveNotice, setReviewSaveNotice] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  // Optional ProcuraBot Slide-over
  const [copilotOpen, setProcuraBotOpen] = useState(false);
  const [copilotTab, setProcuraBotTab] = useState<"qa" | "policy" | "cards">("qa");
  const [copilotRefQuery, setProcuraBotRefQuery] = useState("");
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaAnswer, setQaAnswer] = useState<string | null>(null);
  const [qaResponseId, setQaResponseId] = useState<string | null>(null);
  const [qaVote, setQaVote] = useState<"up" | "down" | null>(null);
  const [qaVoteLoading, setQaVoteLoading] = useState(false);
  const [qaVoteNotice, setQaVoteNotice] = useState<string | null>(null);
  const [qaLoading, setQaLoading] = useState(false);
  const [qaUsedLlm, setQaUsedLlm] = useState(false);
  const [policyText, setPolicyText] = useState("");
  const [policyCategory, setPolicyCategory] = useState("IT Infrastructure");
  const [policySupplier, setPolicySupplier] = useState("");
  const [policyTier, setPolicyTier] = useState("");
  const [policyResult, setPolicyResult] = useState<{
    contradicts?: boolean;
    severity?: string;
    summary?: string;
    suggestion?: string;
    used_llm?: boolean;
  } | null>(null);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [assistCategory, setAssistCategory] = useState("IT Infrastructure");
  const [assistInstruction, setAssistInstruction] = useState("");
  const [assistResult, setAssistResult] = useState<{
    proposed_patch?: Record<string, unknown>;
    notes?: string;
    used_llm?: boolean;
  } | null>(null);
  const [assistLoading, setAssistLoading] = useState(false);
  const [uploadExtract, setUploadExtract] = useState<{
    proposed_patch?: Record<string, unknown>;
    notes?: string;
    filename?: string;
  } | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [pendingPatch, setPendingPatch] = useState<Record<string, unknown> | null>(null);
  const [applyLoading, setApplyLoading] = useState(false);
  const [cardCategories, setCardCategories] = useState<string[]>(["IT Infrastructure", "Software", "Hardware"]);
  const activeOpportunities = opportunities;

  const rankOpportunities = (rows: any[]) =>
    rows.sort((a: any, b: any) => b.total_score - a.total_score);

  const isOpportunityReviewed = (opp: any) =>
    opp?.status === "Approved" ||
    Boolean(opp?.reviewed) ||
    Number(opp?.kli_metrics?.feedback_rows ?? 0) > 0;

  const isOpportunityApproved = (opp: any) => opp?.status === "Approved";

  useEffect(() => {
    if (!copilotOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setProcuraBotOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [copilotOpen]);

  useEffect(() => {
    if (reviewOpp) return;
    setScoringWeights(null);
    setBaselineScoringWeights(null);
  }, [reviewOpp]);

  useEffect(() => {
    if (!reviewSaveNotice) return;
    const ms = reviewSaveNotice.kind === "success" ? 8000 : 12000;
    const t = window.setTimeout(() => setReviewSaveNotice(null), ms);
    return () => window.clearTimeout(t);
  }, [reviewSaveNotice]);

  useEffect(() => {
    (async () => {
      try {
        const r = await apiFetch(`${getApiBaseUrl()}/api/heatmap/intake/categories`, { cache: "no-store" });
        if (!r.ok) return;
        const d = await r.json();
        if (Array.isArray(d.categories) && d.categories.length > 0) setCardCategories(d.categories);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    async function fetchData() {
      try {
        const url = `${getApiBaseUrl()}/api/heatmap/opportunities`;
        
        console.log("Fetching heatmap opportunities from:", url);
        const res = await apiFetch(url, { cache: 'no-store' });
        const data = await res.json();
        
        if (data.opportunities) setOpportunities(rankOpportunities(data.opportunities));
      } catch (err) {
        console.error("Failed to fetch opportunities", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  // Compute Dashboard Stats
  const totalMonitored = activeOpportunities.length;
  const tier1 = activeOpportunities.filter((o) => o.tier === "T1").length;
  const tier2 = activeOpportunities.filter((o) => o.tier === "T2").length;
  const tier3 = activeOpportunities.filter((o) => o.tier === "T3").length;
  
  // Calculate total pipeline value
  const totalValue = activeOpportunities.reduce((acc, curr) => {
    // Check various possible value fields
    const val = curr.estimated_spend || curr.es_value || curr.total_contract_value || 0;
    return acc + Number(val);
  }, 0);
  
  // Format to roughly match "$14.2M" if large enough, or fallback
  const formatMillions = (val: number) => {
    if (val === 0) return "$14.2M"; // Demo fallback if no real financial data exists yet
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(1)}K`;
    return `$${val}`;
  };
  
  const pipelineValueText = formatMillions(totalValue);

  const openReviewModal = async (opp: any) => {
    if (isOpportunityApproved(opp)) return;
    setReviewOpp(opp);
    setFeedbackTier(opp.tier);
    setFeedbackReason("");
    setFeedbackReasonKeys([]);
    setFeedbackHistory(null);
    setFeedbackHistoryLoading(true);
    setScoringWeights(null);
    setBaselineScoringWeights(null);
    try {
      const base = getApiBaseUrl();
      const [histRes, wRes] = await Promise.all([
        apiFetch(`${base}/api/heatmap/feedback/history?opportunity_id=${opp.id}`, { cache: "no-store" }),
        apiFetch(`${base}/api/heatmap/scoring-weights`, { cache: "no-store" }),
      ]);
      if (!histRes.ok) setFeedbackHistory([]);
      else {
        const rows = (await histRes.json()) as any[];
        setFeedbackHistory(Array.isArray(rows) ? rows : []);
      }
      if (wRes.ok) {
        const wd = (await wRes.json()) as { weights?: Record<string, number> };
        if (wd.weights && typeof wd.weights === "object") {
          const snap = { ...wd.weights };
          setScoringWeights(snap);
          setBaselineScoringWeights({ ...snap });
        }
      }
    } catch {
      setFeedbackHistory([]);
    } finally {
      setFeedbackHistoryLoading(false);
    }
  };

  // Feedback Submission Logic
  const submitFeedback = async () => {
    if (!reviewOpp) return;
    if (feedbackReasonKeys.length === 0 && feedbackReason.trim().length < 8) {
      window.alert("Select at least one reason for the adjustment, or enter a short rationale in the text box (or both).");
      return;
    }
    if (feedbackReasonKeys.includes("other") && feedbackReason.trim().length < 8) {
      window.alert('When "Others" is selected, add a bit more detail in the additional notes box.');
      return;
    }
    setFeedbackSubmitting(true);
    try {
      const url = `${getApiBaseUrl()}/api/heatmap/feedback`;

      const isNewRequest = reviewOpp.contract_id == null || reviewOpp.contract_id === "";
      const wkeys = isNewRequest ? PS_NEW_WEIGHT_KEYS : PS_CONTRACT_WEIGHT_KEYS;
      const scoring_weight_overrides =
        scoringWeights != null
          ? wkeys.reduce(
              (acc, k) => {
                acc[k] = scoringWeights[k] ?? 0;
                return acc;
              },
              {} as Record<string, number>
            )
          : undefined;

      const combinedNotes = buildPriorityOverrideNotes(feedbackReasonKeys, feedbackReason);

      const payload = {
        opportunity_id: reviewOpp.id,
        user_id: "human-manager",
        original_tier: reviewOpp.tier,
        suggested_tier: feedbackTier,
        feedback_notes: combinedNotes,
        ...(scoring_weight_overrides ? { scoring_weight_overrides } : {}),
      };

      const res = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        const data = (await res.json().catch(() => ({}))) as {
          opportunity?: { tier?: string; total_score?: number };
        };
        const snap = data.opportunity;
        const updated = opportunities.map((o) => {
          if (o.id === reviewOpp.id) {
            const oldFeedbackRows = Number(o?.kli_metrics?.feedback_rows ?? 0);
            return {
              ...o,
              tier: snap?.tier ?? feedbackTier,
              total_score: snap?.total_score ?? o.total_score,
              reviewed: true,
              kli_metrics: {
                ...(o?.kli_metrics ?? {}),
                feedback_rows: oldFeedbackRows + 1,
              },
            };
          }
          return o;
        });
        setOpportunities(rankOpportunities(updated));

        const scorePart =
          snap?.total_score != null && !Number.isNaN(Number(snap.total_score))
            ? ` Priority score is now ${Number(snap.total_score).toFixed(1)}/10.`
            : "";
        const baseSavedMsg = `Review saved for ${reviewOpp.supplier_name || "this opportunity"} (priority ${heatmapTierLabel(feedbackTier)}).${scorePart} Your feedback is stored in the audit log.`;

        setReviewOpp(null);

        setReviewSaveNotice({ kind: "success", message: baseSavedMsg });
      } else {
        const errBody = await res.text().catch(() => "");
        setReviewSaveNotice({
          kind: "error",
          message: `Review was not saved (server ${res.status}). ${errBody ? errBody.slice(0, 200) : "Try again or check the API."}`,
        });
      }
    } catch (e) {
      console.error(e);
      setReviewSaveNotice({
        kind: "error",
        message: "Could not reach the server. Your review was not saved — check your connection and try again.",
      });
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleApproveToExecution = async (opp: any) => {
    if (isOpportunityApproved(opp)) return;
    if (!isOpportunityReviewed(opp)) {
      alert("Review this opportunity first before approving to S2C Execution.");
      return;
    }
    try {
      const url = `${getApiBaseUrl()}/api/heatmap/approve`;

      const res = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          opportunity_ids: [opp.id],
          approver_id: "human-manager"
        })
      });

      if (res.ok) {
        const data = await res.json();
        const caseId = data.cases?.[String(opp.id)];
        const linked = data.already_linked?.[String(opp.id)] === true;
        alert(
          linked
            ? `Already linked to S2C Execution${caseId ? ` (Case ${caseId})` : ""}.`
            : `Approved to S2C Execution${caseId ? ` (Case ${caseId})` : ""}.`
        );
        // Refresh list so server-side Approved status matches the UI.
        const oppUrl = `${getApiBaseUrl()}/api/heatmap/opportunities`;
        const oppRes = await apiFetch(oppUrl, { cache: "no-store" });
        const oppJson = await oppRes.json();
        if (oppJson.opportunities) {
          setOpportunities(rankOpportunities(oppJson.opportunities));
        }
      } else {
        alert("Failed to approve to S2C Execution. Please try again.");
      }
    } catch (err) {
      console.error(err);
      alert("Network error approving to S2C Execution.");
    }
  };

  const handleRefreshScores = async () => {
    setPipelineRunning(true);
    try {
      const base = getApiBaseUrl();
      const runUrl = `${base}/api/heatmap/run`;
      const statusUrl = `${base}/api/heatmap/run/status`;
      const oppUrl = `${base}/api/heatmap/opportunities`;

      const runRes = await apiFetch(runUrl, { method: "POST" });
      if (!runRes.ok) {
        alert("Failed to run scoring pipeline.");
        return;
      }

      // Poll pipeline status for up to 60s (demo-safe on small backend instances).
      const maxPolls = 20;
      for (let i = 0; i < maxPolls; i++) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const statusRes = await apiFetch(statusUrl, { cache: "no-store" });
        if (!statusRes.ok) continue;
        const status = await statusRes.json();
        if (!status.running) {
          if (status.last_success === false) {
            alert(`Scoring finished with error: ${status.last_error || "unknown error"}`);
          }
          break;
        }
      }

      const oppRes = await apiFetch(oppUrl, { cache: "no-store" });
      const data = await oppRes.json();
      if (data.opportunities) setOpportunities(rankOpportunities(data.opportunities));
    } catch (err) {
      console.error(err);
      const msg = err instanceof Error ? err.message : String(err);
      alert(
        `Network error refreshing scores.\n\n${msg}\n\nAPI base: ${getApiBaseUrl()}${apiConnectivityHint()}`
      );
    } finally {
      setPipelineRunning(false);
    }
  };

  const submitHeatmapQA = async () => {
    setQaLoading(true);
    setQaAnswer(null);
    setQaResponseId(null);
    setQaVote(null);
    setQaVoteNotice(null);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: qaQuestion }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setQaAnswer(typeof data.detail === "string" ? data.detail : "Request failed.");
        setQaUsedLlm(false);
        return;
      }
      setQaAnswer(data.answer || "");
      setQaUsedLlm(Boolean(data.used_llm));
      setQaResponseId(typeof data.response_id === "string" ? data.response_id : null);
    } catch {
      setQaAnswer(`Network error. API: ${getApiBaseUrl()}${apiConnectivityHint()}`);
      setQaUsedLlm(false);
    } finally {
      setQaLoading(false);
    }
  };

  const submitQaVote = async (vote: "up" | "down") => {
    if (!qaAnswer || !qaResponseId || qaQuestion.trim().length < 3) return;
    setQaVoteLoading(true);
    setQaVoteNotice(null);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/qa/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          response_id: qaResponseId,
          question: qaQuestion.trim(),
          answer: qaAnswer,
          vote,
          user_id: "human-manager",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setQaVoteNotice(
          typeof data.detail === "string" ? data.detail : "Could not save feedback."
        );
        return;
      }
      setQaVote(vote);
      setQaVoteNotice("Thanks, feedback saved for KPI tracking.");
    } catch {
      setQaVoteNotice("Network error saving feedback.");
    } finally {
      setQaVoteLoading(false);
    }
  };

  const submitPolicyCheck = async () => {
    setPolicyLoading(true);
    setPolicyResult(null);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/policy/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedback_text: policyText,
          category: policyCategory,
          supplier_name: policySupplier || undefined,
          current_tier: policyTier || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setPolicyResult({ summary: typeof data.detail === "string" ? data.detail : "Request failed." });
        return;
      }
      setPolicyResult(data);
    } catch {
      setPolicyResult({ summary: `Network error. ${getApiBaseUrl()}` });
    } finally {
      setPolicyLoading(false);
    }
  };

  const submitAssistCategory = async () => {
    setAssistLoading(true);
    setAssistResult(null);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/category-cards/assist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: assistCategory, instruction: assistInstruction }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setAssistResult({ notes: typeof data.detail === "string" ? data.detail : "Request failed." });
        return;
      }
      setAssistResult(data);
      if (data.proposed_patch && Object.keys(data.proposed_patch).length > 0) {
        setPendingPatch(data.proposed_patch as Record<string, unknown>);
      }
    } catch {
      setAssistResult({ notes: `Network error. ${getApiBaseUrl()}` });
    } finally {
      setAssistLoading(false);
    }
  };

  const onPolicyFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploadLoading(true);
    setUploadExtract(null);
    try {
      const fd = new FormData();
      fd.append("category", assistCategory);
      fd.append("file", file);
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/category-cards/extract-upload`, {
        method: "POST",
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setUploadExtract({
          notes: typeof data.detail === "string" ? data.detail : "Upload extract failed.",
        });
        return;
      }
      setUploadExtract(data);
      if (data.proposed_patch && Object.keys(data.proposed_patch).length > 0) {
        setPendingPatch(data.proposed_patch as Record<string, unknown>);
      }
    } catch {
      setUploadExtract({ notes: `Network error. ${getApiBaseUrl()}` });
    } finally {
      setUploadLoading(false);
    }
  };

  const applyPatchAndRescore = async () => {
    if (!pendingPatch || Object.keys(pendingPatch).length === 0) return;
    setApplyLoading(true);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/heatmap/category-cards/apply-and-rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: assistCategory, proposed_patch: pendingPatch }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(typeof data.detail === "string" ? data.detail : "Apply failed.");
        return;
      }
      alert(
        "Category cards updated and scoring pipeline started. Refresh the list in a few seconds when the run finishes."
      );
      setTimeout(() => {
        void (async () => {
          try {
            const url = `${getApiBaseUrl()}/api/heatmap/opportunities`;
            const r = await apiFetch(url, { cache: "no-store" });
            const j = await r.json();
            if (j.opportunities) {
              setOpportunities(rankOpportunities(j.opportunities));
            }
          } catch {
            /* ignore */
          }
        })();
      }, 8000);
    } catch {
      alert("Network error.");
    } finally {
      setApplyLoading(false);
    }
  };

  // Matrix axes must match row type: renewals use FIS + EUS/RSS (and SCS for spread);
  // new requests use ES + CSIS on X and IUS on Y (PS_new does not populate FIS/EUS/RSS).
  const chartData = activeOpportunities.map((o) => {
    const isNewRequest = isHeatmapNewRequest(o);
    let x: number;
    let y: number;
    if (isNewRequest) {
      const es = o.es_score ?? 0;
      const csis = o.csis_score ?? 0;
      x = es * 0.65 + csis * 0.35;
      y = o.ius_score ?? 0;
    } else {
      const fis = o.fis_score ?? 0;
      const scs = o.scs_score ?? 0;
      x = fis * 0.65 + scs * 0.35;
      const eus = o.eus_score ?? 0;
      const rss = o.rss_score ?? 0;
      y = eus * 0.5 + rss * 0.5;
    }

    return {
      ...o,
      x: Number(Math.min(10, Math.max(0, x)).toFixed(1)),
      y: Number(Math.min(10, Math.max(0, y)).toFixed(1)),
    };
  });

  const weightAdjustPreview = useMemo(() => {
    if (!reviewOpp || !scoringWeights) return null;
    const isNew = reviewOpp.contract_id == null || reviewOpp.contract_id === "";
    const preview = previewScoreFromWeights(reviewOpp, scoringWeights, isNew);
    if (!preview) return null;
    const currentTotal = Number(reviewOpp.total_score);
    const delta =
      !Number.isNaN(currentTotal)
        ? Math.round((preview.total - currentTotal) * 100) / 100
        : null;
    return {
      ...preview,
      delta,
      currentTotal: Number.isNaN(currentTotal) ? null : currentTotal,
    };
  }, [reviewOpp, scoringWeights]);

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: Record<string, unknown> }> }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const isNew = isHeatmapNewRequest(data as { request_id?: string; contract_id?: string });
      const total = Number(data.total_score);
      const totalStr = Number.isFinite(total) ? total.toFixed(1) : "—";
      return (
        <div className="bg-white p-3 border border-slate-200 shadow-xl rounded-lg max-w-sm max-h-[min(80vh,480px)] overflow-y-auto">
          <p className="font-bold text-slate-800">{String(data.supplier_name || "New Request")}</p>
          <p className="text-xs text-slate-500 mb-2">{String(data.contract_id || data.request_id || "")}</p>
          <p className="text-[10px] uppercase tracking-wide text-slate-400 mb-1">
            {isNew ? "New request" : "Renewal"} · matrix position
          </p>
          <div className="text-xs text-slate-600 space-y-1 mb-2 font-mono">
            {isNew ? (
              <>
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">IUS (vertical)</span>
                  <span>{formatScore(data.ius_score)}</span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">ES / CSIS (horizontal)</span>
                  <span>
                    {formatScore(data.es_score)} / {formatScore(data.csis_score)}
                  </span>
                </div>
              </>
            ) : (
              <>
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">EUS (time pressure)</span>
                  <span>{formatScore(data.eus_score)}</span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500" title={HEATMAP_GLOSSARY.rss}>
                    RSS (supplier risk)
                  </span>
                  <span>{formatScore(data.rss_score)}</span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-slate-500">FIS / SCS (horizontal)</span>
                  <span>
                    {formatScore(data.fis_score)} / {formatScore(data.scs_score)}
                  </span>
                </div>
              </>
            )}
          </div>
          <div className="flex justify-between items-center mb-2 pt-1 border-t border-slate-100">
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 cursor-help"
              title={HEATMAP_GLOSSARY[TIER_TOOLTIP[String(data.tier)] ?? "tier"]}
            >
              {heatmapTierLabel(String(data.tier))}
            </span>
            <span className="font-bold text-sponsor-blue">{totalStr}/10</span>
          </div>
          <div className="pt-1 border-t border-slate-100">
            <HeatmapScoreBreakdown opportunity={data as HeatmapOpportunityLike} compact />
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-slate-50 min-h-screen relative">
      {reviewSaveNotice && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed top-4 left-1/2 z-[70] max-w-lg w-[calc(100%-2rem)] -translate-x-1/2 rounded-xl border px-4 py-3 shadow-lg flex items-start gap-3 ${
            reviewSaveNotice.kind === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-950"
              : "border-red-200 bg-red-50 text-red-950"
          }`}
        >
          {reviewSaveNotice.kind === "success" ? (
            <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-600 mt-0.5" aria-hidden />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" aria-hidden />
          )}
          <p className="text-sm font-medium leading-snug flex-1 min-w-0">{reviewSaveNotice.message}</p>
          <button
            type="button"
            className="shrink-0 rounded-lg p-1 text-slate-500 hover:bg-black/5 hover:text-slate-800"
            onClick={() => setReviewSaveNotice(null)}
            aria-label="Dismiss notification"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-6 pb-20">
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end mb-6 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Sourcing Priority List</h1>
            <p className="text-slate-500 mt-2 text-sm">
              Ranked pipeline view (heatmap scoring): agentic evaluation of contracts and new requests.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-3 bg-white p-1 rounded-lg border border-slate-200 shadow-sm">
              <button
                onClick={() => setViewMode('table')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'table' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                <List className="w-4 h-4" /> Table
              </button>
              <button
                onClick={() => setViewMode('heatmap')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'heatmap' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:text-slate-700'}`}
              >
                <LayoutGrid className="w-4 h-4" /> Matrix
              </button>
            </div>
            <button
              type="button"
              onClick={() => setProcuraBotOpen(true)}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-slate-200 shadow-sm text-sm font-medium text-slate-700 hover:bg-slate-50"
              title="Open Heatmap ProcuraBot (optional)"
            >
              <MessageCircle className="w-4 h-4 text-sponsor-blue" />
              ProcuraBot
            </button>
          </div>
        </header>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t1">High</HeatmapAbbr> - Immediate
            </h3>
            <p className="text-3xl font-bold text-mit-red">{loading ? "..." : tier1}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-mit-red h-1 rounded-full" style={{width: `${Math.min((tier1 / Math.max(totalMonitored, 1)) * 100, 100)}%`}}></div></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t2">Medium</HeatmapAbbr> - Benchmark
            </h3>
            <p className="text-3xl font-bold text-orange-500">{loading ? "..." : tier2}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-orange-500 h-1 rounded-full" style={{width: `${Math.min((tier2 / Math.max(totalMonitored, 1)) * 100, 100)}%`}}></div></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t3">Low</HeatmapAbbr> - Monitor
            </h3>
            <p className="text-3xl font-bold text-blue-500">{loading ? "..." : tier3}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-blue-500 h-1 rounded-full" style={{width: `${Math.min((tier3 / Math.max(totalMonitored, 1)) * 100, 100)}%`}}></div></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 relative overflow-hidden">
             <div className="absolute -right-4 -top-4 w-24 h-24 bg-sponsor-blue opacity-5 rounded-full"></div>
            <h3 className="text-sm font-medium text-slate-500 mb-1">Total Pipeline Value</h3>
            <p className="text-3xl font-bold text-sponsor-blue">{loading ? "..." : pipelineValueText}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-sponsor-blue h-1 rounded-full w-[72%]"></div></div>
          </div>
        </div>

        {/* Heatmap copilot moved to optional slide-over (opened via header button). */}

        {/* View Router */}
        {viewMode === 'heatmap' ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h2 className="font-semibold text-slate-800 mb-1">Strategic Impact vs Urgency &amp; Risk</h2>
            <p className="text-sm text-slate-600 mb-3 max-w-3xl">
              Each point is one opportunity. Read <span className="font-medium text-slate-700">position</span> as strategic
              story, <span className="font-medium text-slate-700">color</span> as recommended pace (tier), and{" "}
              <span className="font-medium text-slate-700">size</span> as overall numeric priority (0–10).
            </p>
            <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 text-left max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">How to read</p>
              <ul className="space-y-2 list-none pl-0">
                <li className="flex gap-2">
                  <span className="shrink-0 font-mono text-sponsor-blue" aria-hidden>
                    →
                  </span>
                  <span>
                    <span className="font-medium text-slate-800">Horizontal impact.</span> Renewals:{" "}
                    <HeatmapAbbr term="fis">FIS</HeatmapAbbr> + <HeatmapAbbr term="scs">SCS</HeatmapAbbr>. New requests:{" "}
                    <HeatmapAbbr term="es">ES</HeatmapAbbr> + <HeatmapAbbr term="csis">CSIS</HeatmapAbbr>. Farther right = stronger
                    financial / category impact.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="shrink-0 font-mono text-sponsor-blue" aria-hidden>
                    ↑
                  </span>
                  <span>
                    <span className="font-medium text-slate-800">Vertical urgency &amp; risk.</span> Renewals blend{" "}
                    <HeatmapAbbr term="eus">EUS</HeatmapAbbr> (time pressure) and{" "}
                    <HeatmapAbbr term="rss">RSS</HeatmapAbbr> (supplier risk) 50/50 — risk is explicit on this axis. New requests
                    use <HeatmapAbbr term="ius">IUS</HeatmapAbbr> only (implementation urgency). Higher = act sooner.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="shrink-0 text-slate-400" aria-hidden>
                    ○
                  </span>
                  <span>
                    <span className="font-medium text-slate-800">Dot size</span> = total priority score (same idea as table
                    rank drivers). <span className="font-medium text-slate-800">Color</span> = tier (T1 fastest path to engage).
                  </span>
                </li>
              </ul>
              <p className="mt-2 text-xs text-slate-500 leading-relaxed">
                The table is sorted by total score; the chart sorts by two blended axes, so the top-right is not always rank
                #1. Midpoint lines (5) are a visual guide only.
              </p>
            </div>
            <div className="w-full h-[500px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 28, left: 28 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name="Impact"
                    tick={{ fontSize: 12, fill: "#64748b" }}
                    label={{
                      value: "Impact (FIS+SCS / ES+CSIS) →",
                      position: "bottom",
                      fill: "#64748b",
                      fontSize: 12,
                    }}
                    domain={[0, 10]}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name="UrgencyRisk"
                    tick={{ fontSize: 12, fill: "#64748b" }}
                    label={{
                      value: "Urgency & risk (EUS+RSS / IUS) ↑",
                      angle: -90,
                      position: "left",
                      fill: "#64748b",
                      fontSize: 12,
                    }}
                    domain={[0, 10]}
                  />
                  <ReferenceLine
                    x={5}
                    stroke="#cbd5e1"
                    strokeDasharray="4 4"
                    strokeWidth={1}
                    ifOverflow="visible"
                  />
                  <ReferenceLine
                    y={5}
                    stroke="#cbd5e1"
                    strokeDasharray="4 4"
                    strokeWidth={1}
                    ifOverflow="visible"
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter
                    name="Opportunities"
                    data={chartData}
                    shape={HeatmapMatrixScatterDot}
                    onClick={(data) => {
                      void openReviewModal(data.payload);
                    }}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-4 text-xs font-medium text-slate-500">
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t1}>
                <div className="w-3 h-3 rounded-full bg-mit-red opacity-80" />
                High — Immediate
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t2}>
                <div className="w-3 h-3 rounded-full bg-orange-500 opacity-80" />
                Medium — Benchmark
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t3}>
                <div className="w-3 h-3 rounded-full bg-blue-500 opacity-80" />
                Low — Monitor
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t4}>
                <div className="w-3 h-3 rounded-full bg-slate-500 opacity-80" />
                Lowest — Defer
              </span>
            </div>
            <p className="mt-3 text-[11px] text-slate-400 text-center flex flex-wrap justify-center gap-x-1 gap-y-0.5">
              <span title={HEATMAP_GLOSSARY.chartAxisX} className="cursor-help border-b border-dotted border-slate-400">
                X: FIS+SCS / ES+CSIS
              </span>
              <span className="text-slate-300">·</span>
              <span title={HEATMAP_GLOSSARY.chartAxisY} className="cursor-help border-b border-dotted border-slate-400">
                Y: EUS+RSS (renewals) / IUS (new)
              </span>
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div className="flex items-center gap-4">
                <h2 className="font-semibold text-slate-800">Prioritized Opportunities</h2>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleRefreshScores}
                  disabled={pipelineRunning}
                  className="px-4 py-2 bg-white border border-slate-200 shadow-sm rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {pipelineRunning ? "Refreshing..." : "Refresh Scores"}
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200 text-left">
                    <th className="px-6 py-4 font-medium">Supplier / Request</th>
                    <th className="px-6 py-4 font-medium">Category</th>
                    <th className="px-6 py-4 font-medium cursor-help" title={HEATMAP_GLOSSARY.tier}>
                      Priority
                    </th>
                    <th className="px-6 py-4 font-medium cursor-help" title="Component scores (hover each chip below). Renewals: EUS, FIS, RSS, SCS, SAS. New requests: IUS, ES, CSIS, SAS.">
                      Score Breakdown
                    </th>
                    <th className="px-6 py-4 font-medium cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                      Total
                    </th>
                    <th className="px-6 py-4 font-medium align-middle">Review Status</th>
                    <th className="px-6 py-4 font-medium align-middle">Approval Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                        <div className="flex flex-col items-center justify-center">
                          <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-sponsor-blue animate-spin mb-3"></div>
                          <p>Loading scored opportunities from backend...</p>
                        </div>
                      </td>
                    </tr>
                  ) : opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                        No opportunities found in the scoring engine.
                      </td>
                    </tr>
                  ) : (
                    activeOpportunities.map((opp) => {
                      const reviewed = isOpportunityReviewed(opp);
                      const approved = isOpportunityApproved(opp);
                      return (
                        <tr key={opp.id} className="transition-colors hover:bg-slate-50">
                          <td className="px-6 py-4">
                            <div className="font-semibold text-slate-900">{opp.supplier_name || 'New Requirement'}</div>
                            <div className="text-xs text-slate-500 font-mono mt-0.5">{opp.contract_id || opp.request_id}</div>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-600">
                            {opp.category}<br/>
                            <span className="text-xs text-slate-400">{opp.subcategory || 'General'}</span>
                          </td>
                          <td className="px-6 py-4">
                            {opp.tier === 'T1' && (
                              <span title={HEATMAP_GLOSSARY.t1} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-mit-red ring-1 ring-inset ring-red-100 border border-mit-red/20 cursor-help">
                                {heatmapTierLabel(opp.tier)}
                              </span>
                            )}
                            {opp.tier === 'T2' && (
                              <span title={HEATMAP_GLOSSARY.t2} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 ring-1 ring-inset ring-orange-100 border border-orange-200 cursor-help">
                                {heatmapTierLabel(opp.tier)}
                              </span>
                            )}
                            {opp.tier === 'T3' && (
                              <span title={HEATMAP_GLOSSARY.t3} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-sponsor-blue border border-sponsor-blue/20 cursor-help">
                                {heatmapTierLabel(opp.tier)}
                              </span>
                            )}
                            {opp.tier === 'T4' && (
                              <span title={HEATMAP_GLOSSARY.t4} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 cursor-help">
                                {heatmapTierLabel(opp.tier)}
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-1.5 text-[10px] font-mono">
                              {opp.eus_score != null && (
                                <span title={HEATMAP_GLOSSARY.eus} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  EUS:{opp.eus_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.ius_score != null && (
                                <span title={HEATMAP_GLOSSARY.ius} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  IUS:{opp.ius_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.fis_score != null && (
                                <span title={HEATMAP_GLOSSARY.fis} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  FIS:{opp.fis_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.es_score != null && (
                                <span title={HEATMAP_GLOSSARY.es} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  ES:{opp.es_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.rss_score != null && (
                                <span title={HEATMAP_GLOSSARY.rss} className="px-1.5 py-0.5 rounded border border-orange-200 text-orange-700 bg-orange-50 cursor-help">
                                  RSS:{opp.rss_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.scs_score != null && (
                                <span title={HEATMAP_GLOSSARY.scs} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  SCS:{opp.scs_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.sas_score != null && (
                                <span title={HEATMAP_GLOSSARY.sas} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  SAS:{opp.sas_score?.toFixed(1)}
                                </span>
                              )}
                              {opp.csis_score != null && (
                                <span title={HEATMAP_GLOSSARY.csis} className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-600 border border-slate-200 cursor-help">
                                  CSIS:{opp.csis_score?.toFixed(1)}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-lg font-bold text-slate-900 cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                              {opp.total_score?.toFixed(1)}
                              <span className="text-xs text-slate-500 font-normal">/10</span>
                            </div>
                          </td>
                          <td className="px-6 py-4 align-middle">
                            {approved ? (
                              <span className="inline-flex items-center text-xs font-semibold uppercase px-2 py-1 rounded bg-slate-100 text-slate-500 border border-slate-200">
                                Reviewed (Locked)
                              </span>
                            ) : reviewed ? (
                              <button
                                onClick={() => {
                                  void openReviewModal(opp);
                                }}
                                className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-1.5 rounded hover:bg-emerald-100 transition"
                                title="Reviewed — click to view/update review"
                              >
                                Reviewed
                              </button>
                            ) : (
                              <button
                                onClick={() => {
                                  void openReviewModal(opp);
                                }}
                                className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-2.5 py-1.5 rounded hover:bg-amber-100 transition"
                                title="Not reviewed — click to review"
                              >
                                Not Reviewed
                              </button>
                            )}
                          </td>
                          <td className="px-6 py-4 align-middle">
                            {approved ? (
                              <span className="inline-flex items-center text-xs font-semibold uppercase px-2 py-1 rounded bg-green-100 text-green-700 border border-green-200">
                                Approved
                              </span>
                            ) : reviewed ? (
                              <button
                                type="button"
                                onClick={() => {
                                  void handleApproveToExecution(opp);
                                }}
                                className="text-xs font-semibold text-white bg-sponsor-blue px-3 py-1.5 rounded hover:bg-blue-700 transition whitespace-nowrap"
                              >
                                Approve to S2C Execution
                              </button>
                            ) : (
                              <span className="text-xs text-slate-400">Review required</span>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Optional ProcuraBot Slide-over */}
      {copilotOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setProcuraBotOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-2xl flex flex-col transform transition-transform border-l border-slate-200">
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <div className="min-w-0">
                <ProcuraBotIdentity subtitle={`Heatmap workspace · ${PROCURABOT_BRAND.tagline}`} />
                <p className="text-sm text-slate-500 mt-1 leading-relaxed">
                  Optional. Ask how rows are ranked (scores stay as shown), check whether your notes fit category policy,
                  or preview updates to category sourcing rules — nothing here overwrites the heatmap until you apply
                  changes elsewhere.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setProcuraBotOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition bg-white p-2 rounded-full shadow-sm"
                aria-label={`Close ${PROCURABOT_BRAND.name}`}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50/30">
              {/* Quick reference so users can see IDs/names while writing questions */}
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800">Opportunity quick reference</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Search by supplier, contract_id, request_id, or priority (e.g. High or Medium). Click a row to insert its ID into your question.
                    </p>
                  </div>
                  <span className="text-[11px] text-slate-400 shrink-0">{opportunities.length} loaded</span>
                </div>
                <input
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                  value={copilotRefQuery}
                  onChange={(e) => setProcuraBotRefQuery(e.target.value)}
                  placeholder='e.g. "TechGlobal", "REQ-", "High", "Medium", "contract"'
                />
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2 font-semibold text-slate-600">Supplier / Request</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">Priority</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {opportunities
                        .filter((o) => {
                          const q = copilotRefQuery.trim().toLowerCase();
                          if (!q) return true;
                          const hay = [
                            o.supplier_name,
                            o.contract_id,
                            o.request_id,
                            o.tier,
                            heatmapTierLabel(o.tier),
                            o.category,
                            o.subcategory,
                          ]
                            .filter(Boolean)
                            .join(" ")
                            .toLowerCase();
                          return hay.includes(q);
                        })
                        .slice(0, 12)
                        .map((o) => (
                          <tr
                            key={`copilot-ref-${o.id}`}
                            className="hover:bg-slate-50 cursor-pointer"
                            onClick={() => {
                              const tag = o.id != null ? `id=${o.id}` : (o.contract_id ? `contract_id=${o.contract_id}` : (o.request_id ? `request_id=${o.request_id}` : ""));
                              if (!tag) return;
                              setProcuraBotTab("qa");
                              setQaQuestion((prev) => {
                                const base = prev.trim();
                                return base ? `${base}\n\n${tag}` : tag;
                              });
                            }}
                            title="Click to insert id into Q&A"
                          >
                            <td className="px-3 py-2">
                              <div className="font-medium text-slate-800 truncate max-w-[340px]">
                                {o.supplier_name || "New Sourcing Request"}
                              </div>
                              <div className="font-mono text-[10px] text-slate-400">
                                {o.contract_id || o.request_id || `id=${o.id}`}
                              </div>
                            </td>
                            <td className="px-3 py-2">
                              <span
                                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                  o.tier === "T1"
                                    ? "bg-red-100 text-mit-red"
                                    : o.tier === "T2"
                                      ? "bg-orange-100 text-orange-700"
                                      : o.tier === "T3"
                                        ? "bg-blue-100 text-blue-700"
                                        : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {heatmapTierLabel(o.tier)}
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono text-slate-700">{Number(o.total_score || 0).toFixed(2)}</td>
                          </tr>
                        ))}
                      {opportunities.length === 0 && (
                        <tr>
                          <td className="px-3 py-3 text-slate-500" colSpan={3}>
                            No opportunities loaded yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs font-medium shrink-0 bg-white w-fit">
                {(
                  [
                    ["qa", "Q&A"],
                    ["policy", "Policy"],
                    ["cards", "Cards"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setProcuraBotTab(key)}
                    className={`px-3 py-2 transition ${
                      copilotTab === key ? "bg-sponsor-blue text-white" : "bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {copilotTab === "qa" && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
                  <label className="block text-sm font-medium text-slate-700">
                    Question <span className="text-slate-400 font-normal">(e.g. Why is supplier A above B?)</span>
                  </label>
                  <textarea
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm min-h-[96px] focus:ring-2 focus:ring-sponsor-blue/20"
                    placeholder="Use names or IDs from the table. Answers use current DB rows + feedback; no rescoring."
                    value={qaQuestion}
                    onChange={(e) => setQaQuestion(e.target.value)}
                  />
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => void submitHeatmapQA()}
                      disabled={qaLoading || qaQuestion.trim().length < 3}
                      className="px-4 py-2 bg-sponsor-blue text-white rounded-lg text-sm font-medium disabled:opacity-50"
                    >
                      {qaLoading ? "Thinking…" : "Explain"}
                    </button>
                    {qaUsedLlm && qaAnswer && (
                      <span className="text-xs text-emerald-700">LLM explanation (grounded on context below)</span>
                    )}
                    {!qaUsedLlm && qaAnswer && (
                      <span className="text-xs text-amber-700">Showing context only or offline mode</span>
                    )}
                  </div>
                  {qaAnswer && (
                    <div className="space-y-3">
                      <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 text-sm text-slate-800 leading-relaxed">
                        {parseSimpleMarkdown(qaAnswer)}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/90 px-3 py-2">
                        <span className="text-xs font-medium text-slate-500">Rate this response</span>
                        <button
                          type="button"
                          disabled={qaVoteLoading}
                          onClick={() => void submitQaVote("up")}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                            qaVote === "up"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-300 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:border-emerald-200 hover:text-emerald-700"
                          } disabled:opacity-50`}
                        >
                          <ThumbsUp className="w-3.5 h-3.5" />
                          Useful
                        </button>
                        <button
                          type="button"
                          disabled={qaVoteLoading}
                          onClick={() => void submitQaVote("down")}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                            qaVote === "down"
                              ? "bg-rose-50 text-rose-700 border-rose-300 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:border-rose-200 hover:text-rose-700"
                          } disabled:opacity-50`}
                        >
                          <ThumbsDown className="w-3.5 h-3.5" />
                          Needs work
                        </button>
                        {qaVoteNotice && (
                          <span className="text-xs text-slate-500">{qaVoteNotice}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {copilotTab === "policy" && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-4">
                  <div className="space-y-2 text-xs leading-relaxed">
                    <p className="text-slate-600">
                      <strong className="text-slate-800">What this does:</strong> Paste reviewer or sourcing rationale and see whether
                      the wording aligns with this category’s official preferred-supplier rules in{" "}
                      <code className="text-slate-700">category_cards.json</code>. Useful before you publish notes, escalate, or file
                      audit text—so narrative matches the policy the heatmap uses.
                    </p>
                    <p className="font-medium text-slate-700">How to use it</p>
                    <ol className="list-decimal list-inside space-y-1 text-slate-600">
                      <li>
                        Choose the <strong className="font-medium text-slate-700">category</strong> whose policy block should be used.
                      </li>
                      <li>
                        Optionally add <strong className="font-medium text-slate-700">supplier</strong> and{" "}
                        <strong className="font-medium text-slate-700">current priority</strong> (e.g. Medium) so the check can use
                        that context.
                      </li>
                      <li>
                        Paste the full <strong className="font-medium text-slate-700">feedback or rationale</strong> (at least a short paragraph; very short snippets are rejected).
                      </li>
                      <li>
                        Click <strong className="font-medium text-slate-700">Check vs policy</strong> and read the summary. Treat the output as a draft review aid, not a formal decision.
                      </li>
                    </ol>
                    <p className="text-slate-500">
                      <strong className="text-slate-600">Suggestion only</strong> — does not change scores, priority bands, or any files. Full
                      analysis needs <code className="text-slate-600">OPENAI_API_KEY</code> on the server; if it’s missing, you’ll see a
                      message that automatic checks aren’t available.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">Category</label>
                      <select
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        value={policyCategory}
                        onChange={(e) => setPolicyCategory(e.target.value)}
                      >
                        {cardCategories.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">Supplier (optional)</label>
                      <input
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        value={policySupplier}
                        onChange={(e) => setPolicySupplier(e.target.value)}
                        placeholder="e.g. CloudServe Group"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">Current priority (optional)</label>
                      <input
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        value={policyTier}
                        onChange={(e) => setPolicyTier(e.target.value)}
                        placeholder="e.g. Medium"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Feedback / rationale text</label>
                    <textarea
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm min-h-[110px]"
                      value={policyText}
                      onChange={(e) => setPolicyText(e.target.value)}
                      placeholder="Paste reviewer rationale to check against preferred-supplier policy…"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => void submitPolicyCheck()}
                    disabled={policyLoading || policyText.trim().length < 5}
                    className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                  >
                    {policyLoading ? "Checking…" : "Check vs policy"}
                  </button>
                  {policyResult && (
                    <div
                      className={`rounded-lg border p-4 text-sm ${
                        policyResult.contradicts ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50/80"
                      }`}
                    >
                      <p className="font-semibold text-slate-800">
                        {policyResult.contradicts ? "Possible misalignment" : "Alignment check"}
                        {policyResult.severity && policyResult.severity !== "none" ? (
                          <span className="font-normal text-slate-500"> — {policyResult.severity}</span>
                        ) : null}
                      </p>
                      {policyResult.summary && <p className="mt-2 text-slate-700">{policyResult.summary}</p>}
                      {policyResult.suggestion ? (
                        <p className="mt-2 text-slate-600">
                          <span className="font-medium">Suggestion:</span> {policyResult.suggestion}
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              )}

              {copilotTab === "cards" && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Upload a policy document (plain text) or describe changes below. The system extracts a structured patch into{" "}
                    <code className="text-slate-600">data/heatmap/category_cards.json</code>, then you can{" "}
                    <strong>apply and re-run scoring</strong>. That file holds preferred-supplier rules and optional{" "}
                    <strong>scoring_mix</strong> (human-readable weight labels per category for new requests vs renewals — see{" "}
                    <code className="text-slate-600">_documentation</code> at the top of the JSON).
                  </p>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Category</label>
                    <select
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm max-w-md"
                      value={assistCategory}
                      onChange={(e) => setAssistCategory(e.target.value)}
                    >
                      {cardCategories.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Upload policy (.txt / paste into a file)</label>
                    <input
                      type="file"
                      accept=".txt,text/plain"
                      onChange={(e) => void onPolicyFileSelected(e)}
                      disabled={uploadLoading}
                      className="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-slate-100 file:text-slate-700"
                    />
                    {uploadLoading && <p className="text-xs text-slate-500 mt-1">Reading file…</p>}
                    {uploadExtract?.filename && (
                      <p className="text-xs text-slate-600 mt-1">Read: {uploadExtract.filename}</p>
                    )}
                    {uploadExtract?.notes && !uploadExtract.proposed_patch && (
                      <p className="text-xs text-amber-800 mt-2">{uploadExtract.notes}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Or: what to change (LLM assist)</label>
                    <textarea
                      className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm min-h-[110px]"
                      value={assistInstruction}
                      onChange={(e) => setAssistInstruction(e.target.value)}
                      placeholder="e.g. Add Acme Corp as preferred in Software and set default to allowed…"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => void submitAssistCategory()}
                    disabled={assistLoading || assistInstruction.trim().length < 10}
                    className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                  >
                    {assistLoading ? "Drafting…" : "Suggest patch (LLM)"}
                  </button>
                  {assistResult && (assistResult.proposed_patch || assistResult.notes) && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2 text-sm">
                      {assistResult.notes && <p className="text-slate-700">{assistResult.notes}</p>}
                      {assistResult.proposed_patch && Object.keys(assistResult.proposed_patch).length > 0 && (
                        <pre className="text-xs bg-slate-900 text-slate-100 rounded p-3 overflow-x-auto">
                          {JSON.stringify(assistResult.proposed_patch, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                  {uploadExtract?.proposed_patch && Object.keys(uploadExtract.proposed_patch).length > 0 && (
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 space-y-2 text-sm">
                      <p className="font-medium text-emerald-900">Extracted from upload</p>
                      <pre className="text-xs bg-slate-900 text-slate-100 rounded p-3 overflow-x-auto">
                        {JSON.stringify(uploadExtract.proposed_patch, null, 2)}
                      </pre>
                    </div>
                  )}
                  {pendingPatch && Object.keys(pendingPatch).length > 0 && (
                    <div className="rounded-lg border border-sponsor-blue/30 bg-slate-50 p-4 space-y-3">
                      <p className="text-sm font-medium text-slate-800">Pending patch (applies to category: {assistCategory})</p>
                      <pre className="text-xs bg-slate-900 text-slate-100 rounded p-3 overflow-x-auto max-h-40">
                        {JSON.stringify(pendingPatch, null, 2)}
                      </pre>
                      <button
                        type="button"
                        onClick={() => void applyPatchAndRescore()}
                        disabled={applyLoading}
                        className="px-4 py-2 bg-sponsor-blue text-white rounded-lg text-sm font-medium disabled:opacity-50"
                      >
                        {applyLoading ? "Applying…" : "Apply patch & re-score opportunities"}
                      </button>
                      <p className="text-xs text-slate-500">
                        Writes to <code className="text-slate-600">category_cards.json</code> and starts the batch pipeline. Intake previews pick up changes immediately; batch rows refresh after the run completes.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Slide-over Feedback Modal - Rich Case Details Style */}
      {reviewOpp && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity" onClick={() => setReviewOpp(null)} />
          <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-2xl flex flex-col transform transition-transform border-l border-slate-200">
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <div>
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">Opportunity Review</h2>
                <p className="text-sm text-slate-500 mt-1">Review AI analysis and provide human-in-the-loop feedback</p>
              </div>
              <button onClick={() => setReviewOpp(null)} className="text-slate-400 hover:text-slate-600 transition bg-white p-2 rounded-full shadow-sm">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-slate-50/30">
              
              {/* Header: identity + single clear score (no raw formula) */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:justify-between sm:items-start gap-6">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Opportunity</p>
                  <p className="text-2xl font-bold text-slate-900 tracking-tight">{reviewOpp.supplier_name || "New Requirement"}</p>
                  <p className="text-sm font-mono text-slate-500 mt-1">{reviewOpp.contract_id || reviewOpp.request_id}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="px-2.5 py-1 bg-slate-100 rounded-md text-xs font-medium text-slate-700 border border-slate-200">
                      {reviewOpp.category}
                    </span>
                    <span className="px-2.5 py-1 bg-slate-100 rounded-md text-xs font-medium text-slate-700 border border-slate-200">
                      {reviewOpp.subcategory || "General"}
                    </span>
                  </div>
                </div>
                <div className="flex sm:flex-col items-center sm:items-end gap-3 sm:gap-2 sm:text-right w-full sm:w-auto">
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide cursor-help border ${
                      reviewOpp.tier === "T1"
                        ? "bg-red-50 text-mit-red border-red-200"
                        : reviewOpp.tier === "T2"
                          ? "bg-orange-50 text-orange-800 border-orange-200"
                          : reviewOpp.tier === "T3"
                            ? "bg-blue-50 text-blue-800 border-blue-200"
                            : "bg-slate-100 text-slate-600 border-slate-200"
                    }`}
                    title={HEATMAP_GLOSSARY[TIER_TOOLTIP[reviewOpp.tier] ?? "tier"]}
                  >
                    {heatmapTierLabel(reviewOpp.tier)}
                  </span>
                  <div>
                    <p className="text-xs font-medium text-slate-500 cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                      Priority score
                    </p>
                    <p className="text-4xl font-black text-sponsor-blue tracking-tight tabular-nums cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                      {reviewOpp.total_score?.toFixed(1)}
                      <span className="text-lg font-semibold text-slate-400">/10</span>
                    </p>
                    <p className="text-xs text-slate-500 mt-1 max-w-[14rem] sm:ml-auto sm:text-right">{reviewOpp.recommended_action_window}</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-gradient-to-b from-slate-50/90 to-white p-6 shadow-sm">
                <p className="text-base font-semibold text-slate-900 mb-1">What drove this score</p>
                <p className="text-xs text-slate-500 mb-5">Bars show strength (0–10); points show how much each metric added to the total.</p>
                <HeatmapScoreBreakdown opportunity={reviewOpp as HeatmapOpportunityLike} />
              </div>

              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-slate-50 to-slate-100 rounded-bl-full border-l border-b border-slate-100"></div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2 relative z-10">Supporting Artifacts</p>
                  <ul className="space-y-3 relative z-10">
                    <li className="flex items-center gap-3 text-sm text-slate-700 hover:text-sponsor-blue cursor-pointer transition">
                      <div className="w-8 h-8 rounded bg-red-50 text-red-500 flex items-center justify-center font-bold text-xs">PDF</div>
                      <span className="underline decoration-slate-200 underline-offset-2">Master_Agreement_2021.pdf</span>
                    </li>
                    <li className="flex items-center gap-3 text-sm text-slate-700 hover:text-sponsor-blue cursor-pointer transition">
                      <div className="w-8 h-8 rounded bg-green-50 text-green-600 flex items-center justify-center font-bold text-xs">XLSX</div>
                      <span className="underline decoration-slate-200 underline-offset-2">PO_Spend_History_12M.xlsx</span>
                    </li>
                    <li className="flex items-center gap-3 text-sm text-slate-700 hover:text-sponsor-blue cursor-pointer transition">
                      <div className="w-8 h-8 rounded bg-blue-50 text-blue-600 flex items-center justify-center font-bold text-xs">DOC</div>
                      <span className="underline decoration-slate-200 underline-offset-2">Supplier_QBR_Notes.docx</span>
                    </li>
                  </ul>
              </div>

              {/* Human Feedback Section + History */}
              <div className="space-y-4">
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                  <p className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-3 mb-5 flex items-center gap-2">
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                    Human-in-the-Loop Override
                  </p>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:border-r lg:border-slate-100 lg:pr-6">
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Adjust Priority</label>
                      <select 
                        className="w-full border border-slate-300 rounded-lg shadow-sm py-2.5 px-3 text-sm focus:ring-2 focus:ring-sponsor-blue/20 focus:border-sponsor-blue font-medium bg-slate-50 cursor-pointer"
                        value={feedbackTier} 
                        onChange={(e) => setFeedbackTier(e.target.value)}
                      >
                        <option value="T1">High — Immediate</option>
                        <option value="T2">Medium — Benchmark</option>
                        <option value="T3">Low — Monitor</option>
                        <option value="T4">Lowest — Defer</option>
                      </select>
                    </div>
                    <div className="lg:col-span-2 space-y-4">
                      <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">
                          Rationale & Next Steps
                        </label>
                        <p className="text-xs text-slate-500 mb-3">
                          Why does this row deserve a different priority than the scored rank? Options align with{" "}
                          <strong className="text-slate-600">PS_new</strong> (IUS, ES, CSIS, SAS) and{" "}
                          <strong className="text-slate-600">PS_contract</strong> (EUS, FIS, RSS, SCS, SAS). Select all that
                          apply.
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2.5 mb-1">
                          {PRIORITY_OVERRIDE_REASONS.map((r) => (
                            <label
                              key={r.id}
                              className="flex items-start gap-2.5 text-sm text-slate-700 cursor-pointer leading-snug"
                            >
                              <input
                                type="checkbox"
                                className="mt-0.5 rounded border-slate-300 text-sponsor-blue focus:ring-sponsor-blue shrink-0"
                                checked={feedbackReasonKeys.includes(r.id)}
                                onChange={() => {
                                  setFeedbackReasonKeys((prev) =>
                                    prev.includes(r.id) ? prev.filter((k) => k !== r.id) : [...prev, r.id]
                                  );
                                }}
                              />
                              <span>{r.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5">Additional notes</label>
                        <textarea 
                          className="w-full border border-slate-300 rounded-lg shadow-sm py-3 px-4 text-sm focus:ring-2 focus:ring-sponsor-blue/20 focus:border-sponsor-blue min-h-[96px] placeholder-slate-400 bg-slate-50"
                          placeholder={
                            feedbackReasonKeys.includes("other")
                              ? "Describe the “other” reason (required when Others is checked)…"
                              : "Optional: stakeholders, timing, links to incidents, or next steps…"
                          }
                          value={feedbackReason}
                          onChange={(e) => setFeedbackReason(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {scoringWeights && reviewOpp && (
                  <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                    <p className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-3 mb-2">
                      Scoring weights (global average — like connection weights)
                    </p>
                    <p className="text-xs text-slate-500 mb-4">
                      Adjust the mix for{" "}
                      {reviewOpp.contract_id == null || reviewOpp.contract_id === ""
                        ? "new requests (PS_new)"
                        : "renewals (PS_contract)"}
                      . Values renormalize to 100%. Your priority choice still applies a small learning nudge toward that band.
                    </p>
                    <p className="text-[11px] text-slate-600 mb-3 flex items-center gap-2">
                      <span className="inline-flex items-center gap-1.5 shrink-0">
                        <span className="w-2 h-2 rounded-full bg-red-600 ring-2 ring-white shadow shrink-0" />
                        <span className="border-l-2 border-dotted border-red-500 h-3 inline-block w-0 align-middle" />
                      </span>
                      <span>
                        Red dot and dotted line = <strong className="text-slate-700">global average</strong> weight when this panel
                        opened (anchor). Numbers on the right show percentage points vs that average after renormalization.
                      </span>
                    </p>
                    <div className="space-y-3">
                      {(reviewOpp.contract_id == null || reviewOpp.contract_id === ""
                        ? PS_NEW_WEIGHT_KEYS
                        : PS_CONTRACT_WEIGHT_KEYS
                      ).map((k) => {
                        const cur = scoringWeights[k] ?? 0;
                        const base = baselineScoringWeights?.[k];
                        const deltaPp = base != null ? Math.round((cur - base) * 1000) / 10 : null;
                        const anchorLeftPct = base != null ? weightToSliderTrackPercent(base) : null;
                        return (
                          <div key={k}>
                            <div className="flex justify-between text-xs font-medium text-slate-600 mb-1 gap-2">
                              <span className="min-w-0">{WEIGHT_LABELS[k] ?? k}</span>
                              <span className="text-right shrink-0 leading-tight">
                                <span className="text-slate-800">{(cur * 100).toFixed(1)}%</span>
                                {deltaPp != null && (
                                  <span
                                    className={`ml-1.5 block text-[10px] font-semibold sm:inline sm:ml-1.5 ${
                                      Math.abs(deltaPp) < 0.05
                                        ? "text-slate-400"
                                        : deltaPp > 0
                                          ? "text-red-600"
                                          : "text-emerald-700"
                                    }`}
                                    title="Difference vs global average for this factor (percentage points)"
                                  >
                                    {Math.abs(deltaPp) < 0.05
                                      ? "at avg"
                                      : `${deltaPp > 0 ? "+" : ""}${deltaPp.toFixed(1)} pp vs avg`}
                                  </span>
                                )}
                              </span>
                            </div>
                            <div className="relative w-full h-8 flex items-center">
                              {anchorLeftPct != null && (
                                <div
                                  className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 h-6 z-10"
                                  aria-hidden
                                >
                                  <div
                                    className="absolute top-0 bottom-0 -translate-x-1/2 flex flex-col items-center"
                                    style={{ left: `${anchorLeftPct}%` }}
                                    title={`Global average: ${((base ?? 0) * 100).toFixed(1)}%`}
                                  >
                                    <span className="w-2 h-2 rounded-full bg-red-600 border-2 border-white shadow shrink-0 z-20" />
                                    <span className="w-0 flex-1 min-h-[10px] border-l-2 border-dotted border-red-600 opacity-90" />
                                  </div>
                                </div>
                              )}
                              <input
                                type="range"
                                min={1}
                                max={99}
                                step={1}
                                value={Math.min(99, Math.max(1, Math.round((scoringWeights[k] ?? 0.2) * 100)))}
                                onChange={(e) => {
                                  const v = Number(e.target.value) / 100;
                                  const keys =
                                    reviewOpp.contract_id == null || reviewOpp.contract_id === ""
                                      ? PS_NEW_WEIGHT_KEYS
                                      : PS_CONTRACT_WEIGHT_KEYS;
                                  setScoringWeights((prev) => {
                                    if (!prev) return prev;
                                    return normalizeWeightGroup({ ...prev, [k]: v }, keys);
                                  });
                                }}
                                className="relative z-20 w-full accent-[#2563eb]"
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {weightAdjustPreview && (
                      <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50/90 p-4">
                        <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-900 mb-2">
                          Preview before save (weighted formula)
                        </p>
                        <p className="text-sm text-slate-800">
                          With the sliders above and the component scores in this modal, the linear score would be about{" "}
                          <strong className="text-indigo-900">{weightAdjustPreview.total.toFixed(2)}</strong>
                          /10 → math band{" "}
                          <strong>
                            {heatmapTierLabel(weightAdjustPreview.mathTier)}
                          </strong>
                        </p>
                        {weightAdjustPreview.currentTotal != null && (
                          <p className="text-xs text-slate-600 mt-2">
                            Current row total: {weightAdjustPreview.currentTotal.toFixed(2)}/10
                            {weightAdjustPreview.delta != null && (
                              <>
                                {" "}
                                (
                                {weightAdjustPreview.delta > 0 ? "+" : ""}
                                {weightAdjustPreview.delta.toFixed(2)} vs current)
                              </>
                            )}
                          </p>
                        )}
                        <p className="text-[11px] text-slate-500 mt-3 leading-snug">
                          This does not include category policy weights from{" "}
                          <code className="text-[10px] bg-white/80 px-1 rounded">category_cards.json</code> or the
                          feedback-memory learning nudge — those can shift the stored total after save. The priority you pick
                          below is still recorded as your decision.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">
                    Feedback History
                  </p>
                  {feedbackHistoryLoading && (
                    <p className="text-xs text-slate-500">Loading prior reviews…</p>
                  )}
                  {!feedbackHistoryLoading && (feedbackHistory == null || feedbackHistory.length === 0) && (
                    <p className="text-xs text-slate-400">
                      No prior feedback logged for this opportunity yet. Your review will become the first audit entry.
                    </p>
                  )}
                  {!feedbackHistoryLoading && feedbackHistory && feedbackHistory.length > 0 && (
                    <ul className="space-y-3 text-xs text-slate-600 max-h-56 overflow-y-auto pr-1">
                      {feedbackHistory.map((fb) => (
                        <li key={fb.id} className="border-b border-slate-100 pb-2 last:border-b-0 last:pb-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold">{fb.reviewer_id}</span>
                            <span className="text-[10px] text-slate-400">
                              {new Date(fb.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <div className="mt-0.5 text-[11px] text-slate-500">
                            {fb.component_affected} · {fb.adjustment_type} {fb.adjustment_value}
                          </div>
                          {fb.reason_code && (
                            <div className="mt-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                              {fb.reason_code}
                            </div>
                          )}
                          {fb.comment_text && (
                            <p className="mt-1 text-[11px] text-slate-600 line-clamp-3">
                              “{fb.comment_text}”
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-slate-200 bg-white flex gap-4">
              <button 
                onClick={() => setReviewOpp(null)}
                className="flex-1 px-4 py-3 border-2 border-slate-200 text-slate-700 bg-white rounded-lg font-bold text-sm hover:bg-slate-50 hover:border-slate-300 transition"
              >
                Cancel Evaluation
              </button>
              <button 
                onClick={submitFeedback}
                disabled={feedbackSubmitting}
                className="flex-[2] px-4 py-3 bg-sponsor-blue text-white rounded-lg font-bold text-sm hover:bg-blue-700 transition shadow-lg disabled:opacity-50"
              >
                {feedbackSubmitting ? 'Saving Review and Applying Decision...' : 'Save Review and Apply Decision'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
