# Agentic Sourcing System: Technical Backend Documentation

This document provides a detailed technical deep-dive into the backend architecture and logic of the Agentic Sourcing Copilot. It is intended for auditing, technical review, and developers seeking to understand the inner workings of the system.

---

## 🏗️ 1. High-Level Architecture

The system follows a service-oriented architecture with a clear separation between governance, execution, and persistence.

- **API Layer (FastAPI)**: The entry point for all frontend requests.
- **Service Layer (ChatService, CaseService)**: Orchestrates business logic and service interactions.
- **Agent Layer (Supervisor & Worker Agents)**: The "brain" of the system, using LLMs to analyze data and generate artifacts.
- **RAG Layer (Retriever, Vector Store)**: Handles document retrieval and grounding analysis.
- **Persistence Layer (SQLite/ChromaDB)**: Stores case data, chat history, and document embeddings.

---

## 💬 2. The Chat Request Lifecycle

What happens when a human asks something in the chat window?

### Step 1: Frontend Submission
The user types a message and clicks send. The Streamlit frontend sends a `POST` request to `/api/chat` with:
- `case_id`: The unique identifier for the current procurement project.
- `user_message`: The raw text input from the user.
- `use_tier_2`: A flag indicating whether to use more advanced (and expensive) LLM models.

### Step 2: ChatService Entry Point
`ChatService.process_message()` is the main orchestrator. It performs the following setup:
1. **Traceability**: Generates a unique `trace_id` (UUID) for logging and debugging this specific request.
2. **Context Retrieval**: Loads the current case state (DTP stage, status, metadata) from the database.
3. **Conversation Memory**: If enabled, fetches recent chat history to provide context to the LLM.

### Step 3: Intent Classification (The Supervisor's First Job)
The system doesn't immediately run a heavy agent for every simple "Hello" or "Explain this". Instead, it uses the `IntentRouter` to classify the message into one of five categories:
- **STATUS**: Inquiries about progress (e.g., "Where are we?").
- **EXPLAIN**: Requests for clarification on existing data (e.g., "Why did you suggest this?").
- **EXPLORE**: Hypothetical comparisons (e.g., "What if we switched to Supplier X?").
- **DECIDE**: Explicit requests for analysis or action (e.g., "Scan for signals" or "Draft RFx").
- **GENERAL**: Greetings or off-topic conversation.

**Logic Chain for Classification**:
1. **Pattern Matching**: Quick regex check for greetings or simple status keywords.
2. **LLM Classification**: If patterns don't match, an LLM analyzes the message + case context to determine the goal and work type.
3. **Approval Detection**: If the system is currently "Waiting for Human", it checks if the message is an approval or rejection of a pending recommendation.

### Step 4: Routing & Execution
Based on the intent, the `ChatService` routes to a specific handler:

#### A. Read-Only Intents (STATUS, EXPLAIN)
The system generates a conversational response using the existing case data *without* invoking a specialized worker agent. This saves cost and provides instant feedback.

#### B. Execution Intents (DECIDE, EXPLORE)
If the user wants new work done, the Supervisor determines which specialist agent to call based on the current **DTP Stage**:
- **DTP-01/02** -> `SourcingSignalAgent`: Scans market data and internal signals.
- **DTP-03** -> `SupplierScoringAgent`: Evaluates suppliers against a scorecard.
- **DTP-04** -> `RfxDraftAgent`: Generates RFP/RFQ document drafts.
- **DTP-05** -> `NegotiationSupportAgent`: Prepares leverage points and target terms.
- **DTP-06** -> `ContractSupportAgent`: Analyzes legal terms and compliance.

### Step 5: Agent Processing (The Specialist's Job)
When a specialist agent (e.g., `SourcingSignalAgent`) is invoked:
1. **RAG Retrieval**: The agent queries the `Retriever` to find relevant documents (contracts, signal reports, supplier profiles) grounded in the case's category and region.
2. **Reasoning**: The LLM processes the retrieved documents + user prompt + case data.
3. **Artifact Generation**: The agent produces an `ArtifactPack`, which contains:
   - **Artifacts**: Structured objects like Signal Reports or Scorecards.
   - **Rationale**: The "why" behind the results.
   - **Next Actions**: Recommended steps for the user.
   - **Risks**: Potential issues identified during analysis.

### Step 6: Persistence & State Update
The `ArtifactPack` and the conversation history are saved:
- The `CaseService` persists the artifacts to the database.
- The `Case Status` might update (e.g., moving from "DTP-01" to "DTP-02").
- If the agent made a recommendation, the case state is set to `waiting_for_human = True`.

### Step 7: Final Response Generation
The `ChatService` takes the agent's output and formats it into a conversational message for the user. This includes:
- A summary of what was done.
- A call to action (e.g., "Review the signals above").
- Metadata for the UI to render structured components (tabs, cards).

---

## 🛠️ 3. Key Backend Components

### 1. The Supervisor Agent (`backend/supervisor/`)
The Supervisor is the hub. It manages the **DTP (Draft to Procurement)** workflow. It ensures that the system doesn't skip steps—for example, it won't allow drafting an RFx before suppliers have been scored.

### 2. RAG Pipeline (`backend/rag/`)
- **Ingestion**: Documents are split into chunks and embedded into a vector store (ChromaDB).
- **Retrieval**: Uses semantic search to find the top $K$ most relevant chunks.
- **Grounding**: Agents are instructed to provide "grounding source IDs" for every claim they make, which the UI displays as citations.

### 3. Artifact Placement Map (`backend/artifacts/placement.py`)
This is the single source of truth for where data should appear in the UI. For example:
- `SIGNAL_REPORT` -> Appears in the "Signals" tab.
- `EVALUATION_SCORECARD` -> Appears in the "Scoring" tab.

### 4. Task-Based Agent Workflow (`backend/tasks/`)
Agents do not just "ask an LLM a question". They follow a structured **Task-Based** execution model:
- **Task Registry**: All available atomic tasks (e.g., "Analyze Signal Breach", "Calculate Supplier Score") are defined in the `registry.py`.
- **Planners**: When an agent is invoked, a `Planner` determines the sequence of atomic tasks needed to satisfy the user request.
- **Task Execution**: Each task is executed individually, often with its own specific prompt and RAG context. This ensures high precision and avoids "LLM wandering."
- **Task Feedback**: The results of each task are fed into the next, creating a logical chain of reasoning.

---

## 🛡️ 4. Governance & Safety
- **Human-in-the-Loop**: All major decisions (approving a supplier, finalizing an RFx) require explicit user approval.
- **Cost Awareness**: The `ConversationContextManager` prunes chat history to prevent context window blow-up and excessive API costs.
- **Transparency**: Detailed execution metadata (tokens used, tasks performed) is recorded for every agent run for auditability.
