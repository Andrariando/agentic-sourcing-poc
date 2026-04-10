"use client";

import { useEffect, useMemo, useState } from "react";

const SYSTEM1_SPECIALISTS = [
  { id: "spend", label: "Spend Pattern", hint: "Spend data · opportunities" },
  { id: "renewal", label: "Contract Renewal", hint: "Expiry · time window" },
  { id: "category", label: "Category Strategy", hint: "Policy · preferred supplier" },
  { id: "risk", label: "Supplier Risk", hint: "Risk profile" },
] as const;

const SYSTEM2_SPECIALISTS = [
  { id: "signal", label: "Sourcing Signal", hint: "DTP-01" },
  { id: "supplier", label: "Supplier Scoring", hint: "DTP-02" },
  { id: "rfx", label: "RFx Draft", hint: "DTP-03" },
  { id: "negotiation", label: "Negotiation Support", hint: "DTP-04" },
  { id: "contract", label: "Contract Support", hint: "DTP-05" },
  { id: "implementation", label: "Implementation", hint: "DTP-06" },
] as const;

/** ViewBox tuned for side-by-side columns (~half of wide layout) */
const VB = 500;
const CX = 250;
const CY = 250;
const R = 156;

/** Hub / satellite radii used to trim spokes so lines are not buried under filled circles */
const HUB_TRIM = 40;
const SAT_TRIM = 18;

function nodePosition(index: number, total: number) {
  const start = -Math.PI / 2;
  const step = (2 * Math.PI) / total;
  const a = start + step * index;
  return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
}

/** Line from hub edge to satellite edge — always visible between nodes */
function trimSpoke(nx: number, ny: number, inner = HUB_TRIM, outer = SAT_TRIM) {
  const dx = nx - CX;
  const dy = ny - CY;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const x1 = CX + ux * inner;
  const y1 = CY + uy * inner;
  const x2 = nx - ux * outer;
  const y2 = ny - uy * outer;
  const path = `M ${x1.toFixed(1)} ${y1.toFixed(1)} L ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  const pathRev = `M ${x2.toFixed(1)} ${y2.toFixed(1)} L ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  return { x1, y1, x2, y2, path, pathRev };
}

type Accent = "emerald" | "cyan";

