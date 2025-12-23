# Agentic Sourcing Copilot — Enterprise POC

A **human-in-the-loop, multi-agent decision-support system** for procurement sourcing, built on the Dynamic Transaction Pipeline (DTP-01 to DTP-06) methodology.

> **Phase 3** — Enterprise Memory & Evidence Implementation

---

## 🎯 Design Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Decision is focal point** | AI advises, human decides |
| **Rules > LLM** | Deterministic rules before any LLM reasoning |
| **No autonomous decisions** | All recommendations require human approval |
| **Full traceability** | Every output attributable to inputs, rules, data, and agent |
| **Grounded retrieval** | Answers cite uploaded documents/data |

---

## 🏗️ Architecture

### Folder Structure

```
agentic-sourcing-poc/
│
├── frontend/                    # Streamlit UI only
│   ├── app.py                   # Main entry point
│   ├── api_client.py            # Backend communication
│   └── pages/
│       ├── case_dashboard.py    # Case list & metrics
│       ├── case_copilot.py      # Decision console + chat
│       └── knowledge_management.py  # Document/data upload
│
├── backend/                     # All business logic
│   ├── main.py                  # FastAPI server (API entry point)
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
│   ├── ingestion/               # Data ingestion pipelines
│   │   ├── document_ingest.py   # PDF/DOCX/TXT → ChromaDB (RAG)
│   │   ├── data_ingest.py       # CSV/Excel → SQLite (Data Lake)
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
│   └── services/                # Business logic layer
│       ├── case_service.py      # Case management
│       ├── chat_service.py      # Copilot with Supervisor
│       └── ingestion_service.py # Ingestion orchestration
│
├── shared/                      # Cross-cutting modules
│   ├── schemas.py               # Pydantic schemas
│   └── constants.py             # Enums & constants
│
├── data/                        # Synthetic data & databases
│   ├── datalake.db              # SQLite data lake
│   └── chroma_db/               # ChromaDB vector store
│
└── requirements.txt
```

### System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Streamlit)                        │
│  Case Dashboard │ Case Copilot (Decision Console) │ Knowledge Mgmt  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼ API Client
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                           │
│  /api/cases │ /api/chat │ /api/decisions │ /api/ingest │ /health    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
      │  SUPERVISOR │      │    RAG      │      │  DATA LAKE  │
      │  (LangGraph)│      │ (ChromaDB)  │      │  (SQLite)   │
      └─────────────┘      └─────────────┘      └─────────────┘
              │
    ┌─────────┼─────────┬─────────┬─────────┐
    ▼         ▼         ▼         ▼         ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│Strategy││Supplier││Negotia-││Contract││ Signal │
│ Agent  ││ Agent  ││tion    ││ Agent  ││ Agent  │
└────────┘└────────┘└────────┘└────────┘└────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key

### Installation

```bash
# Clone repository
git clone https://github.com/Andrariando/agentic-sourcing-poc.git
cd agentic-sourcing-poc

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
```

### Running Locally

#### Option 1: Separated Mode (Full Architecture)

```bash
# Terminal 1: Start Backend
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start Frontend
streamlit run frontend/app.py
```

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:8501

#### Option 2: Integrated Mode (Single Process)

```bash
# Set environment variable
export USE_INTEGRATED_MODE=true

# Run frontend only (backend runs in-process)
streamlit run frontend/app.py
```

---

## 📡 API Reference

### Case Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases` | List all cases |
| GET | `/api/cases/{id}` | Get case details |
| POST | `/api/cases` | Create new case |

### Copilot Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message to copilot |

### Human Decisions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/decisions/approve` | Approve recommendation |
| POST | `/api/decisions/reject` | Reject recommendation |

### Document Ingestion (RAG)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/document` | Upload PDF/DOCX/TXT |
| GET | `/api/documents` | List ingested documents |
| DELETE | `/api/documents/{id}` | Delete document |

### Structured Data Ingestion
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/data/preview` | Preview CSV/Excel |
| POST | `/api/ingest/data` | Ingest to data lake |
| GET | `/api/ingest/history` | View ingestion history |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

## 🔐 Governance Rules

1. **Frontend never calls agents directly** — All via API → Supervisor
2. **Supervisor is single source of truth** — State managed centrally
3. **Intent classification is deterministic** — Keyword-based, no LLM
4. **Exploration doesn't change state** — EXPLORE intent is read-only
5. **Stage advancement requires approval** — Human clicks Approve/Reject
6. **Retrieval is stage-gated** — Documents filtered by DTP relevance

---

## 🎨 UI Design

Enterprise-grade decision console using MIT color system:

| Color | Hex | Usage |
|-------|-----|-------|
| MIT Navy | `#003A8F` | Headers, structure |
| MIT Cardinal Red | `#A31F34` | Actions, alerts |
| Near Black | `#1F1F1F` | Body text |
| Charcoal | `#4A4A4A` | Secondary text |
| Light Gray | `#D9D9D9` | Borders |
| White | `#FFFFFF` | Backgrounds |

### Page Layout

**Case Copilot** — 3-column decision console:
- **Left**: Case Context (read-only)
- **Center**: Decision Card + Evidence + Approval Buttons
- **Right**: Copilot Chat (fixed-height, scrollable)

---

## 🧪 Demo Scenarios

### 1. Upload Contract → Ask Grounded Question
1. Go to **Knowledge & Data**
2. Upload a contract PDF with metadata
3. Create/open a case
4. Ask: "What are the key terms in the contract?"
5. ✅ Answer cites uploaded document

### 2. Upload KPI Data → Performance Question
1. Upload CSV with supplier performance data
2. Ask: "How is supplier X performing?"
3. ✅ Answer cites data lake

### 3. Stage Gating
1. Open case at DTP-01
2. Ask: "Execute the contract"
3. ✅ System explains action not available at current stage

### 4. Human Approval Flow
1. Ask: "Recommend a strategy"
2. Agent provides recommendation
3. Click **Approve** → Stage advances
4. Click **Reject** → Stays at current stage

---

## 📁 Data

Synthetic test data generated via `backend/seed_data.py`:
- Cases at various DTP stages
- Supplier performance metrics
- Spend data
- SLA events

Seed demo data from the Dashboard → "Seed Demo Cases" button.

---

## 🚢 Deployment

### Streamlit Cloud (Integrated Mode)

1. Push to GitHub
2. Connect repo on [Streamlit Cloud](https://streamlit.io/cloud)
3. Set secrets:
   ```
   OPENAI_API_KEY = "sk-..."
   ```
4. Deploy

### Production (Separated Mode)

Deploy backend on:
- AWS (EC2, ECS, Lambda)
- Google Cloud Run
- Azure App Service
- Render / Railway

Set environment variable:
```bash
API_BASE_URL=https://your-backend-url.com
USE_API_MODE=true
```

---

## ⚠️ Notes

- **Research POC** — Not production-ready
- **Synthetic data** — All metrics are illustrative
- **Token limits** — 3,000 tokens per case cap
- **No authentication** — Add API keys for production

---

## 📜 License

Research POC — Not for production use

---

## 🛠️ Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| Phase 1 | Core agentic workflow, LangGraph integration | ✅ Complete |
| Phase 2 | Collaboration mode, constraint extraction | ✅ Complete |
| Phase 3 | Enterprise memory (RAG + Data Lake), UI refactor | ✅ Complete |
| Phase 4 | Authentication, audit logging, production hardening | 🔜 Planned |
