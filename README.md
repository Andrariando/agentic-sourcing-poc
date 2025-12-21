# Agentic AI for Dynamic Sourcing Pipelines - Research POC

A research proof-of-concept web application demonstrating **agentic orchestration**, **human-in-the-loop governance**, and a **human-like collaborative assistant** for dynamic sourcing pipeline management.

> 📖 **For detailed architecture documentation, see [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)**

---

## Key Features

### 🤝 Collaboration Mode
The chatbot behaves like a thoughtful human assistant:
- **Discusses before executing** — Asks clarifying questions, surfaces tradeoffs
- **Extracts binding constraints** — "I don't mind disruption" becomes a hard constraint
- **Acknowledges preferences** — Immediately confirms what it heard
- **Transitions explicitly** — Only executes when user says "proceed"

### 🔒 Governance First
- **Rules > LLM** — Deterministic rules applied before any LLM reasoning
- **Supervisor Authority** — Only the Supervisor can change case state
- **Human-in-the-Loop** — Significant decisions require human approval

### 🎯 DTP Pipeline (DTP-01 to DTP-06)
Strategy → Planning → Sourcing → Negotiation → Contracting → Execution

---

## Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key (or create .env file)
export OPENAI_API_KEY=your_api_key_here

# Run
streamlit run app.py
```

The app will be available at `http://localhost:8501`

---

## How It Works

### Two Interaction Modes

| Mode | Trigger Examples | Behavior |
|------|------------------|----------|
| **Collaboration** | "What are the options?", "Help me think..." | Discussion, no workflow execution |
| **Execution** | "Proceed", "Run analysis", "Recommend" | Workflow execution with constraints |

### Constraint Extraction

User statements automatically become binding constraints:

| User Says | Constraint Extracted |
|-----------|---------------------|
| "I don't mind disruption" | `disruption_tolerance = HIGH` |
| "Budget is fixed" | `budget_flexibility = FIXED` |
| "Price is the priority" | `priority_criteria = ["price"]` |
| "Prefer the current supplier" | `supplier_preference = PREFER_INCUMBENT` |

These constraints are injected into agent prompts and **override default logic**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      USER MESSAGE                            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   INTENT CLASSIFIER    │  (Rule-based, no LLM)
              │  COLLABORATIVE/EXECUTION│
              └────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌──────────────────────┐        ┌──────────────────────┐
│  COLLABORATION MODE  │        │   EXECUTION MODE     │
│                      │        │                      │
│ • Extract constraints│        │ • LangGraph workflow │
│ • Ask questions      │        │ • Supervisor agent   │
│ • Frame options      │        │ • Specialist agents  │
│ • No DTP advancement │        │ • DTP transitions    │
└──────────────────────┘        └──────────────────────┘
          │                                 │
          └────────────────┬────────────────┘
                           ▼
              ┌────────────────────────┐
              │   SHARED STATE         │
              │ • CaseMemory           │
              │ • ExecutionConstraints │
              └────────────────────────┘
```

### Key Components

| Component | Purpose | LLM Usage |
|-----------|---------|-----------|
| Intent Classifier | Route to COLLABORATIVE or EXECUTION mode | None |
| Constraint Extractor | Extract binding constraints from user input | None |
| Collaboration Engine | Generate discussion responses | None |
| Supervisor Agent | Orchestrate workflow, manage state | None |
| Strategy Agent | Recommend sourcing strategy (DTP-01) | Summarization only |
| Supplier Agent | Score and shortlist suppliers (DTP-02/03) | Explanation only |

---

## Data

All data is synthetic and anonymized. Data files in `/data`:
- `categories.json` — Category definitions
- `suppliers.json` — Supplier information
- `performance.json` — Supplier performance metrics
- `contracts.json` — Contract details
- `market.json` — Market benchmark data
- `cases_seed.json` — Seed cases

---

## Documentation

| Document | Description |
|----------|-------------|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Complete system architecture |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Phase 1 implementation details |
| [PHASE2_CHANGES_SUMMARY.md](PHASE2_CHANGES_SUMMARY.md) | Phase 2 changes |

---

## Notes

- Research POC software, not production-ready
- All metrics and outputs are illustrative and synthetic
- Token usage tracked and limited (3,000 token per-case cap)
- Agent outputs cached using SHA-256 input hashing

---

## Deployment

### Streamlit Community Cloud

1. Push repository to GitHub
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud)
3. Connect your GitHub repository
4. Set `OPENAI_API_KEY` in Streamlit Cloud settings
5. Deploy

---

**License:** Research POC — Not for production use
