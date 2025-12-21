# Agentic AI System Architecture

**Version:** 3.0 (Phase 3 Complete)  
**Last Updated:** December 2024

---

## Executive Summary

This document describes the complete architecture of the Agentic AI Sourcing System—a research proof-of-concept that implements a **human-like collaborative assistant** for dynamic sourcing pipelines (DTP).

The system is designed around three core principles:

1. **Governance First** — Rules and policies override LLM reasoning
2. **Human Authority** — All significant decisions require human approval
3. **Collaboration as Input** — User discussions shape execution (not just trigger it)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Interaction Modes](#2-interaction-modes)
3. [Intent Classification](#3-intent-classification)
4. [Collaboration Mode](#4-collaboration-mode)
5. [Execution Constraints](#5-execution-constraints)
   - 5.1 [Constraint Compliance Invariant](#51-constraint-compliance-invariant-critical) ⚠️ **CRITICAL**
6. [Execution Mode & Workflow](#6-execution-mode--workflow)
7. [Agent Architecture](#7-agent-architecture)
8. [Supervisor & Orchestration](#8-supervisor--orchestration)
9. [Memory Architecture](#9-memory-architecture)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [Guardrails & Governance](#11-guardrails--governance)
12. [File Reference](#12-file-reference)

---

## 1. System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              STREAMLIT UI (app.py)                          │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │   Chat Input    │───▶│ Intent Classifier│───▶│  Mode Router            │  │
│  │   (User Intent) │    │  (Rule-based)    │    │  COLLABORATIVE/EXECUTION│  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘  │
│                                                          │                   │
│           ┌──────────────────────────────────────────────┼──────────────────┤
│           │                                              │                  │
│           ▼                                              ▼                  │
│  ┌─────────────────────────┐                 ┌─────────────────────────┐   │
│  │   COLLABORATION MODE    │                 │    EXECUTION MODE       │   │
│  │                         │                 │                         │   │
│  │ • Collaboration Engine  │                 │ • LangGraph Workflow    │   │
│  │ • Constraint Extractor  │                 │ • Supervisor Agent      │   │
│  │ • DTP Templates         │                 │ • Specialist Agents     │   │
│  │ • No DTP Advancement    │                 │ • DTP Stage Transitions │   │
│  └─────────────────────────┘                 └─────────────────────────┘   │
│           │                                              │                  │
│           ▼                                              ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SHARED STATE & MEMORY                             │   │
│  │  • CaseMemory (narrative context)                                    │   │
│  │  • ExecutionConstraints (binding user preferences)                   │   │
│  │  • Session State (chat history, cases)                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose | LLM Usage |
|-----------|---------|-----------|
| **Intent Classifier** | Route user input to COLLABORATIVE or EXECUTION mode | None (rule-based) |
| **Collaboration Engine** | Generate discussion responses, extract constraints | None (templates) |
| **Constraint Extractor** | Extract binding constraints from user statements | None (rule-based) |
| **Supervisor Agent** | Orchestrate workflow, manage state, route agents | None (deterministic) |
| **Strategy Agent** | Recommend sourcing strategy (DTP-01) | Rules first, LLM for summarization |
| **Supplier Agent** | Evaluate and score suppliers (DTP-02/03) | Rules first, LLM for explanation |
| **Negotiation Agent** | Create negotiation plans (DTP-04) | LLM with constraints |
| **RFx Draft Agent** | Draft RFx documents (DTP-03) | LLM with templates |
| **Contract Support Agent** | Extract contract terms (DTP-05) | LLM for extraction |
| **Implementation Agent** | Create rollout plans (DTP-06) | LLM for planning |

---

## 2. Interaction Modes

The system operates in two distinct modes:

### Collaboration Mode (Default)

**Purpose:** Sense-making, discussion, clarification

**Behavior:**
- ❌ Does NOT advance DTP stage
- ❌ Does NOT invoke LangGraph workflow
- ❌ Does NOT call decision agents
- ✅ References CaseMemory for context
- ✅ Extracts binding constraints from user input
- ✅ Asks DTP-specific clarifying questions
- ✅ Frames options without recommending

**Tone:** First-person, collaborative, curious (never directive)

### Execution Mode

**Purpose:** Run agents, produce recommendations, advance DTP

**Behavior:**
- ✅ Invokes LangGraph workflow
- ✅ Calls Supervisor and specialist agents
- ✅ May advance DTP stage (with human approval)
- ✅ Produces structured recommendations
- ✅ Consumes ExecutionConstraints from collaboration

**Trigger:** Explicit execution intent from user (e.g., "proceed", "run analysis")

---

## 3. Intent Classification

**File:** `utils/intent_classifier.py`

The Intent Classifier determines whether user input should trigger Collaboration Mode or Execution Mode.

### Classification Logic (Rule-Based, No LLM)

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              PATTERN MATCHING (Deterministic)                    │
│                                                                  │
│  EXECUTION patterns:     "proceed", "run analysis", "recommend"  │
│  COLLABORATIVE patterns: "what are the options", "help me think" │
│  AMBIGUOUS patterns:     "what should we do" → default COLLAB    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
     ┌────────────────┐              ┌────────────────┐
     │ COLLABORATIVE  │              │   EXECUTION    │
     │ (default when  │              │ (explicit      │
     │  ambiguous)    │              │  action only)  │
     └────────────────┘              └────────────────┘
```

### Pattern Examples

| Pattern Type | Examples | Result |
|--------------|----------|--------|
| **Execution** | "proceed", "run analysis", "make a recommendation", "go ahead" | EXECUTION |
| **Collaborative** | "what are the options", "help me think", "what are the risks" | COLLABORATIVE |
| **Ambiguous** | "what should we do", "thoughts?", "suggestions?" | COLLABORATIVE (default) |

### Key Design Decisions

1. **Default to COLLABORATIVE** — Ambiguous inputs trigger discussion, not execution
2. **No LLM** — Fully deterministic, auditable, transparent
3. **High confidence required for EXECUTION** — Protects against accidental workflow triggers

---

## 4. Collaboration Mode

**Files:** 
- `utils/collaboration_engine.py`
- `utils/collaboration_templates.py`

### Collaboration Engine

Generates human-like collaborative responses that feel like a thoughtful consultant.

```python
# Response Generation Flow
1. Extract constraints from user input (ConstraintExtractor)
2. Acknowledge constraints immediately (builds trust)
3. Reference CaseMemory context (what we know)
4. Frame options without recommending
5. Ask 1-2 DTP-specific clarifying questions
6. Offer transition to execution ("Ready for me to proceed?")
```

### DTP-Specific Templates

Each DTP stage has tailored collaboration content:

| DTP Stage | Focus Areas | Example Questions |
|-----------|-------------|-------------------|
| **DTP-01** (Strategy) | Strategy framing, risk tolerance | "What's driving the urgency here?" |
| **DTP-02** (Planning) | Evaluation criteria, weighting | "What matters most — price, quality, or reliability?" |
| **DTP-03** (Sourcing) | Supplier screening, market scan | "Should we cast a wide net or focus on a targeted shortlist?" |
| **DTP-04** (Negotiation) | Negotiation posture, flexibility | "How aggressive should our negotiation posture be?" |
| **DTP-05** (Contracting) | Contract terms, implementation risk | "Are there any contract terms requiring special attention?" |
| **DTP-06** (Execution) | Value realization, monitoring | "What's the most critical metric for success?" |

### Example Collaboration Response

**User:** "What are the options here?"

**System Response:**
```
You're right to explore the options. Let's think through this together.

At this stage, we're shaping the overall approach. There are typically 
a few paths: renewing with the current supplier, renegotiating terms, 
running a competitive process, or consolidating the category entirely. 
Each has different risk/reward profiles.

**Before we proceed, I'd like to understand:**
- What's driving the urgency here — is it cost pressure, service issues, or contract timing?
- How much disruption are you comfortable with if we pursue a competitive approach?

---
💡 Once we've aligned on the strategic direction and key priorities, 
I can run the analysis and provide a formal recommendation. Want me to do that now?
```

---

## 5. Execution Constraints

**Files:**
- `utils/execution_constraints.py`
- `utils/constraint_extractor.py`

### Core Principle

> **When a human states a preference, constraint, or requirement, it MUST override default assumptions in all future reasoning.**

Collaboration is not just "discussion" — it is **decision-shaping input**.

### ExecutionConstraints Model

```python
ExecutionConstraints:
  # Core preferences
  disruption_tolerance: LOW | MEDIUM | HIGH | UNSPECIFIED
  risk_appetite: LOW | MEDIUM | HIGH | UNSPECIFIED
  time_sensitivity: LOW | MEDIUM | HIGH | UNSPECIFIED
  
  # Process requirements
  stakeholder_alignment_required: bool
  legal_review_required: bool
  
  # Budget
  budget_flexibility: FIXED | FLEXIBLE | UNSPECIFIED
  max_budget: float (optional)
  
  # Supplier preferences
  supplier_preference: PREFER_INCUMBENT | PREFER_NEW | NEUTRAL
  excluded_suppliers: List[str]
  required_suppliers: List[str]
  
  # Negotiation
  negotiation_posture: COLLABORATIVE | COMPETITIVE | BALANCED
  walkaway_terms: List[str]
  must_have_terms: List[str]
  
  # Evaluation
  priority_criteria: List[str]  # e.g., ["price", "quality"]
```

### Constraint Extraction (Deterministic)

The ConstraintExtractor uses **pattern matching only** (no LLM):

| User Statement | Constraint Extracted | Acknowledgment |
|----------------|---------------------|----------------|
| "I don't mind disruption" | `disruption_tolerance = HIGH` | "Got it — disruption is acceptable, so I'll include more aggressive options." |
| "Need to align with category management" | `stakeholder_alignment_required = True` | "Noted — stakeholder alignment is required, so I'll factor that into the timeline." |
| "Budget is fixed" | `budget_flexibility = FIXED` | "Understood — the budget is fixed, so I'll only consider options within that limit." |
| "Price is the priority" | `priority_criteria = ["price"]` | "Got it — cost/price is the top priority, so I'll weight that heavily." |
| "Push them hard" | `negotiation_posture = COMPETITIVE` | "Noted — I'll structure the negotiation strategy aggressively to maximize leverage." |

### How Constraints Flow to Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COLLABORATION MODE                               │
│                                                                         │
│   User: "I don't mind disruption, but price is king"                    │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │                  CONSTRAINT EXTRACTOR                         │     │
│   │                                                               │     │
│   │   disruption_tolerance = HIGH ✓                               │     │
│   │   priority_criteria = ["price"] ✓                             │     │
│   └──────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│   ExecutionConstraints stored in session_state                          │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ (user later says "proceed")
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXECUTION MODE                                  │
│                                                                         │
│   workflow_state["execution_constraints"] = ExecutionConstraints         │
│                              │                                          │
│                              ▼                                          │
│   ┌──────────────────────────────────────────────────────────────┐     │
│   │                    AGENT PROMPT                               │     │
│   │                                                               │     │
│   │   === BINDING USER CONSTRAINTS (MUST OVERRIDE DEFAULTS) ===   │     │
│   │   • Disruption tolerance: HIGH                                │     │
│   │   • Priority criteria: price                                  │     │
│   │                                                               │     │
│   │   Your recommendation MUST account for these constraints.     │     │
│   │   If you cannot satisfy a constraint, you MUST explain why.   │     │
│   │   === END BINDING CONSTRAINTS ===                             │     │
│   └──────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Difference: CaseMemory vs ExecutionConstraints

| Aspect | CaseMemory | ExecutionConstraints |
|--------|------------|---------------------|
| **Purpose** | Narrative context, history | Binding decision inputs |
| **Authority** | Informational (context only) | Authoritative (must obey) |
| **Content** | Decisions made, agent outputs, user intents | User preferences, requirements, constraints |
| **Usage** | Injected for context | Injected as hard requirements |
| **Override** | Cannot override logic | MUST override default logic |

---

## 5.1 Constraint Compliance Invariant (CRITICAL)

**File:** `utils/constraint_compliance.py`

### Architectural Invariant (Non-Negotiable)

> **No execution output is valid unless it explicitly accounts for every active ExecutionConstraint.**

"Accounting for" means:
- Either **satisfying** the constraint
- OR **explicitly explaining** why it cannot be satisfied

**SILENCE IS FORBIDDEN.**

### ConstraintComplianceChecker

A deterministic checker that runs **after every agent execution** and **before Supervisor approval**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT EXECUTION                              │
│                           │                                      │
│                           ▼                                      │
│              ┌────────────────────────┐                          │
│              │   Agent Output         │                          │
│              └────────────────────────┘                          │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         CONSTRAINT COMPLIANCE CHECKER                     │   │
│  │         (Deterministic, Rule-based, No LLM)               │   │
│  │                                                           │   │
│  │   For each active constraint:                             │   │
│  │   ✓ Check if output references the constraint             │   │
│  │   ✓ OR justifies why it doesn't apply                     │   │
│  │                                                           │   │
│  │   Result: COMPLIANT | NON_COMPLIANT | NO_CONSTRAINTS       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│           ┌───────────────┴───────────────┐                      │
│           │                               │                      │
│           ▼                               ▼                      │
│    ┌────────────┐                  ┌────────────┐                │
│    │ COMPLIANT  │                  │NON_COMPLIANT│                │
│    │            │                  │             │                │
│    │ Proceed    │                  │ Add warning │                │
│    │ normally   │                  │ to response │                │
│    └────────────┘                  └────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

### Mandatory Behavioral Reflection

When constraints exist, the chatbot **MUST** acknowledge them **before** presenting a recommendation:

**Example (constraints exist):**
```
**Based on your stated preferences:**
Since disruption is acceptable and price is the priority, I've factored these into my analysis.

---

I've completed my analysis for this case and have a recommendation ready.

**Recommended Strategy: RFx** (confidence: 85%)
...
```

**Example (unchanged recommendation):**
```
**Based on your stated preferences:**
Since disruption is acceptable, I've factored this into my analysis.

_Even with these preferences, the recommendation remains RFx because 
the competitive process offers the best price leverage regardless of 
disruption tolerance._

---

**Recommended Strategy: RFx** (confidence: 85%)
...
```

### Compliance Status in State

The workflow state tracks compliance:

```python
PipelineState:
  constraint_compliance_status: "COMPLIANT" | "NON_COMPLIANT" | "NO_CONSTRAINTS"
  constraint_violations: List[str]  # What wasn't addressed
  constraint_reflection: str  # Mandatory acknowledgment text
```

### What Gets Checked

| Constraint | Keywords Checked in Output |
|------------|---------------------------|
| `disruption_tolerance = HIGH` | "disruption", "aggressive", "competitive", "switch" |
| `disruption_tolerance = LOW` | "stability", "continuity", "conservative", "incumbent" |
| `risk_appetite = HIGH` | "risk", "aggressive", "bold", "opportunity" |
| `risk_appetite = LOW` | "conservative", "safe", "caution", "minimize risk" |
| `time_sensitivity = HIGH` | "urgent", "fast", "immediate", "speed" |
| `priority_criteria = ["price"]` | "price" must appear in output |
| `excluded_suppliers = ["X"]` | "X" must NOT appear in shortlist |

### Trust-Building Behavior

This invariant ensures:

1. **User feels heard** — Their stated preferences are visibly acknowledged
2. **Transparency** — If constraints can't be satisfied, user knows why
3. **No silent repetition** — Same recommendation requires justification
4. **Auditable** — Compliance status is logged in state

---

## 6. Execution Mode & Workflow

**File:** `graphs/workflow.py`

### LangGraph Workflow

```
                    ┌─────────────┐
                    │    START    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ SUPERVISOR  │◀──────────────────────────┐
                    │             │                           │
                    └──────┬──────┘                           │
                           │                                  │
           ┌───────────────┼───────────────┐                  │
           │               │               │                  │
           ▼               ▼               ▼                  │
    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
    │ Strategy │    │ Supplier │    │ Negotia- │              │
    │  Agent   │    │  Agent   │    │   tion   │              │
    │ (DTP-01) │    │(DTP-02/3)│    │ (DTP-04) │              │
    └────┬─────┘    └────┬─────┘    └────┬─────┘              │
         │               │               │                    │
         └───────────────┴───────────────┘                    │
                         │                                    │
                         ▼                                    │
                  ┌─────────────┐                              │
                  │  SUPERVISOR │──────────────────────────────┘
                  │  (Review)   │
                  └──────┬──────┘
                         │
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
     ┌─────────────┐          ┌─────────────┐
     │ WAIT_FOR_   │          │    END      │
     │   HUMAN     │          │             │
     └─────────────┘          └─────────────┘
```

### Execution Constraints in Workflow

When a workflow node calls an agent, it passes `execution_constraints`:

```python
# In workflow.py strategy_node
execution_constraints = state.get("execution_constraints")

recommendation = strategy_agent.recommend_strategy(
    case_summary,
    user_intent,
    execution_constraints=execution_constraints  # Binding constraints
)
```

The agent then injects constraints into its LLM prompt:

```python
# In strategy_agent.py
constraints_injection = execution_constraints.get_prompt_injection()

prompt = f"""You are a Strategy Agent...

{constraints_injection}

Your role:
- Synthesize information from retrieved data
- Explain tradeoffs between options
...
"""
```

---

## 7. Agent Architecture

### Rules > Retrieval > LLM Pattern

All agents follow a strict hierarchy:

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT EXECUTION FLOW                         │
│                                                                  │
│  1. RULES (Priority 1)                                           │
│     └─▶ Deterministic business rules applied FIRST               │
│     └─▶ If rule matches → return deterministic output (NO LLM)   │
│                                                                  │
│  2. EXECUTION CONSTRAINTS (Priority 2)                           │
│     └─▶ Binding user preferences from collaboration              │
│     └─▶ Injected into LLM prompt as hard requirements            │
│                                                                  │
│  3. RETRIEVAL (Priority 3)                                       │
│     └─▶ Retrieve data (contracts, performance, market)           │
│     └─▶ Retrieve from Vector Knowledge Layer                     │
│                                                                  │
│  4. LLM (Priority 4 - Summarization Only)                        │
│     └─▶ LLM reasons within constraints                           │
│     └─▶ LLM explains, summarizes, structures                     │
│     └─▶ LLM does NOT make decisions                              │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Summary

| Agent | DTP Stage | Primary Function | LLM Role |
|-------|-----------|------------------|----------|
| **StrategyAgent** | DTP-01 | Recommend sourcing strategy | Summarize tradeoffs |
| **SupplierEvaluationAgent** | DTP-02/03 | Score and shortlist suppliers | Explain differences |
| **RFxDraftAgent** | DTP-03 | Draft RFx documents | Fill templates |
| **NegotiationSupportAgent** | DTP-04 | Create negotiation plans | Identify leverage |
| **ContractSupportAgent** | DTP-05 | Extract contract terms | Structured extraction |
| **ImplementationAgent** | DTP-06 | Create rollout plans | Plan generation |
| **CaseClarifierAgent** | Any | Request clarification | Generate questions |
| **SignalInterpretationAgent** | Pre-DTP | Interpret sourcing signals | Explain signals |

---

## 8. Supervisor & Orchestration

**File:** `agents/supervisor.py`

### Supervisor Responsibilities

The Supervisor is the **only orchestrator** and is **fully deterministic** (no LLM calls):

1. **State Management** — Only Supervisor can update `CaseSummary`
2. **DTP Stage Transitions** — Only Supervisor can advance DTP stages
3. **Agent Routing** — Supervisor determines which agent runs next
4. **Human-in-the-Loop** — Supervisor determines when human approval is required
5. **Policy Enforcement** — Supervisor enforces policy constraints

### Routing Logic

```python
def determine_next_agent(dtp_stage, latest_output, policy_context):
    """
    Deterministic routing based on DTP stage and agent outputs.
    """
    # After Strategy → route to Supplier Evaluation
    if isinstance(latest_output, StrategyRecommendation):
        if latest_output.recommended_strategy in ["RFx", "Renegotiate"]:
            return "SupplierEvaluation"
    
    # After Supplier Shortlist → route to RFx or Negotiation
    if isinstance(latest_output, SupplierShortlist):
        if dtp_stage == "DTP-03":
            return "RFxDraft"
        elif dtp_stage == "DTP-04":
            return "NegotiationSupport"
    
    # ... more routing logic
```

### Human-in-the-Loop Decision

```python
def should_wait_for_human(latest_output, policy_context):
    """
    Determine if human approval is required.
    Based on:
    - Materiality thresholds
    - Policy requirements
    - Decision impact (HIGH/MEDIUM/LOW)
    """
    return rule_engine.should_require_human(
        dtp_stage, latest_output, policy_context
    )
```

---

## 9. Memory Architecture

### CaseMemory

**File:** `utils/case_memory.py`

Structured, bounded memory for case continuity:

```python
CaseMemory:
  case_id: str
  entries: List[MemoryEntry]  # Rolling, bounded to 20
  
  # Summarized state
  current_strategy: str
  current_supplier_choice: str
  human_decisions: List[str]
  key_user_intents: List[str]
  active_contradictions: List[str]
  
  # Collaboration tracking (Phase 3)
  collaboration_insights: List[str]
  user_preferences: Dict[str, Any]
  flagged_risks: List[str]
  key_decisions: List[str]
  intent_shifts: List[str]  # Audit trail
  
  # Counters
  total_agent_calls: int
  total_human_decisions: int
  total_collaboration_turns: int
```

### ExecutionConstraints

**File:** `utils/execution_constraints.py`

Binding constraints extracted from collaboration (see Section 5).

### Session State

Streamlit session state stores:

- `cases` — All case objects
- `chat_responses` — Chat history per case
- `case_memories` — CaseMemory per case
- `execution_constraints` — ExecutionConstraints per case
- `workflow_state` — Current workflow state

---

## 10. Data Flow Diagrams

### Complete User Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER MESSAGE                                    │
│                     "I don't mind disruption, what are the options?"        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INTENT CLASSIFIER                                   │
│                                                                             │
│   Pattern match: "what are the options" → COLLABORATIVE                     │
│   Confidence: 0.85                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONSTRAINT EXTRACTOR                                  │
│                                                                             │
│   Pattern match: "don't mind disruption" → disruption_tolerance = HIGH     │
│   Store in ExecutionConstraints                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       COLLABORATION ENGINE                                   │
│                                                                             │
│   1. Acknowledge constraint: "Got it — disruption is acceptable..."        │
│   2. Reference context from CaseMemory                                      │
│   3. Frame options (DTP-01 template)                                        │
│   4. Ask clarifying questions                                               │
│   5. Offer transition: "Want me to run the analysis?"                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESPONSE TO USER                                   │
│                                                                             │
│   "Got it — disruption is acceptable, so I'll include more aggressive       │
│   options in my analysis.                                                   │
│                                                                             │
│   At this stage, we're shaping the overall approach. There are typically    │
│   a few paths: renewing with the current supplier, renegotiating terms,     │
│   running a competitive process...                                          │
│                                                                             │
│   Before we proceed, I'd like to understand:                                │
│   - What's driving the urgency here?                                        │
│   - How much disruption are you comfortable with?                           │
│                                                                             │
│   💡 Once we've aligned, I can run the analysis. Want me to do that now?"   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Execution Flow with Constraints

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER MESSAGE                                    │
│                          "Yes, proceed with the analysis"                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INTENT CLASSIFIER                                   │
│                                                                             │
│   Pattern match: "proceed" → EXECUTION                                      │
│   Confidence: 0.90                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RECORD INTENT SHIFT                                   │
│                                                                             │
│   CaseMemory: COLLABORATIVE → EXECUTION (trigger: "proceed with analysis") │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        INITIALIZE WORKFLOW                                   │
│                                                                             │
│   workflow_state = {                                                        │
│       case_id, dtp_stage, user_intent,                                      │
│       execution_constraints: ExecutionConstraints  ◀── FROM SESSION STATE  │
│   }                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LANGGRAPH WORKFLOW                                  │
│                                                                             │
│   SUPERVISOR → STRATEGY AGENT                                               │
│                      │                                                      │
│                      ▼                                                      │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │  STRATEGY AGENT                                             │          │
│   │                                                             │          │
│   │  1. Apply rules (contract expiry, performance)              │          │
│   │  2. Inject execution_constraints into prompt:               │          │
│   │     "=== BINDING USER CONSTRAINTS ===                       │          │
│   │      • Disruption tolerance: HIGH                           │          │
│   │      Your recommendation MUST account for these."           │          │
│   │  3. LLM reasons within constraints                          │          │
│   │  4. Return StrategyRecommendation                           │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                      │                                                      │
│                      ▼                                                      │
│   SUPERVISOR reviews → determines next agent or WAIT_FOR_HUMAN              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Guardrails & Governance

### Governance Hierarchy

```
1. POLICIES & RULES (Highest Authority)
   └─▶ RuleEngine enforces business rules
   └─▶ PolicyLoader provides stage constraints
   └─▶ Rules ALWAYS override LLM output

2. EXECUTION CONSTRAINTS (User Authority)
   └─▶ Binding preferences from collaboration
   └─▶ Override default agent logic
   └─▶ Must be explained if cannot be satisfied

3. SUPERVISOR (Orchestration Authority)
   └─▶ Only entity that can change case state
   └─▶ Only entity that can advance DTP stages
   └─▶ Deterministic (no LLM)

4. AGENTS (No Authority)
   └─▶ Propose outputs only
   └─▶ Cannot change state directly
   └─▶ LLM used for summarization/explanation only
```

### Token Guardrails

- **Per-case budget:** 3,000 tokens maximum
- **Tiered models:** Tier 1 (gpt-4o-mini) vs Tier 2 (gpt-4o)
- **Budget tracking:** Tokens tracked across all agent calls
- **Fallback:** When budget exceeded, deterministic fallback output

### Agent Validation

```python
# All agent outputs are validated
validation_result = validate_agent_output(
    agent_name="Strategy",
    output=recommendation,
    dtp_stage="DTP-01",
    case_summary=case_summary
)

if not validation_result.is_valid:
    # Log violation, potentially reject output
```

### Contradiction Detection

```python
# Detect contradictions between agent outputs
contradictions = detect_contradictions(
    current_output=recommendation,
    output_history=state.get("output_history", [])
)

if contradictions:
    # Flag for human review
```

---

## 12. File Reference

### Core Application

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI, chat interface, workflow integration |
| `graphs/workflow.py` | LangGraph workflow definition and execution |

### Agents

| File | Purpose |
|------|---------|
| `agents/base_agent.py` | Base class for all agents |
| `agents/supervisor.py` | Deterministic orchestration agent |
| `agents/strategy_agent.py` | Strategy recommendation (DTP-01) |
| `agents/supplier_agent.py` | Supplier evaluation (DTP-02/03) |
| `agents/negotiation_agent.py` | Negotiation planning (DTP-04) |
| `agents/rfx_draft_agent.py` | RFx document drafting (DTP-03) |
| `agents/contract_support_agent.py` | Contract term extraction (DTP-05) |
| `agents/implementation_agent.py` | Implementation planning (DTP-06) |
| `agents/signal_agent.py` | Signal interpretation |
| `agents/case_clarifier_agent.py` | Clarification requests |

### Collaboration System (Phase 3)

| File | Purpose |
|------|---------|
| `utils/intent_classifier.py` | Rule-based intent classification |
| `utils/collaboration_engine.py` | Generate collaborative responses |
| `utils/collaboration_templates.py` | DTP-specific templates and questions |
| `utils/execution_constraints.py` | Binding constraint model |
| `utils/constraint_extractor.py` | Deterministic constraint extraction |
| `utils/constraint_compliance.py` | Constraint compliance checker (enforcement invariant) |

### State & Memory

| File | Purpose |
|------|---------|
| `utils/state.py` | PipelineState definition |
| `utils/case_memory.py` | CaseMemory for narrative context |
| `utils/schemas.py` | Pydantic schemas for all data types |

### Rules & Policy

| File | Purpose |
|------|---------|
| `utils/rules.py` | RuleEngine for business rules |
| `utils/policy_loader.py` | PolicyLoader for DTP constraints |
| `utils/dtp_stages.py` | DTP stage definitions |

### Utilities

| File | Purpose |
|------|---------|
| `utils/data_loader.py` | Load data from JSON files |
| `utils/caching.py` | Agent output caching |
| `utils/token_accounting.py` | Token budget tracking |
| `utils/agent_validator.py` | Agent output validation |
| `utils/contradiction_detector.py` | Detect output contradictions |
| `utils/knowledge_layer.py` | Vector Knowledge Layer interface |

---

## Summary

This system implements a **human-like collaborative assistant** that:

1. **Listens** — Classifies intent and enters discussion mode by default
2. **Extracts** — Captures binding constraints from user statements
3. **Acknowledges** — Immediately confirms what it heard (builds trust)
4. **Discusses** — Frames options, asks questions, surfaces tradeoffs
5. **Executes** — Only when explicitly requested, with constraints enforced
6. **Respects** — User preferences override default logic

The result is an AI system that feels like a thoughtful human assistant, not a transactional command executor.

---

**END OF SYSTEM ARCHITECTURE DOCUMENT**
