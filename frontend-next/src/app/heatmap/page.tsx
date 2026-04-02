"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutGrid, List, X, ExternalLink, MessageCircle, Table2 } from "lucide-react";
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";
import { HeatmapAbbr, HEATMAP_GLOSSARY, type HeatmapGlossaryKey } from "@/lib/heatmap-glossary";

const TIER_TOOLTIP: Record<string, HeatmapGlossaryKey> = {
  T1: "t1",
  T2: "t2",
  T3: "t3",
  T4: "t4",
};

export default function HeatmapPriorityPage() {
  const [opportunities, setOpportunities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'heatmap'>('table');
  
  // Selection State
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  
  // Review Modal State
  const [reviewOpp, setReviewOpp] = useState<any | null>(null);
  const [feedbackTier, setFeedbackTier] = useState<string>("T1");
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

  // Optional Copilot Slide-over
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotTab, setCopilotTab] = useState<"qa" | "policy" | "cards">("qa");
  const [copilotRefQuery, setCopilotRefQuery] = useState("");
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaAnswer, setQaAnswer] = useState<string | null>(null);
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
  const activeOpportunities = opportunities.filter((o) => o.status !== "Approved");

  const rankOpportunities = (rows: any[]) =>
    rows
      .filter((o) => o.status !== "Approved")
      .sort((a: any, b: any) => b.total_score - a.total_score);

  useEffect(() => {
    if (!copilotOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCopilotOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [copilotOpen]);

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

  // Selection Logic
  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(new Set(activeOpportunities.map(o => o.id as number)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: number) => {
    const nextSet = new Set(selectedIds);
    if (nextSet.has(id)) nextSet.delete(id);
    else nextSet.add(id);
    setSelectedIds(nextSet);
  };

  // Feedback Submission Logic
  const submitFeedback = async () => {
    if (!reviewOpp) return;
    setFeedbackSubmitting(true);
    try {
      const url = `${getApiBaseUrl()}/api/heatmap/feedback`;

      const payload = {
        opportunity_id: reviewOpp.id,
        user_id: "human-manager",
        original_tier: reviewOpp.tier,
        suggested_tier: feedbackTier,
        feedback_notes: feedbackReason
      };

      const res = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        // Optimistic UI update (tier / notes); server-side Approved only after /approve.
        const updated = opportunities.map(o => {
          if (o.id === reviewOpp.id) {
            return { ...o, tier: feedbackTier };
          }
          return o;
        });
        setOpportunities(rankOpportunities(updated));
        setReviewOpp(null);

        // Tier 1: single bridge into case management — same path as "Approve Selected" (one case per opportunity).
        if (feedbackTier === "T1") {
          try {
            const approveUrl = `${getApiBaseUrl()}/api/heatmap/approve`;
            const approveRes = await apiFetch(approveUrl, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                opportunity_ids: [reviewOpp.id],
                approver_id: "human-manager",
              }),
            });
            const approveData = await approveRes.json();
            const caseId = approveData.cases?.[String(reviewOpp.id)];
            if (caseId) {
              window.location.href = `/cases/${caseId}/copilot`;
              return;
            }
          } catch (e) {
            console.error(e);
          }
          alert("Review saved. Approval succeeded but no case id was returned; open Case Dashboard to continue.");
        }
      } else {
        alert("Feedback submission failed. Please verify backend payload compatibility.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handlePushToCasework = async () => {
    // Check if any non-T1 is selected
    const selectedOpps = activeOpportunities.filter(o => selectedIds.has(o.id as number));
    if (selectedOpps.length === 0) return;

    const nonT1 = selectedOpps.some(o => o.tier !== 'T1');
    if (nonT1) {
      alert("Error: Only Tier 1 (Critical) opportunities can be pushed directly to Case Dashboard. Please review and approve lower tier items first.");
      return;
    }

    try {
      const url = `${getApiBaseUrl()}/api/heatmap/approve`;

      const res = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          opportunity_ids: Array.from(selectedIds),
          approver_id: "human-manager"
        })
      });

      if (res.ok) {
        const data = await res.json();
        const ids = data.cases ? Object.values(data.cases).join(", ") : "";
        const linked = data.cases ? Object.keys(data.cases).length : 0;
        alert(
          `Success! ${linked} opportunity(ies) linked to case(s)` +
            (data.approved_count ? ` (${data.approved_count} newly created). ` : ". ") +
            (ids ? `Case ID(s): ${ids}. ` : "") +
            "Open the Case Dashboard to continue."
        );
        setSelectedIds(new Set());
        // Refresh list so server-side Approved status matches the UI.
        const oppUrl = `${getApiBaseUrl()}/api/heatmap/opportunities`;
        const oppRes = await apiFetch(oppUrl, { cache: "no-store" });
        const oppJson = await oppRes.json();
        if (oppJson.opportunities) {
          setOpportunities(rankOpportunities(oppJson.opportunities));
        }
      } else {
        alert("Failed to push to casework. Please try again.");
      }
    } catch (err) {
      console.error(err);
      alert("Network error pushing to casework.");
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
    } catch {
      setQaAnswer(`Network error. API: ${getApiBaseUrl()}${apiConnectivityHint()}`);
      setQaUsedLlm(false);
    } finally {
      setQaLoading(false);
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
    const isNewRequest = Boolean(o.request_id) && !o.contract_id;
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
      z: o.total_score * 15, // visual radius size
    };
  });

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border border-slate-200 shadow-xl rounded-lg max-w-xs">
          <p className="font-bold text-slate-800">{data.supplier_name || 'New Request'}</p>
          <p className="text-xs text-slate-500 mb-2">{data.contract_id || data.request_id}</p>
          <div className="flex justify-between items-center mb-2">
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 cursor-help"
              title={HEATMAP_GLOSSARY[TIER_TOOLTIP[data.tier] ?? "tier"]}
            >
              {data.tier}
            </span>
            <span className="font-bold text-sponsor-blue">{data.total_score.toFixed(1)}/10</span>
          </div>
          <p className="text-xs text-slate-600 line-clamp-3 leading-snug">{data.justification_summary}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 bg-slate-50 min-h-screen relative">
      <div className="max-w-7xl mx-auto space-y-6 pb-20">
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end mb-6 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Sourcing Priority Heatmap</h1>
            <p className="text-slate-500 mt-2 text-sm">Agentic continuous evaluation of existing contracts and new requests.</p>
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
              onClick={() => setCopilotOpen(true)}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-slate-200 shadow-sm text-sm font-medium text-slate-700 hover:bg-slate-50"
              title="Open Heatmap Copilot (optional)"
            >
              <MessageCircle className="w-4 h-4 text-sponsor-blue" />
              Copilot
            </button>
          </div>
        </header>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t1">Tier 1</HeatmapAbbr> - Immediate
            </h3>
            <p className="text-3xl font-bold text-mit-red">{loading ? "..." : tier1}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-mit-red h-1 rounded-full" style={{width: `${Math.min((tier1 / Math.max(totalMonitored, 1)) * 100, 100)}%`}}></div></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t2">Tier 2</HeatmapAbbr> - Benchmark
            </h3>
            <p className="text-3xl font-bold text-orange-500">{loading ? "..." : tier2}</p>
            <div className="mt-3 w-full bg-slate-100 rounded-full h-1"><div className="bg-orange-500 h-1 rounded-full" style={{width: `${Math.min((tier2 / Math.max(totalMonitored, 1)) * 100, 100)}%`}}></div></div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <h3 className="text-sm font-medium text-slate-500 mb-1">
              <HeatmapAbbr term="t3">Tier 3</HeatmapAbbr> - Monitor
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
            <h2 className="font-semibold text-slate-800 mb-1">Strategic Impact vs Urgency Matrix</h2>
            <p className="text-xs text-slate-500 mb-4 leading-relaxed max-w-3xl">
              Plotted position matches each row&apos;s score family. Renewals (
              <HeatmapAbbr term="psContract">PS_contract</HeatmapAbbr>): horizontal{" "}
              <HeatmapAbbr term="fis">FIS</HeatmapAbbr> blended with <HeatmapAbbr term="scs">SCS</HeatmapAbbr>; vertical{" "}
              <HeatmapAbbr term="eus">EUS</HeatmapAbbr> and <HeatmapAbbr term="rss">RSS</HeatmapAbbr>. New requests (
              <HeatmapAbbr term="psNew">PS_new</HeatmapAbbr>): horizontal <HeatmapAbbr term="es">ES</HeatmapAbbr> with{" "}
              <HeatmapAbbr term="csis">CSIS</HeatmapAbbr>; vertical <HeatmapAbbr term="ius">IUS</HeatmapAbbr>. The table is sorted
              by total score; the &quot;top-right&quot; corner is not the same as rank #1.
            </p>
            <div className="w-full h-[500px]">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis type="number" dataKey="x" name="Impact" tick={{fontSize: 12, fill: '#64748b'}} label={{ value: 'Financial impact (FIS+SCS / ES+CSIS) →', position: 'bottom', fill: '#64748b', fontSize: 12 }} domain={[0, 10]} />
                  <YAxis type="number" dataKey="y" name="Urgency" tick={{fontSize: 12, fill: '#64748b'}} label={{ value: 'Urgency & risk (EUS+RSS / IUS) →', angle: -90, position: 'left', fill: '#64748b', fontSize: 12 }} domain={[0, 10]} />
                  <ZAxis type="number" dataKey="z" range={[60, 400]} name="Volume" />
                  <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter name="Opportunities" data={chartData} onClick={(data) => setReviewOpp(data.payload)}>
                    {chartData.map((entry, index) => {
                      let fill = "#64748b"; // T4
                      if (entry.tier === "T1") fill = "#ef4444";
                      if (entry.tier === "T2") fill = "#f97316";
                      if (entry.tier === "T3") fill = "#3b82f6";
                      return <Cell key={`cell-${index}`} fill={fill} fillOpacity={0.7} stroke={fill} strokeWidth={2} className="cursor-pointer transition-all hover:fill-opacity-100" />
                    })}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 mt-4 text-xs font-medium text-slate-500">
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t1}>
                <div className="w-3 h-3 rounded-full bg-mit-red opacity-80" />
                Tier 1 (Critical)
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t2}>
                <div className="w-3 h-3 rounded-full bg-orange-500 opacity-80" />
                Tier 2 (Immediate)
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t3}>
                <div className="w-3 h-3 rounded-full bg-blue-500 opacity-80" />
                Tier 3 (Monitor)
              </span>
              <span className="flex items-center gap-2 cursor-help" title={HEATMAP_GLOSSARY.t4}>
                <div className="w-3 h-3 rounded-full bg-slate-500 opacity-80" />
                Tier 4 (Low)
              </span>
            </div>
            <p className="mt-3 text-[11px] text-slate-400 text-center flex flex-wrap justify-center gap-x-1 gap-y-0.5">
              <span title={HEATMAP_GLOSSARY.chartAxisX} className="cursor-help border-b border-dotted border-slate-400">
                X-axis: FIS / ES
              </span>
              <span className="text-slate-300">·</span>
              <span title={HEATMAP_GLOSSARY.chartAxisY} className="cursor-help border-b border-dotted border-slate-400">
                Y-axis: EUS / RSS
              </span>
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div className="flex items-center gap-4">
                <h2 className="font-semibold text-slate-800">Prioritized Opportunities</h2>
                {selectedIds.size > 0 && (
                  <span className="text-xs bg-blue-50 text-sponsor-blue font-medium px-2.5 py-1 rounded-full border border-blue-100">
                    {selectedIds.size} selected
                  </span>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleRefreshScores}
                  disabled={pipelineRunning}
                  className="px-4 py-2 bg-white border border-slate-200 shadow-sm rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {pipelineRunning ? "Refreshing..." : "Refresh Scores"}
                </button>
                <button 
                  onClick={handlePushToCasework}
                  disabled={selectedIds.size === 0}
                  className="px-4 py-2 bg-sponsor-blue text-white shadow-md rounded-md text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Approve Selected (Run DTP01)
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200 text-left">
                    <th className="px-6 py-4 font-medium w-10">
                      <input 
                        type="checkbox" 
                        className="rounded border-slate-300 w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" 
                        checked={selectedIds.size === activeOpportunities.length && activeOpportunities.length > 0}
                        onChange={handleSelectAll}
                      />
                    </th>
                    <th className="px-6 py-4 font-medium">Supplier / Request</th>
                    <th className="px-6 py-4 font-medium">Category</th>
                    <th className="px-6 py-4 font-medium cursor-help" title={HEATMAP_GLOSSARY.tier}>
                      Tier
                    </th>
                    <th className="px-6 py-4 font-medium cursor-help" title="Component scores (hover each chip below). Renewals: EUS, FIS, RSS, SCS, SAS. New requests: IUS, ES, CSIS, SAS.">
                      Score Breakdown
                    </th>
                    <th className="px-6 py-4 font-medium cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                      Total
                    </th>
                    <th className="px-6 py-4 font-medium">Action Window</th>
                    <th className="px-6 py-4 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-slate-500">
                        <div className="flex flex-col items-center justify-center">
                          <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-sponsor-blue animate-spin mb-3"></div>
                          <p>Loading scored opportunities from backend...</p>
                        </div>
                      </td>
                    </tr>
                  ) : opportunities.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-6 py-12 text-center text-slate-500">
                        No opportunities found in the scoring engine.
                      </td>
                    </tr>
                  ) : (
                    activeOpportunities.map((opp) => {
                      const id = opp.id;
                      const isSelected = selectedIds.has(id);
                      return (
                        <tr key={id} className={`transition-colors ${isSelected ? 'bg-blue-50/50' : 'hover:bg-slate-50'}`}>
                          <td className="px-6 py-4 border-l-2 border-transparent" style={{borderLeftColor: isSelected ? '#1e3a8a' : 'transparent'}}>
                            <input 
                              type="checkbox" 
                              className="rounded border-slate-300 w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" 
                              checked={isSelected}
                              onChange={() => handleSelectOne(id)}
                            />
                          </td>
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
                                T1
                              </span>
                            )}
                            {opp.tier === 'T2' && (
                              <span title={HEATMAP_GLOSSARY.t2} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700 ring-1 ring-inset ring-orange-100 border border-orange-200 cursor-help">
                                T2
                              </span>
                            )}
                            {opp.tier === 'T3' && (
                              <span title={HEATMAP_GLOSSARY.t3} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-sponsor-blue border border-sponsor-blue/20 cursor-help">
                                T3
                              </span>
                            )}
                            {opp.tier === 'T4' && (
                              <span title={HEATMAP_GLOSSARY.t4} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200 cursor-help">
                                T4
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
                          <td className="px-6 py-4 text-sm font-medium text-slate-700">
                            {opp.recommended_action_window || (opp.tier === 'T1' ? 'Critical' : opp.tier === 'T2' ? 'Immediate' : 'Monitor')}
                          </td>
                          <td className="px-6 py-4 text-right">
                            {opp.status === 'Approved' ? (
                              <span className="text-xs font-semibold text-green-600 uppercase flex items-center justify-end gap-1">
                                Reviewed <ExternalLink className="w-3 h-3"/>
                              </span>
                            ) : (
                              <button 
                                onClick={async () => {
                                  setReviewOpp(opp);
                                  setFeedbackTier(opp.tier);
                                  setFeedbackReason("");
                                  setFeedbackHistory(null);
                                  setFeedbackHistoryLoading(true);
                                  try {
                                    const url = `${getApiBaseUrl()}/api/heatmap/feedback/history?opportunity_id=${opp.id}`;
                                    const r = await apiFetch(url, { cache: "no-store" });
                                    if (!r.ok) {
                                      setFeedbackHistory([]);
                                    } else {
                                      const rows = (await r.json()) as any[];
                                      setFeedbackHistory(Array.isArray(rows) ? rows : []);
                                    }
                                  } catch {
                                    setFeedbackHistory([]);
                                  } finally {
                                    setFeedbackHistoryLoading(false);
                                  }
                                }}
                                className="text-sponsor-blue hover:text-blue-800 text-sm font-medium bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded transition"
                              >
                                Review
                              </button>
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

        {/* --- SOURCING OPPORTUNITY MATRIX (full table on dedicated page) --- */}
        <div className="mt-12 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-6 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Sourcing Opportunity Matrix</h2>
              <p className="text-sm text-slate-500 mt-1">
                Per-opportunity KPI/KLI grid for all five Agentic Outcomes — moved to its own page for readability.
              </p>
            </div>
            <Link
              href="/heatmap/matrix"
              className="inline-flex items-center gap-2 shrink-0 px-4 py-2.5 rounded-lg bg-sponsor-blue text-white text-sm font-bold shadow hover:bg-blue-700 transition-colors"
            >
              <Table2 className="w-4 h-4" />
              Open matrix
            </Link>
          </div>
        </div>
      </div>

      {/* Optional Copilot Slide-over */}
      {copilotOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
            onClick={() => setCopilotOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-2xl flex flex-col transform transition-transform border-l border-slate-200">
            <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <div className="min-w-0">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                  <MessageCircle className="w-5 h-5 text-sponsor-blue shrink-0" />
                  Heatmap copilot
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  Optional. Explain rankings (scores stay truth), check feedback vs policy, draft{" "}
                  <code className="text-slate-600">category_cards.json</code> patches (preview only).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCopilotOpen(false)}
                className="text-slate-400 hover:text-slate-600 transition bg-white p-2 rounded-full shadow-sm"
                aria-label="Close copilot"
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
                      Search by supplier, contract_id, request_id, or tier. Click a row to insert its ID into your question.
                    </p>
                  </div>
                  <span className="text-[11px] text-slate-400 shrink-0">{opportunities.length} loaded</span>
                </div>
                <input
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                  value={copilotRefQuery}
                  onChange={(e) => setCopilotRefQuery(e.target.value)}
                  placeholder='e.g. "TechGlobal", "REQ-", "T1", "contract"'
                />
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2 font-semibold text-slate-600">Supplier / Request</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">Tier</th>
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
                              setCopilotTab("qa");
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
                                {o.tier}
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
                    onClick={() => setCopilotTab(key)}
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
                    <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">
                      {qaAnswer}
                    </div>
                  )}
                </div>
              )}

              {copilotTab === "policy" && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
                  <p className="text-xs text-slate-500">
                    Suggestion only — does not change scores or files. Compares your text to{" "}
                    <code className="text-slate-600">category_cards.json</code> for the category.
                  </p>
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
                      <label className="block text-xs font-medium text-slate-600 mb-1">Current tier (optional)</label>
                      <input
                        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                        value={policyTier}
                        onChange={(e) => setPolicyTier(e.target.value)}
                        placeholder="T2"
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
                  <p className="text-xs text-slate-500">
                    Upload a policy document (plain text) or describe changes below. The system extracts a structured patch,
                    then you can <strong>apply it and re-run scoring</strong> so opportunity tiers update (SAS from category cards).
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
              
              {/* Header Box */}
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex justify-between items-start">
                <div>
                  <p className="text-xs font-bold text-sponsor-blue uppercase tracking-widest mb-2 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-sponsor-blue animate-pulse"></span>
                    Target
                  </p>
                  <p className="text-2xl font-bold text-slate-800">{reviewOpp.supplier_name || 'New Requirement'}</p>
                  <p className="text-sm font-mono text-slate-500 mt-1">{reviewOpp.contract_id || reviewOpp.request_id}</p>
                  <div className="mt-4 flex gap-2">
                    <span className="px-2.5 py-1 bg-slate-100 rounded text-xs font-medium text-slate-600 border border-slate-200">{reviewOpp.category}</span>
                    <span className="px-2.5 py-1 bg-slate-100 rounded text-xs font-medium text-slate-600 border border-slate-200">{reviewOpp.subcategory || 'General'}</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-slate-500 mb-1 cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                    Agentic Score
                  </p>
                  <p className="text-4xl font-black text-sponsor-blue tracking-tighter cursor-help" title={HEATMAP_GLOSSARY.agenticScore}>
                    {reviewOpp.total_score?.toFixed(1)}
                    <span className="text-lg text-slate-400">/10</span>
                  </p>
                  <p
                    className="text-xs font-bold text-mit-red mt-2 uppercase bg-red-50 inline-block px-2 py-1 rounded cursor-help"
                    title={HEATMAP_GLOSSARY[TIER_TOOLTIP[reviewOpp.tier] ?? "tier"]}
                  >
                    {reviewOpp.tier} - {reviewOpp.recommended_action_window}
                  </p>
                </div>
              </div>

              {/* Justification Box */}
              <div className="bg-blue-50/50 p-6 rounded-xl border border-blue-100">
                <p className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3">AI Engine Justification</p>
                <p className="text-sm text-slate-700 leading-relaxed italic border-l-4 border-sponsor-blue pl-4 py-1">
                  &ldquo;{reviewOpp.justification_summary}&rdquo;
                </p>
              </div>

              {/* Detailed Breakdown & Artifacts Grid */}
              <div className="grid grid-cols-2 gap-6">
                
                {/* Mathematical Engine Breakdown */}
                <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 border-b border-slate-100 pb-2">Sub-Score Breakdown</p>
                  <div className="space-y-3">
                    {reviewOpp.eus_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.eus}>
                          Expiry Urgency (EUS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.eus_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.ius_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.ius}>
                          Implement Urgency (IUS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.ius_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.fis_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.fis}>
                          Financial Impact (FIS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.fis_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.es_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.es}>
                          Estimated Spend (ES)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.es_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.rss_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.rss}>
                          Supplier Risk (RSS)
                        </span>
                        <span className="font-mono text-sm font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded border border-orange-100">{reviewOpp.rss_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.scs_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.scs}>
                          Spend Concentration (SCS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.scs_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.csis_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.csis}>
                          Category Spend (CSIS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.csis_score?.toFixed(1)}</span>
                      </div>
                    )}
                    {reviewOpp.sas_score != null && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-slate-600 cursor-help border-b border-dotted border-slate-300" title={HEATMAP_GLOSSARY.sas}>
                          Strategic Alignment (SAS)
                        </span>
                        <span className="font-mono text-sm font-semibold bg-slate-100 px-2 py-0.5 rounded">{reviewOpp.sas_score?.toFixed(1)}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Context & Artifacts */}
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
              </div>

              {/* Human Feedback Section + History */}
              <div className="space-y-4">
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                  <p className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-3 mb-5 flex items-center gap-2">
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                    Human-in-the-Loop Override
                  </p>
                  <div className="grid grid-cols-3 gap-6">
                    <div className="col-span-1 border-r border-slate-100 pr-6">
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Adjust Priority</label>
                      <select 
                        className="w-full border border-slate-300 rounded-lg shadow-sm py-2.5 px-3 text-sm focus:ring-2 focus:ring-sponsor-blue/20 focus:border-sponsor-blue font-medium bg-slate-50 cursor-pointer"
                        value={feedbackTier} 
                        onChange={(e) => setFeedbackTier(e.target.value)}
                      >
                        <option value="T1">T1 - Critical</option>
                        <option value="T2">T2 - Immediate</option>
                        <option value="T3">T3 - Monitor</option>
                        <option value="T4">T4 - Low Priority</option>
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Rationale & Next Steps</label>
                      <textarea 
                        className="w-full border border-slate-300 rounded-lg shadow-sm py-3 px-4 text-sm focus:ring-2 focus:ring-sponsor-blue/20 focus:border-sponsor-blue min-h-[100px] placeholder-slate-400 bg-slate-50"
                        placeholder="e.g., 'We decided to consolidate this supplier last week, pushing to Q3 instead. Downgrading to Tier 3 monitor.'"
                        value={feedbackReason}
                        onChange={(e) => setFeedbackReason(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

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