const ACCENT = {
  emerald: {
    hot: "#34d399",
    hotStroke: "#d1fae5",
    nodeIdle: "#64748b",
    nodeIdleStroke: "#cbd5e1",
    glow: "rgba(52,211,153,0.28)",
    edgeUnder: "rgba(15,23,42,0.85)",
    edgeIdle: "rgba(52,211,153,0.95)",
    edgeBroadcast: "rgba(167,243,208,0.98)",
    edgeHot: "#a7f3d0",
    particle: "#ecfdf5",
    ripple: "rgba(52,211,153,0.45)",
    centerFill: "rgba(30,41,59,0.96)",
    centerFillHot: "rgba(5,150,105,0.62)",
    centerStrokeIdle: "#cbd5e1",
    centerStrokeHot: "#d1fae5",
  },
  cyan: {
    hot: "#22d3ee",
    hotStroke: "#ecfeff",
    nodeIdle: "#64748b",
    nodeIdleStroke: "#cbd5e1",
    glow: "rgba(34,211,238,0.28)",
    edgeUnder: "rgba(15,23,42,0.85)",
    edgeIdle: "rgba(34,211,238,0.95)",
    edgeBroadcast: "rgba(165,243,252,0.98)",
    edgeHot: "#a5f3fc",
    particle: "#ecfeff",
    ripple: "rgba(34,211,238,0.45)",
    centerFill: "rgba(30,41,59,0.96)",
    centerFillHot: "rgba(0,58,143,0.62)",
    centerStrokeIdle: "#cbd5e1",
    centerStrokeHot: "#bae6fd",
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

  const spokes = useMemo(() => outer.map((n) => trimSpoke(n.x, n.y)), [outer]);

  const activeIdx = phase === 0 ? -1 : phase - 1;
  const supervisorHot = phase === 0;

  const glowId = `${idPrefix}-node-glow`;
  const hubR = supervisorHot ? 36 : 30;

  return (
    <div className="w-full flex justify-center items-stretch py-2">
      <svg
        viewBox={`0 0 ${VB} ${VB}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-[min(38vh,380px)] min-h-[260px] sm:min-h-[280px] lg:h-[min(44vh,420px)] lg:min-h-[300px] drop-shadow-[0_0_24px_rgba(15,23,42,0.5)]"
        role="img"
        aria-hidden
      >
        <defs>
          <filter id={glowId} x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Pulse rings from hub */}
        {!reduceMotion &&
          [0, 1.1, 2.2].map((begin, ri) => (
            <circle
              key={`ripple-${idPrefix}-${ri}`}
              cx={CX}
              cy={CY}
              r={hubR + 8}
              fill="none"
              stroke={palette.ripple}
              strokeWidth="1.5"
            >
              <animate attributeName="r" values={`${hubR + 8};${R + hubR + 40}`} dur="3.2s" begin={`${begin}s`} repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0" dur="3.2s" begin={`${begin}s`} repeatCount="indefinite" />
            </circle>
          ))}

        {/* Wide underlay + main spokes (trimmed so not hidden under node fills) */}
        {spokes.map((s, i) => {
          const n = outer[i];
          const hot = activeIdx === i;
          const broadcast = supervisorHot;
          const strokeColor = hot ? palette.edgeHot : broadcast ? palette.edgeBroadcast : palette.edgeIdle;
          const wMain = hot ? 5.5 : broadcast ? 4.8 : 4.2;
          const wUnder = wMain + 5;
          return (
            <g key={`spoke-${idPrefix}-${n.id}`}>
              <path
                d={s.path}
                fill="none"
                stroke={palette.edgeUnder}
                strokeWidth={wUnder}
                strokeLinecap="round"
                strokeOpacity={0.95}
              />
              <path
                d={s.path}
                fill="none"
                stroke={strokeColor}
                strokeWidth={wMain}
                strokeLinecap="round"
                strokeOpacity={1}
              />
            </g>
          );
        })}

        {/* Moving “data” along every spoke — staggered */}
        {!reduceMotion &&
          spokes.map((s, i) => {
            const n = outer[i];
            const dur = 2.8 + i * 0.15;
            const begin = `${i * 0.32}s`;
            const hot = activeIdx === i;
            return (
              <g key={`pkt-${idPrefix}-${n.id}`}>
                <circle r={hot ? 5 : 3.5} fill={palette.particle} filter={hot ? `url(#${glowId})` : undefined} opacity={hot ? 1 : 0.85}>
                  <animateMotion dur={`${dur}s`} repeatCount="indefinite" begin={begin} path={s.path} rotate="auto" />
                </circle>
                <circle r={2.5} fill={palette.edgeHot} opacity={0.7}>
                  <animateMotion
                    dur={`${dur}s`}
                    repeatCount="indefinite"
                    begin={`${i * 0.32 + dur * 0.5}s`}
                    path={s.pathRev}
                    rotate="auto"
                  />
                </circle>
              </g>
            );
          })}

        {/* Active channel emphasis */}
        {!reduceMotion &&
          spokes.map((s, i) => {
            const hot = activeIdx === i;
            if (!hot) return null;
            const n = outer[i];
            return (
              <path
                key={`flow-${idPrefix}-${n.id}`}
                d={s.path}
                fill="none"
                stroke={palette.edgeHot}
                strokeWidth={2.5}
                strokeOpacity={0.95}
                strokeLinecap="round"
                strokeDasharray="14 18"
                className="welcome-agent-dash"
              />
            );
          })}

        {outer.map((n, i) => {
          const hot = activeIdx === i;
          const r = hot ? 16 : 13;
          const fill = hot ? palette.hot : palette.nodeIdle;
          const stroke = hot ? palette.hotStroke : palette.nodeIdleStroke;
          return (
            <g key={`nd-${idPrefix}-${n.id}`}>
              <circle
                cx={n.x}
                cy={n.y}
                r={r + 8}
                fill={hot ? palette.glow : "rgba(148,163,184,0.12)"}
                className={hot && !reduceMotion ? "welcome-agent-node-pulse" : ""}
              />
              <circle
                cx={n.x}
                cy={n.y}
                r={r}
                fill={fill}
                stroke={stroke}
                strokeWidth={hot ? 2.6 : 2}
                filter={hot ? `url(#${glowId})` : undefined}
              />
            </g>
          );
        })}

        <g>
          <circle
            cx={CX}
            cy={CY}
            r={hubR}
            fill={supervisorHot ? palette.centerFillHot : palette.centerFill}
            stroke={supervisorHot ? palette.centerStrokeHot : palette.centerStrokeIdle}
            strokeWidth={supervisorHot ? 3.2 : 2.4}
            filter={supervisorHot ? `url(#${glowId})` : undefined}
            className={supervisorHot && !reduceMotion ? "welcome-agent-node-pulse-slow" : ""}
          />
          <text
            x={CX}
            y={CY - 8}
            textAnchor="middle"
            fill="#f8fafc"
            fontSize="17"
            fontWeight="800"
            fontFamily="system-ui, sans-serif"
          >
            {centerAbbr}
          </text>
          <text
            x={CX}
            y={CY + 12}
            textAnchor="middle"
            fill="#e2e8f0"
            fontSize="11.5"
            fontWeight="700"
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
          const lx = n.x + (n.x - CX) * 0.18;
          const ly = n.y + (n.y - CY) * 0.18;
          return (
            <text
              key={`lb-${idPrefix}-${n.id}`}
              x={lx}
              y={ly + (sub ? -4 : 5)}
              textAnchor="middle"
              fill={hot ? "#ffffff" : "#e2e8f0"}
              fontSize={hot ? 13 : 11.5}
              fontWeight={hot ? 700 : 650}
              fontFamily="system-ui, sans-serif"
              className="select-none"
              style={{ textShadow: hot ? "0 0 20px rgba(255,255,255,0.35)" : "0 1px 8px rgba(0,0,0,0.8)" }}
            >
              <tspan x={lx} dy="0" fontWeight="800">
                {label}
              </tspan>
              {sub ? (
                <tspan x={lx} dy="14" fontSize={9.5} fill={hot ? "#f1f5f9" : "#cbd5e1"} fontWeight="650">
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
      className="relative w-full mx-auto overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950 text-left shadow-[0_0_80px_-20px_rgba(52,211,153,0.18)]"
      aria-label="Animated diagrams of System 1 and System 2 agent meshes"
    >
      <div
        className="pointer-events-none absolute inset-0 welcome-agent-grid opacity-90 welcome-agent-scan welcome-agent-grid-drift"
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_75%_60%_at_25%_35%,rgba(5,150,105,0.14),transparent),radial-gradient(ellipse_65%_55%_at_85%_45%,rgba(0,58,143,0.22),transparent)]" />

      <div className="relative z-10 p-5 md:p-8 border-b border-slate-800/80">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400 mb-2">Dual agent architectures</p>
        <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">System 1 and System 2 agent meshes</h2>
        <p className="mt-3 text-sm md:text-base text-slate-300 max-w-5xl leading-relaxed">
          Both stacks use LangGraph-style orchestration with shared context and retrieval.{" "}
          <span className="text-emerald-300">System 1</span> scores opportunities for the heatmap;{" "}
          <span className="text-cyan-300">System 2</span> runs source-to-contract execution. Trimmable hub-to-agent paths stay visible;
          particles and ripples illustrate concurrent signal flow (illustrative).
        </p>
        {reduceMotion && (
          <p className="mt-3 text-sm text-amber-200/90 font-mono">Motion reduced — ripples and particles disabled.</p>
        )}
      </div>

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-slate-800/80">
        <div className="p-5 md:p-6 lg:p-7 border-b lg:border-b-0 border-slate-800/80">
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.85)]" />
            <h3 className="text-base md:text-lg font-bold text-emerald-100 tracking-wide uppercase">System 1 · Prioritization</h3>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed mb-2">
            Supervisor coordinates spend, renewal, category strategy, and supplier-risk signals into scores and explanations
            (opportunity register / heatmap).
          </p>
          <AgentConstellation
            specialists={SYSTEM1_SPECIALISTS}
            accent="emerald"
            idPrefix="s1"
            reduceMotion={reduceMotion}
            intervalMs={1600}
            centerAbbr="SUP"
            centerDetail="Supervisor"
          />
          <p className="mt-3 text-xs sm:text-sm text-slate-400 font-mono leading-relaxed border-t border-slate-800/80 pt-4">
            <span className="text-emerald-200 font-semibold">Supervisor</span>
            {" · "}
            {SYSTEM1_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>

        <div className="p-5 md:p-6 lg:p-7">
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.85)]" />
            <h3 className="text-base md:text-lg font-bold text-cyan-100 tracking-wide uppercase">System 2 · S2C execution</h3>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed mb-2">
            Supervisor routes work across six specialists from sourcing signal through implementation; human-in-the-loop chat and
            artifacts attach to case execution.
          </p>
          <AgentConstellation
            specialists={SYSTEM2_SPECIALISTS}
            accent="cyan"
            idPrefix="s2"
            reduceMotion={reduceMotion}
            intervalMs={1500}
            centerAbbr="SUP"
            centerDetail="Supervisor"
          />
          <p className="mt-3 text-xs sm:text-sm text-slate-400 font-mono leading-relaxed border-t border-slate-800/80 pt-4">
            <span className="text-cyan-200 font-semibold">Supervisor</span>
            {" · "}
            {SYSTEM2_SPECIALISTS.map((s) => s.label).join(" · ")}
          </p>
        </div>
      </div>
    </section>
  );
}
