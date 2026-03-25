# Procurement Agentic System — Next.js Frontend

The modern, premium frontend for the Procurement Agentic System. Built with Next.js 16 (App Router), Tailwind CSS v4, Recharts, and Framer Motion.

## Design System

| Token | Value | Usage |
|-------|-------|-------|
| `--ink` | `#0F172A` | Deep navy backgrounds |
| `--canvas` | `#F8FAFC` | Light surface backgrounds |
| `--sponsor-blue` | `#1E3A8A` | Primary accent / interactive |
| `--mit-red` | `#A31F34` | Critical / T1 alerts |
| Font (Headers) | **Syne** | Bold, modern headings |
| Font (Body) | **DM Sans** | Clean, readable body text |

## Pages

| Route | Description |
|-------|-------------|
| `/heatmap` | Sourcing Priority Heatmap — KPI stat cards, Table/Matrix toggle, Recharts scatter chart, Sourcing Opportunity Matrix (KLI) |
| `/cases/[id]/copilot` | Case Copilot — 60/40 split-screen with triage panel, Context & AI Signals, Governance Console, Live Agentic Process Log, and chat panel |
| `/intake` | Business Intake — New sourcing request form; calls `/api/heatmap/intake/preview` (debounced) and `/api/heatmap/intake` |
| `/kpi` | KPI Dashboard |

## Dependencies

| Package | Purpose |
|---------|---------|
| `next` (v16) | React framework (App Router + Turbopack) |
| `recharts` | Scatter charts for the Heatmap Matrix view |
| `framer-motion` | Staggered page-load animations |
| `lucide-react` | Icon library |

## Getting Started

```bash
# Install dependencies
npm install

# Start dev server (requires backend running on port 8000)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend URL |

## Key Architecture Decisions

1. **Data-Driven UI**: All UI elements dynamically bind to the backend `CaseDetail` and `ScoredOpportunity` schemas — no hardcoded mock data.
2. **Activity Log Transparency**: The Live Agentic Process terminal polls the backend `activity_log` for real-time LangGraph execution events (`agent_name`, `task_name`, `output_summary`).
3. **Pre-seeded Chat History**: The chat panel initializes from the `chat_history` JSON field in the `CaseDetail` response.
4. **Signals from Key Findings**: The "Context & AI Signals" panel derives its bullet points from `summary.key_findings` (with keyword-based color coding) and `latest_agent_output.risk_assessment`.
