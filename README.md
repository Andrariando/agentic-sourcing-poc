# Procurement Agentic System — Enterprise POC

A **human-in-the-loop, multi-agent decision-support system** for procurement sourcing, built on the Dynamic Transaction Pipeline (DTP-01 to DTP-06) methodology.

> **Current Version** — Dual-Frontend System with 7 Official Agents, Artifact System & Agentic Sourcing Heatmap

---

## 📚 Documentation

This project includes comprehensive documentation covering all aspects of the system:

### Core Documentation

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

## 🏗️ Architecture

### Official Agents (7 First-Class Modules)

### Official Agents: What They Think & Decide

The system consists of **7 specialized agents**, each with a distinct "brain" (logic), data access, and decision responsibility.

| Agent | DTP Stage | Thinking Process (Logic) | Key Decisions (Human Approval) |
|-------|-----------|--------------------------|-------------------------------|
| **Supervisor** | *All* | **Orchestrator**: Monitors case state, validates inputs, and decides which specialist agent to call. It acts as the "Manager" ensuring no steps are skipped. | Routing to next stage, Handling exceptions |
| **Sourcing Signal** | DTP-01 | **Scanner**: "Do we have a problem/opportunity?"<br>1. Checks contract expiry dates<br>2. Detects spend anomalies (>15% variance)<br>3. Flags supplier risk (score < 6.0) | Create new case? (Y/N) |
| **Strategy Agent** | DTP-01 | **Strategist**: "How should we approach this?"<br>1. Retrieves market reports & benchmarks<br>2. Analyzes supplier leverage<br>3. Recommends path: Renewal, RFP, or Renegotiation | Confirm Strategy (e.g., "Go to RFP") |
| **RFx Draft Agent** | DTP-02 | **Author**: "What are our requirements?"<br>1. Pulls similar past RFPs (RAG)<br>2. Structures technical vs commercial requirements<br>3. Drafts full RFP document | Approve RFP release to market |
| **Supplier Scoring** | DTP-03 | **Evaluator**: "Who is the best fit?"<br>1. Numerical scoring of proposals against weightings<br>2. identifying compliance gaps<br>3. Ranking suppliers (1st, 2nd, 3rd) | Shortslist/Finalist Selection |
| **Negotiation Support** | DTP-04 | **Coach**: "How do we get the best deal?"<br>1. Analyzes proposal vs. market benchmark<br>2. Identifies specific trade-offs (Price vs Term)<br>3. Generates script/email for negotiation | strategies and counter-offers |
| **Contract Support** | DTP-05 | **Paralegal**: "Are the terms safe?"<br>1. Extracts key clauses (Indemnity, SLA, Term)<br>2. Flags deviations from policy<br>3. Generates signature pack | Contract Signature |
| **Implementation** | DTP-06 | **Planner**: "How do we realize value?"<br>1. Creates rollout schedule (Gantt logic)<br>2. Defines success KPIs<br>3. Assigns resource stakeholders | Activate Project |

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

### System Flow

```
User Message → Supervisor (Intent Classification)
                ↓
         ActionPlan (agent + tasks)
                ↓
         Agent Execution (tasks → ArtifactPack)
                ↓
         Persist Artifacts → Update State (Supervisor only)
                ↓
         UI: Procurement Workbench (Artifacts + Next Actions)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/Andrariando/agentic-sourcing-poc.git
cd agentic-sourcing-poc

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
```

### Running Locally

```bash
# Terminal 1: Start Backend (from project root)
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start Next.js Frontend (New Heatmap System)
cd frontend-next && npm run dev

# Terminal 3 (Optional): Start Legacy Streamlit Frontend
streamlit run frontend/app.py
```

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Next.js UI**: http://localhost:3000 (New Heatmap System)
- **Streamlit UI**: http://localhost:8501 (Legacy DTP System)

### Seed Demo Data (IT & Corporate Services)

```bash
# Seed 10 realistic IT cases with DTP-ready data
python backend/scripts/seed_it_demo_data.py
```

This creates **10 test cases covering DTP-01 to DTP-04** (Strategy through Negotiation):

| Case ID | Name | Category | Stage | Description | Key Decision |
|---------|------|----------|-------|-------------|--------------|
| CASE-001 | IT Managed Services Renewal | IT_SERVICES | DTP-01 | Renewal with TechCorp, pricing above market | Review renewal terms vs market |
| CASE-002 | End-User Hardware Refresh | HARDWARE | DTP-01 | 2,500 unit refresh (Dell vs HP/Lenovo) | Approve competitive RFP |
| CASE-009 | Global Telecom Consolidation | TELECOM | DTP-01 | Consolidating 15 countries to 1-2 carriers | Strategic sourcing approval |
| CASE-003 | Cloud Migration (AWS/Azure) | CLOUD | DTP-02 | Migrating 40% workloads to cloud | Approve technical requirements |
| CASE-007 | SD-WAN Upgrade | NETWORK | DTP-02 | Replacing MPLS with SD-WAN | Approve vendor shortlist |
| CASE-010 | DevOps Toolchain Standards | SOFTWARE | DTP-02 | Standardizing CI/CD (GitHub vs GitLab) | Approve evaluation matrix |
| CASE-004 | Cybersecurity SOC Services | SECURITY | DTP-03 | Scoring proposals (SecureNet vs CyberGuard) | Select finalists for presentation |
| CASE-008 | HRIS Platform Selection | SAAS | DTP-03 | Workday vs Oracle HCM evaluation | Confirm scoring results |
| CASE-005 | Data Center Co-location | INFRASTRUCTURE | DTP-04 | Equinix negotiation (power rates) | Approve final terms |
| CASE-006 | Microsoft EA Renewal | SOFTWARE | DTP-04 | E3 to E5 step-up, 15% uplift proposed | Authorize negotiation strategy |

