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

## 🤖 Agent Details & Sub-Tasks

### 1. Supervisor Agent

**Purpose**: Orchestrates workflow, validates inputs, selects sourcing pathway, routes to downstream agents.

**Key Responsibilities**:
- Two-level intent classification (UserGoal, WorkType)
- Stage transition validation
- Required input validation
- Agent and task routing
- Human checkpoint enforcement
- **ONLY component allowed to write case state**

**Sub-Tasks**:
1. **`classify_intent_two_level`** — Classifies user message into (UserGoal, WorkType) using pattern matching
2. **`validate_stage_transition`** — Checks if requested action is allowed at current DTP stage
3. **`validate_required_inputs`** — Verifies all required data is present (category, supplier, contract, etc.)
4. **`select_sourcing_pathway`** — Determines sourcing approach (strategic, competitive, simplified) based on rules
5. **`route_agent_and_tasks`** — Creates ActionPlan with agent name and ordered task list
6. **`enforce_human_checkpoints`** — Determines if approval is required
7. **`update_state_and_log`** — Updates case state (dtp_stage, status, waiting_for_human) and activity log

**Outputs**:
- `STATUS_SUMMARY` artifact
- `NEXT_BEST_ACTIONS` artifact
- `ActionPlan` (internal)

**Analytical Logic**: Heuristic routing rules, context memory, retrieval of procedural references/playbooks.

---

### 2. Sourcing Signal Agent

**Purpose**: Monitors contract metadata, spend patterns, supplier performance, and approved external signals to proactively identify sourcing cases.

**Key Responsibilities**:
- Detect contract expiry signals
- Identify performance degradation
- Flag spend anomalies
- Apply relevance filters
- Generate autoprep recommendations

**Sub-Tasks**:
1. **`detect_contract_expiry_signals`** — Queries SQLite contracts table for expiring contracts (30-90 day window)
2. **`detect_performance_degradation_signals`** — Analyzes supplier performance trends for declining scores or high risk
3. **`detect_spend_anomalies`** — Statistical deviation analysis on spend patterns (2+ standard deviations)
4. **`apply_relevance_filters`** — Filters signals by category, DTP stage, and severity
5. **`semantic_grounded_summary`** — LLM narration of signals (only after retrieval/analytics)
6. **`produce_autoprep_recommendations`** — Generates next actions and required inputs for case preparation

**Outputs**:
- `SIGNAL_REPORT` — Signal details with urgency score (1-10)
- `SIGNAL_SUMMARY` — Human-readable summary
- `AUTOPREP_BUNDLE` — Recommended actions + required inputs
- `NEXT_BEST_ACTIONS` — Actionable next steps

**Analytical Logic**: Signal retrieval from SQLite + approved external feeds, structured summarization, relevance filters, semantic grounding.

**Example**: Detects contract expiring in 35 days → Urgency score 7 → Recommends "Review contract terms" + "Evaluate alternatives"

---

### 3. Supplier Scoring Agent

**Purpose**: Converts human-defined evaluation criteria into structured score inputs; processes historical performance and risk data.

**Key Responsibilities**:
- Build evaluation criteria from inputs
- Pull supplier performance data
- Pull risk indicators
- Normalize metrics for comparison
- Compute weighted scores and ranking
- Check eligibility against rules
- Generate explanations

**Sub-Tasks**:
1. **`build_evaluation_criteria`** — Constructs criteria from user inputs + templates (weights, descriptions)
2. **`pull_supplier_performance`** — Retrieves performance KPIs from SQLite (quality, delivery, responsiveness, cost variance)
3. **`pull_risk_indicators`** — Gets SLA events, breach counts, severity from SQLite
4. **`normalize_metrics`** — Normalizes all metrics to 0-10 scale for fair comparison
5. **`compute_scores_and_rank`** — Calculates weighted scores using criteria weights, ranks suppliers
6. **`eligibility_checks`** — Applies rule-based thresholds (min score, max breaches, required capabilities)
7. **`generate_explanations`** — LLM narration explaining why suppliers scored as they did

