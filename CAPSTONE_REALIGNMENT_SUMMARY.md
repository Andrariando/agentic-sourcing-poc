# Capstone Design Realignment Summary

**Date:** 2025-01-12  
**Status:** ✅ Complete - All agents aligned with Table 3 and capstone requirements

---

## Overview

The agentic sourcing system has been realigned to **exactly match** the capstone design specifications from Table 3, while maintaining the core architecture principles:
- **Orchestration-first**: SupervisorAgent is the only orchestrator
- **Governance-first**: PolicyLoader + RuleEngine enforce constraints
- **Conversational UX**: GPT-like experience with Supervisor as narrator
- **Deterministic control**: LLMs reason within bounded constraints; Supervisor decides

---

## Agent Realignment (Table 3 Compliance)

### ✅ 1. Supervisor Agent (DTP 01-06) - NO CHANGES

**Status:** Already aligned with Table 3

**Responsibilities:**
- Directs workflow, validates inputs, selects sourcing pathway
- Orchestrates downstream agents
- Analytical Logic: Heuristic routing rules; context memory; retrieval of procedural references

**Key Points:**
- Deterministic (no LLM calls)
- Only entity that can update `CaseSummary` and advance `dtp_stage`
- Uses `RuleEngine` and `PolicyLoader` for all decisions

---

### ✅ 2. Sourcing Signal Layer (Pre-DTP / DTP-01) - NO CHANGES

**Status:** Already implemented as deterministic SignalAggregator (not an agent)

**Responsibilities:**
- Scans contract metadata, spend patterns, supplier performance
- Emits `CaseTrigger` objects only (signals, not decisions)
- Analytical Logic: Signal retrieval; structured summarization; relevance filters

**Key Points:**
- Does NOT renew, renegotiate, terminate, or award contracts
- Only initiates cases at DTP-01 (system-initiated case creation)
- Market data used only for urgency/context, not for decisions

---

### ✅ 3. Strategy Agent (DTP-01) - REALIGNED

**Status:** Enhanced to match capstone requirements

**Changes Made:**
- ✅ Already follows Rules > Retrieval > LLM pattern
- ✅ Enhanced prompt to clarify: LLM reasons within `allowed_strategies` constraints
- ✅ Added Vector Knowledge Layer integration (category strategy context)
- ✅ LLM synthesizes information, explains tradeoffs, structures options
- ✅ LLM does NOT have decision authority (Supervisor enforces policy)

**Current Implementation:**
- Step 1: Check cache
- Step 2: Retrieve data (contract, performance, market, category)
- Step 3: Apply deterministic rules FIRST (`RuleEngine.apply_strategy_rules()`)
- Step 4: If rule matches → return deterministic output (zero LLM tokens)
- Step 5: If no rule → LLM reasons within `allowed_strategies` to explain tradeoffs

**LLM Reasoning (Bounded):**
- Synthesizes retrieved information
- Explains tradeoffs between strategy options
- Structures options within policy constraints
- Does NOT override rules or make autonomous decisions

---

### ✅ 4. Supplier Scoring Agent (DTP-02/03) - REALIGNED

**Status:** Completely realigned from "SupplierEvaluationAgent" to match Table 3

**Previous Name:** SupplierEvaluationAgent  
**New Alignment:** Supplier Scoring Agent (Table 3: DTP-02/03)

**Key Changes:**
1. ✅ Added `RuleEngine` integration for deterministic eligibility checks
2. ✅ Deterministic filtering: applies rule-based eligibility (must-haves, performance threshold)
3. ✅ Performance normalization (simple normalization for POC; ML in production)
4. ✅ LLM reasons to: explain differences, summarize risks, structure comparisons
5. ✅ Does NOT select winners - that's a human decision
6. ✅ Prompt updated to clarify: scoring and comparison only, no winner selection

**Implementation Pattern:**
```
STEP 1: Apply deterministic eligibility checks (RuleEngine)
  - Filters out suppliers below performance threshold
  - Filters out suppliers missing must-have requirements
STEP 2: Normalize performance data (0-10 scoring)
STEP 3: LLM reasons to score, explain differences, summarize risks
STEP 4: Return structured shortlist (top_choice_supplier_id is optional, non-binding)
```

---

