# Agentic AI for Dynamic Sourcing Pipelines - Research POC

A research proof-of-concept web application demonstrating agentic orchestration, human-in-the-loop governance, and traceability for dynamic sourcing pipeline management.

## Deployment

This Streamlit app is deployable to Streamlit Community Cloud or equivalent platforms.

### Prerequisites

- Python 3.9+
- OpenAI API key

### Environment Variables

Set the following environment variable:

```bash
OPENAI_API_KEY=your_api_key_here
```

For local development, create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_api_key_here
```

### Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running Locally

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

### Deployment to Streamlit Community Cloud

1. Push this repository to GitHub
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud)
3. Connect your GitHub repository
4. Set the `OPENAI_API_KEY` environment variable in the Streamlit Cloud settings
5. Deploy

## Demo Steps

1. **Overview Tab**: View case summaries and status
2. **Signals Tab**: Evaluate signals and create cases from signals
3. **Copilot Tab**: Enter user intent and run the agentic workflow
4. **Agent Activity Tab**: Inspect detailed agent logs with LLM inputs/outputs
5. **Case Trace Tab**: View timeline of case progression through DTP stages

## Architecture

- **Sourcing Signal Layer (deterministic, non-agent)**: Scans contracts, performance, and simple spend/benchmark signals to emit `CaseTrigger` objects that **initiate cases at DTP‑01**.  
  - This layer does **not** renew, renegotiate, terminate, or award contracts – it only emits **signals** that a case should be opened.
- **LangGraph**: Orchestrates the sourcing workflow with explicit state management.
- **Supervisor Agent**: Deterministic central coordinator that owns case state, DTP stage transitions, and all routing/approval logic. Only the Supervisor can update `CaseSummary` or advance stages.
- **Specialist Agents**: Signal Interpretation, Strategy, Supplier Evaluation, Negotiation Support, Case Clarifier (all LLM-powered but **state-less**).
- **Vector Knowledge Layer (read-only)**: Conceptual layer providing governed, stage-scoped retrieval of DTP procedures, category strategies, RFx templates, contract clauses, and historical sourcing cases. Retrieval **grounds** reasoning but never overrides rules or policies.
- **Human-in-the-Loop**: `WAIT_FOR_HUMAN` node explicitly pauses the workflow when policy or materiality requires human approval (Approve/Edit/Reject).
- **Token Guardrails**: Tiered model strategy with per-case budget limits.

### Governance Principles

- **Rules & Policies First**: `RuleEngine` and `PolicyLoader` enforce what is allowed before any LLM narration.
- **Supervisor Authority**: SupervisorAgent is the only orchestrator; LLM agents cannot change stages or status.
- **System-Initiated Renewals**: All proactive renewal behavior is framed as **system-initiated case creation at DTP‑01**, never as automatic renewal/termination.
- **LLMs as Narrators**: LLM agents summarize, explain, and propose – they do **not** make awards or policy decisions.
- **Chatbot UX is Read-Only**: The GPT-like chat in the UI only explains what the Supervisor + policies have already allowed; it never bypasses governance.

## Data

All data is synthetic and anonymized for demonstration purposes. Data files are located in `/data`:
- `categories.json`: Category definitions (CAT-01, CAT-02, ...)
- `suppliers.json`: Supplier information (SUP-001, SUP-002, ...)
- `performance.json`: Supplier performance metrics
- `contracts.json`: Contract details (CON-001, ...)
- `market.json`: Market benchmark data
- `cases_seed.json`: Seed cases (CASE-0001, ...)

## Notes

- This is research POC software, not production-ready
- All metrics and outputs are illustrative and synthetic
- Token usage is tracked and limited per case (3,000 token hard cap)
- Agent outputs are cached using SHA-256 input hashing






