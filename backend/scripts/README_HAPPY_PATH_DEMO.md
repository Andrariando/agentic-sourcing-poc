# Happy Path Demo Script

This script creates a complete demonstration case that runs through all 6 DTP stages (DTP-01 to DTP-06) with full chat history.

## What It Does

1. **Seeds Data**: Ensures all required synthetic data exists (suppliers, spend, SLA events, documents)
2. **Creates Demo Case**: Creates or resets `CASE-DEMO-001` 
3. **Runs Full Workflow**: Executes all stages with appropriate chat messages:
   - DTP-01: Scan signals → Strategy recommendation
   - DTP-02: Score suppliers
   - DTP-03: Draft RFx
   - DTP-04: Support negotiation
   - DTP-05: Extract key terms
   - DTP-06: Generate implementation plan
4. **Saves Chat History**: All conversations are saved to the case's activity log
5. **Persists State**: Final case state is saved to the database

## Usage

```bash
# From project root
python backend/scripts/run_happy_path_demo.py
```

## Output

- **Case ID**: `CASE-DEMO-001`
- **Final Stage**: DTP-06
- **Final Status**: In Progress (or Closed)
- **Chat History**: Saved in activity log and `data/happy_path_demo.json`
- **Artifacts**: All artifacts from each stage are persisted

## Viewing in UI

After running the script:

1. Start backend:
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```

2. Start frontend:
   ```bash
   streamlit run frontend/app.py
   ```

3. Open `CASE-DEMO-001` in the Case Copilot:
   - Navigate to Case Dashboard
   - Find and select `CASE-DEMO-001`
   - Chat history will be automatically loaded from activity log
   - All artifacts will be visible in the Artifacts panel

## Chat History Format

Chat messages are stored in the case's `activity_log` with this structure:

```json
{
  "timestamp": "2025-01-15T10:30:00",
  "action": "Chat: user",
  "agent_name": "User",
  "details": {
    "message": "Scan signals",
    "stage": "DTP-01",
    "metadata": {...}
  }
}
```

The UI automatically converts these to chat history format for display.

## Demo Data File

A complete snapshot is saved to `data/happy_path_demo.json` containing:
- Full chat history
- Stage transition log
- Final case state
- Timestamps

This file can be used for reference or to restore the demo state.

