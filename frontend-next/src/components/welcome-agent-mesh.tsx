"use client";

import { useEffect, useMemo, useState } from "react";

/**
 * System 1 — Opportunity prioritization / heatmap (LangGraph + shared memory).
 * Matches architecture: Supervisor coordinates spend, renewal, strategy, risk agents.
 */
const SYSTEM1_SPECIALISTS = [
  { id: "spend", label: "Spend Pattern", hint: "Spend data · opportunities" },
  { id: "renewal", label: "Contract Renewal", hint: "Expiry · time window" },
  { id: "category", label: "Category Strategy", hint: "Policy · preferred supplier" },
  { id: "risk", label: "Supplier Risk", hint: "Risk profile" },
] as const;

/**
 * System 2 — S2C execution (official seven first-class agents).
 * Matches backend/agents/__init__.py / AgentName enum.
 */
const SYSTEM2_SPECIALISTS = [
  { id: "signal", label: "Sourcing Signal", hint: "DTP-01" },
  { id: "supplier", label: "Supplier Scoring", hint: "DTP-02" },
  { id: "rfx", label: "RFx Draft", hint: "DTP-03" },
  { id: "negotiation", label: "Negotiation Support", hint: "DTP-04" },
  { id: "contract", label: "Contract Support", hint: "DTP-05" },
  { id: "implementation", label: "Implementation", hint: "DTP-06" },
] as const;

const CX = 200;
const CY = 200;
const R = 118;

function nodePosition(index: number, total: number) {
  const start = -Math.PI / 2;
  const step = (2 * Math.PI) / total;
  const a = start + step * index;
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
}

type Accent = "emerald" | "cyan";

const ACCENT = {
  emerald: {
    hot: "#34d399",
    hotStroke: "#6ee7b7",
    glow: "rgba(52,211,153,0.15)",
    lineLo: "rgba(52,211,153,0.15)",
    lineMid: "rgba(16,185,129,0.55)",
    centerFillHot: "rgba(5,150,105,0.45)",
    centerStrokeHot: "#6ee7b7",
  },
  cyan: {
    hot: "#22d3ee",
    hotStroke: "#67e8f9",
    glow: "rgba(34,211,238,0.15)",
    lineLo: "rgba(34,211,238,0.15)",
    lineMid: "rgba(0,58,143,0.6)",
    centerFillHot: "rgba(0,58,143,0.5)",
    centerStrokeHot: "#38bdf8",
  },
} as const;

type Spec = { id: string; label: string; hint: string };

function AgentConstellation({
  specialists,
  accent,
  idPrefix,
  reduceMotion,
  intervalMs,
  centerAbbr,
  centerDetail,
}: {
  specialists: readonly Spec[];
  accent: Accent;
  idPrefix: string;
  reduceMotion: boolean;
  intervalMs: number;
  centerAbbr: string;
  centerDetail: string;
}) {
  const palette = ACCENT[accent];
  const totalPhases = specialists.length + 1;
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (reduceMotion) return;
    const t = window.setInterval(() => {
      setPhase((p) => (p + 1) % totalPhases);
    }, intervalMs);
    return () => window.clearInterval(t);
  }, [reduceMotion, totalPhases, intervalMs]);

  const outer = useMemo(() => {
    return specialists.map((s, i) => ({
      ...s,
      ...nodePosition(i, specialists.length),
    }));
  }, [specialists]);

  const activeIdx = phase === 0 ? -1 : phase - 1;
  const supervisorHot = phase === 0;

  const gradId = `${idPrefix}-mesh-line`;
  const glowId = `${idPrefix}-node-glow`;

  return (
    <svg
      viewBox="0 0 400 400"
      className="w-full max-w-[min(100%,360px)] mx-auto h-auto drop-shadow-[0_0_18px_rgba(15,23,42,0.4)]"
      role="img"
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={palette.lineLo} />
          <stop offset="50%" stopColor={palette.lineMid} />
          <stop offset="100%" stopColor={palette.lineLo} />
        </linearGradient>
        <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {outer.map((n, i) => {
        const hot = activeIdx === i;
        const strokeOpacity = reduceMotion
          ? 0.32
          : hot
            ? 0.92
            : supervisorHot
              ? 0.38
              : 0.14;
        return (
          <line
            key={`ln-${idPrefix}-${n.id}`}
            x1={CX}
            y1={CY}
            x2={n.x}
            y2={n.y}
            stroke={`url(#${gradId})`}
            strokeWidth={hot ? 2.2 : 1}
            strokeOpacity={strokeOpacity}
            strokeDasharray={hot && !reduceMotion ? "6 10" : "4 14"}
            className={hot && !reduceMotion ? "welcome-agent-dash" : undefined}
          />
        );
      })}

      {outer.map((n, i) => {
        const hot = activeIdx === i;
        const r = hot ? 11 : 8;
        const fill = hot ? palette.hot : "#334155";
        const stroke = hot ? palette.hotStroke : "rgba(148,163,184,0.5)";
        return (
          <g key={`nd-${idPrefix}-${n.id}`}>
            <circle
              cx={n.x}
              cy={n.y}
              r={r + 4}
              fill={hot ? palette.glow : "transparent"}
              className={hot && !reduceMotion ? "welcome-agent-node-pulse" : ""}
            />
            <circle
              cx={n.x}
              cy={n.y}
              r={r}
              fill={fill}
              stroke={stroke}
              strokeWidth={hot ? 1.5 : 1}
              filter={hot ? `url(#${glowId})` : undefined}
            />
          </g>
        );
      })}

      <g>
        <circle
          cx={CX}
          cy={CY}
          r={supervisorHot ? 26 : 20}
          fill={supervisorHot ? palette.centerFillHot : "rgba(30,41,59,0.9)"}
          stroke={supervisorHot ? palette.centerStrokeHot : "rgba(100,116,139,0.6)"}
          strokeWidth={supervisorHot ? 2 : 1.5}
          filter={supervisorHot ? `url(#${glowId})` : undefined}
          className={supervisorHot && !reduceMotion ? "welcome-agent-node-pulse-slow" : ""}
        />
        <text
          x={CX}
          y={CY - 5}
          textAnchor="middle"
          fill="#f1f5f9"
          fontSize="10"
          fontWeight="700"
          fontFamily="system-ui, sans-serif"
        >
          {centerAbbr}
        </text>
        <text
          x={CX}
          y={CY + 7}
          textAnchor="middle"
          fill="#94a3b8"
          fontSize="6.5"
          fontFamily="system-ui, sans-serif"
        >
          {centerDetail}
        </text>
      </g>

      {outer.map((n, i) => {
        const hot = activeIdx === i;
        const parts = n.label.split(" ");
        const label = parts[0];
        const sub = parts.slice(1).join(" ");
        const lx = n.x + (n.x - CX) * 0.22;
        const ly = n.y + (n.y - CY) * 0.22;
        return (
          <text
            key={`lb-${idPrefix}-${n.id}`}
            x={lx}
            y={ly + (sub ? -2 : 3)}
            textAnchor="middle"
            fill={hot ? "#e2e8f0" : "#64748b"}
            fontSize={hot ? 9 : 7.5}
            fontWeight={hot ? 600 : 500}
            fontFamily="system-ui, sans-serif"
            className="select-none"
          >
            <tspan x={lx} dy="0" fontWeight="700">
              {label}
            </tspan>
            {sub ? (
              <tspan x={lx} dy="11" fontSize={6.5} fill={hot ? "#94a3b8" : "#475569"}>
                {sub}
              </tspan>
            ) : null}
          </text>
        );
      })}
    </svg>
  );
}

