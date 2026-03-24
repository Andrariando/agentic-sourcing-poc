"use client";

import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, FileText, Activity, ShieldCheck, ChevronRight, MessageSquare, Briefcase, Clock } from "lucide-react";

export default function LegacyCaseCopilotPage() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Good morning! Let's advance TechGlobal Inc into DTP02 Supplier Evaluation. Have you uploaded their recent SOC2 compliance report?" }
  ]);
  const [input, setInput] = useState("");
  const [governanceApproved, setGovernanceApproved] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages([...messages, { role: "user", content: input }]);
    setInput("");
    
    // Simulate thinking delay
    setTimeout(() => {
      setMessages(prev => [
        ...prev, 
        { role: "assistant", content: "Thank you. I have extracted the BPRA risk indicators and updated the supplier profile. Would you like me to submit the DTP02 evaluation for approval?" }
      ]);
    }, 1500);
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden w-full m-0 p-0 font-sans">
      
      {/* LEFT PANEL: Case Details (60%) */}
      <div className="w-[60%] flex flex-col h-full overflow-y-auto bg-slate-50/50 border-r border-slate-200">
        
        {/* Condensed Header */}
        <div className="bg-sponsor-blue text-white p-6 sticky top-0 z-10 shadow-md flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold tracking-tight mb-1">TechGlobal Inc Renewal</h1>
            <div className="flex items-center gap-3 text-sm text-blue-100 font-medium">
              <span>CASE-2026-001</span>
              <span>•</span>
              <span className="bg-blue-800/50 px-2 py-0.5 rounded text-white flex items-center gap-1.5 border border-blue-400/30">
                <Briefcase className="w-3.5 h-3.5" />
                IT Infrastructure
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className="bg-sponsor-orange text-white px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest shadow-sm">
              In Progress
            </span>
          </div>
        </div>

        <div className="p-8 space-y-8">
          
          {/* Quick Overview & Triage panel */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="bg-amber-50 border-b border-amber-200 p-4 flex gap-4 items-start">
              <div className="bg-amber-100 text-amber-700 p-2 rounded-lg">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-amber-900 font-bold text-sm">DTP01 Triage: NOT COVERED - Sourcing Required</h3>
                <p className="text-amber-700 text-sm mt-1 leading-relaxed">No existing contract covers this massive expansion request. Supplier evaluation and negotiation strategy required.</p>
              </div>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-slate-100 bg-white">
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">DTP Stage</p>
                <p className="font-semibold text-slate-800">DTP02</p>
                <p className="text-xs text-slate-500">Supplier Eval</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Supplier</p>
                <p className="font-semibold text-slate-800">TechGlobal Inc</p>
                <p className="text-xs text-slate-500">ID: SUP-9021</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Trigger Source</p>
                <p className="font-semibold text-sponsor-blue">Signal</p>
                <p className="text-xs text-slate-500">Expiry Risk</p>
              </div>
              <div className="p-4 text-center">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Est. Spend</p>
                <p className="font-bold text-slate-800">$3.0M</p>
                <p className="text-xs text-slate-500">Tier 1 Target</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Context & Signals */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-red-50 to-white rounded-bl-full border-l border-b border-red-50"></div>
              <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4 text-slate-400" />
                Context & AI Signals
              </h3>
              <div className="space-y-4">
                <div className="flex gap-3 items-start">
                  <div className="w-2 h-2 rounded-full bg-mit-red mt-1.5 shadow-sm shadow-red-200 shrink-0"></div>
                  <p className="text-sm text-slate-700">Contract expires in 45 days. High Expiry Urgency Score (EUS) detected.</p>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 shadow-sm shadow-green-200 shrink-0"></div>
                  <p className="text-sm text-slate-700">Strong historical SLA compliance (99.9% uptime). Low Performance Risk.</p>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-2 h-2 rounded-full bg-mit-red mt-1.5 shadow-sm shadow-red-200 shrink-0"></div>
                  <p className="text-sm text-slate-700">High dependency. They host mission-critical Tier-1 business applications.</p>
                </div>
              </div>
            </div>

            {/* Extracted Artifacts */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-slate-800 font-bold text-sm flex items-center gap-2 mb-4">
                <FileText className="w-4 h-4 text-slate-400" />
                Extracted Artifacts
              </h3>
              <ul className="space-y-3">
                <li className="flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-100 cursor-pointer">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-red-50 text-red-600 flex items-center justify-center font-bold text-[10px] uppercase shadow-sm">PDF</div>
                    <span className="text-sm font-medium text-sponsor-blue underline decoration-blue-100 underline-offset-2">Master_Agreement_2021.pdf</span>
                  </div>
                  <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded">Ingested</span>
                </li>
                <li className="flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-100 cursor-pointer">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-green-50 text-green-700 flex items-center justify-center font-bold text-[10px] uppercase shadow-sm">XLSX</div>
                    <span className="text-sm font-medium text-sponsor-blue underline decoration-blue-100 underline-offset-2">PO_Spend_History_12M.xlsx</span>
                  </div>
                  <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded">Ingested</span>
                </li>
                <li className="flex items-center justify-between p-2 hover:bg-slate-50 rounded-lg transition-colors border border-transparent hover:border-slate-100 cursor-pointer">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded bg-slate-100 text-slate-600 flex items-center justify-center font-bold text-[10px] border border-slate-200 border-dashed">NEW</div>
                    <span className="text-sm font-medium text-slate-400 italic">Upload SOC2 Report...</span>
                  </div>
                  <span className="text-xs text-slate-400 uppercase font-semibold">Pending</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Governance Decision Console */}
          <div className="bg-white rounded-xl shadow-sm border-2 border-slate-200 overflow-hidden">
            <div className="bg-slate-50 p-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-slate-800 font-bold text-[15px] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-sponsor-blue" />
                DTP02: Governance Decision Console
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
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"><input type="radio" name="soc" className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" /> Yes, Verified</label>
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"><input type="radio" name="soc" className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" /> Pending / Missing</label>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Does this supplier meet minimum IT Infrastructure thresholds? *</label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"><input type="radio" name="thresh" className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" /> Meets Thresholds</label>
                      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer"><input type="radio" name="thresh" className="w-4 h-4 text-sponsor-blue focus:ring-sponsor-blue" /> Does Not Meet (Requires Exemption)</label>
                    </div>
                  </div>
                  
                  <div className="flex gap-4 pt-4 border-t border-slate-100">
                     <button onClick={() => setGovernanceApproved(true)} className="flex-1 py-3 bg-sponsor-blue text-white rounded-lg font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 hover:-translate-y-0.5 transition-all">
                       ✅ Confirm & Approve Eval
                     </button>
                     <button className="flex-1 py-3 bg-white text-slate-600 border-2 border-slate-200 rounded-lg font-bold hover:bg-slate-50 hover:text-slate-800 transition">
                       ↩️ Request Revision
                     </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="mb-12"></div>
        </div>
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
                : "bg-white border border-slate-200 text-slate-700 rounded-2xl rounded-tl-sm shadow-[0_2px_10px_-3px_rgba(6,81,237,0.1)]"
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
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
            />
            <button 
              className="p-3 bg-sponsor-blue text-white rounded-lg hover:bg-blue-700 transition shadow-md disabled:opacity-50 disabled:cursor-not-allowed m-0.5"
              onClick={handleSend}
              disabled={!input.trim()}
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
