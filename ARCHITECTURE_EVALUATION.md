# Agentic AI System Architecture Evaluation & Refactoring Plan

**Date:** 2025-01-12  
**Reviewer:** Senior AI Systems Architect  
**System:** Procurement Sourcing Agentic AI POC

---

## 1. HIGH-LEVEL DIAGNOSIS

### Critical Violations of Agentic Design Principles

#### 1.1 Chatbot Behavior Instead of Workflow
**Location:** `app.py` lines 847-1032, 1222-1301

**Problem:**
- Functions `generate_status_response()`, `generate_recommendation_response()`, `build_strategy_chat_response()` create conversational, free-form responses
- System treats user queries as chat messages rather than structured workflow inputs
- Chat interface (`run_copilot()`) bypasses explicit decision points
- Status queries return conversational text instead of structured state

**Impact:** System behaves like a chatbot assistant, not a decision-support workflow system.

**Evidence:**
```python
# app.py:873-920 - Conversational status generation
def generate_status_response(case: Case) -> str:
    response_parts.append(f"Here's the latest update on **{case.case_id}**:")
    # ... conversational language, not structured output
```

#### 1.2 LLM-First Architecture (Violates Rules > LLM Principle)
**Location:** All agent implementations (`agents/strategy_agent.py`, `agents/supplier_agent.py`, etc.)

**Problem:**
- Agents call LLMs immediately without checking deterministic rules first
- Policy constraints exist in prompts (e.g., "If contract expires in <= 60 days...") but are not enforced as code
- No rule engine layer between input validation and LLM calls
- LLMs infer policy instead of applying encoded rules

**Impact:** System cannot guarantee deterministic behavior. Same inputs may produce different outputs.

**Evidence:**
```python
# agents/strategy_agent.py:54-101
# Prompt includes policy rules as guidance, not enforcement:
prompt = f"""...
For predictable outputs:
- If contract expires in <= 60 days AND performance is declining/stable-low: recommend "RFx"
"""
# This should be a deterministic rule checked BEFORE LLM call
```

#### 1.3 Missing Rule Enforcement Layer
**Location:** No dedicated rule engine exists

**Problem:**
- `build_policy_context()` in `app.py:105-132` creates policy metadata but doesn't enforce it
- No deterministic validation before agent execution
- DTP stage transitions not validated against policy rules
- No guardrails preventing invalid state transitions

**Impact:** System cannot enforce enterprise policy constraints deterministically.

#### 1.4 Implicit Decision Logic
**Location:** `agents/supervisor.py:104-111`

**Problem:**
- `should_wait_for_human()` always returns `True` for any output
- No materiality assessment
- No policy-based decision points
- Human-in-the-loop triggered universally, not selectively

**Impact:** Every agent output requires human approval, defeating automation benefits.

**Evidence:**
```python
# agents/supervisor.py:104-111
def should_wait_for_human(self, dtp_stage: str, latest_output: Any, policy_context) -> bool:
    if latest_output:
        return True  # Always requires human approval - too simplistic
    return False
```

#### 1.5 Missing Agents
**Location:** Only 4 agents exist vs. 7 required

**Missing Agents:**
- Market Intelligence Agent (retrieval + summarization)
- Supplier Scoring Agent (deterministic scoring + ML normalization)
- RFx Draft Agent (template-driven generation)
- Contract Support Agent (structured extraction + validation)
- Implementation Agent (deterministic rollout + reporting)

**Existing Agents:**
- Strategy Agent (exists but LLM-first)
- Supplier Evaluation Agent (exists but LLM-first)
- Negotiation Support Agent (exists but LLM-first)
- Signal Interpretation Agent (exists but LLM-first)

#### 1.6 State Management Issues
**Location:** `graphs/workflow.py`, `utils/state.py`

**Problem:**
- State transitions not explicitly validated
- No guardrails preventing invalid DTP stage jumps
- Human decisions not properly tracked in state
- Override events not logged with full traceability

---

## 2. ARCHITECTURE MISMATCHES VS INTENDED DESIGN

