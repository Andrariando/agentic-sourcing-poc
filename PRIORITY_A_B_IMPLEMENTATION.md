# Priority A & B Implementation Summary

## Overview

This document summarizes the implementation of **Priority A (Proactive Sourcing & Renewal Intelligence)** and **Priority B (Collaborative Supervisor Behavior)** for the Agentic AI Dynamic Sourcing Pipeline system.

## ✅ Priority A — Proactive Sourcing & Renewal Intelligence

### 1. Sourcing Signal Layer (`utils/signal_aggregator.py`)

**Purpose:** Deterministic **Sourcing Signal Layer** that scans contracts and suppliers to identify renewal, savings, and risk **signals**. It emits `CaseTrigger` objects only and never makes sourcing decisions.

**Key Features:**
- `scan_for_renewals()`: Identifies contracts expiring within 90 days and emits **renewal signals**.
- `scan_for_savings_opportunities()`: Detects spend anomalies vs market benchmarks and emits **savings signals**.
- `scan_for_risk_signals()`: Flags performance degradation and incident patterns as **risk signals**.
- `aggregate_all_signals()`: Comprehensive scanning across all signal types.
- `create_case_from_trigger()`: Converts `CaseTrigger` into a **system-initiated case payload at DTP‑01**.

**Usage (signal emission, not decision):**
```python
from utils.signal_aggregator import SignalAggregator

aggregator = SignalAggregator()
triggers = aggregator.aggregate_all_signals()  # Returns List[CaseTrigger]

# Create case from trigger
case_payload = aggregator.create_case_from_trigger(trigger, existing_case_ids)
```

**CaseTrigger Schema (signal, not decision):**
```python
class CaseTrigger(BaseModel):
    trigger_type: Literal["Renewal", "Savings", "Risk", "Monitoring"]
    category_id: str
    supplier_id: Optional[str]
    contract_id: Optional[str]
    urgency: Literal["Low", "Medium", "High"]
    triggering_signals: List[str]
    recommended_entry_stage: Literal["DTP-01"] = "DTP-01"
```

### 2. Renewal-First Logic (`utils/policy_loader.py`)

**Purpose:** Dynamic policy loading with renewal-specific constraints.

**Key Features:**
- Category-specific policy overrides
- Renewal-specific strategy constraints (default: ["Renew", "Renegotiate", "Terminate"])
- RFx allowed only if explicitly permitted by category policy
- Stage-specific mandatory checks and human approval requirements

**Usage:**
```python
from utils.policy_loader import PolicyLoader

loader = PolicyLoader()
policy = loader.load_policy_for_stage(
    dtp_stage="DTP-01",
    category_id="CAT-01",
    trigger_type="Renewal"  # Applies renewal constraints
)

# Check if strategy is allowed
is_allowed = loader.is_strategy_allowed("RFx", "DTP-01", "CAT-01", "Renewal")
```

**Policy Context:**
```python
class DTPPolicyContext(BaseModel):
    allowed_actions: List[str]
    mandatory_checks: List[str]
    human_required_for: List[str]
    allowed_strategies: Optional[List[str]]  # NEW: For renewal constraints
    allow_rfx_for_renewals: bool  # NEW: Whether RFx allowed for renewals
```

### 3. Supervisor Proactive Case Initiation

**Enhancement:** Supervisor can now create **system-initiated cases at DTP‑01** from `CaseTrigger` objects produced by the Sourcing Signal Layer.

**Method:**
```python
supervisor.create_case_from_trigger(trigger: CaseTrigger, existing_case_ids: List[str])
```

**Integration:** The workflow can now be triggered proactively by:
1. Scanning for signals
2. Generating CaseTrigger objects
3. Creating cases automatically (tagged as `"System"` trigger_source) at **DTP‑01**

> Guardrail: This does **not** renew, renegotiate, or terminate contracts. It only initiates cases; all outcomes still flow through Supervisor + policies + human approvals.

## ✅ Priority B — Collaborative Supervisor Behavior

### 1. Case Clarifier Agent (`agents/case_clarifier_agent.py`)

**Purpose:** LLM-powered agent that generates targeted questions for humans when clarification is needed.

**Key Features:**
- Generates specific, actionable questions (not vague)
- Provides suggested options to guide human decisions
- Identifies missing information or policy ambiguities
- Only responsibility: question generation (Supervisor remains deterministic)

**Usage:**
```python
from agents.case_clarifier_agent import CaseClarifierAgent

clarifier = CaseClarifierAgent(tier=1)
clarification, llm_input, output_dict, input_tokens, output_tokens = clarifier.request_clarification(
    case_summary,
    latest_output,
    context={
        "reason": "Low confidence in strategy recommendation",
        "confidence": 0.55,
        "missing_fields": ["budget_constraints"],
        "policy_ambiguity": "Multiple valid paths exist"
    }
)
```

**ClarificationRequest Schema:**
```python
class ClarificationRequest(BaseModel):
    reason: str
    questions: List[str]
    suggested_options: Optional[List[str]]
    missing_information: List[str]
    context_summary: str
```

### 2. Confidence-Aware Supervisor Routing

**Enhancement:** Supervisor routing now considers confidence scores.

**Routing Logic:**
- **High confidence (≥ 0.8)**: Continue workflow automatically
- **Medium confidence (0.6-0.8)**: May request clarification or secondary agent review
- **Low confidence (< 0.6)**: Pause and request human clarification