### ✅ 5. RFx Draft Agent (DTP-03) - CREATED

**Status:** New agent created per Table 3

**File:** `agents/rfx_draft_agent.py`

**Responsibilities:**
- Assembles RFx draft using templates, past examples, and structured generation
- Analytical Logic: Template assembly; retrieval of past RFx materials; controlled narrative generation; rule-based completeness checks

**Implementation:**
- ✅ Retrieves RFx templates from Vector Knowledge Layer (`get_vector_context(..., topic="rfq_template")`)
- ✅ LLM fills template structure (Overview, Requirements, Evaluation Criteria, Timeline, Terms & Conditions)
- ✅ LLM adapts language to category context
- ✅ LLM explains intent and adaptations
- ✅ Rule-based completeness checks before returning output
- ✅ Does NOT invent commercial terms (requires human/legal approval)

**Output Schema:** `RFxDraft`
- `rfx_sections`: Dict of filled template sections
- `completeness_check`: Rule-based validation results
- `template_source`: Which template was used
- `explanation`: LLM explanation of intent

---

### ✅ 6. Negotiation Support Agent (DTP-04) - REALIGNED

**Status:** Enhanced to match Table 3

**Changes Made:**
- ✅ Added Vector Knowledge Layer integration (negotiation playbook)
- ✅ Prompt updated to clarify: comparative and advisory only
- ✅ LLM reasons to: identify leverage, explain gaps, suggest scenarios
- ✅ NO award decisions (human makes final choice)
- ✅ NO policy enforcement (Supervisor enforces policy)

**Current Implementation:**
- Retrieves negotiation playbook from Vector Knowledge Layer
- LLM uses benchmarks and heuristics as context (not binding)
- LLM identifies leverage points and explains bid gaps
- LLM suggests negotiation scenarios
- Does NOT make award decisions or enforce policy

---

### ✅ 7. Contract Support Agent (DTP-04/05) - CREATED

**Status:** New agent created per Table 3

**File:** `agents/contract_support_agent.py`

**Responsibilities:**
- Extracts key award terms and prepares structured inputs for contracting
- Analytical Logic: Template-guided extraction; rule-based contract field validation; knowledge graph grounding for term alignment

**Implementation:**
- ✅ Retrieves contract clause library from Vector Knowledge Layer
- ✅ LLM extracts terms using template structure (Service Levels, Payment Terms, Termination, Compliance)
- ✅ LLM explains term mappings to clause library
- ✅ LLM flags inconsistencies for human review
- ✅ Rule-based field validation (required fields check)
- ✅ Does NOT create new clauses or modify terms

**Output Schema:** `ContractExtraction`
- `extracted_terms`: Template-guided extracted terms
- `validation_results`: Rule-based field validation
- `mapping_explanations`: LLM explanations of term mappings
- `inconsistencies`: Flagged inconsistencies for human review

---

### ✅ 8. Implementation Agent (DTP-05/06) - CREATED

**Status:** New agent created per Table 3

**File:** `agents/implementation_agent.py`

**Responsibilities:**
- Produces rollout steps and early post-award indicators
- Analytical Logic: Deterministic calculations; retrieval of rollout playbooks; structured reporting templates

**Implementation:**
- ✅ Deterministic rollout calculations (`_calculate_projected_savings()`, `_determine_rollout_steps()`)
- ✅ Retrieves rollout playbook from Vector Knowledge Layer
- ✅ LLM reasons to: explain impacts, summarize KPIs
- ✅ No strategic reasoning - only explanation of deterministic outputs
- ✅ Structured reporting based on playbook template

**Output Schema:** `ImplementationPlan`
- `rollout_steps`: Deterministic rollout steps (from playbook)
- `projected_savings`: Deterministic calculation (5% of annual value for POC)
- `service_impacts`: LLM-structured impact summary
- `kpi_summary`: LLM-structured KPI explanation
- `explanation`: LLM explanation of impacts

---

### ✅ 9. Case Clarifier Agent (Any stage) - NO CHANGES

**Status:** Already aligned (LLM-only by design, appropriate)

**Responsibilities:**
- Generates targeted, actionable clarification questions
- NEVER advances workflow (Supervisor decides routing)

---

## System Layers (Explicitly Declared)

### ✅ 1. Data Lake (Foundational, Non-LLM)