### 2.1 Decision Logic Hierarchy Violation

**Intended:** Rules > Analytics > Retrieval > LLM Narration  
**Current:** LLM > (implicit rules in prompts)

**Required Fix:**
1. Create explicit rule engine (`utils/rules.py`)
2. Add deterministic validation layer before LLM calls
3. Move policy rules from prompts to code
4. LLMs only used for narration/summarization after rules applied

### 2.2 Agent Responsibility Contamination

**Intended:** Each agent has single, bounded responsibility  
**Current:** Agents perform multiple functions (retrieval + analysis + decision)

**Example - Strategy Agent:**
- Should: Apply rules → Retrieve data → Summarize
- Currently: LLM analyzes everything and makes decisions

**Required Fix:**
- Separate rule application from LLM calls
- Agents retrieve data deterministically
- LLMs only summarize retrieved data

### 2.3 Human-in-the-Loop Design Violation

**Intended:** Explicit decision points with Approve/Edit/Reject  
**Current:** Conversational approval via chat parsing

**Problem:**
- `parse_hil_decision()` in `app.py:49-102` uses keyword matching
- No structured decision UI
- Human edits not properly tracked
- Override events not logged

**Required Fix:**
- Structured decision points in workflow
- Explicit Approve/Edit/Reject actions
- Full traceability of human decisions

### 2.4 Traceability Gaps

**Intended:** Every output attributable to inputs, rules, data, agent  
**Current:** Partial traceability (activity logs exist but incomplete)

**Missing:**
- Rule execution logs (which rules fired)
- Data retrieval logs (what data was used)
- Decision rationale (why this output)
- Override tracking (what human changed)

---

## 3. PROPOSED CORRECTED AGENTIC ARCHITECTURE

### 3.1 Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT                          │
│  • Owns state (case_id, dtp_stage, inputs, outputs)         │
│  • Enforces DTP order (explicit transitions)                │
│  • Validates inputs (deterministic checks)                    │
│  • Routes tasks (agent allocation)                           │
│  • Logs overrides (human decision tracking)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐
│   RULE ENGINE │ │   RETRIEVAL  │ │   ANALYTICS  │
│   (Priority 1)│ │   (Priority 4)│ │  (Priority 3)│
│               │ │               │ │              │
│ • Policy rules│ │ • Data loader│ │ • Scoring   │
│ • DTP checks  │ │ • Cache check│ │ • Normalize  │
│ • Validation │ │ • Summarize  │ │ • Anomaly    │
└───────┬───────┘ └───────┬───────┘ └──────┬───────┘
        │                 │                │
        └─────────────────┼────────────────┘
                         │
                         ▼
                ┌────────────────┐
                │  LLM NARRATION │
                │  (Priority 5)  │
                │                │
                │ • Summarize    │
                │ • Explain      │
                │ • NO DECISIONS  │
                └────────────────┘
```

### 3.2 Agent Responsibilities (Corrected)

| Agent | Responsibility | Rules Applied | LLM Used For |
|-------|---------------|----------------|--------------|
| **Supervisor** | State management, routing, validation | DTP transitions, policy checks | None (deterministic) |
| **Market Intelligence** | Data retrieval + grounded summarization | None | Summarization only |
| **Supplier Scoring** | Deterministic scoring + ML normalization | Scoring rules, thresholds | None (deterministic) |
| **RFx Draft** | Template-driven generation | Template rules, constraints | Filling templates |
| **Negotiation Support** | Heuristics + anomaly detection | Negotiation rules | NO awards |
| **Contract Support** | Structured extraction + validation | Contract rules, validation | Extraction only |
| **Implementation** | Deterministic rollout + reporting | Rollout rules | Reporting only |
| **Strategy** | Rule application + data retrieval + summarization | Strategy rules (contract expiry, performance) | Summarization only |

### 3.3 Decision Logic Flow (Corrected)

```
1. INPUT RECEIVED
   ↓
2. RULE ENGINE CHECK (Deterministic)
   ├─ Policy rules applied
   ├─ DTP stage validation
   ├─ Input validation
   └─ If rule violation → REJECT (no LLM call)
   ↓