**Method:**
```python
next_agent, routing_reason, clarification_request = supervisor.determine_next_agent_with_confidence(
    dtp_stage,
    latest_output,
    policy_context,
    trigger_type
)
```

**Routing Reasons:**
- `"normal_routing"`: Standard routing
- `"low_confidence_clarification"`: Low confidence requires clarification
- `"medium_confidence_policy_requires_human"`: Policy requires human review
- `"out_of_scope"`: Requested action not supported

### 3. Capability Registry & Out-of-Scope Detection

**Purpose:** Explicit handling of agent capabilities to prevent unsupported actions.

**Capability Registry:**
```python
AGENT_CAPABILITIES = {
    "Strategy": ["Renew", "Renegotiate", "RFx", "Terminate", "Monitor"],
    "SupplierEvaluation": ["SupplierShortlist"],
    "NegotiationSupport": ["NegotiationPlan"],
    "SignalInterpretation": ["SignalAssessment"],
    "CaseClarifier": ["ClarificationRequest"]
}
```

**Out-of-Scope Detection:**
```python
is_capable, out_of_scope_notice = supervisor.check_agent_capability(
    agent_name="Strategy",
    requested_action="CustomAction"
)

if not is_capable:
    # Workflow pauses with OutOfScopeNotice
    # Human notified with:
    # - What is out of scope
    # - What alternatives exist
    # - What external action is required
```

**OutOfScopeNotice Schema:**
```python
class OutOfScopeNotice(BaseModel):
    requested_action: str
    reason: str
    suggested_next_steps: List[str]
    alternative_actions: Optional[List[str]]
    external_action_required: bool
```

## Workflow Integration

### New Workflow Nodes

1. **case_clarifier_node**: Generates clarification requests
2. **Enhanced supervisor_node**: Uses confidence-aware routing and capability checks

### Updated Routing

The `route_from_supervisor` function now handles:
- `"case_clarifier"`: Routes to Case Clarifier Agent
- Enhanced confidence-based routing
- Out-of-scope detection

### Workflow Flow

```
Supervisor → (Confidence Check) → CaseClarifier (if needed) → Supervisor
Supervisor → (Capability Check) → OutOfScopeNotice → Wait for Human
Supervisor → (Policy Check) → Strategy (with renewal constraints) → Supervisor
```

## Strategy Agent Updates

**Enhancement:** Strategy Agent now respects renewal constraints from policy.

**Changes:**
- Accepts `allowed_strategies` parameter
- Accepts `trigger_type` parameter
- Prompt includes policy constraints
- Validates strategy against allowed list

**Usage in Workflow:**
```python
recommendation = strategy_agent.recommend_strategy(
    case_summary,
    user_intent,
    allowed_strategies=policy.allowed_strategies,  # ["Renew", "Renegotiate", "Terminate"]
    trigger_type="Renewal"
)
```

## State Schema Updates

**New Optional Fields:**
- `trigger_type`: From CaseTrigger ("Renewal", "Savings", "Risk", "Monitoring")
- `clarification_reason`: Reason for clarification request
- `missing_fields`: Fields missing requiring clarification
- `policy_ambiguity`: Policy ambiguity requiring clarification
- `multiple_paths`: Multiple valid paths requiring human choice

## Design Constraints Maintained

✅ **Supervisor remains deterministic** - No LLM calls in Supervisor  
✅ **LLMs never update case state directly** - Only Supervisor updates state  
✅ **All human interactions explicit** - WAIT_FOR_HUMAN nodes  
✅ **No parallel execution** - Sequential workflow maintained  
✅ **No monitoring** - Focus on core functionality  

## Testing Recommendations

1. **Proactive Case Creation:**
   - Run `SignalAggregator.aggregate_all_signals()`
   - Verify CaseTrigger objects generated
   - Verify cases created with "System" trigger_source

2. **Renewal Constraints:**
   - Create renewal case (trigger_type="Renewal")
   - Verify Strategy Agent only recommends ["Renew", "Renegotiate", "Terminate"]
   - Verify RFx blocked unless category policy allows

3. **Confidence Routing:**
   - Test with low confidence output (< 0.6)
   - Verify CaseClarifier invoked
   - Verify workflow pauses for human input

4. **Out-of-Scope Detection:**
   - Request unsupported action
   - Verify OutOfScopeNotice generated
   - Verify workflow pauses with clear message

## Files Modified/Created

### New Files:
- `utils/signal_aggregator.py` - Proactive signal scanning
- `utils/policy_loader.py` - Dynamic policy loading
- `agents/case_clarifier_agent.py` - Collaborative question generation

### Modified Files:
- `utils/schemas.py` - Added CaseTrigger, ClarificationRequest, OutOfScopeNotice
- `agents/supervisor.py` - Enhanced routing, capability checks, proactive case creation
- `agents/strategy_agent.py` - Renewal constraint enforcement
- `graphs/workflow.py` - Integrated new nodes and routing
- `utils/state.py` - Added new state fields

## Next Steps (Future Enhancements)

1. **Signal Aggregation Scheduling:** Automate periodic scanning
2. **Clarification Response Handling:** Process human responses to clarification requests
3. **Policy Database:** Load policies from external source (database/API)
4. **Enhanced Missing Field Detection:** Automatically identify missing required fields
5. **Multi-Path Resolution:** UI for human to choose between multiple valid paths

---

**Implementation Date:** 2025-01-12  
**Status:** ✅ Complete - Ready for testing


