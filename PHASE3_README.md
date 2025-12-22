# Phase 3: Enterprise Memory & Evidence Implementation

## Architecture Overview

Phase 3 implements a clean frontend/backend separation with:
- **Document ingestion → RAG** (ChromaDB)
- **Structured data ingestion → Data Lake** (SQLite)
- **Agent-controlled, supervisor-governed retrieval**
- **Human-in-the-loop governance**

```
agentic-sourcing-poc/
│
├── frontend/                    # Streamlit UI only
│   ├── app.py                   # Main entry point
│   ├── api_client.py            # Backend API client
│   └── pages/
│       ├── case_dashboard.py    # Case list & details
│       ├── case_copilot.py      # Chat interface
│       └── knowledge_management.py  # Document/data upload
│
├── backend/                     # All business logic
│   ├── main.py                  # FastAPI server
│   │
│   ├── supervisor/              # Central orchestration
│   │   ├── graph.py             # LangGraph workflow
│   │   ├── state.py             # State management
│   │   └── router.py            # Intent classification
│   │
│   ├── agents/                  # Specialized agents
│   │   ├── base.py              # Base agent with retrieval tools
│   │   ├── strategy.py          # DTP-01 Strategy Agent
│   │   ├── supplier_eval.py     # DTP-03/04 Supplier Agent
│   │   ├── negotiation.py       # DTP-04 Negotiation Agent
│   │   └── signal.py            # Signal Interpretation Agent
│   │
│   ├── ingestion/               # Data ingestion
│   │   ├── document_ingest.py   # PDF/DOCX/TXT → ChromaDB
│   │   ├── data_ingest.py       # CSV/Excel → SQLite
│   │   └── validators.py        # Schema validation
│   │
│   ├── rag/                     # Vector retrieval
│   │   ├── vector_store.py      # ChromaDB wrapper
│   │   └── retriever.py         # Document retriever
│   │
│   ├── persistence/             # Data lake
│   │   ├── database.py          # SQLite connection
│   │   └── models.py            # SQLModel tables
│   │
│   └── services/                # Business logic
│       ├── case_service.py      # Case management
│       ├── chat_service.py      # Copilot with Supervisor
│       └── ingestion_service.py # Ingestion orchestration
│
└── shared/                      # Shared modules
    ├── schemas.py               # Pydantic schemas
    └── constants.py             # Enums & constants
```

## Running the System

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-your-key-here
```

### 3. Start the Backend

```bash
# From project root
python -m uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### 4. Start the Frontend

In a new terminal:

```bash
# From project root
streamlit run frontend/app.py
```

The UI will be available at `http://localhost:8501`

## Governance Rules Enforced

### 1. Frontend Never Touches Backend Directly
- All communication via `frontend/api_client.py`
- No direct database access
- No direct agent calls

### 2. Supervisor is Single Source of Truth
- All chat goes through `ChatService` → Supervisor
- Intent classified before any action
- State managed centrally

### 3. Agents Use Explicit Retrieval Tools
- `retrieve_documents(query, filters)` for RAG
- `get_supplier_performance(supplier_id)` for data
- No "magic memory"

### 4. Human Approval for Stage Changes
- DECIDE intent requires approval
- Strategy recommendations require approval
- Exploration doesn't change state

### 5. Retrieval Gated by DTP Stage
- Documents filtered by stage relevance
- Invalid retrievals blocked
- User informed why

## Demo Scenarios

### Scenario 1: Upload a Contract → Ask Grounded Question

1. Go to **Knowledge & Data** page
2. Upload a contract PDF
   - Set Document Type: "Contract"
   - Set Supplier ID if applicable
   - Set DTP Relevance: DTP-01, DTP-05
3. Go to **Case Dashboard**
4. Create a new case for the same category
5. Open the case in **Copilot**
6. Ask: "What are the key terms in the current contract?"
7. Response should be grounded in the uploaded document

### Scenario 2: Upload Supplier KPI Data → Performance Question

1. Go to **Knowledge & Data** page
2. Upload a CSV with supplier performance:
   ```csv
   supplier_id,overall_score,quality_score,delivery_score,trend
   SUP-001,8.5,8.0,9.0,improving
   SUP-002,6.0,7.0,5.0,declining
   ```
3. Open a case for that category
4. Ask: "How is supplier SUP-001 performing?"
5. Response should cite the uploaded data

### Scenario 3: Ask Irrelevant Question → Gating

1. Open a case at DTP-01 (Strategy)
2. Ask: "Execute the contract"
3. System should explain this action isn't available at current stage

### Scenario 4: Explore Without Stage Change

1. Open a case at DTP-01
2. Ask: "What if we went with an RFx approach?"
3. This is EXPLORE intent → no state change
4. Agent provides analysis without awaiting approval

### Scenario 5: Decision with Human Approval

1. Open a case at DTP-01
2. Ask: "Recommend a strategy for this case"
3. This is DECIDE intent → requires approval
4. Agent provides recommendation
5. UI shows "Awaiting your approval"
6. Click Approve → Stage advances to DTP-02
7. Click Reject → Stay at DTP-01

## Success Criteria

1. ✅ Upload a contract → ask a question → answer grounded in document
2. ✅ Upload supplier KPI CSV → ask performance question → answer grounded in data
3. ✅ Ask a question irrelevant to current DTP → system explains why it's gated
4. ✅ Explore alternatives without advancing stage
5. ✅ Advance stage only after explicit human approval

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/cases` | GET | List cases |
| `/api/cases` | POST | Create case |
| `/api/cases/{id}` | GET | Get case details |
| `/api/chat` | POST | Send message to copilot |
| `/api/decisions/approve` | POST | Approve pending decision |
| `/api/decisions/reject` | POST | Reject pending decision |
| `/api/ingest/document` | POST | Upload document for RAG |
| `/api/ingest/data` | POST | Upload structured data |
| `/api/ingest/data/preview` | POST | Preview data before upload |
| `/api/documents` | GET | List ingested documents |
| `/api/documents/{id}` | DELETE | Delete document |

## Key Design Decisions

1. **Supervisor Graph** runs synchronously in `ChatService`
2. **Intent Classification** uses keyword matching (deterministic, no LLM)
3. **Stage Transitions** require explicit human approval
4. **Retrieval** is filtered by metadata (supplier, category, DTP stage)
5. **Fallback Outputs** used when LLM fails - never blocks user
6. **Activity Logging** tracks all agent actions for traceability