3. DETERMINISTIC VALIDATION (Priority 2)
   ├─ Schema validation
   ├─ Required fields check
   └─ If invalid → REJECT (no LLM call)
   ↓
4. LIGHTWEIGHT ANALYTICS (Priority 3)
   ├─ Scoring (deterministic)
   ├─ Normalization (ML-based but deterministic)
   └─ Anomaly detection (heuristic)
   ↓
5. RETRIEVAL-AUGMENTED CONTEXT (Priority 4)
   ├─ Data retrieval (deterministic)
   ├─ Cache check (deterministic)
   └─ Context assembly
   ↓
6. LLM NARRATION/SUMMARIZATION (Priority 5)
   ├─ Summarize retrieved data
   ├─ Explain reasoning
   └─ NO DECISIONS MADE
   ↓
7. OUTPUT VALIDATION
   ├─ Schema check
   ├─ Rule compliance check
   └─ If invalid → REJECT
   ↓
8. HUMAN REVIEW (if required by policy)
   ├─ Approve → Continue
   ├─ Edit → Apply edits → Continue
   └─ Reject → Terminate
```

---

## 4. CONCRETE REFACTORING RECOMMENDATIONS

### 4.1 Create Rule Engine (`utils/rules.py`)

**Purpose:** Encode all policy rules as deterministic functions

**Structure:**
```python
class RuleEngine:
    def apply_strategy_rules(self, contract, performance, market) -> Optional[str]:
        """Apply deterministic strategy rules. Returns strategy if rule matches, None otherwise."""
        # Rule 1: Contract expiry <= 60 days + declining performance → RFx
        if contract.expiry_days <= 60 and performance.trend == "declining":
            return "RFx"
        # Rule 2: Contract expiry > 180 days + stable-good performance → Renew
        if contract.expiry_days > 180 and performance.trend == "stable-good":
            return "Renew"
        # ... more rules
        return None  # No rule matched, proceed to LLM
    
    def validate_dtp_transition(self, current_stage, next_stage, policy_context) -> bool:
        """Validate DTP stage transition against policy."""
        allowed = policy_context.allowed_actions
        return next_stage in allowed
    
    def should_require_human(self, output, dtp_stage, policy_context) -> bool:
        """Determine if human approval required based on materiality and policy."""
        # Check policy context
        if dtp_stage in policy_context.human_required_for:
            return True
        # Check materiality (decision_impact)
        if hasattr(output, 'decision_impact'):
            return output.decision_impact == DecisionImpact.HIGH
        return False
```

### 4.2 Refactor Strategy Agent

**Before:** LLM makes strategy decision  
**After:** Rules → Retrieval → LLM summarization

```python
class StrategyAgent(BaseAgent):
    def recommend_strategy(self, case_summary, user_intent, use_cache=True):
        # STEP 1: Apply deterministic rules
        rule_engine = RuleEngine()
        contract = get_contract(case_summary.contract_id) if case_summary.contract_id else None
        performance = get_performance(case_summary.supplier_id) if case_summary.supplier_id else None
        
        # Check rules FIRST
        rule_based_strategy = rule_engine.apply_strategy_rules(contract, performance, None)
        if rule_based_strategy:
            # Rule matched - return deterministic output (no LLM)
            return self._create_rule_based_recommendation(
                case_summary, rule_based_strategy, contract, performance
            )
        
        # STEP 2: No rule matched - retrieve data
        market = get_market_data(case_summary.category_id)
        category = get_category(case_summary.category_id)
        
        # STEP 3: LLM only for summarization (not decision)
        # Prompt changed: "Summarize the following data and explain the context..."
        # NOT "Recommend a strategy..."
