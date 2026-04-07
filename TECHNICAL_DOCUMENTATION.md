# Comprehensive Technical Documentation

**Purpose**: Single reference for engineers and architects to understand this repository end-to-end—**dual-system architecture**, components, APIs, data flows, and extension points.

**Last updated**: April 2026 (aligned with current `backend/main.py`, `backend/heatmap/*`, and `frontend-next/*`)

**Related documents**

| Document | Role |
|----------|------|
| [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) | Deep narrative on DTP stages, chat lifecycle, agents, artifacts, heatmap formulas (section 15), troubleshooting |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Roadmap: review themes, quick wins, KPI/KLI tracks, suggested implementation order |
| [BUSINESS_OVERVIEW.md](BUSINESS_OVERVIEW.md) | Business translation, use cases, caveats, Azure roadmap |
| [README.md](README.md) | Quick start, tracks, env vars |
| [architecture.puml](architecture.puml) | PlantUML diagram (legacy-centric; heatmap is separate) |

---

## Table of contents

1. [Architecture at a glance](#1-architecture-at-a-glance)
2. [Repository layout](#2-repository-layout)
3. [Runtime and entry points](#3-runtime-and-entry-points)
4. [Shared layer](#4-shared-layer)
5. [Backend: FastAPI surface (`backend/main.py`)](#5-backend-fastapi-surface-backendmainpy)
6. [System A — Legacy DTP Copilot](#6-system-a--legacy-dtp-copilot)
7. [System B — Opportunity Heatmap](#7-system-b--opportunity-heatmap)
8. [Integration between systems](#8-integration-between-systems)
9. [Frontends](#9-frontends)
10. [Data, persistence, and vector stores](#10-data-persistence-and-vector-stores)
11. [Configuration and environment variables](#11-configuration-and-environment-variables)
12. [Scripts and operational tooling](#12-scripts-and-operational-tooling)
13. [Testing](#13-testing)
14. [Extension points and conventions](#14-extension-points-and-conventions)

---

## 1. Architecture at a glance

### 1.1 Dual-system model

This repository implements **two independent product slices** behind **one FastAPI application** (`backend/main.py`):

| System | Role | Primary API prefix | Primary persistence |
|--------|------|--------------------|------------------------|
| **Legacy DTP Copilot** | Case-centric workflow: DTP-01 → DTP-06, chat, decisions, RAG, artifacts | `/api/cases`, `/api/chat`, `/api/decisions`, `/api/ingest`, `/api/documents` | `data/datalake.db` + Chroma `sourcing_documents` |
| **Opportunity Heatmap** | Opportunity scoring, tiers T1–T4, intake, feedback memory, copilot helpers | `/api/heatmap/*` | `data/heatmap.db` + Chroma `heatmap_documents` |

**Critical rule**: No shared case/opportunity state between the two. The **only** integration is **Heatmap → Legacy** when a user approves heatmap opportunities: `backend/heatmap/services/case_bridge.py` calls the same `create_case` path used by the legacy API.

### 1.2 High-level diagram (text)

```
                    ┌─────────────────────────────────────┐
                    │         FastAPI (main.py)           │
                    │  CORS + GZip + lifespan(init_db)   │
                    └──────────────┬──────────────────────┘
           ┌─────────────────────┴─────────────────────┐
           │                                               │
    ┌──────▼──────┐                                 ┌──────▼──────┐
    │ Legacy DTP  │                                 │  Heatmap   │
    │ services/   │                                 │ heatmap/   │
    │ supervisor/ │                                 │ LangGraph  │
    │ agents/     │                                 │ pipeline   │
    └──────┬──────┘                                 └──────┬──────┘
           │                                               │
    datalake.db +                                  heatmap.db +
    sourcing_documents                             heatmap_documents
```

---

## 2. Repository layout

```
Cursor Code/
├── backend/                    # Python backend (all server logic)
│   ├── main.py                 # FastAPI app: legacy routes + heatmap router include
│   ├── agents/legacy/          # DTP specialist agents (strategy, RFx, negotiation, …)
│   ├── artifacts/              # Artifact builders, renderers, UI placement map
│   ├── heatmap/                # Heatmap subsystem (router, agents, scoring, bridge)
│   ├── ingestion/              # Document + tabular ingest
│   ├── persistence/            # SQLModel models + DB init (core app)
│   ├── rag/                    # Retriever + vector store (legacy)
│   ├── services/               # case_service, chat_service, ingestion_service, llm_responder, …
│   ├── supervisor/             # LangGraph supervisor workflow (intent → agent → approval)
│   ├── tasks/                  # Task registry + per-domain tasks
│   ├── scripts/                # Seeds, demos, audits
│   └── tests/                  # Unit/integration-style tests
├── frontend/                   # Legacy Streamlit UI (optional)
├── frontend-next/              # Next.js App Router UI (heatmap + cases)
├── graphs/                     # Unified LangGraph workflow (`workflow.py`) invoked by ChatService
├── shared/                       # Pydantic schemas, enums, decision definitions, stage prereqs
├── data/                         # SQLite DBs, JSON seeds, heatmap category cards, synthetic CSV output
├── requirements.txt
├── README.md
├── SYSTEM_DOCUMENTATION.md       # Detailed DTP + heatmap narrative
├── BUSINESS_OVERVIEW.md
└── TECHNICAL_DOCUMENTATION.md    # This file
```

---

## 3. Runtime and entry points

- **API server**: `python -m uvicorn backend.main:app --reload --port 8000`
- **Startup**: `lifespan` calls `init_db()` from `backend/persistence/database.py` (core app DB only; heatmap DB is initialized via heatmap persistence layer when used).
- **OpenAPI**: `http://localhost:8000/docs`

---

## 4. Shared layer

### 4.1 `shared/schemas.py`

Central **Pydantic** contracts for the legacy API:

- **Cases**: `CaseSummary`, `CaseDetail` (includes `artifact_pack_summaries`, `working_documents`), `CaseListResponse`, `CreateCaseRequest`, `CreateCaseResponse`; artifact helpers: `ArtifactPackSummary`, `WorkingDocumentsState`, `WorkingDocumentSlot`, revise request/response types
- **Chat**: `ChatRequest`, `ChatResponse` (includes `intent_classified`, `agents_called`, `waiting_for_human`, `dtp_stage`, etc.)
- **Decisions**: `DecisionRequest`, `DecisionResponse` (supports `decision_data` for structured decision console)
- **Ingestion**: document ingest responses, data preview/ingest responses, document list
- **Health**: `HealthCheckResponse`

### 4.2 `shared/constants.py`

Enums and shared constants: `UserIntent`, `DocumentType`, `DataType`, `CaseStatus`, `TriggerSource`, `DecisionImpact`, API base URL defaults, endpoint path maps.

### 4.3 Other `shared/` modules

Typically used by both documentation and backend logic:

- **Decision definitions** (`shared/decision_definitions.py`): stage-specific questions for the Decision Console
- **Working document prompts** (`shared/working_documents_prompt.py`): truncate/format stored drafts for LLM context
- **Stage prerequisites** (`shared/stage_prereqs.py`): preflight checks per DTP stage
- **Schemas** beyond REST (`shared/schemas.py` may include additional models—see file for full list)

---

## 5. Backend: FastAPI surface (`backend/main.py`)

All routes below are defined on `app` except **`/api/heatmap/*`**, which is mounted via `include_router`.

### 5.1 Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness; returns version and component status strings |

### 5.2 Cases (Legacy DTP)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cases` | List cases (filters: `status`, `dtp_stage`, `category_id`, `limit`) |
| GET | `/api/cases/{case_id}` | Full case detail for copilot UI; includes `artifact_pack_summaries`, `working_documents` (see §6.11) |
| POST | `/api/cases` | Create case (`CreateCaseRequest`) |
| GET | `/api/cases/{case_id}/artifacts/{artifact_id}/export` | Download a **single** stored artifact as **Word** (`export_format=docx`) or **PDF** (`export_format=pdf`); see `backend/services/artifact_document_export.py`. |
| GET | `/api/cases/{case_id}/artifact-packs/{pack_id}/export` | Download an **entire artifact pack** as Markdown (`export_format=md`), Word (`docx`), or PDF (`pdf`). |
| POST | `/api/cases/{case_id}/working-documents` | `multipart/form-data`: `role` = `rfx` \| `contract`, `file` = `.docx`. Extracts plain text and stores it on the case (`working_documents_json`). |
| POST | `/api/cases/{case_id}/working-documents/revise` | JSON `WorkingDocumentReviseRequest` (`role`, `instruction`). LLM full-document rewrite; persists with `updated_by: copilot`. See `backend/services/working_document_revision.py`. |
| GET | `/api/cases/{case_id}/working-documents/{role}/export` | Download the stored working copy as `.docx` (`build_plain_text_docx_bytes` in `artifact_document_export.py`). |

### 5.3 Chat (Legacy DTP)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Main copilot: `ChatService.process_message` → supervisor / agent workflow |

### 5.4 Decisions (Legacy DTP)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/decisions/approve` | Approve pending decision (`decision_data` optional) |
| POST | `/api/decisions/reject` | Reject / request revision |

### 5.5 Ingestion (Legacy DTP)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ingest/document` | Upload PDF/DOCX/TXT + metadata → RAG chunks |
| GET | `/api/documents` | List documents (filters) |
| DELETE | `/api/documents/{document_id}` | Delete document |
| POST | `/api/ingest/data/preview` | Preview CSV/Excel |
| POST | `/api/ingest/data` | Ingest structured data |
| GET | `/api/ingest/history` | Ingestion history |

### 5.6 Heatmap (mounted router)

Prefix: **`/api/heatmap`**. Implemented in `backend/heatmap/heatmap_router.py`.

See [Section 7](#7-system-b--opportunity-heatmap) for the full route table and behavior.

---

## 6. System A — Legacy DTP Copilot

### 6.1 Purpose

Orchestrate **per-case** procurement work: intent classification, agent execution, artifact generation, human decisions, and stage transitions (DTP-01 … DTP-06).

### 6.2 Core services

| Module | Responsibility |
|--------|----------------|
| `backend/services/case_service.py` | CRUD-style access to cases; `create_case`, `get_case`, `list_cases`, updates |
| `backend/services/chat_service.py` | **Primary orchestrator** for `/api/chat`: loads case state, calls `LLMResponder` for intent, routes to LangGraph supervisor / decision handlers, persists chat and activity |
| `backend/services/llm_responder.py` | LLM-first intent classification and natural-language responses |
| `backend/services/ingestion_service.py` | Document + data ingest orchestration (delegates to `backend/ingestion/*`) |
| `backend/services/conversation_context.py` | Chat history trimming / context windows |
| `backend/services/response_envelope.py` | Standardized response shaping (if used by chat paths) |
| `backend/services/feature_flags.py` | Feature toggles |

### 6.3 Supervisor workflow

| Module | Responsibility |
|--------|----------------|
| `backend/supervisor/graph.py` | `SupervisorGraph`: LangGraph nodes—classify intent → validate → execute agent → approval gate → process decision → format response |
| `backend/supervisor/router.py` | `IntentRouter` and routing helpers |
| `backend/supervisor/state.py` | `SupervisorState`, `StateManager`—typed state for the graph |

**Governance rules** (enforced in graph design): load state before actions, classify intent first, block invalid transitions, require human approval for stage changes where applicable.

### 6.4 Legacy agents (`backend/agents/legacy/`)

Specialist agents (non-exhaustive; see each file for prompts and outputs):

| Agent module | Typical DTP focus |
|--------------|-------------------|
| `supervisor_agent.py` | Orchestration within legacy agent layer |
| `sourcing_signal_agent.py` | Signals / opportunity sensing |
| `strategy.py` | Strategy / triage-style reasoning |
| `triage_agent.py` | Classification / routing assistance |
| `rfx_draft_agent.py` | RFx drafting |
| `supplier_eval.py` / `supplier_scoring_agent.py` | Evaluation / scoring |
| `negotiation.py` / `negotiation_support_agent.py` | Negotiation support |
| `contract_support_agent.py` | Contract review support |
| `implementation_agent.py` | Implementation planning |
| `base.py` | Shared agent base behaviors |

Agents are invoked **from the supervisor/task execution path**, not directly from HTTP (except indirectly via `/api/chat`).

### 6.5 Tasks (`backend/tasks/`)

| File | Role |
|------|------|
| `registry.py` | Registers `BaseTask` subclasses by name; metadata (`requires_llm`, `requires_retrieval`) |
| `planners.py` | Sequences tasks per agent/plan |
| `contract_tasks.py`, `scoring_tasks.py`, `rfx_tasks.py`, `negotiation_tasks.py`, `implementation_tasks.py`, `signal_tasks.py` | Domain-specific executable tasks |
| `base_task.py` | Task interface |

### 6.6 Artifacts (`backend/artifacts/`)

| File | Role |
|------|------|
| `builders.py` | Construct structured artifact payloads |
| `renderers.py` | Render artifacts for UI consumption |
| `placement.py` | Maps artifact types to UI tabs/sections |
| `utils.py` | Helpers |

### 6.7 RAG (`backend/rag/`)

| File | Role |
|------|------|
| `retriever.py` | Semantic retrieval for case-grounded prompts |
| `vector_store.py` | Chroma integration for **legacy** document store |
| `vector_store_interface.py` | Abstract interface (for future Azure AI Search, etc.) |

### 6.8 Ingestion (`backend/ingestion/`)

| File | Role |
|------|------|
| `document_ingest.py` | Chunking + embedding pipeline for uploaded files |
| `data_ingest.py` | Tabular ingest (supplier performance, spend, SLA events, …) |
| `validators.py` | Validation helpers |

### 6.9 Persistence — core app (`backend/persistence/`)

| File | Role |
|------|------|
| `database.py` | SQLite engine, session, `init_db()` |
| `models.py` | SQLModel models for cases, suppliers, documents, chat history, etc. |
| `db_interface.py` | Abstraction for future hosted DB |

### 6.10 Unified LangGraph workflow (`graphs/workflow.py`)

`ChatService` invokes the **unified case workflow** via:

- `from graphs.workflow import get_workflow_graph` (see `backend/services/chat_service.py`)

This lives at the repo root: **`graphs/workflow.py`** (alongside `graphs/__init__.py`). It orchestrates specialist agent nodes for case execution.

**Related but separate**: `backend/supervisor/graph.py` defines `SupervisorGraph` (intent → validate → execute → approval → decision). Depending on code paths, both “supervisor-style” routing and the unified `graphs.workflow` graph participate in legacy behavior—when extending agents, trace **`chat_service.py`** first, then **`graphs/workflow.py`**, then **`backend/supervisor/graph.py`**.

### 6.11 Word round-trip, pack export, and copilot teaching

**Not** in-browser Microsoft Word; this is an explicit **download → edit locally → re-upload** loop for demos and pilots.

| Concern | Implementation |
|--------|------------------|
| **Artifact pack export** | Next.js case copilot: **Work products** card — export all artifacts in a pack as `.md` / `.docx` / `.pdf` (`artifact_document_export.py`: `build_artifact_pack_*`). |
| **Working document slots** | Two slots per case — **RFx** and **contract** — persisted as JSON on `case_states.working_documents_json` (plain text extracted from uploaded `.docx` via `backend/services/docx_text.py`). |
| **Copilot context** | `ChatService` passes `working_documents` into `case_context`; `LLMResponder` injects `format_working_documents_for_prompt()` (`shared/working_documents_prompt.py`). The model is instructed to **teach** the download → Word → save → **Upload .docx** flow when users ask how to edit. |
| **Intent routing** | Questions like “how do I upload Word?” are classified as **direct answer** (not specialist agent). |
| **UI** | `frontend-next/src/app/cases/[id]/copilot/page.tsx`: **Word round-trip · RFx & contract** card + first assistant message (`buildAssistantWelcome`) explains the same steps. |

**Environment**: `OPENAI_API_KEY` required for **Apply Copilot revision** (`working_document_revision.py`).

---

## 7. System B — Opportunity Heatmap

### 7.1 Purpose

Score and rank **opportunities** (batch contracts + intake requests) using a **deterministic framework** (`scoring_framework.py`), run a **LangGraph pipeline** per opportunity, optionally apply **review memory** and **LLM interpreter** fallbacks, and expose **copilot** endpoints for explain-only Q&A and policy assistance.

### 7.2 HTTP API (`backend/heatmap/heatmap_router.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/heatmap/qa` | Heatmap copilot Q&A (`HeatmapQARequest` → answer + `used_llm`) |
| POST | `/api/heatmap/policy/check` | Feedback vs `category_cards.json` alignment |
| POST | `/api/heatmap/category-cards/assist` | LLM-suggested JSON patch for category cards (preview; requires `OPENAI_API_KEY`) |
| POST | `/api/heatmap/category-cards/extract` | Deterministic extract: body `category`, `raw_text` → `proposed_patch` (unstructured policy text → structured fields) |
| POST | `/api/heatmap/category-cards/extract-upload` | Same as extract, but `multipart/form-data`: `category` + `file` (plain text, max 500KB) |
| POST | `/api/heatmap/category-cards/apply` | Merge `proposed_patch` into `data/heatmap/category_cards.json` (atomic write; supplier map merges) |
| POST | `/api/heatmap/category-cards/apply-and-rerun` | Apply patch, then start the batch scoring pipeline (same background job as `POST /run`) so **batch** opportunity scores refresh |
| GET | `/api/heatmap/intake/categories` | List categories from category cards + `category_cards_meta` (SHA-256 fingerprint) |
| POST | `/api/heatmap/intake/preview` | PS_new preview + meta (including `feedback_memory_delta`) |
| POST | `/api/heatmap/intake` | Persist intake opportunity (`source=intake`) |
| GET | `/api/heatmap/opportunities` | List scored opportunities |
| POST | `/api/heatmap/feedback` | Submit reviewer feedback (structured + legacy payload mapping) |
| POST | `/api/heatmap/approve` | Approve opportunities → **case bridge** creates legacy cases |
| POST | `/api/heatmap/run` | Start batch scoring pipeline (background thread) |
| GET | `/api/heatmap/run/status` | Pipeline status |

### 7.3 Scoring pipeline (`backend/heatmap/agents/`)

| File | Role |
|------|------|
| `graph.py` | LangGraph: `spend → contract → strategy → risk → supervisor → tick` loop over contracts |
| `state.py` | `HeatmapState`, `ScoredOpportunity`, signal TypedDicts |
| `spend_agent.py` | FIS/ES/SCS/CSIS signals |
| `contract_agent.py` | EUS/IUS + action windows; optional LLM interpreter for messy expiry dates |
| `strategy_agent.py` | SAS from `category_cards.json`; optional preferred-status normalization |
| `risk_agent.py` | RSS from supplier metrics |
| `supervisor_agent.py` | Weighted PS_contract / PS_new totals, tier, justification; calls `apply_learning_nudge` |

### 7.4 Scoring math

Implemented in `backend/heatmap/scoring_framework.py` (deterministic helpers) and aggregated in `supervisor_agent.py`.

Formulas (see also `SYSTEM_DOCUMENTATION.md` §15):

- **Existing contracts**: `PS_contract = 0.30·EUS + 0.25·FIS + 0.20·RSS + 0.15·SCS + 0.10·SAS`
- **New requests**: `PS_new = 0.30·IUS + 0.30·ES + 0.25·CSIS + 0.15·SAS`

Tiers: T1 ≥ 8.0, T2 ≥ 6.0, T3 ≥ 4.0, else T4.

### 7.5 Heatmap services

| Module | Role |
|--------|------|
| `services/intake_scoring.py` | PS_new for intake; persists `Opportunity` rows |
| `services/feedback_service.py` | Persist `ReviewFeedback` + upsert Chroma chunks for learning |
| `services/feedback_memory.py` | Retrieve similar feedback; bounded learning nudge (LLM JSON + heuristic fallback) |
| `services/heatmap_copilot.py` | Q&A, policy check, category-cards assist, unstructured text → patch extract (OpenAI where applicable) |
| `services/category_cards_store.py` | Merge validated patches into `category_cards.json` (atomic write) |
| `services/llm_interpreter.py` | Fallback extraction/normalization (expiry ISO, preferred status tokens) |
| `services/case_bridge.py` | Map approved opportunities → `create_case()` in legacy system |

### 7.6 Heatmap persistence

| Module | Role |
|--------|------|
| `persistence/heatmap_database.py` | SQLite session for `heatmap.db` |
| `persistence/heatmap_models.py` | `Opportunity`, `ReviewFeedback`, `AuditLog`, etc. |
| `persistence/heatmap_vector_store.py` | Chroma collection `heatmap_documents` |

### 7.7 Batch pipeline

| Module | Role |
|--------|------|
| `run_pipeline_init.py` | Generate/load synthetic CSVs, run graph, persist **batch** opportunities (preserves `source=intake`) |
| `seed_synthetic_data.py` | CLI to generate synthetic data / seed run |
| `context_builder.py` | Aggregates spend/category context; FIS field selection (TCV vs ACV via env) |

### 7.8 Category cards: unstructured policy → scoring

- **Source of truth on disk**: `data/heatmap/category_cards.json` (drives **SAS** via `strategy_agent` / intake scoring).
- **Demo flow**: paste or upload plain-text policy notes → `extract` or `extract-upload` → review `proposed_patch` → `apply` or `apply-and-rerun`. The latter reloads cards in `run_init()` and recomputes **batch** rows; **intake** preview/submit reads the updated file on the next request without a pipeline run.
- **PDF/Word**: not parsed server-side; export to `.txt` for upload, or paste text into extract.

---

## 8. Integration between systems

- **Heatmap → Legacy**: `POST /api/heatmap/approve` → `case_bridge.py` → `CaseService.create_case` (or equivalent) so a **new DTP case** exists for downstream `/api/chat` work.
- **No reverse bridge** in core design: legacy cases do not automatically push back into heatmap scores.

---

## 9. Frontends

### 9.1 Next.js (`frontend-next/`)

- **Framework**: Next.js App Router (`src/app/`)
- **API base**: `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000` in `src/lib/api-base.ts`)
- **Routes (pages)**:

| Route | System | Purpose |
|-------|--------|---------|
| `/` | Shell | Landing |
| `/heatmap` | Heatmap | Priority list, matrix, copilot slide-over, review |
| `/intake` | Heatmap | Business intake + PS_new preview |
| `/cases` | Legacy DTP | Case list |
| `/cases/copilot` | Legacy DTP | Empty-state / case selection shell |
| `/cases/[id]/copilot` | Legacy DTP | Case copilot split view |

**Note**: The sidebar in `src/app/layout.tsx` may link to paths like `/cases/active/copilot`; the repo currently includes `/cases/copilot` and `/cases/[id]/copilot`. Prefer the paths that exist under `src/app/cases/`.

**Libraries**: Tailwind, Recharts, Framer Motion, Lucide (see `frontend-next/package.json`).

### 9.2 Streamlit (`frontend/`)

Legacy UI entry: `frontend/app.py` with pages under `frontend/pages/` (case dashboard, case copilot, knowledge management). Uses `frontend/api_client.py` to call the same FastAPI backend.

---

## 10. Data, persistence, and vector stores

| Asset | Path / name | Used by |
|-------|-------------|---------|
| Core SQLite | `data/datalake.db` | Legacy cases, chat, ingestion metadata |
| Heatmap SQLite | `data/heatmap.db` | Opportunities, feedback, audit |
| Category cards | `data/heatmap/category_cards.json` | SAS / defaults for heatmap |
| Legacy Chroma | `data/chroma_db/` (typical) + collection `sourcing_documents` | Document RAG for DTP |
| Heatmap Chroma | path under `data/chromadb/` (see `heatmap_vector_store.py`) + collection `heatmap_documents` | Feedback memory + copilot snippets |
| Seeds | `data/cases_seed.json`, scripts | Demo cases |

---

## 11. Configuration and environment variables

### 11.1 Shared

- `OPENAI_API_KEY`: Enables OpenAI-backed features (LLMResponder, heatmap copilot, learning, interpreter).

### 11.2 Legacy DTP (representative)

- Model selection may be influenced by `use_tier_2` on `ChatRequest` and internal service settings—see `chat_service.py` / `llm_responder.py`.

### 11.3 Heatmap (representative)

| Variable | Purpose |
|----------|---------|
| `HEATMAP_FIS_USE_ACV` | Use ACV instead of TCV for FIS in batch scoring |
| `HEATMAP_LEARNING` | `0`/`false` disables review memory |
| `HEATMAP_LEARNING_MODEL` | Model for learning synthesis (default `gpt-4o-mini`) |
| `HEATMAP_COPILOT_MODEL` | Heatmap copilot model (fallback chain in `heatmap_copilot.py`) |
| `HEATMAP_INTERPRETER_MODEL` | LLM interpreter fallback model |

See `README.md` and `SYSTEM_DOCUMENTATION.md` §15 for the authoritative list.

---

## 12. Scripts and operational tooling

| Script | Purpose |
|--------|---------|
| `backend/scripts/seed_it_demo_data.py` | Seed legacy DTP demo cases + documents |
| `backend/scripts/run_happy_path_demo.py` | End-to-end DTP demo |
| `backend/heatmap/seed_synthetic_data.py` | Heatmap synthetic data generation / pipeline kickoff |
| `backend/scripts/audit_case_readiness.py` | Case readiness audits |
| `backend/scripts/ensure_demo_cases.py` | Ensure demo cases exist |
| `backend/scripts/patch_docs.py`, `patch_seed.py` | Maintenance |

---

## 13. Testing

Location: `backend/tests/`

Examples:

- `test_chat_routing.py` — chat routing behavior
- `test_artifact_placement.py` — artifact placement map
- `verify_agent_dialogue.py`, `verify_negotiation_override.py`, `repro_generic_answer.py` — behavioral checks

Run with `pytest` from repo root (ensure `PYTHONPATH` includes project root if needed).

---

## 14. Extension points and conventions

### 14.1 Adding a legacy API endpoint

1. Add Pydantic models to `shared/schemas.py` if needed.
2. Implement logic in the appropriate `backend/services/*` module.
3. Register route on `app` in `backend/main.py` (or refactor into a router module and `include_router`).

### 14.2 Adding a heatmap endpoint

1. Add handler to `backend/heatmap/heatmap_router.py` (or split sub-routers and include).
2. Keep scoring logic in `scoring_framework.py` / agents—not in the router.

### 14.3 Adding a new DTP agent task

1. Implement `BaseTask` subclass under `backend/tasks/`.
2. Register in `backend/tasks/registry.py`.
3. Wire into planner / agent invocation path.

### 14.4 Safety conventions

- **Heatmap copilot** must not mutate scores in the DB unless explicitly designed (today: explain-only endpoints).
- **Learning** applies bounded deltas; disable via `HEATMAP_LEARNING=0` for pure formula runs.

---

## Document maintenance

When you change:

- **API routes** → update `backend/main.py` / `heatmap_router.py` and this file’s tables.
- **New env vars** → update §11 and `README.md`.
- **New UI routes** → update §9 and `README.md`.

For narrative detail on **DTP stages**, **decision console**, and **heatmap UX**, keep **SYSTEM_DOCUMENTATION.md** as the long-form companion; this file is the **structural map**.
