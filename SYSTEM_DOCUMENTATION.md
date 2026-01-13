# Agentic Sourcing System: Technical Backend Documentation

This document provides a detailed technical deep-dive into the backend architecture and logic of the Agentic Sourcing Copilot. It is intended for auditing, technical review, and developers seeking to understand the inner workings of the system.

**Last Updated**: January 2026

---

## 🏗️ 1. High-Level Architecture

The system follows a service-oriented architecture with a clear separation between governance, execution, and persistence.

- **API Layer (FastAPI)**: The entry point for all frontend requests (`backend/main.py`).
- **Service Layer (ChatService, CaseService)**: Orchestrates business logic and service interactions.
- **Agent Layer (Supervisor & Worker Agents)**: The "brain" of the system, using LLMs to analyze data and generate artifacts.
- **RAG Layer (Retriever, Vector Store)**: Handles document retrieval and grounding analysis.
- **Persistence Layer (SQLite/ChromaDB)**: Stores case data, chat history, and document embeddings.

### Running the System

```bash
# Terminal 1: Start Backend API
python -m uvicorn backend.main:app --port 8000

# Terminal 2: Start Frontend
python -m streamlit run frontend/app.py

# Seed Demo Data
python backend/scripts/seed_comprehensive_data.py
```

---

## 💬 2. The Chat Request Lifecycle

What happens when a human asks something in the chat window?

### Step 1: Frontend Submission
The user types a message and clicks send. The Streamlit frontend (`frontend/pages/case_copilot.py`) sends a `POST` request via `APIClient` to `/api/chat` with:
- `case_id`: The unique identifier for the current procurement project.
- `user_message`: The raw text input from the user.
- `use_tier_2`: A flag indicating whether to use more advanced (and expensive) LLM models.

### Step 2: ChatService Entry Point
`ChatService.process_message()` in `backend/services/chat_service.py` is the main orchestrator. It performs:
1. **Traceability**: Generates a unique `trace_id` (UUID) for logging and debugging this specific request.
2. **Context Retrieval**: Loads the current case state (DTP stage, status, metadata) from the database.
3. **Conversation Memory**: If enabled, fetches recent chat history to provide context to the LLM.

### Step 3: Hybrid Routing (Autonomy Layer)
Instead of rigid hard-coded rules, the system now uses a **Hybrid Routing Strategy** (`graphs/workflow.py`) to decide "Who does the work":

1.  **Status/Greeting Check**: Simple greetings or status checks are handled quickly.
2.  **Deterministic Rules (Guardrails)**: First, the `SupervisorAgent` checks if strict DTP rules mandate a specific path (e.g., "After RFx Draft, MUST go to Negotiation"). This ensures process integrity and prevents out-of-order execution.
3.  **LLM Autonomy (Reasoning)**: If the rules provide no specific direction (e.g., the user asks a random question like "Why are costs up?"), the Supervisor asks an **LLM Router** (`decide_next_agent_llm`).
    *   The LLM analyzes the user's intent and context.
    *   It selects the best specialist agent (e.g., `SignalInterpretation` for cost analysis) regardless of the current stage.
    *   **User Intent Override**: The system now prioritizes explicit user instructions over default rules (e.g., "Ignore the budget warning").
    *   **Explanation Logic**: If the user asks for explanation of an existing output (e.g., "How did you calculate this?"), the Router skips agent execution to prevent re-work, allowing the system to simply explain the prior result.
    *   This enables a seamless "Happy Path" where the user can ask anything at any time.

### Step 4: Agent Execution (LangGraph)
Once the path is chosen, the system executes the workflow:
1.  **Specialist Agent Node**: The selected agent (e.g., `StrategyAgent`) runs.
    *   It retrieves necessary data (SQL + RAG).
    *   It generates a structured artifact (e.g., `StrategyRecommendation`).
    *   It is **deterministic** in its calculations (e.g. scoring) but uses LLM for synthesis.
2.  **Loop**: The output is fed back to the Supervisor to determine if more work is needed or if it should return to the user.

### Step 6: Persistence & State Update
The output and conversation history are saved:
- The `CaseService` persists the artifacts to the database.
- The `Case Status` might update (e.g., moving from "DTP-01" to "DTP-02").
- If the agent made a recommendation, the case state is set to `waiting_for_human = True`.