```

### 4.3 Refactor Supervisor Agent

**Changes:**
1. Add explicit state validation
2. Add DTP transition validation
3. Improve `should_wait_for_human()` with materiality checks
4. Add override logging

```python
class SupervisorAgent:
    def validate_state(self, state: PipelineState) -> tuple[bool, Optional[str]]:
        """Validate state completeness and correctness."""
        # Check required fields
        if not state.get("case_id"):
            return False, "Missing case_id"
        if not state.get("dtp_stage"):
            return False, "Missing dtp_stage"
        # Check DTP stage validity
        if state["dtp_stage"] not in ["DTP-01", "DTP-02", ..., "DTP-06"]:
            return False, f"Invalid DTP stage: {state['dtp_stage']}"
        return True, None
    
    def should_wait_for_human(self, dtp_stage, latest_output, policy_context) -> bool:
        """Improved: Check policy + materiality."""
        # Check policy context first
        if dtp_stage in _policy_list(policy_context, "human_required_for"):
            return True
        
        # Check materiality
        if latest_output and hasattr(latest_output, 'decision_impact'):
            if latest_output.decision_impact == DecisionImpact.HIGH:
                return True
        
        # Check DTP stage requirements
        if dtp_stage in ["DTP-04", "DTP-06"]:  # Negotiation and Execution require human
            return True
        
        return False
```

### 4.4 Refactor Workflow Graph

**Changes:**
1. Add explicit validation nodes
2. Add rule application nodes
3. Separate retrieval from LLM calls
4. Add human decision nodes with explicit Approve/Edit/Reject

```python
def create_workflow_graph():
    workflow = StateGraph(PipelineState)
    
    # Add validation node
    workflow.add_node("validate_input", validate_input_node)
    
    # Add rule application node
    workflow.add_node("apply_rules", apply_rules_node)
    
    # Add retrieval node
    workflow.add_node("retrieve_data", retrieve_data_node)
    
    # Add agent nodes (now LLM-only for summarization)
    workflow.add_node("strategy", strategy_node)
    
    # Add human decision node
    workflow.add_node("human_decision", human_decision_node)
    
    # Flow: validate → apply_rules → retrieve_data → agent → supervisor → human_decision (if needed)
```

### 4.5 Refactor App.py (Remove Chatbot Behavior)

**Changes:**
1. Remove conversational response generators
2. Replace with structured output display
3. Add explicit decision UI (Approve/Edit/Reject buttons)
4. Remove chat parsing logic

```python
# REMOVE:
# - generate_status_response()
# - generate_recommendation_response()
# - build_strategy_chat_response()
# - parse_hil_decision()

# REPLACE WITH:
def display_structured_output(case: Case):
    """Display structured agent output with explicit decision buttons."""
    if case.latest_agent_output:
        # Display structured output
        st.json(case.latest_agent_output.model_dump())
        
        # Explicit decision buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✅ Approve", key="approve"):
                inject_human_decision(case.case_id, "Approve")
        with col2:
            if st.button("✏️ Edit", key="edit"):
                show_edit_form(case)
        with col3:
            if st.button("❌ Reject", key="reject"):
                show_reject_form(case)
```

---

## 5. REWRITTEN EXAMPLE PROMPTS

### 5.1 Supervisor Agent Prompt (Deterministic - No LLM)

**Current:** Supervisor uses LLM implicitly  
**Corrected:** Supervisor is pure logic (no LLM)

```python
# No prompt needed - Supervisor is deterministic
class SupervisorAgent:
    def determine_next_agent(self, dtp_stage, latest_output, policy_context):
        # Pure logic, no LLM
        allowed_actions = policy_context.allowed_actions
        # ... deterministic routing logic
```

### 5.2 Strategy Agent Prompt (Bounded, Role-Specific, Grounded)

**Before:**
```
You are a Strategy Agent...
Analyze this case and recommend a sourcing strategy...
```

**After:**
```
You are a Strategy Agent for dynamic sourcing pipelines (DTP-01).

Your role is LIMITED to:
1. Summarizing the retrieved contract, performance, and market data
2. Explaining the context and implications
3. Providing narrative rationale for the strategy determined by rules

IMPORTANT CONSTRAINTS:
- You do NOT make strategy decisions (rules have already determined the strategy)
- You do NOT override policy rules
- You do NOT invent criteria

