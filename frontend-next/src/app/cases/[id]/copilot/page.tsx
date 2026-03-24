"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { CheckCircle2, AlertTriangle, FileText, Activity, ShieldCheck, ChevronRight, MessageSquare, Briefcase, Clock, Terminal } from "lucide-react";
import { motion } from "framer-motion";
import { buildDecisionDataForStage } from "@/lib/dtp-approve-defaults";
import { apiFetch } from "@/lib/api-fetch";
import { getApiBaseUrl, apiConnectivityHint } from "@/lib/api-base";

export default function LegacyCaseCopilotPage() {
  const params = useParams();
  const caseId = params.id as string;

  const [caseDetails, setCaseDetails] = useState<any>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [messages, setMessages] = useState([
    { role: "assistant", content: `Hello! I am the Supervisor Agent assigned to this case. How can I assist you?` }
  ]);
  const [input, setInput] = useState("");
  const [governanceApproved, setGovernanceApproved] = useState(false);
  const [govSoc2, setGovSoc2] = useState<"verified" | "pending" | "">("");
  const [govInfra, setGovInfra] = useState<"meets" | "exemption" | "">("");
  const [isTyping, setIsTyping] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const container: any = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.1 } } };
  const item: any = { hidden: { opacity: 0, y: 15 }, show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } } };

  // 1. Fetch Case Details & Chat History
  useEffect(() => {
    async function fetchCase() {
      try {
        const url = `${getApiBaseUrl()}/api/cases/${caseId}`;
        const res = await apiFetch(url);
        if (!res.ok) {
          setCaseError("Case not found or API error.");
          return;
        }
        const data = await res.json();
        setCaseDetails(data);

        // Load chat history from pre-seeded chat_history field OR from activity log chat entries
        if (data.chat_history) {
          try {
            const parsed = typeof data.chat_history === 'string' ? JSON.parse(data.chat_history) : data.chat_history;
            if (Array.isArray(parsed) && parsed.length > 0) {
              setMessages(parsed.map((m: any) => ({ role: m.role, content: m.content })));
            }
          } catch(e) { console.warn('Failed to parse chat_history', e); }
        }
      } catch (err) {
        console.error("Failed to fetch case details:", err);
        setCaseError("Network error attempting to fetch case.");
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
      fetchCase();
      fetchDocs();
      // Setup simple polling for live agentic logs
      const interval = setInterval(fetchCase, 5000);
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

        <motion.div variants={container} initial="hidden" animate="show" className="p-8 space-y-8 flex-1">
          
          {/* Quick Overview & Triage panel */}
          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-amber-50 border-b border-amber-200 p-4 flex gap-4 items-start">
              <div className="bg-amber-100 text-amber-700 p-2 rounded-lg">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-amber-900 font-bold text-sm">{displayStage} Triage: Sourcing Action Required</h3>
                <p className="text-amber-700 text-sm mt-1 leading-relaxed">
                  {summaryText}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-slate-100 bg-white">
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">DTP Stage</p>
                <p className="font-semibold text-slate-800">{displayStage}</p>
                <p className="text-xs text-slate-500">Active</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Supplier</p>
                <p className="font-semibold text-slate-800">{supplierId}</p>
                <p className="text-xs text-slate-500">ID Reference</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Trigger Source</p>
                <p className="font-semibold text-sponsor-blue">{triggerSource}</p>
                <p className="text-xs text-slate-500">System Origin</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Recommended</p>
                <p className="font-bold text-slate-800 text-[13px] leading-snug">{recommendedAction}</p>
                {strategyConfidence && <p className="text-xs text-green-600 font-semibold mt-1">Confidence: {strategyConfidence}</p>}
              </div>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Context & Signals */}
            <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-red-50 to-white rounded-bl-full border-l border-b border-red-50"></div>
              <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-slate-400" />
                Context & AI Signals
              </h3>
              <div className="space-y-4">
                {keyFindings.length > 0 ? (
                  keyFindings.map((finding, idx) => {
                    // Color based on type or default — null-safe
                    const txt = (finding.text || '').toLowerCase();
                    const isRisk = finding.type === 'pricing' || txt.includes('risk') || txt.includes('expir') || txt.includes('spend') || txt.includes('cost');
                    const isPositive = finding.type === 'evaluation' || finding.type === 'approval_status' || txt.includes('leading') || txt.includes('ready') || txt.includes('stable');
                    return (
                      <div key={idx} className="flex gap-3 items-start">
                        <div className={`w-2 h-2 rounded-full ${isRisk ? 'bg-mit-red shadow-red-200' : isPositive ? 'bg-green-500 shadow-green-200' : 'bg-blue-500 shadow-blue-200'} mt-1.5 shadow-sm shrink-0`}></div>
                        <p className="text-sm text-slate-700">{finding.text}</p>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-sm text-slate-400 italic">No contextual signals available yet. Provide documents or trigger agent analysis.</div>
                )}
                
                {riskAssessment && (
                  <div className="flex gap-3 items-start mt-2 pt-2 border-t border-slate-100">
                    <div className="w-2 h-2 rounded-full bg-amber-500 shadow-amber-200 mt-1.5 shadow-sm shrink-0"></div>
                    <p className="text-sm text-slate-700"><span className="font-semibold">Risk:</span> {riskAssessment}</p>
                  </div>
                )}
              </div>
            </motion.div>

            {/* Extracted Artifacts */}
            <motion.div variants={item} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2 mb-4">
                <FileText className="w-4 h-4 text-slate-400" />
                Extracted Artifacts
              </h3>
              <ul className="space-y-3">
                {documents.length > 0 ? (
                  documents.map((doc, idx) => {
                    const ext = doc.filename.split('.').pop()?.toUpperCase() || 'DOC';
                    const isPdf = ext === 'PDF';
                    return (
                      <li key={idx} onClick={() => handleDocumentClick(doc.filename)} className="flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-100 cursor-pointer">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded flex items-center justify-center font-bold text-[10px] uppercase shadow-sm ${isPdf ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-700'}`}>
                            {ext}
                          </div>
                          <span className="text-sm font-medium text-sponsor-blue underline decoration-blue-100 underline-offset-2 break-all">{doc.filename}</span>
                        </div>
                        <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded">Ingested</span>
                      </li>
                    );
                  })
                ) : (
                  <div className="text-sm text-slate-400 italic py-2">
                    No artifacts extracted yet. Upload a document below.
                  </div>
                )}
                
                {/* Live Document Upload component */}
                <li className="relative group flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg transition-colors border-2 border-slate-200 border-dashed cursor-pointer overflow-hidden">
                  <input type="file" onChange={handleFileUpload} disabled={isUploading} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-slate-100 text-slate-600 flex items-center justify-center font-bold text-[10px] uppercase shadow-sm group-hover:bg-sponsor-blue group-hover:text-white transition-colors">
                      {isUploading ? <Clock className="w-4 h-4 animate-spin" /> : "NEW"}
                    </div>
                    <span className="text-sm font-medium text-slate-400 italic group-hover:text-sponsor-blue transition-colors">
                      {isUploading ? "Vectorizing Content..." : "Drop new PDF / XLSX here..."}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Upload</span>
                </li>
              </ul>
            </motion.div>
          </div>

          {/* Governance Decision Console */}
          <motion.div variants={item} className="bg-white rounded-xl shadow-sm border-2 border-slate-200 overflow-hidden">
            <div className="bg-slate-50 p-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-slate-800 font-bold text-[15px] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sponsor-blue" />
                {displayStage}: Governance Decision Console
              </h3>
              <div className="flex items-center gap-2 text-xs font-semibold text-green-600 bg-green-50/50 px-2.5 py-1 rounded-full border border-green-200">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                Synced with Copilot
              </div>
            </div>
            
            <div className="p-6">
              <p className="text-sm text-slate-600 mb-6 italic border-l-2 border-slate-300 pl-4 py-1">
                Approve the supplier risk evaluation to proceed into DTP03 Sourcing & Negotiation strategy. Requirements: Full IT Risk sweep, BPRA, and InfoSec SOC2 verification.
              </p>

              {governanceApproved ? (
                <div className="bg-green-50 text-green-800 p-6 rounded-lg text-center border border-green-200">
                  <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                  <h4 className="font-bold text-lg mb-1">Evaluation Approved</h4>
                  <p className="text-sm text-green-700">DTP02 gate cleared! Transitioning to DTP03 Sourcing via the Capstone Pipeline.</p>
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

          {/* Live Agentic Activity Log */}
          <motion.div variants={item} className="bg-ink rounded-xl shadow-2xl border border-slate-800 overflow-hidden flex flex-col mt-6 mb-12">
            <div className="bg-slate-900/80 px-4 py-3 border-b border-slate-800 flex justify-between items-center shrink-0">
               <h3 className="text-white font-bold text-[13px] flex items-center gap-2 font-syne tracking-wide">
                 <Terminal className="w-4 h-4 text-emerald-400" />
                 Live Agentic Process Log
               </h3>
               <div className="flex items-center gap-2">
                 <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                 <span className="text-[10px] text-slate-400 font-medium uppercase tracking-widest">System Active</span>
               </div>
            </div>
            
            <div className="p-4 h-48 overflow-y-auto space-y-2.5 font-mono text-[11.5px] bg-[#0A0C10] select-text">
              {caseDetails?.activity_log && caseDetails.activity_log.length > 0 ? caseDetails.activity_log.map((log: any, i: number) => (
                 <div key={i} className="flex gap-3 text-slate-300 border-b border-slate-800/40 pb-2.5 last:border-0 hover:bg-white/5 transition-colors -mx-4 px-4 py-1">
                    <span className="text-slate-500 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                    <span className="text-emerald-400 font-semibold shrink-0">
                      {log.agent_name || 'System'}:
                    </span>
                    <span className="text-slate-400 break-words leading-relaxed max-w-[80%]">
                      {log.output_summary || log.task_name || 'Processing...'}
                    </span>
                 </div>
              )) : (
                 <div className="text-slate-500 italic flex items-center gap-2 h-full justify-center">
                   <div className="w-1.5 h-1.5 bg-slate-600 rounded-full animate-pulse"></div> Waiting for LangGraph Events...
                 </div>
              )}
              <div ref={logEndRef} />
            </div>
          </motion.div>

        </motion.div>
      </div>

      {/* RIGHT PANEL: Copilot Chat (40%) */}
      <div className="w-[40%] flex flex-col h-full bg-white shadow-2xl z-20">
        
        {/* Chat Header */}
        <header className="px-6 py-5 border-b border-slate-100 bg-white">
          <div className="flex items-center gap-3">
             <div className="w-8 h-8 rounded-lg bg-sponsor-blue flex items-center justify-center shadow-md">
               <MessageSquare className="w-4 h-4 text-white" />
             </div>
             <div>
               <h2 className="text-lg font-bold text-slate-900 leading-tight">Case Copilot</h2>
               <p className="text-xs text-slate-500 font-medium">Chat Agent Assistance</p>
             </div>
          </div>
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
