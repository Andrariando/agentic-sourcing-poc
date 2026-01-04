# Complete the Happy Path Demo

If your demo case is stuck at DTP-01, here's how to complete it through all stages:

## Quick Fix: Re-run the Demo Script

The demo script has been improved to be more robust. Simply run it again:

```bash
python backend/scripts/run_happy_path_demo.py
```

The script will:
1. Detect if the case already exists
2. Reset it to DTP-01 if not complete
3. Run through ALL stages (DTP-01 → DTP-06)
4. Save complete chat history
5. Verify completion

## Verify Completion

After running the script, check the output. You should see:

```
FINAL VERIFICATION
============================================================
  Current Stage: DTP-06
  Status: In Progress
  Activity Log Entries: XX

  ✓ SUCCESS: Case completed all stages (DTP-06)

DEMO COMPLETE
============================================================
✅ Demo case is complete and ready to view!
```

If you see a warning that the case is not at DTP-06, check the logs above for errors.

## What the Script Does

The improved script now:

1. **Processes all 7 messages** in sequence:
   - DTP-01: "Scan signals"
   - DTP-01: "Recommend a strategy for this case"
   - DTP-02: "Score suppliers"
   - DTP-03: "Draft RFx"
   - DTP-04: "Support negotiation"
   - DTP-05: "Extract key terms"
   - DTP-06: "Generate implementation plan"

2. **Auto-approves decisions** to advance stages

3. **Retries and verifies** each stage completion

4. **Saves chat history** to activity log (loaded automatically in UI)

5. **Final verification** ensures case reaches DTP-06

## If Still Stuck at DTP-01

If the case remains at DTP-01 after running the script:

### Option 1: Delete and Recreate
```bash
# The script will recreate it automatically
python backend/scripts/run_happy_path_demo.py
```

### Option 2: Manual Reset
You can manually delete the case and re-run:
```python
from backend.persistence.database import get_db_session
from backend.persistence.models import CaseState
from sqlmodel import delete, select

session = get_db_session()
case = session.exec(select(CaseState).where(CaseState.case_id == "CASE-DEMO-001")).first()
if case:
    session.exec(delete(CaseState).where(CaseState.case_id == "CASE-DEMO-001"))
    session.commit()
session.close()
```

### Option 3: Check Backend Logs
Make sure the backend is running properly. The script needs the backend services to execute agents.

## Viewing in Streamlit

Once complete:

1. **Start backend** (Terminal 1):
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```

2. **Start Streamlit** (Terminal 2):
   ```bash
   streamlit run frontend/app.py
   ```

3. **Open the case**:
   - Go to Dashboard
   - Find `CASE-DEMO-001`
   - Click to open
   - **Chat history will load automatically** from activity log
   - Should show DTP-06 in the header

## Expected Chat History

The complete chat history should include:

1. "Scan signals" → AI response (Signal Report)
2. "Approve" → Stage advance
3. "Recommend a strategy for this case" → AI response (Strategy)
4. "Approve" → Stage advance
5. "Score suppliers" → AI response (Scorecard)
6. "Approve" → Stage advance
7. "Draft RFx" → AI response (RFx Draft)
8. "Approve" → Stage advance
9. "Support negotiation" → AI response (Negotiation Plan)
10. "Approve" → Stage advance
11. "Extract key terms" → AI response (Contract Terms)
12. "Approve" → Stage advance
13. "Generate implementation plan" → AI response (Implementation Plan)
14. "Approve" → Stage advance (to DTP-06)

Total: ~14-16 messages with all interactions.

## Troubleshooting

**Problem**: Script completes but case is still at DTP-01
- **Solution**: Check backend logs for agent execution errors
- **Solution**: Ensure backend services are properly initialized
- **Solution**: Verify database is writable

**Problem**: Chat history not showing in UI
- **Solution**: Check that activity_log contains chat entries
- **Solution**: Refresh the page after loading case
- **Solution**: Verify the case copilot loads activity log correctly

**Problem**: Agents not executing
- **Solution**: Check backend is running and healthy
- **Solution**: Verify agent services are initialized
- **Solution**: Check for missing dependencies

## Next Steps

Once the demo is complete:
- ✅ Case at DTP-06
- ✅ Full chat history visible
- ✅ All artifacts available in tabs
- ✅ Ready for demonstration

