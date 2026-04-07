# Procurement Agentic System — Dual-System Enterprise POC

This repository contains **two independent procurement systems** that share a single FastAPI server (`backend/main.py`) but **do not share state**:

1. **Legacy DTP Copilot (DTP-01 → DTP-06)**: A human-in-the-loop, multi-agent decision-support system for end-to-end sourcing execution.
2. **Opportunity Heatmap (agentic scoring + intake)**: A separate agentic system that continuously evaluates sourcing opportunities (renewals + new requests) and prioritizes them using a weighted scoring model with optional LLM support.

> **Integration point**: The only bridge between the systems is **Heatmap → DTP case creation** via `backend/heatmap/services/case_bridge.py` (approving a heatmap opportunity creates a new legacy DTP case).

---

## 📚 Documentation

This project includes comprehensive documentation covering all aspects of the system:

### Core Documentation

- **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** — Consolidated roadmap: review themes, quick wins, KPI/KLI implementation tracks, suggested order
- **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)** — Comprehensive technical reference (dual-system architecture, all API routes, packages, frontends, data stores)
- **[SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)** — Complete technical documentation
  - Architecture overview and design philosophy
  - Intent classification system (hybrid rule-based + LLM)
  - Chat service flow and message processing
  - Agent system (all 7 agents with detailed sub-tasks)
  - Task execution hierarchy (Rules → Retrieval → Analytics → LLM)
  - DTP stage progression and governance
  - Artifact system and persistence
  - Data models and schemas
  - UI/UX flow and components
  - Demo & testing instructions
  - Dual-system architecture: Legacy DTP vs Opportunity Heatmap

- **[BUSINESS_OVERVIEW.md](BUSINESS_OVERVIEW.md)** — Business translation + use cases
  - What each system is for (Heatmap vs DTP Copilot)
  - Defined use cases and success metrics
  - Caveats / what this POC is (and is not)
  - Azure-aligned path to production (security, data, AI services)

