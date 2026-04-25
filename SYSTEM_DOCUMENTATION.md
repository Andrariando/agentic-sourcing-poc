# Agentic Sourcing System: Technical Backend Documentation

This document provides a detailed technical deep-dive into the backend architecture and logic of the Agentic Sourcing ProcuraBot. It is intended for auditing, technical review, and developers seeking to understand the inner workings of the system.

**Last Updated**: April 7, 2026

---

## 🏗️ 1. High-Level Architecture (Dual-System)

This repository contains **two independent systems** that share the same FastAPI process (`backend/main.py`) but are otherwise isolated by design.

### System A — Legacy DTP ProcuraBot (DTP-01 → DTP-06)

**Purpose**: end-to-end sourcing execution inside a “case” using chat + multi-agent workflows + artifacts + governance decisions.

**Core layers**
- **API Layer (FastAPI)**: `/api/cases/*`, `/api/chat`, `/api/decisions/*`, `/api/ingest/*`
- **Service Layer**: `ChatService`, `CaseService`, `LLMResponder`, etc.
- **Agent Layer**: Supervisor + specialist agents (DTP stages)
- **RAG Layer**: retrieval over `sourcing_documents`
- **Persistence Layer**: SQLite `data/datalake.db` + Chroma (legacy collection)

### System B — Opportunity Heatmap (agentic scoring + intake)

**Purpose**: continuously evaluate sourcing opportunities (renewals + new requests) and prioritize them using a deterministic scoring framework with optional LLM layers (explanations, policy check, bounded learning, interpreter fallbacks)

**Core layers**
- **API Layer (FastAPI)**: `/api/heatmap/*`
- **Agent Layer**: LangGraph scoring pipeline in `backend/heatmap/agents/*`
- **Vector memory layer**: Chroma collection `heatmap_documents` (review feedback memory + copilot snippets)
- **Persistence Layer**: SQLite `data/heatmap.db`

### What is shared vs isolated?

**Shared**
- One FastAPI process: `backend/main.py` on port 8000 (serves both API surfaces)
- One Next.js app (optional): `frontend-next` can display both systems’ UIs

**Isolated (by design)**
- Databases:
  - Legacy DTP: `data/datalake.db`
  - Heatmap: `data/heatmap.db`
- Vector stores:
  - Legacy DTP: `sourcing_documents`
  - Heatmap: `heatmap_documents`
- Agents/state machines:
  - Legacy: `backend/agents`, `backend/supervisor`, `backend/services/*`
  - Heatmap: `backend/heatmap/*`

### The only integration point

The two systems share **no case state** and **no scoring state**. The single integration point is:
- **Heatmap approve → create legacy case**: `POST /api/heatmap/approve` calls `backend/heatmap/services/case_bridge.py`, which invokes the legacy case-creation service.

> **Note**: The Heatmap section later in this document repeats the same statement (and includes a diagram). This section is the “front door” summary.

### Running the System

```bash
# Terminal 1: Start Backend API (serves BOTH Legacy DTP + Heatmap APIs)
python -m uvicorn backend.main:app --port 8000

# Terminal 2: Start Next.js Frontend (unified UI for Heatmap + Cases)
cd frontend-next && npm run dev

# Generate Heatmap Synthetic Data (run once)
python backend/heatmap/seed_synthetic_data.py

# Seed Legacy DTP Demo Data (run once)
python backend/scripts/seed_it_demo_data.py
```

---

## 💬 2. The Chat Request Lifecycle

What happens when a human asks something in the chat window?

### Step 1: Frontend Submission (Legacy DTP system)
The user types a message and clicks send. The **Legacy DTP UI** (Streamlit: `frontend/pages/case_copilot.py`, or Next.js cases UI: `frontend-next/src/app/cases/[id]/copilot/page.tsx`) sends a `POST` request to `/api/chat` with:
- `case_id`: The unique identifier for the current procurement project.
- `user_message`: The raw text input from the user.
- `use_tier_2`: A flag indicating whether to use more advanced (and expensive) LLM models.

### Step 2: ChatService Entry Point
`ChatService.process_message()` in `backend/services/chat_service.py` is the main orchestrator. It performs:
1. **Traceability**: Generates a unique `trace_id` (UUID) for logging and debugging this specific request.
2. **Context Retrieval**: Loads the current case state (DTP stage, status, metadata) from the database.
3. **Conversation Memory**: If enabled, fetches recent chat history to provide context to the LLM.

### Step 3: LLM-First Intent Analysis (LLMResponder)
Instead of rigid hard-coded rules, the system now uses a **LLM-First Strategy** (`backend/services/llm_responder.py`) to understand every user message:

1.  **Intent Classification**: The `LLMResponder` analyzes the user's message, conversation history, and case state to determine the intent.
    *   `needs_agent`: User wants to perform a task (e.g., "Score suppliers").
    *   `is_approval`/`is_rejection`: User is deciding on a recommendation.
    *   `needs_data`: User provided partial info, system needs to ask for more.
    *   `can_answer_directly`: User just asked a question (e.g., "What are the risks?") or wants to chat.

2.  **Dynamic Routing**:
    *   **Agent Execution**: If `needs_agent` is detected, the `ChatService` clears any "waiting" flags and routes to the LangGraph workflow.
    *   **Decision Processing**: If approval/rejection is detected, the system processes the decision and updates the stage.
    *   **Direct Response**: If the LLM can answer directly (using case context), it generates a response without running the full agent workflow.
    *   **Mixed Intents**: If the user asks a question *during* a pending approval (e.g. "What are the risks?"), the LLM answers the question AND gently reminds the user that a decision is still pending.

3.  **Natural Response Generation**:
    *   All responses are generated by the LLM (no templates).
    *   The LLM synthesizes the "Agent Output" (technical data) into a natural, friendly conversation.
    *   It maintains a consistent persona (helpful, professional copilot).

### Step 4: Agent Execution (LangGraph)
Once the path is chosen, the system executes the workflow:
1.  **Specialist Agent Node**: The selected agent (e.g., `StrategyAgent`) runs.
    *   It retrieves necessary data (SQL + RAG).
    *   It generates a structured artifact (e.g., `StrategyRecommendation`).
    *   **"Talk Back" Capability**: If the agent identifies missing data or risks, it can return an `AgentDialogue` object (e.g. "I need clarification") instead of a plan.
    *   It is **deterministic** in its calculations (e.g. scoring) but uses LLM for synthesis.
2.  **Loop**: The output is fed back to the Supervisor.
    *   **Success**: Output stored, stage advances.
    *   **Clarification Needed**: Supervisor routes to `CaseClarifier`.
    *   **Concern Raised**: Supervisor routes to `WaitForHuman`.

### Step 6: Persistence & State Update
The output and conversation history are saved:
- The `CaseService` persists the artifacts to the database.
- The `Case Status` might update (e.g., moving from "DTP-01" to "DTP-02").
- If the agent made a recommendation, the case state is set to `waiting_for_human = True`.

### Step 7: Natural Response Generation
The `LLMResponder` takes the agent's raw output (or direct answer) and formats it into a conversational message for the user. It ensures the tone is consistent and helpful, and seamlessly handles "Ask for more data" scenarios if the user's request was incomplete. In the current UX, ProcuraBot is framed as an **AI assistant** supporting the human decision-maker (not as a supervisor role).

### Word round-trip (RFx & contract drafts) — teaching users the loop

The Next.js case copilot (`frontend-next/src/app/cases/[id]/copilot/page.tsx`) supports **human-in-the-loop editing in Microsoft Word** alongside AI:

1. **Download** — From **Work products**, export an artifact pack as `.docx` (or, once text exists, use the **Word** button under **Word round-trip · RFx & contract**).
2. **Edit** — Open the file in **Microsoft Word**, change the draft, **Save**.
3. **Re-upload** — In the same left panel, under **Word round-trip**, choose the **RFx** or **Contract** slot and click **Upload .docx**. The backend extracts plain text (`POST /api/cases/{case_id}/working-documents`) and stores it on the case.
4. **Chat** — ProcuraBot receives that text via `working_documents` in the LLM prompt (`shared/working_documents_prompt.py`, `backend/services/llm_responder.py`) so users can ask clause-level questions.
5. **Optional AI rewrite** — **Apply ProcuraBot revision** runs a full-document LLM pass (`POST .../working-documents/revise`); then **Word** downloads an updated `.docx`.

The **first assistant message** in chat and the **LLM system prompts** explicitly teach this path (including “ask me *how do I edit the document?*”). This is **not** live co-authoring with Word Online; it is export/import of `.docx` with plain-text round-trip. See **TECHNICAL_DOCUMENTATION.md §6.11** for API and file references.

---

## 📊 3. DTP Stage Data Requirements

Each DTP (Draft to Procurement) stage uses specific data sources and produces specific outputs.

### DTP-01: Strategy & Triage - "The Gatekeeper"

**Mindset**: Sense-Making ("Do we even need sourcing?")

DTP-01 has **two capabilities** that work together:

---

#### DTP-01A: Smart Triage (Coverage + Classification)

**Purpose**: Classify requests into categories that determine the DTP routing path, and seek human confirmation.

**Agent**: `TriageAgent` (`backend/agents/triage_agent.py`)

**Logic (Deterministic + Confirmation)**:
1. **Coverage Check**: Match `user_intent` against `contracts.json` keywords.
2. **Smart Classification**: Infer category from contract data + user keywords.
3. **Build Evidence**: Explain *why* a category was proposed (e.g., "Contract expires in 30 days").
4. **Propose & Confirm**: Present proposal to human for confirmation before locking path.

**Request Categories & Routing**:
| Category | Description | Routing Path |
|----------|-------------|--------------|
| **Demand-Based** | New requirement, no existing contract | Full: 01→02→03→04→05→06 |
| **Renewal (No Change)** | Renewing as-is | Fast: 01→04→05→06 |
| **Renewal (Scope Change)** | Renewing with modifications | Full: 01→02→03→04→05→06 |
| **Ad-Hoc** | Urgent/emergency request | Full with alerts |
| **Fast-Pass** | Pre-approved catalog item | Fast: 01→05→06 |

**Output**: `TriageResult`
```python
class TriageResult:
    proposed_request_type: RequestType  # System's proposal
    confidence: float  # How sure (0.0-1.0)
    evidence: List[str]  # Why this classification
    routing_path: List[str]  # Active stages
    skipped_stages: List[str]  # Stages to skip
    status: TriageStatus  # AWAITING_CONFIRMATION → CONFIRMED
```

**Human Confirmation Flow**:
1. Agent: "I classified this as **Renewal (No Change)** (90% confidence)"
2. Evidence: "Contract CTR-001 expires in 30 days"
3. Impact: "⚠️ This will SKIP DTP-02/03. Jump to Negotiation."
4. User: **[Confirm]** or **[Wrong - New Demand]**

