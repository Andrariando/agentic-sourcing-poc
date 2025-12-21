# Case Memory System

**Phase 2 Implementation - Objective A**

## Overview

The Case Memory system provides **real, structured memory** for sourcing cases, replacing the previous cosmetic memory that only existed for display purposes.

## Problem Solved

Previously:
- Conversation history was stored only in `st.session_state.chat_responses` for display
- Agents received no context about prior interactions
- Each workflow invocation was effectively stateless
- The chatbot appeared to "remember" but agents couldn't actually use past context

Now:
- A structured `CaseMemory` object persists across workflow invocations
- Memory is updated after every workflow execution
- Memory context is injected into agent prompts
- Memory is bounded (not raw chat transcripts)

## Architecture

### CaseMemory Model

```
CaseMemory
├── case_id: str
├── entries: List[MemoryEntry]  # Rolling, bounded to 20 entries
├── current_strategy: str       # Latest recommended strategy
├── current_supplier_choice: str # Latest supplier recommendation
├── human_decisions: List[str]  # Last 10 decisions
├── key_user_intents: List[str] # Last 5 user requests
├── active_contradictions: List[str]
├── total_agent_calls: int
└── total_human_decisions: int
```

### MemoryEntry Model

```
MemoryEntry
├── timestamp: str
├── entry_type: str  # "decision", "approval", "rejection", "user_intent", "agent_output", "contradiction"
├── agent_name: str
├── summary: str     # Concise, max ~100 chars
└── details: Dict
```

## Usage

### Creating Memory

```python
from utils.case_memory import create_case_memory

memory = create_case_memory("CASE-0001")
```

### Recording Events

```python
# Record agent output
memory.record_agent_output(
    agent_name="Strategy",
    output_type="StrategyRecommendation",
    summary="Recommends RFx",
    details={"recommended_strategy": "RFx", "confidence": 0.85}
)

# Record human decision
memory.record_human_decision(
    decision="Approve",
    reason="Aligned with category strategy",
    context="Strategy recommendation"
)

# Record user intent
memory.record_user_intent("I want to explore alternative suppliers")

# Record contradiction
memory.record_contradiction(
    description="Strategy changed from Renew to RFx",
    agents_involved=["Strategy", "Strategy"],
    details={}
)
```

### Injecting into Agent Prompts

```python
# Get bounded context for prompt injection
prompt_context = memory.get_prompt_context()

# Returns something like:
# === CASE MEMORY ===
# • Current recommended strategy: RFx
# • Human decisions so far: Approve: Strategy recommendation
# • Recent activity:
#   - Strategy: Recommends RFx
#   - User: I want to explore alternative suppliers
# === END CASE MEMORY ===
```

## Integration Points

### 1. Workflow (graphs/workflow.py)

Memory is updated in `supervisor_node` after each agent execution:

```python
case_memory = state.get("case_memory")
if case_memory is None:
    case_memory = create_case_memory(case_summary.case_id)
    state["case_memory"] = case_memory

if latest_output and latest_agent_name:
    update_memory_from_workflow_result(
        case_memory, latest_agent_name, latest_output, user_intent
    )
```

### 2. App (app.py)

Memory is persisted in session state:

```python
if "case_memories" not in st.session_state:
    st.session_state.case_memories = {}
st.session_state.case_memories[case_id] = case_memory
```

### 3. Response Generation

Memory context can be used in response generation:

```python
response_adapter.generate_response(
    output, case_state_dict, memory=case_memory, ...
)
```

## Bounds and Limits

| Item | Limit | Rationale |
|------|-------|-----------|
| Memory entries | 20 | Prevent unbounded growth |
| User intents | 5 | Focus on recent requests |
| Human decisions | 10 | Capture key approvals |
| Prompt context | ~500 tokens | Keep prompts manageable |

## What Memory Does NOT Do

- ❌ Store raw chat transcripts
- ❌ Replace PipelineState (execution state)
- ❌ Store full agent outputs (only summaries)
- ❌ Persist across browser sessions (Streamlit limitation)
- ❌ Make decisions (only provides context)

## Future Enhancements

- Database persistence for cross-session memory
- Semantic summarization of memory entries
- Memory-aware prompt compression
- Cross-case memory for category patterns