**Outputs**:
- `EVALUATION_SCORECARD` — Criteria and weights used
- `SUPPLIER_SCORECARD` — Scored table with all suppliers + ranking
- `SUPPLIER_SHORTLIST` — Top N suppliers with rationale

**Analytical Logic**: Deterministic scoring formulas, ML performance normalization (optional), rule-based eligibility checks, explanatory generation.

**Example**: Evaluates 3 suppliers → SUP-001 scores 7.8/10 (best) → SUP-002 scores 7.2/10 → SUP-003 scores 8.2/10 but has eligibility issues → Shortlist: SUP-001, SUP-003

---

### 4. RFx Draft Agent

**Purpose**: Assembles RFx drafts using templates, past examples, and structured generation based on sourcing manager inputs.

**Key Responsibilities**:
- Determine RFx path (RFI/RFP/RFQ)
- Retrieve templates and past examples
- Assemble document sections
- Check completeness
- Draft questions and requirements
- Create Q&A tracker

**Sub-Tasks**:
1. **`determine_rfx_path`** — Rules-based selection: RFI if requirements undefined, RFQ if <$50K and specs complete, RFP otherwise
2. **`retrieve_templates_and_past_examples`** — Searches ChromaDB for RFx templates and past examples by category
3. **`assemble_rfx_sections`** — Builds standard sections (Executive Summary, Scope, Technical Requirements, Pricing, etc.)
4. **`completeness_checks`** — Rule-based validation: all required sections present, no placeholder content
5. **`draft_questions_and_requirements`** — LLM generation of key questions grounded in templates
6. **`create_qa_tracker`** — Creates structured Q&A tracking table for supplier responses

**Outputs**:
- `RFX_PATH` — Determined path (RFI/RFP/RFQ) with rationale
- `RFX_DRAFT_PACK` — Complete draft document with sections
- `RFX_QA_TRACKER` — Q&A tracking table

**Analytical Logic**: Template assembly, retrieval of past RFx materials, controlled narrative generation, rule-based completeness checks.

**Example**: Category IT Services, $450K value → Determines RFP path → Retrieves IT Services RFP template → Assembles 7 sections → Completeness 85% → Generates 5 key questions → Creates tracker

---

### 5. Negotiation Support Agent

**Purpose**: Highlights bid differences, identifies negotiation levers, provides structured insights **WITHOUT making award decisions**.

**Key Responsibilities**:
- Compare supplier bids
- Extract leverage points
- Retrieve market benchmarks
- Detect price anomalies
- Propose targets and fallbacks
- Generate negotiation playbook

**Sub-Tasks**:
1. **`compare_bids`** — Structured comparison of bids (price, terms, SLA, services) with variance calculations
2. **`leverage_point_extraction`** — Identifies negotiation leverage from performance data and competitive alternatives
3. **`benchmark_retrieval`** — Searches ChromaDB for market rate benchmarks and industry standards
4. **`price_anomaly_detection`** — Statistical analysis to flag unusually high/low bids (>20% from mean)
5. **`propose_targets_and_fallbacks`** — Calculates target price (5% below lowest), fallback (lowest bid), walk-away (10% above lowest)
6. **`negotiation_playbook`** — LLM generation of talking points, give/get trades, closing techniques

**Outputs**:
- `NEGOTIATION_PLAN` — Targets, fallbacks, playbook summary
- `LEVERAGE_SUMMARY` — Identified leverage points with strength ratings
- `TARGET_TERMS` — Specific target values for key terms

**Analytical Logic**: Structured bid comparison, price anomaly detection, benchmark retrieval, negotiation heuristics.

**Example**: 3 bids received → Price spread 5.6% → Identifies competition leverage → Target: $427,500 (5% below lowest) → Fallback: $450,000 → Walk-away: $495,000 → Generates playbook with talking points

