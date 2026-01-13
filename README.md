# Agentic Sourcing Copilot — Enterprise POC

A **human-in-the-loop, multi-agent decision-support system** for procurement sourcing, built on the Dynamic Transaction Pipeline (DTP-01 to DTP-06) methodology.

> **Current Version** — Procurement Workbench with 7 Official Agents & Artifact System

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

### Seed Synthetic Data (Comprehensive Demo)

```bash
# Seed 5 complete cases with full data
python backend/scripts/seed_comprehensive_data.py
```

This creates **5 comprehensive test cases** with full end-to-end data:

| Case ID | Name | Category | DTP Stage | Description |
|---------|------|----------|-----------|-------------|
| CASE-0001 | IT Services Contract Renewal | IT_SERVICES | DTP-01 | Contract expiring in 35 days |
| CASE-0002 | Office Supplies Cost Reduction | OFFICE_SUPPLIES | DTP-01 | Spend anomaly (+20% over budget) |
| CASE-0003 | Cloud Infrastructure Migration | CLOUD_SERVICES | DTP-02 | AWS/Azure/GCP evaluation |
| CASE-0004 | Marketing Agency Selection | MARKETING_SERVICES | DTP-03 | 4 agency proposals to evaluate |
| CASE-0005 | Facilities Management Negotiation | FACILITIES_MANAGEMENT | DTP-04 | Incumbent requesting 8% increase |

**Data Seeded**:
- **16 suppliers** across 5 categories with differentiated performance
- **12 months of spend data** per category with anomalies
- **SLA events** (breaches, warnings, compliance) for supplier differentiation
- **11 documents** (71 chunks) in ChromaDB:
  - RFP templates, market benchmarks, policy docs
  - Cloud provider comparisons, migration guides
  - Contract templates, evaluation rubrics

**Sample Chatbot Interactions**:
```
CASE-0001: "What's the renewal strategy for this case?"
CASE-0002: "Why are costs increasing?"
CASE-0003: "Compare the cloud providers"
CASE-0004: "Evaluate the marketing proposals"
CASE-0005: "What's our negotiation position?"
```

---

## 🎮 Happy Path Demo

Run the complete demo workflow:

```bash
# 1. Generate demo case with full workflow
python backend/scripts/run_happy_path_demo.py

# 2. Start backend
python -m uvicorn backend.main:app --reload --port 8000

# 3. Start frontend (in another terminal)
streamlit run frontend/app.py

# 4. Open CASE-DEMO-001 in the UI
#    - Navigate to Case Dashboard
#    - Select CASE-DEMO-001
#    - View complete chat history and artifacts
```

The demo creates `CASE-DEMO-001` with:
- Full DTP-01 to DTP-06 workflow
- Complete chat history from all interactions
- All artifacts from each stage
- Execution metadata for audit trail

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

---

## 🔐 Governance Rules

1. **Supervisor is ONLY component that writes case state** — All other agents return outputs only
2. **Decision logic hierarchy** — Rules → Retrieval → Analytics → LLM (in that order)
3. **Human approval required** — For any DECIDE-type recommendation or stage change
4. **Traceability** — Every artifact includes `grounded_in` references; missing = UNVERIFIED
5. **Hybrid intent classification** — Rule-based (fast) + LLM fallback (accurate) for ambiguous cases
6. **Artifact persistence** — All agent outputs saved as ArtifactPacks with execution metadata

---

## 🎨 UI Design

**Procurement Workbench** — Modern SaaS layout:

- **Top**: Condensed case header (ID, category, stage, status)
- **Main**: Two-column layout
  - **Left (60%)**: Case details (overview, strategy, signals, governance, timeline)
  - **Right (40%)**: Chat interface (scrollable history, message input)
- **Bottom**: Full-width artifacts panel (tabs: Signals, Scoring, RFx, Negotiation, Contract, Implementation, History, Audit Trail)

For detailed UI/UX flow, see [System Documentation - UI/UX Flow](SYSTEM_DOCUMENTATION.md#uiux-flow).

---

## 📦 Artifact System

For complete artifact system documentation including structure, verification status, and persistence, see [System Documentation - Artifact System](SYSTEM_DOCUMENTATION.md#artifact-system).

---

## 🤖 Agents & Tasks

For detailed information about all 7 agents, their sub-tasks, execution flow, and examples, see [System Documentation - Agent System](SYSTEM_DOCUMENTATION.md#agent-system) and [Task Execution Hierarchy](SYSTEM_DOCUMENTATION.md#task-execution-hierarchy).

---

## 📁 Data

Comprehensive synthetic test data:

### Test Cases (5 cases)
| Case | Category | Stage | Key Features |
|------|----------|-------|--------------|
| CASE-0001 | IT_SERVICES | DTP-01 | Contract renewal, 3 suppliers, stable performance |
| CASE-0002 | OFFICE_SUPPLIES | DTP-01 | Cost anomaly trigger, spend trending up |
| CASE-0003 | CLOUD_SERVICES | DTP-02 | AWS/Azure/GCP comparison, migration planning |
| CASE-0004 | MARKETING_SERVICES | DTP-03 | 4 agencies, evaluation rubric, creative scoring |
| CASE-0005 | FACILITIES_MANAGEMENT | DTP-04 | Incumbent negotiation, market benchmarks |

### Suppliers (16 suppliers across 5 categories)
- **IT Services**: TechCorp Solutions, Global IT Partners, CloudFirst Systems
- **Office Supplies**: OfficeMax Pro, Corporate Supply Co, BulkOffice Direct
- **Cloud Services**: AWS, Azure, Google Cloud Platform
- **Marketing**: Creative Minds Agency, Digital First, B2B Marketing Pros, Integrated Brand
- **Facilities**: FacilityPro Services, BuildingCare Plus, Integrated Facilities Group

### Documents in ChromaDB (11 documents, 71 chunks)
- RFP templates (IT, Marketing)
- Market benchmarks (IT, Office, Facilities)
- Cloud provider comparison \u0026 migration guides
- Contract templates \u0026 SOW
- Procurement policy \u0026 DTP gates

Seed via: `python backend/scripts/seed_comprehensive_data.py`

---

## 🔧 Recent Changes (January 2026)

### Bug Fixes
- Fixed duplicate `process_message` method in ChatService
- Fixed Pydantic/dict handling for AgentActionLog and BudgetState
- Fixed Windows encoding issues (emojis → ASCII)

### Data Enhancements
- New comprehensive seed script with 5 cases
- 16 suppliers with differentiated performance
- 11 documents for RAG retrieval

For detailed change log, see [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md#recent-changes-january-2026).

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
