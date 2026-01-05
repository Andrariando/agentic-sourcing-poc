# System Documentation - Agentic Sourcing Copilot

Comprehensive documentation of all system logic, mechanisms, and architectural decisions.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Intent Classification System](#intent-classification-system)
3. [Chat Service Flow](#chat-service-flow)
4. [Agent System](#agent-system)
5. [Task Execution Hierarchy](#task-execution-hierarchy)
6. [DTP Stage Progression](#dtp-stage-progression)
7. [Artifact System](#artifact-system)
8. [Data Models & Persistence](#data-models--persistence)
9. [UI/UX Flow](#uiux-flow)
10. [Conversation Memory & Context Management](#conversation-memory--context-management)
11. [Demo & Testing](#demo--testing)

---

## Architecture Overview

### Design Philosophy

The system follows a **human-in-the-loop, rule-first architecture**:

| Principle | Implementation |
|-----------|----------------|
| **Decision is focal point** | AI advises, human decides |
| **Rules > LLM** | Deterministic rules before any LLM reasoning |
| **No autonomous decisions** | All recommendations require human approval |
| **Full traceability** | Every artifact grounded in data with verification status |
| **Grounded retrieval** | Answers cite uploaded documents/data |
| **Supervisor-only state changes** | Only Supervisor Agent can modify case state |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit Frontend                      │
│  (Dashboard | Case Copilot | Knowledge Management)          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Chat Service │  │ Case Service │  │ Ingestion    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌────────────────────────────────────┐                     │
│  │      Supervisor (Router)           │                     │
│  │  - Intent Classification           │                     │
│  │  - Agent Routing                   │                     │
│  │  - State Management                │                     │
│  └──────┬─────────────────────────────┘                     │
│         │                                                    │
│         ▼                                                    │
│  ┌────────────────────────────────────┐                     │
│  │  7 Official Agents                │                     │
│  │  - Sourcing Signal                │                     │
│  │  - Supplier Scoring               │                     │
│  │  - RFx Draft                      │                     │
│  │  - Negotiation Support            │                     │
│  │  - Contract Support               │                     │
│  │  - Implementation                 │                     │
│  └──────┬─────────────────────────────┘                     │
│         │                                                    │
│         ▼                                                    │
│  ┌────────────────────────────────────┐                     │
│  │  Task Execution Layer              │                     │
│  │  Rules → Retrieval → Analytics → LLM                    │
│  └────────────────────────────────────┘                     │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   SQLite     │ │   ChromaDB   │ │   Files      │
│  (Structured)│ │  (Vectors)   │ │  (Uploads)   │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Folder Structure

```
backend/
├── supervisor/          # Central orchestration
│   ├── router.py       # Intent classification & routing
│   └── state.py        # State management
├── agents/             # 7 official agents
│   ├── base.py         # Base agent with retrieval
│   ├── sourcing_signal_agent.py
│   ├── supplier_scoring_agent.py
│   ├── rfx_draft_agent.py
│   ├── negotiation_support_agent.py
│   ├── contract_support_agent.py
│   └── implementation_agent.py
├── tasks/              # Sub-tasks (internal to agents)
│   ├── planners.py     # Deterministic playbooks
│   ├── registry.py     # Task registry
│   └── *_tasks.py      # Task implementations
├── artifacts/          # Artifact builders & renderers
├── services/           # Business logic layer
│   ├── chat_service.py      # Copilot with Supervisor
│   ├── case_service.py      # Case + artifact management
│   └── ingestion_service.py # Ingestion orchestration
├── persistence/        # Data lake (SQLite)
├── rag/               # Vector retrieval (ChromaDB)
└── scripts/           # Utility scripts

frontend/
├── app.py             # Main entry point
├── api_client.py      # Backend communication
└── pages/
    ├── case_dashboard.py
    ├── case_copilot.py
    └── knowledge_management.py

shared/
├── constants.py       # Enums & constants
└── schemas.py         # Pydantic schemas
```

---

## Intent Classification System

### Overview

The system uses a **hybrid classification approach** combining rule-based patterns with LLM fallback for ambiguous cases.

### Classification Flow

```
User Message
    ↓
┌─────────────────────────────────┐
│  Context Gathering              │
│  - DTP stage                    │
│  - Has existing output?         │
│  - Case status                  │
│  - Waiting for approval?        │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  Single-Level Classification    │
│  (STATUS | EXPLAIN | EXPLORE |  │
│   DECIDE)                       │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  Two-Level Classification       │
│  (UserGoal + WorkType)          │
│                                 │
│  1. Rule-Based (Fast)           │
│     - Pattern matching          │
│     - Context-aware checks      │
│     - Confidence scoring        │
│                                 │
│  2. If confidence < 0.85:       │
│     LLM Classification          │
│     - Structured output         │
│     - Cached results            │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  Action Plan Generation         │
│  (Agent + Tasks)                │
└─────────────────────────────────┘
```

### Single-Level Classification

**Purpose**: Quick routing to intent handlers (STATUS, EXPLAIN, EXPLORE, DECIDE)

**Patterns** (in priority order):
1. **STATUS** - "status", "progress", "update", "where are we"
2. **DECIDE** - Action verbs: "scan", "score", "draft", "generate", "create"
3. **EXPLORE** - "what if", "alternative", "options", "compare"
4. **EXPLAIN** - "what is", "explain", "why", "how does", "tell me"

**Context-Aware Adjustments**:
- If action verb + no existing output → DECIDE (high confidence)
- If question + has existing output → EXPLAIN
- If question + no output + "can you" → DECIDE (action request)

### Two-Level Classification

**Purpose**: Detailed intent for agent selection and task planning

**User Goals**:
- **TRACK** - Monitor/check status, scan data
- **UNDERSTAND** - Explain existing recommendations/data
- **CREATE** - Generate artifacts (draft, score, plan)
- **CHECK** - Validate/comply with policy
- **DECIDE** - Make decision requiring approval

**Work Types**:
- **ARTIFACT** - Generate work products
- **DATA** - Retrieve/analyze data
- **APPROVAL** - Human decision required
- **COMPLIANCE** - Policy/rule check
- **VALUE** - Savings/ROI analysis

**Rule-Based Classification**:

1. **Special Case Patterns** (highest priority, confidence 0.95):
   - `check eligibility`, `validate` → CHECK
   - `score supplier`, `evaluate supplier` → CREATE
   - `draft rfx`, `create rfx` → CREATE
   - `scan signals` → CREATE (if no output) or TRACK (if has output)
   - `negotiat`, `leverage` → CREATE
   - `extract terms` → CREATE
   - `implement`, `rollout` → CREATE

2. **Action Verb Detection** (confidence 0.95):
   - If action verb detected + no existing output → CREATE
   - Action verbs: `scan`, `score`, `draft`, `support`, `extract`, `generate`, `create`, `build`, `prepare`, `compare`, `define`, `track`, `evaluate`, `analyze`

3. **Pattern Matching** (confidence 0.85):
   - Matches against GOAL_PATTERNS and WORK_PATTERNS dictionaries
   - First match wins

4. **Context-Aware Adjustments**:
   - Question + existing output → UNDERSTAND (instead of CREATE)

**LLM Classification** (for ambiguous cases):

- **Trigger**: Rule-based confidence < 0.85
- **Model**: GPT-4o-mini (temperature 0.1)
- **Input**: Message + context (DTP stage, has output, status)
- **Output**: JSON with `user_goal`, `work_type`, `confidence`, `rationale`
- **Caching**: MD5 hash of (message + context) → cached result
- **Cache Size**: 100 entries (LRU eviction)

**Hybrid Routing**:
```python
if rule_confidence >= 0.85:
    return rule_result
else:
    llm_result = classify_intent_llm(message, context)
    if rule_confidence < 0.7:
        return llm_result  # Trust LLM more
    else:
        # Weighted merge
        return llm_result if llm_confidence > rule_confidence else rule_result
```

### Example Classifications

| Message | Context | Single-Level | Two-Level | Confidence |
|---------|---------|--------------|-----------|------------|
| "Scan signals" | DTP-01, no output | DECIDE | CREATE + DATA | 0.95 |
| "What signals do we have?" | DTP-01, has output | EXPLAIN | TRACK + DATA | 0.85 |
| "Score suppliers" | DTP-02, no output | DECIDE | CREATE + DATA | 0.95 |
| "Check supplier eligibility" | DTP-02, no output | DECIDE | CHECK + DATA | 0.95 |
| "Explain the scoring" | DTP-02, has output | EXPLAIN | UNDERSTAND + DATA | 0.85 |
| "Can you draft an RFx?" | DTP-03, no output | DECIDE | CREATE + ARTIFACT | 0.95 |

---

## Chat Service Flow

### Message Processing Pipeline

```
User Message
    ↓
┌─────────────────────────────────┐
│  1. Load Case State             │
│     - DTP stage                 │
│     - Status                    │
│     - Latest agent output       │
│     - Waiting for human?        │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  1a. Get Conversation Context   │
│     (if memory enabled)         │
│     - Retrieve recent messages  │
│     - Summarize older messages  │
│     - Estimate token cost       │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  2. Check for Approval/Rejection│
│     (if waiting_for_human)      │
│     - Pattern matching          │
│     - Process decision          │
│     - Advance stage if approved │
│     - Save message to DB        │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  3. Classify Intent             │
│     - Single-level (router)     │
│     - Two-level (for DECIDE)    │
│     - Context-aware             │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  4. Save User Message to DB     │
│     (if memory enabled)         │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  5. Route to Intent Handler     │
│                                 │
│  STATUS → _handle_status_intent │
│  EXPLAIN → _handle_explain_intent│
│  EXPLORE → _handle_explore_intent│
│  DECIDE → _handle_decide_intent │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  6. Generate Response           │
│     - Format agent output       │
│     - Include grounding         │
│     - Set waiting flag          │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  7. Save Assistant Response     │
│     (if memory enabled)         │
└─────────────────────────────────┘
```

### Intent Handlers

#### STATUS Intent Handler

**Purpose**: Provide case status without running agents

**Logic**:
1. Check for affirmative responses ("yes", "analyze") - if no output exists, route to agent analysis
2. Build status summary:
   - Current stage and name
   - Category, supplier (if applicable)
   - Latest recommendation (if exists)
   - Waiting for approval notice (if applicable)
3. Return friendly status message

**No agent execution** - uses cached state only

#### EXPLAIN Intent Handler

**Purpose**: Explain existing agent outputs or case information

**Logic**:
1. **Check for action keywords** - If "scan signals", "score suppliers", etc., route to agent analysis instead
2. If no `latest_agent_output`:
   - Check for affirmative response → route to agent analysis
   - Otherwise → ask what user wants to know
3. If `latest_agent_output` exists:
   - Parse output based on `agent_name`
   - Format response with specific details:
     - SourcingSignal: signals, urgency score, summary
     - SupplierScoring: suppliers, criteria, scores
     - RFxDraft: RFx path, sections, completeness
     - NegotiationSupport: leverage points, targets, playbook
     - ContractSupport: terms, validation, handoff
     - Implementation: checklist, indicators, savings
   - Include grounding references
   - Ask if user wants more detail

#### EXPLORE Intent Handler

**Purpose**: Explore alternatives without changing state

**Logic**:
1. Check if exploration is allowed at current stage
2. Run agent analysis if appropriate
3. Mark as exploration (no state change)
4. Return hypothetical results

#### DECIDE Intent Handler

**Purpose**: Execute agent analysis and require approval

**Logic**:
1. Use two-level intent classification (hybrid)
2. Generate action plan (agent + tasks)
3. Execute agent:
   - Run tasks in order
   - Track execution metadata
   - Build artifact pack
4. Check if approval required:
   - DECIDE goal → always requires approval
   - Stage-specific rules (DTP-04, DTP-05)
5. Update state:
   - Set `latest_agent_output`
   - Set `waiting_for_human` = True (if approval needed)
   - Update activity log
6. Format response:
   - Show agent output summary
   - Request approval if needed
   - Suggest next steps

### Approval/Rejection Processing

**Pattern Detection**:
- Approval: "yes", "approve", "proceed", "go ahead", "confirm", "accept", "agree"
- Rejection: "no", "reject", "cancel", "stop", "decline", "wait", "hold"

**When Approved**:
1. Call `process_decision(case_id, "Approve")`
2. Advance DTP stage (if transition allowed)
3. Update `waiting_for_human` = False
4. Log decision in activity log
5. Return confirmation with new stage

**When Rejected**:
1. Call `process_decision(case_id, "Reject")`
2. Keep current stage
3. Update `waiting_for_human` = False
4. Log decision
5. Offer alternatives (explore, revise, provide feedback)

---

## Agent System

### Base Agent Architecture

All agents inherit from `BaseAgent`:

```python
class BaseAgent(ABC):
    def __init__(self, name: str, tier: int = 1):
        self.name = name
        self.tier = tier  # 1 = gpt-4o-mini, 2 = gpt-4o
        self.retriever = get_retriever()  # ChromaDB + SQLite
        self.llm = ChatOpenAI(...)
    
    @abstractmethod
    def execute(self, case_context: Dict[str, Any]) -> ArtifactPack:
        """Execute agent logic and return artifact pack."""
        pass
    
    def retrieve_documents(self, query: str, doc_types: List[str]) -> List[Document]:
        """Retrieve documents from ChromaDB."""
        pass
    
    def retrieve_data(self, query: str, table: str) -> List[Dict]:
        """Retrieve structured data from SQLite."""
        pass
```

**Key Features**:
- **Controlled retrieval**: Agents can only retrieve via explicit tools
- **Execution metadata tracking**: Tracks tokens, costs, documents retrieved, task details
- **No state modification**: Agents return outputs only; Supervisor updates state

### Agent Execution Flow

```
Agent.execute(context)
    ↓
┌─────────────────────────────────┐
│  1. Initialize Execution        │
│     Metadata                    │
│     - Timestamp                 │
│     - User message              │
│     - DTP stage                 │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  2. Get Action Plan             │
│     (from Planner)              │
│     - Agent name                │
│     - Task list                 │
│     - Approval required?        │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  3. Execute Tasks               │
│     (in order)                  │
│     - Track each task           │
│     - Collect outputs           │
│     - Build grounding refs      │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  4. Finalize Metadata           │
│     - Total tokens              │
│     - Estimated cost            │
│     - Documents retrieved       │
│     - Task details              │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  5. Build Artifact Pack         │
│     - Artifacts                 │
│     - Next actions              │
│     - Risks                     │
│     - Execution metadata        │
└─────────────────────────────────┘
```

### The 7 Official Agents

#### 1. Sourcing Signal Agent

**Purpose**: Detect sourcing opportunities from contracts, spend, performance

**Tasks**:
1. `detect_contract_expiry_signals` - Query contracts expiring in 30-90 days
2. `detect_performance_degradation_signals` - Analyze supplier performance trends
3. `detect_spend_anomalies` - Statistical deviation analysis (2+ std dev)
4. `apply_relevance_filters` - Filter by category, stage, severity
5. `semantic_grounded_summary` - LLM narration of signals
6. `produce_autoprep_recommendations` - Generate next actions

**Outputs**:
- `SIGNAL_REPORT` - Signals with urgency scores (1-10)
- `SIGNAL_SUMMARY` - Human-readable summary
- `AUTOPREP_BUNDLE` - Recommended actions + required inputs

**Example**: Detects contract expiring in 35 days → Urgency 7 → Recommends "Review contract terms" + "Evaluate alternatives"

#### 2. Supplier Scoring Agent

**Purpose**: Evaluate and rank suppliers based on performance and criteria

**Tasks**:
1. `build_evaluation_criteria` - Construct criteria from inputs + templates
2. `pull_supplier_performance` - Retrieve KPIs (quality, delivery, responsiveness, cost variance)
3. `pull_risk_indicators` - Get SLA events, breach counts, severity
4. `normalize_metrics` - Normalize all metrics to 0-10 scale
5. `compute_scores_and_rank` - Calculate weighted scores, rank suppliers
6. `eligibility_checks` - Apply rule-based thresholds (min score, max breaches)
7. `generate_explanations` - LLM narration explaining scores

**Outputs**:
- `EVALUATION_SCORECARD` - Criteria and weights
- `SUPPLIER_SCORECARD` - Scored table with all suppliers + ranking
- `SUPPLIER_SHORTLIST` - Top N suppliers with rationale

#### 3. RFx Draft Agent

**Purpose**: Assemble RFx documents (RFI/RFP/RFQ) from templates and examples

**Tasks**:
1. `determine_rfx_path` - Rules: RFI if requirements undefined, RFQ if <$50K, RFP otherwise
2. `retrieve_templates_and_past_examples` - Search ChromaDB for templates
3. `assemble_rfx_sections` - Build standard sections (Executive Summary, Scope, Technical, Pricing)
4. `completeness_checks` - Validate all required sections present
5. `draft_questions_and_requirements` - LLM generation of key questions
6. `create_qa_tracker` - Create Q&A tracking table

**Outputs**:
- `RFX_PATH` - Determined path (RFI/RFP/RFQ) with rationale
- `RFX_DRAFT_PACK` - Complete draft document
- `RFX_QA_TRACKER` - Q&A tracking table

#### 4. Negotiation Support Agent

**Purpose**: Provide negotiation insights without making award decisions

**Tasks**:
1. `compare_bids` - Structured comparison (price, terms, SLA, services) with variance
2. `leverage_point_extraction` - Identify leverage from performance + competition
3. `benchmark_retrieval` - Search ChromaDB for market rate benchmarks
4. `price_anomaly_detection` - Flag unusually high/low bids (>20% from mean)
5. `propose_targets_and_fallbacks` - Calculate target (5% below lowest), fallback, walk-away
6. `negotiation_playbook` - LLM generation of talking points, give/get trades

**Outputs**:
- `NEGOTIATION_PLAN` - Targets, fallbacks, playbook summary
- `LEVERAGE_SUMMARY` - Leverage points with strength ratings
- `TARGET_TERMS` - Specific target values for key terms

#### 5. Contract Support Agent

**Purpose**: Extract key terms and prepare implementation handoff

**Tasks**:
1. `extract_key_terms` - Retrieve contract docs, extract structured terms (pricing, term, SLA, liability, termination)
2. `term_validation` - Rule-based checks against policy (liability limits, SLA minimums, cure periods, payment terms)
3. `term_alignment_summary` - LLM narration summarizing alignment and issues
4. `implementation_handoff_packet` - Create structured handoff (summary, contacts, SLA, payment, dates, risks)

**Outputs**:
- `KEY_TERMS_EXTRACT` - Structured extraction of all key terms
- `TERM_VALIDATION_REPORT` - Validation results with issues flagged
- `CONTRACT_HANDOFF_PACKET` - Complete handoff for implementation team

#### 6. Implementation Agent

**Purpose**: Produce rollout steps and early success indicators

**Tasks**:
1. `build_rollout_checklist` - Retrieve rollout playbooks, create phased checklist (Preparation, Kick-off, Transition, Steady State)
2. `compute_expected_savings` - Deterministic: annual savings = old value - new value, total = annual × term years
3. `define_early_indicators` - Define KPIs (SLA compliance, response time, delivery, invoice accuracy, satisfaction) with risk triggers
4. `reporting_templates` - Generate templates for monthly reports, quarterly reviews, savings tracking

**Outputs**:
- `IMPLEMENTATION_CHECKLIST` - Phased rollout checklist with owners and dates
- `EARLY_INDICATORS_REPORT` - KPI definitions with targets and risk triggers
- `VALUE_CAPTURE_TEMPLATE` - Savings breakdown and reporting templates

---

## Task Execution Hierarchy

### Decision Hierarchy

All tasks follow the same execution hierarchy:

```
Task.execute(context)
    ↓
┌─────────────────────────────────┐
│  1. run_rules()                 │
│     - Deterministic checks      │
│     - Policy validation         │
│     - May short-circuit         │
│     Output: RulesResult         │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  2. run_retrieval()             │
│     - Query ChromaDB            │
│     - Query SQLite              │
│     - Build grounding refs      │
│     Output: RetrievalResult     │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  3. run_analytics()             │
│     - Compute scores            │
│     - Normalize metrics         │
│     - Compare, rank             │
│     - Detect anomalies          │
│     Output: AnalyticsResult     │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  4. run_llm()                   │
│     (only if needed)            │
│     - Narrative summaries       │
│     - Explanations              │
│     - LLM narration             │
│     Output: LLMResult           │
└────────────┬────────────────────┘
             ↓
┌─────────────────────────────────┐
│  TaskResult                     │
│  - data                         │
│  - grounded_in (refs)           │
│  - tokens_used                  │
└─────────────────────────────────┘
```

**Key Principles**:
1. **Rules first** - Never call LLM if rules block
2. **Retrieval second** - Always ground in data before analysis
3. **Analytics third** - Use deterministic calculations when possible
4. **LLM last** - Only for narration/packaging, not decision-making

### Task Playbooks

Each agent has a playbook that maps `(user_goal, work_type, dtp_stage)` → ordered task list.

**Example - Supplier Scoring Agent**:
```python
SUPPLIER_SCORING_PLAYBOOKS = {
    "default": [
        "build_evaluation_criteria",
        "pull_supplier_performance",
        "pull_risk_indicators",
        "normalize_metrics",
        "compute_scores_and_rank",
        "eligibility_checks",
        "generate_explanations",
    ],
    "track": [
        "pull_supplier_performance",
        "compute_scores_and_rank",
    ],
    "check": [
        "pull_supplier_performance",
        "pull_risk_indicators",
        "eligibility_checks",
    ],
}
```

**Task Selection**:
- If `user_goal = CREATE` and `work_type = DATA` → "default" playbook
- If `user_goal = TRACK` → "track" playbook (lighter)
- If `user_goal = CHECK` → "check" playbook (validation focus)

---

## DTP Stage Progression

### DTP Stages

| Stage | Name | Description |
|-------|------|-------------|
| DTP-01 | Strategy | Signal detection, strategy recommendation |
| DTP-02 | Planning | Supplier scoring, market intelligence |
| DTP-03 | Sourcing | RFx drafting |
| DTP-04 | Negotiation | Negotiation support |
| DTP-05 | Contracting | Contract term extraction, validation |
| DTP-06 | Execution | Implementation planning |

### Stage Transition Rules

**Allowed Transitions**:
```
DTP-01 → DTP-02
DTP-02 → DTP-03, DTP-04
DTP-03 → DTP-04
DTP-04 → DTP-05
DTP-05 → DTP-06
DTP-06 → DTP-06 (terminal)
```

**Transition Validation**:
1. Check allowed transitions dictionary
2. Check policy context (if provided)
3. Validate required inputs are present
4. Require human approval (if configured)

**Transition Triggers**:
- Human approval of recommendation → automatic stage advance
- Explicit user request → validate and advance if allowed
- No automatic progression without human approval

### Stage-Specific Agent Access

| Stage | Available Agents |
|-------|------------------|
| DTP-01 | Sourcing Signal |
| DTP-02 | Supplier Scoring, Sourcing Signal |
| DTP-03 | RFx Draft, Supplier Scoring |
| DTP-04 | Negotiation Support, Supplier Scoring |
| DTP-05 | Contract Support |
| DTP-06 | Implementation |

### Stage Requirements

Each stage has required inputs that must be present before certain actions:

- **DTP-01**: Category ID (optional: Contract ID)
- **DTP-02**: Category ID, Evaluation Criteria
- **DTP-03**: Category ID, Requirements, RFx Type
- **DTP-04**: Supplier ID(s), Bids, Negotiation Context
- **DTP-05**: Contract Document, Supplier ID, Terms
- **DTP-06**: Contract ID, Supplier ID, Implementation Details

---

## Artifact System

### ArtifactPack Structure

```python
class ArtifactPack(BaseModel):
    pack_id: str
    agent_name: str
    artifacts: List[Artifact]
    next_actions: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    created_at: str
    tasks_executed: List[str]
    execution_metadata: Optional[ExecutionMetadata]
```

### Artifact Structure

```python
class Artifact(BaseModel):
    artifact_id: str
    type: ArtifactType  # SIGNAL_REPORT, SUPPLIER_SCORECARD, etc.
    title: str
    content_text: str
    verification_status: str  # VERIFIED, PARTIAL, UNVERIFIED
    grounded_in: List[GroundingReference]
```

### Verification Status

- **VERIFIED**: All claims grounded in retrieved documents/data
- **PARTIAL**: Some claims grounded, some inferred
- **UNVERIFIED**: No grounding references found

### Grounding References

```python
class GroundingReference(BaseModel):
    source_type: str  # "document", "data", "policy"
    source_id: str
    relevance: str
    excerpt: Optional[str] = None
```

### Artifact Types

**By Agent**:
- **Sourcing Signal**: `SIGNAL_REPORT`, `SIGNAL_SUMMARY`, `AUTOPREP_BUNDLE`
- **Supplier Scoring**: `EVALUATION_SCORECARD`, `SUPPLIER_SCORECARD`, `SUPPLIER_SHORTLIST`
- **RFx Draft**: `RFX_PATH`, `RFX_DRAFT_PACK`, `RFX_QA_TRACKER`
- **Negotiation Support**: `NEGOTIATION_PLAN`, `LEVERAGE_SUMMARY`, `TARGET_TERMS`
- **Contract Support**: `KEY_TERMS_EXTRACT`, `TERM_VALIDATION_REPORT`, `CONTRACT_HANDOFF_PACKET`
- **Implementation**: `IMPLEMENTATION_CHECKLIST`, `EARLY_INDICATORS_REPORT`, `VALUE_CAPTURE_TEMPLATE`

### Artifact Persistence

1. **Save to Database**: `ArtifactPackModel` (SQLite) stores:
   - Pack metadata
   - Serialized artifacts
   - Execution metadata (JSON)
   - Timestamps

2. **Retrieve for UI**: `case_service.get_all_artifact_packs(case_id)` returns all packs with full metadata

3. **Display in UI**: Artifacts shown in tabs by type, with expandable cards showing details

---

## Data Models & Persistence

### Case State Model

```python
class SupervisorState(TypedDict):
    case_id: str
    dtp_stage: str
    status: str  # "In Progress", "Waiting for Human", "Closed"
    category_id: Optional[str]
    supplier_id: Optional[str]
    contract_id: Optional[str]
    latest_agent_output: Optional[Dict[str, Any]]
    latest_agent_name: Optional[str]
    waiting_for_human: bool
    activity_log: List[Dict[str, Any]]
```

**Persistence**: Stored in `CaseModel` (SQLite) as JSON fields

### ArtifactPack Model

```python
class ArtifactPackModel(SQLModel, table=True):
    pack_id: str  # Primary key
    case_id: str  # Foreign key
    agent_name: str
    artifacts_json: str  # Serialized List[Artifact]
    next_actions_json: str  # Serialized List[Dict]
    risks_json: str  # Serialized List[Dict]
    tasks_executed_json: str  # Serialized List[str]
    execution_metadata_json: Optional[str]  # Serialized ExecutionMetadata
    created_at: str
```

### ExecutionMetadata Model

```python
class ExecutionMetadata(BaseModel):
    agent_name: str
    dtp_stage: str
    execution_timestamp: str
    user_message: str
    total_tasks: int
    tasks_executed: List[str]
    total_tokens_used: int
    estimated_cost_usd: float
    model_used: str
    documents_retrieved: List[str]
    retrieval_sources: List[Dict[str, Any]]
    task_details: List[TaskExecutionDetail]
```

**TaskExecutionDetail**:
```python
class TaskExecutionDetail(BaseModel):
    task_name: str
    execution_order: int
    status: str  # "completed", "skipped", "error"
    tokens_used: Optional[int]
    output_summary: Optional[str]
    grounding_sources: List[Dict[str, Any]]
```

### ChatMessage Model

```python
class ChatMessage(SQLModel, table=True):
    message_id: str  # Primary key (UUID)
    case_id: str  # Foreign key to CaseState
    role: str  # "user" | "assistant"
    content: str  # Message text
    intent_classified: Optional[str]  # UserIntent enum value
    agents_called: Optional[str]  # JSON array
    tokens_used: Optional[int]
    estimated_cost_usd: Optional[float]
    created_at: str  # ISO timestamp
```

**Purpose**: Persistent storage for conversation history to enable multi-turn conversations with context awareness.

**Usage**: 
- Messages saved after each user/assistant exchange (if conversation memory enabled)
- Retrieved for context when processing new messages
- Used for cost estimation and budget enforcement

### Data Stores

1. **SQLite** (`data/datalake.db`):
   - Cases, ArtifactPacks, ChatMessages (via SQLModel)
   - Structured data: Suppliers, Contracts, Performance, Spend, SLA Events

2. **ChromaDB** (`data/chromadb/`):
   - Document embeddings (PDF, DOCX, TXT)
   - Semantic search for retrieval

3. **Files** (`data/synthetic_docs/`):
   - Uploaded documents (for reference)
   - Synthetic test documents

---

## UI/UX Flow

### Page Structure

#### 1. Case Dashboard (`case_dashboard.py`)

**Purpose**: List all cases with metrics and filtering

**Components**:
- Case cards showing:
  - Case ID, name, category
  - Current stage and status
  - Key findings summary
  - Quick actions

- Filters:
  - Stage
  - Status
  - Category

- Demo data management:
  - Run happy path demo
  - Open demo case

#### 2. Case Copilot (`case_copilot.py`)

**Purpose**: Main workbench for case interaction

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Case Header (Condensed)                                │
│  - Case ID, Category, Stage, Status                     │
└─────────────────────────────────────────────────────────┘
┌──────────────────────────────┬──────────────────────────┐
│  Case Details (60%)          │  Chat Interface (40%)    │
│  - Overview                  │  - Scrollable history    │
│  - Strategy                  │  - Message input         │
│  - Signals                   │  - Welcome prompts       │
│  - Governance                │  - Metadata display      │
│  - Documents & Timeline      │                          │
└──────────────────────────────┴──────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Artifacts Panel (Full Width)                           │
│  Tabs: Signals | Scoring | RFx | Negotiation |          │
│        Contract | Implementation | History | Audit Trail│
│  - Expandable cards                                       │
│  - Detailed artifact views                               │
└─────────────────────────────────────────────────────────┘
```

**Chat Interface**:
- **Scrollable container**: Fixed height, auto-scrolls to bottom
- **Message bubbles**: User (right), Assistant (left)
- **Welcome message**: Shows on first load with suggested prompts
- **Metadata**: Shows agent, intent, tokens used (expandable)

**Artifact Tabs**:
- **Signals**: Signal reports, urgency scores, recommendations
- **Scoring**: Scorecards, shortlists, criteria
- **RFx Drafts**: RFx paths, draft documents, Q&A trackers
- **Negotiation**: Negotiation plans, leverage points, targets
- **Contract**: Term extracts, validation reports, handoff packets
- **Implementation**: Checklists, indicators, value capture
- **History**: Activity log with timestamps
- **Audit Trail**: Execution metadata, task details, costs

#### 3. Knowledge Management (`knowledge_management.py`)

**Purpose**: Upload documents and structured data

**Features**:
- Document upload (PDF, DOCX, TXT)
- CSV/Excel data upload
- Document list with metadata
- Ingestion history

### Chat History Loading

Chat history is loaded from case `activity_log`:

1. Filter entries where `action` starts with "Chat:"
2. Extract user/assistant messages
3. Parse metadata (agent, intent, timestamp)
4. Display in chronological order
5. Auto-scroll to bottom (latest message)

---

## Conversation Memory & Context Management

### Overview

The system supports **optional conversation memory** to enable ChatGPT-like multi-turn conversations with cost-aware context management. This feature is **disabled by default** for backward compatibility and must be explicitly enabled via environment variable.

**Key Features**:
- Persistent conversation history in database
- Cost-aware context selection (recent messages + summaries)
- Pre-execution cost estimation and budget enforcement
- Graceful degradation (system works if feature disabled)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              ConversationContextManager                 │
│  • Retrieve recent messages (last N)                    │
│  • Summarize older conversations                        │
│  • Estimate token costs                                 │
│  • Filter context within budget                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    ChatService                          │
│  1. Get relevant context (if enabled)                   │
│  2. Estimate cost before execution                      │
│  3. Check budget limits                                 │
│  4. Include context in agent execution                  │
│  5. Save messages to database                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Agents                               │
│  • Receive conversation_history in case_context         │
│  • Use context for better reasoning (optional)          │
│  • Work without context (backward compatible)           │
└─────────────────────────────────────────────────────────┘
```

### Configuration

**Environment Variables**:

```bash
# Enable/disable conversation memory (default: false)
ENABLE_CONVERSATION_MEMORY=false

# Cost management
MAX_COST_PER_MESSAGE=1.0  # Maximum cost per message in USD
MAX_CONTEXT_TOKENS=1500   # Maximum tokens for conversation context
RECENT_MESSAGES_COUNT=10  # Always include last N messages
SUMMARIZE_THRESHOLD=20    # Summarize if more than N messages

# Summarization (optional)
ENABLE_SUMMARIZATION=true  # Enable conversation summarization
```

### Context Selection Strategy

1. **Recent Messages First**: Always include last N messages (default: 10)
2. **Token Budget**: Context limited by `MAX_CONTEXT_TOKENS` (default: 1500 tokens)
3. **Summarization**: If >N messages exist, summarize older messages (future enhancement)
4. **Trimming**: If still over limit, trim oldest messages until within budget

### Cost Estimation

**Pre-execution cost estimation**:
- Estimates tokens for conversation context
- Estimates tokens for user message
- Estimates tokens for agent execution (base + output)
- Calculates cost based on model tier (gpt-4o-mini vs gpt-4o)
- Enforces `MAX_COST_PER_MESSAGE` limit

**Cost Calculation**:
- **Tier 1 (gpt-4o-mini)**: $0.15/1K input, $0.60/1K output
- **Tier 2 (gpt-4o)**: $5.00/1K input, $15.00/1K output

### Token Estimation

Uses **tiktoken** if available for accurate token counting, otherwise falls back to approximation (4 characters ≈ 1 token).

### Backward Compatibility

**All changes are backward compatible**:
- Feature disabled by default (`ENABLE_CONVERSATION_MEMORY=false`)
- System works identically if feature disabled
- Agents receive `conversation_history` in `case_context` but can ignore it
- Graceful degradation if database/conversation manager fails

### Message Storage

**ChatMessage Table**:
- Stores all user and assistant messages
- Includes metadata: intent, agents called, tokens used, cost
- Indexed by `case_id` and `created_at` for efficient retrieval
- Messages persist across sessions

**Retrieval**:
- Messages retrieved by `case_id`
- Ordered by `created_at` (chronological)
- Limited to recent messages (configurable limit)

### Integration Points

1. **ChatService.process_message()**:
   - Retrieves context at start (if enabled)
   - Saves user message after classification
   - Saves assistant response after generation

2. **Agent Execution**:
   - `case_context` includes `conversation_history` (if available)
   - Agents can use context for better reasoning
   - Agents work without context (backward compatible)

3. **Cost Enforcement**:
   - Pre-execution cost estimation
   - Budget check before agent execution
   - Returns cost warning if exceeds limit

### Future Enhancements

1. **LLM-based Summarization**: Use gpt-4o-mini to summarize older conversations
2. **Semantic Search**: Use embeddings to find relevant past messages
3. **Cross-Case Context**: Reference conversations from related cases
4. **User Preferences**: Per-user conversation memory settings
5. **Advanced Compression**: More sophisticated token reduction techniques

---

## Demo & Testing

### Happy Path Demo

**Purpose**: Complete demonstration case showing full DTP-01 to DTP-06 workflow

**Script**: `backend/scripts/run_happy_path_demo.py`

**Process**:
1. **Seed Data**: Ensures suppliers, spend, SLA events, documents exist
2. **Create Case**: Creates or resets `CASE-DEMO-001`
3. **Execute Workflow**: Sends messages through all stages:
   - DTP-01: "Scan signals" → "What signals do we have?" → "Recommend strategy"
   - DTP-02: "Score suppliers" → "Check eligibility" → "Explain scoring"
   - DTP-03: "Draft RFx" → "Explain RFx path"
   - DTP-04: "Support negotiation" → "Explain leverage points"
   - DTP-05: "Extract key terms" → "Explain validation"
   - DTP-06: "Generate implementation plan" → "Explain checklist"
4. **Auto-Approve**: Automatically approves decisions to advance stages
5. **Save History**: All conversations saved to `activity_log`
6. **Persist State**: Final state saved to database

**Usage**:
```bash
python backend/scripts/run_happy_path_demo.py
```

**Output**:
- Case `CASE-DEMO-001` in DTP-06
- Complete chat history in activity log
- All artifacts persisted
- Snapshot saved to `data/happy_path_demo.json`

**Viewing in UI**:
1. Start backend: `python -m uvicorn backend.main:app --reload --port 8000`
2. Start frontend: `streamlit run frontend/app.py`
3. Navigate to Case Dashboard
4. Select `CASE-DEMO-001`
5. Chat history loads automatically
6. Explore artifacts in bottom panel

### Test Scripts

**Intent Classification Test**: `backend/scripts/test_intent_classification.py`
- Tests various message types
- Verifies context-aware classification
- Shows confidence scores

**Usage**:
```bash
python backend/scripts/test_intent_classification.py
```

---

## Key Design Decisions

### Why Hybrid Classification?

- **Speed**: Rules handle 80-90% of cases instantly
- **Accuracy**: LLM handles ambiguous cases better than pure rules
- **Cost**: LLM only called when needed (~10-20% of messages)
- **Maintainability**: Rules for common cases, LLM for edge cases

### Why Supervisor-Only State Changes?

- **Consistency**: Single source of truth for state
- **Governance**: All transitions validated in one place
- **Auditability**: All state changes logged by Supervisor
- **Safety**: Prevents agents from corrupting state

### Why Rules → Retrieval → Analytics → LLM?

- **Determinism**: Rules provide consistent results
- **Grounding**: Retrieval ensures answers are data-driven
- **Efficiency**: Analytics uses deterministic calculations
- **Narration**: LLM only for human-readable summaries

### Why ArtifactPacks?

- **Structure**: Consistent output format across agents
- **Traceability**: Grounding references for verification
- **Flexibility**: Multiple artifacts per pack
- **Auditability**: Execution metadata for transparency

---

## Future Enhancements

1. **Production Hardening**:
   - Authentication & authorization
   - Rate limiting
   - Error handling & retries
   - Monitoring & logging

2. **Advanced Features**:
   - Multi-turn conversations
   - Context memory across sessions
   - Custom agent workflows
   - Integration with external systems

3. **Performance**:
   - Async task execution
   - Caching improvements
   - Database indexing
   - Vector store optimization

---

## References

- **Main README**: `README.md` (quick start guide)
- **Code**: See folder structure above for implementation details
- **Constants**: `shared/constants.py` for enums and configurations
- **Schemas**: `shared/schemas.py` for data models