**Current Implementation:**
- `utils/data_loader.py` provides read-only access to:
  - `contracts.json` - Contract metadata
  - `suppliers.json` - Supplier master data
  - `performance.json` - Performance metrics
  - `market.json` - Spend history and benchmarks
  - `categories.json`, `requirements.json` - Category context

**Used For:**
- Deterministic logic (RuleEngine)
- Signal aggregation (SignalAggregator)
- Agent context retrieval

**No reasoning happens here** - pure data access.

---

### ✅ 2. Vector Knowledge Layer (RAG, Read-Only)

**File:** `utils/knowledge_layer.py`

**Current Implementation:**
- Conceptual abstraction with `get_vector_context()` function
- Returns structured context dictionaries for:
  - `"dtp_procedure"` - DTP procedures
  - `"category_strategy"` - Category strategies
  - `"rfq_template"` - RFx templates
  - `"negotiation_playbook"` - Negotiation heuristics
  - `"contract_clauses"` - Contract clause library
  - `"rollout_playbook"` - Implementation playbooks
  - `"historical_cases"` - Historical sourcing cases

**Wired Into Agents:**
- ✅ Strategy Agent: Retrieves category strategy context
- ✅ RFx Draft Agent: Retrieves RFx templates
- ✅ Negotiation Support Agent: Retrieves negotiation playbook
- ✅ Contract Support Agent: Retrieves contract clause library
- ✅ Implementation Agent: Retrieves rollout playbook

**Purpose:**
- Grounding (reduces hallucination)
- Consistency (template-driven generation)
- Never overrides rules, policies, or Supervisor decisions

---

### ✅ 3. Conversational Memory (Case-Scoped)

**Current Implementation:**
- `app.py`: `st.session_state.chat_responses[case_id]` stores case-scoped chat history
- Append-only, auditable within Streamlit session
- No cross-case memory leakage (strictly keyed by `case_id`)

**Governance:**
- Agents do NOT reason over raw chat history
- Supervisor maintains rolling summary via `CaseSummary.summary_text`, `key_findings`, `recommended_action`
- Chat layer narrates what Supervisor has already determined

---

## Orchestration Logic (Supervisor-Centric)

### ✅ Supervisor Routing (Enhanced)

**File:** `agents/supervisor.py` - `determine_next_agent()`

**Table 3-Aligned Routing:**
- DTP-01 → Strategy Agent
- DTP-02 → Supplier Scoring Agent (SupplierEvaluation)
- DTP-03 → RFx Draft Agent OR Supplier Scoring Agent (depending on state)
- DTP-04 → Negotiation Support Agent OR Contract Support Agent (depending on state)
- DTP-05 → Contract Support Agent OR Implementation Agent (depending on state)
- DTP-06 → Implementation Agent

**Key Logic:**
- Routes based on `dtp_stage` and `latest_agent_output`
- Checks policy constraints via `PolicyLoader`
- Uses confidence-aware routing (routes to CaseClarifier if needed)
- Checks agent capabilities via `AGENT_CAPABILITIES` registry

---

## GPT-Like Chat Experience (UX Layer)

### ✅ Conversational Response Structure

**File:** `app.py` - `build_strategy_chat_response()`, status responses, etc.

**Pattern (4-Step Structure):**
1. **What was evaluated** (grounded facts)
2. **What is allowed** (policy constraints)
3. **What is suggested** (non-binding)
4. **What the human can do next** (explicit choices)

**Example Response Structure:**
```
Here's the latest update on CASE-0001 from the sourcing workflow:
[What was evaluated] I've completed a strategy analysis and recommend RFx.
[What is allowed] Based on policy constraints, RFx is allowed for this renewal case.
[What is suggested] The main reasons are: contract expiring in 30 days, performance declining.
[What you can do] Would you like to approve this recommendation or make changes?
```

**Agent-Specific Responses:**
- ✅ Strategy: Explains tradeoffs, structures options
- ✅ Supplier Scoring: Explains differences, summarizes risks (does NOT select winner)
- ✅ RFx Draft: Explains template usage, completeness
- ✅ Negotiation: Highlights leverage, explains gaps (NO award decision)
- ✅ Contract: Explains extractions, flags inconsistencies
- ✅ Implementation: Explains impacts, summarizes KPIs
- ✅ Clarifier: Natural follow-up questions (not errors)