**Confidence Scoring** (Rule-Based Heuristic):
| Score | Meaning | Example |
|-------|---------|---------|
| **0.9** | Very confident | Contract expiry match + no scope change |
| **0.85** | Confident | Signal-triggered OR explicit keywords ("fast-pass") |
| **0.8** | Moderate | User mentioned "renew" keyword |
| **0.75** | Mixed signals | "renew" + "change" keywords together |
| **0.6** | Low (default) | No strong evidence, guessing Demand-Based |

*Note: Confidence is NOT ML-based. It's calculated from evidence strength: Contract data > User keywords > Default guess.*

**Frontend Display**: `render_triage_panel()` shows proposal, evidence, and confirmation buttons.

---

#### DTP-01B: Strategy (Need Identification)

**Purpose**: Identify sourcing opportunities, frame the problem, and define initial strategy.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Case Summary** | `CaseState` table | `case_id`, `category_id`, `trigger_source`, `status` |
| **Supplier Performance** | `SupplierPerformance` table | `supplier_id`, `overall_score`, `trend`, `risk_level` |
| **Spend Metrics** | `SpendMetric` table | `spend_amount`, `budget_amount`, `variance_percent` |
| **SLA Events** | `SLAEvent` table | `event_type`, `severity`, `sla_metric` |
| **Market Documents** | ChromaDB | `Market_Benchmark`, `Policy` documents |

**Agent**: `StrategyAgent` (`agents/strategy_agent.py`)
**Collaboration**: Supports dynamic user overrides (e.g. "Change strategy to X") to prioritize user intent over default rules.

**Output**: `StrategyRecommendation`
```python
class StrategyRecommendation:
    recommended_action: str  # "Renew", "Bid", "Monitor", "Terminate"
    confidence_score: float  # 0.0 to 1.0
    justification: str
    key_factors: List[str]
    risks: List[RiskItem]
    clarification_questions: List[str]  # Smart Intake: probes fuzzy intent
```

**Required Decisions**:
| Decision | Type | Options | Critical Path |
|----------|------|---------|---------------|
| **Is new sourcing required?** | Choice | Yes / No / Cancel | No → Terminate, Cancel → Terminate |
| **Sourcing route?** | Choice | Strategic / Tactical / Spot | (Only if Yes above) |

**Sample Interaction**:
- User: "What's the renewal strategy for this case?"
- Agent: Queries supplier performance, spend trends, and SLA compliance to recommend action.

---

### DTP-02: Planning (Supplier Evaluation Prep) - "The Architect"

**Mindset**: Structuring ("Turn fuzzy intent into clear requirements")
**Purpose**: Freeze assumptions, clarify requirements, and prepare evaluation criteria.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Supplier Performance** | `SupplierPerformance` table | All performance scores (quality, delivery, responsiveness) |
| **Historical RFPs** | ChromaDB | Past RFP templates, evaluation criteria |
| **Market Benchmarks** | ChromaDB | Pricing benchmarks, typical SLAs |

**Agent**: `SupplierEvaluationAgent` (`agents/supplier_eval.py`)
**Collaboration**: Accepts user overrides for eligibility (e.g., "Include all suppliers", "Add Supplier X").

**Output**: `SupplierShortlist`
```python
class SupplierShortlist:
    shortlist: List[ShortlistEntry]  # Ranked suppliers with scores
    evaluation_criteria: Dict[str, float]  # Criteria weights
    methodology: str
    clarification_needed: bool  # The Architect: needs requirement freeze?
    clarification_questions: List[str]  # Questions to clarify vague requirements
```

**Required Decisions**:
| Decision | Type | Options |
|----------|------|---------|
| **Is supplier shortlist complete?** | Choice | Yes / No |

---

### DTP-03: Sourcing (RFx & Selection) - "The Controller"

**Mindset**: Executing ("Let's see what the market says")
**Purpose**: Execute RFx process, manage timeline, and ensure procedural fairness.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Supplier Proposals** | Uploaded documents | Pricing, capabilities, references |
| **Evaluation Rubrics** | ChromaDB | Scoring criteria from policy docs |
| **Comparison Templates** | ChromaDB | Historical RFP evaluations |

**Agent**: `RfxDraftAgent` (in workflow)

**Output**: `RFxDraft` with evaluation matrices

**Required Decisions**:
| Decision | Type | Options |
|----------|------|---------|
| **Has evaluation been completed?** | Choice | Yes / No |

---

### DTP-04: Negotiation - "The Decision Owner"

**Mindset**: Negotiating ("Real value happens here")
**Purpose**: Challenge safe choices, balance trade-offs (Price vs Risk), and select winner.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Market Rates** | ChromaDB | Benchmark pricing, typical increases |
| **Supplier History** | `SupplierPerformance` | Past performance, relationship strength |
| **Alternative Quotes** | Case context | Competitive pricing data |
| **BATNA Info** | ChromaDB | Best alternative options |

**Agent**: `NegotiationAgent` (`agents/negotiation.py`)
**Collaboration**: User can specify terms (e.g., "Net 60", "Focus on Price") which override default playbook strategies.

**Output**: `NegotiationPlan`
```python
class NegotiationPlan:
    leverage_points: List[str]
    target_terms: Dict[str, str]
    walkaway_position: str
    recommended_tactics: List[str]
    challenge_questions: List[str]  # The Challenger: pushback on assumptions
```

**Required Decisions**:
| Decision | Type | Options |
|----------|------|---------|
| **Which supplier to award?** | Text | Supplier ID |
| **Savings validated by Finance?** | Choice | Yes / No (Provisional) |
| **Legal approved contract terms?** | Choice | Yes / No |

**Sample Interaction**:
- User: "What's our negotiation position for this renewal?"
- Agent: Analyzes market benchmarks, alternative quotes, and relationship history.

---

### DTP-05: Contracting - "The Closer"

**Mindset**: Closing ("Lock it in")
**Purpose**: Eliminate risk, validate compliance, and finalize contract terms.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Contract Templates** | ChromaDB | Standard terms, legal clauses |
| **Negotiated Terms** | Previous outputs | Agreed pricing, SLAs |
| **Policy Requirements** | ChromaDB | Compliance checklist, approval gates |

**Agent**: `ContractSupportAgent`
**Collaboration**: Prioritizes user-requested clauses over standard templates.

**Output**: `ContractExtraction` with key terms and compliance status

**Required Decisions**:
| Decision | Type | Options |
|----------|------|---------|
| **Stakeholders signed approval memo?** | Choice | Yes |

---

### DTP-06: Implementation - "The Historian"

**Mindset**: Reporting ("Did this actually matter?")
**Purpose**: Defend value, track savings/avoidance, and manage rollout.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Implementation Guides** | ChromaDB | Rollout best practices, timelines |
| **KPI Definitions** | Case context | Agreed metrics from contract |
| **Transition Plans** | ChromaDB | Change management docs |

**Agent**: `ImplementationAgent`
**Collaboration**: Allows modification of rollout steps (e.g. "Add Legal Review") via user intent.

**Output**: `ImplementationPlan` with milestones and KPIs

**Required Decisions**:
| Decision | Type | Options |
|----------|------|---------|
| **Contract signed and stored in CLM?** | Choice | Yes |

---

## 🗂️ 4. Synthetic Data Reference

The system comes with comprehensive synthetic data for testing. Run the seed script:

```bash
python backend/scripts/seed_it_demo_data.py
```

### Available Test Cases (10 Cases covering DTP-01 to DTP-04)

| Case ID | Name | Category | DTP Stage | Description |
|---------|------|----------|-----------|-------------|
| CASE-001 | IT Managed Services Renewal | IT_SERVICES | DTP-01 | Renewal with TechCorp, pricing above market |
| CASE-002 | End-User Hardware Refresh | HARDWARE | DTP-01 | 2,500 unit refresh (Dell vs HP/Lenovo) |
| CASE-009 | Global Telecom Consolidation | TELECOM | DTP-01 | Consolidating 15 countries to 1-2 carriers |
| CASE-003 | Cloud Migration (AWS/Azure) | CLOUD | DTP-02 | Migrating 40% workloads to cloud |
| CASE-007 | SD-WAN Upgrade | NETWORK | DTP-02 | Replacing MPLS with SD-WAN |
| CASE-010 | DevOps Toolchain Standards | SOFTWARE | DTP-02 | Standardizing CI/CD (GitHub vs GitLab) |
| CASE-004 | Cybersecurity SOC Services | SECURITY | DTP-03 | Scoring proposals (SecureNet vs CyberGuard) |
| CASE-008 | HRIS Platform Selection | SAAS | DTP-03 | Workday vs Oracle HCM evaluation |
| CASE-005 | Data Center Co-location | INFRASTRUCTURE | DTP-04 | Equinix negotiation (power rates) |
| CASE-006 | Microsoft EA Renewal | SOFTWARE | DTP-04 | E3 to E5 step-up, 15% uplift proposed |

### Supplier Data Highlights

**IT Services**:
- SUP-IT-01: TechCorp Solutions (7.8/10, stable)
- SUP-IT-02: Global Systems Inc (6.5/10, declining risk)

**Hardware**:
- SUP-HW-01: Dell Technologies (8.5/10, benchmark partner)
- SUP-HW-02: HP Inc (8.0/10, improving)
- SUP-HW-03: Lenovo (7.5/10, stable)

**Cloud**:
- SUP-CL-01: AWS (9.0/10, strong technical)
- SUP-CL-02: Microsoft Azure (8.8/10, better pricing)

**Security**:
- SUP-SEC-01: SecureNet Defense (9.2/10, premium)
- SUP-SEC-02: CyberGuard AI (7.5/10, budget/innovator)

### Documents in ChromaDB (15+ Context-Aware Docs)

| Document | Type | Category | Usage |
|----------|------|----------|-------|
| **RFP Templates** | Template | Hardware, Cloud, SOC | DTP-02 Structuring |
| **Market Reports** | Report | Telecom, Fleet | DTP-01 Strategy |
| **Vendor Proposals** | Proposal | SecureNet, CyberGuard, Workday, Equinix, Microsoft | DTP-03 & 04 |
| **Contracts** | MSA | Legal | DTP-05 Review |


## 🛠️ 5. Key Backend Components

### 1. ChatService (`backend/services/chat_service.py`)
The main orchestrator for chat interactions. Contains:
- `process_message()`: Primary API method — orchestrates chat-level state
- Intent-specific handlers: `_handle_status_intent()`, `_handle_explain_intent()`, etc.
- Preflight readiness check: `check_stage_readiness()` blocks agents if prerequisites missing
- Response formatting and error handling

**State Ownership Clarification**:
- **ChatService**: Manages `waiting_for_human`, `activity_log`, `latest_agent_output`
- **Supervisor**: Manages DTP stage transitions and agent routing

