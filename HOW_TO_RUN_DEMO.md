# How to Load and View the Happy Path Demo in Streamlit

## Step-by-Step Instructions

### 1. Run the Demo Script First

Before loading in Streamlit, you need to create the demo case:

```bash
# From the project root directory
python backend/scripts/run_happy_path_demo.py
```

This will:
- Create `CASE-DEMO-001` 
- Run through all DTP stages (01-06)
- Save complete chat history
- Persist all artifacts

**Expected output:**
```
============================================================
HAPPY PATH DEMO - Full DTP-01 to DTP-06 Workflow
============================================================

Seeding required data...
  ✓ Data already seeded
  ✓ Documents available

Setting up demo case...
  ✓ Using case: CASE-DEMO-001

============================================================
EXECUTING HAPPY PATH
============================================================

[DTP-01] Scan for sourcing signals
  User: Scan signals
  AI: ...
  ✓ Approved - Advanced to DTP-02

... (continues through all stages)

============================================================
DEMO COMPLETE
============================================================
```

### 2. Start the Backend Server

Open Terminal 1:

```bash
# From project root
python -m uvicorn backend.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 3. Start Streamlit Frontend

Open Terminal 2 (keep backend running):

```bash
# From project root
streamlit run frontend/app.py
```

**Expected output:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

Streamlit will automatically open in your browser at `http://localhost:8501`

### 4. Navigate to the Demo Case

You have **3 ways** to access `CASE-DEMO-001`:

#### Option A: From Case Dashboard (Recommended)
1. **Click "Case Dashboard"** in the left sidebar (or it loads by default)
2. **Look for `CASE-DEMO-001`** in the cases list
   - Should show: "Happy Path Demo - IT Services Renewal"
   - Stage: DTP-06
   - Status: In Progress
3. **Click on the case card** to open it in the Case Copilot

#### Option B: Direct Case ID Input
1. **Click "Case Copilot"** in the left sidebar
2. If no case is selected, you'll see a text input
3. **Type:** `CASE-DEMO-001`
4. **Click "Open Case"** button

#### Option C: Quick Access Button (New)
1. **In the Dashboard**, look for the "Demo Data Management" expander
2. **Click the expander** to see demo options
3. **Click "Open Demo Case"** button (will be added)

### 5. View the Demo Case

Once `CASE-DEMO-001` is open, you'll see:

#### Left Panel (60%) - Case Details:
- **Section 1**: Quick Overview (case ID, category, supplier, etc.)
- **Section 2**: Strategy Rationale (recommendation with confidence)
- **Section 3**: Signals & Key Findings
- **Section 4**: Governance Status
- **Section 5**: Documents & Timeline (expandable)

#### Right Panel (40%) - Chat Interface:
- **Complete chat history** from the demo run
- Scrollable conversation showing all interactions
- Shows user messages and AI responses
- Metadata (agent, intent, docs retrieved)

#### Bottom Panel - Artifacts:
- **Tabs**: Signals | Scoring | RFx | Negotiation | Contract | Implementation | History
- **Full artifacts** from each stage
- Expandable cards with detailed information

### 6. What to Check

✅ **Chat History**: Scroll through the conversation to see all prompts and responses
✅ **Stage Progress**: Check the case header - should show DTP-06
✅ **Artifacts**: Click through artifact tabs to see outputs from each stage
✅ **Activity Timeline**: Expand "Documents & Timeline" to see full activity log

## Troubleshooting

### Case Not Found?
- Make sure you ran the demo script first
- Check that backend is running and healthy
- Try refreshing the page

### No Chat History Showing?
- The chat history loads from activity log
- If empty, the demo script may not have completed successfully
- Re-run the demo script

### Backend Connection Issues?
- Verify backend is running on port 8000
- Check `http://localhost:8000/health` in browser
- Should return: `{"status": "healthy", "mode": "api"}`

### Streamlit Not Loading?
- Make sure you're in the project root directory
- Check that `frontend/app.py` exists
- Try: `streamlit run frontend/app.py --server.port 8501`

## Demo Case Details

- **Case ID**: `CASE-DEMO-001`
- **Name**: Happy Path Demo - IT Services Renewal
- **Category**: IT_SERVICES
- **Supplier**: SUP-001
- **Contract**: CTR-001
- **Final Stage**: DTP-06 (Implementation)
- **Chat Messages**: ~14-16 messages (7 user prompts + 7 AI responses + approvals)

## Files Created

- **Demo Case**: Stored in database (`data/datalake.db`)
- **Demo Snapshot**: `data/happy_path_demo.json`
- **Chat History**: Saved in case activity log

## Next Steps

After viewing the demo:
- Try sending new messages to the chat
- Explore different artifact tabs
- Check the activity timeline
- Review the governance status