---

## Core Philosophy Compliance

### ✅ LLMs ARE Allowed to Reason

**Confirmed in All Agents:**
- ✅ Synthesize information (Strategy, Supplier Scoring)
- ✅ Explain tradeoffs (Strategy, Negotiation)
- ✅ Structure options (Strategy, Supplier Scoring)
- ✅ Draft content (RFx Draft, Contract Support)
- ✅ Answer questions naturally in chat (all agents via Supervisor narration)

### ✅ LLMs DO NOT Have Decision Authority

**Enforced in Architecture:**
- ✅ Agents cannot advance DTP stages (only Supervisor can)
- ✅ Agents cannot enforce policy (PolicyLoader + RuleEngine do this)
- ✅ Agents cannot execute sourcing actions (human approval required)
- ✅ Agents cannot bypass human approval (WAIT_FOR_HUMAN node gates all decisions)

**Example:**
- Supplier Scoring Agent provides `top_choice_supplier_id` as **optional, non-binding**
- Human makes final choice via Supervisor approval
- RFx Draft Agent fills template but does NOT create binding commercial terms
- Contract Support Agent extracts terms but does NOT execute contracts

### ✅ Decision Authority Lives In

**Confirmed:**
- ✅ SupervisorAgent: Only orchestrator, owns state transitions
- ✅ PolicyLoader: Loads policy constraints (e.g., renewal strategy constraints)
- ✅ RuleEngine: Applies deterministic rules (e.g., eligibility checks, strategy rules)
- ✅ WAIT_FOR_HUMAN: Gates all human-in-the-loop decisions

**Rules constrain the decision space. LLMs reason *within* that constrained space. The Supervisor decides what happens next.**

---

## Files Modified/Created

### New Files:
- `agents/rfx_draft_agent.py` - RFx Draft Agent (Table 3: DTP-03)
- `agents/contract_support_agent.py` - Contract Support Agent (Table 3: DTP-04/05)
- `agents/implementation_agent.py` - Implementation Agent (Table 3: DTP-05/06)

### Modified Files:
- `agents/supplier_agent.py` - Realigned to Supplier Scoring Agent (Table 3: DTP-02/03)
- `agents/strategy_agent.py` - Enhanced with Vector Knowledge Layer, bounded reasoning prompts
- `agents/negotiation_agent.py` - Enhanced with Vector Knowledge Layer, comparative/advisory prompts
- `agents/supervisor.py` - Updated routing logic and capability registry
- `utils/schemas.py` - Added RFxDraft, ContractExtraction, ImplementationPlan schemas
- `utils/state.py` - Updated PipelineState to include new output types
- `utils/knowledge_layer.py` - Enhanced with actual template/playbook content
- `graphs/workflow.py` - Added new nodes, updated routing
- `app.py` - Added conversational responses for new agent outputs

---

## Testing Checklist

### ✅ Architecture Compliance:
- [x] Supervisor is only orchestrator
- [x] All agents route back to Supervisor
- [x] WAIT_FOR_HUMAN gates human decisions
- [x] PolicyLoader enforces constraints
- [x] RuleEngine applies deterministic rules

### ✅ Table 3 Compliance:
- [x] All 7 functional agents match Table 3 specifications
- [x] DTP stage alignment correct
- [x] Analytical logic patterns match Table 3
- [x] LLM reasoning is bounded and non-authoritative

### ✅ Conversational UX:
- [x] Supervisor narrates workflow decisions
- [x] Responses follow 4-step structure (evaluated/allowed/suggested/next steps)
- [x] CaseClarifier questions feel natural
- [x] WAIT_FOR_HUMAN is conversational

---

## Summary

The system now **exactly matches** the capstone design:
- ✅ All 7 functional agents from Table 3 are implemented and aligned
- ✅ System layers explicitly declared (Data Lake, Vector Knowledge, Conversational Memory)
- ✅ Supervisor-centric orchestration maintained
- ✅ GPT-like conversational experience with governance-first control
- ✅ LLMs reason within bounded constraints; Supervisor + policies decide

**The chatbot never decides what happens next; it only explains what the Supervisor + policies have already determined is allowed.**

---

**END OF REALIGNMENT SUMMARY**

