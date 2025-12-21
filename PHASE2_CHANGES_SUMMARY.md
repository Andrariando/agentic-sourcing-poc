# Phase 2 Changes Summary

## What Was Fixed

### 1. Memory Made Real (Objective A)
**Problem:** Agents were stateless; conversation history was cosmetic display-only.

**Fix:** Created `CaseMemory` class (`utils/case_memory.py`) that:
- Maintains a rolling, bounded history of decisions and events
- Gets updated after every workflow execution
- Provides prompt context for agents via `get_prompt_context()`
- Stores user intents, approvals, rejections, and contradictions

**Why It Matters:** Agents now have actual context about what happened in prior turns. The chatbot doesn't just *look* like it remembers—it actually does.

---

### 2. Decision Logic Separated from Chat (Objective B)
**Problem:** `app.py` mixed UI rendering, workflow execution, and response construction in one tangled file.

**Fix:** Created `ResponseAdapter` class (`utils/response_adapter.py`) that:
- Takes structured agent outputs → produces natural language
- Has dedicated handlers for each output type
- Automatically adds HIL prompts and contradiction warnings
- Lives outside `app.py`

**Why It Matters:** Adding a new agent type no longer requires editing `app.py`. Response formatting is consistent and centralized.

---

### 3. Agent Boundaries Enforced in Code (Objective C)
**Problem:** Agent constraints were prompt-based and advisory; nothing stopped an agent from returning an invalid output.

**Fix:** Created `AgentOutputValidator` class (`utils/agent_validator.py`) that:
- Maintains a canonical `AGENT_OUTPUT_REGISTRY` of allowed outputs per agent
- Validates outputs in `supervisor_node` after every agent execution
- Flags violations in `guardrail_events`
- Performs type-specific validation (e.g., strategy values, confidence ranges)

**Why It Matters:** Prompts describe constraints; code enforces them. Invalid agent behavior is now caught and logged.

---

### 4. Case State Ownership Clarified (Objective D)
**Problem:** Multiple overlapping state objects (Case, CaseSummary, PipelineState) with unclear ownership.

**Fix:** Created canonical `CaseState` model (`utils/case_state.py`) that:
- Represents the single authoritative case record
- Includes summary, memory, outputs, and history in one object
- Has clear mutation rules (only Supervisor can change it)
- Provides methods for recording events and advancing stages

**Why It Matters:** Future developers know where the truth lives. State transitions are explicit, not implicit.

---

### 5. Contradictions Made Visible (Objective E)
**Problem:** Later agents silently overwrote earlier decisions; humans never saw conflicts.

**Fix:** Created `ContradictionDetector` class (`utils/contradiction_detector.py`) that:
- Detects strategy changes, supplier mismatches, and approval conflicts
- Logs contradictions in case memory
- Surfaces them in chat via ResponseAdapter warnings
- Does NOT attempt automatic resolution

**Why It Matters:** Humans see when agents disagree. Transparency over automation.

---

## What Remains Out of Scope

| Item | Why |
|------|-----|
| Database persistence | Requires infrastructure; POC uses session state |
| Vector retrieval | Knowledge layer remains a placeholder |
| Automatic conflict resolution | Violates "transparency > automation" principle |
| Cross-session memory | Would require external storage |
| Full CaseState migration | Backward compatibility preserved |
| UI redesign | Not requested |
| New external services | Ground rules prohibit |

---

## Files Created

| File | Purpose |
|------|---------|
| `utils/case_memory.py` | Structured memory layer |
| `utils/response_adapter.py` | Chat narration adapter |
| `utils/agent_validator.py` | Output validation |
| `utils/case_state.py` | Canonical state model |
| `utils/contradiction_detector.py` | Conflict detection |
| `CASE_MEMORY.md` | Memory documentation |
| `ARCHITECTURE_PHASE2.md` | Architecture documentation |
| `PHASE2_CHANGES_SUMMARY.md` | This document |

## Files Modified

| File | Changes |
|------|---------|
| `graphs/workflow.py` | Integrated validation, memory updates, contradiction detection in supervisor_node |
| `utils/state.py` | Added Phase 2 fields (case_memory, output_history, detected_contradictions, etc.) |
| `app.py` | Integrated ResponseAdapter, memory persistence, contradiction surfacing |
| `utils/__init__.py` | Exported Phase 2 modules |

---

## How to Verify

1. **Memory works:**
   - Create a case → approve a strategy → check that memory shows the approval
   - Memory context is visible in agent logs

2. **Validation works:**
   - Check `guardrail_events` in state after agent execution
   - Invalid outputs are flagged

3. **Contradictions work:**
   - Run strategy agent twice with different inputs
   - Chat should show ⚠️ contradiction warning

4. **Demo still works:**
   - `streamlit run app.py` starts normally
   - Cases can be created and processed
   - Human approvals still function

---

## Summary

Phase 2 transforms the POC from a "demo with cosmetic memory" to a "demo with real memory and governance." The chatbot now remembers, validates, and surfaces conflicts—without breaking the conversational UX or adding infrastructure overhead.