**Important**: There is a legacy `process_message_langgraph()` method (lines 1009+) used by the standalone `app.py`. The API uses the first method.

### 2. The Supervisor Agent (`backend/supervisor/`)
The Supervisor is the hub. It manages the DTP workflow and ensures steps aren't skipped.

### 3. RAG Pipeline (`backend/rag/`)
- **Ingestion**: Documents are split into chunks and embedded into ChromaDB.
- **Retrieval**: Uses semantic search to find the top K most relevant chunks.
- **Grounding**: Agents provide "grounding source IDs" for citations.

### 4. Artifact Placement Map (`backend/artifacts/placement.py`)
Single source of truth for where data appears in the UI:
- `SIGNAL_REPORT` → "Signals" tab
- `EVALUATION_SCORECARD` → "Scoring" tab
- `RFX_DRAFT` → "RFx" tab

### 5. Task-Based Agent Workflow (`backend/tasks/`)
Agents follow a structured **Task-Based** execution model:
1. **Task Registry**: Atomic tasks defined in `registry.py`
2. **Planners**: Determine task sequence
3. **Task Execution**: Each task has its own prompt and RAG context
4. **Task Feedback**: Results feed into the next task

### 5. LLMResponder (`backend/services/llm_responder.py`)
**[NEW]** The unified response handling service that replaces regex/template logic.
- **Intent Analysis**: Determines if user needs an agent, is approving, or just chatting.
- **Response Generation**: Generates all user-facing text.
- **Data Sufficiency**: Checks if user provided enough info; if not, generates natural follow-up questions.

---

## 🛡️ 6. Governance & Safety
- **Human-in-the-Loop**: All major decisions require explicit user approval.
- **Cost Awareness**: The `ConversationContextManager` prunes chat history.
- **Transparency**: Detailed execution metadata recorded for auditability.
- **Preflight Readiness**: Cases blocked from proceeding if prerequisites missing.

### State Ownership
| Component | Manages |
|-----------|--------|
| **Supervisor** | DTP stage transitions, agent routing |
| **ChatService** | `waiting_for_human`, `activity_log`, chat-level state |
| **CaseService** | Persistence layer for all state |

---

## 🔧 7. Recent Changes (January 2026)

### Collaborative Architecture Refactor
1.  **User Intent Injection**: All agents now accept `user_intent` to override deterministic rules/templates.
2.  **Refinement Loops**: The "Reject" decision in the workflow now triggers a **Feedback Loop** (Refinement) instead of termination. Users can provide a reason, and the agent re-runs with that context.
3.  **Platform Stability**: Fixed Windows-specific Unicode logging crashes.

### LLM-First Conversational Architecture
1.  **New `LLMResponder` Service** (`backend/services/llm_responder.py`): Replaces templated responses with dynamic LLM generation.
2.  **Smart Intent Classification**: Distinguishes QUESTIONS (answered directly) from ACTION REQUESTS (trigger agents).
3.  **Conversation Memory**: Context-aware responses using prior chat history.
4.  **Activity Logging**: All interactions (including direct responses) now logged for transparency.

### Bug Fixes
1. **Duplicate `process_message` method**: Renamed legacy method to `process_message_langgraph()` to prevent API issues.
2. **Pydantic/dict handling**: Fixed attribute access for `AgentActionLog` and `BudgetState` objects.
3. **Windows encoding**: Replaced emojis with ASCII-safe text in print statements.
4. **Backend emojis**: Fixed encoding issues in `backend/main.py` and `graphs/workflow.py`.
5. **Missing `_create_response`**: Added helper method for ChatResponse construction.
6. **UnboundLocalError**: Removed redundant local imports causing variable shadowing.
7. **Welcome message**: Fixed literal `\n` display using proper multiline strings.

### Data Enhancements
1. Created IT-focused seed script (`backend/scripts/seed_it_demo_data.py`).
2. Added 10 realistic IT/Corporate test cases across all DTP stages.
3. Seeded 20+ suppliers with differentiated performance data.
4. Added 15+ context-aware documents (Proposals, Templates, Reports) to ChromaDB.

### Architecture Clarifications
- Frontend (`frontend/app.py`) communicates with backend API on port 8000.
- The root `app.py` is a legacy standalone version (not used with API architecture).

### Agent-Supervisor Dialogue ("Talking Back")
1.  **Bi-Directional Communication**: Agents can now return `AgentDialogue` objects to "talk back" to the Supervisor instead of strictly returning plans.
    *   `NeedClarification`: Routes to user for more info.
    *   `ConcernRaised`: Routes to human for safety check.
2.  **Separate Agent Logs**: Internal agent reasoning and dialogues are now displayed in a dedicated "🔍 Agent Logs" panel in the frontend, keeping the main chat clean.

---

## 🔐 8. Decision Core (January 2026)

The **Decision Core** is a new capability that enables structured, semantically validated human decisions at every DTP stage.

### Key Features

1.  **Structured Decision Definitions** (`shared/decision_definitions.py`): Defines stage-specific questions, answer types, dependencies, and critical path actions.

2.  **Dynamic Decision Console** (UI): Replaces the simple Approve/Reject buttons with a dynamic form rendered from `DTP_DECISIONS`. Supports:
    - Choice (radio buttons) and Text input types
    - Conditional questions (dependencies)
    - Pre-filled answers from chat history (bidirectional sync)

3.  **Conversational Decision Flow** (Chat): The copilot proactively asks decision questions when a case enters "Waiting for Human Decision" status. It:
    - Identifies the first unanswered required question
    - Uses strict scaffolding (expects "1" or "2" or exact text)
    - Rejects ambiguous answers and re-prompts
    - Presents a summary and confirmation before advancing

4.  **Semantic Validation** (Backend): The `ChatService.process_decision()` method validates all required questions are answered before allowing approval. Critical path decisions (e.g., `sourcing_required = No`) trigger special actions like case termination.

5.  **Rich Decision Data**: Each answer is stored with metadata:
    ```python
    {
        "answer": "Yes",
        "decided_by_role": "User",
        "timestamp": "2026-01-15T10:00:00Z",
        "status": "final",
        "confidence": "high"
    }
    ```

6.  **Stage-Based Locking**: Decisions for previous DTP stages are read-only in the backend validation.

### Decision Questions by Stage

| Stage | Question ID | Question Text | Type | Required |
|-------|-------------|---------------|------|----------|
| DTP-01 | `sourcing_required` | Is new sourcing required? | Choice (Yes/No/Cancel) | ✓ |
| DTP-01 | `sourcing_route` | Recommended sourcing route? | Choice (Strategic/Tactical/Spot) | ✓ (if Yes) |
| DTP-02 | `supplier_list_confirmed` | Is supplier shortlist complete? | Choice (Yes/No) | ✓ |
| DTP-03 | `evaluation_complete` | Has evaluation been completed? | Choice (Yes/No) | ✓ |
| DTP-04 | `award_supplier_id` | Which supplier are we awarding to? | Text | ✓ |
| DTP-04 | `final_savings_confirmed` | Savings validated by Finance? | Choice (Yes/No) | ✓ |
| DTP-04 | `legal_approval` | Legal approved contract terms? | Choice (Yes/No) | ✓ |
| DTP-05 | `stakeholder_signoff` | Stakeholders signed approval memo? | Choice (Yes) | ✓ |
| DTP-06 | `contract_signed` | Contract signed and stored in CLM? | Choice (Yes) | ✓ |

### Files Modified

| File | Change |
|------|--------|
| `shared/decision_definitions.py` | **[NEW]** Stage-specific decision maps |
| `shared/schemas.py` | Added `decision_data` to `DecisionRequest` |
| `backend/services/chat_service.py` | Proactive questioning, answer parsing, validation, rich storage |
| `backend/main.py` | Passes `decision_data` to `process_decision` |
| `frontend/api_client.py` | Added `decision_data` param to `approve_decision` |
| `frontend/pages/case_copilot.py` | Dynamic `render_decision_console()` function |
| `backend/seed_data.py` | Enriched test cases with `human_decision` and `latest_agent_output` |

---

## 📡 9. Sourcing Signal Layer (January 2026)

The **Sourcing Signal Layer** enables proactive, automated scanning of the contracts database to identify sourcing opportunities *before* humans need to manually create cases.

### Capability Overview

| Feature | Status | Description |
|---------|--------|-------------|
| **Contract Expiry Scanning** | ✅ Active | Detects contracts expiring within 90 days |
| **Risk Signal Detection** | ✅ Active | Flags suppliers with declining performance or high risk |
| **Savings Opportunity Detection** | ✅ Active | Identifies spend anomalies vs. market benchmarks |
| **Case Creation from Signals** | ✅ Active | One-click case creation from detected signals |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    📡 Signal Scanner                        │
│  (utils/signal_aggregator.py - SignalAggregator class)      │
└───────────────────────────┬─────────────────────────────────┘
                            │ scan_for_renewals()
                            │ scan_for_risk_signals()
                            │ scan_for_savings_opportunities()
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 📂 Data Source                              │
│  (utils/data_loader.py → data/contracts.json)               │
│                                                             │
│  🔌 INTEGRATION POINT: Replace load_json_data() with        │
│     API calls to your Contract Management Platform.         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 🖥️ Dashboard UI                             │
│  (frontend/pages/case_dashboard.py)                         │
│  - "📡 Sourcing Signal Scanner" expander                    │
│  - "Scan for Signals" button                                │
│  - Signal cards with "Create Case" action                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `utils/signal_aggregator.py` | Core scanning logic (deterministic, no LLM) |
| `frontend/api_client.py` | `scan_sourcing_signals()`, `create_case_from_signal()` |
| `frontend/pages/case_dashboard.py` | UI component for scanning |
| `utils/data_loader.py` | **Data source integration point** |

### Connecting a Real Contract Platform

To integrate with a live Contract Management System (CLM), modify `utils/data_loader.py`:

```python
# BEFORE (current mock implementation)
def load_json_data(filename: str) -> list:
    path = DATA_DIR / filename
    return json.loads(path.read_text())

# AFTER (example integration)
def load_json_data(filename: str) -> list:
    if filename == "contracts.json":
        # Call your CLM API instead of reading a file
        response = requests.get(
            "https://your-clm-platform.com/api/contracts",
            headers={"Authorization": f"Bearer {CLM_API_KEY}"}
        )
        return response.json()
    # ... fallback for other files
```

### Signal Types

| Signal Type | Trigger Condition | Urgency |
|-------------|-------------------|---------|
| **Renewal** | Contract expires within 90 days | High (≤30d), Medium (≤60d), Low (≤90d) |
| **Risk** | Supplier score < 5.0 OR declining trend + score < 6.0 | High / Medium |
| **Savings** | Spend variance > 15% from market benchmark | Medium / Low |

