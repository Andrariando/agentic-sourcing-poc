"use client";

import { useEffect, useMemo, useState } from "react";

/**
 * System 1 — Opportunity prioritization / heatmap (LangGraph + shared memory).
 */
const SYSTEM1_SPECIALISTS = [
  { id: "spend", label: "Spend Pattern", hint: "Spend data · opportunities" },
  { id: "renewal", label: "Contract Renewal", hint: "Expiry · time window" },
  { id: "category", label: "Category Strategy", hint: "Policy · preferred supplier" },
  { id: "risk", label: "Supplier Risk", hint: "Risk profile" },
] as const;

/**
 * System 2 — S2C execution (official seven first-class agents).
 */
const SYSTEM2_SPECIALISTS = [
  { id: "signal", label: "Sourcing Signal", hint: "DTP-01" },
  { id: "supplier", label: "Supplier Scoring", hint: "DTP-02" },
  { id: "rfx", label: "RFx Draft", hint: "DTP-03" },
  { id: "negotiation", label: "Negotiation Support", hint: "DTP-04" },
  { id: "contract", label: "Contract Support", hint: "DTP-05" },
  { id: "implementation", label: "Implementation", hint: "DTP-06" },
] as const;

/** Larger canvas so labels/nodes read clearly when scaled up in layout */
const VB = 420;
const CX = 210;
const CY = 210;
const R = 132;

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
    hotStroke: "#a7f3d0",
    nodeIdle: "#64748b",
    nodeIdleStroke: "#94a3b8",
    glow: "rgba(52,211,153,0.22)",
    /** Always-visible hub spokes */
    edgeIdle: "rgba(110,231,183,0.78)",
    edgeBroadcast: "rgba(167,243,208,0.92)",
    edgeHot: "#6ee7b7",
    centerFill: "rgba(30,41,59,0.95)",
    centerFillHot: "rgba(5,150,105,0.55)",
    centerStrokeIdle: "rgba(148,163,184,0.85)",
    centerStrokeHot: "#a7f3d0",
  },
  cyan: {
    hot: "#22d3ee",
    hotStroke: "#a5f3fc",
    nodeIdle: "#64748b",
    nodeIdleStroke: "#94a3b8",
    glow: "rgba(34,211,238,0.22)",
    edgeIdle: "rgba(103,232,249,0.78)",
    edgeBroadcast: "rgba(165,243,252,0.92)",
    edgeHot: "#67e8f9",
    centerFill: "rgba(30,41,59,0.95)",
    centerFillHot: "rgba(0,58,143,0.55)",
    centerStrokeIdle: "rgba(148,163,184,0.85)",
    centerStrokeHot: "#7dd3fc",
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

  const glowId = `${idPrefix}-node-glow`;

  return (
    <div className="w-full flex justify-center items-center min-h-[min(52vh,520px)] md:min-h-[min(56vh,580px)] py-2">
      <svg
        viewBox={`0 0 ${VB} ${VB}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full max-w-none h-[min(52vh,520px)] md:h-[min(56vh,580px)] drop-shadow-[0_0_20px_rgba(15,23,42,0.5)]"
        role="img"
        aria-hidden
      >
        <defs>
          <filter id={glowId} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Base edges: solid, always visible (flow simulation) */}
        {outer.map((n, i) => {
          const hot = activeIdx === i;
          const broadcast = supervisorHot;
          const strokeColor = hot
            ? palette.edgeHot
            : broadcast
              ? palette.edgeBroadcast
              : palette.edgeIdle;
          const strokeWidth = hot ? 4.2 : broadcast ? 3.4 : 3;
          return (
            <line
              key={`ln-base-${idPrefix}-${n.id}`}
              x1={CX}
              y1={CY}
              x2={n.x}
              y2={n.y}
              stroke={strokeColor}
              strokeWidth={strokeWidth}
              strokeOpacity={1}
              strokeLinecap="round"
            />
          );
        })}

        {/* Active edge pulse overlay (motion) */}
        {!reduceMotion &&
          outer.map((n, i) => {
            const hot = activeIdx === i;
            if (!hot) return null;
            return (
              <line
                key={`ln-flow-${idPrefix}-${n.id}`}
                x1={CX}
                y1={CY}
                x2={n.x}
                y2={n.y}
                stroke={palette.edgeHot}
                strokeWidth={2}
                strokeOpacity={0.95}
                strokeLinecap="round"
                strokeDasharray="10 14"
                className="welcome-agent-dash"
              />
            );
          })}

        {outer.map((n, i) => {
          const hot = activeIdx === i;
          const r = hot ? 15 : 12;
          const fill = hot ? palette.hot : palette.nodeIdle;
          const stroke = hot ? palette.hotStroke : palette.nodeIdleStroke;
          return (
            <g key={`nd-${idPrefix}-${n.id}`}>
              <circle
                cx={n.x}
                cy={n.y}
                r={r + 6}
                fill={hot ? palette.glow : "rgba(148,163,184,0.08)"}
                className={hot && !reduceMotion ? "welcome-agent-node-pulse" : ""}
              />
              <circle
                cx={n.x}
                cy={n.y}
                r={r}
                fill={fill}
                stroke={stroke}
                strokeWidth={hot ? 2.2 : 1.6}
                filter={hot ? `url(#${glowId})` : undefined}
              />
            </g>
          );
        })}

        <g>
          <circle
            cx={CX}
            cy={CY}
            r={supervisorHot ? 34 : 28}
            fill={supervisorHot ? palette.centerFillHot : palette.centerFill}
            stroke={supervisorHot ? palette.centerStrokeHot : palette.centerStrokeIdle}
            strokeWidth={supervisorHot ? 2.8 : 2}
            filter={supervisorHot ? `url(#${glowId})` : undefined}
            className={supervisorHot && !reduceMotion ? "welcome-agent-node-pulse-slow" : ""}
          />
          <text
            x={CX}
            y={CY - 7}
            textAnchor="middle"
            fill="#f8fafc"
            fontSize="14"
            fontWeight="800"
            fontFamily="system-ui, sans-serif"
          >
            {centerAbbr}
          </text>
          <text
            x={CX}
            y={CY + 10}
            textAnchor="middle"
            fill="#cbd5e1"
            fontSize="10"
            fontWeight="600"
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
          const lx = n.x + (n.x - CX) * 0.2;
          const ly = n.y + (n.y - CY) * 0.2;
          return (
            <text
              key={`lb-${idPrefix}-${n.id}`}
              x={lx}
              y={ly + (sub ? -3 : 4)}
              textAnchor="middle"
              fill={hot ? "#f1f5f9" : "#cbd5e1"}
              fontSize={hot ? 12 : 10.5}
              fontWeight={hot ? 650 : 600}
              fontFamily="system-ui, sans-serif"
              className="select-none"
            >
              <tspan x={lx} dy="0" fontWeight="800">
                {label}
              </tspan>
              {sub ? (
                <tspan x={lx} dy="13" fontSize={9} fill={hot ? "#e2e8f0" : "#94a3b8"} fontWeight="600">
                  {sub}
                </tspan>
              ) : null}
            </text>
          );
        })}
      </svg>
    </div>
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

      <div className="relative z-10 p-5 md:p-8 border-b border-slate-800/80">
        <p className="text-[11px] font-semibold uppercase tracking-[0.35em] text-slate-400 mb-2">
          Dual agent architectures
        </p>
        <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">System 1 and System 2 agent meshes</h2>
        <p className="mt-3 text-sm md:text-base text-slate-400 max-w-3xl leading-relaxed">
          Both stacks use LangGraph-style orchestration with shared context and retrieval.{" "}
          <span className="text-emerald-300/90">System 1</span> scores and explains opportunities for the heatmap;{" "}
          <span className="text-cyan-300/90">System 2</span> runs source-to-contract execution with the seven documented specialists.
          Solid lines show the supervisor-to-specialist flow; the highlighted channel animates for emphasis.
        </p>
        <ul className="mt-3 space-y-1 text-xs text-slate-500 font-mono">
          {reduceMotion && <li className="text-amber-200/80">Motion reduced — static view</li>}
        </ul>
      </div>

      <div className="relative z-10 grid grid-cols-1 xl:grid-cols-2 gap-0 xl:divide-x xl:divide-slate-800/80">
        <div className="p-5 md:p-8 border-b xl:border-b-0 border-slate-800/80 xl:border-emerald-500/20">
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.75)]" />
            <h3 className="text-base md:text-lg font-bold text-emerald-100 tracking-wide uppercase">
              System 1 · Prioritization
            </h3>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed mb-1 max-w-prose">
            Supervisor coordinates spend, renewal, category strategy, and supplier-risk signals into scores and explanations
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
          <p className="mt-2 text-xs md:text-sm text-slate-400 font-mono leading-relaxed border-t border-slate-800/80 pt-4">
            <span className="text-emerald-200 font-semibold">Supervisor</span>
            {" · "}
            {SYSTEM1_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>

        <div className="p-5 md:p-8 xl:border-cyan-500/20">
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.75)]" />
            <h3 className="text-base md:text-lg font-bold text-cyan-100 tracking-wide uppercase">
              System 2 · S2C execution
            </h3>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed mb-1 max-w-prose">
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
          <p className="mt-2 text-xs md:text-sm text-slate-400 font-mono leading-relaxed border-t border-slate-800/80 pt-4">
            <span className="text-cyan-200 font-semibold">Supervisor</span>
            {" · "}
            {SYSTEM2_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>
      </div>
    </section>
  );
}