Retrieved Data Summary:
[Contract data, performance data, market data]

Rule-Determined Strategy: {rule_based_strategy}

Your task: Provide a clear, grounded summary explaining:
1. What the data shows
2. Why the rule-determined strategy fits this case
3. Key risks and opportunities to consider

Respond with JSON matching StrategyRecommendation schema, but note:
- recommended_strategy MUST match the rule-determined strategy
- rationale should explain the data, not invent new criteria
```

---

## 6. TESTING & VALIDATION CHECKLIST

### 6.1 Determinism Testing

**Test:** Same inputs produce same outputs across runs

**Method:**
1. Create test case with fixed inputs
2. Run workflow 10 times
3. Verify outputs are identical (except timestamps)
4. Verify rule application is consistent

**Expected:** 100% consistency (no LLM variance in decisions)

### 6.2 Override Tracking

**Test:** Human decisions and edits are fully traceable

**Method:**
1. Approve a recommendation
2. Edit a recommendation
3. Reject a recommendation
4. Verify all actions logged with:
   - Timestamp
   - User ID
   - Original output
   - Edited fields (if any)
   - Reason (if rejection)

**Expected:** Complete audit trail

### 6.3 Agent Stability

**Test:** Agents perform only their intended function

**Method:**
1. For each agent, verify:
   - Only retrieves data it's responsible for
   - Only applies rules it's responsible for
   - LLM only used for summarization (not decisions)
2. Check activity logs for cross-contamination

**Expected:** No agent performs another agent's function

### 6.4 Human-AI Collaboration Metrics

**Metrics to Track:**
1. **Decision Point Hit Rate:** % of outputs requiring human review
2. **Override Rate:** % of human decisions that edit/reject
3. **Time to Decision:** Time from output to human decision
4. **Rule Coverage:** % of cases resolved by rules (no LLM)

**Targets:**
- Decision Point Hit Rate: 20-30% (not 100%)
- Override Rate: <10%
- Time to Decision: <24 hours
- Rule Coverage: >60%

### 6.5 Policy Compliance Testing

**Test:** System enforces policy rules deterministically

**Method:**
1. Create test cases that should trigger specific rules
2. Verify rules fire correctly
3. Verify LLM does not override rules
4. Verify invalid transitions are blocked

**Expected:** 100% policy compliance

---

## 7. IMPLEMENTATION PRIORITY

### Phase 1: Critical Fixes (Week 1)
1. ✅ Create rule engine (`utils/rules.py`)
2. ✅ Refactor Strategy Agent to apply rules first
3. ✅ Fix Supervisor `should_wait_for_human()` logic
4. ✅ Add state validation in Supervisor

### Phase 2: Architecture Refactoring (Week 2)
1. ✅ Refactor all agents to follow Rules > Retrieval > LLM pattern
2. ✅ Add explicit validation nodes to workflow
3. ✅ Refactor app.py to remove chatbot behavior
4. ✅ Add structured decision UI

### Phase 3: Missing Agents (Week 3)
1. ✅ Create Market Intelligence Agent
2. ✅ Create Supplier Scoring Agent
3. ✅ Create RFx Draft Agent
4. ✅ Create Contract Support Agent
5. ✅ Create Implementation Agent

### Phase 4: Testing & Validation (Week 4)
1. ✅ Implement determinism tests
2. ✅ Implement override tracking tests
3. ✅ Implement agent stability tests
4. ✅ Measure human-AI collaboration metrics

---

## 8. HARD CONSTRAINTS TO ENFORCE

1. **LLMs never make awards or policy decisions** → Enforce via rule engine
2. **Rules > Analytics > Retrieval > LLM** → Refactor agent execution order
3. **Humans must Approve/Edit/Reject all outputs** → Add structured decision UI
4. **Full traceability** → Enhance logging with rule execution, data retrieval, decision rationale
5. **Explicit decision points** → Remove conversational approval, add explicit buttons
6. **Deterministic validation** → Add validation layer before LLM calls

---

**END OF EVALUATION**