---

### 6. Contract Support Agent

**Purpose**: Extracts key award terms and prepares structured inputs for contracting and implementation.

**Key Responsibilities**:
- Extract key terms from documents
- Validate terms against policy
- Summarize term alignment
- Create implementation handoff packet

**Sub-Tasks**:
1. **`extract_key_terms`** — Retrieves contract documents from ChromaDB, extracts structured terms (pricing, term, SLA, liability, termination)
2. **`term_validation`** — Rule-based checks against policy (liability limits, SLA minimums, cure periods, payment terms)
3. **`term_alignment_summary`** — LLM narration summarizing term alignment and any issues
4. **`implementation_handoff_packet`** — Creates structured handoff with contract summary, contacts, SLA summary, payment schedule, critical dates, risk items

**Outputs**:
- `KEY_TERMS_EXTRACT` — Structured extraction of all key terms
- `TERM_VALIDATION_REPORT` — Validation results with issues flagged
- `CONTRACT_HANDOFF_PACKET` — Complete handoff for implementation team

**Analytical Logic**: Template-guided extraction, rule-based contract field validation, knowledge graph grounding (optional), term alignment.

**Example**: Extracts terms from contract doc → Validates: liability OK, SLA 99.5% OK, payment Net 30 OK → 1 issue: termination clause missing → Creates handoff with all details

---

### 7. Implementation Agent

**Purpose**: Produces rollout steps and early post-award indicators (savings + service impacts).

**Key Responsibilities**:
- Build rollout checklist
- Compute expected savings
- Define early success indicators
- Generate reporting templates

**Sub-Tasks**:
1. **`build_rollout_checklist`** — Retrieves rollout playbooks from ChromaDB, creates phased checklist (Preparation, Kick-off, Transition, Steady State)
2. **`compute_expected_savings`** — Deterministic calculations: annual savings = old value - new value, total = annual × term years, breakdown (hard 70%, soft 20%, avoidance 10%)
3. **`define_early_indicators`** — Defines KPIs for early monitoring (SLA compliance, response time, delivery, invoice accuracy, satisfaction) with risk triggers
4. **`reporting_templates`** — Generates structured templates for monthly reports, quarterly reviews, savings tracking

**Outputs**:
- `IMPLEMENTATION_CHECKLIST` — Phased rollout checklist with owners and dates
- `EARLY_INDICATORS_REPORT` — KPI definitions with targets and risk triggers
- `VALUE_CAPTURE_TEMPLATE` — Savings breakdown and reporting templates

**Analytical Logic**: Deterministic calculations, retrieval of rollout playbooks, structured reporting templates.

**Example**: Contract value $450K (old $500K) → Annual savings $50K (10%) → Total $150K over 3 years → Creates 4-phase checklist (90 days) → Defines 5 KPIs → Sets up monthly/quarterly templates

---

## 🔄 Task Execution Flow

All sub-tasks follow the same execution hierarchy:

```
Task.execute(context)
  ↓
1. run_rules(context)
   → Deterministic checks, policy validation
   → May short-circuit if rules block execution
  ↓
2. run_retrieval(context, rules_result)
   → Query ChromaDB for documents
   → Query SQLite for structured data
   → Build grounding references
  ↓
3. run_analytics(context, rules_result, retrieval_result)
   → Compute scores, normalize metrics
   → Compare, rank, detect anomalies
   → Apply eligibility rules
  ↓
4. run_llm(context, rules_result, retrieval_result, analytics_result)
   → Only if needs_llm_narration() returns True
   → Generate narrative summaries
   → Create explanations
  ↓
TaskResult(data, grounded_in, tokens_used)
```

**Key Principles**:
- **Rules first** — Never call LLM if rules block
- **Retrieval second** — Always ground in data before analysis
- **Analytics third** — Use deterministic calculations when possible
- **LLM last** — Only for narration/packaging, not decision-making

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
