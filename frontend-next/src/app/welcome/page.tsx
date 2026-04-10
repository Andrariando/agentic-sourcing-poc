"use client";

import Link from "next/link";
import { useState } from "react";

const FLOW_STEPS = [
  {
    id: "ingest",
    title: "1) Ingest data",
    detail:
      "Upload renewal/new-business documents or CSV in System 1 Upload. Data is parsed into candidate opportunities before approval.",
  },
  {
    id: "score",
    title: "2) Score and prioritize",
    detail:
      "Approved rows are scored and appear in the heatmap matrix and prioritized table, with human review/approval gates.",
  },
  {
    id: "execute",
    title: "3) Execute S2C",
    detail:
      "High-priority opportunities can be bridged into case execution workflows (documents, decisions, and copilot support).",
  },
];

export default function WelcomePage() {
  const [active, setActive] = useState(FLOW_STEPS[0].id);
  const activeStep = FLOW_STEPS.find((s) => s.id === active) ?? FLOW_STEPS[0];

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-slate-50 min-h-full">
      <div className="max-w-6xl mx-auto space-y-6">
        <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-8">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Executive Overview</p>
          <h1 className="text-3xl font-bold text-slate-900 mt-2 tracking-tight">Agentic Sourcing Command Center</h1>
          <p className="text-slate-600 mt-3 max-w-3xl leading-relaxed">
            Two connected systems: System 1 identifies where to act first (prioritization), and System 2 drives source-to-contract
            execution with human oversight.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/system-1/upload" className="px-4 py-2 rounded-lg bg-sponsor-blue text-white text-sm font-semibold">
              Go to System 1 Upload
            </Link>
            <Link href="/heatmap" className="px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-semibold">
              Open Heatmap Prioritization
            </Link>
            <Link href="/cases" className="px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-semibold">
              Open S2C Cases
            </Link>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <article className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-slate-900">System 1: Opportunity Prioritization</h2>
            <ul className="mt-3 space-y-2 text-sm text-slate-600 list-disc list-inside">
              <li>Accepts renewal and new-business signals from uploads and intake.</li>
              <li>Scores urgency, impact, risk, and strategic alignment.</li>
              <li>Supports human review before approval and bridge to execution.</li>
            </ul>
          </article>
          <article className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-slate-900">System 2: S2C Execution</h2>
            <ul className="mt-3 space-y-2 text-sm text-slate-600 list-disc list-inside">
              <li>Case dashboard for sourcing workflow and stage progression.</li>
              <li>ProcuraBot support for draft documents and guided decisions.</li>
              <li>Performance views for reliability and human intervention trends.</li>
            </ul>
          </article>
        </section>

        <section className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-slate-900">Interactive flow</h2>
          <p className="text-sm text-slate-500 mt-1">Click each step to see how the systems connect.</p>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            {FLOW_STEPS.map((step) => (
              <button
                key={step.id}
                type="button"
                onClick={() => setActive(step.id)}
                className={`text-left rounded-lg border p-4 transition ${
                  active === step.id
                    ? "border-sponsor-blue bg-blue-50/70"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <p className="text-sm font-semibold text-slate-800">{step.title}</p>
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-800">{activeStep.title}</p>
            <p className="text-sm text-slate-600 mt-1 leading-relaxed">{activeStep.detail}</p>
          </div>
        </section>
      </div>
    </div>
  );
}