**Data Seeded**:
- **16 suppliers** with differentiated performance (e.g., declining trends, risk flags)
- **11 context-aware documents** in ChromaDB (Proposals, RFPs, Market Reports)
- **SLA events** and spend anomalies to trigger specific agent behaviors

---

## 🎮 Demo Options

### Option A: Breadth Demo (10 Cases at Different Stages)
Use `seed_it_demo_data.py` to show variety of cases across DTP-01 to DTP-04.
- Best for: Showing system handles multiple parallel cases
- Limitation: Each case is at a specific stage, not end-to-end

### Option B: Depth Demo (One Case End-to-End)
Use `run_happy_path_demo.py` to show complete DTP-01 → DTP-06 workflow.
- Best for: Showing complete procurement lifecycle
- Creates: `CASE-DEMO-001` with full history and artifacts

```bash
# Option A: Breadth Demo
python backend/scripts/seed_it_demo_data.py

# Option B: Depth Demo
python backend/scripts/run_happy_path_demo.py
```

For detailed demo instructions, see [System Documentation - Demo & Testing](SYSTEM_DOCUMENTATION.md#demo--testing).

---

## 📡 API Reference

### Case Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases` | List all cases |
| GET | `/api/cases/{id}` | Get case details |
| POST | `/api/cases` | Create new case |

### Copilot Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message to copilot (returns ArtifactPack) |

### Human Decisions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/decisions/approve` | Approve recommendation |
| POST | `/api/decisions/reject` | Reject recommendation |

### Document Ingestion (RAG)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/document` | Upload PDF/DOCX/TXT |
| GET | `/api/documents` | List ingested documents |
| DELETE | `/api/documents/{id}` | Delete document |

### Structured Data Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/data/preview` | Preview CSV/Excel |
| POST | `/api/ingest/data` | Ingest to data lake |
| GET | `/api/ingest/history` | View ingestion history |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

### Sourcing Heatmap System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/heatmap/opportunities` | List all scored opportunities (T1-T4) |
| POST | `/api/heatmap/feedback` | Submit human override feedback |
| POST | `/api/heatmap/approve` | Approve opportunities → legacy DTP cases (via case bridge) |
| POST | `/api/heatmap/run` | Trigger batch scoring engine (background on API server) |
| GET | `/api/heatmap/run/status` | Pipeline job status and last error |
| GET | `/api/heatmap/intake/categories` | Category list from `category_cards.json` |
| POST | `/api/heatmap/intake/preview` | PS_new preview (no DB write) |
| POST | `/api/heatmap/intake` | Save new intake opportunity (`source=intake`; batch re-runs keep these rows) |
| POST | `/api/heatmap/qa` | Heatmap copilot: natural-language explanations (scores unchanged) |
| POST | `/api/heatmap/policy/check` | Compare feedback text to `category_cards.json` (suggestion) |
| POST | `/api/heatmap/category-cards/assist` | Suggested JSON patch for category cards (manual merge) |

**FIS / contract value:** default **TCV**; set env `HEATMAP_FIS_USE_ACV=1` to use **ACV** for batch scoring.

**Review memory (learn from feedback):** Human feedback is embedded into Chroma; batch scoring and intake preview apply a **bounded** total-score nudge via `feedback_memory.py` (optional **`gpt-4o-mini`** completion when `OPENAI_API_KEY` is set). Env: **`HEATMAP_LEARNING_MODEL`** (default `gpt-4o-mini`), **`HEATMAP_LEARNING=0`** to disable.

**Heatmap copilot** (`heatmap_copilot.py` + `/api/heatmap/qa`, `/policy/check`, `/category-cards/assist`): explain-only Q&A over DB + feedback, policy hints, and draft category-card JSON — **does not** overwrite scores or files. Optional **`HEATMAP_COPILOT_MODEL`** (defaults to `HEATMAP_LEARNING_MODEL` then `gpt-4o-mini`). **How this affects users** (trust, fallbacks, review memory vs. explanations): see `SYSTEM_DOCUMENTATION.md` → **User experience impact: Heatmap copilot and review memory**.

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
- **Case Copilot** (`/cases/[id]/copilot`) — 60/40 split-screen with evidence/artifacts on the left and chat + Decision Console on the right (Cursor-style workflow)
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
