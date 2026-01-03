# Agentic Sourcing Copilot — Enterprise POC

A **human-in-the-loop, multi-agent decision-support system** for procurement sourcing, built on the Dynamic Transaction Pipeline (DTP-01 to DTP-06) methodology.

> **Current Version** — Procurement Workbench with 7 Official Agents & Artifact System

---

## 🎯 Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Decision is focal point** | AI advises, human decides |
| **Rules > LLM** | Deterministic rules before any LLM reasoning |
| **No autonomous decisions** | All recommendations require human approval |
| **Full traceability** | Every artifact grounded in data with verification status |
| **Grounded retrieval** | Answers cite uploaded documents/data |
| **Supervisor-only state changes** | Only Supervisor Agent can modify case state |

---

## 🏗️ Architecture

### Official Agents (7 First-Class Modules)

1. **Supervisor Agent** — Orchestrates workflow, validates inputs, routes to agents
2. **Sourcing Signal Agent** — Monitors contracts, spend, performance for opportunities
3. **Supplier Scoring Agent** — Evaluates and ranks suppliers
4. **RFx Draft Agent** — Assembles RFx documents (RFI/RFP/RFQ)
5. **Negotiation Support Agent** — Provides negotiation insights (NO award decisions)
6. **Contract Support Agent** — Extracts terms, validates, prepares handoff
7. **Implementation Agent** — Rollout planning and value capture

### Folder Structure

```
agentic-sourcing-poc/
│
├── frontend/                    # Streamlit UI
│   ├── app.py                   # Main entry point
│   ├── api_client.py            # Backend communication
│   └── pages/
│       ├── case_dashboard.py    # Case list & metrics
│       ├── case_copilot.py      # Procurement Workbench
│       └── knowledge_management.py  # Document/data upload
│
├── backend/                     # All business logic
│   ├── main.py                  # FastAPI server
│   │
│   ├── supervisor/              # Central orchestration
│   │   ├── state.py             # State management
│   │   └── router.py            # Two-level intent routing
│   │
│   ├── agents/                  # Official agents (7 modules)
│   │   ├── base.py              # Base agent with retrieval
│   │   ├── supervisor_agent.py
│   │   ├── sourcing_signal_agent.py
│   │   ├── supplier_scoring_agent.py
│   │   ├── rfx_draft_agent.py
│   │   ├── negotiation_support_agent.py
│   │   ├── contract_support_agent.py
│   │   └── implementation_agent.py
│   │
│   ├── tasks/                   # Sub-tasks (internal to agents)
│   │   ├── base_task.py         # Task execution hierarchy
│   │   ├── registry.py          # Task registry
│   │   ├── planners.py          # Deterministic playbooks
│   │   ├── signal_tasks.py
│   │   ├── scoring_tasks.py
│   │   ├── rfx_tasks.py
│   │   ├── negotiation_tasks.py
│   │   ├── contract_tasks.py
│   │   └── implementation_tasks.py
│   │
│   ├── artifacts/               # Artifact builders & renderers
│   │   ├── builders.py          # ArtifactPack construction
│   │   ├── renderers.py         # UI formatting
│   │   └── utils.py             # Grounding utilities
│   │
│   ├── ingestion/               # Data ingestion pipelines
│   │   ├── document_ingest.py   # PDF/DOCX/TXT → ChromaDB
│   │   ├── data_ingest.py       # CSV/Excel → SQLite
│   │   └── validators.py        # Schema validation
│   │
│   ├── rag/                     # Vector retrieval
│   │   ├── vector_store.py      # ChromaDB wrapper
│   │   └── retriever.py         # Document retriever
│   │
│   ├── persistence/             # Data lake
│   │   ├── database.py          # SQLite connection
│   │   └── models.py            # SQLModel tables (includes Artifact)
│   │
│   ├── services/                # Business logic layer
│   │   ├── case_service.py      # Case + artifact management
│   │   ├── chat_service.py      # Copilot with Supervisor
│   │   └── ingestion_service.py # Ingestion orchestration
│   │
│   └── scripts/                 # Utility scripts
│       └── seed_synthetic_data.py  # Happy Path demo data
│
├── shared/                      # Cross-cutting modules
│   ├── schemas.py               # Pydantic schemas (ArtifactPack, etc.)
│   └── constants.py             # Enums (AgentName, ArtifactType, etc.)
│
└── data/                        # Synthetic data & databases
    ├── datalake.db              # SQLite data lake
    ├── chroma_db/               # ChromaDB vector store
    ├── synthetic/                # Synthetic data files
    └── synthetic_docs/           # Sample documents for RAG
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
# Terminal 1: Start Backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start Frontend
streamlit run frontend/app.py
```

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8501

