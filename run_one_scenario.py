"""
Minimal script to run one synthetic sourcing scenario and export a poster‑ready trace.

Steps:
1) Load the first seed case from data/cases_seed.json
2) Run the LangGraph workflow headless
3) Extract an execution trace using `extract_execution_trace`
4) Write the result to `scenario_trace.json`
"""

import json
from pathlib import Path

from utils.scenario_runner import load_seed_cases, run_case_headless
from utils.trace_export import extract_execution_trace


def main() -> None:
    # 1) Load one synthetic seed case
    cases = load_seed_cases()
    if not cases:
        raise RuntimeError("No seed cases found in data/cases_seed.json")
    case = cases[0]

    # 2) Run LangGraph headless with a fixed, synthetic intent
    user_intent = "What is the next best action I should take on this case?"
    _, updated_case = run_case_headless(case, user_intent=user_intent)

    # 3) Extract execution trace from the updated case
    steps = extract_execution_trace(updated_case)

    output = {
        "case_id": updated_case.case_id,
        "user_intent": user_intent,
        "status": updated_case.status,
        "steps": steps,
    }

    # 4) Write JSON file suitable for inclusion in a research poster
    out_path = Path("scenario_trace.json")
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {out_path.resolve()}")


if __name__ == "__main__":
    main()







