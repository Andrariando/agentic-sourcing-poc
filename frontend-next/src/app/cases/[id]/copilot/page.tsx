"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, AlertTriangle, FileText, ShieldCheck, ChevronRight, MessageSquare, Briefcase, Clock, Terminal, Activity, Users, UserPlus, Download, ThumbsUp, ThumbsDown, Paperclip, X } from "lucide-react";
import { motion } from "framer-motion";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl } from "@/lib/api-base";
import { getMockCasePerformanceInsight } from "@/lib/mock-case-performance";
import { buildDecisionDataForStage } from "@/lib/dtp-approve-defaults";
import { computeStageReadiness, splitStageFields, stageSchema, type DtpFieldSchema } from "@/lib/dtp-stage-schema";
import ProcuraBotIdentity from "@/components/branding/ProcuraBotIdentity";
import { PROCURABOT_BRAND } from "@/lib/procurabot-brand";
import DtpStepper, { type DtpStage } from "@/components/workflow/DtpStepper";
import OpportunityContextRail from "@/components/workflow/OpportunityContextRail";
import FutureStageRequirements from "@/components/workflow/FutureStageRequirements";

/** Normalize common LLM quirks so chat reads cleanly before Markdown pass. */
function normalizeAssistantText(text: string): string {
  return text
    .replace(/(Cancel request)\s+(Tell me)/gi, "$1\n\n$2")
    .replace(/\s*(\*Options:\*)/g, "\n\n$1");
}

/**
 * Inline **bold** and *italic* (subset of Markdown). Assistant messages use this from the LLM;
 * React does not parse Markdown when rendering raw strings.
 */
function parseInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let key = 0;
  const re = /(\*\*[\s\S]+?\*\*|\*[^*\n]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(text.slice(last, m.index));
    }
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
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts.length === 0 ? text : <>{parts}</>;
}

function parseSimpleMarkdown(text: string): React.ReactNode {
  const normalized = normalizeAssistantText(text);
  const lines = normalized.split("\n");
  return (
    <>
      {lines.map((line, lineIdx) => (
        <React.Fragment key={`ln-${lineIdx}`}>
          {lineIdx > 0 ? <br /> : null}
          {parseInlineMarkdown(line)}
        </React.Fragment>
      ))}
    </>
  );
}

function formatHintForField(key: string): string | null {
  const k = (key || "").toLowerCase();
  if (k.includes("date")) return "Format: YYYY-MM-DD (example: 2026-08-01)";
  if (k.includes("usd") || k.includes("value") || k.includes("amount")) return "Format: numeric only, no commas (example: 4200000)";
  if (k.includes("received") || k.includes("count")) return "Format: x/y or integer (example: 3/5)";
  if (k.includes("signoff")) return "Format: name and date (example: Jane Doe - 2026-09-15)";
  if (k.includes("started") || k.includes("confirmed") || k.includes("signed")) return "Format: yes/no";
  if (k.includes("reference") || k.includes("id")) return "Format: short code (example: CT-2026-001)";
  return null;
}

function usageHintForField(field: DtpFieldSchema): string {
  if (field.document_dependency) return `Used to populate ${field.document_dependency.toUpperCase()} draft outputs.`;
  if (field.critical) return "Used for stage readiness gating and approval progression.";
  if (field.ai_extractable) return "Used by ProcuraBot extraction and long-chat memory grounding.";
  return "Used as supporting context for recommendations and handoff quality.";
}

type ArtifactPackSummaryRow = {
  pack_id: string;
  agent_name?: string;
  created_at?: string;
  artifact_count?: number;
  is_latest?: boolean;
};

type DocumentCenterRow = {
  id: string;
  filename: string;
  file_type?: string;
  document_type?: string;
  source: string;
  updated_at?: string;
  pack_id?: string;
  artifact_count?: number;
};

function getFriendlyArtifactSourceName(agentName?: string): string {
  const raw = (agentName || "").trim();
  if (!raw) return "ProcuraBot run";
  if (raw.toLowerCase() === "copilot") return "ProcuraBot";
  return raw;
}

async function downloadArtifactPackExport(
  caseId: string,
  packId: string,
  format: "md" | "docx" | "pdf"
): Promise<void> {
  const url = `${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/artifact-packs/${encodeURIComponent(packId)}/export?export_format=${format}`;
  const res = await apiFetch(url);
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(t || `Export failed (${res.status})`);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let filename = `pack_export.${format}`;
  const m = cd && /filename="([^"]+)"/.exec(cd);
  if (m) filename = m[1];
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(u);
}

function readDecisionAnswer(val: unknown): string | undefined {
  if (val == null) return undefined;
  if (typeof val === "object" && val !== null && "answer" in (val as object)) {
    const a = (val as { answer?: unknown }).answer;
    if (a == null || a === "") return undefined;
    return String(a);
  }
  if (typeof val === "string" && val) return val;
  return undefined;
}

/** RFx focus tier: from API ``dtp02_fit`` (deterministic) or legacy shortlist seed. */
type Dtp02ShortlistRole = "primary" | "secondary" | "included" | "user-added";
const DTP_STAGES: DtpStage[] = [
  { id: "DTP-01", label: "Sourcing Pathway", shortLabel: "Pathway" },
  { id: "DTP-02", label: "Evaluation Setup", shortLabel: "Eval setup" },
  { id: "DTP-03", label: "RFP Issue", shortLabel: "RFP issue" },
  { id: "DTP-04", label: "Evaluate & Negotiate", shortLabel: "Evaluate" },
  { id: "DTP-05", label: "Contracting", shortLabel: "Contract" },
  { id: "DTP-06", label: "Implementation", shortLabel: "Implement" },
];

type Dtp02ShortlistRow = {
  supplier_id: string;
  supplier_name: string;
  riskLabel: string;
  fitLabel: string;
  roleKey: Dtp02ShortlistRole;
  notes?: string;
};

function shortlistRoleFromLegacyRaw(o: Record<string, unknown>): Dtp02ShortlistRole {
  const r = String(o.shortlist_role ?? o.dtp02_fit ?? "").toLowerCase();
  if (r === "user-added") return "user-added";
  if (r === "optional" || o.optional === true) return "secondary";
  if (r === "secondary" || r === "included" || r === "primary") return r as Dtp02ShortlistRole;
  if (r === "core") return "primary";
  return "included";
}

function normalizeDtp02ShortlistRows(rawList: unknown): Dtp02ShortlistRow[] {
  if (!Array.isArray(rawList)) return [];
  return rawList.map((raw, idx) => {
    const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
    const sid = o.supplier_id != null && String(o.supplier_id) ? String(o.supplier_id) : `SL-${idx}`;
    const name =
      o.supplier_name != null && String(o.supplier_name)
        ? String(o.supplier_name)
        : o.name != null && String(o.name)
          ? String(o.name)
          : "Supplier";
    const scoreRaw = o.overall_score ?? o.score;
    const fitLabel =
      typeof scoreRaw === "number" && !Number.isNaN(scoreRaw) ? `${Number(scoreRaw).toFixed(1)} / 10` : "—";
    const notes =
      typeof o.notes === "string"
        ? o.notes
        : Array.isArray(o.strengths)
          ? String(o.strengths[0] ?? "")
          : undefined;
    const risk =
      o.risk_level != null && String(o.risk_level) ? String(o.risk_level) : "—";
    return {
      supplier_id: sid,
      supplier_name: name,
      riskLabel: risk,
      fitLabel,
      roleKey: shortlistRoleFromLegacyRaw(o),
      notes: notes || undefined,
    };
  });
}

function categoryPoolApiToRows(pool: unknown): Dtp02ShortlistRow[] {
  if (!Array.isArray(pool)) return [];
  return pool.map((raw, idx) => {
    const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
    const sid = o.supplier_id != null && String(o.supplier_id) ? String(o.supplier_id) : `POOL-${idx}`;
    const name =
      o.supplier_name != null && String(o.supplier_name) ? String(o.supplier_name) : sid;
    const fitNum = o.overall_score;
    const fitLabel =
      typeof fitNum === "number" && !Number.isNaN(fitNum) ? `${fitNum.toFixed(1)} / 10` : "—";
    const risk = o.risk_level != null && String(o.risk_level) ? String(o.risk_level) : "—";
    const fit = String(o.dtp02_fit ?? "included").toLowerCase();
    const roleKey: Dtp02ShortlistRole =
      fit === "primary" || fit === "secondary" || fit === "included" ? (fit as Dtp02ShortlistRole) : "included";
    const cid = o.category_id != null && String(o.category_id) ? String(o.category_id) : "";
    return {
      supplier_id: sid,
      supplier_name: name,
      riskLabel: risk,
      fitLabel,
      roleKey,
      notes: cid ? `Enterprise catalog · ${cid}` : undefined,
    };
  });
}

function buildAssistantWelcome(data: any): string {
  const name = data.name || "this case";
  const stage = data.dtp_stage || "DTP-01";
  const focus = data.copilot_focus;
  const title = focus?.stage_title ? ` — ${focus.stage_title}` : "";
  let msg = `I'm your AI assistant for **${name}**. We're in **${stage}${title}**.\n\n`;
  if (focus?.stage_description) msg += `${focus.stage_description}\n\n`;

  msg +=
    "You can upload files directly in chat (Word, PDF, spreadsheets, and images). " +
    "I will use them as context for answers and recommendations.\n\n";

  const pending = focus?.pending_questions || [];
  if (pending.length > 0) {
    const pq = pending[0];
    msg += `**Decision to work through:** ${pq.text}\n`;
    const labels = pq.option_labels as string[] | undefined;
    if (labels?.length) msg += `*Options:* ${labels.slice(0, 6).join(" · ")}\n\n`;
    msg += `Tell me your priorities and we can compare tradeoffs—no need to have it figured out yet. [What are my best options here?]`;
  } else {
    msg += `Checklist items for this stage look complete. I can help with next steps, risks, or what happens if we move forward. [What's the smartest next step?]`;
  }
  return msg;
}