### Seed Synthetic Data (Happy Path Demo)

```bash
# Seed CASE-0001 and sample data
python backend/scripts/seed_synthetic_data.py
```

This creates:
- **CASE-0001** — IT Services Contract Renewal
- Supplier performance data (3 suppliers)
- Spend data with anomalies
- SLA events
- Sample documents in ChromaDB

---

## 🎮 Happy Path Demo Sequence

Open **CASE-0001** in the Procurement Workbench and run:

1. **"Scan signals"** → Signal Report with urgency score + recommendations
2. **"Score suppliers"** → Supplier Scorecard + Shortlist (SUP-001 ranked #1)
3. **"Draft RFx"** → RFx Draft Pack + Q&A Tracker
4. **"Support negotiation"** → Negotiation Plan + Leverage Points + Targets
5. **"Extract key terms"** → Key Terms Extract + Validation Report + Handoff Packet
6. **"Generate implementation plan"** → Implementation Checklist + Early Indicators + Value Capture

Each step produces **ArtifactPacks** with:
- Multiple artifacts (reports, scorecards, drafts)
- Next best actions
- Risk items
- Grounding references (doc IDs, data sources)

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

---

## 🔐 Governance Rules

1. **Supervisor is ONLY component that writes case state** — All other agents return outputs only
2. **Decision logic hierarchy** — Rules → Retrieval → Analytics → LLM (in that order)
3. **Human approval required** — For any DECIDE-type recommendation or stage change
4. **Traceability** — Every artifact includes `grounded_in` references; missing = UNVERIFIED
5. **Two-level intent routing** — (UserGoal, WorkType) → Agent + Tasks
6. **Artifact persistence** — All agent outputs saved as ArtifactPacks with verification status

---

## 🎨 UI Design

**Procurement Workbench** — Three-panel layout:

- **Top Panel**: Next Best Actions (stage-specific quick actions)
- **Left Panel**: Artifacts (tabs: Signals, Scoring, RFx, Negotiation, Contract, Implementation, History)
- **Center Panel**: Chat Copilot (conversational interface)
- **Right Panel**: Governance (stage, status, approval controls)

MIT color system:
- **MIT Navy** (`#003A8F`) — Headers, structure
- **MIT Cardinal Red** (`#A31F34`) — Actions, alerts
- **Near Black** (`#1F1F1F`) — Body text
- **Charcoal** (`#4A4A4A`) — Secondary text

---

## 📦 Artifact System

Agents produce **ArtifactPacks** containing:

- **Artifacts** — Work products (reports, scorecards, drafts, checklists)
- **Next Actions** — Recommended next steps with rationale
- **Risks** — Identified risks with mitigation
- **Grounding** — References to source documents/data
- **Verification Status** — VERIFIED, PARTIAL, or UNVERIFIED

Artifact types include:
- `SIGNAL_REPORT`, `SUPPLIER_SCORECARD`, `RFX_DRAFT_PACK`
- `NEGOTIATION_PLAN`, `KEY_TERMS_EXTRACT`, `IMPLEMENTATION_CHECKLIST`
- And more (see `shared/constants.py` for full list)

---

## 🧪 Task System

Each agent has **sub-tasks** that follow the decision hierarchy:

1. **run_rules()** — Deterministic policy checks
2. **run_retrieval()** — ChromaDB + SQLite data retrieval
3. **run_analytics()** — Scoring, normalization, comparison
4. **run_llm()** — Narrative generation (only if needed)

Tasks are **internal to agents** and not exposed separately in UI.

---

## 📁 Data

Synthetic test data:
- **CASE-0001** — IT Services contract renewal scenario
- **3 Suppliers** — Performance data with differentiation
- **12 months spend** — With anomaly detection
- **SLA events** — Supplier performance issues
- **Sample documents** — RFP template, benchmarks, policy, contract terms

Seed via: `python backend/scripts/seed_synthetic_data.py`

---

## ⚠️ Notes

- **Research POC** — Not production-ready
- **Synthetic data** — All metrics are illustrative
- **No authentication** — Add API keys for production
- **Backward compatible** — Legacy agents still work alongside new system

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
| Procurement Workbench UI | ✅ Complete |
| Synthetic Data & Demo | ✅ Complete |
| Production Hardening | 🔜 Planned |