- **[architecture.puml](architecture.puml)** — Visual architecture diagram (PlantUML)
  - Complete system architecture visualization
  - Shows all 7 agents, task execution, artifact system
  - Data flows and component interactions
  - **Render**: Use PlantUML extension in VS Code/Cursor (`Alt+D`) or online at [plantuml.com](http://www.plantuml.com/plantuml)

- **[ARCHITECTURE_DIAGRAMS_STATUS.md](ARCHITECTURE_DIAGRAMS_STATUS.md)** — Architecture diagram status and usage guide
  - Diagram version and update status
  - How to render and view the diagram
  - What the diagram covers

### Configuration & Setup

- **[requirements.txt](requirements.txt)** — Python dependencies
  - All required packages and versions
  - Install with: `pip install -r requirements.txt`

### Reference Materials

- **[methodology_extract.txt](methodology_extract.txt)** — Research methodology notes
  - Background on DTP methodology
  - Design principles and approach

### Quick Links

- **This README** — Quick start guide, overview, and navigation
- **API Documentation** — Auto-generated at `http://localhost:8000/docs` when backend is running
- **Code Documentation** — Inline docstrings throughout the codebase

### Documentation Sections by Topic

- **Getting Started**: See [Quick Start](#-quick-start) below
- **Architecture**: [SYSTEM_DOCUMENTATION.md - Architecture Overview](SYSTEM_DOCUMENTATION.md#architecture-overview)
- **Intent Classification**: [SYSTEM_DOCUMENTATION.md - Intent Classification System](SYSTEM_DOCUMENTATION.md#intent-classification-system)
- **Agents & Tasks**: [SYSTEM_DOCUMENTATION.md - Agent System](SYSTEM_DOCUMENTATION.md#agent-system)
- **Demo & Testing**: [SYSTEM_DOCUMENTATION.md - Demo & Testing](SYSTEM_DOCUMENTATION.md#demo--testing)
- **API Reference**: See [API Reference](#-api-reference) section below

---

## 🎯 Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Decision is focal point** | AI advises, human decides |
| **LLM-First Intent** | LLM classifies intent dynamically (replaces legacy regex rules) |
| **No autonomous decisions** | All recommendations require human approval |
| **Full traceability** | Every artifact grounded in data with verification status |
| **Grounded retrieval** | Answers cite uploaded documents/data |
| **Supervisor routes, ChatService orchestrates** | Supervisor manages DTP stage transitions; ChatService manages chat state |

---

## 🧭 Two systems in one repo

### System A: Legacy DTP Copilot (end-to-end workflow)

**What it is**: the original procurement copilot that runs the DTP methodology (DTP-01 to DTP-06). Users work inside a case, chat with the copilot, review artifacts, and approve/reject decisions.

**Key API surface**:
- `/api/cases/*`, `/api/chat`, `/api/decisions/*`, `/api/ingest/*`
- Artifact download: `GET /api/cases/{case_id}/artifacts/{artifact_id}/export?export_format=docx|pdf` (Word/PDF from stored agent artifacts)

**Primary UI**:
- Legacy Streamlit UI (`frontend/`) or Next.js case routes (`frontend-next/src/app/cases/*`)

### System B: Opportunity Heatmap (scoring + intake + copilot)

**What it is**: a separate agentic system that prioritizes opportunities using a deterministic scoring framework plus optional LLM layers (explanations, policy checks, bounded learning, fallback interpretation).

**Key API surface**:
- `/api/heatmap/*` (opportunities, run/status, feedback, approve bridge, intake, copilot, **category-cards** extract/upload/apply/apply-and-rerun)

**Primary UI**:
- Next.js heatmap routes (`frontend-next/src/app/heatmap`, `/intake`)

### What is shared vs isolated?

**Shared**
- One FastAPI process: `backend/main.py` on port 8000
- One Next.js app (if used): `frontend-next`

**Isolated (by design)**
- Databases:
  - Legacy DTP: `data/datalake.db`
  - Heatmap: `data/heatmap.db`
- Vector stores / memory:
  - Legacy DTP: Chroma collection `sourcing_documents`
  - Heatmap: Chroma collection `heatmap_documents`
- Agents and state machines:
  - Legacy: `backend/agents`, `backend/supervisor`, `backend/services/*`
  - Heatmap: `backend/heatmap/*` (LangGraph scoring pipeline)

### Folder Structure

```
agentic-sourcing-poc/
│
├── frontend/                    # Legacy Streamlit UI (DTP System)
│   ├── app.py                   # Main entry point
│   ├── api_client.py            # Backend communication
│   └── pages/
│       ├── case_dashboard.py    # Case list & metrics
│       ├── case_copilot.py      # Procurement Workbench
│       └── knowledge_management.py  # Document/data upload
│
├── frontend-next/               # New Next.js UI (Heatmap + Copilot)
│   ├── src/app/
│   │   ├── layout.tsx           # Root layout (Syne/DM Sans fonts, sidebar)
│   │   ├── globals.css          # Premium dark-mode design tokens
│   │   ├── heatmap/page.tsx     # Sourcing Priority Heatmap + KPI Dashboard
│   │   ├── intake/page.tsx      # Business Intake form
│   │   ├── kpi/page.tsx         # KPI Dashboard page
│   │   └── cases/[id]/copilot/  # Case Copilot (60/40 split)
│   │       └── page.tsx         # Triage, Signals, Chat, Governance
│   └── package.json             # Dependencies (recharts, framer-motion)
│
├── backend/                     # All business logic
│   ├── main.py                  # FastAPI server
│   ├── supervisor/              # Central orchestration
│   ├── agents/                  # Official agents (7 modules)
│   ├── tasks/                   # Sub-tasks (internal to agents)
│   ├── artifacts/               # Artifact builders & renderers
│   ├── ingestion/               # Data ingestion pipelines
│   ├── rag/                     # Vector retrieval (ChromaDB)
│   ├── persistence/             # Data lake (SQLite + SQLModel)
│   ├── services/                # Business logic layer
│   ├── scripts/                 # Utility & seed scripts
│   └── heatmap/                 # Agentic Heatmap (separate SQLite + LangGraph)
│       ├── agents/              # Pipeline agents + graph.py
│       ├── persistence/         # heatmap_models, heatmap_database
│       ├── services/            # feedback_service, case_bridge, intake_scoring
│       ├── context_builder.py   # Spend/category context; FIS TCV vs ACV
│       ├── heatmap_router.py    # /api/heatmap/* (incl. intake)
│       ├── run_pipeline_init.py # Batch pipeline + DB (keeps intake rows)
│       └── seed_synthetic_data.py
│
├── shared/                      # Cross-cutting modules
│   ├── schemas.py               # Pydantic schemas
│   └── constants.py             # Enums
│
└── data/                        # Databases & synthetic data
    ├── datalake.db              # SQLite data lake
    ├── heatmap.db               # Heatmap scoring database
    ├── heatmap/                 # category_cards.json; heatmap/synthetic/*.csv (generated)
    ├── chroma_db/               # ChromaDB vector store
    └── cases_seed.json          # Pre-seeded case data
```

---

## 🚀 Quick Start (pick a track)

### Prerequisites
- Python 3.9+
- Node.js (for Next.js UI)
- Optional: OpenAI API key (enables LLM features; both systems have fallbacks)

### Install

```bash
pip install -r requirements.txt
cd frontend-next && npm install
```

### Start the shared backend (required for both systems)

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### Track 1: Heatmap-only demo (recommended quick path)

```bash
# (One-time) generate synthetic heatmap CSVs + seed/persist scored opportunities
python backend/heatmap/seed_synthetic_data.py

# Start Next.js UI
cd frontend-next && npm run dev
```

Open:
- Heatmap UI: `http://localhost:3000/heatmap`
- Intake UI: `http://localhost:3000/intake`
- API docs: `http://localhost:8000/docs`

### Track 2: Legacy DTP demo (cases + chat + artifacts)

```bash
# (One-time) seed legacy cases + documents for RAG
python backend/scripts/seed_it_demo_data.py

# Optional legacy UI
streamlit run frontend/app.py
```

Open:
- Streamlit legacy UI: `http://localhost:8501`
- Or use Next.js case routes under `http://localhost:3000/cases`

### Track 3: Bridge demo (Heatmap → create DTP cases)

1. Run **Track 1** (heatmap has opportunities)
2. Approve one or more opportunities in Heatmap UI (calls `/api/heatmap/approve`)
3. Navigate to the created case in the Legacy DTP UI (Next.js `/cases/[id]/copilot` or Streamlit dashboard)

---

## 📡 API Reference (by system)

### Legacy DTP
- **Cases**: `GET /api/cases`, `GET /api/cases/{id}`, `POST /api/cases`
- **Chat**: `POST /api/chat`
- **Decisions**: `POST /api/decisions/approve`, `POST /api/decisions/reject`
- **Ingestion**: `POST /api/ingest/document`, `POST /api/ingest/data`, etc.

### Opportunity Heatmap
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/heatmap/opportunities` | List scored opportunities (T1–T4) |
| POST | `/api/heatmap/run` | Trigger scoring pipeline (background) |
| GET | `/api/heatmap/run/status` | Pipeline status |
| POST | `/api/heatmap/feedback` | Submit human override feedback |
| POST | `/api/heatmap/approve` | **Bridge**: approve opportunities → create legacy DTP cases |
| GET | `/api/heatmap/intake/categories` | Category keys from `category_cards.json` |
| POST | `/api/heatmap/intake/preview` | PS_new preview (no DB write) |
| POST | `/api/heatmap/intake` | Persist intake opportunity |
| POST | `/api/heatmap/qa` | Heatmap copilot: explain-only Q&A |
| POST | `/api/heatmap/policy/check` | Feedback vs policy suggestion |
| POST | `/api/heatmap/category-cards/assist` | Category cards patch suggestion |

---

## 🔐 Environment Variables (high-signal)

### Shared
- `OPENAI_API_KEY`: enables LLM-powered features; both systems have graceful fallbacks when unset.

### Heatmap
- `HEATMAP_FIS_USE_ACV=1`: use ACV instead of TCV for FIS in batch scoring
- `HEATMAP_LEARNING=0`: disable review-memory learning layer
- `HEATMAP_LEARNING_MODEL`: model for review-memory synthesis (default `gpt-4o-mini`)
- `HEATMAP_COPILOT_MODEL`: model for heatmap copilot explanations (default falls back to learning model)
- `HEATMAP_INTERPRETER_MODEL`: model for interpreter fallbacks (default `gpt-4o-mini`)

---

## 🔐 Governance Rules

1. **Supervisor manages DTP stage transitions** — ChatService orchestrates chat-level state
2. **LLM-First intent classification** — LLMResponder dynamically classifies all user intents
3. **Human approval required** — For any DECIDE-type recommendation or stage change
4. **Traceability** — Every artifact includes `grounded_in` references; missing = UNVERIFIED
5. **Preflight readiness check** — Cases blocked if prerequisites missing for current stage
6. **Artifact persistence** — All agent outputs saved as ArtifactPacks with execution metadata

---

## 🎨 UI Design

### New Heatmap System (Next.js)
Premium dark-mode glassmorphic design with Syne/DM Sans typography:

- **Priority Heatmap** (`/heatmap`) — KPI stat cards, Table/Matrix toggle, Recharts scatter chart, KLI Outcome Matrix, **Heatmap copilot** (Q&A, policy check, category-cards assist); see system doc **User experience impact** for how this shapes trust and workload
- **Case Copilot** (`/cases/[id]/copilot`) — 60/40 split-screen with evidence/artifacts on the left and chat + Decision Console on the right (Cursor-style workflow). Includes **Word round-trip** (download `.docx` → edit in Microsoft Word → re-upload), artifact **pack export**, and copilot prompts that teach that flow; see [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) §6.11 and [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) (Chat lifecycle → Word round-trip).
- **Case Copilot (no case selected)** (`/cases/copilot`) — default split-shell empty state with links back to Case Dashboard/Heatmap
- **Business Intake** (`/intake`) — New sourcing request form with API-backed **PS_new** preview and submit
- **KPI Dashboard** (`/kpi`) — Performance metrics

### Legacy DTP System (Streamlit)
- **Case Dashboard** — Case list & metrics
- **Case Copilot** — Procurement Workbench with dark-mode agent activity log
- **Knowledge Management** — Document/data upload

For detailed UI/UX flow, see [System Documentation - UI/UX Flow](SYSTEM_DOCUMENTATION.md#uiux-flow).

---

## 📦 Artifact System

For complete artifact system documentation including structure, verification status, and persistence, see [System Documentation - Artifact System](SYSTEM_DOCUMENTATION.md#artifact-system).

---

## 🤖 Agents & Tasks

For detailed information about all 7 agents, their sub-tasks, execution flow, and examples, see [System Documentation - Agent System](SYSTEM_DOCUMENTATION.md#agent-system) and [Task Execution Hierarchy](SYSTEM_DOCUMENTATION.md#task-execution-hierarchy).

---

## 📁 Data

Comprehensive synthetic test data focused on IT & Corporate Services:

### Test Cases (10 Cases covering DTP-01 to DTP-04)
See [Quick Start](#-quick-start) for the full list of 10 supported demo cases.

### Documents in ChromaDB (Context-Aware RAG)
Agents now dynamically retrieve these documents to provide specific advice:

| Document Type | Examples | Used By |
|---------------|----------|---------|
| **Market Reports** | Telecom 2025, Fleet 2025 | StrategyAgent (DTP-01) |
| **RFP Templates** | Cybersecurity SOC, Hardware, Cloud | RFxDraftAgent (DTP-02/03) |
| **Proposals** | Microsoft EA, AWS, Workday, SecureNet | NegotiationAgent (DTP-04) |
| **Contracts** | MSA Template, Service Desk SOW | ContractSupportAgent (DTP-05) |
| **Guides** | Cloud Migration Implementation Guide | ImplementationAgent (DTP-06) |

Seed via: `python backend/scripts/seed_it_demo_data.py`

---

### Proactive Assistant Workflow
- **State-Aware Progression triggered by LLM**: The system proactively guides users through DTP stages (e.g., "Ready to move to Negotiation?").
- **Persistence Fixes**: Robust state management ensures no context is lost during multi-turn decision flows.

### Decision + Chat Synchronization (March 2026)
- **Decision console in chat panel**: Approve/Revision actions are now performed from the right Copilot panel.
- **Immediate Copilot reaction**: After approve/reject, the UI automatically sends a follow-up prompt to `/api/chat` so users get state-aware next-step guidance immediately.
- **Left panel as context desk**: Governance on the left is now status/context while artifacts and logs remain visible for decision support.

### Bug Fixes
- Fixed duplicate `process_message` method in ChatService
- Fixed Pydantic/dict handling for AgentActionLog and BudgetState
- Fixed "Approve Loop" where new commands were blocked by pending approval state
- Fixed unrequested email template generation in LLM responses
- Fixed Windows encoding issues (emojis → ASCII)
- **[Feb 2026]** Fixed decision persistence across DTP stages (preflight checks now work correctly)
- **[Feb 2026]** Fixed circular dependency in DTP-02 prerequisites  
- **[Feb 2026]** Fixed `budget_state` initialization in workflow

### Verification & Testing
- **End-to-End Simulation**: `scripts/simulate_case_001_journey.py` verifies the full DTP-01 to DTP-06 lifecycle.
- **Data Enhancements**:
  - New comprehensive seed script with 5 cases
  - 16 suppliers with differentiated performance
  - 11 documents for RAG retrieval
  - Seed now upserts synthetic `document_records` so `/api/documents` lists demo artifacts consistently (not only Chroma chunks)

For detailed change log, see [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md#recent-changes-january-2026).

---

## ⚠️ Notes

- **Research POC** — Not production-ready
- **Synthetic data** — All metrics are illustrative
- **No authentication** — Add API keys for production
- **Persistence** — Uses local SQLite (not suitable for stateless cloud deployments without external DB)

---

## 📜 License

Research POC — Not for production use

---

## 🛠️ Development Status

| Component | Status |
|-----------|--------|
| 7 Official Agents | ✅ Complete |
| Task System | ✅ Complete |
| Artifact System | ✅ Complete |
| Legacy Streamlit UI | ✅ Complete |
| Next.js Heatmap + Copilot UI | ✅ Complete |
| Agentic Scoring Engine | ✅ Complete |
| KPI Dashboard & KLI Matrix | ✅ Complete |
| Live Agentic Process Log | ✅ Complete |
| Synthetic Data & Demo | ✅ Complete |
| Microsoft Entra ID Auth | 🔜 Planned |
| Azure AI Search Integration | 🔜 Planned |
| Production Hardening | 🔜 Planned |