/** True when this stage's structured answers exist on the server (from chat or legacy console). */
function isStageDecisionRecordedOnServer(caseDetails: any): boolean {
  const stage = caseDetails?.dtp_stage;
  if (!stage || !caseDetails?.human_decision?.[stage]) return false;
  const expected = buildDecisionDataForStage(stage, caseDetails?.supplier_id);
  if (!expected) return false;
  const row = caseDetails.human_decision[stage];
  return Object.keys(expected).every((k) => readDecisionAnswer(row[k]));
}

export default function CaseProcuraBotPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [caseDetails, setCaseDetails] = useState<any>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [documentsCenter, setDocumentsCenter] = useState<{
    uploads: DocumentCenterRow[];
    internal_references: DocumentCenterRow[];
    generated_outputs: DocumentCenterRow[];
  }>({ uploads: [], internal_references: [], generated_outputs: [] });
  const [documentsTab, setDocumentsTab] = useState<"uploads" | "generated" | "internal">("uploads");
  const [documentsQuery, setDocumentsQuery] = useState("");
  const [documentsTypeFilter, setDocumentsTypeFilter] = useState<"all" | "pdf" | "docx" | "xlsx" | "bundle" | "other">("all");
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [chatFiles, setChatFiles] = useState<File[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [msgVoteByIdx, setMsgVoteByIdx] = useState<Record<number, "up" | "down">>({});
  const [msgVoteBusyIdx, setMsgVoteBusyIdx] = useState<number | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const initialChatHydrated = useRef(false);
  const chatFileInputRef = useRef<HTMLInputElement>(null);

  /** Demo-only rows added in the UI (not persisted). Resets per case. */
  const [demoAddedShortlistRows, setDemoAddedShortlistRows] = useState<Dtp02ShortlistRow[]>([]);
  const [optionalSupplierName, setOptionalSupplierName] = useState("");
  const [optionalSupplierRegion, setOptionalSupplierRegion] = useState("");
  const [packExportError, setPackExportError] = useState<string | null>(null);
  const [packExportLoading, setPackExportLoading] = useState<string | null>(null);
  const [cancelReasonCode, setCancelReasonCode] = useState("strategy_change");
  const [cancelReasonText, setCancelReasonText] = useState("");
  const [cancelSubmitting, setCancelSubmitting] = useState(false);
  const [stageInputValues, setStageInputValues] = useState<Record<string, string>>({});
  const [stageInputSubmitting, setStageInputSubmitting] = useState(false);
  const [draftGeneratingRole, setDraftGeneratingRole] = useState<"rfx" | "contract" | null>(null);
  const [stageInputBusy, setStageInputBusy] = useState(false);
  const [stageExtractBusy, setStageExtractBusy] = useState(false);
  const [extractSourceText, setExtractSourceText] = useState("");
  const [extractPreview, setExtractPreview] = useState<Record<string, string> | null>(null);
  const [advanceSubmitting, setAdvanceSubmitting] = useState(false);
  const [advanceMessage, setAdvanceMessage] = useState<string | null>(null);
  const [chatPanelWidthPct, setChatPanelWidthPct] = useState(40);
  const isResizingChatPanelRef = useRef(false);

  useEffect(() => {
    setDemoAddedShortlistRows([]);
    setOptionalSupplierName("");
    setOptionalSupplierRegion("");
  }, [caseId]);
  useEffect(() => {
    if (!caseDetails) return;
    setStageInputValues((prev) => ({
      ...prev,
      request_title: prev.request_title || String(caseDetails?.name || ""),
      business_unit: prev.business_unit || String(caseDetails?.business_unit || ""),
      estimated_annual_value_usd: prev.estimated_annual_value_usd || String(caseDetails?.estimated_spend_usd || ""),
      required_start_date: prev.required_start_date || String(caseDetails?.required_start_date || ""),
      implementation_urgency: prev.implementation_urgency || String(caseDetails?.implementation_urgency || ""),
    }));
  }, [caseDetails]);

  useEffect(() => {
    if (!caseId) return;
    const stage = String(caseDetails?.dtp_stage || "DTP-01");
    const run = async () => {
      try {
        const res = await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/stage-intake?stage=${encodeURIComponent(stage)}`);
        if (!res.ok) return;
        const data = await res.json();
        const vals = (data?.values && typeof data.values === "object") ? (data.values as Record<string, string>) : {};
        if (Object.keys(vals).length > 0) {
          setStageInputValues((prev) => ({ ...prev, ...vals }));
        }
      } catch {
        // no-op; keep local state fallback
      }
    };
    void run();
  }, [caseId, caseDetails?.dtp_stage]);

  useEffect(() => {
    const onMouseMove = (event: MouseEvent) => {
      if (!isResizingChatPanelRef.current) return;
      const rawRightPct = ((window.innerWidth - event.clientX) / window.innerWidth) * 100;
      const clamped = Math.max(28, Math.min(55, rawRightPct));
      setChatPanelWidthPct(clamped);
    };
    const onMouseUp = () => {
      isResizingChatPanelRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);


  /** Stage checklist satisfied on server (answers recorded for current DTP stage). */
  const stageDecisionComplete = Boolean(caseDetails && isStageDecisionRecordedOnServer(caseDetails));

  const container: any = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } };
  const item: any = { hidden: { opacity: 0, y: 15 }, show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } } };

  // 1. Fetch Case Details & Chat History (poll only updates case meta — never resets chat)
  useEffect(() => {
    if (!caseId) {
      setCaseLoading(false);
      return;
    }
    initialChatHydrated.current = false;
    setCaseLoading(true);
    setCaseError(null);

    async function fetchCase(isPoll: boolean) {
      try {
        const url = `${getApiBaseUrl()}/api/cases/${caseId}`;
        const res = await apiFetch(url);
        if (!res.ok) {
          if (!isPoll) {
            setCaseError("Case not found or API error.");
            setCaseDetails(null);
            initialChatHydrated.current = false;
            setMessages([]);
          }
          if (!isPoll) setCaseLoading(false);
          return;
        }
        const data = await res.json();
        setCaseError(null);
        setCaseDetails(data);
        if (!isPoll) setCaseLoading(false);

        if (isPoll || initialChatHydrated.current) return;
        initialChatHydrated.current = true;

        if (data.chat_history) {
          try {
            const parsed = typeof data.chat_history === 'string' ? JSON.parse(data.chat_history) : data.chat_history;
            if (Array.isArray(parsed) && parsed.length > 0) {
              setMessages(parsed.map((m: any) => ({ role: m.role, content: m.content })));
              return;
            }
          } catch (e) {
            console.warn('Failed to parse chat_history', e);
          }
        }
        setMessages([{ role: "assistant", content: buildAssistantWelcome(data) }]);
      } catch (err) {
        console.error("Failed to fetch case details:", err);
        if (!isPoll) {
          setCaseError("Network error attempting to fetch case.");
          setCaseDetails(null);
          initialChatHydrated.current = false;
          setMessages([]);
        }
        if (!isPoll) setCaseLoading(false);
      }
    }
    
  // 2. Fetch Documents center
    async function fetchDocsCenter() {
      try {
        const url = `${getApiBaseUrl()}/api/cases/${caseId}/documents/center`;
        const res = await apiFetch(url);
        const data = await res.json();
        setDocumentsCenter({
          uploads: Array.isArray(data.uploads) ? data.uploads : [],
          internal_references: Array.isArray(data.internal_references) ? data.internal_references : [],
          generated_outputs: Array.isArray(data.generated_outputs) ? data.generated_outputs : [],
        });
      } catch (err) {
        console.error("Failed to fetch document center:", err);
      }
    }

    fetchCase(false);
    fetchDocsCenter();
    const interval = setInterval(() => fetchCase(true), 5000);
    return () => clearInterval(interval);
  }, [caseId]);

  const refreshCaseMeta = async () => {
    try {
      const url = `${getApiBaseUrl()}/api/cases/${caseId}`;
      const res = await apiFetch(url);
      if (res.ok) setCaseDetails(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  // Auto-scroll the process log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [caseDetails?.activity_log]);

  const fetchDocsCenterNow = async () => {
    try {
      const url = `${getApiBaseUrl()}/api/cases/${caseId}/documents/center`;
      const res = await apiFetch(url);
      const data = await res.json();
      setDocumentsCenter({
        uploads: Array.isArray(data.uploads) ? data.uploads : [],
        internal_references: Array.isArray(data.internal_references) ? data.internal_references : [],
        generated_outputs: Array.isArray(data.generated_outputs) ? data.generated_outputs : [],
      });
    } catch (err) {
      console.error("Failed to refresh document center:", err);
    }
  };

  const sendChatTurn = async (userMsg: string, files: File[] = [], visibleMsg?: string) => {
    if (!caseDetails) return;
    const trimmed = userMsg.trim();
    if (!trimmed && files.length === 0) return;
    const fileNames = files.map((f) => f.name);
    const userVisibleMsg = visibleMsg ?? [trimmed, fileNames.length ? `Attached: ${fileNames.join(", ")}` : ""]
      .filter(Boolean)
      .join("\n");
    setMessages(prev => [...prev, { role: "user", content: userVisibleMsg }]);
    setIsTyping(true);

    try {
      let res: Response;
      if (fileNames.length > 0) {
        const url = `${getApiBaseUrl()}/api/chat/with-attachments`;
        const fd = new FormData();
        fd.append("case_id", caseId);
        fd.append("user_message", trimmed);
        fd.append("use_tier_2", "true");
        files.forEach((f) => fd.append("files", f));
        res = await apiFetch(url, { method: "POST", body: fd });
      } else {
        const url = `${getApiBaseUrl()}/api/chat`;
        res = await apiFetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            case_id: caseId,
            user_message: trimmed,
            use_tier_2: true
          })
        });
      }

      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        const lastMsg = [...data.messages].reverse().find((m: any) => m.role === "assistant" || m.role === "ai");
        if (lastMsg) {
          setMessages(prev => [...prev, { role: "assistant", content: lastMsg.content }]);
        }
      } else if (data.assistant_message) {
        setMessages(prev => [...prev, { role: "assistant", content: data.assistant_message }]);
      } else if (data.response) {
        setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
      }
      await refreshCaseMeta();
      await fetchDocsCenterNow();
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: "assistant", content: "Error: Could not reach the LangGraph Backend API." }]);
    } finally {
      setIsTyping(false);
    }
  };

  // 3. Handle Live Chat
  const handleSend = async () => {
    if (!caseDetails) return;
    if (!input.trim() && chatFiles.length === 0) return;
    const userMsg = input.trim();
    const files = [...chatFiles];
    setInput("");
    setChatFiles([]);
    await sendChatTurn(userMsg, files);
  };

  const getActiveStageFields = () => stageSchema(String(caseDetails?.dtp_stage || "DTP-01"));

  const saveStageIntake = async (source = "human_form") => {
    setStageInputBusy(true);
    try {
      await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/stage-intake`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stage: String(caseDetails?.dtp_stage || "DTP-01"),
          values: stageInputValues,
          source,
          updated_by: "human-manager",
        }),
      });
      await refreshCaseMeta();
    } finally {
      setStageInputBusy(false);
    }
  };

  const sendStructuredInputToCopilot = async () => {
    const activeStageFields = getActiveStageFields();
    if (activeStageFields.length === 0) return;
    setStageInputSubmitting(true);
    try {
      await saveStageIntake("human_form");
      const lines = activeStageFields.map((f) => `- ${f.key}: ${(stageInputValues[f.key] || "").trim() || "(missing)"}`);
      const msg = [
        `Please use this structured human input for ${displayStage}.`,
        "",
        "Update your case understanding, identify missing required and critical data, and guide me step-by-step to complete what is still missing.",
        "",
        ...lines,
      ].join("\n");
      await sendChatTurn(msg, [], `[Structured input submitted for ${displayStage}]`);
    } finally {
      setStageInputSubmitting(false);
    }
  };

  const generateDraftFromStructuredInput = async (role: "rfx" | "contract") => {
    const activeStageFields = getActiveStageFields();
    if (activeStageFields.length === 0) return;
    setDraftGeneratingRole(role);
    try {
      const checkRes = await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/stage-intake/generation-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stage: displayStage,
          values: stageInputValues,
        }),
      });
      const check = await checkRes.json().catch(() => ({} as { can_generate?: boolean; missing_fields?: string[] }));
      if (!checkRes.ok || !check.can_generate) {
        const miss = Array.isArray(check?.missing_fields) ? check.missing_fields.join(", ") : "required fields";
        alert(`Cannot generate yet. Missing: ${miss}`);
        return;
      }
      await saveStageIntake("human_form");
      const roleName = role === "rfx" ? "RFx" : "Contract";
      const lines = activeStageFields.map((f) => `- ${f.label}: ${(stageInputValues[f.key] || "").trim() || "(missing)"}`);
      const msg = [
        `Generate a ${roleName} draft from this structured input and store it as a generated output artifact pack for this case.`,
        "If key fields are missing, make assumptions explicit in the draft and list open questions at the end.",
        "",
        ...lines,
      ].join("\n");
      await sendChatTurn(msg, [], `[Generate ${roleName} draft request submitted]`);
    } finally {
      setDraftGeneratingRole(null);
    }
  };

  const extractToStructuredFields = async () => {
    const freeText = extractSourceText.trim() || String(messages.filter((m) => m.role === "assistant").slice(-1)[0]?.content || "").trim();
    if (!freeText) {
      alert("Provide text or have at least one assistant response to extract from.");
      return;
    }
    setStageExtractBusy(true);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/stage-intake/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stage: displayStage,
          free_text: freeText,
          existing_values: stageInputValues,
        }),
      });
      if (!res.ok) {
        alert("Could not extract structured values from text.");
        return;
      }
      const data = await res.json();
      const proposed = (data?.proposed_values && typeof data.proposed_values === "object")
        ? (data.proposed_values as Record<string, string>)
        : {};
      setExtractPreview(proposed);
    } finally {
      setStageExtractBusy(false);
    }
  };

  const applyExtractPreview = async () => {
    if (!extractPreview) return;
    setStageInputValues((prev) => ({ ...prev, ...extractPreview }));
    setExtractPreview(null);
    await saveStageIntake("chat_extract_confirmed");
  };

  const advanceStage = async () => {
    if (!caseDetails || readinessState.readiness === "blocked") return;
    setAdvanceSubmitting(true);
    setAdvanceMessage(null);
    try {
      await saveStageIntake("human_form");
      const decisionData = buildDecisionDataForStage(displayStage, supplierId);
      const res = await apiFetch(`${getApiBaseUrl()}/api/decisions/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: caseId,
          decision: "Approve",
          reason: `Advance from ${displayStage} via stage workspace`,
          decision_data: decisionData || undefined,
        }),
      });
      const data = await res.json().catch(() => ({} as { message?: string; detail?: string; new_dtp_stage?: string }));
      if (!res.ok) {
        setAdvanceMessage(data?.detail || data?.message || "Could not advance stage yet.");
        return;
      }
      setAdvanceMessage(data?.message || `Advanced to ${data?.new_dtp_stage || "next stage"}.`);
      await refreshCaseMeta();
      await fetchDocsCenterNow();
    } catch {
      setAdvanceMessage("Could not advance stage due to network/server error.");
    } finally {
      setAdvanceSubmitting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!caseDetails) return;
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", "OTHER");
      formData.append("case_id", caseId);

      const url = `${getApiBaseUrl()}/api/ingest/document`;

      await apiFetch(url, {
        method: 'POST',
        body: formData
      });
      
      // Auto-reload the page to show new doc and new Agentic Log entry
      window.location.reload(); 
    } catch (err) {
      console.error(err);
      alert("Document upload failed.");
    } finally {
      setIsUploading(false);
    }
  };

  const renderMessageContent = (content: string) => {
    // If the message contains [Bracketed Actions], render them as clickable action chips
    const actionRegex = /\[(.*?)\]/g;
    const matches = Array.from(content.matchAll(actionRegex));

    if (matches.length === 0) {
      return <div className="break-words">{parseSimpleMarkdown(content)}</div>;
    }

    const cleanContent = content.replace(actionRegex, "").trim();

    return (
      <div className="flex flex-col gap-3">
        <div className="break-words">{parseSimpleMarkdown(cleanContent)}</div>
        <div className="flex flex-wrap gap-2 mt-1">
          {matches.map((match, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setInput(match[1]);
                setTimeout(() => document.getElementById("send-btn")?.click(), 100);
              }}
              className="bg-white text-sponsor-blue border border-sponsor-blue/30 px-3 py-1.5 rounded-full text-[11px] font-bold tracking-wide hover:bg-sponsor-blue hover:text-white transition-colors shadow-sm"
            >
              ⚡ {match[1]}
            </button>
          ))}
        </div>
      </div>
    );
  };

  const submitAssistantVote = async (msgIdx: number, content: string, vote: "up" | "down") => {
    if (!caseId || !content?.trim()) return;
    setMsgVoteBusyIdx(msgIdx);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/copilot/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vote,
          assistant_message: content,
          user_id: "human-manager",
        }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(t || `Feedback failed (${res.status})`);
      }
      setMsgVoteByIdx((prev) => ({ ...prev, [msgIdx]: vote }));
    } catch (e) {
      console.error(e);
      alert("Could not save feedback on this response.");
    } finally {
      setMsgVoteBusyIdx(null);
    }
  };

  const hasLiveCase = Boolean(caseDetails);
  const displayName = caseDetails?.name || "Case";
  const displayCategory = caseDetails?.category_id || "Category";
  const displayStage = caseDetails?.dtp_stage || "DTP-01";
  const activeStageFields = stageSchema(displayStage);
  const prioritizedStageFields = [...activeStageFields].sort((a, b) => {
    const rank = (f: DtpFieldSchema) => (f.critical ? 0 : f.required ? 1 : 2);
    return rank(a) - rank(b);
  });
  const readinessState = computeStageReadiness(displayStage, stageInputValues);
  const fieldBuckets = splitStageFields(displayStage, stageInputValues);
  const missingRequiredFields = readinessState.missingRequired;
  const stageIdx = Math.max(0, DTP_STAGES.findIndex((s) => s.id === displayStage));
  const completedStageIds = DTP_STAGES.slice(0, stageIdx).map((s) => s.id);
  const caseStatus = String(caseDetails?.status || "In Progress");
  const isCaseCancelled = caseStatus.toLowerCase() === "cancelled";
  
  // Derive display text from the real API schema
  const summaryText = caseDetails?.summary?.summary_text || "Analyzing background signals and compiling case recommendations...";
  const supplierId = caseDetails?.supplier_id || "Unassigned";
  const triggerSource = caseDetails?.trigger_source || "User";
  
  // Extract key_findings as signal bullets
  const keyFindings: Array<{type?: string; text: string}> = (caseDetails?.summary?.key_findings || []).map((f: any) => {
    if (typeof f === 'string') return { text: f };
    if (f?.text) return { type: f.type, text: f.text };
    return { text: JSON.stringify(f) };
  });
  
  // Strategy output (rich data from strategy agent)
  const strategyOutput = caseDetails?.latest_agent_output;
  const strategyConfidence = strategyOutput?.confidence ? `${(strategyOutput.confidence * 100).toFixed(0)}%` : null;
  const recommendedAction = caseDetails?.summary?.recommended_action || strategyOutput?.recommended_strategy || "Pending agent analysis";
  const riskAssessment = strategyOutput?.risk_assessment || null;
  const topFindings = keyFindings.slice(0, 3);
  const focus = caseDetails?.copilot_focus;
  const stageDecisionTemplate = buildDecisionDataForStage(displayStage, supplierId);
  const stageValuesByStage: Record<string, Record<string, string>> = {};
  if (caseDetails?.human_decision && typeof caseDetails.human_decision === "object") {
    Object.entries(caseDetails.human_decision as Record<string, unknown>).forEach(([stageKey, rowVal]) => {
      if (!rowVal || typeof rowVal !== "object") return;
      const intake = (rowVal as Record<string, unknown>)["_stage_intake"];
      if (!intake || typeof intake !== "object") return;
      const vals = (intake as Record<string, unknown>)["values"];
      if (!vals || typeof vals !== "object") return;
      stageValuesByStage[stageKey] = vals as Record<string, string>;
    });
  }
  stageValuesByStage[displayStage] = {
    ...(stageValuesByStage[displayStage] || {}),
    ...stageInputValues,
  };
  const suggestedChatPrompts: string[] = (focus?.suggested_chat_prompts as string[]) || [];
  const perfInsight = hasLiveCase
    ? getMockCasePerformanceInsight({
        caseId,
        name: displayName,
        categoryId: displayCategory,
        dtpStage: displayStage,
        triggerSource,
        supplierId,
      })
    : null;

  const poolFromCase = categoryPoolApiToRows(caseDetails?.category_supplier_pool);
  const legacyAgentShortlist = normalizeDtp02ShortlistRows(strategyOutput?.shortlisted_suppliers);
  const dtp02ShortlistBase =
    poolFromCase.length > 0 ? poolFromCase : legacyAgentShortlist;
  const dtp02ShortlistRows: Dtp02ShortlistRow[] = [...dtp02ShortlistBase, ...demoAddedShortlistRows];
  const showDtp02ShortlistCard = hasLiveCase && displayStage === "DTP-02";
  const activeDocuments =
    documentsTab === "uploads"
      ? documentsCenter.uploads
      : documentsTab === "generated"
        ? documentsCenter.generated_outputs
        : documentsCenter.internal_references;
  const filteredDocuments = activeDocuments.filter((d) => {
    const q = documentsQuery.trim().toLowerCase();
    const name = (d.filename || "").toLowerCase();
    const docType = (d.document_type || "").toLowerCase();
    const fileType = (d.file_type || "").toLowerCase();
    const qPass = !q || name.includes(q) || docType.includes(q) || fileType.includes(q);
    if (!qPass) return false;
    if (documentsTypeFilter === "all") return true;
    if (documentsTypeFilter === "other") {
      return !["pdf", "docx", "xlsx", "xls", "bundle"].includes(fileType);
    }
    if (documentsTypeFilter === "xlsx") return fileType === "xlsx" || fileType === "xls";
    return fileType === documentsTypeFilter;
  });
  const decisionAuditRows: Array<{ stage: string; question: string; answer: string; by: string; when?: string }> = [];
  if (caseDetails?.human_decision && typeof caseDetails.human_decision === "object") {
    Object.entries(caseDetails.human_decision as Record<string, unknown>).forEach(([stageKey, rowVal]) => {
      if (!rowVal || typeof rowVal !== "object") return;
      Object.entries(rowVal as Record<string, unknown>).forEach(([qKey, ansVal]) => {
        if (!ansVal || typeof ansVal !== "object") return;
        const ansObj = ansVal as Record<string, unknown>;
        const answer = ansObj.answer != null ? String(ansObj.answer) : "";
        if (!answer) return;
        decisionAuditRows.push({
          stage: stageKey,
          question: qKey.replaceAll("_", " "),
          answer,
          by: ansObj.decided_by_role != null ? String(ansObj.decided_by_role) : "User",
          when: ansObj.timestamp != null ? String(ansObj.timestamp) : undefined,
        });
      });
    });
  }
  decisionAuditRows.sort((a, b) => (b.when || "").localeCompare(a.when || ""));

  const addDemoOptionalSupplier = () => {
    const name = optionalSupplierName.trim();
    if (!name) return;
    const region = optionalSupplierRegion.trim() || "TBD";
    setDemoAddedShortlistRows((prev) => [
      ...prev,
      {
        supplier_id: `DEMO-OPT-${Date.now()}`,
        supplier_name: name,
        riskLabel: region,
        fitLabel: "—",
        roleKey: "user-added",
        notes: "Added for demo — not in seeded catalog; confirm before RFx.",
      },
    ]);
    setOptionalSupplierName("");
    setOptionalSupplierRegion("");
  };

  const handleCancelCase = async () => {
    if (!hasLiveCase || isCaseCancelled) return;
    setCancelSubmitting(true);
    try {
      const res = await apiFetch(`${getApiBaseUrl()}/api/cases/${encodeURIComponent(caseId)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason_code: cancelReasonCode,
          reason_text: cancelReasonText || undefined,
          cancelled_by: "human-manager",
        }),
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(t || `Cancel failed (${res.status})`);
      }
      await refreshCaseMeta();
      alert("Case cancelled successfully.");
    } catch (e) {
      console.error(e);
      alert("Could not cancel this case.");
    } finally {
      setCancelSubmitting(false);
    }
  };

  return (
    <div className={`flex h-screen bg-slate-50 overflow-hidden w-full m-0 p-0 font-sans ${isResizingChatPanelRef.current ? "select-none" : ""}`}>
      
      {/* LEFT PANEL: Case Details (Resizable) */}
      <div
        className="flex flex-col h-full overflow-y-auto bg-slate-50/50 border-r border-slate-200"
        style={{ width: `${100 - chatPanelWidthPct}%` }}
      >
        
        {/* Condensed Header */}
        <div className="bg-sponsor-blue text-white p-6 sticky top-0 z-10 shadow-md flex flex-row flex-wrap gap-3 justify-between items-center shrink-0">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight mb-1 font-syne">
              {hasLiveCase ? displayName : caseLoading ? "Loading case…" : "Case ProcuraBot"}
            </h1>
            <div className="flex items-center gap-3 text-sm text-blue-100 font-medium flex-wrap min-w-0">
              {hasLiveCase ? (
                <>
                  <span className="truncate">{caseId}</span>
                  <span className="shrink-0">•</span>
                  <span className="bg-blue-800/50 px-2 py-0.5 rounded text-white flex items-center gap-1.5 border border-blue-400/30 shrink-0 max-w-full">
                    <Briefcase className="w-3.5 h-3.5 shrink-0" />
                    <span className="truncate">{displayCategory}</span>
                  </span>
                </>
              ) : (
                <span className="break-words">
                  {caseLoading
                    ? `Fetching ${caseId}…`
                    : caseError
                      ? `Could not load ${caseId}`
                      : "Select a case from the dashboard"}
                </span>
              )}
            </div>
          </div>
          {hasLiveCase ? (
            <span className={`inline-flex shrink-0 items-center justify-center whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide shadow-sm self-center ${
              isCaseCancelled ? "bg-slate-200 text-slate-700" : "bg-sponsor-orange text-white"
            }`}>
              {caseStatus}
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center justify-center whitespace-nowrap bg-blue-900/60 text-blue-100 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide border border-blue-400/30 self-center">
              {caseLoading ? "Loading" : "No case"}
            </span>
          )}
        </div>

        <motion.div variants={container} initial="hidden" animate="show" className="p-8 space-y-6 flex-1">
          <DtpStepper
            stages={DTP_STAGES}
            currentStageId={displayStage}
            completedStageIds={completedStageIds}
          />
          {!hasLiveCase ? (
            caseLoading ? (
              <div className="animate-pulse space-y-6" aria-hidden>
                <div className="h-32 bg-slate-200 rounded-xl" />
                <div className="h-48 bg-slate-200 rounded-xl" />
                <div className="h-56 bg-slate-200 rounded-xl" />
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="bg-slate-50 border-b border-slate-200 p-6 flex gap-4 items-start">
                  <div className="bg-slate-100 text-slate-500 p-3 rounded-lg shrink-0">
                    <Briefcase className="w-6 h-6" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-slate-900 font-bold text-base font-syne">Case details</h3>
                    <p className="text-slate-600 text-sm mt-2 leading-relaxed">
                      {caseError
                        ? `${caseError} The link may be wrong or the case was removed. Choose another case from the dashboard.`
                        : "No case is loaded yet. Open the Case Dashboard and select a case to see the summary, stage, governance checklist, and ProcuraBot context."}
                    </p>
                    {caseId ? (
                      <p className="text-xs text-slate-500 mt-3 font-mono break-all">Requested ID: {caseId}</p>
                    ) : null}
                    <div className="mt-5 flex flex-wrap gap-3">
                      <a
                        href="/cases"
                        className="inline-flex items-center justify-center px-5 py-2.5 bg-sponsor-blue text-white rounded-lg font-bold text-sm shadow-md hover:bg-blue-700 transition-colors"
                      >
                        Case Dashboard
                      </a>
                      <a
                        href="/heatmap"
                        className="inline-flex items-center justify-center px-5 py-2.5 bg-white text-slate-700 border-2 border-slate-200 rounded-lg font-bold text-sm hover:bg-slate-50 transition-colors"
                      >
                        Heatmap
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            )
          ) : (
            <>
          <OpportunityContextRail
            typeLabel={String(caseDetails?.opportunity_type || "workflow_case")}
            opportunityLabel={displayName}
            opportunityRef={caseId}
            spendUsd={Number(caseDetails?.estimated_spend_usd || 0)}
            monthsToExpiry={String(caseDetails?.months_to_expiry ?? "—")}
            implementationMonths={String(caseDetails?.implementation_timeline_months ?? "—")}
            preferredSupplierStatus={String(caseDetails?.preferred_supplier_status || "—")}
            artifactCount={Array.isArray(caseDetails?.supporting_artifacts) ? caseDetails.supporting_artifacts.length : 0}
            hasReview={stageDecisionComplete}
            isApproved={String(caseDetails?.status || "").toLowerCase() === "approved"}
          />
          {/* Essential context only — what you need to understand the case */}
          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-amber-50 border-b border-amber-200 p-4 flex gap-3 items-start">
              <div className="bg-amber-100 text-amber-700 p-2 rounded-lg shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <h3 className="text-amber-900 font-bold text-sm">{displayStage}{focus?.stage_title ? ` · ${focus.stage_title}` : ""}</h3>
                <p className="text-amber-900/90 text-sm mt-1 leading-relaxed">{summaryText}</p>
                <p className="text-xs text-amber-800/80 mt-2">
                  <span className="font-semibold">Supplier:</span> {supplierId} · <span className="font-semibold">Trigger:</span> {triggerSource} · <span className="font-semibold">Suggested move:</span> {recommendedAction}
                  {strategyConfidence ? (
                    <span
                      className="cursor-help border-b border-dotted border-amber-800/50"
                      title="Confidence from the latest saved strategy output for this case."
                    >
                      {" "}· Recommendation confidence: {strategyConfidence}
                    </span>
                  ) : null}
                </p>
              </div>
            </div>
            <div className="p-4 border-t border-slate-100">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Top signals</p>
              {topFindings.length > 0 ? (
                <ul className="space-y-2">
                  {topFindings.map((finding, idx) => (
                    <li key={idx} className="text-sm text-slate-700 flex gap-2">
                      <span className="text-sponsor-blue font-bold">·</span>
                      <span>{finding.text}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-400 italic">No key findings yet—upload a document or ask ProcuraBot to analyze.</p>
              )}
              {riskAssessment && (
                <p className="text-sm text-slate-700 mt-3 pt-3 border-t border-slate-100"><span className="font-semibold">Risk note:</span> {riskAssessment}</p>
              )}
            </div>
          </motion.div>

          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 p-4">
              <h3 className="text-slate-800 font-bold text-sm">DTP checkpoint contract</h3>
              <p className="text-xs text-slate-500 mt-1">
                Stage approval uses structured decision payload keys so backend semantics stay consistent.
              </p>
            </div>
            <div className="p-4">
              {!stageDecisionTemplate || Object.keys(stageDecisionTemplate).length === 0 ? (
                <p className="text-xs text-slate-500">No checkpoint keys defined for this stage yet.</p>
              ) : (
                <ul className="space-y-2 text-xs text-slate-700">
                  {Object.entries(stageDecisionTemplate).map(([key, value]) => (
                    <li key={key} className="flex items-center justify-between gap-3 rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
                      <span className="font-mono text-[11px] text-slate-600">{key}</span>
                      <span className="font-semibold text-slate-800">{String(value)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.div>

          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 p-4">
              <h3 className="text-slate-800 font-bold text-sm">Execution cancellation</h3>
              <p className="text-xs text-slate-500 mt-1">
                Use when execution has started but should be stopped with a captured reason.
              </p>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Reason code</label>
                <select
                  value={cancelReasonCode}
                  onChange={(e) => setCancelReasonCode(e.target.value)}
                  className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm"
                  disabled={isCaseCancelled || cancelSubmitting}
                >
                  <option value="strategy_change">Strategy change</option>
                  <option value="budget_cut">Budget cut</option>
                  <option value="scope_change">Scope change</option>
                  <option value="supplier_issue">Supplier issue</option>
                  <option value="duplicate_case">Duplicate case</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Reason details (optional)</label>
                <textarea
                  value={cancelReasonText}
                  onChange={(e) => setCancelReasonText(e.target.value)}
                  rows={2}
                  className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm"
                  placeholder="Explain why execution is being cancelled..."
                  disabled={isCaseCancelled || cancelSubmitting}
                />
              </div>
              <button
                type="button"
                onClick={() => void handleCancelCase()}
                disabled={isCaseCancelled || cancelSubmitting}
                className="inline-flex items-center justify-center rounded-md bg-red-600 text-white px-3 py-2 text-xs font-semibold hover:bg-red-700 disabled:opacity-50"
              >
                {isCaseCancelled ? "Case already cancelled" : cancelSubmitting ? "Cancelling..." : "Cancel execution"}
              </button>
            </div>
          </motion.div>

          {showDtp02ShortlistCard && (
            <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 border-b border-slate-200 p-4 flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2">
                  <Users className="w-4 h-4 text-sponsor-blue" />
                  Supplier shortlist · DTP-02
                </h3>
                <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500 bg-white border border-slate-200 px-2 py-1 rounded">
                  Demo view
                </span>
              </div>
              <div className="p-4 space-y-4">
                <p className="text-sm text-slate-600 leading-relaxed">
                  Everyone here is drawn from the <span className="font-semibold text-slate-800">same enterprise supplier catalog</span>, filtered by this case&apos;s category (<span className="font-mono text-xs">{displayCategory}</span>
                  ). RFx focus (primary / secondary / included) is a deterministic demo tier from KPI scores—mirroring how an agent would prioritize who to invite before RFx. Use{" "}
                  <span className="font-semibold text-slate-800">Add optional supplier</span> to simulate a name not yet in the catalog.
                </p>
                <div className="overflow-x-auto rounded-lg border border-slate-100">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        <th className="px-3 py-2">Supplier</th>
                        <th className="px-3 py-2">Risk</th>
                        <th className="px-3 py-2">KPI</th>
                        <th className="px-3 py-2">RFx focus</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dtp02ShortlistRows.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="px-3 py-6 text-center text-slate-500 italic">
                            No suppliers in catalog for this category yet — add an optional supplier below to simulate discovery.
                          </td>
                        </tr>
                      ) : (
                        dtp02ShortlistRows.map((row) => {
                          const badge =
                            row.roleKey === "primary"
                              ? "bg-blue-50 text-blue-800 border-blue-200"
                              : row.roleKey === "secondary"
                                ? "bg-amber-50 text-amber-900 border-amber-200"
                                : row.roleKey === "included"
                                  ? "bg-slate-50 text-slate-700 border-slate-200"
                                  : "bg-violet-50 text-violet-900 border-violet-200";
                          const roleLabel =
                            row.roleKey === "primary"
                              ? "Primary"
                              : row.roleKey === "secondary"
                                ? "Secondary"
                                : row.roleKey === "included"
                                  ? "Included"
                                  : "You added";
                          return (
                            <tr key={`${row.supplier_id}-${row.supplier_name}`} className="border-t border-slate-100 align-top">
                              <td className="px-3 py-2.5">
                                <span className="font-semibold text-slate-900">{row.supplier_name}</span>
                                <p className="text-[10px] font-mono text-slate-400 mt-0.5">{row.supplier_id}</p>
                                {row.notes ? (
                                  <p className="text-[11px] text-slate-500 mt-1 leading-snug max-w-md">{row.notes}</p>
                                ) : null}
                              </td>
                              <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap capitalize">{row.riskLabel}</td>
                              <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{row.fitLabel}</td>
                              <td className="px-3 py-2.5">
                                <span className={`inline-flex text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded border ${badge}`}>
                                  {roleLabel}
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-end rounded-lg bg-slate-50/80 border border-slate-100 p-3">
                  <div className="flex-1 min-w-[140px]">
                    <label className="block text-[10px] font-bold uppercase tracking-wide text-slate-500 mb-1">Optional supplier name</label>
                    <input
                      type="text"
                      value={optionalSupplierName}
                      onChange={(e) => setOptionalSupplierName(e.target.value)}
                      placeholder="e.g. Oracle Cloud Infrastructure"
                      className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400"
                    />
                  </div>
                  <div className="w-full sm:w-40">
                    <label className="block text-[10px] font-bold uppercase tracking-wide text-slate-500 mb-1">Note / region</label>
                    <input
                      type="text"
                      value={optionalSupplierRegion}
                      onChange={(e) => setOptionalSupplierRegion(e.target.value)}
                      placeholder="e.g. NA · EU"
                      className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={addDemoOptionalSupplier}
                    className="inline-flex items-center justify-center gap-1.5 rounded-md bg-sponsor-blue text-white px-3 py-2 text-xs font-bold shadow-sm hover:bg-blue-700 transition-colors sm:shrink-0"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    Add optional supplier
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 leading-snug">
                  Rows are loaded from your case category supplier list. Added rows are temporary and reset on refresh.
                </p>
              </div>
            </motion.div>
          )}

          {perfInsight && (
            <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 border-b border-slate-200 p-4 flex items-center justify-between gap-3">
                <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2">
                  <Activity className="w-4 h-4 text-sponsor-blue" />
                  Recent performance &amp; insight
                </h3>
                {perfInsight.handoffTag ? (
                  <span className="text-[10px] font-bold uppercase tracking-wide bg-amber-100 text-amber-900 px-2 py-1 rounded">
                    {perfInsight.handoffTag}
                  </span>
                ) : null}
              </div>
              <div className="p-4 space-y-4">
                <p className="text-[11px] text-slate-500">{perfInsight.period}</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {perfInsight.kpis.map((k, i) => (
                    <div key={i} className="rounded-lg border border-slate-100 bg-slate-50/80 p-3">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 leading-tight mb-1">{k.label}</p>
                      <p className="text-lg font-bold text-slate-900">{k.value}</p>
                      {k.hint ? <p className="text-[10px] text-slate-500 mt-0.5">{k.hint}</p> : null}
                    </div>
                  ))}
                </div>
                <ul className="space-y-2 text-sm text-slate-700 list-disc pl-5">
                  {perfInsight.bullets.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
                <p className="text-[10px] text-slate-400 leading-snug border-t border-slate-100 pt-3">{perfInsight.sourceNote}</p>
              </div>
            </motion.div>
          )}

          {hasLiveCase && activeStageFields.length > 0 && (
            <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 border-b border-slate-200 p-4">
                <h3 className="text-slate-800 font-bold text-sm">Human input workspace · {displayStage}</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Fill missing information directly here. ProcuraBot will guide completion and use this for draft generation.
                </p>
              </div>
              <div className="p-4 space-y-4">
                <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                  Manual entry is captured and persisted when you click <span className="font-semibold">Save stage input</span>. The same values are reused by ProcuraBot, generation checks, and stage progression.
                  <div className="mt-1 text-blue-800/90">
                    Examples: dates use <span className="font-mono">YYYY-MM-DD</span>, currency fields are numeric only, and boolean confirmations use <span className="font-mono">yes/no</span>.
                  </div>
                </div>
                <div
                  className={`rounded-md px-3 py-2 text-xs border ${
                    readinessState.readiness === "blocked"
                      ? "border-red-200 bg-red-50 text-red-900"
                      : readinessState.readiness === "ready_with_warnings"
                        ? "border-amber-200 bg-amber-50 text-amber-900"
                        : "border-emerald-200 bg-emerald-50 text-emerald-800"
                  }`}
                >
                  {readinessState.readiness === "blocked" && (
                    <>Blocked: critical fields missing — {readinessState.missingCritical.map((f) => f.label).join(", ")}</>
                  )}
                  {readinessState.readiness === "ready_with_warnings" && (
                    <>Ready with warnings: remaining required fields — {missingRequiredFields.map((f) => f.label).join(", ")}</>
                  )}
                  {readinessState.readiness === "ready" && <>Ready: required fields are complete for {displayStage}.</>}
                </div>

                {readinessState.readiness === "blocked" && readinessState.missingCritical.length > 0 && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-900">
                    <p className="font-semibold mb-1">Why blocked</p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {readinessState.missingCritical.map((f) => (
                        <li key={`blocked-${f.key}`}>
                          {f.label} ({f.key})
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {missingRequiredFields.length > 0 && (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                    Missing required fields: {missingRequiredFields.map((f) => f.label).join(", ")}
                  </div>
                )}

                {fieldBuckets.prefilled.length > 0 && (
                  <details className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <summary className="cursor-pointer text-xs font-semibold text-slate-700">
                      Known prefilled fields ({fieldBuckets.prefilled.length})
                    </summary>
                    <p className="text-[11px] text-slate-500 mt-1">
                      These values are already known from case context or earlier inputs.
                    </p>
                  </details>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {prioritizedStageFields.map((f: DtpFieldSchema) => (
                    <div key={f.key} className={f.multiline ? "lg:col-span-2" : ""}>
                      <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                        {f.label} {f.required ? <span className="text-red-500">*</span> : null}
                        {f.critical ? <span className="ml-1 text-[10px] text-red-600">(critical)</span> : null}
                        {!f.required && !f.critical ? <span className="ml-1 text-[10px] text-slate-500">(optional)</span> : null}
                        {f.ai_extractable ? <span className="ml-1 text-[10px] text-blue-600">(AI-extractable)</span> : null}
                      </label>
                      {f.multiline ? (
                        <textarea
                          value={stageInputValues[f.key] || ""}
                          onChange={(e) => setStageInputValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                          placeholder={f.placeholder}
                          rows={3}
                          className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm text-slate-700"
                        />
                      ) : (
                        <input
                          type={f.key.toLowerCase().includes("date") ? "date" : "text"}
                          value={stageInputValues[f.key] || ""}
                          onChange={(e) => setStageInputValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                          placeholder={f.placeholder}
                          className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm text-slate-700"
                        />
                      )}
                      {formatHintForField(f.key) ? (
                        <p className="mt-1 text-[11px] text-slate-500">{formatHintForField(f.key)}</p>
                      ) : null}
                      <p className="mt-1 text-[11px] text-slate-400">How this is used: {usageHintForField(f)}</p>
                    </div>
                  ))}
                </div>

                {fieldBuckets.optional.length > 0 && (
                  <details className="rounded-md border border-slate-200 bg-white px-3 py-2">
                    <summary className="cursor-pointer text-xs font-semibold text-slate-700">
                      Optional enhancement fields ({fieldBuckets.optional.length})
                    </summary>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Optional fields improve AI guidance quality but do not block critical progression.
                    </p>
                  </details>
                )}

                {(displayStage === "DTP-03" || displayStage === "DTP-04") && (
                  <div className="rounded-md border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold text-slate-700 mb-2">
                      Supplier feedback workspace (structured)
                    </p>
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 border border-slate-200">
                          <th className="px-2 py-1 border border-slate-200">Capture area</th>
                          <th className="px-2 py-1 border border-slate-200">Status</th>
                          <th className="px-2 py-1 border border-slate-200">How to update</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="px-2 py-1 border border-slate-200">Response receipt status</td>
                          <td className="px-2 py-1 border border-slate-200">{stageInputValues.supplier_response_received ? "Captured" : "Missing"}</td>
                          <td className="px-2 py-1 border border-slate-200">Field + chat extraction</td>
                        </tr>
                        <tr>
                          <td className="px-2 py-1 border border-slate-200">Clarification / evaluation notes</td>
                          <td className="px-2 py-1 border border-slate-200">
                            {stageInputValues.supplier_clarification_feedback || stageInputValues.supplier_evaluation_feedback ? "Captured" : "Missing"}
                          </td>
                          <td className="px-2 py-1 border border-slate-200">Paste supplier feedback then extract</td>
                        </tr>
                        <tr>
                          <td className="px-2 py-1 border border-slate-200">Negotiation deltas</td>
                          <td className="px-2 py-1 border border-slate-200">{stageInputValues.negotiation_feedback ? "Captured" : "Missing"}</td>
                          <td className="px-2 py-1 border border-slate-200">Manual input + copilot refinement</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3 space-y-2">
                  <label className="block text-xs font-semibold text-slate-700">
                    Extract structured updates from chat or pasted feedback
                  </label>
                  <textarea
                    value={extractSourceText}
                    onChange={(e) => setExtractSourceText(e.target.value)}
                    rows={2}
                    placeholder="Paste supplier feedback or leave blank to use last assistant response..."
                    className="w-full rounded-md border border-slate-200 px-2.5 py-2 text-sm text-slate-700 bg-white"
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void extractToStructuredFields()}
                      disabled={stageExtractBusy}
                      className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 px-3 py-1.5 text-xs font-semibold hover:bg-slate-100 disabled:opacity-50"
                    >
                      {stageExtractBusy ? "Extracting..." : "Extract to fields"}
                    </button>
                    {extractPreview && (
                      <button
                        type="button"
                        onClick={() => void applyExtractPreview()}
                        className="inline-flex items-center justify-center rounded-md bg-emerald-600 text-white px-3 py-1.5 text-xs font-semibold hover:bg-emerald-700"
                      >
                        Confirm AI extraction
                      </button>
                    )}
                  </div>
                  {extractPreview && (
                    <pre className="text-[11px] rounded border border-emerald-200 bg-emerald-50 p-2 overflow-x-auto">
                      {JSON.stringify(extractPreview, null, 2)}
                    </pre>
                  )}
                </div>

                <div className="sticky bottom-0 z-10 -mx-4 mt-2 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
                  <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void saveStageIntake("human_form")}
                    disabled={stageInputBusy}
                    className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 px-3 py-2 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                  >
                    {stageInputBusy ? "Saving..." : "Save stage input"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void sendStructuredInputToCopilot()}
                    disabled={stageInputSubmitting}
                    className="inline-flex items-center justify-center rounded-md bg-sponsor-blue text-white px-3 py-2 text-xs font-semibold hover:bg-blue-700 disabled:opacity-50"
                  >
                    {stageInputSubmitting ? "Sending..." : "Send structured input to ProcuraBot"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void generateDraftFromStructuredInput("rfx")}
                    disabled={draftGeneratingRole != null || readinessState.readiness === "blocked"}
                    className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 px-3 py-2 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                  >
                    {draftGeneratingRole === "rfx" ? "Generating..." : "Generate RFx draft"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void generateDraftFromStructuredInput("contract")}
                    disabled={draftGeneratingRole != null || readinessState.readiness === "blocked"}
                    className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 px-3 py-2 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                  >
                    {draftGeneratingRole === "contract" ? "Generating..." : "Generate contract draft"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void advanceStage()}
                    disabled={advanceSubmitting || readinessState.readiness === "blocked"}
                    className="inline-flex items-center justify-center rounded-md bg-emerald-600 text-white px-3 py-2 text-xs font-semibold hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {advanceSubmitting ? "Advancing..." : "Advance stage"}
                  </button>
                  </div>
                  {advanceMessage ? (
                    <p className="mt-2 text-xs text-slate-600">{advanceMessage}</p>
                  ) : null}
                </div>
              </div>
            </motion.div>
          )}

          {hasLiveCase && (
            <motion.div variants={item}>
              <FutureStageRequirements
                stages={DTP_STAGES}
                currentStageId={displayStage}
                stageValuesByStage={stageValuesByStage}
              />
            </motion.div>
          )}

          {hasLiveCase && (
            <details className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden group">
              <summary className="list-none cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-sponsor-blue" />
                  Case documents
                </span>
                <span className="text-[11px] text-slate-500">Expand when needed</span>
              </summary>
              <div className="p-4 space-y-3">
                <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
                  {([
                    ["uploads", "Case uploads"],
                    ["generated", "Generated outputs"],
                    ["internal", "Internal references"],
                  ] as const).map(([k, lbl]) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setDocumentsTab(k)}
                      className={`px-2.5 py-1.5 rounded text-[11px] font-semibold inline-flex items-center gap-1.5 ${
                        documentsTab === k ? "bg-sponsor-blue text-white" : "text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      <span>{lbl}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${documentsTab === k ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"}`}>
                        {k === "uploads" ? documentsCenter.uploads.length : k === "generated" ? documentsCenter.generated_outputs.length : documentsCenter.internal_references.length}
                      </span>
                    </button>
                  ))}
                </div>

                <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
                  <input
                    type="text"
                    value={documentsQuery}
                    onChange={(e) => setDocumentsQuery(e.target.value)}
                    placeholder="Search files..."
                    className="flex-1 rounded-md border border-slate-200 px-2.5 py-2 text-sm text-slate-700 placeholder:text-slate-400"
                  />
                  <select
                    value={documentsTypeFilter}
                    onChange={(e) => setDocumentsTypeFilter(e.target.value as typeof documentsTypeFilter)}
                    className="rounded-md border border-slate-200 px-2.5 py-2 text-sm text-slate-700 bg-white"
                  >
                    <option value="all">All types</option>
                    <option value="pdf">PDF</option>
                    <option value="docx">DOCX</option>
                    <option value="xlsx">XLSX</option>
                    <option value="bundle">Bundle</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                {packExportError ? (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{packExportError}</p>
                ) : null}
                {documentsTab === "uploads" && (
                  <ul className="space-y-2">
                    {filteredDocuments.length === 0 ? (
                      <li className="text-sm text-slate-500 italic">No uploads yet. Attach files in chat to add context.</li>
                    ) : (
                      filteredDocuments.map((doc) => (
                        <li key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-900 truncate">{doc.filename}</p>
                            <p className="text-[11px] text-slate-500">{doc.document_type || "Document"}{doc.updated_at ? ` · ${doc.updated_at}` : ""}</p>
                          </div>
                          <span className="text-[10px] font-bold uppercase tracking-wide bg-white border border-slate-200 px-2 py-1 rounded text-slate-600">
                            {doc.file_type || "file"}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                )}
                {documentsTab === "internal" && (
                  <ul className="space-y-2">
                    {filteredDocuments.length === 0 ? (
                      <li className="text-sm text-slate-500 italic">No internal references found for this case yet.</li>
                    ) : (
                      filteredDocuments.map((doc) => (
                        <li key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-900 truncate">{doc.filename}</p>
                            <p className="text-[11px] text-slate-500">
                              {doc.document_type || "Reference"}
                              {doc.updated_at ? ` · ${doc.updated_at}` : ""}
                            </p>
                          </div>
                          <span className="text-[10px] font-bold uppercase tracking-wide bg-blue-50 border border-blue-200 px-2 py-1 rounded text-blue-700">
                            Internal
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                )}
                {documentsTab === "generated" && (
                  <ul className="space-y-3">
                    {filteredDocuments.length === 0 ? (
                      <li className="text-sm text-slate-500 italic">No generated outputs yet. Ask ProcuraBot to draft an RFx first.</li>
                    ) : (
                      filteredDocuments.map((row) => (
                        <li
                          key={row.id}
                          className="rounded-lg border border-slate-100 bg-slate-50/80 p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-900 truncate">
                              {getFriendlyArtifactSourceName(row.source)}
                            </p>
                            <p className="text-[11px] text-slate-500 font-mono truncate mt-0.5">{row.pack_id || row.id}</p>
                            <p className="text-[11px] text-slate-500 mt-1">
                              {row.artifact_count != null ? `${row.artifact_count} file(s)` : "—"}
                              {row.updated_at ? ` · ${row.updated_at}` : ""}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2 shrink-0">
                            {(["md", "docx", "pdf"] as const).map((fmt) => (
                              <button
                                key={fmt}
                                type="button"
                                disabled={packExportLoading !== null || !row.pack_id}
                                onClick={async () => {
                                  if (!row.pack_id) return;
                                  setPackExportError(null);
                                  const key = `${row.pack_id}-${fmt}`;
                                  setPackExportLoading(key);
                                  try {
                                    await downloadArtifactPackExport(caseId, row.pack_id, fmt);
                                  } catch (e) {
                                    setPackExportError(e instanceof Error ? e.message : "Export failed.");
                                  } finally {
                                    setPackExportLoading(null);
                                  }
                                }}
                                className="inline-flex items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                              >
                                {packExportLoading === `${row.pack_id}-${fmt}` ? "…" : <Download className="w-3 h-3" />}
                                {fmt}
                              </button>
                            ))}
                          </div>
                        </li>
                      ))
                    )}
                  </ul>
                )}
              </div>
            </details>
          )}


          <details className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden group">
            <summary className="list-none cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-sponsor-blue" />
                Decision audit
              </span>
              <span className="text-[11px] text-slate-500">Expand when needed</span>
            </summary>
            <div className="p-4">
              {decisionAuditRows.length === 0 ? (
                <p className="text-sm text-slate-500 italic">No recorded decisions yet for this case.</p>
              ) : (
                <ul className="space-y-2">
                  {decisionAuditRows.slice(0, 12).map((r, idx) => (
                    <li key={`${r.stage}-${r.question}-${idx}`} className="rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                      <p className="text-xs text-slate-500">
                        {r.stage} · {r.when || "Time not captured"}
                      </p>
                      <p className="text-sm text-slate-800 mt-1">
                        <span className="font-semibold capitalize">{r.question}:</span> {r.answer}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">By: {r.by}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </details>

          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border-2 border-slate-200 overflow-hidden">
            <div className="bg-slate-50 p-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-slate-800 font-bold text-[15px] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sponsor-blue" />
                Decision checklist · {displayStage}
              </h3>
            </div>
            <div className="p-6">
              <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                <strong>{displayStage}</strong>
                {readinessState.readiness === "blocked"
                  ? " — Progression is blocked until critical stage fields are completed."
                  : focus?.pending_questions?.length
                  ? " — Answer step-by-step in ProcuraBot chat (this same window). When all prompts are complete, type yes or approve to confirm this stage."
                  : " — Open questions look resolved in chat. Type approve when you are ready to move to the next stage."}
              </p>
              <p className="text-xs text-slate-500 mb-4">
                Use this panel for evidence and context; all formal decisions run through chat—try **reject** or **request revision** if you need a new pass.
              </p>

              {stageDecisionComplete ? (
                <div className="bg-green-50 text-green-800 p-6 rounded-lg text-center border border-green-200">
                  <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h4 className="font-bold text-lg mb-1">Stage answers recorded</h4>
                  <p className="text-sm text-green-700">
                    This stage&apos;s checklist is saved on the server. Continue in chat; the workflow may advance after approval.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 text-sm text-slate-700">
                  {focus?.pending_questions?.length ? (
                    <ul className="list-disc pl-5 space-y-2">
                      {(focus.pending_questions as { text?: string }[]).map((pq, i) => (
                        <li key={i}>{pq.text || "Pending question"}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>No open checklist items. If you are ready, type <span className="font-semibold">approve</span> in chat.</p>
                  )}
                </div>
              )}
            </div>
          </motion.div>

          <details className="bg-[#0A0C10] rounded-xl border border-slate-800 overflow-hidden mb-12 group">
            <summary className="cursor-pointer list-none flex items-center justify-between px-4 py-3 bg-slate-900/80 text-white font-bold text-[13px]">
              <span className="flex items-center gap-2 font-syne tracking-wide">
                <Terminal className="w-4 h-4 text-emerald-400" />
                System activity ({caseDetails?.activity_log?.length ?? 0}) — expand for details
              </span>
              <ChevronRight className="w-4 h-4 text-slate-400 group-open:rotate-90 transition-transform" />
            </summary>
            <div className="p-4 max-h-48 overflow-y-auto space-y-2.5 font-mono text-[11.5px] text-slate-300 select-text">
              {caseDetails?.activity_log && caseDetails.activity_log.length > 0 ? caseDetails.activity_log.map((log: any, i: number) => (
                <div key={i} className="flex gap-3 border-b border-slate-800/40 pb-2 last:border-0">
                  <span className="text-slate-500 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                  <span className="text-emerald-400 font-semibold shrink-0">{log.agent_name || "System"}:</span>
                  <span className="text-slate-400 break-words">{log.output_summary || log.task_name || "…"}</span>
                </div>
              )) : (
                <p className="text-slate-500 italic text-center py-4">No agent steps yet.</p>
              )}
              <div ref={logEndRef} />
            </div>
          </details>

            </>
          )}
        </motion.div>
      </div>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize ProcuraBot panel"
        title="Drag to resize ProcuraBot panel"
        onMouseDown={() => {
          isResizingChatPanelRef.current = true;
          document.body.style.cursor = "col-resize";
          document.body.style.userSelect = "none";
        }}
        onDoubleClick={() => setChatPanelWidthPct(40)}
        className="w-2 shrink-0 cursor-col-resize bg-slate-100 hover:bg-slate-200 active:bg-slate-300 border-l border-r border-slate-200"
      />

      {/* RIGHT PANEL: ProcuraBot Chat (Resizable) */}
      <div className="flex flex-col h-full bg-white shadow-2xl z-20" style={{ width: `${chatPanelWidthPct}%` }}>
        
        {/* Chat Header */}
        <header className="px-6 py-4 border-b border-slate-100 bg-white space-y-3">
          <ProcuraBotIdentity
            subtitle={
              hasLiveCase
                ? `${displayStage}${focus?.stage_title ? ` · ${focus.stage_title}` : ""}`
                : caseLoading
                  ? "Loading…"
                  : "Select a case to begin"
            }
          />
          <div className="flex items-center gap-2">
            <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700">
              Context scope
            </span>
            <span className="text-xs text-slate-600">
              {hasLiveCase ? `Case-level (${displayStage})` : "Portfolio-level"}
            </span>
          </div>
          {hasLiveCase && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500 mb-1">What ProcuraBot remembers</p>
              <div className="flex flex-wrap gap-1.5">
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-slate-200 bg-white text-slate-700">
                  Stage fields: {Object.keys(stageInputValues).filter((k) => String(stageInputValues[k] || "").trim()).length}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-slate-200 bg-white text-slate-700">
                  Extraction: {extractPreview ? "proposal pending confirm" : "none pending"}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-slate-200 bg-white text-slate-700">
                  Working drafts: {((caseDetails?.working_documents?.rfx?.plain_text ? 1 : 0) + (caseDetails?.working_documents?.contract?.plain_text ? 1 : 0))}/2
                </span>
              </div>
            </div>
          )}
          {hasLiveCase && suggestedChatPrompts.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {suggestedChatPrompts.map((q, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => { setInput(q); setTimeout(() => document.getElementById("send-btn")?.click(), 50); }}
                  className="text-left text-[11px] font-medium px-2.5 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-sponsor-blue hover:text-white border border-slate-200 transition-colors max-w-[100%] line-clamp-2"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </header>

        {/* Messages body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[url('https://www.transparenttextures.com/patterns/tiny-grid.png')]">
          {caseLoading ? (
            <div className="flex flex-col items-center justify-center min-h-[40%] text-slate-500 text-sm">Loading case…</div>
          ) : !hasLiveCase ? (
            <div className="flex flex-col items-center justify-center min-h-[40%] text-center text-slate-600 px-4">
              <MessageSquare className="w-10 h-10 text-slate-300 mb-3 shrink-0" />
              <p className="text-sm max-w-sm leading-relaxed">
                Chat turns on once a case is loaded. Open the{" "}
                <a href="/cases" className="text-sponsor-blue font-semibold underline underline-offset-2">
                  Case Dashboard
                </a>{" "}
                and choose a case to open {PROCURABOT_BRAND.name}.
              </p>
            </div>
          ) : (
            <>
              <div className="text-center pb-4">
                <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-3 py-1 rounded-full uppercase tracking-widest border border-slate-200">
                  {PROCURABOT_BRAND.shortName} Session Started
                </span>
              </div>

              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  {msg.role === "assistant" && (
                    <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mr-3 mt-1 shrink-0">
                      <MessageSquare className="w-4 h-4 text-sponsor-blue" />
                    </div>
                  )}
                  <div
                    className={`max-w-[85%] p-4 text-[15px] leading-relaxed shadow-sm ${
                      msg.role === "user"
                        ? "bg-sponsor-blue text-white rounded-2xl rounded-tr-sm"
                        : "bg-white border border-slate-200 text-slate-700 rounded-2xl rounded-tl-sm shadow-[0_2px_10px_-3px_rgba(6,81,237,0.1)] break-words"
                    }`}
                  >
                    {msg.role === "assistant" ? renderMessageContent(msg.content) : msg.content}
                    {msg.role === "assistant" && (
                      <div className="mt-3 pt-2 border-t border-slate-100">
                        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/90 px-3 py-2">
                        <span className="text-[11px] font-medium text-slate-500">Rate this response</span>
                        <button
                          type="button"
                          disabled={msgVoteBusyIdx === i}
                          onClick={() => void submitAssistantVote(i, String(msg.content || ""), "up")}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                            msgVoteByIdx[i] === "up"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-300 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:border-emerald-200 hover:text-emerald-700"
                          }`}
                        >
                          <ThumbsUp className="w-3 h-3" />
                          Useful
                        </button>
                        <button
                          type="button"
                          disabled={msgVoteBusyIdx === i}
                          onClick={() => void submitAssistantVote(i, String(msg.content || ""), "down")}
                          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition ${
                            msgVoteByIdx[i] === "down"
                              ? "bg-rose-50 text-rose-700 border-rose-300 shadow-sm"
                              : "bg-white text-slate-600 border-slate-200 hover:border-rose-200 hover:text-rose-700"
                          }`}
                        >
                          <ThumbsDown className="w-3 h-3" />
                          Needs work
                        </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isTyping && (
                <div className="flex justify-start">
                  <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mr-3 mt-1 shrink-0">
                    <MessageSquare className="w-4 h-4 text-sponsor-blue" />
                  </div>
                  <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm p-4 flex gap-1 items-center">
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"></div>
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100">
          {chatFiles.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {chatFiles.map((f, idx) => (
                <span
                  key={`${f.name}-${idx}`}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600"
                >
                  <Paperclip className="w-3 h-3" />
                  <span className="max-w-[220px] truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => setChatFiles((prev) => prev.filter((_, i) => i !== idx))}
                    className="text-slate-400 hover:text-slate-600"
                    aria-label={`Remove ${f.name}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2 p-1.5 bg-slate-50 border border-slate-300 rounded-xl focus-within:ring-2 focus-within:ring-sponsor-blue/20 focus-within:border-sponsor-blue transition-all shadow-inner">
            <input
              ref={chatFileInputRef}
              type="file"
              multiple
              accept=".docx,.pdf,.txt,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp"
              className="hidden"
              onChange={(e) => {
                const picked = Array.from(e.target.files || []);
                if (picked.length > 0) setChatFiles((prev) => [...prev, ...picked]);
                e.target.value = "";
              }}
              disabled={isTyping || !hasLiveCase || caseLoading}
            />
            <button
              type="button"
              onClick={() => chatFileInputRef.current?.click()}
              disabled={isTyping || !hasLiveCase || caseLoading}
              className="p-2 text-slate-500 hover:text-sponsor-blue rounded-lg disabled:opacity-50"
              aria-label="Attach files"
              title="Attach files"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <textarea 
              className="flex-1 bg-transparent resize-none outline-none py-2.5 px-3 text-[15px] text-slate-900 placeholder:text-slate-400"
              rows={1}
              placeholder="Ask ProcuraBot or attach files..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { 
                  e.preventDefault(); 
                  handleSend(); 
                }
              }}
              disabled={isTyping || !hasLiveCase || caseLoading}
            />
            <button 
              id="send-btn"
              className="p-3 bg-sponsor-blue text-white rounded-lg hover:bg-blue-700 transition shadow-md disabled:opacity-50 disabled:cursor-not-allowed m-0.5"
              onClick={handleSend}
              disabled={(!input.trim() && chatFiles.length === 0) || isTyping || !hasLiveCase || caseLoading}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
              </svg>
            </button>
          </div>
          <p className="text-center text-[11px] text-slate-400 font-medium mt-3 flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            AI-generated content. Confirm decisions in chat; validate material choices with your policy owners.
          </p>
        </div>

      </div>
    </div>
  );
}
