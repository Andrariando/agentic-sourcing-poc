"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, AlertTriangle, FileText, ShieldCheck, ChevronRight, MessageSquare, Briefcase, Clock, Terminal } from "lucide-react";
import { motion } from "framer-motion";
import { buildDecisionDataForStage } from "@/lib/dtp-approve-defaults";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";

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

function buildAssistantWelcome(data: any): string {
  const name = data.name || "this case";
  const stage = data.dtp_stage || "DTP-01";
  const focus = data.copilot_focus;
  const title = focus?.stage_title ? ` — ${focus.stage_title}` : "";
  let msg = `I'm your Supervisor for **${name}**. We're in **${stage}${title}**.\n\n`;
  if (focus?.stage_description) msg += `${focus.stage_description}\n\n`;
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

/** Copilot governance SOC2 / infra attestations saved by /api/decisions/approve */
function isGovernanceCompleteOnServer(caseDetails: any): boolean {
  const stage = caseDetails?.dtp_stage;
  if (!stage || !caseDetails?.human_decision?.[stage]) return false;
  const row = caseDetails.human_decision[stage];
  return Boolean(
    readDecisionAnswer(row.governance_soc2_status) &&
      readDecisionAnswer(row.governance_infra_status)
  );
}

export default function LegacyCaseCopilotPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [caseDetails, setCaseDetails] = useState<any>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [governanceApproved, setGovernanceApproved] = useState(false);
  const [govSoc2, setGovSoc2] = useState<"verified" | "pending" | "">("");
  const [govInfra, setGovInfra] = useState<"meets" | "exemption" | "">("");
  const [isTyping, setIsTyping] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const initialChatHydrated = useRef(false);

  useEffect(() => {
    if (caseDetails && !isGovernanceCompleteOnServer(caseDetails)) {
      setGovernanceApproved(false);
    }
  }, [caseDetails?.case_id, caseDetails?.dtp_stage, caseDetails?.human_decision]);

  const showEvalApproved =
    (caseDetails && isGovernanceCompleteOnServer(caseDetails)) || governanceApproved;

  const container: any = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } };
  const item: any = { hidden: { opacity: 0, y: 15 }, show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } } };

  // 1. Fetch Case Details & Chat History (poll only updates case meta — never resets chat)
  useEffect(() => {
    initialChatHydrated.current = false;

    async function fetchCase(isPoll: boolean) {
      try {
        const url = `${getApiBaseUrl()}/api/cases/${caseId}`;
        const res = await apiFetch(url);
        if (!res.ok) {
          if (!isPoll) setCaseError("Case not found or API error.");
          return;
        }
        const data = await res.json();
        setCaseDetails(data);

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
        if (!isPoll) setCaseError("Network error attempting to fetch case.");
      }
    }
    
    // 2. Fetch Documents
    async function fetchDocs() {
      try {
        const url = `${getApiBaseUrl()}/api/documents`;
        const res = await apiFetch(url);
        const data = await res.json();
        if (data.documents) {
            setDocuments(data.documents);
        }
      } catch (err) {
        console.error("Failed to fetch documents:", err);
      }
    }

    if (caseId) {
      fetchCase(false);
      fetchDocs();
      const interval = setInterval(() => fetchCase(true), 5000);
      return () => clearInterval(interval);
    }
  }, [caseId]);

  // Auto-scroll the process log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [caseDetails?.activity_log]);

  // 3. Handle Live Chat
  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setInput("");
    setIsTyping(true);
    
    try {
      const url = `${getApiBaseUrl()}/api/chat`;
        
      const res = await apiFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          user_message: userMsg,
          use_tier_2: true
        })
      });
      
      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        // Find the last assistant message
        const lastMsg = [...data.messages].reverse().find(m => m.role === "assistant" || m.role === "ai");
        if (lastMsg) {
            setMessages(prev => [...prev, { role: "assistant", content: lastMsg.content }]);
        }
      } else if (data.assistant_message) {
         setMessages(prev => [...prev, { role: "assistant", content: data.assistant_message }]);
      } else if (data.response) {
         setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: "assistant", content: "Error: Could not reach the LangGraph Backend API." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleDocumentClick = (filename: string) => {
     alert(`Feature coming soon: Download/Preview for ${filename}`);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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
    
    if (matches.length === 0) return content;
    
    const cleanContent = content.replace(actionRegex, '').trim();
    
    return (
      <div className="flex flex-col gap-3">
        <span>{cleanContent}</span>
        <div className="flex flex-wrap gap-2 mt-1">
           {matches.map((match, idx) => (
             <button 
               key={idx} 
               onClick={() => { setInput(match[1]); setTimeout(() => document.getElementById("send-btn")?.click(), 100); }}
               className="bg-white text-sponsor-blue border border-sponsor-blue/30 px-3 py-1.5 rounded-full text-[11px] font-bold tracking-wide hover:bg-sponsor-blue hover:text-white transition-colors shadow-sm"
             >
               ⚡ {match[1]}
             </button>
           ))}
        </div>
      </div>
    );
  };

  // 4. Governance Approval
  const handleApproveGovernance = async () => {
    if (govSoc2 !== "verified" || govInfra !== "meets") {
      alert("Please confirm SOC2 verification and that IT infrastructure meets thresholds before approving.");
      return;
    }

    const stage = caseDetails?.dtp_stage || "DTP-01";
    const stagePayload = buildDecisionDataForStage(stage, caseDetails?.supplier_id);
    if (!stagePayload) {
      alert(`No decision schema for stage ${stage}. Check API / case state.`);
      return;
    }

    const decision_data = {
      ...stagePayload,
      governance_soc2_status: govSoc2 === "verified" ? "Yes, Verified" : govSoc2,
      governance_infra_status: govInfra === "meets" ? "Meets Thresholds" : govInfra,
    };

    try {
      const url = `${getApiBaseUrl()}/api/decisions/approve`;
        
      const res = await apiFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          decision: "Approve",
          reason: "Approved via Next.js Copilot UI",
          decision_data,
        })
      });
      if (res.ok) {
        setGovernanceApproved(true);
      } else {
        let detail = res.statusText || `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body?.detail) {
            detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
          }
        } catch {
          /* ignore */
        }
        alert(`Could not approve: ${detail}`);
      }
    } catch(err) {
      console.error(err);
      alert(`Network error.\n\nAPI base: ${getApiBaseUrl()}${apiConnectivityHint()}`);
    }
  };

  const displayName = caseDetails?.name || "Loading Case...";
  const displayCategory = caseDetails?.category_id || "Category";
  const displayStage = caseDetails?.dtp_stage || "DTP-01";
  
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
  const suggestedChatPrompts: string[] = (focus?.suggested_chat_prompts as string[]) || [];

  if (caseError) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-slate-50">
        <AlertTriangle className="w-16 h-16 text-mit-red mb-4" />
        <h1 className="text-2xl font-bold font-syne text-slate-800 mb-2">Case Not Found</h1>
        <p className="text-slate-600 mb-6">{caseError}</p>
        <button onClick={() => window.location.href = '/heatmap'} className="px-6 py-2 bg-sponsor-blue text-white rounded-lg font-bold">
          Return to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden w-full m-0 p-0 font-sans">
      
      {/* LEFT PANEL: Case Details (60%) */}
      <div className="w-[60%] flex flex-col h-full overflow-y-auto bg-slate-50/50 border-r border-slate-200">
        
        {/* Condensed Header */}
        <div className="bg-sponsor-blue text-white p-6 sticky top-0 z-10 shadow-md flex justify-between items-center shrink-0">
          <div>
            <h1 className="text-2xl font-bold tracking-tight mb-1 font-syne">{displayName}</h1>
            <div className="flex items-center gap-3 text-sm text-blue-100 font-medium">
              <span>{caseId}</span>
              <span>•</span>
              <span className="bg-blue-800/50 px-2 py-0.5 rounded text-white flex items-center gap-1.5 border border-blue-400/30">
                <Briefcase className="w-3.5 h-3.5" />
                {displayCategory}
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className="bg-sponsor-orange text-white px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest shadow-sm">
              In Progress
            </span>
          </div>
        </div>

        <motion.div variants={container} initial="hidden" animate="show" className="p-8 space-y-6 flex-1">
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
                  {strategyConfidence ? ` (${strategyConfidence} confidence)` : ""}
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
                <p className="text-sm text-slate-400 italic">No key findings yet—upload a document or ask Copilot to analyze.</p>
              )}
              {riskAssessment && (
                <p className="text-sm text-slate-700 mt-3 pt-3 border-t border-slate-100"><span className="font-semibold">Risk note:</span> {riskAssessment}</p>
              )}
            </div>
          </motion.div>

          <details className="bg-white rounded-xl border border-slate-200 shadow-sm group">
            <summary className="cursor-pointer list-none flex items-center gap-2 px-4 py-3 font-bold text-sm text-slate-800 border-b border-slate-100">
              <ChevronRight className="w-4 h-4 text-slate-400 group-open:rotate-90 transition-transform" />
              <FileText className="w-4 h-4 text-slate-400" />
              Supporting documents ({documents.length})
            </summary>
            <div className="p-4 pt-0">
              <ul className="space-y-2">
                {documents.length > 0 ? (
                  documents.map((doc, idx) => {
                    const ext = doc.filename.split(".").pop()?.toUpperCase() || "DOC";
                    const isPdf = ext === "PDF";
                    return (
                      <li key={idx} onClick={() => handleDocumentClick(doc.filename)} className="flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg cursor-pointer text-sm">
                        <span className={`font-bold text-[10px] px-2 py-0.5 rounded ${isPdf ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>{ext}</span>
                        <span className="flex-1 truncate ml-2 text-sponsor-blue">{doc.filename}</span>
                      </li>
                    );
                  })
                ) : (
                  <li className="text-sm text-slate-400 italic py-2">None yet.</li>
                )}
                <li className="relative border-2 border-dashed border-slate-200 rounded-lg p-2 mt-2">
                  <input type="file" onChange={handleFileUpload} disabled={isUploading} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" />
                  <span className="text-sm text-slate-500">{isUploading ? "Uploading…" : "Upload PDF / XLSX"}</span>
                </li>
              </ul>
            </div>
          </details>

          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border-2 border-slate-200 overflow-hidden">
            <div className="bg-slate-50 p-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-slate-800 font-bold text-[15px] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sponsor-blue" />
                Governance · {displayStage}
              </h3>
            </div>
            <div className="p-6">
              <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                <strong>{displayStage}</strong>
                {focus?.pending_questions?.length
                  ? " — Discuss tradeoffs in Copilot first if you want, then record IT risk attestations below before approving."
                  : " — Formal checklist for this stage looks complete; attest below if your process still requires it."}
              </p>
              <p className="text-xs text-slate-500 mb-4">SOC2 and infrastructure gates apply before you confirm.</p>

              {showEvalApproved ? (
                <div className="bg-green-50 text-green-800 p-6 rounded-lg text-center border border-green-200">
                  <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h4 className="font-bold text-lg mb-1">Evaluation Approved</h4>
                  <p className="text-sm text-green-700">Recorded. Workflow will advance from {displayStage} when the backend processes this approval.</p>
                </div>
              ) : (
                <div className="space-y-6">
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Has InfoSec verified the SOC2 compliance? *</label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input type="radio" name="soc" checked={govSoc2 === "verified"} onChange={() => setGovSoc2("verified")} className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" />
                        Yes, Verified
                      </label>
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input type="radio" name="soc" checked={govSoc2 === "pending"} onChange={() => setGovSoc2("pending")} className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" />
                        Pending / Missing
                      </label>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Does this supplier meet minimum IT Infrastructure thresholds? *</label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input type="radio" name="thresh" checked={govInfra === "meets"} onChange={() => setGovInfra("meets")} className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" />
                        Meets Thresholds
                      </label>
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                        <input type="radio" name="thresh" checked={govInfra === "exemption"} onChange={() => setGovInfra("exemption")} className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" />
                        Does Not Meet (Requires Exemption)
                      </label>
                    </div>
                  </div>
                  
                  <div className="flex gap-4 pt-4 border-t border-slate-100">
                     <button onClick={handleApproveGovernance} className="flex-1 py-3 bg-sponsor-blue text-white rounded-lg font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 hover:-translate-y-0.5 transition-all">
                       ✅ Confirm & Approve Eval
                     </button>
                     <button className="flex-1 py-3 bg-white text-slate-600 border-2 border-slate-200 rounded-lg font-bold hover:bg-slate-50 hover:text-slate-800 transition">
                       ↩️ Request Revision
                     </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>

          <details className="bg-[#0A0C10] rounded-xl border border-slate-800 overflow-hidden mb-12 group">
            <summary className="cursor-pointer list-none flex items-center justify-between px-4 py-3 bg-slate-900/80 text-white font-bold text-[13px]">
              <span className="flex items-center gap-2 font-syne tracking-wide">
                <Terminal className="w-4 h-4 text-emerald-400" />
                Agent activity ({caseDetails?.activity_log?.length ?? 0}) — expand if debugging
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

        </motion.div>
      </div>

      {/* RIGHT PANEL: Copilot Chat (40%) */}
      <div className="w-[40%] flex flex-col h-full bg-white shadow-2xl z-20">
        
        {/* Chat Header */}
        <header className="px-6 py-4 border-b border-slate-100 bg-white space-y-3">
          <div className="flex items-center gap-3">
             <div className="w-8 h-8 rounded-lg bg-sponsor-blue flex items-center justify-center shadow-md">
               <MessageSquare className="w-4 h-4 text-white" />
             </div>
             <div>
               <h2 className="text-lg font-bold text-slate-900 leading-tight">Case Copilot</h2>
               <p className="text-xs text-slate-500 font-medium">{displayStage}{focus?.stage_title ? ` · ${focus.stage_title}` : ""}</p>
             </div>
          </div>
          {suggestedChatPrompts.length > 0 && (
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
          <div className="text-center pb-4">
             <span className="text-[10px] font-bold text-slate-400 bg-slate-100 px-3 py-1 rounded-full uppercase tracking-widest border border-slate-200">Session Started</span>
          </div>
          
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center mr-3 mt-1 shrink-0">
                  <MessageSquare className="w-4 h-4 text-sponsor-blue" />
                </div>
              )}
              <div className={`max-w-[85%] p-4 text-[15px] leading-relaxed shadow-sm ${
                msg.role === "user" 
                ? "bg-sponsor-blue text-white rounded-2xl rounded-tr-sm" 
                : "bg-white border border-slate-200 text-slate-700 rounded-2xl rounded-tl-sm shadow-[0_2px_10px_-3px_rgba(6,81,237,0.1)] break-words"
              }`}>
                {msg.role === "assistant" ? renderMessageContent(msg.content) : msg.content}
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
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100">
          <div className="flex items-end gap-2 p-1.5 bg-slate-50 border border-slate-300 rounded-xl focus-within:ring-2 focus-within:ring-sponsor-blue/20 focus-within:border-sponsor-blue transition-all shadow-inner">
            <textarea 
              className="flex-1 bg-transparent resize-none outline-none py-2.5 px-3 text-[15px] text-slate-900 placeholder:text-slate-400"
              rows={1}
              placeholder="Ask Copilot a question or attach files..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { 
                  e.preventDefault(); 
                  handleSend(); 
                }
              }}
              disabled={isTyping}
            />
            <button 
              id="send-btn"
              className="p-3 bg-sponsor-blue text-white rounded-lg hover:bg-blue-700 transition shadow-md disabled:opacity-50 disabled:cursor-not-allowed m-0.5"
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
              </svg>
            </button>
          </div>
          <p className="text-center text-[11px] text-slate-400 font-medium mt-3 flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            AI-generated content. Validate with Governance Console before approving.
          </p>
        </div>

      </div>
    </div>
  );
}