### Step 7: Final Response Generation
The `ResponseAdapter` takes the agent's output and formats it into a conversational message for the user.

---

## 📊 3. DTP Stage Data Requirements

Each DTP (Draft to Procurement) stage uses specific data sources and produces specific outputs.

### DTP-01: Strategy (Need Identification)

**Purpose**: Identify sourcing opportunities and define initial strategy.

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
```

**Sample Interaction**:
- User: "What's the renewal strategy for this case?"
- Agent: Queries supplier performance, spend trends, and SLA compliance to recommend action.

---

### DTP-02: Planning (Supplier Evaluation Prep)

**Purpose**: Prepare evaluation criteria and supplier longlist.

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
```

---

### DTP-03: Sourcing (RFx & Selection)

**Purpose**: Issue RFx, collect responses, evaluate, and shortlist.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Supplier Proposals** | Uploaded documents | Pricing, capabilities, references |
| **Evaluation Rubrics** | ChromaDB | Scoring criteria from policy docs |
| **Comparison Templates** | ChromaDB | Historical RFP evaluations |

**Agent**: `RfxDraftAgent` (in workflow)

**Output**: `RFxDraft` with evaluation matrices

---

### DTP-04: Negotiation

**Purpose**: Negotiate best terms with selected supplier(s).

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
```

**Sample Interaction**:
- User: "What's our negotiation position for this renewal?"
- Agent: Analyzes market benchmarks, alternative quotes, and relationship history.

---

### DTP-05: Contracting

**Purpose**: Finalize contract terms and prepare for signature.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Contract Templates** | ChromaDB | Standard terms, legal clauses |
| **Negotiated Terms** | Previous outputs | Agreed pricing, SLAs |
| **Policy Requirements** | ChromaDB | Compliance checklist, approval gates |

**Agent**: `ContractSupportAgent`
**Collaboration**: Prioritizes user-requested clauses over standard templates.

**Output**: `ContractExtraction` with key terms and compliance status

---

### DTP-06: Implementation

**Purpose**: Execute, monitor, and capture value.

**Input Data Used**:
| Data Type | Source | Fields Used |
|-----------|--------|-------------|
| **Implementation Guides** | ChromaDB | Rollout best practices, timelines |
| **KPI Definitions** | Case context | Agreed metrics from contract |
| **Transition Plans** | ChromaDB | Change management docs |

**Agent**: `ImplementationAgent`
**Collaboration**: Allows modification of rollout steps (e.g. "Add Legal Review") via user intent.

**Output**: `ImplementationPlan` with milestones and KPIs

---

## 🗂️ 4. Synthetic Data Reference

The system comes with comprehensive synthetic data for testing. Run the seed script:

```bash
python backend/scripts/seed_comprehensive_data.py
```

### Available Test Cases

| Case ID | Name | Category | DTP Stage | Key Data |
|---------|------|----------|-----------|----------|
| CASE-0001 | IT Services Contract Renewal | IT_SERVICES | DTP-01 | 3 suppliers, 12mo spend, SLA history |
| CASE-0002 | Office Supplies Cost Reduction | OFFICE_SUPPLIES | DTP-01 | 3 suppliers, spend anomaly (+20%) |
| CASE-0003 | Cloud Infrastructure Migration | CLOUD_SERVICES | DTP-02 | AWS/Azure/GCP comparison data |
| CASE-0004 | Marketing Agency Selection | MARKETING_SERVICES | DTP-03 | 4 agency proposals, evaluation rubric |
| CASE-0005 | Facilities Management Negotiation | FACILITIES_MANAGEMENT | DTP-04 | Incumbent vs. market benchmarks |

### Supplier Data (16 suppliers across 5 categories)

**IT Services**:
- SUP-IT-001: TechCorp Solutions (7.8/10, stable, low risk)
- SUP-IT-002: Global IT Partners (7.2/10, improving, medium risk)
- SUP-IT-003: CloudFirst Systems (8.2/10, stable, low risk)

**Office Supplies**:
- SUP-OFF-001: OfficeMax Pro (7.0/10, declining, cost issues)
- SUP-OFF-002: Corporate Supply Co (8.0/10, competitive pricing)
- SUP-OFF-003: BulkOffice Direct (7.5/10, best pricing)

**Cloud Services**:
- SUP-CLOUD-001: Amazon Web Services (8.8/10)
- SUP-CLOUD-002: Microsoft Azure (8.7/10, better pricing)
- SUP-CLOUD-003: Google Cloud Platform (8.5/10, best pricing)

**Marketing Services**:
- SUP-MKT-001: Creative Minds Agency (8.3/10, premium)
- SUP-MKT-002: Digital First Marketing (8.0/10, improving)
- SUP-MKT-003: B2B Marketing Pros (7.8/10, value pricing)
- SUP-MKT-004: Integrated Brand Solutions (7.5/10)

**Facilities Management**:
- SUP-FAC-001: FacilityPro Services (8.5/10, requesting 8% increase)
- SUP-FAC-002: BuildingCare Plus (7.8/10, market rate)
- SUP-FAC-003: Integrated Facilities Group (7.5/10, competitive)

### Documents in ChromaDB (11 documents, 71 chunks)

| Document | Type | Category | DTP Relevance |
|----------|------|----------|---------------|
| RFP_Template_IT_Services.txt | RFx | IT_SERVICES | DTP-02, DTP-03 |
| IT_Services_Market_Benchmark_2025.txt | Market Report | IT_SERVICES | DTP-01, DTP-04 |
| Office_Supplies_Catalog_Pricing.txt | Catalog | OFFICE_SUPPLIES | DTP-01, DTP-02 |
| Office_Supplies_Market_Analysis.txt | Market Report | OFFICE_SUPPLIES | DTP-01, DTP-04 |
| Cloud_Provider_Comparison_Guide.txt | Technical Guide | CLOUD_SERVICES | DTP-01, DTP-02, DTP-03 |
| Cloud_Migration_Best_Practices.txt | Technical Guide | CLOUD_SERVICES | DTP-02, DTP-06 |
| Marketing_Agency_RFP_Template.txt | RFx | MARKETING_SERVICES | DTP-02, DTP-03 |
| Marketing_Agency_Evaluation_Rubric.txt | Evaluation Guide | MARKETING_SERVICES | DTP-03 |
| Facilities_Management_SOW.txt | Contract | FACILITIES_MANAGEMENT | DTP-05, DTP-06 |
| Facilities_Management_Market_Rates.txt | Market Report | FACILITIES_MANAGEMENT | DTP-01, DTP-04 |
| Procurement_Policy_DTP_Gates.txt | Policy | All | DTP-01 to DTP-06 |

---

## 🛠️ 5. Key Backend Components

### 1. ChatService (`backend/services/chat_service.py`)
The main orchestrator. Contains:
- `process_message()`: Primary API method (lines 121-251)
- Intent-specific handlers: `_handle_status_intent()`, `_handle_explain_intent()`, etc.
- Response formatting and error handling

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

---

## 🛡️ 6. Governance & Safety
- **Human-in-the-Loop**: All major decisions require explicit user approval.
- **Cost Awareness**: The `ConversationContextManager` prunes chat history.
- **Transparency**: Detailed execution metadata recorded for auditability.

---

## 🔧 7. Recent Changes (January 2026)

### Collaborative Architecture Refactor
1.  **User Intent Injection**: All agents now accept `user_intent` to override deterministic rules/templates.
2.  **Refinement Loops**: The "Reject" decision in the workflow now triggers a **Feedback Loop** (Refinement) instead of termination. Users can provide a reason, and the agent re-runs with that context.
3.  **Platform Stability**: Fixed Windows-specific Unicode logging crashes.


### Bug Fixes
1. **Duplicate `process_message` method**: Renamed legacy method to `process_message_langgraph()` to prevent API issues.
2. **Pydantic/dict handling**: Fixed attribute access for `AgentActionLog` and `BudgetState` objects.
3. **Windows encoding**: Replaced emojis with ASCII-safe text in print statements.
4. **Backend emojis**: Fixed encoding issues in `backend/main.py` and `graphs/workflow.py`.

### Data Enhancements
1. Created comprehensive seed script (`backend/scripts/seed_comprehensive_data.py`).
2. Added 5 realistic test cases across different categories and DTP stages.
3. Seeded 16 suppliers with differentiated performance data.
4. Added 11 category-specific documents to ChromaDB.

### Architecture Clarifications
- Frontend (`frontend/app.py`) communicates with backend API on port 8000.
- The root `app.py` is a legacy standalone version (not used with API architecture).
