"""
Vector Knowledge Layer (read‑only, governed retrieval).

This module represents the **Vector Knowledge Layer** described in the
capstone design. In a production system this would front a vector database
or similar retrieval system. For the POC it is a conceptual, read‑only
abstraction with simple hooks that can be wired to real retrieval later.

DESIGN INTENT:
- Centralized, governed access to unstructured / semi‑structured knowledge
  such as:
  - DTP procedures and playbooks
  - Category strategies
  - RFx templates and evaluation guides
  - Contract clause libraries
  - Historical sourcing cases and lessons learned
- Retrieval is:
  - **Read‑only**
  - **Scoped by category_id and DTP stage**
  - **Never overrides rules or policies**
- Agents may **only** access this kind of knowledge through this layer,
  not by reading arbitrary raw documents.

IMPORTANT:
- This layer **grounds** reasoning and drafting but does **NOT** make
  decisions. All policy enforcement, stage transitions, and approvals
  remain with:
  - `RuleEngine`
  - `PolicyLoader`
  - `SupervisorAgent`
  - Human decision makers (via WAIT_FOR_HUMAN).
"""

from typing import Dict, Any, Optional, List


def get_vector_context(
    category_id: Optional[str],
    dtp_stage: str,
    topic: str,
) -> Dict[str, Any]:
    """
    Retrieve read‑only, stage‑scoped context from the Vector Knowledge Layer.

    Args:
        category_id: Category being sourced (e.g., "CAT-01"), or None for generic guidance.
        dtp_stage: Current DTP stage (e.g., "DTP-01", "DTP-03").
        topic: High‑level topic, e.g. "category_strategy", "rfq_template",
               "negotiation_playbook", "dtp_procedure".

    Returns:
        A small, structured context dictionary that can be passed into
        agent prompts as **grounding information only**.

    NOTE:
        - This POC implementation returns illustrative placeholders only.
        - In a full system, this would call a vector store and perform
          filtered, policy‑governed retrieval.
    """
    context: Dict[str, Any] = {
        "category_id": category_id,
        "dtp_stage": dtp_stage,
        "topic": topic,
        "notes": [],
    }

    if topic == "dtp_procedure":
        context["notes"] = [
            "Follow DTP stage ordering and PolicyLoader constraints.",
            "SupervisorAgent owns routing and approvals; agents only propose.",
        ]
        context["content"] = "DTP procedures require stage-by-stage progression with Supervisor approval."
    elif topic == "category_strategy":
        context["notes"] = [
            "Use category strategy as background context only.",
            "Do not override encoded rules or enterprise policies.",
        ]
        context["content"] = f"Category {category_id} strategy context (for grounding reasoning only, not binding decisions)."
    elif topic == "rfq_template":
        context["notes"] = [
            "Templates provide structure for RFx documentation.",
            "All commercial terms still require human/legal approval.",
        ]
        context["content"] = {
            "sections": ["Overview", "Requirements", "Evaluation Criteria", "Timeline", "Terms & Conditions"],
            "structure": "Template-driven RFx with sections for category requirements and evaluation criteria.",
            "instructions": "Fill template sections with case-specific data. Do not invent commercial terms."
        }
    elif topic == "negotiation_playbook":
        context["notes"] = [
            "Playbooks provide negotiation heuristics and benchmarks.",
            "Do not make award decisions or enforce policy.",
        ]
        context["content"] = {
            "leverage_analysis": "Compare bid terms against market benchmarks and contract history.",
            "scenario_planning": "Prepare for common negotiation scenarios based on bid gaps.",
            "benchmark_guidance": "Reference historical pricing and terms as context only."
        }
    elif topic == "contract_clauses":
        context["notes"] = [
            "Clause snippets are for reference; they are not legal advice.",
            "Supervisor + humans decide which clauses to adopt.",
        ]
        context["content"] = {
            "standard_clauses": ["Service Levels", "Termination", "Payment Terms", "Compliance"],
            "guidance": "Use clause library as reference. Legal review required before adoption."
        }
    elif topic == "rollout_playbook":
        context["notes"] = [
            "Rollout playbooks provide structured implementation steps.",
            "Calculations are deterministic; LLM explains impacts only.",
        ]
        context["content"] = {
            "steps": ["Contract execution", "Supplier onboarding", "System integration", "Monitoring setup"],
            "kpis": ["Savings realization", "Service levels", "Compliance metrics"]
        }
    elif topic == "historical_cases":
        context["notes"] = [
            "Use past cases as qualitative reference, not as binding precedent.",
            "Never leak one customer's data into another customer's case.",
        ]
        context["content"] = f"Historical cases for category {category_id} (anonymized examples for pattern recognition only)."

    return context





