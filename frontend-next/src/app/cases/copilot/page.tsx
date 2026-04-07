"use client";

import Link from "next/link";
import { Briefcase, MessageSquare } from "lucide-react";
import ProcuraBotIdentity from "@/components/branding/ProcuraBotIdentity";
import { PROCURABOT_BRAND } from "@/lib/procurabot-brand";

/**
 * /cases/copilot — no case id in the URL; same shell as the per-case ProcuraBot with a default details pane.
 */
export default function CaseProcuraBotNoIdPage() {
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden w-full m-0 p-0 font-sans">
      <div className="w-[60%] flex flex-col h-full overflow-y-auto bg-slate-50/50 border-r border-slate-200">
        <div className="bg-sponsor-blue text-white p-6 sticky top-0 z-10 shadow-md flex flex-row flex-wrap gap-3 justify-between items-center shrink-0">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold tracking-tight mb-1 font-syne">Case ProcuraBot</h1>
            <p className="text-sm text-blue-100 font-medium">Select a case from the dashboard</p>
          </div>
          <span className="inline-flex shrink-0 items-center justify-center whitespace-nowrap bg-blue-900/60 text-blue-100 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide border border-blue-400/30 self-center">
            No case
          </span>
        </div>

        <div className="p-8 space-y-6 flex-1">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 p-6 flex gap-4 items-start">
              <div className="bg-slate-100 text-slate-500 p-3 rounded-lg shrink-0">
                <Briefcase className="w-6 h-6" />
              </div>
              <div className="min-w-0">
                <h3 className="text-slate-900 font-bold text-base font-syne">Case details</h3>
                <p className="text-slate-600 text-sm mt-2 leading-relaxed">
                  No case is loaded yet. Open the Case Dashboard and select a case to see the summary, stage, governance
                  checklist, and ProcuraBot context.
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Link
                    href="/cases"
                    className="inline-flex items-center justify-center px-5 py-2.5 bg-sponsor-blue text-white rounded-lg font-bold text-sm shadow-md hover:bg-blue-700 transition-colors"
                  >
                    Case Dashboard
                  </Link>
                  <Link
                    href="/heatmap"
                    className="inline-flex items-center justify-center px-5 py-2.5 bg-white text-slate-700 border-2 border-slate-200 rounded-lg font-bold text-sm hover:bg-slate-50 transition-colors"
                  >
                    Heatmap
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="w-[40%] flex flex-col h-full bg-white shadow-2xl z-20">
        <header className="px-6 py-4 border-b border-slate-100 bg-white">
          <ProcuraBotIdentity subtitle="Select a case to begin" />
        </header>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center text-center text-slate-600 px-4 bg-[url('https://www.transparenttextures.com/patterns/tiny-grid.png')]">
          <MessageSquare className="w-10 h-10 text-slate-300 mb-3 shrink-0" />
          <p className="text-sm max-w-sm leading-relaxed">
            Chat turns on once a case is loaded. Open the{" "}
            <Link href="/cases" className="text-sponsor-blue font-semibold underline underline-offset-2">
              Case Dashboard
            </Link>{" "}
            and choose a case to open {PROCURABOT_BRAND.name}.
          </p>
        </div>

        <div className="p-4 bg-white border-t border-slate-100">
          <div className="flex items-end gap-2 p-1.5 bg-slate-100 border border-slate-200 rounded-xl opacity-60">
            <textarea
              className="flex-1 bg-transparent resize-none outline-none py-2.5 px-3 text-[15px] text-slate-500 placeholder:text-slate-400"
              rows={1}
              placeholder="Select a case to chat…"
              disabled
              readOnly
            />
            <button type="button" className="p-3 bg-slate-300 text-white rounded-lg m-0.5 cursor-not-allowed" disabled>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