---

### 10. Agent Context Awareness (RAG) (January 2026)

To prevent generic outputs, all DTP Agents now possess **Context-Aware Retrieval Augmented Generation (RAG)** capabilities. They automatically retrieve and reference specific case documents from the Vector Store (ChromaDB) to ground their advice.

### Mechanism
1.  **Retrieval**: Agents perform targeted semantic searches in ChromaDB using the `case_id` or `category_id`.
2.  **Injection**: Retrieved document content is injected directly into the LLM system prompt.
3.  **Grounding**: The LLM uses this data to generate specific, evidence-based recommendations.

### Agent-Document Mapping

| Agent | DTP Stage | Retrieved Document Type | Example Use Case |
|-------|-----------|-------------------------|------------------|
| **StrategyAgent** | DTP-01 | Market Reports, Category Strategy | "Telecom Market Report 2025" for price benchmarking |
| **RFxDraftAgent** | DTP-02/03 | RFP Templates, Requirements | "Cybersecurity SOC RFP Template" to structure requirements |
| **NegotiationAgent** | DTP-04 | Proposals, Contracts | "Microsoft EA Renewal Proposal" for specific pricing ($32/user) |
| **ContractSupportAgent** | DTP-05 | Contract Templates (MSA/SOW) | "Service Desk SOW Template" for SLA extraction |
| **ImplementationAgent** | DTP-06 | Implementation Guides | "Cloud Migration Guide" for rollout step definition |

### Data Seeding
The seed script (`backend/scripts/seed_it_demo_data.py`) automatically populates the Vector Store with these documents for all 10 demo cases. This ensures that every demo case has high-quality, relevant documents for the agents to analyze.

---

## 🔧 11. Proactive Assistant & Verification (February 2026)

### A. Proactive Assistant (DTP Stage Progression)

**Purpose**: To guide users seamlessly through the complex DTP process without requiring them to memorize stage gates.

**Mechanism**:
1.  **Intent Detection**: The `LLMResponder` detects "Progression" intents (e.g., "Ready to move next", "Approve and proceed") via the `is_progression` flag.
2.  **Proactive Questioning**: If DTP prerequisites are missing (e.g., "Is sourcing required?"), the system *pauses* stage advancement and asks the user specifically for that data.
3.  **State Persistence**: Crucially, the system enters a persistent `Waiting for Human Decision` state. **[CRITICAL FIX]** The state is saved *immediately* upon triggering the question, ensuring the context is not lost if the user replies hours later.
4.  **Confirmation Loop**: Once all data is gathered, the system asks for a final distinct confirmation ("Confirm transition to DTP-04?") before calling the Supervisor to advance the stage.

### B. Verification: End-to-End Simulation

A new simulation harness (`scripts/simulate_case_001_journey.py`) has been added to verify the complete lifecycle without UI interaction.

**Capabilities**:
- **Mocked LLM**: Simulates user intents ("Approve", "Strategic") using a deterministic mock layer, removing randomness.
- **Full DTP Coverage**: verifying transitions from DTP-01 (Strategy) → DTP-06 (Implementation).
- **State Validation**: Asserts that `dtp_stage` and `status` are correct at every step.

**Usage**:
```bash
python scripts/simulate_case_001_journey.py
```

### C. Artifact & Decision Flow Fixes (January 2026)

### A. Artifact Type Detection (Centralized Mapping)

**Problem**: Artifacts were getting wrong types due to inconsistent agent name handling (e.g., "Strategy" vs "STRATEGY" vs "StrategyAgent").

**Solution**: Added centralized `AGENT_TO_ARTIFACT_TYPE` mapping in `chat_service.py`:

```python
AGENT_TO_ARTIFACT_TYPE = {
    "Strategy": ArtifactType.STRATEGY_ANALYSIS,
    "STRATEGY": ArtifactType.STRATEGY_ANALYSIS,
    "StrategyAgent": ArtifactType.STRATEGY_ANALYSIS,
    "Signal": ArtifactType.SIGNAL_REPORT,
    "SourcingSignal": ArtifactType.SIGNAL_REPORT,
    # ... 21 variants total
}
```

**Usage**: Replace `output.__class__.__name__` checks with dictionary lookup.

---

### B. UI String Matching Fix for Recommended Strategy

**Problem**: The "Recommended Strategy" UI component in `case_copilot.py` was hard-coded to expect only a `recommended_strategy` key from the agent output. Different agents (e.g. StrategyAgent vs SignalAssessmentAgent) use different schema fields such as `recommended_action`, `recommendation`, or `explanation` for their final output. Because the key was missing, the UI remained stuck on "Waiting for ProcuraBot Analysis...".

**Solution**: Updated the recommendation extractor to check multiple acceptable fields using a prioritized list. 

```python
        # Extract recommendation using possible keys from different agent output schemas
        rec = None
        for key in ["recommended_strategy", "recommended_action", "recommendation", "explanation"]:
            rec = output.get(key) if isinstance(output, dict) else getattr(output, key, None)
            if rec:
                break
```

**Result**: The "Recommended Strategy" component now dynamically displays the correct output regardless of which specific agent processed the request.

---

### C. Decision Flow Bypass for Task Requests

**Problem**: When `waiting_for_human = True`, ALL user messages were hijacked into the decision answer flow. Asking "Prepare the negotiation guideline" would loop back to the same decision question instead of executing agents.

**Solution**: Added intent detection bypass (lines 277-287 in `chat_service.py`):

```python
# Check if user wants to DO something, not answer a question
intent_summary = intent.get("intent_summary", "").upper()
is_task_request = intent_summary in ["EXPLORE", "DO", "ANALYZE"]

task_keywords = ["prepare", "generate", "create", "draft", "analyze", "help me with"]
message_looks_like_task = any(kw in user_message.lower() for kw in task_keywords)

if state.get("waiting_for_human") and not is_task_request and not message_looks_like_task:
    # Only then enter decision flow
```

**Result**: Users can now execute agent tasks while decision questions are pending.

---

### C. Supplier ID Sync

**Problem**: When user answers "Which supplier are we awarding to?" in chat, the `case.supplier_id` wasn't updated. Quick Overview showed "Not Assigned" even after selection.

**Solution**: Added sync logic after saving decision answer:

```python
if pending_question["id"] == "award_supplier_id":
    self.case_service.update_case(case_id, {"supplier_id": parsed_answer})
```

**Result**: Quick Overview now displays the selected supplier name.

---

### D. None Handling Fixes

**Problem**: `state.get("human_decision", {}).get(...)` fails when key exists but value is `None`. Common error pattern causing `AttributeError`.

**Solution**: Changed to defensive pattern using `or {}`:

```python
# Before (broken)
current_answers = state.get("human_decision", {}).get(current_stage, {})

# After (safe)
human_decisions = state.get("human_decision") or {}
current_answers = human_decisions.get(current_stage) or {}
```

**Locations Fixed**:
- Line 287: First decision check
- Line 418: Fallback decision check
- Line 1991: Semantic validation
- Line 1999: Parent answer lookup

---

### E. DTP-Ready Case Seed Data

**Problem**: Cases were labeled by DTP stage but lacked the required upstream decisions to actually proceed. E.g., CASE-0004 (DTP-04) had no prior stage decisions.

**Solution**: Enhanced `data/cases_seed.json` with:

1. **`human_decision`**: Pre-filled answers for prior DTP stages
2. **`case_context`**: Stage-relevant data fields

**Example (CASE-0004 in DTP-04)**:
```json
{
  "case_id": "CASE-0004",
  "dtp_stage": "DTP-04",
  "human_decision": {
    "DTP-01": {"sourcing_required": {"answer": "Yes"}, "sourcing_route": {"answer": "Strategic"}},
    "DTP-02": {"supplier_list_confirmed": {"answer": "Yes"}},
    "DTP-03": {"evaluation_complete": {"answer": "Yes"}}
  },
  "case_context": {
    "selected_supplier_id": "SUP-005",
    "selected_supplier_name": "FacilityPro Services",
    "target_savings_percent": 12
  }
}
```

### Files Modified

| File | Change |
|------|--------|
| `backend/services/chat_service.py` | +AGENT_TO_ARTIFACT_TYPE mapping, +STRING_TO_AGENT_NAME mapping, +decision bypass logic, +supplier sync, +None handling fixes |
| `data/cases_seed.json` | Enhanced with human_decision and case_context for all 5 cases |

---

## 🔧 13. Workflow Fixes (February 2026)

### Decision Persistence Across Stages

**Problem**: Preflight checks failed with "Decision 'sourcing_required' from DTP-01 not answered" even after decisions were made. Historical decisions were being cleared after each stage transition.

**Root Cause**: Two locations in `workflow.py` set `state["human_decision"] = None` after processing:
1. `supervisor_node` (line 369-372)
2. `process_human_decision` (line 1718-1722)

**Solution**: Removed both lines that cleared `human_decision`. Now only `waiting_for_human` flag is cleared, preserving historical decision data for preflight checks.

### Stage Prerequisites Fix

**Problem**: DTP-02 prereqs required `candidate_suppliers` as an INPUT, but DTP-02's purpose is to PRODUCE this list (circular dependency).

**Solution**: Removed `candidate_suppliers` from `context_fields` in `shared/stage_prereqs.py`. DTP-02 now only requires the `DTP-01.sourcing_required` decision to be answered.

---

## 🔍 14. Troubleshooting Common Issues

### Chat Loop (Repeated Questions)
**Symptom**: Asking for a task like "Prepare negotiation guideline" keeps showing the same decision question.
**Cause**: Task keywords not recognized.
**Fix**: Add the keyword to `task_keywords` list in `chat_service.py` (line 283).

### Supplier Not Showing in UI
**Symptom**: Quick Overview shows "Not Assigned" after answering award question.
**Cause**: Case record not updated.
**Fix**: Ensure `award_supplier_id` sync logic is in place (line 365-370).

### AttributeError on human_decision
**Symptom**: Error accessing `human_decision.get(...)`.
**Cause**: `human_decision` is None, not empty dict.
**Fix**: Use `state.get("human_decision") or {}` pattern.

### Artifacts Not Appearing
**Symptom**: Artifacts generated but not visible in UI.
**Cause**: Agent name not in `AGENT_TO_ARTIFACT_TYPE` mapping.
**Fix**: Add the agent name variant to the mapping dictionary.

### Preflight Check Blocks Stage Transition
**Symptom**: "Decision 'X' from DTP-Y not answered" even after answering.
**Cause**: `human_decision` dict cleared after stage transition.
**Fix**: Ensure `workflow.py` does NOT set `state["human_decision"] = None` in `supervisor_node` or `process_human_decision`.