export function WelcomeAgentMesh() {
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduceMotion(mq.matches);
    const onChange = () => setReduceMotion(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <section
      className="relative overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950 text-left shadow-[0_0_70px_-16px_rgba(52,211,153,0.12)]"
      aria-label="Animated diagrams of System 1 and System 2 agent meshes"
    >
      <div
        className="pointer-events-none absolute inset-0 welcome-agent-grid opacity-90 welcome-agent-scan"
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_30%_40%,rgba(5,150,105,0.12),transparent),radial-gradient(ellipse_60%_50%_at_80%_50%,rgba(0,58,143,0.2),transparent)]" />

      <div className="relative z-10 p-5 md:p-7 border-b border-slate-800/80">
        <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-slate-400 mb-2">
          Dual agent architectures
        </p>
        <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">System 1 and System 2 agent meshes</h2>
        <p className="mt-2 text-sm text-slate-400 max-w-3xl leading-relaxed">
          Both stacks use LangGraph-style orchestration with shared context and retrieval.{" "}
          <span className="text-emerald-300/90">System 1</span> scores and explains opportunities for the heatmap;{" "}
          <span className="text-cyan-300/90">System 2</span> runs source-to-contract execution with the seven documented specialists.
          Animation highlights coordination paths (illustrative).
        </p>
        <ul className="mt-3 space-y-1 text-xs text-slate-500 font-mono">
          {reduceMotion && <li className="text-amber-200/80">Motion reduced — static view</li>}
        </ul>
      </div>

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-0 lg:divide-x lg:divide-slate-800/80">
        {/* System 1 */}
        <div className="p-5 md:p-6 border-b lg:border-b-0 border-slate-800/80 border-emerald-500/15">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
            <h3 className="text-sm font-bold text-emerald-100 tracking-wide uppercase">System 1 · Prioritization</h3>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed mb-4">
            Supervisor agent coordinates spend, renewal, category strategy, and supplier-risk signals into scores and explanations
            (opportunity register / heatmap).
          </p>
          <AgentConstellation
            specialists={SYSTEM1_SPECIALISTS}
            accent="emerald"
            idPrefix="s1"
            reduceMotion={reduceMotion}
            intervalMs={1400}
            centerAbbr="SUP"
            centerDetail="Supervisor"
          />
          <p className="mt-4 text-[10px] text-slate-500 font-mono leading-relaxed border-t border-slate-800/80 pt-3">
            <span className="text-emerald-200/80">Supervisor</span>
            {" · "}
            {SYSTEM1_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>

        {/* System 2 */}
        <div className="p-5 md:p-6 border-cyan-500/15">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.7)]" />
            <h3 className="text-sm font-bold text-cyan-100 tracking-wide uppercase">System 2 · S2C execution</h3>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed mb-4">
            Supervisor routes work across six specialists from sourcing signal through implementation; human-in-the-loop chat and
            artifacts attach to case execution.
          </p>
          <AgentConstellation
            specialists={SYSTEM2_SPECIALISTS}
            accent="cyan"
            idPrefix="s2"
            reduceMotion={reduceMotion}
            intervalMs={1300}
            centerAbbr="SUP"
            centerDetail="Supervisor"
          />
          <p className="mt-4 text-[10px] text-slate-500 font-mono leading-relaxed border-t border-slate-800/80 pt-3">
            <span className="text-cyan-200/80">Supervisor</span>
            {" · "}
            {SYSTEM2_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>
      </div>
    </section>
  );
}
