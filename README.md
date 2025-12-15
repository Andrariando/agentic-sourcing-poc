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

- **LangGraph**: Orchestrates agent workflow with state management
- **Supervisor Agent**: Central coordinator managing case state and DTP stage transitions
- **Specialist Agents**: Signal Interpretation, Strategy, Supplier Evaluation, Negotiation Support
- **Human-in-the-Loop**: WAIT_FOR_HUMAN node for approval/rejection of agent outputs
- **Token Guardrails**: Tiered model strategy with per-case budget limits

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