### KeyError: budget_state
**Symptom**: Error when processing human decisions in workflow.
**Cause**: `budget_state` not initialized in state before running workflow.
**Fix**: Add `if "budget_state" not in state: state["budget_state"] = {}` before `_run_workflow()`.

---

## 🗺️ 15. Opportunity Heatmap Agentic System (March 2026)

The **Opportunity Heatmap** is a **completely independent agentic system** that continuously evaluates sourcing opportunities (contract renewals and new requests) and prioritizes them using a weighted AI scoring model. Batch demo data is IT Infrastructure–heavy; **category cards** (`data/heatmap/category_cards.json`) extend SAS and defaults to additional categories (for example Software, Hardware). The heatmap is architecturally separate from the Legacy DTP system.

### Dual-System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    UNIFIED FASTAPI BACKEND                         │
│  backend/main.py (serves BOTH systems on port 8000)                │
├─────────────────────────────┬───────────────────────────────────────┤
│  NEW HEATMAP SYSTEM         │  LEGACY DTP SYSTEM                   │
│  /api/heatmap/*             │  /api/cases/* /api/chat/*             │
│                             │                                       │
│  backend/heatmap/           │  backend/services/                    │
│  ├── agents/                │  backend/supervisor/                  │
│  │   ├── state.py           │  agents/                              │
│  │   ├── spend_agent.py     │  graphs/                              │
│  │   ├── contract_agent.py  │                                       │
│  │   ├── strategy_agent.py  │                                       │
│  │   ├── risk_agent.py      │                                       │
│  │   ├── supervisor_agent.py│                                       │
│  │   └── graph.py           │                                       │
│  ├── persistence/           │  backend/persistence/                 │
│  │   ├── heatmap_database.py│  (database.py, models.py)             │
│  │   ├── heatmap_models.py  │                                       │
│  │   └── heatmap_vector_store│                                      │
│  ├── services/              │  backend/services/                    │
│  │   ├── feedback_service.py│  (case_service.py, chat_service.py)   │
│  │   ├── case_bridge.py ────┼──▶ create_case() (ONLY TOUCHPOINT)    │
│  │   └── intake_scoring.py  │                                       │
│  ├── context_builder.py     │  (shared context + FIS field)        │
│  ├── run_pipeline_init.py   │  (batch job + DB seed)                │
│  └── heatmap_router.py      │                                       │
│                             │                                       │
│  data/heatmap.db            │  data/datalake.db                     │
│  ChromaDB: heatmap_documents│  ChromaDB: sourcing_documents         │
└─────────────────────────────┴───────────────────────────────────────┘
```

> **CRITICAL**: The two systems share NO state, NO agents, and NO databases. The `case_bridge.py` is the **only** integration point, calling `create_case()` to push approved opportunities into the legacy DTP01 pipeline.

### Heatmap Scoring Formulas

**Existing Contracts:**
```
PS_contract = 0.30(EUS) + 0.25(FIS) + 0.20(RSS) + 0.15(SCS) + 0.10(SAS)
```

**New Requests:**
```
PS_new = 0.30(IUS) + 0.30(ES) + 0.25(CSIS) + 0.15(SAS)
```

| Score | Full Name | Range | Source |
|-------|-----------|-------|--------|
| EUS | Expiry Urgency Score | 0-10 | Contract Agent |
| IUS | Implementation Urgency Score | 0-10 | Contract Agent |
| FIS | Financial Impact Score | 0-10 | Spend Agent |
| ES | Estimated Spend Score | 0-10 | Spend Agent |
| RSS | Supplier Risk Score | 0-10 | Risk Agent |
| SCS | Spend Concentration Score | 0-10 | Spend Agent |
| CSIS | Category Spend Importance Score | 0-10 | Spend Agent |
| SAS | Strategic Alignment Score | 0-10 | Strategy Agent |

### FIS: TCV vs ACV

For **existing contracts**, **FIS** is driven by contract value from the synthetic contracts CSV. By default the framework uses **TCV** (column `TCV (Total Contract Value USD)`). To use **ACV** instead, set the environment variable **`HEATMAP_FIS_USE_ACV`** to `1`, `true`, or `yes`. The spend agent and `context_builder` then read `ACV (Annual Contract Value USD)`. Intake preview responses include `meta.fis_field_note` so the UI can state which field batch scoring uses.

### Tier Classification
| Tier | Score Range | Priority |
|------|-------------|----------|
| T1 | ≥ 8.0 | Critical — immediate sourcing action |
| T2 | 6.0 – 7.99 | High — plan within quarter |
| T3 | 4.0 – 5.99 | Medium — monitor |
| T4 | < 4.0 | Low — no action needed |

### LangGraph Pipeline

The pipeline runs sequentially per opportunity:
```
spend_agent → contract_agent → strategy_agent → risk_agent → supervisor → tick → (loop or END)
```

- Each agent appends its signal to the shared `HeatmapState`.
- The `supervisor` aggregates all four signals using the weighted formula, then applies two **optional AI layers**:
  - **LLM interpreter fallbacks** (input robustness): when deterministic parsing fails for messy fields (example: missing/unparseable expiration date; messy preferred-supplier labels), the pipeline can call a small LLM “interpreter” that extracts/normalizes structured values. This is **fallback-only** and the extracted output is validated before use.
  - **Review memory** (`feedback_memory.py`): retrieve similar past feedback from Chroma, optional LLM-suggested bounded learning adjustment (see below), **`Learning:`** line on the justification, and **tier** derived from the adjusted total.
- The `tick` node increments the index; the conditional edge loops or terminates.

### Human-in-the-Loop AI Learning

1. **User input**: Humans adjust priority (tier) and optionally leave rationale via the heatmap **Review** flow. The API persists structured rows in **`ReviewFeedback`** (SQLite) and audit events.
2. **Vector memory**: Every feedback submission also upserts text into the Chroma collection **`heatmap_documents`** (`backend/heatmap/persistence/heatmap_vector_store.py`). Embeddings use **`text-embedding-3-small`** when `OPENAI_API_KEY` is set (same pattern as LangChain `OpenAIEmbeddings`). Chunks include human-readable context plus metadata: `category`, `supplier_name`, `opportunity_tier`, `component`, `adjustment_type`, `adjustment_value`, `reason_code`, `opportunity_id` (`backend/heatmap/services/feedback_service.py`).
3. **Review memory (applied scoring)**: After the deterministic **PS_contract** / **PS_new** total is computed, **`backend/heatmap/services/feedback_memory.py`** retrieves the top similar feedback snippets, then applies a **small bounded learning adjustment** and recomputes **tier** from the adjusted total. A short **`| Learning: …`** sentence is appended to **`justification_summary`** so users see why the score shifted.
   - **Batch pipeline**: Wired in **`supervisor_agent.py`** immediately after the weighted sum.
   - **Intake preview & persist**: Wired in **`intake_scoring.py`** after `ps_new_components`. Preview responses expose **`meta.feedback_memory_delta`** (the additive delta on the 0–10 total). Component sub-scores (IUS, ES, etc.) remain the pre-memory values; only **total_score** / **tier** reflect the nudge.
   - **LLM synthesis**: When snippets exist and `OPENAI_API_KEY` is set, **`gpt-4o-mini`** (override with **`HEATMAP_LEARNING_MODEL`**) returns strict JSON with **component-level deltas** (bounded \(\pm 0.5\) each) and a `user_note`. The backend converts those component deltas into a single bounded **total delta** using the current scoring weights, clamps it (roughly **±0.6**), then applies it to the total. If the API is unavailable or parsing fails, a **deterministic** fallback infers a small nudge from snippet text and metadata.
   - **Disable learning**: Set **`HEATMAP_LEARNING=0`** (or `false` / `off`) to skip retrieval and LLM usage (baseline formula only).
4. **Operational note**: With an empty Chroma collection there is **no** retrieval and **no** extra chat completion cost; costs accrue when historical feedback exists and new opportunities are scored.

### LLM interpreter fallbacks (input robustness)

The Heatmap scoring engine is intentionally deterministic, but real-world contract/supplier data is messy. To make the opportunity layer more “AI oriented” without letting an LLM take over scoring, the system includes a small **LLM interpreter** layer that runs **only when deterministic parsing fails**.

**Implementation**
- **Module**: `backend/heatmap/services/llm_interpreter.py`
- **Model**: `HEATMAP_INTERPRETER_MODEL` (default `gpt-4o-mini`)
- **Activation**: requires `OPENAI_API_KEY` and a parse failure / missing field.
- **Output**: strict JSON in “JSON mode”, then server-side validation (format checks, confidence clamp).

**What it does today**
1. **Expiration date extraction** (EUS robustness)
   - If `contract_details["Expiration Date"]` is missing or unparseable, the contract agent attempts to extract an ISO date (`YYYY-MM-DD`) from other metadata.
   - **Wired in**: `backend/heatmap/agents/contract_agent.py` (existing contracts only).
   - **Guardrails**: if the interpreter returns non-ISO or null, the system falls back to the previous safe default behavior (EUS=5, action_window="Unknown").

2. **Preferred status normalization** (SAS robustness)
   - If a record provides a messy `preferred_supplier_status` string, the strategy agent can normalize it to one of:
     `preferred | allowed | nonpreferred | straightpo | unknown`
   - **Wired in**: `backend/heatmap/agents/strategy_agent.py`
   - The normalized token is then scored deterministically using `category_cards.json` + `SAS_BY_STATUS`.

**Why this matters**
- Keeps your **math model stable** (tiers remain explainable).
- Uses the LLM where it’s strongest: **interpretation/normalization** of semi-structured fields.
- Avoids over-reliance: if the LLM is unavailable, scoring still works (with defaults).

### Business intake and opportunity provenance

- **`Opportunity.source`**: `batch` = row produced by the LangGraph CSV pipeline; `intake` = row created via **`POST /api/heatmap/intake`**.
- **Intake fields** (stored on `Opportunity`): `estimated_spend_usd`, `implementation_timeline_months`, `request_title`, `preferred_supplier_status`, plus PS_new component scores (`ius_score`, `es_score`, `csis_score`, `sas_score`) and tier.
- **PS_new preview/submit** (`backend/heatmap/services/intake_scoring.py`): Uses the same IUS / ES / CSIS / SAS helpers as the framework. **ES** normalizes against `max_estimated_spend_pipeline` = max(estimated spend on existing **intake** opportunities with no `contract_id`, the current request’s estimate, and `1.0`).
- **Batch re-run safety**: `run_init` / `POST /api/heatmap/run` deletes and re-inserts only opportunities where `source == "batch"`. Intake rows are **preserved**.

### Category cards

`data/heatmap/category_cards.json` holds per-category metadata for **SAS**: `default_preferred_status`, optional `category_strategy_sas`, and `supplier_preferred_status` (supplier name → preferred tier). Loaded via `backend/heatmap/context_builder.py` for both the batch pipeline and intake.

**Unstructured policy → structured patch (demo)**  
- **`POST /api/heatmap/category-cards/extract`** accepts `category` + `raw_text` and returns a **deterministic** `proposed_patch` (line-based hints for default status, SAS number, supplier lines like `Supplier: preferred`).  
- **`POST /api/heatmap/category-cards/extract-upload`** accepts the same as multipart: `category` + `file` (plain text, max 500KB).  
- **`POST /api/heatmap/category-cards/apply`** merges the patch into `category_cards.json` via `backend/heatmap/services/category_cards_store.py` (atomic write; `supplier_preferred_status` keys merge with existing).  
- **`POST /api/heatmap/category-cards/apply-and-rerun`** applies the patch and starts **`POST /api/heatmap/run`**’s background job so **batch** opportunities are re-scored. Intake rows already in `heatmap.db` keep stored scores until re-submitted or until you rely on preview with fresh file reads.

**UI**: Next.js heatmap copilot **Category cards** tab supports file upload, LLM assist (`/category-cards/assist`), and **Apply patch & re-score opportunities** (`apply-and-rerun`).

### API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/heatmap/opportunities` | List all scored opportunities |
| POST | `/api/heatmap/feedback` | Submit human score adjustment + written feedback (supports both structured payload and legacy Next.js payload) |
| POST | `/api/heatmap/approve` | Approve opportunities → creates Legacy DTP cases via bridge (returns `cases` map: opportunity id → case id; idempotent per opportunity via heatmap `AuditLog`) |
| POST | `/api/heatmap/run` | Start heatmap scoring job in background (non-blocking) |
| GET | `/api/heatmap/run/status` | Check scoring job status (`running`, success/error, timestamps, count) |
| GET | `/api/heatmap/intake/categories` | List category keys from `category_cards.json` (sorted) |
| POST | `/api/heatmap/intake/preview` | Compute **PS_new** for a candidate request without persisting (`meta`, `scores`, `total_score`, `tier`, `justification`). **`meta.feedback_memory_delta`**: optional additive adjustment from **review memory**; justification may include **`\| Learning: …`**. |
| POST | `/api/heatmap/intake` | Persist intake opportunity (`source=intake`); body includes `request_title`, `category`, optional `subcategory` / `supplier_name`, `estimated_spend_usd`, `implementation_timeline_months`, optional `preferred_supplier_status`, optional `justification_summary_text` |
| POST | `/api/heatmap/qa` | **Heatmap copilot — explain only:** body `question`. Loads opportunity rows from DB + recent `ReviewFeedback` + Chroma snippets; LLM answers without changing scores (`used_llm` if OpenAI ran). |
| POST | `/api/heatmap/policy/check` | **Suggestion only:** body `feedback_text`, `category`, optional `supplier_name`, `current_tier`. Compares text to `category_cards.json` via LLM JSON (`contradicts`, `severity`, `summary`, `suggestion`). |
| POST | `/api/heatmap/category-cards/assist` | **Preview only:** body `category`, `instruction`. LLM returns `proposed_patch` (requires `OPENAI_API_KEY`). |
| POST | `/api/heatmap/category-cards/extract` | **Preview only:** body `category`, `raw_text`. Deterministic extract → `proposed_patch`. |
| POST | `/api/heatmap/category-cards/extract-upload` | **Preview only:** multipart `category` + `file` (text). Same extract as above. |
| POST | `/api/heatmap/category-cards/apply` | Merge `proposed_patch` into `category_cards.json` on disk. |
| POST | `/api/heatmap/category-cards/apply-and-rerun` | Apply patch + start batch scoring pipeline (refresh batch opportunity tiers/scores). |

### User experience impact: Heatmap copilot and review memory

These capabilities change how users *feel* and work with the heatmap—not just what the API returns.

#### Heatmap copilot (`/heatmap` panel + `/api/heatmap/qa`, `/policy/check`, `/category-cards/*`)

- **Q&A (“Why is X above Y?”)**  
  - **Easier understanding:** Users get a short narrative tied to **current database rows** and recent feedback / similar vector snippets, instead of mentally diffing scores.  
  - **Trust model:** Prompts require treating stored **totals and tiers as ground truth**; the LLM explains only.  
  - **Without `OPENAI_API_KEY`:** Responses fall back to a **raw context excerpt**—usable for power users, less polished for general stakeholders.  
  - **Hallucination risk:** If an entity is not in context, the model should say so; occasional drift is possible—UI copy should keep “explanation only” explicit.

- **Policy check**  
  - **Safer reviews:** Reviewers get a **suggestion** whether written rationale aligns with **`category_cards.json`** (preferred-supplier posture). Useful before escalations or audits.  
  - **Non-blocking:** Does not auto-reject feedback or change scores—reduces anxiety without hard gates.

- **Category-cards assist / extract / apply**  
  - **Assist:** Natural-language instruction → LLM `proposed_patch` (preview).  
  - **Extract / upload:** Unstructured policy text → deterministic `proposed_patch` (or upload `.txt`).  
  - **Apply & re-score:** Optional one-step **write to `category_cards.json`** + **batch pipeline** so the opportunity list reflects new SAS-related scoring (demo path; production should add approval audit).

#### Review memory (bounded score nudge + `Learning:` line)

- **Adaptive feel:** Totals and tiers can **shift slightly** when similar past feedback exists; the **`| Learning: …`** sentence (and on intake, **`feedback_memory_delta`**) explains *why* in product language.  
- **Possible surprise:** Users may ask why a number changed vs. last run; mitigated by visible learning text and delta metadata.  
- **Intake nuance:** Component sub-scores (IUS, ES, CSIS, SAS) stay **pre-memory** values; **total_score** / **tier** reflect the nudge—advanced users should read the sidebar chip and justification as the source of truth for the final total.

**Overall:** ProcuraBot **reduces cognitive load** for reading the heatmap and supports **governance** on reviews and policy edits. Category-card changes can remain preview-only or be **applied** explicitly for demos. Review memory trades a little **predictability of the raw formula** for **visible adaptation** from human corrections.

### Deployment-Safe Runtime Mode (Render 512MB)

To support low-memory hosting (Render 512MB), Heatmap scoring is intentionally run in a lightweight mode:

1. `POST /api/heatmap/run` returns immediately and starts a background thread.
2. Frontend polls `GET /api/heatmap/run/status` until completion.
3. Once complete, frontend refreshes `GET /api/heatmap/opportunities`.

This prevents long synchronous requests and significantly reduces timeout risk during demos.

### Compatibility Notes (March 24, 2026)

#### 1) Feedback payload backward compatibility

The backend now accepts two feedback formats:

- **Structured format** (canonical):
  - `reviewer_id`, `adjustment_type`, `adjustment_value`, `reason_code`, `comment_text`, `component_affected`
- **Legacy Next.js format** (auto-translated):
  - `user_id`, `original_tier`, `suggested_tier`, `feedback_notes`

The router translates legacy tier overrides into structured adjustments before persisting to `ReviewFeedback` and `AuditLog`.

#### 2) Duplicate “Heatmap Approved” rows on the case dashboard

Two legacy cases with the same supplier name usually mean one of:

- **Two heatmap opportunities** (e.g. same supplier, different `category`: `IT Infrastructure` vs `CLOUD`) were both approved — each gets its own legacy case (different template path: DTP-01 vs DTP-02).
- **Review modal + Approve Selected** used to disagree: Review only called `/feedback` and redirected to a **seeded** case id without bridging, while Approve created a **new** case — or the UI showed “Approved” locally while the DB stayed `Pending`, so Approve could run again.
- **Double-submit** on Approve before idempotency could create two cases for the same opportunity.

**Mitigations (implemented):** bridge checks existing `CASE_APPROVED` audit for that `opportunity_id` before creating; T1 Review flow calls `/api/heatmap/approve` and redirects to the returned `case_id`; bulk approve refreshes opportunities from the API.

#### 3) Opportunity-to-case bridge reuse

`backend/heatmap/services/case_bridge.py` now reuses existing seeded case paths where possible (e.g., CASE-001..CASE-006 mapping by category keywords) to preserve rich DTP context and demo continuity.

Instead of creating only empty DTP-01 cases, the bridge can clone a template path and fill opportunity-specific identifiers (supplier/contract/name/trigger source), which reduces missing-context issues in case copilot demos.

### Synthetic Data

Generated to `data/heatmap/synthetic/` (excluded from git). Schemas mirror the real Sample Data:
- `synthetic_spend.csv` (150 PO records)
- `synthetic_contracts.csv` (25 contracts)
- `synthetic_supplier_metrics.csv` (10 suppliers)

Committed configuration (not generated):
- `data/heatmap/category_cards.json` — category strategy and preferred-supplier mappings for SAS (see **Category cards** above).

### Next.js Frontend (`frontend-next/`)

Replaces the entire Streamlit UI with a unified Next.js 16 application (Tailwind CSS v4, App Router).

| Route | System | Description |
|-------|--------|-------------|
| `/heatmap` | Heatmap | Priority list with Tier badges and score breakdowns; **Heatmap copilot** panel (Q&A, policy check, category-cards assist) |
| `/intake` | Heatmap | Business intake submit form; backend preview API (`/api/heatmap/intake/preview`) remains available for programmatic checks and testing |
| `/cases` | Legacy DTP | Case dashboard tracking DTP01–DTP06 progress |
| `/cases/[id]/copilot` | Legacy DTP | Cursor-style split: left evidence/artifacts, right chat + decision console |
| `/cases/copilot` | Legacy DTP | No-case-selected default shell (context + disabled chat prompt) |

**Theme**: MIT colorways (Cardinal Red `#A31F34`, Silver Gray `#8A8B8C`) and Sponsor colorways (Blue `#1a3cff`, Orange `#ff5c35`).

### Key Files

| File | Purpose |
|------|---------|
| `backend/heatmap/agents/state.py` | TypedDict state for the LangGraph pipeline |
| `backend/heatmap/agents/graph.py` | LangGraph pipeline definition |
| `backend/heatmap/agents/spend_agent.py` | FIS / ES / SCS / CSIS scoring |
| `backend/heatmap/agents/contract_agent.py` | EUS / IUS scoring based on expiry dates |
| `backend/heatmap/agents/strategy_agent.py` | SAS scoring |
| `backend/heatmap/agents/risk_agent.py` | RSS scoring from supplier metrics |
| `backend/heatmap/agents/supervisor_agent.py` | Weighted aggregation, tier classification, **review memory** nudge |
| `backend/heatmap/persistence/heatmap_models.py` | SQLModel tables (Opportunity, ReviewFeedback, AuditLog, etc.) |
| `backend/heatmap/persistence/heatmap_database.py` | SQLite connection (separate `heatmap.db`) |
| `backend/heatmap/persistence/heatmap_vector_store.py` | ChromaDB collection for feedback memory |
| `backend/heatmap/services/feedback_service.py` | Human feedback + Chroma upsert (rich metadata for every submission) |
| `backend/heatmap/services/feedback_memory.py` | Retrieve similar feedback, bounded score nudge + **Learning:** note (OpenAI JSON or heuristic fallback) |
| `backend/heatmap/services/heatmap_copilot.py` | Explain-only Q&A, policy-vs-feedback check, category-cards assist (uses **`HEATMAP_COPILOT_MODEL`** or `HEATMAP_LEARNING_MODEL` fallback) |
| `backend/heatmap/services/case_bridge.py` | Bridge to Legacy create_case() API |
| `backend/heatmap/services/intake_scoring.py` | PS_new scoring + persist intake opportunities |
| `backend/heatmap/context_builder.py` | Heatmap context (spend aggregates, category cards, FIS field, max TCV by category) |
| `backend/heatmap/run_pipeline_init.py` | Generate synthetic CSVs, run LangGraph pipeline, persist batch opportunities (preserves `source=intake`) |
| `backend/heatmap/heatmap_router.py` | FastAPI router (including intake endpoints) |
| `backend/heatmap/seed_synthetic_data.py` | Synthetic data generator |
| `data/heatmap/category_cards.json` | Category-level SAS / preferred-supplier configuration |
| `backend/persistence/db_interface.py` | Abstract DB interface (Azure SQL ready) |
| `backend/rag/vector_store_interface.py` | Abstract Vector Store interface (Azure AI Search ready) |

---

## 🔄 16. ProcuraBot Decision Sync + Synthetic Artifact Visibility (March 2026)

### A. Cursor-Style ProcuraBot Interaction Model

The Next.js case copilot now uses a single action zone:

- **Left panel**: read-only context (signals, supporting docs, decision status, activity log).
- **Right panel**: active workspace (chat + Decision Console controls).

This keeps "review" and "decide" conceptually linked while preserving artifact visibility.

### B. Decision-to-Chat Reaction Loop

When a user clicks **Approve** or **Request Revision** in the right panel:

1. The UI calls the decision endpoint (`/api/decisions/approve` or `/api/decisions/reject`).
2. On success, the UI appends an immediate "decision recorded" assistant message.
3. The UI auto-posts a follow-up prompt to `/api/chat` with decision context.
4. The returned assistant message is appended to the same thread ("what changed + what next").

Result: chat visibly reacts to decisions in the same workflow, instead of requiring manual follow-up prompts.

### C. Synthetic Artifacts Now Visible via `/api/documents`

`backend/scripts/seed_it_demo_data.py` now seeds artifacts in two places:

- **Chroma vector chunks** (for agent retrieval / grounding).
- **`document_records` table** (for `/api/documents` UI listing).

This removes the mismatch where artifacts were retrievable by agents but missing in document list views.

### D. Files Updated

| File | Change |
|------|--------|
| `frontend-next/src/app/cases/[id]/copilot/page.tsx` | Decision Console moved to chat side and decision-triggered chat follow-up behavior |
| `frontend-next/src/app/cases/copilot/page.tsx` | New no-case-selected default shell route |
| `backend/scripts/seed_it_demo_data.py` | Added synthetic document catalog reuse and `document_records` upsert |

---

## 🧩 17. System 1 + Heatmap Consistency Patch Log (April 2026)

This section records the full patch stream implemented for System 1 upload UX, score consistency, review workflow behavior, and config-driven scoring governance.

### A. System 1 Upload UX and Data Quality Improvements

#### 1) Top rows control made easier and defaulted to 100
- **File:** `frontend-next/src/app/system-1/upload/page.tsx`
- **Changes:**
  - Default `Top rows` changed from `50` to `100`.
  - Added separate input state (`topNInput`) so typing does not auto-reset mid-edit.
  - Added commit-on-blur/Enter behavior with clamped range.
  - Added quick preset buttons (`50`, `100`, `200`).
- **Purpose:** reduce friction in batch preview controls.

#### 2) Confidence removed from System 1 preview UI
- **File:** `frontend-next/src/app/system-1/upload/page.tsx`
- **Changes:**
  - Removed user-facing confidence column/percentages from the preview table.
  - Simplified warning acknowledgment text to avoid confidence terminology.
- **Purpose:** avoid confusion while keeping backend confidence computation available for internal logic.

#### 3) Warnings behavior corrected for new business
- **File:** `frontend-next/src/app/system-1/upload/page.tsx`
- **Changes:**
  - `Supplier name missing` warning now only applies to renewal rows.
  - Added display-level warning filtering to suppress that warning for `new_business` even if present in merged warnings.
- **Purpose:** align warnings with expected data semantics.

#### 4) Reset workflow moved from row-level to selected-row bulk action
- **File:** `frontend-next/src/app/system-1/upload/page.tsx`
- **Changes:**
  - Removed per-row reset action column/button.
  - Added `Reset selected edits` action near approve controls.
- **Purpose:** cleaner workflow for larger datasets and less table clutter.

#### 5) Table spacing/layout cleanup
- **File:** `frontend-next/src/app/system-1/upload/page.tsx`
- **Changes:**
  - Tuned table layout/column widths to eliminate right-gap and readability issues.
  - Balanced warnings column sizing after action-column removal.
- **Purpose:** stable, readable table rendering with fewer visual artifacts.

### B. System 1 Data Consumption and Provenance Fixes

#### 1) Preserve score-relevant fields during bundle fusion
- **File:** `backend/heatmap/services/system1_bundle_scan.py`
- **Changes:**
  - Preserved/propagated `preferred_supplier_status`, `rss_score`, `months_to_expiry`, `implementation_timeline_months`.
  - Prioritized row-level values before metric fallback when fusing.
- **Purpose:** prevent unnecessary defaulted components and improve completeness/readiness quality.

#### 2) Bulk-upload months/artifacts fixes at approval persistence
- **File:** `backend/main.py`
- **Changes:**
  - Derive `months_to_expiry` from `contract_end_date` when missing.
  - For bundle-scan synthesized rows, attach all uploaded files as supporting artifacts.
  - Preserve richer `scoring_inputs` in `score_provenance`.
- **Purpose:** ensure review drawer displays expected scoring inputs/artifacts for upload-staged opportunities.

#### 3) Review modal fallback for months-to-expiry display
- **File:** `frontend-next/src/app/heatmap/page.tsx`
- **Changes:**
  - Added fallback resolution: top-level field -> provenance scoring input -> computed from `contract_end_date`.
- **Purpose:** avoid blank months-to-expiry when source is present indirectly.

### C. Heatmap Score Consistency and Review Workflow Corrections

#### 1) Pipeline value `$0` aggregation bug fixed
- **File:** `frontend-next/src/app/heatmap/page.tsx`
- **Changes:**
  - Total pipeline value now sums canonical `estimated_spend_usd` first, with robust numeric parsing and alias fallback.
- **Purpose:** accurate KPI display for mixed data sources.

#### 2) Renewal urgency policy updated (<12 months treated as urgent)
- **File:** `backend/heatmap/scoring_framework.py`
- **Changes:**
  - Updated EUS bands:
    - `<=3: 10`, `<=6: 9`, `<=12: 8`, `<=18: 5`, `>18: 2`.
- **Purpose:** align urgency model with business expectation.

#### 3) Review modal/table mismatch reduced
- **Files:**
  - `frontend-next/src/app/heatmap/page.tsx`
  - `backend/heatmap/services/feedback_service.py`
- **Changes:**
  - Modal slider baseline now prefers row effective weights (`weights_used_json.effective_weights`) when available.
  - Save flow now recomputes opportunities with updated learned/global mix for better table consistency.
- **Purpose:** reduce confusing discrepancy between “preview before save” and table score state.

#### 4) Save review now visibly updates reviewed row score
- **File:** `backend/heatmap/services/feedback_service.py`
- **Changes:**
  - On save with `scoring_weight_overrides`, reviewed row total is directly recomputed from saved slider mix and persisted.
- **Purpose:** enforce user expectation that review-save immediately reflects in table score.

#### 5) Reviewed vs Approved state separation
- **File:** `frontend-next/src/app/heatmap/page.tsx`
- **Changes:**
  - Removed “Reviewed (Locked)” behavior for approved rows in review-status column.
  - Review modal can be opened/updated independent of S2 approval state.
- **Purpose:** maintain clear separation:
  - **Review** = scoring/human assessment
  - **Approve to S2C** = explicit execution action

### D. Bulk Scoring and Table Scoring Alignment

#### 1) Bulk preview now uses learned weights + category overlay
- **File:** `backend/heatmap/services/system1_scoring_orchestrator.py`
- **Changes:**
  - Loads learned weights from DB.
  - Applies category scoring overlay per row.
  - Uses effective weights in total-score calculation (renewal/new formulas).
- **Purpose:** avoid divergent hardcoded-weight path in bulk scoring.

#### 2) Bulk preview now applies feedback-memory learning nudge
- **File:** `backend/heatmap/services/system1_scoring_orchestrator.py`
- **Changes:**
  - Added `apply_learning_nudge(...)` after weighted baseline.
  - Emits final nudged `total_score` and `tier` in preview output.
- **Purpose:** match final table-style scoring behavior (weights + nudge), reducing remaining parity gaps.

#### 3) Bulk scan performance safeguard (interactive fast mode)
- **File:** `backend/heatmap/services/system1_scoring_orchestrator.py`
- **Changes:**
  - Added `SYSTEM1_ENABLE_LEARNING_NUDGE_PREVIEW` env flag (default OFF).
  - In preview/bundle scan, learning nudge is skipped by default to prevent long scan times.
  - Deterministic weighted scoring remains active and uses learned/category-overlaid weights.
- **Purpose:** keep `Scan files and fuse opportunities` responsive for interactive use while preserving consistent core scoring math.

### E. Config-Driven Scoring (Phase foundation implemented)

#### 1) Versioned scoring config persistence
- **Files:**
  - `backend/heatmap/persistence/heatmap_models.py`
  - `backend/heatmap/persistence/heatmap_database.py`
- **Changes:**
  - Added `ScoringConfigVersion` table (`draft|active|archived`, JSON payload, metadata timestamps).

#### 2) Config schema/validator/registry service
- **File:** `backend/heatmap/services/scoring_config_registry.py`
- **Changes:**
  - Added structured config schema models.
  - Added default config bootstrap with parameters + formulas.
  - Added validation for keys/rules/formulas/weight values.
  - Added extractor to map published config formula weight values into learned-weight overrides.

#### 3) Scoring config API endpoints
- **File:** `backend/heatmap/heatmap_router.py`
- **Endpoints added:**
  - `GET /api/heatmap/scoring-config/active`
  - `GET /api/heatmap/scoring-config/versions`
  - `POST /api/heatmap/scoring-config/draft`
  - `PUT /api/heatmap/scoring-config/draft/{id}`
  - `POST /api/heatmap/scoring-config/draft/{id}/validate`
  - `POST /api/heatmap/scoring-config/draft/{id}/publish`

#### 4) Publish wiring to live scoring
- **File:** `backend/heatmap/heatmap_router.py`
- **Changes:**
  - On publish, configured formula `weight_values` are normalized and synced into learned weights.
- **Purpose:** ensure published config immediately influences both bulk + table scoring paths that depend on learned weights.

#### 5) Initial management UI page
- **Files:**
  - `frontend-next/src/app/heatmap/scoring-parameters/page.tsx`
  - `frontend-next/src/app/SidebarNav.tsx`
- **Changes:**
  - Added new navigation entry and page for:
    - viewing active config,
    - creating/updating draft JSON,
    - validating draft,
    - publishing draft.

### F. Test and Validation Summary

Backend tests were run repeatedly after each major scoring/config change to keep regression risk low.

- `python -m py_compile ...` executed for modified backend modules.
- `python -m pytest tests/test_heatmap_api.py` results progressed and remained green:
  - 31 passed
  - 32 passed
  - 34 passed
  - **35 passed** (latest, includes scoring-config publish/weight-sync path)

New/expanded automated coverage includes:
- System1 preserved fields and warning behavior.
- Learned-weight usage in System1 preview scoring.
- Scoring config draft/validate/publish lifecycle.
- Scoring config publish -> learned weights sync verification.

## 18. Human-AI DTP Collaboration Patch Log (April 2026)

This section documents the hybrid-gated, cursor-like collaboration upgrade for the Next.js case copilot workspace.

### A. Stage Schema Engine (DTP-01..DTP-06)

#### 1) Canonical stage field schema
- **File:** `frontend-next/src/lib/dtp-stage-schema.ts`
- **Added:**
  - `DTP_STAGE_SCHEMA` with per-stage field definitions and metadata:
    - `required`
    - `critical`
    - `optional`
    - `ai_extractable`
    - `document_dependency`
  - Utility functions:
    - `stageSchema(stage)`
    - `computeStageReadiness(stage, values)` -> `blocked | ready_with_warnings | ready`
    - `splitStageFields(stage, values)` -> prefilled/missing/optional buckets
- **Purpose:** remove hardcoded per-stage field rendering and make DTP requirements explicit and extensible.

### B. Hybrid Readiness + Progression Gating

#### 1) Readiness-aware center workspace
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Workspace now computes stage readiness from schema + current values.
  - Added readiness banner that clearly indicates:
    - blocked due to critical missing fields
    - ready with warnings
    - ready
  - Added missing-required summary and optional-field grouping to improve usability.
- **Purpose:** enforce stage quality gates while preserving flexibility for non-critical context.

#### 2) Gating wired to generation actions
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Draft-generation buttons are disabled when stage is `blocked`.
  - Stage checklist copy now reflects blocked progression state.
- **Purpose:** prevent premature draft generation when critical data is absent.

### C. Bidirectional Form-Chat Sync (Human Confirmation First)

#### 1) Persisted stage-intake API
- **Files:**
  - `backend/main.py`
  - `backend/services/case_service.py`
- **Endpoints added:**
  - `GET /api/cases/{case_id}/stage-intake?stage=...`
  - `PUT /api/cases/{case_id}/stage-intake`
  - `POST /api/cases/{case_id}/stage-intake/extract`
  - `POST /api/cases/{case_id}/stage-intake/generation-check`
- **Behavior:**
  - Stage intake payload is stored under `human_decision[stage]["_stage_intake"]`.
  - Retrieval returns only the `values` object for UI prefill.
  - Extract endpoint provides heuristic proposals; UI must confirm before applying.
- **Purpose:** keep structured stage data auditable and synchronized with chat-assisted updates.

#### 2) Frontend sync + extraction confirmation loop
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Auto-loads stage intake when case/stage changes.
  - Added **Save stage input** action.
  - Added **Extract to fields** action from pasted text or last assistant reply.
  - Added **Confirm AI extraction** action before applying proposed updates.
  - Structured input send action persists stage intake first, then prompts copilot.
- **Purpose:** preserve human control; AI suggestions never silently overwrite structured values.

### D. DTP-03/04 Supplier Feedback Workspace

#### 1) Structured supplier-feedback capture block
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Added for DTP-03 and DTP-04:**
  - response receipt status
  - clarification/evaluation notes status
  - negotiation deltas status
  - clear guidance on manual capture + chat extraction path
- **Purpose:** support real supplier interaction feedback in a structured and reviewable format.

### E. DTP-05/06 Confirmation Checkpoints

#### 1) Critical contracting/execution fields
- **File:** `frontend-next/src/lib/dtp-stage-schema.ts`
- **Added critical gates:**
  - **DTP-05:** `contract_signed`, `legal_signoff`, `contract_reference`, etc.
  - **DTP-06:** `execution_started`, `implementation_milestones`, `kpi_monitoring_status`, `execution_confirmed_by_human`
- **Purpose:** ensure late-stage transitions are backed by explicit human confirmations.

### F. Document Generation Validation Loop

#### 1) Generation precondition check endpoint
- **File:** `backend/main.py`
- **Added logic:**
  - `_required_generation_keys(stage)` map
  - `POST /api/cases/{case_id}/stage-intake/generation-check`
  - Returns `can_generate`, `required_fields`, and `missing_fields`
- **Purpose:** deterministic guardrail before generating RFx/contract drafts from stage data.

#### 2) Frontend generation guard + refresh
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Generation calls precheck endpoint first.
  - If missing fields exist, generation is blocked with actionable feedback.
  - On successful chat/generation actions, case metadata and document center refresh automatically.
- **Purpose:** keep generated outputs aligned with validated structured inputs.

### G. Tests and Verification

#### 1) New API tests
- **File:** `tests/test_heatmap_api.py`
- **Added tests:**
  - `test_stage_intake_roundtrip_and_extract`
  - `test_stage_generation_check_preconditions`
- **Coverage:**
  - stage-intake save/retrieve
  - extraction proposal flow
  - generation precondition pass/fail behavior

#### 2) Execution summary
- Frontend build:
  - `npm run build` (Next.js) -> **passed**
- Targeted backend tests:
  - `python -m pytest tests/test_heatmap_api.py -k "stage_intake or generation_check"` -> **passed**
- Existing document/export suites also remain green in prior runs:
  - `tests/test_working_documents.py`
  - `tests/test_artifact_export.py`

## 19. DTP UX Refactor Implementation Patch Log (April 2026)

This section records the implementation pass for the **DTP UX Refactor Plan** focused on simplifying the case copilot into a critical-first, hybrid-gated stage workspace.

### A. Copilot Workspace Composition (Critical-First)

#### 1) Secondary sections collapsed to reduce cognitive load
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Converted non-primary panels into explicit expanders:
    - `Case documents`
    - `Decision audit`
    - `System activity` (already collapsible, retained)
  - Kept stage-operational content in the main workspace.
- **Purpose:** keep attention on immediate stage progression tasks while preserving access to supporting context.

#### 2) Sticky action row standardized
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Maintained one sticky action row for stage operations:
    - `Save stage input`
    - `Send structured input to ProcuraBot`
    - `Generate RFx draft`
    - `Generate contract draft`
    - `Advance stage` (new explicit action)
- **Purpose:** ensure users always have the next operational actions available without scrolling.

### B. Stage Schema Rendering Polish

#### 1) Field badge consistency and guidance
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Added consistent badge/label signals for:
    - `critical`
    - `required`
    - `optional`
    - `AI-extractable`
  - Preserved bucket-based rendering aligned with schema behavior:
    - known/prefilled context
    - missing/required focus
    - optional enhancement area
- **Purpose:** improve scanability and reduce ambiguity about field importance and AI-assist capability.

### C. Hybrid Gating + Progression Guardrails

#### 1) Explicit stage advance action wired to decision API
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Changes:**
  - Added `advanceStage()` workflow:
    - persists current stage intake (`saveStageIntake`)
    - builds stage decision payload (`buildDecisionDataForStage`)
    - posts decision approval to `/api/decisions/approve`
    - refreshes case metadata and document center
  - Introduced UX state for progression feedback:
    - `advanceSubmitting`
    - `advanceMessage`
- **Purpose:** make stage progression explicit, auditable, and aligned with decision contracts.

#### 2) Readiness-gated progression and generation
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Behavior enforced:**
  - `blocked`: disables generation and `Advance stage`
  - `ready_with_warnings`: allows proceed path while warnings remain visible
  - `ready`: full action enablement
- **Purpose:** implement hybrid gating semantics directly in UI controls and reduce invalid transitions.

### D. Form-Chat Collaboration and Confirmation

#### 1) Human-confirmed extraction preserved
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Behavior retained and hardened:**
  - `Extract to fields` produces proposal preview only.
  - `Confirm AI extraction` required before application/persistence.
  - Confirmed values persist through stage-intake APIs.
- **Purpose:** keep AI assist helpful but never auto-committing critical structured data.

### E. Stage-Specific UX (DTP-03..DTP-06)

#### 1) Supplier feedback workspace continuity
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Behavior retained/polished for DTP-03/04:**
  - structured status blocks for receipt/evaluation/negotiation feedback
  - chat extraction integration path remains available
- **Purpose:** preserve structured supplier interaction tracking while improving overall page hierarchy.

#### 2) Late-stage checkpoint usability
- **Files:** 
  - `frontend-next/src/app/cases/[id]/copilot/page.tsx`
  - `frontend-next/src/lib/dtp-stage-schema.ts`
- **Behavior:** contracting/execution checkpoints remain first-class and participate in readiness gating.
- **Purpose:** maintain operational rigor in DTP-05/06 while aligning with simplified layout.

### F. Document Generation and Output Refresh

#### 1) Local stage-context generation actions
- **File:** `frontend-next/src/app/cases/[id]/copilot/page.tsx`
- **Behavior:**
  - generation controls remain local to stage workspace (no global clutter)
  - blocked readiness prevents generation
  - post-action refresh keeps generated outputs current in document center
- **Purpose:** keep draft-generation flow contextual, deterministic, and visible.

### G. Validation Results (This Implementation Pass)

#### 1) Frontend build
- `npm run build` in `frontend-next` -> **passed**

#### 2) Targeted backend/API regressions
- `python -m pytest tests/test_heatmap_api.py -k "stage_intake or generation_check"` -> **passed**
- `python -m pytest tests/test_working_documents.py tests/test_artifact_export.py` -> **passed**

#### 3) Notes
- Existing warnings remain non-blocking (Pydantic v2 deprecation config warning and PyPDF2 deprecation warning), unchanged by this patch.

