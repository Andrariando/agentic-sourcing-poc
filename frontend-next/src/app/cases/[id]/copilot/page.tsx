"use client";

import React, { useState } from "react";

export default function LegacyCaseCopilotPage() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Good morning! Let's advance TechGlobal Inc into DTP02 Supplier Evaluation. Have you uploaded their recent SOC2 compliance report?" }
  ]);
  const [input, setInput] = useState("");

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
    <div className="flex-1 flex flex-col h-screen bg-slate-50">
      {/* Copilot Header */}
      <header className="h-16 flex items-center px-6 bg-white border-b border-slate-200 shrink-0 shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-slate-900 tracking-tight">Case Copilot: CASE-2026-001</h1>
          <p className="text-xs text-slate-500">TechGlobal Inc Renewal • DTP02</p>
        </div>
        <div className="ml-auto flex gap-2">
          <button className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-md text-xs font-semibold hover:bg-slate-200">
            View Documents
          </button>
        </div>
      </header>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-xl p-4 rounded-xl ${
              msg.role === "user" 
              ? "bg-sponsor-blue text-white rounded-br-none" 
              : "bg-white border border-slate-200 text-slate-800 rounded-bl-none shadow-sm"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-200 shrink-0">
        <div className="max-w-4xl mx-auto flex items-end gap-3 p-2 bg-slate-50 border border-slate-300 rounded-xl focus-within:ring-1 focus-within:ring-sponsor-blue transition-all">
          <button className="p-2 text-slate-400 hover:text-sponsor-blue transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
            </svg>
          </button>
          <textarea 
            className="flex-1 bg-transparent resize-none outline-none py-2 text-sm text-slate-900 max-h-32"
            rows={1}
            placeholder="Review the supplier docs and suggest the risk score..."
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
            className="p-2 bg-sponsor-blue text-white rounded-lg hover:bg-blue-700 transition-colors"
            onClick={handleSend}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
            </svg>
          </button>
        </div>
        <p className="text-center text-xs text-slate-400 mt-2">
          Legacy DTP Supervisor Copilot can make mistakes. Please verify important DTP submissions.
        </p>
      </div>

    </div>
  );
}
