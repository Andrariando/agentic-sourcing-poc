"""
Streamlit app for Agentic AI Dynamic Sourcing Pipelines - Research POC
"""
import streamlit as st
import json
import os
import pandas as pd
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables - explicitly specify path to ensure .env is found
# Get the directory where app.py is located
app_dir = Path(__file__).parent.absolute()
env_path = app_dir / ".env"

# Load .env file if it exists
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Fallback: try loading from current working directory
    load_dotenv(override=True)

# Verify API key is loaded (for debugging)
if not os.getenv("OPENAI_API_KEY"):
    st.warning("⚠️ OPENAI_API_KEY not found. Please ensure your .env file is in the project root and contains: OPENAI_API_KEY=your_key_here")

# Import utilities
from utils.schemas import (
    Case, CaseSummary, Signal, HumanDecision, AgentActionLog,
    StrategyRecommendation, SupplierShortlist, NegotiationPlan, SignalAssessment,
    TriggerSource, CaseStatus, BudgetState, CacheMeta,
    DTPPolicyContext, SignalRegisterEntry, DecisionImpact,
    ClarificationRequest, RFxDraft, ContractExtraction, ImplementationPlan,
)
from utils.state import PipelineState
from utils.data_loader import (
    load_json_data, get_category, get_supplier, get_contract,
    get_performance, get_market_data, generate_signal_from_contract
)
from utils.dtp_stages import get_dtp_stage_display, get_dtp_stage_full
from utils.case_analysis import get_decision_signal, get_recommended_action, get_case_urgency
from utils.token_accounting import create_initial_budget_state
from graphs.workflow import get_workflow_graph
from agents.signal_agent import SignalInterpretationAgent
from utils.response_adapter import get_response_adapter
from utils.case_memory import CaseMemory, create_case_memory, update_memory_from_workflow_result

# Simple parser for HIL decisions issued via chat
def parse_hil_decision(user_intent: str) -> Optional[str]:
    """
    Map free‑text user responses to an explicit human decision.
    
    Designed for natural phrasing like:
    - "Yes, let's do RFx"
    - "Go ahead with your recommendation"
    - "No, I don't want to proceed"
    """
    intent = user_intent.strip().lower()

    approve_terms = [
        "approve",
        "approved",
        "proceed",
        "go ahead",
        "looks good",
        "accept",
        "sounds good",
        "sounds great",
        "let's do",
        "lets do",
        "let's go with",
        "lets go with",
        "i agree",
        "agree with",
        "yes",
        "yep",
        "ok",
        "okay",
    ]
    reject_terms = [
        "reject",
        "decline",
        "do not proceed",
        "don't proceed",
        "not ok",
        "disagree",
        "stop",
        "no,",
        "no.",
        "no ",
        "let's not",
        "lets not",
        "rather not",
        "i don't agree",
        "i disagree",
    ]

    if any(term in intent for term in approve_terms):
        return "Approve"
    if any(term in intent for term in reject_terms):
        return "Reject"
    return None

# Policy helper: derive default DTP policy context
def build_policy_context(dtp_stage: str) -> DTPPolicyContext:
    """Return a policy context for the given DTP stage (lightweight governor)."""
    allowed_transitions = {
        "DTP-01": ["DTP-02"],
        "DTP-02": ["DTP-03", "DTP-04"],
        "DTP-03": ["DTP-04"],
        "DTP-04": ["DTP-05"],
        "DTP-05": ["DTP-06"],
    }
    stage_checks = {
        "DTP-01": ["Ensure category strategy exists"],
        "DTP-02": ["FMV check", "Market localization"],
        "DTP-03": ["Supplier MCDM criteria defined"],
        "DTP-04": ["DDR/HCC flags resolved", "Compliance approvals"],
        "DTP-05": ["Contracting guardrails"],
        "DTP-06": ["Savings validation & reporting"],
    }
    human_required = {
        "DTP-01": ["High-impact strategy shifts"],
        "DTP-02": ["Approach to market decisions"],
        "DTP-04": ["Supplier award / negotiation mandate"],
        "DTP-06": ["Savings sign-off"],
    }
    return DTPPolicyContext(
        allowed_actions=allowed_transitions.get(dtp_stage, []),
        mandatory_checks=stage_checks.get(dtp_stage, []),
        human_required_for=human_required.get(dtp_stage, []),
    )

# Signal register seed
def initial_signal_register() -> list[SignalRegisterEntry]:
    return []

# MIT Palette
PRIMARY_COLOR = "#003A8F"
ACCENT_COLOR = "#A31F34"
TEXT_COLOR = "#4A4A4A"
SEPARATOR_COLOR = "#D9D9D9"
BG_COLOR = "#FFFFFF"

# Page config
st.set_page_config(
    page_title="Agentic Sourcing Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - Enterprise styling with lightweight design system
st.markdown(f"""
<style>
    /* Design tokens */
    :root {{
        --space-xs: 4px;
        --space-sm: 8px;
        --space-md: 12px;
        --space-lg: 16px;
        --space-xl: 24px;

        --radius-sm: 4px;
        --radius-md: 8px;
        --radius-lg: 12px;

        --font-size-xs: 0.75rem;
        --font-size-sm: 0.85rem;
        --font-size-md: 0.9rem;
        --font-size-lg: 1rem;
        --font-size-xl: 1.25rem;

        --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.08);
        --shadow-md: 0 4px 8px rgba(15, 23, 42, 0.10);
    }}

    /* Page background */
    body {{
        background-color: #F3F4F6;
    }}

    /* Utility / text colors */
    .primary-color {{ color: {PRIMARY_COLOR}; }}
    .accent-color {{ color: {ACCENT_COLOR}; }}
    .metric-label {{ font-size: var(--font-size-xs); color: {TEXT_COLOR}; }}

    /* Generic cards */
    .card {{
        background: #FFFFFF;
        border-radius: var(--radius-md);
        padding: var(--space-md) var(--space-lg);
        box-shadow: var(--shadow-sm);
        border: 1px solid #E5E7EB;
        margin-bottom: var(--space-md);
    }}
    .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: var(--space-sm);
        font-weight: 600;
        color: #111827;
        font-size: var(--font-size-lg);
    }}
    .card-subtitle {{
        font-size: var(--font-size-sm);
        color: #6B7280;
        margin-bottom: var(--space-sm);
    }}
    .card-body {{
        font-size: var(--font-size-md);
        color: #111827;
    }}

    /* Hero card for case header */
    .card-hero {{
        background: linear-gradient(135deg, #EEF2FF 0%, #F9FAFB 60%);
        border-color: #CBD5F5;
        max-width: 100%;
        box-sizing: border-box;
        margin-right: var(--space-md);  /* keep clear of Copilot column divider */
    }}
    .card-hero-main {{
        display: flex;
        justify-content: space-between;
        gap: var(--space-lg);
        align-items: flex-start;
        flex-wrap: wrap;
    }}
    .card-hero-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: #111827;
    }}
    .card-hero-meta {{
        font-size: var(--font-size-sm);
        color: #4B5563;
    }}
    .card-hero-metrics {{
        text-align: right;
        font-size: var(--font-size-sm);
        color: #4B5563;
    }}

    /* Metric tiles (used on main page and activity summary) */
    .metric-row {{
        display: flex;
        gap: var(--space-lg);
        flex-wrap: wrap;
    }}
    .metric-tile {{
        flex: 0 1 210px;
        padding: var(--space-sm) var(--space-md);
        border-radius: var(--radius-md);
        background: #F9FAFB;
        border: 1px solid #E5E7EB;
        box-shadow: var(--shadow-sm);
    }}
    .metric-tile-label {{
        font-size: var(--font-size-xs);
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        margin-bottom: 2px;
    }}
    .metric-tile-value {{
        font-size: var(--font-size-lg);
        font-weight: 600;
        color: #111827;
    }}
    .metric-tile-caption {{
        font-size: var(--font-size-xs);
        color: #6B7280;
        margin-top: 2px;
    }}

    /* Pills / badges / chips */
    .pill {{
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: var(--font-size-xs);
        font-weight: 500;
        border: 1px solid transparent;
        gap: 4px;
        white-space: nowrap;
    }}
    .pill-primary {{
        background-color: #EEF2FF;
        color: #3730A3;
        border-color: #C7D2FE;
    }}
    .pill-neutral {{
        background-color: #F3F4F6;
        color: #374151;
        border-color: #E5E7EB;
    }}
    .pill-success {{
        background-color: #DCFCE7;
        color: #166534;
        border-color: #BBF7D0;
    }}
    .pill-warning {{
        background-color: #FEF9C3;
        color: #92400E;
        border-color: #FDE68A;
    }}
    .pill-danger {{
        background-color: #FEE2E2;
        color: #B91C1C;
        border-color: #FCA5A5;
    }}

    .badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: var(--font-size-xs);
        font-weight: 500;
        background-color: #F3F4F6;
        color: #4B5563;
    }}

    .chip-filter-summary {{
        font-size: var(--font-size-xs);
        color: #6B7280;
        margin-top: 2px;
    }}

    /* Status / decision badges (hook existing mappings into pill/badge system) */
    .status-pill {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 500;
    }}
    .status-open {{
        background-color: #E3F2FD;
        color: #1976D2;
    }}
    .status-in-progress {{
        background-color: #E8F5E9;
        color: #388E3C;
    }}
    .status-closed {{
        background-color: #F5F5F5;
        color: #616161;
    }}

    /* App header - compact strong navy band */
    .app-header {{
        background: {PRIMARY_COLOR};
        padding: 8px 24px 10px 24px;
        border-bottom: 1px solid #0F172A;
        box-shadow: var(--shadow-sm);
        margin-bottom: 8px;
    }}
    .app-header-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
    }}
    .app-header-left {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }}
    .app-header-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: #FFFFFF;
    }}
    .app-header-pill {{
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(255,255,255,0.10);
        border: 1px solid rgba(255,255,255,0.35);
        color: #FFFFFF;
        font-size: var(--font-size-xs);
        font-weight: 500;
        white-space: nowrap;
    }}
    .app-header-tabs {{
        display: flex;
        gap: 8px;
        align-items: center;
    }}
    .app-header-tab {{
        padding: 3px 10px;
        border-radius: 999px;
        font-size: var(--font-size-xs);
        color: rgba(255,255,255,0.8);
        background: transparent;
        border: 1px solid transparent;
    }}
    .app-header-tab-active {{
        color: {PRIMARY_COLOR};
        background: #FFFFFF;
        border-color: #E5E7EB;
        font-weight: 500;
    }}
    .app-header-separator {{
        color: rgba(255,255,255,0.6);
        font-size: var(--font-size-xs);
    }}
    .app-header-meta {{
        margin-top: 2px;
        font-size: var(--font-size-xs);
        color: rgba(255,255,255,0.78);
    }}

    /* Layout containers */
    .content-shell {{
        margin: 0 24px 24px 24px;
        padding: 0 20px 16px 20px;
        background: #FFFFFF;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-md);
    }}
    .main-content {{
        margin-top: 0;
        padding-top: 0;
        margin-bottom: 24px;
    }}
    .column-center {{
        padding: 10px 15px;
        margin-right: 10px;
        border-right: 2px solid #E0E0E0;
    }}
    .column-right {{
        background-color: #FAFAFA;
        padding: 10px 15px;
        border-radius: 4px;
        margin-left: 10px;
        border-left: 2px solid #E0E0E0;
    }}

    /* Cases table */
    .cases-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: var(--font-size-md);
    }}
    .cases-table-header {{
        background-color: #F5F5F5;
        border-bottom: 2px solid {SEPARATOR_COLOR};
        padding: 12px 8px;
        font-weight: 600;
        color: {TEXT_COLOR};
        text-align: left;
        font-size: var(--font-size-sm);
    }}
    .cases-table-row {{
        border-bottom: 1px solid {SEPARATOR_COLOR};
        transition: background-color 0.15s ease, box-shadow 0.15s ease;
    }}
    .cases-table-row:hover {{
        background-color: #FAFAFA;
        box-shadow: inset 3px 0 0 {PRIMARY_COLOR};
    }}
    .cases-table-cell {{
        padding: 12px 8px;
        vertical-align: middle;
    }}

    /* Chat */
    .chat-message {{
        padding: 8px 12px !important;
        margin: 8px 0 !important;
        border-radius: 8px;
        max-width: 85%;
        font-size: var(--font-size-sm);
    }}
    .chat-user {{
        background-color: #E3F2FD;
        margin-left: auto;
        text-align: right;
    }}
    .chat-assistant {{
        background-color: #F5F5F5;
        margin-right: auto;
    }}
    .chat-container {{
        padding: 10px;
        background-color: #FAFAFA;
        border-radius: 8px;
        margin-bottom: 10px;
        border: 1px solid #E0E0E0;
    }}

    /* DTP stepper */
    .dtp-stepper {{
        display: flex;
        gap: var(--space-sm);
        margin-bottom: var(--space-md);
        flex-wrap: wrap;
    }}
    .dtp-step {{
        padding: 4px 10px;
        border-radius: 999px;
        font-size: var(--font-size-xs);
        border: 1px solid #E5E7EB;
        color: #6B7280;
        background: #F9FAFB;
    }}
    .dtp-step-active {{
        border-color: #2563EB;
        background: #DBEAFE;
        color: #1D4ED8;
        font-weight: 600;
    }}

    /* Copilot card */
    .card-copilot {{
        background: #FFFFFF;
        border-radius: var(--radius-md);
        border: 1px solid #E5E7EB;
        box-shadow: var(--shadow-sm);
        padding: var(--space-sm) var(--space-md);
    }}

    /* Activity log */
    .activity-log-entry {{
        background-color: #F9F9F9;
        border-left: 4px solid {PRIMARY_COLOR};
        padding: 15px;
        margin: 10px 0;
        border-radius: 4px;
    }}

    /* Global spacing tweaks */
    .element-container {{
        margin-bottom: 0.5rem !important;
    }}
    h2, h3 {{
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }}
    hr {{
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }}
    /* Hide "Press Enter to submit form" text in forms */
    .stForm > div > div > div > small {{
        display: none !important;
    }}
    /* Alternative selector for form help text */
    form small {{
        display: none !important;
    }}
    /* Hide Streamlit form help text - comprehensive selectors */
    div[data-testid="stForm"] small {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    /* Hide all small text elements within forms */
    .stForm small,
    form .stTextInput + small,
    .element-container:has(form) small {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        opacity: 0 !important;
        font-size: 0 !important;
        line-height: 0 !important;
    }}
    /* Target the specific help text that appears below text inputs in forms */
    div[data-testid="stTextInput"] + div small,
    div[data-testid="stTextInput"] ~ small {{
        display: none !important;
        visibility: hidden !important;
    }}
    /* Most aggressive: Hide ALL small elements in forms */
    form small,
    [data-testid="stForm"] small,
    .stForm small {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        font-size: 0 !important;
        line-height: 0 !important;
        opacity: 0 !important;
    }}
    .stColumns > div {{
        gap: 0 !important;
    }}
    /* Enterprise Cases Table Styling */
    .cases-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }}
    .cases-table-header {{
        background-color: #F5F5F5;
        border-bottom: 2px solid {SEPARATOR_COLOR};
        padding: 12px 8px;
        font-weight: 600;
        color: {TEXT_COLOR};
        text-align: left;
    }}
    .cases-table-row {{
        border-bottom: 1px solid {SEPARATOR_COLOR};
        transition: background-color 0.15s ease;
    }}
    .cases-table-row:hover {{
        background-color: #FAFAFA;
    }}
    .cases-table-cell {{
        padding: 12px 8px;
        vertical-align: middle;
    }}
    .decision-signal-badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
        white-space: nowrap;
    }}
    .signal-high {{
        background-color: #FFEBEE;
        color: #C62828;
        border: 1px solid #EF5350;
    }}
    .signal-medium {{
        background-color: #FFF3E0;
        color: #E65100;
        border: 1px solid #FF9800;
    }}
    .signal-low {{
        background-color: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #66BB6A;
    }}
    .signal-info {{
        background-color: #E3F2FD;
        color: #1565C0;
        border: 1px solid #42A5F5;
    }}
    .action-badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        color: {PRIMARY_COLOR};
        background-color: #F5F5F5;
        border: 1px solid {SEPARATOR_COLOR};
    }}
    .timestamp-cell {{
        font-size: 0.85rem;
        color: #666;
        font-family: 'Courier New', monospace;
    }}
    .case-id-link {{
        color: {PRIMARY_COLOR};
        text-decoration: none;
        font-weight: 500;
        cursor: pointer;
    }}
    .case-id-link:hover {{
        text-decoration: underline;
    }}
    .status-badge-enterprise {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 500;
    }}
    .status-open {{
        background-color: #E3F2FD;
        color: #1976D2;
    }}
    .status-in-progress {{
        background-color: #E8F5E9;
        color: #388E3C;
    }}
    .status-waiting {{
        background-color: #FFF3E0;
        color: #F57C00;
    }}
    .status-closed {{
        background-color: #F5F5F5;
        color: #616161;
    }}
    .status-rejected {{
        background-color: #FFEBEE;
        color: #C62828;
    }}
</style>
<script>
    // Global script to hide form help text - runs on every page load
    (function() {{
        function removeFormHelpText() {{
            // Remove all small elements that might contain form help text
            document.querySelectorAll('small').forEach(el => {{
                const text = (el.textContent || el.innerText || '').toLowerCase();
                if (text.includes('press enter') || text.includes('submit form') || 
                    text.includes('enter to') || text.includes('to submit')) {{
                    el.remove();
                }}
            }});
        }}
        
        // Run when DOM is ready
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', removeFormHelpText);
        }} else {{
            removeFormHelpText();
        }}
        
        // Run after a delay
        setTimeout(removeFormHelpText, 100);
        setTimeout(removeFormHelpText, 500);
        
        // Watch for new elements
        const observer = new MutationObserver(removeFormHelpText);
        observer.observe(document.body, {{ childList: true, subtree: true }});
    }})();
</script>
""", unsafe_allow_html=True)


# Session state initialization
if "cases" not in st.session_state:
    st.session_state.cases: Dict[str, Case] = {}
    # Load seed cases
    seed_cases = load_json_data("cases_seed.json")
    for case_data in seed_cases:
        # Map 'summary' field to 'summary_text' for CaseSummary schema
        case_summary_data = case_data.copy()
        if "summary" in case_summary_data and "summary_text" not in case_summary_data:
            case_summary_data["summary_text"] = case_summary_data.pop("summary")
        case_summary = CaseSummary(**case_summary_data)
        # Generate timestamps - use created_date if available, otherwise use current time
        try:
            # Try to parse created_date and create ISO timestamp
            created_date_obj = datetime.strptime(case_data["created_date"], "%Y-%m-%d")
            created_ts = created_date_obj.isoformat()
        except:
            # Fallback to current time
            created_ts = datetime.now().isoformat()
        updated_ts = created_ts
        
        case = Case(
            case_id=case_data["case_id"],
            name=case_data.get("name", case_data["case_id"]),
            category_id=case_data["category_id"],
            contract_id=case_data.get("contract_id"),
            supplier_id=case_data.get("supplier_id"),
            dtp_stage=case_data["dtp_stage"],
            trigger_source=case_data["trigger_source"],
            user_intent=None,
            created_date=case_data["created_date"],
            updated_date=case_data.get("updated_date", case_data["created_date"]),
            created_timestamp=created_ts,
            updated_timestamp=updated_ts,
            status=case_data["status"],
            summary=case_summary,
            latest_agent_output=None,
            latest_agent_name=None,
            activity_log=[],
            human_decision=None
        )
        st.session_state.cases[case_data["case_id"]] = case

if "signals" not in st.session_state:
    st.session_state.signals: list[Dict[str, Any]] = []
    # Generate simple, read-only **signals** from contracts.
    # This mirrors the behavior of the Sourcing Signal Layer:
    # - It surfaces renewal / risk signals so humans can initiate cases.
    # - It does NOT renew, renegotiate, or terminate contracts by itself.
    contracts = load_json_data("contracts.json")
    for contract in contracts:
        if contract["expiry_days"] <= 90:  # Only show near-term expiries
            signal = generate_signal_from_contract(contract["contract_id"])
            st.session_state.signals.append(signal)

if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None

if "workflow_state" not in st.session_state:
    st.session_state.workflow_state: Optional[PipelineState] = None


def create_new_case(category_id: str, trigger_source: str, contract_id: Optional[str] = None, supplier_id: Optional[str] = None) -> str:
    """Create a new case"""
    # Generate case ID
    existing_ids = [c.case_id for c in st.session_state.cases.values()]
    case_num = len(existing_ids) + 1
    case_id = f"CASE-{case_num:04d}"
    
    category = get_category(category_id)
    case_name = f"New {category['name'] if category else category_id} Case"
    
    case_summary = CaseSummary(
        case_id=case_id,
        category_id=category_id,
        contract_id=contract_id,
        supplier_id=supplier_id,
        dtp_stage="DTP-01",
        trigger_source=trigger_source,
        status="In Progress",
        created_date=datetime.now().strftime("%Y-%m-%d"),
        summary_text=f"New case for category {category_id}",
        key_findings=[],
        recommended_action=None
    )
    
    # Generate timestamps
    now_iso = datetime.now().isoformat()
    now_date = datetime.now().strftime("%Y-%m-%d")
    
    case = Case(
        case_id=case_id,
        name=case_name,
        category_id=category_id,
        contract_id=contract_id,
        supplier_id=supplier_id,
        dtp_stage="DTP-01",
        trigger_source=trigger_source,
        user_intent=None,
        created_date=now_date,
        updated_date=now_date,
        created_timestamp=now_iso,
        updated_timestamp=now_iso,
        status="In Progress",
        summary=case_summary,
        latest_agent_output=None,
        latest_agent_name=None,
        activity_log=[],
        human_decision=None
    )
    
    st.session_state.cases[case_id] = case
    return case_id


def is_status_query(user_intent: str) -> bool:
    """Detect if user is asking for status/progress information (not action recommendations)"""
    intent_lower = user_intent.lower()
    
    # Explicit status/progress keywords
    status_keywords = [
        "progress", "status", "update", "latest", "current", "state",
        "check status", "show status", "tell status", "what's the status",
        "where are we", "how far", "what stage", "current stage"
    ]
    
    # Action/recommendation keywords that should NOT be treated as status queries
    action_keywords = [
        "what should", "what do", "what are you", "recommend", "suggest", 
        "next step", "next action", "what to do", "how to proceed",
        "should we", "can we", "let's", "run", "execute", "start", "begin"
    ]
    
    # If it contains action keywords, it's NOT a status query
    if any(keyword in intent_lower for keyword in action_keywords):
        return False
    
    # Check for explicit status keywords
    return any(keyword in intent_lower for keyword in status_keywords)


def generate_status_response(case: Case) -> str:
    """
    Generate a natural, conversational response about case status.

    UX framing:
    - (1) What has been evaluated so far (grounded in case + activity_log)
    - (2) What is allowed next (per DTP stage + policy)
    - (3) What is suggested (non-binding, not an autonomous decision)
    - (4) What the human can do next (explicit choice / decision point)
    """
    from utils.dtp_stages import get_dtp_stage_display
    
    response_parts = []
    
    # Start with a friendly, Supervisor-like narration
    response_parts.append(f"Here's the latest update on **{case.case_id}** from the sourcing workflow:")
    
    # Current status in natural language
    stage_display = get_dtp_stage_display(case.dtp_stage)
    if case.status == "Waiting for Human Decision":
        response_parts.append(f"⏸️ The case is currently **{case.status.lower()}** - waiting for your review. We're at the **{stage_display}** stage ({case.dtp_stage}).")
    elif case.status == "In Progress":
        response_parts.append(f"🔄 The case is **{case.status.lower()}** and we're working through the **{stage_display}** stage ({case.dtp_stage}).")
    else:
        response_parts.append(f"The case status is **{case.status}** and we're at the **{stage_display}** stage ({case.dtp_stage}).")
    
    # Latest activity in conversational tone
    if case.latest_agent_output:
        if isinstance(case.latest_agent_output, StrategyRecommendation):
            response_parts.append(f"📊 I've completed a strategy analysis and recommend **{case.latest_agent_output.recommended_strategy}**.")
            if case.latest_agent_output.rationale:
                reasons = case.latest_agent_output.rationale[:2]
                response_parts.append(f"The main reasons are: {', '.join(reasons)}.")
        elif isinstance(case.latest_agent_output, SupplierShortlist):
            supplier_count = len(case.latest_agent_output.shortlisted_suppliers)
            response_parts.append(f"🔍 I've evaluated the market and shortlisted **{supplier_count} suppliers**.")
            if case.latest_agent_output.top_choice_supplier_id:
                response_parts.append(f"My top recommendation is **{case.latest_agent_output.top_choice_supplier_id}**.")
        elif isinstance(case.latest_agent_output, RFxDraft):
            sections_count = len(case.latest_agent_output.rfx_sections)
            response_parts.append(f"📄 I've created an RFx draft with **{sections_count} sections** ready for your review.")
        elif isinstance(case.latest_agent_output, NegotiationPlan):
            response_parts.append(f"💼 I've prepared a negotiation plan with **{len(case.latest_agent_output.negotiation_objectives)} key objectives** ready for your review.")
        elif isinstance(case.latest_agent_output, ContractExtraction):
            terms_count = len(case.latest_agent_output.extracted_terms)
            response_parts.append(f"📋 I've extracted **{terms_count} contract terms** ready for contracting review.")
        elif isinstance(case.latest_agent_output, ImplementationPlan):
            steps_count = len(case.latest_agent_output.rollout_steps)
            response_parts.append(f"🚀 I've created an implementation plan with **{steps_count} rollout steps** ready for your review.")
    
    # Recent activity
    if case.activity_log:
        recent_activity = case.activity_log[-1]
        activity_date = recent_activity.timestamp[:10]
        response_parts.append(f"📝 The most recent activity was on {activity_date}: {recent_activity.agent_name} completed '{recent_activity.task_name}'.")
    
    # Next steps in natural language, explicitly calling out human role
    if case.status == "Waiting for Human Decision":
        response_parts.append("👤 **Your decision needed:** Please review the latest output and let me know if you'd like to approve, edit, or reject it. I won't proceed without your call.")
    elif case.dtp_stage == "DTP-01":
        response_parts.append("➡️ **What's next:** Once you review the strategy recommendation, we can move forward with supplier evaluation.")
    elif case.dtp_stage in ["DTP-03", "DTP-04"]:
        response_parts.append("➡️ **What's next:** We're actively evaluating suppliers. I'll keep you updated as we progress.")
    
    return " ".join(response_parts)


def generate_recommendation_response(case: Case) -> str:
    """Generate a response with actionable recommendations"""
    from utils.dtp_stages import get_dtp_stage_display
    from utils.case_analysis import get_recommended_action
    
    response_parts = []
    
    # Get recommended action
    action_label, action_type, action_rationale = get_recommended_action(case)
    
    if action_label:
        response_parts.append(f"Based on the current state of **{case.case_id}**, I recommend:")
        response_parts.append(f"**{action_label}**")
        
        if action_rationale:
            response_parts.append("Here's why:")
            for reason in action_rationale[:3]:
                response_parts.append(f"• {reason}")
        
        # Add context about current stage
        stage_display = get_dtp_stage_display(case.dtp_stage)
        response_parts.append(f"\nWe're currently at the **{stage_display}** stage ({case.dtp_stage}), so this action aligns with our workflow.")
        
        # Offer to execute
        if action_type in ["strategy_analysis", "market_scan", "supplier_evaluation", "negotiation"]:
            response_parts.append(f"\nWould you like me to **{action_label.lower()}** now?")
    else:
        response_parts.append(f"I don't have a specific recommendation for **{case.case_id}** at this moment.")
        response_parts.append("Would you like me to analyze the case and provide a recommendation?")
    
    return " ".join(response_parts)


def build_strategy_chat_response(case: Case, user_intent: str) -> str:
    """
    Build a richer, less robotic chat response for a strategy recommendation.
    
    Uses case stage + rationale to:
    - Acknowledge the user's question
    - Explain the recommendation in bullets
    - Make it clear what happens next
    - Invite the user to collaborate / adjust
    """
    from utils.dtp_stages import get_dtp_stage_display

    rec = case.latest_agent_output  # type: ignore[assignment]
    stage_display = get_dtp_stage_display(case.dtp_stage)
    parts: list[str] = []

    # 1) Meet the user where they are
    intent_lower = user_intent.lower()
    if any(word in intent_lower for word in ["why", "explain", "rationale", "because"]):
        parts.append(
            f"Happy to walk you through my thinking on **{case.case_id}** "
            f"at the **{stage_display}** stage ({case.dtp_stage})."
        )
    elif any(word in intent_lower for word in ["update", "progress", "latest", "where are we"]):
        parts.append(
            f"I've just re‑analyzed the case **{case.case_id}** using the latest contract, performance, "
            f"and market data for the **{stage_display}** stage ({case.dtp_stage})."
        )
    else:
        parts.append(
            f"I've taken a fresh look at **{case.case_id}** in the context of the **{stage_display}** stage "
            f"({case.dtp_stage})."
        )

    # 2) Clear recommendation
    parts.append(f"My current recommendation is **{rec.recommended_strategy}** for this case.")

    # 3) Human‑readable rationale as bullets
    if getattr(rec, "rationale", None):
        reasons = rec.rationale[:3]
        if reasons:
            parts.append("Here are the key factors driving this recommendation:")
            for r in reasons:
                parts.append(f"- {r}")

    # 4) Confidence framing
    if getattr(rec, "confidence", None):
        parts.append(
            f"Overall, I'm about **{int(rec.confidence * 100)}%** confident in this path "
            "given the current data."
        )

    # 5) Stage‑aware, collaborative next step
    if case.status == "Waiting for Human Decision":
        parts.append(
            "To move forward, I need your call: does this direction fit your objectives, or are there "
            "constraints I should factor in before we proceed?"
        )
    elif case.dtp_stage == "DTP-01":
        parts.append(
            "If this looks right, I can move us into supplier evaluation next. "
            "If you have specific preferences (e.g., incumbent bias, timelines, budget limits), "
            "tell me and I'll adjust the strategy."
        )
    elif case.dtp_stage in ["DTP-03", "DTP-04"]:
        parts.append(
            "From here we can translate this into concrete supplier actions and negotiation steps. "
            "Would you like me to focus on refining the shortlist, or start shaping the negotiation plan?"
        )
    else:
        parts.append(
            "If this doesn't fully resonate, let me know what you'd change or what additional context "
            "I should consider, and I'll revise the recommendation."
        )

    return "\n\n".join(parts)


def run_copilot(case_id: str, user_intent: str, use_tier_2: bool = False):
    """Run copilot workflow"""
    case = st.session_state.cases[case_id]
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY environment variable not set. Please set it in your .env file or environment.")
        return
    
    # Initialize **case-scoped conversational memory**.
    # - chat_responses is keyed by case_id to avoid cross-case leakage.
    # - This is append-only and auditable within the current session.
    # - It complements (but does NOT replace) PipelineState and CaseSummary.
    if "chat_responses" not in st.session_state:
        st.session_state.chat_responses = {}
    if case_id not in st.session_state.chat_responses:
        st.session_state.chat_responses[case_id] = []
    
    # Add user message immediately to chat history (before processing).
    # The Supervisor + agents operate on structured state; the chat layer
    # simply narrates what has already been determined to be allowed.
    st.session_state.chat_responses[case_id].append({
        "user": user_intent,
        "assistant": "🤔 Let me process that for you...",
        "timestamp": datetime.now().isoformat(),
        "pending": True,  # Mark as pending
        "workflow_started": False  # Track if workflow actually started
    })

    # If the workflow is paused waiting for human, allow chat-based approval/rejection
    pending_state = st.session_state.get("workflow_state")
    decision_intent = parse_hil_decision(user_intent)
    if pending_state and pending_state.get("case_id") == case_id and pending_state.get("waiting_for_human") and decision_intent:
        try:
            graph = get_workflow_graph()
            pending_state["human_decision"] = HumanDecision(
                decision=decision_intent,
                reason=user_intent,
                edited_fields={},
                timestamp=datetime.now().isoformat(),
                user_id=None
            )
            final_state = graph.invoke(pending_state, {"recursion_limit": 30})

            # Update case
            case.latest_agent_output = final_state.get("latest_agent_output")
            case.latest_agent_name = final_state.get("latest_agent_name")
            case.activity_log.extend(final_state.get("activity_log", []))
            case.summary = final_state["case_summary"]
            case.dtp_stage = final_state["dtp_stage"]
            case.human_decision = pending_state["human_decision"]
            now = datetime.now()
            case.updated_date = now.strftime("%Y-%m-%d")
            case.updated_timestamp = now.isoformat()
            case.status = "In Progress" if decision_intent == "Approve" else "Rejected"

            st.session_state.workflow_state = final_state
            st.session_state.cases[case_id] = case

            # Update chat with outcome
            assistant_msg = f"✅ Decision **{decision_intent}** recorded and processed."
            if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
                st.session_state.chat_responses[case_id][-1] = {
                    "user": user_intent,
                    "assistant": assistant_msg,
                    "timestamp": datetime.now().isoformat(),
                    "pending": False,
                    "workflow_started": False
                }
            st.rerun()
            return
        except Exception as e:
            if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
                st.session_state.chat_responses[case_id][-1] = {
                    "user": user_intent,
                    "assistant": f"❌ Error processing decision: {e}",
                    "timestamp": datetime.now().isoformat(),
                    "pending": False
                }
            st.rerun()
            return
    
    # Check if this is a status/progress query (not action/recommendation)
    intent_lower = user_intent.lower()
    is_recommendation_query = any(keyword in intent_lower for keyword in [
        "what should", "what do", "what are you", "recommend", "suggest", 
        "next step", "next action", "what to do", "how to proceed",
        "should we", "can we", "what are you recommending"
    ])
    
    if is_status_query(user_intent) and not is_recommendation_query:
        # Generate status response without running workflow
        status_response = generate_status_response(case)
        case.user_intent = user_intent
        
        # Update the pending message with the actual response
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            st.session_state.chat_responses[case_id][-1] = {
                "user": user_intent,
                "assistant": status_response,
                "timestamp": datetime.now().isoformat()
            }
        
        st.session_state.cases[case_id] = case
        st.rerun()
        return
    
    # Handle recommendation queries - provide actionable response
    if is_recommendation_query:
        recommendation_response = generate_recommendation_response(case)
        case.user_intent = user_intent
        
        # Update the pending message with the actual response
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            st.session_state.chat_responses[case_id][-1] = {
                "user": user_intent,
                "assistant": recommendation_response,
                "timestamp": datetime.now().isoformat()
            }
        
        st.session_state.cases[case_id] = case
        st.rerun()
        return
    
    # Initialize workflow state
    # Use existing agent output if available (for context)
    latest_agent_output = case.latest_agent_output
    latest_agent_name = case.latest_agent_name
    
    workflow_state: PipelineState = {
        "case_id": case.case_id,
        "dtp_stage": case.dtp_stage,
        "trigger_source": case.trigger_source,
        "user_intent": user_intent,
        "case_summary": case.summary,
        "latest_agent_output": latest_agent_output,  # Preserve existing output for context
        "latest_agent_name": latest_agent_name,
        "activity_log": [],
        "human_decision": None,
        "budget_state": create_initial_budget_state(),
        "cache_meta": CacheMeta(cache_hit=False, cache_key=None, input_hash=None, schema_version="1.0"),
        "error_state": None,
        "waiting_for_human": False,
        "use_tier_2": use_tier_2,
        "visited_agents": [],  # Track visited agents to prevent loops
        "iteration_count": 0,  # Track Supervisor iterations
        "dtp_policy_context": build_policy_context(case.dtp_stage),
        "signal_register": initial_signal_register(),
    }
    
    # Store tier preference for agent initialization
    workflow_state["use_tier_2"] = use_tier_2
    
    # Mark workflow as started in chat response
    if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
        st.session_state.chat_responses[case_id][-1]["workflow_started"] = True
        st.session_state.chat_responses[case_id][-1]["assistant"] = "🔄 **Workflow Started**\n\nInitializing agents and analyzing case..."
    
    try:
        # Run workflow
        graph = get_workflow_graph()
        # Increased recursion limit to handle Supervisor → Agent → Supervisor cycles
        # With loop detection, this should be sufficient
        config = {"recursion_limit": 30}  # Reduced from 50 since we have loop detection
        
        # Update chat with workflow progress
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            st.session_state.chat_responses[case_id][-1]["assistant"] = "🔄 **Executing Workflow**\n\n• Supervisor analyzing case state\n• Determining next agent to run\n• Processing..."
        
        # Invoke workflow
        final_state = graph.invoke(workflow_state, config)
        
        # Update chat with completion status
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            agents_called = [log.agent_name for log in final_state.get("activity_log", [])]
            unique_agents = list(set(agents_called))
            agent_summary = ", ".join(unique_agents) if unique_agents else "No agents"
            st.session_state.chat_responses[case_id][-1]["assistant"] = f"✅ **Workflow Completed**\n\n• Agents called: {agent_summary}\n• Total actions: {len(final_state.get('activity_log', []))}\n• Processing results..."
        
        # Update case with results
        case.latest_agent_output = final_state.get("latest_agent_output")
        case.latest_agent_name = final_state.get("latest_agent_name")
        case.activity_log.extend(final_state.get("activity_log", []))
        case.summary = final_state["case_summary"]
        case.dtp_stage = final_state["dtp_stage"]
        now = datetime.now()
        case.updated_date = now.strftime("%Y-%m-%d")
        case.updated_timestamp = now.isoformat()
        case.user_intent = user_intent
        
        if final_state.get("waiting_for_human"):
            case.status = "Waiting for Human Decision"
        
        # Generate conversational response for chat.
        # UX PRINCIPLE:
        # - SupervisorAgent is the conceptual narrator of the workflow.
        # - The chat never decides what happens next; it explains
        #   what the Supervisor + policies have already allowed.
        if "chat_responses" not in st.session_state:
            st.session_state.chat_responses = {}
        if case_id not in st.session_state.chat_responses:
            st.session_state.chat_responses[case_id] = []
        
        # PHASE 2 - OBJECTIVE A: Update case memory from workflow result
        case_memory = final_state.get("case_memory")
        if case_memory is None:
            case_memory = create_case_memory(case_id)
        
        if case.latest_agent_output and case.latest_agent_name:
            update_memory_from_workflow_result(
                case_memory,
                case.latest_agent_name,
                case.latest_agent_output,
                user_intent=user_intent
            )
        
        # Store memory in session state for persistence within session
        if "case_memories" not in st.session_state:
            st.session_state.case_memories = {}
        st.session_state.case_memories[case_id] = case_memory
        
        # PHASE 2 - OBJECTIVE E: Get detected contradictions
        detected_contradictions = final_state.get("detected_contradictions", [])
        
        # PHASE 2 - OBJECTIVE B: Use ResponseAdapter for response generation
        response_adapter = get_response_adapter()
        case_state_dict = {
            "case_id": case.case_id,
            "dtp_stage": case.dtp_stage,
            "status": case.status,
            "category_id": case.category_id,
        }
        
        # Create natural, conversational response based on agent output
        assistant_response = ""
        if case.latest_agent_output:
            if isinstance(case.latest_agent_output, StrategyRecommendation):
                # Use richer, stage‑aware, collaborative phrasing
                assistant_response = build_strategy_chat_response(case, user_intent)
            elif isinstance(case.latest_agent_output, SupplierShortlist):
                supplier_count = len(case.latest_agent_output.shortlisted_suppliers)
                
                # Check if this is a fallback error response
                is_error = (supplier_count == 0 and 
                           ("LLM" in case.latest_agent_output.comparison_summary or 
                            "error" in case.latest_agent_output.comparison_summary.lower() or
                            "Fallback" in case.latest_agent_output.comparison_summary))
                
                if is_error:
                    # Error case - provide helpful troubleshooting message
                    assistant_response = "⚠️ I encountered an issue while evaluating suppliers. "
                    assistant_response += f"**Error:** {case.latest_agent_output.recommendation}\n\n"
                    if "LLM" in case.latest_agent_output.comparison_summary:
                        assistant_response += "**Details:** " + case.latest_agent_output.comparison_summary + "\n\n"
                    assistant_response += "**Possible causes:**\n"
                    assistant_response += "• OpenAI API key not configured or invalid\n"
                    assistant_response += "• Network connectivity issue\n"
                    assistant_response += "• API rate limit reached\n\n"
                    assistant_response += "Please check your API configuration and try again."
                elif supplier_count == 0:
                    # No suppliers found but no error
                    assistant_response = f"I've completed the supplier evaluation for **{case.category_id}**. "
                    assistant_response += f"**{case.latest_agent_output.recommendation}**\n\n"
                    assistant_response += "This may be due to strict eligibility requirements or performance thresholds. "
                    assistant_response += "Would you like me to review the requirements or adjust the criteria?"
                else:
                    # Success case
                    assistant_response = f"Perfect! I've completed the supplier evaluation. I've identified and analyzed **{supplier_count} qualified suppliers** for this category."
                    if case.latest_agent_output.top_choice_supplier_id:
                        assistant_response += f" Based on my analysis, **{case.latest_agent_output.top_choice_supplier_id}** stands out as the top recommendation."
                    if case.latest_agent_output.comparison_summary:
                        assistant_response += f" {case.latest_agent_output.comparison_summary[:100]}..."
                    assistant_response += " Would you like me to prepare a detailed comparison or start the negotiation process?"
            elif isinstance(case.latest_agent_output, RFxDraft):
                sections_count = len(case.latest_agent_output.rfx_sections)
                completeness = case.latest_agent_output.completeness_check
                assistant_response = f"I've created an RFx draft with **{sections_count} sections** based on the template and category requirements."
                if completeness.get("all_sections_filled"):
                    assistant_response += " All required sections have been filled."
                else:
                    assistant_response += " Some sections may need additional review."
                assistant_response += " The draft is ready for your review. Would you like me to proceed with supplier evaluation next?"
            elif isinstance(case.latest_agent_output, NegotiationPlan):
                objectives_count = len(case.latest_agent_output.negotiation_objectives)
                assistant_response = f"Excellent! I've prepared a comprehensive negotiation plan with **{objectives_count} key objectives**."
                if case.latest_agent_output.leverage_points:
                    assistant_response += f" I've identified several leverage points we can use: {', '.join(case.latest_agent_output.leverage_points[:2])}."
                assistant_response += " The plan is ready for your review. Policy still requires your approval before any negotiation is initiated."
            elif isinstance(case.latest_agent_output, ContractExtraction):
                terms_count = len(case.latest_agent_output.extracted_terms)
                validation = case.latest_agent_output.validation_results
                assistant_response = f"I've extracted **{terms_count} contract terms** using template-guided extraction."
                if validation.get("required_fields_present"):
                    assistant_response += " All required fields are present."
                if case.latest_agent_output.inconsistencies:
                    assistant_response += f" I've flagged {len(case.latest_agent_output.inconsistencies)} inconsistencies that need your review."
                assistant_response += " The extracted terms are ready for contracting. Would you like me to proceed with the implementation plan?"
            elif isinstance(case.latest_agent_output, ImplementationPlan):
                steps_count = len(case.latest_agent_output.rollout_steps)
                savings = case.latest_agent_output.projected_savings
                assistant_response = f"I've created an implementation plan with **{steps_count} rollout steps**."
                if savings:
                    assistant_response += f" Projected savings: **${savings:,.2f}** (deterministic calculation)."
                assistant_response += " The plan includes structured KPIs and impact explanations. Ready for your review and approval."
            elif isinstance(case.latest_agent_output, ClarificationRequest):
                # Case Clarifier Agent output: render as natural follow-up questions,
                # not as an error. This is a collaboration request, not a failure.
                cr = case.latest_agent_output
                assistant_response = f"Before I can proceed, I need a bit more context: **{cr.reason}**.\n\n"
                if cr.questions:
                    assistant_response += "Here are the key questions I need you to answer:\n"
                    for q in cr.questions:
                        assistant_response += f"- {q}\n"
                if cr.suggested_options:
                    assistant_response += "\nYou can pick from these options or provide your own wording:\n"
                    for opt in cr.suggested_options:
                        assistant_response += f"- {opt}\n"
                assistant_response += "\nOnce you respond, I'll route your answer through the Supervisor so we stay within policy."
            else:
                # PHASE 2: Use ResponseAdapter for unknown output types
                assistant_response = response_adapter.generate_response(
                    case.latest_agent_output,
                    case_state_dict,
                    memory=case_memory,
                    user_intent=user_intent,
                    waiting_for_human=final_state.get("waiting_for_human", False),
                    contradictions=detected_contradictions
                )
        
        # PHASE 2 - OBJECTIVE E: Add contradiction warnings to response
        if detected_contradictions and assistant_response:
            contradiction_warning = "\n\n---\n⚠️ **Heads up:** I've detected some conflicting information:\n"
            for c in detected_contradictions[:3]:
                contradiction_warning += f"• {c}\n"
            contradiction_warning += "\nPlease review and let me know how you'd like to proceed."
            assistant_response += contradiction_warning
        
        if not case.latest_agent_output:
            # Fallback if no output yet - but show what actually happened
            activity_count = len(final_state.get("activity_log", []))
            if activity_count > 0:
                last_activity = final_state["activity_log"][-1]
                assistant_response = f"✅ **Workflow executed successfully**\n\n"
                assistant_response += f"• **{activity_count} actions** completed\n"
                assistant_response += f"• Last agent: **{last_activity.agent_name}** - {last_activity.task_name}\n"
                assistant_response += f"• DTP Stage: **{final_state['dtp_stage']}**\n\n"
                assistant_response += "However, no specific output was generated. The workflow may have completed without producing a recommendation. Would you like me to run a specific analysis?"
            else:
                assistant_response = "⚠️ **Workflow executed but no actions were logged**\n\n"
                assistant_response += "The workflow ran but didn't produce any agent activity. This might indicate:\n"
                assistant_response += "• The case is in a stage that doesn't require agent action\n"
                assistant_response += "• All required analyses are already complete\n"
                assistant_response += "• The workflow determined no action is needed\n\n"
                assistant_response += "Would you like me to run a specific analysis or check the case status?"
        
        # Update the pending message with the actual response
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            # Add workflow execution summary
            agents_called = list(set([log.agent_name for log in final_state.get('activity_log', [])]))
            total_tokens = sum([log.token_total for log in final_state.get('activity_log', [])])
            cache_hits = sum([1 for log in final_state.get('activity_log', []) if log.cache_hit])
            
            workflow_summary = f"\n\n---\n**Backend Execution Summary:**\n"
            workflow_summary += f"• **Agents called:** {', '.join(agents_called) if agents_called else 'None'}\n"
            workflow_summary += f"• **Total actions:** {len(final_state.get('activity_log', []))}\n"
            workflow_summary += f"• **Tokens used:** {total_tokens}\n"
            workflow_summary += f"• **Cache hits:** {cache_hits}/{len(final_state.get('activity_log', []))}\n"
            workflow_summary += f"• **DTP Stage:** {final_state['dtp_stage']}\n"
            
            st.session_state.chat_responses[case_id][-1] = {
                "user": user_intent,
                "assistant": assistant_response + workflow_summary,
                "timestamp": datetime.now().isoformat(),
                "pending": False,
                "workflow_started": True,
                "workflow_summary": {
                    "agents_called": agents_called,
                    "total_actions": len(final_state.get('activity_log', [])),
                    "tokens_used": total_tokens,
                    "cache_hits": cache_hits,
                    "dtp_stage": final_state['dtp_stage']
                }
            }
        else:
            # Fallback: add new entry if pending message not found
            st.session_state.chat_responses[case_id].append({
                "user": user_intent,
                "assistant": assistant_response,
                "timestamp": datetime.now().isoformat(),
                "pending": False
            })
        
        # Store workflow state for HIL
        st.session_state.workflow_state = final_state
        st.session_state.cases[case_id] = case
        
        st.rerun()
        
    except Exception as e:
        # Check if it's a recursion error
        error_msg = str(e)
        is_recursion_error = "Recursion limit" in error_msg or "GraphRecursionError" in error_msg
        
        if is_recursion_error:
            error_response = f"⚠️ **Workflow Loop Detected**\n\n"
            error_response += "The workflow exceeded the recursion limit, indicating a possible infinite loop.\n\n"
            error_response += "**What happened:**\n"
            error_response += "• Workflow entered a loop (Supervisor → Agent → Supervisor)\n"
            error_response += "• Loop detection mechanisms were triggered\n"
            error_response += "• Workflow was terminated to prevent infinite execution\n\n"
            error_response += "**Possible causes:**\n"
            error_response += "• Agent routing logic creating cycles\n"
            error_response += "• Missing stop conditions in workflow\n"
            error_response += "• Human decision not properly injected\n\n"
            error_response += "**Backend details:** Check Agent Activity Log for Supervisor routing decisions."
        else:
            error_response = f"❌ **Workflow Execution Error**\n\n"
            error_response += f"**Error:** {error_msg}\n\n"
            error_response += "**What happened:**\n"
            error_response += "• Workflow was initialized\n"
            error_response += "• Attempted to execute agent pipeline\n"
            error_response += "• Error occurred during execution\n\n"
            error_response += "**Possible causes:**\n"
            error_response += "• API key not configured\n"
            error_response += "• Network connectivity issue\n"
            error_response += "• Agent processing error\n"
            error_response += "• Invalid case state\n\n"
            error_response += "Check the error details below or try again."
        
        if st.session_state.chat_responses[case_id] and st.session_state.chat_responses[case_id][-1].get("pending"):
            st.session_state.chat_responses[case_id][-1] = {
                "user": user_intent,
                "assistant": error_response,
                "timestamp": datetime.now().isoformat(),
                "pending": False,
                "workflow_started": True,
                "error": True
            }
        
        st.error(f"Error running workflow: {e}")
        if not is_recursion_error:
            st.exception(e)


def inject_human_decision(case_id: str, decision: str, reason: Optional[str] = None, edited_fields: Dict[str, Any] = None):
    """Inject human decision into workflow state"""
    if st.session_state.workflow_state:
        human_decision = HumanDecision(
            decision=decision,
            reason=reason,
            edited_fields=edited_fields or {},
            timestamp=datetime.now().isoformat(),
            user_id=None
        )
        
        st.session_state.workflow_state["human_decision"] = human_decision
        
        # Continue workflow - invoke again, supervisor will process the decision
        try:
            graph = get_workflow_graph()
            config = {"recursion_limit": 50}
            final_state = graph.invoke(st.session_state.workflow_state, config)
            
            # Update case
            case = st.session_state.cases[case_id]
            case.latest_agent_output = final_state.get("latest_agent_output")
            case.latest_agent_name = final_state.get("latest_agent_name")
            case.activity_log.extend(final_state.get("activity_log", []))
            case.summary = final_state["case_summary"]
            case.dtp_stage = final_state["dtp_stage"]
            case.human_decision = human_decision
            now = datetime.now()
            case.updated_date = now.strftime("%Y-%m-%d")
            case.updated_timestamp = now.isoformat()
            
            if final_state.get("waiting_for_human"):
                case.status = "Waiting for Human Decision"
            else:
                case.status = "In Progress" if decision == "Approve" else "Rejected"
            
            st.session_state.workflow_state = final_state
            st.session_state.cases[case_id] = case
            
            st.success(f"Decision {decision} processed!")
            st.rerun()
        except Exception as e:
            st.error(f"Error processing decision: {e}")


def evaluate_signal(signal: Dict[str, Any]):
    """Evaluate a signal using Signal Interpretation Agent"""
    # Create temporary case for signal evaluation
    case_id = f"TEMP-{signal['signal_id']}"
    
    case_summary = CaseSummary(
        case_id=case_id,
        category_id=signal["category_id"],
        contract_id=signal.get("contract_id"),
        supplier_id=signal.get("supplier_id"),
        dtp_stage="DTP-01",
        trigger_source="Signal",
        status="In Progress",
        created_date=datetime.now().strftime("%Y-%m-%d"),
        summary_text=f"Signal evaluation: {signal['description']}",
        key_findings=[],
        recommended_action=None
    )
    
    try:
        signal_agent = SignalInterpretationAgent(tier=1)
        assessment, _, _ = signal_agent.interpret_signal(signal, case_summary, use_cache=True)
        return assessment
    except Exception as e:
        st.error(f"Error evaluating signal: {e}")
        return None


# Header (appears on all pages)
is_detail_view = st.session_state.selected_case_id is not None

if not is_detail_view:
    # Important: no leading spaces, to avoid markdown code blocks
    breadcrumb_html = (
        '<div class="app-header-tabs">'
        '<span class="app-header-tab app-header-tab-active">Cases</span>'
        "</div>"
    )
else:
    selected_case = st.session_state.cases.get(st.session_state.selected_case_id)
    case_label = selected_case.case_id if selected_case else st.session_state.selected_case_id
    breadcrumb_html = (
        '<div class="app-header-tabs">'
        '<span class="app-header-tab">Cases</span>'
        '<span class="app-header-separator">/</span>'
        f'<span class="app-header-tab app-header-tab-active">Case {case_label}</span>'
        "</div>"
    )

header_html = (
    '<div class="app-header">'
    '<div class="app-header-top">'
    '<div class="app-header-left">'
    '<div class="app-header-title">Agentic Sourcing Assistant</div>'
    f"{breadcrumb_html}"
    "</div>"
    '<div class="app-header-pill">Research POC · Synthetic data</div>'
    "</div>"
    '<div class="app-header-meta">Pilot environment · DTP workflow</div>'
    "</div>"
)
st.markdown(header_html, unsafe_allow_html=True)

# Main content - Cases Management Page
if st.session_state.selected_case_id is None:
    # 1. Purpose Framing Block (Top of Page)
    st.markdown(
        """
        <div style="margin-top: 20px; margin-bottom: 24px; padding: 20px 24px; background-color: #F8FAFF; border-left: 4px solid #003A8F; border-radius: 4px;">
            <h2 style="margin: 0 0 8px 0; font-size: 1.5rem; font-weight: 600; color: #0B2D56;">Active Sourcing Decisions</h2>
            <p style="margin: 0; font-size: 0.95rem; line-height: 1.6; color: #4A4A4A;">
                Each case represents a sourcing decision evaluated through a Supervisor-orchestrated DTP workflow, combining deterministic signal detection, policy guardrails, specialized agent reasoning, and governed knowledge retrieval.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 2. Define What a "Case" Is (Explicitly) - Aligned with new logic
    st.markdown(
        """
        <div style="margin-bottom: 20px; padding: 12px 16px; background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 4px;">
            <div style="font-size: 0.9rem; color: #4A4A4A; line-height: 1.6;">
                <strong>What is a case?</strong> A case is created when the <strong>Sourcing Signal Layer</strong> (deterministic, non-agent) scans contracts, performance metrics, and market data to detect signals (renewals, savings opportunities, risks) and emits a case trigger. The case is then evaluated through the DTP workflow with strategy options (e.g., renew, renegotiate, RFx, or exit).
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 3. Reframe Metrics as System-Level Signals
    st.markdown(
        """
        <div class="card" style="margin-bottom: 24px;">
            <div class="card-header">
                <span>System-Level Outcomes (Illustrative)</span>
            </div>
            <div class="metric-row">
                <div class="metric-tile">
                    <div class="metric-tile-label">
                        Cycle Time Reduction
                        <span style="cursor: help; margin-left: 4px; color: #6B7280;" title="Definition: Time saved vs. legacy manual process&#10;Baseline: Traditional sourcing cycle (45-60 days)&#10;Evaluation scope: End-to-end DTP workflow execution">ⓘ</span>
                    </div>
                    <div class="metric-tile-value">-15%</div>
                    <div class="metric-tile-caption">Vs. legacy process baseline</div>
                </div>
                <div class="metric-tile">
                    <div class="metric-tile-label">
                        Decision Consistency
                        <span style="cursor: help; margin-left: 4px; color: #6B7280;" title="Definition: Alignment with enterprise playbook and policy guardrails enforced by Supervisor Agent&#10;Baseline: Manual decision variance (estimated 70-75%)&#10;Evaluation scope: All agent outputs (Strategy, Supplier Scoring, RFx, Negotiation, Contract, Implementation) vs. PolicyLoader rules and RuleEngine constraints">ⓘ</span>
                    </div>
                    <div class="metric-tile-value">92%</div>
                    <div class="metric-tile-caption">Aligned to playbook / policy</div>
                </div>
                <div class="metric-tile">
                    <div class="metric-tile-label">
                        Knowledge Reuse
                        <span style="cursor: help; margin-left: 4px; color: #6B7280;" title="Definition: Cases leveraging Vector Knowledge Layer (templates, playbooks, historical cases) and cached agent outputs&#10;Baseline: Zero reuse in manual process&#10;Evaluation scope: Cache hits, template reuse, and signal register matches">ⓘ</span>
                    </div>
                    <div class="metric-tile-value">60%</div>
                    <div class="metric-tile-caption">Cases reusing knowledge & signals</div>
                </div>
            </div>
            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #E0E0E0; font-size: 0.8rem; color: #6B7280; font-style: italic;">
                Results shown are from synthetic pilot cases and intended for directional evaluation only.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 4. Make Agentic Value Visible (Without Diagrams) - Aligned with new logic
    st.markdown(
        """
        <div style="margin-bottom: 24px; padding: 16px 20px; background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 4px;">
            <div style="font-size: 0.85rem; font-weight: 600; color: #374151; margin-bottom: 12px;">How Decisions Are Produced</div>
            <div style="font-size: 0.85rem; color: #6B7280; line-height: 2.0;">
                <div style="margin-bottom: 8px;"><strong>1. Signal Detection (Deterministic):</strong> The Sourcing Signal Layer scans data and emits case triggers—it does <em>not</em> make decisions, only initiates cases.</div>
                <div style="margin-bottom: 8px;"><strong>2. Supervisor Orchestration:</strong> The Supervisor Agent (deterministic) is the <em>only orchestrator</em>—it enforces DTP logic, policy guardrails, and routes tasks to specialized agents.</div>
                <div style="margin-bottom: 8px;"><strong>3. Specialized Agents (7 functional agents):</strong> Strategy, Supplier Scoring, RFx Draft, Negotiation Support, Contract Support, Implementation, and Case Clarifier. LLMs reason within policy constraints (synthesize, explain, structure) but do <em>not</em> make decisions.</div>
                <div style="margin-bottom: 8px;"><strong>4. Knowledge Grounding:</strong> Vector Knowledge Layer provides read-only access to templates, playbooks, and historical cases to ground reasoning—never overrides rules or policies.</div>
                <div><strong>5. Human-in-the-Loop:</strong> Recommendations are logged with rationale. Policy-required approvals pause workflow for human review (Approve/Edit/Reject).</div>
            </div>
            <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #E5E7EB; font-size: 0.8rem; color: #6B7280; font-style: italic;">
                <strong>Core Principle:</strong> LLMs reason within bounded constraints; the Supervisor + policies decide what happens next. The chat narrates Supervisor decisions—it never makes autonomous choices.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 5. Add Scale & Scope Cues
    all_cases = list(st.session_state.cases.values())
    active_cases = [c for c in all_cases if c.status in ["Open", "In Progress", "Waiting for Human Decision"]]
    closed_cases = [c for c in all_cases if c.status in ["Closed", "Rejected"]]
    dtp_stages_present = sorted(list(set([c.dtp_stage for c in all_cases])))
    dtp_range = f"{dtp_stages_present[0]} to {dtp_stages_present[-1]}" if len(dtp_stages_present) > 1 else dtp_stages_present[0] if dtp_stages_present else "N/A"
    
    st.markdown(
        f"""
        <div style="margin-bottom: 20px; padding: 10px 16px; background-color: #FFFFFF; border-bottom: 1px solid #E0E0E0;">
            <div style="font-size: 0.9rem; color: #4A4A4A;">
                <strong>{len(all_cases)} total cases</strong> · <strong>{len(active_cases)} in progress</strong> · covering stages {dtp_range}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 6. Make Filters Teach the Sourcing Model
    st.markdown('<div style="margin-bottom: 12px; font-size: 0.9rem; color: #4A4A4A; font-weight: 500;">Filter Cases</div>', unsafe_allow_html=True)
    
    # Filters and search - reordered to reflect sourcing model
    col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 2])
    with col1:
        status_filter = st.selectbox(
            "Case Status",
            ["All", "Open", "In Progress", "Closed", "Waiting for Human Decision", "Rejected"],
            key="status_filter",
            label_visibility="collapsed"
        )
        st.caption("Case Status")
    with col2:
        dtp_filter_options = ["All", "DTP-01 (Strategy)", "DTP-02 (Planning)", "DTP-03 (Sourcing)", "DTP-04 (Negotiation)", "DTP-05 (Contracting)", "DTP-06 (Execution)"]
        dtp_filter_display = st.selectbox(
            "DTP Stage",
            dtp_filter_options,
            key="dtp_filter",
            label_visibility="collapsed"
        )
        st.caption("DTP Stage")
        # Extract DTP stage code from display value
        if dtp_filter_display != "All":
            dtp_stage_filter = dtp_filter_display.split(" ")[0]
        else:
            dtp_stage_filter = "All"
    with col3:
        categories = sorted(list(set([c.category_id for c in all_cases])))
        category_options = ["All"] + categories
        category_filter = st.selectbox(
            "Category",
            category_options,
            key="category_filter",
            label_visibility="collapsed"
        )
        st.caption("Category")
    with col4:
        decision_outcomes = ["All", "Approve", "Reject", "Pending"]
        decision_filter = st.selectbox(
            "Decision Outcome",
            decision_outcomes,
            key="decision_filter",
            label_visibility="collapsed"
        )
        st.caption("Decision Outcome")
    with col5:
        date_filter = st.selectbox(
            "Date",
            ["All", "Today", "This Week", "This Month"],
            key="date_filter",
            label_visibility="collapsed"
        )
        st.caption("Date")
        search_query = st.text_input(
            "Search",
            placeholder="Search cases...",
            key="search_input",
            label_visibility="collapsed"
        )
        # Clear filters / summary row
        filters_active = (
            status_filter != "All"
            or dtp_stage_filter != "All"
            or category_filter != "All"
            or decision_filter != "All"
            or date_filter != "All"
            or bool(search_query)
        )
        active_count = sum([
            int(status_filter != "All"),
            int(dtp_stage_filter != "All"),
            int(category_filter != "All"),
            int(decision_filter != "All"),
            int(date_filter != "All"),
            int(bool(search_query)),
        ])
        if filters_active:
            st.caption(f"Filters ({active_count})")
            if st.button("Clear filters", key="clear_filters", help="Reset all filters to defaults"):
                st.session_state.status_filter = "All"
                st.session_state.dtp_filter = "All"
                st.session_state.category_filter = "All"
                st.session_state.decision_filter = "All"
                st.session_state.date_filter = "All"
                st.session_state.search_input = ""
                st.rerun()
    
    # Debug/Admin tools
    with st.expander("🛠️ Debug Tools", expanded=False):
        st.caption("Admin and debugging utilities")
        col_debug1, col_debug2 = st.columns([1, 3])
        with col_debug1:
            if st.button("Clear Agent Cache", help="Clear all cached agent outputs. Use this if you're seeing stale or error results."):
                from utils.caching import cache
                cache.clear()
                st.success("✅ Cache cleared! All agent outputs will be regenerated on next run.")
                st.info("Note: You may need to restart your case workflow for changes to take effect.")
        with col_debug2:
            st.text(f"Session: {len(st.session_state.cases)} cases loaded")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 7. Improve Case Exploration Affordance
    st.markdown(
        """
        <div style="margin-bottom: 16px; padding: 10px 14px; background-color: #F0F4F8; border-left: 3px solid #003A8F; border-radius: 3px;">
            <div style="font-size: 0.85rem; color: #4A4A4A;">
                Select a case to inspect signals, agent recommendations, and decision rationale.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Cases table
    cases_list = list(st.session_state.cases.values())
    
    # Apply filters - updated to match new filter structure
    if status_filter != "All":
        cases_list = [c for c in cases_list if c.status == status_filter]
    if dtp_stage_filter != "All":
        cases_list = [c for c in cases_list if c.dtp_stage == dtp_stage_filter]
    if category_filter != "All":
        cases_list = [c for c in cases_list if c.category_id == category_filter]
    if decision_filter != "All":
        if decision_filter == "Approve":
            cases_list = [c for c in cases_list if c.human_decision and c.human_decision.decision == "Approve"]
        elif decision_filter == "Reject":
            cases_list = [c for c in cases_list if c.human_decision and c.human_decision.decision == "Reject"]
        elif decision_filter == "Pending":
            cases_list = [c for c in cases_list if c.status == "Waiting for Human Decision"]
    if date_filter != "All":
        now = datetime.now()
        if date_filter == "Today":
            cases_list = [c for c in cases_list if c.updated_date == now.strftime("%Y-%m-%d")]
        elif date_filter == "This Week":
            week_ago = now - timedelta(days=7)
            cases_list = [c for c in cases_list if datetime.fromisoformat(c.updated_timestamp.replace('Z', '+00:00')).replace(tzinfo=None) >= week_ago]
        elif date_filter == "This Month":
            month_ago = now - timedelta(days=30)
            cases_list = [c for c in cases_list if datetime.fromisoformat(c.updated_timestamp.replace('Z', '+00:00')).replace(tzinfo=None) >= month_ago]
    if search_query:
        cases_list = [c for c in cases_list if search_query.lower() in c.name.lower() or search_query.lower() in c.case_id.lower()]
    
    # Enterprise Cases Table - Decision-Oriented Design (with metrics)
    if cases_list:
        cases_list = sorted(cases_list, key=lambda c: c.updated_timestamp, reverse=True)

        header_col1, header_col2, header_col3, header_col4, header_col5, header_col6, header_col7 = st.columns([2.2, 1.3, 1.0, 1.5, 2.0, 1.3, 1.4])
        with header_col1:
            st.markdown('<div class="cases-table-header"><strong>Case ID &amp; Name</strong></div>', unsafe_allow_html=True)
        with header_col2:
            st.markdown('<div class="cases-table-header"><strong>Category</strong></div>', unsafe_allow_html=True)
        with header_col3:
            st.markdown('<div class="cases-table-header"><strong>Status</strong></div>', unsafe_allow_html=True)
        with header_col4:
            st.markdown('<div class="cases-table-header"><strong>Decision Signal</strong></div>', unsafe_allow_html=True)
        with header_col5:
            st.markdown('<div class="cases-table-header"><strong>Recommended Action</strong></div>', unsafe_allow_html=True)
        with header_col6:
            st.markdown('<div class="cases-table-header"><strong>Created</strong></div>', unsafe_allow_html=True)
        with header_col7:
            st.markdown('<div class="cases-table-header"><strong>Last Updated</strong></div>', unsafe_allow_html=True)

        for idx, case in enumerate(cases_list):
            category = get_category(case.category_id)
            category_name = category["name"] if category else case.category_id
            signal_type, signal_label, _ = get_decision_signal(case)
            signal_label = signal_label or "No Signal"
            action_label, _, _ = get_recommended_action(case)
            action_label = action_label or "No Action"
            action_display = action_label[:35] + ('...' if len(action_label) > 35 else '')

            try:
                created_dt = datetime.fromisoformat(case.created_timestamp.replace('Z', '+00:00'))
                created_str = created_dt.strftime("%Y-%m-%d %H:%M")
            except:
                created_str = case.created_date

            try:
                updated_dt = datetime.fromisoformat(case.updated_timestamp.replace('Z', '+00:00'))
                updated_str = updated_dt.strftime("%Y-%m-%d %H:%M")
                time_diff = datetime.now() - updated_dt.replace(tzinfo=None)
                if time_diff.days > 0:
                    time_ago = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    time_ago = f"{time_diff.seconds // 3600}h ago"
                elif time_diff.seconds > 60:
                    time_ago = f"{time_diff.seconds // 60}m ago"
                else:
                    time_ago = "Just now"
            except:
                updated_str = case.updated_date
                time_ago = ""

            status_class_map = {
                "Open": "status-open",
                "In Progress": "status-in-progress",
                "Waiting for Human Decision": "status-waiting",
                "Closed": "status-closed",
                "Rejected": "status-rejected"
            }
            status_class = status_class_map.get(case.status, "status-closed")

            signal_class_map = {
                "action_required": "signal-high",
                "renewal_at_risk": "signal-high",
                "contract_expiry": "signal-medium",
                "strategy_recommended": "signal-info",
                "supplier_shortlisted": "signal-info",
                "signal_assessment": "signal-info",
                "no_signal": "signal-low"
            }
            signal_class = signal_class_map.get(signal_type, "signal-info")

            col1, col2, col3, col4, col5, col6, col7 = st.columns([2.2, 1.3, 1.0, 1.5, 2.0, 1.3, 1.4])
            with col1:
                if st.button(
                    case.case_id,
                    key=f"case_select_{case.case_id}_{idx}",
                    use_container_width=True,
                    help="Open case details",
                ):
                    st.session_state.selected_case_id = case.case_id
                    st.rerun()
                st.caption(case.name[:45] + ('...' if len(case.name) > 45 else ''))
            with col2:
                st.markdown(f'<div class="cases-table-cell" style="font-size: 0.9rem;">{category_name}</div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div style="padding: 8px 0;"><span class="status-badge-enterprise {status_class}">{case.status}</span></div>', unsafe_allow_html=True)
            with col4:
                st.markdown(f'<div style="padding: 8px 0;"><span class="decision-signal-badge {signal_class}">{signal_label}</span></div>', unsafe_allow_html=True)
            with col5:
                st.markdown(f'<div style="padding: 8px 0;"><span class="action-badge">{action_display}</span></div>', unsafe_allow_html=True)
            with col6:
                st.markdown(f'<div class="timestamp-cell" style="padding: 8px 0;">{created_str}</div>', unsafe_allow_html=True)
            with col7:
                st.markdown(f'<div class="timestamp-cell" style="padding: 8px 0; background-color: #FAFAFA;">{updated_str}</div>', unsafe_allow_html=True)
                if time_ago:
                    st.caption(time_ago)

            if idx < len(cases_list) - 1:
                st.markdown("<hr style='margin: 0; border: none; border-top: 1px solid #E0E0E0;'>", unsafe_allow_html=True)

    else:
        st.info("No cases found matching the filters.")

    # Footer (always shown on main page branch)
    st.markdown("---")
    current_time = datetime.now().strftime("%I:%M %p EST")
    st.markdown(f"Last sync: {current_time}")

# Case detail view (outer branch when a case is selected)
else:
    # Case detail view - world-class reference design
    selected_case = st.session_state.cases[st.session_state.selected_case_id]
    
    # Back button and case actions
    col_back, col_reset = st.columns([3, 1])
    with col_back:
        if st.button("← Back to Cases", use_container_width=False):
            st.session_state.selected_case_id = None
            st.rerun()
    with col_reset:
        if st.button("🔄 Reset Case State", use_container_width=False, help="Clear cached errors and workflow state for this case"):
            # Clear any cached results for this case
            from utils.caching import cache
            # Clear cache entries for this case (approximate - clear all since cache doesn't have case-level clear)
            cache.clear()
            
            # Reset workflow state if present
            if "workflow_state" in st.session_state and st.session_state.workflow_state.get("case_summary", {}).get("case_id") == selected_case.case_id:
                st.session_state.workflow_state = None
            
            # Reset case latest output if it's an error
            if selected_case.latest_agent_output:
                from utils.schemas import SupplierShortlist
                if isinstance(selected_case.latest_agent_output, SupplierShortlist):
                    if (len(selected_case.latest_agent_output.shortlisted_suppliers) == 0 and
                        ("error" in selected_case.latest_agent_output.comparison_summary.lower() or
                         "fallback" in selected_case.latest_agent_output.comparison_summary.lower())):
                        # Clear error output
                        selected_case.latest_agent_output = None
                        selected_case.latest_agent_name = None
            
            st.success("✅ Case state reset! Cache cleared. You can now retry the workflow.")
            st.rerun()
    
    # Two column layout: Case Details (wider center), Sourcing Copilot (compact right)
    col_center, col_right = st.columns([2.8, 1.2], gap="small")
    
    with col_center:
        st.markdown('<div class="column-center">', unsafe_allow_html=True)
        # Case header hero band
        category = get_category(selected_case.category_id)
        category_name = category["name"] if category else selected_case.category_id

        try:
            updated_dt = datetime.fromisoformat(selected_case.updated_timestamp.replace("Z", "+00:00"))
            updated_str = updated_dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            updated_str = selected_case.updated_date

        # Compute spend estimate (reused below)
        contract = None
        if selected_case.contract_id:
            contract = get_contract(selected_case.contract_id)
        spend_estimate = f"${contract['annual_value_usd']:,}" if contract and contract.get("annual_value_usd") else "$125,000"
        spend_display = spend_estimate.replace(",", ".")

        st.markdown(
            f"""
            <div class="card card-hero">
                <div class="card-hero-main">
                    <div>
                        <div class="card-hero-title">Case {selected_case.case_id}</div>
                        <div class="card-hero-meta">{selected_case.name}</div>
                        <div class="card-hero-meta" style="margin-top: 6px;">
                            <span class="badge">Category: {category_name}</span>
                            <span class="badge" style="margin-left: 6px;">Requester: System</span>
                        </div>
                    </div>
                    <div class="card-hero-metrics">
                        <div style="margin-bottom: 4px;">
                            <span class="status-badge-enterprise">{selected_case.status}</span>
                        </div>
                        <div style="margin-bottom: 4px;">
                            <span class="pill pill-primary">Stage {selected_case.dtp_stage}</span>
                        </div>
                        <div>Spend est.: <strong>{spend_display}</strong></div>
                        <div style="font-size: 0.75rem; color: #9CA3AF;">Last updated {updated_str}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Summary Section (card)
        st.markdown(
            """
            <div class="card">
                <div class="card-header"><span>Summary</span></div>
            """,
            unsafe_allow_html=True,
        )
        col_summary_left, col_summary_right = st.columns([2, 1])
        with col_summary_left:
            st.markdown(f"**Description:** {selected_case.summary.summary_text}")
        with col_summary_right:
            st.markdown(f"**Category:** {category_name}")
            st.markdown(f"**Requester:** System")
            st.markdown(f"**Spend estimated:** {spend_display}")
        st.markdown("</div>", unsafe_allow_html=True)

        # AI Insights – storytelling layout (card)
        st.markdown(
            """
            <div class="card">
                <div class="card-header"><span>AI Insights</span></div>
            """,
            unsafe_allow_html=True,
        )
        col_ai_suppliers, col_ai_cost, col_ai_risk = st.columns(3)
        if selected_case.latest_agent_output and isinstance(selected_case.latest_agent_output, SupplierShortlist):
            suppliers = [
                s.get("name", s.get("supplier_id", "N/A"))
                for s in selected_case.latest_agent_output.shortlisted_suppliers[:3]
            ]
            supplier_list = ", ".join(suppliers) if suppliers else "RedPixel, XYZ Marketing"
        else:
            supplier_list = "Analysis pending"

        with col_ai_suppliers:
            st.markdown("**Suppliers**")
            st.markdown(f"{supplier_list}")
        with col_ai_cost:
            st.markdown("**Cost & benchmarks**")
            if supplier_list != "Analysis pending":
                st.markdown("$120K–$140K (3 suppliers)")
            else:
                st.markdown("Benchmarks pending")
        with col_ai_risk:
            st.markdown("**Risk & compliance**")
            if supplier_list != "Analysis pending":
                st.markdown("Moderate (no critical flags identified)")
            else:
                st.markdown("Not assessed")
        st.markdown("</div>", unsafe_allow_html=True)
        
        # DTP Stage stepper + Recommended Actions Section (card)
        dtp_stages = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]
        dtp_html = '<div class="dtp-stepper">'
        for stage in dtp_stages:
            is_active = stage == selected_case.dtp_stage
            cls = "dtp-step dtp-step-active" if is_active else "dtp-step"
            label = get_dtp_stage_display(stage)
            dtp_html += f'<span class="{cls}">{stage} &ndash; {label}</span>'
        dtp_html += "</div>"

        # Recommended Actions Section - Sequential based on DTP stage
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header"><span>Recommended Actions</span></div>', unsafe_allow_html=True)
        st.markdown(dtp_html, unsafe_allow_html=True)
        
        # Show current stage context
        stage_display = get_dtp_stage_display(selected_case.dtp_stage)
        st.caption(f"Current Stage: {selected_case.dtp_stage} - {stage_display}")
        
        # Determine available actions based on DTP stage and case state
        action_buttons = []
        dtp_stage = selected_case.dtp_stage
        has_strategy = (selected_case.latest_agent_output and 
                       isinstance(selected_case.latest_agent_output, StrategyRecommendation))
        has_supplier_shortlist = (selected_case.latest_agent_output and 
                                 isinstance(selected_case.latest_agent_output, SupplierShortlist))
        waiting_for_decision = selected_case.status == "Waiting for Human Decision"
        
        # DTP-01: Strategy stage - can only run strategy analysis
        if dtp_stage == "DTP-01":
            if not has_strategy:
                action_buttons.append(("Run Strategy Analysis", "Analyze sourcing strategy for this case", True))
            elif waiting_for_decision:
                # Show approval buttons separately (not as copilot action)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve Strategy", key=f"approve_strategy_{selected_case.case_id}", use_container_width=True, type="primary"):
                        inject_human_decision(selected_case.case_id, "Approve")
                with col2:
                    if st.button("❌ Reject Strategy", key=f"reject_strategy_{selected_case.case_id}", use_container_width=True):
                        reason = st.text_input("Rejection reason", key=f"reject_reason_{selected_case.case_id}")
                        if reason:
                            inject_human_decision(selected_case.case_id, "Reject", reason=reason)
            else:
                st.info("✅ Strategy analysis complete. Ready to proceed to planning stage.")
        
        # DTP-02: Planning stage - can draft RFP/requirements after strategy approved
        elif dtp_stage == "DTP-02":
            if has_strategy:
                action_buttons.append(("Draft RFP", "Generate RFP draft for this case", True))
                action_buttons.append(("Market Intelligence", "Provide market intelligence update", True))
            else:
                action_buttons.append(("Run Strategy Analysis", "Analyze sourcing strategy first", False))
        
        # DTP-03: Sourcing stage - can evaluate suppliers after planning
        elif dtp_stage == "DTP-03":
            if has_strategy:
                if not has_supplier_shortlist:
                    action_buttons.append(("Evaluate Suppliers", "Identify and evaluate suppliers for this category", True))
                else:
                    action_buttons.append(("Review Supplier Shortlist", "Show me the supplier shortlist details", True))
            else:
                action_buttons.append(("Complete Strategy First", "Strategy must be approved before supplier evaluation", False))
        
        # DTP-04: Negotiation stage - can negotiate after suppliers shortlisted
        elif dtp_stage == "DTP-04":
            if has_supplier_shortlist:
                action_buttons.append(("Create Negotiation Plan", "Launch negotiation workflow", True))
                if selected_case.latest_agent_output and isinstance(selected_case.latest_agent_output, NegotiationPlan):
                    action_buttons.append(("Review Negotiation Plan", "Show me the negotiation plan", True))
            else:
                action_buttons.append(("Complete Supplier Evaluation First", "Suppliers must be shortlisted before negotiation", False))
        
        # DTP-05: Contracting stage
        elif dtp_stage == "DTP-05":
            action_buttons.append(("Finalize Contract", "Review and finalize contract terms", True))
        
        # DTP-06: Execution stage
        elif dtp_stage == "DTP-06":
            st.info("Case is in execution stage. Contract management in progress.")
        
        # Display actions with enabled/disabled states
        if action_buttons:
            for button_label, action_query, enabled in action_buttons:
                label_clean = button_label.replace(" ", "_")
                if enabled:
                    if st.button(f"▶ {button_label}", key=f"action_btn_{label_clean}_{selected_case.case_id}", use_container_width=True):
                        run_copilot(selected_case.case_id, action_query, use_tier_2=False)
                else:
                    st.button(
                        f"⏸ {button_label}",
                        key=f"action_btn_{label_clean}_{selected_case.case_id}",
                        use_container_width=True,
                        disabled=True,
                    )
                    st.caption("⚠️ Complete previous stage first")
        else:
            st.caption("No immediate actions available at this stage.")

        st.markdown("</div>", unsafe_allow_html=True)
    
    with col_right:
        st.markdown('<div class="card-copilot">', unsafe_allow_html=True)
        st.markdown("### Sourcing Copilot")
        # Context line to tie Copilot to the case
        dtp_label = get_dtp_stage_display(selected_case.dtp_stage)
        try:
            contract = get_contract(selected_case.contract_id) if selected_case.contract_id else None
            spend_estimate = f"${contract['annual_value_usd']:,}" if contract and contract.get("annual_value_usd") else "$125,000"
            spend_display = spend_estimate.replace(",", ".")
        except Exception:
            spend_display = "$125.000"
        st.caption(
            f"Linked to {selected_case.case_id} · {selected_case.dtp_stage} – {dtp_label} · Est. spend {spend_display}"
        )
        
        # Quick prompt chips for common actions (compact row)
        qp_col1, qp_col2, qp_col3 = st.columns(3)
        with qp_col1:
            if st.button("Summarize this case", key=f"qp_summary_{selected_case.case_id}"):
                run_copilot(
                    selected_case.case_id,
                    "Give me an executive summary of this case and key risks.",
                    use_tier_2=False,
                )
        with qp_col2:
            if st.button("Explain current stage", key=f"qp_stage_{selected_case.case_id}"):
                run_copilot(
                    selected_case.case_id,
                    "Explain the current DTP stage and what needs to happen next.",
                    use_tier_2=False,
                )
        with qp_col3:
            if st.button("Next best action", key=f"qp_next_action_{selected_case.case_id}"):
                run_copilot(
                    selected_case.case_id,
                    "What is the next best action I should take on this case?",
                    use_tier_2=False,
                )

        # Show chat history from session state
        has_chat_history = ("chat_responses" in st.session_state and 
                           selected_case.case_id in st.session_state.chat_responses and
                           st.session_state.chat_responses[selected_case.case_id])
        
        if has_chat_history:
            chat_history = st.session_state.chat_responses[selected_case.case_id]
            for idx, chat_item in enumerate(chat_history):
                # User message
                st.markdown(f'<div class="chat-message chat-user">{chat_item["user"]}</div>', unsafe_allow_html=True)
                # Assistant response - format nicely
                response_text = chat_item["assistant"]
                # Convert markdown-style formatting to HTML
                # Replace **text** with <strong>text</strong>
                response_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', response_text)
                # Replace line breaks
                response_text = response_text.replace("\n\n", "<br><br>").replace("\n", "<br>")
                st.markdown(f'<div class="chat-message chat-assistant">{response_text}</div>', unsafe_allow_html=True)
                if idx < len(chat_history) - 1:
                    st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="chat-container" style="text-align: center; color: #666;">'
                '💬 Start a conversation by asking about the case'
                "</div>",
                unsafe_allow_html=True,
            )
        
        # Auto-scroll handled implicitly by Streamlit layout; no custom JS needed
        
        # Backend Activity Panel - Show what's happening
        if has_chat_history:
            latest_chat = st.session_state.chat_responses[selected_case.case_id][-1]
            if latest_chat.get("pending") or latest_chat.get("workflow_started"):
                with st.expander("🔍 **Backend Activity** (Click to see what's happening)", expanded=True):
                    if latest_chat.get("workflow_started"):
                        st.info("✅ **Workflow is executing**")
                        st.markdown("**Current Status:**")
                        st.code(latest_chat.get("assistant", "Processing..."), language=None)
                        
                        # Show recent activity logs if available
                        if selected_case.activity_log:
                            st.markdown("**Recent Agent Actions:**")
                            for log in selected_case.activity_log[-3:]:  # Show last 3
                                st.markdown(f"• **{log.agent_name}** - {log.task_name} ({log.timestamp[:19]})")
                                if log.cache_hit:
                                    st.caption(f"  ⚡ Cache hit - no LLM call needed")
                                else:
                                    st.caption(f"  🤖 LLM call: {log.model_used} ({log.token_total} tokens, ${log.estimated_cost_usd:.4f})")
                    else:
                        st.warning("⏳ **Waiting for workflow to start**")
                        st.markdown("The request is queued but workflow hasn't started yet.")
        
        # Compact action buttons - removed to save space, actions are in Recommended Actions section
        
        # Chat input - compact form
        with st.form(key=f"chat_form_{selected_case.case_id}", clear_on_submit=True):
            user_input = st.text_input(
                "", 
                placeholder="Ask anything...", 
                key=f"copilot_input_{selected_case.case_id}",
                help=""  # Empty help text to prevent default form help
            )
            submitted = st.form_submit_button("Send", type="primary", use_container_width=True)
            
            if submitted:
                if user_input.strip():
                    run_copilot(selected_case.case_id, user_input, use_tier_2=False)
                else:
                    st.warning("Please enter a message")
        
        # JavaScript to hide form help text - more aggressive approach
        st.markdown(f"""
        <script>
            (function() {{
                function hideFormHelpText() {{
                    // Method 1: Find all small elements and hide those with "Press Enter" text
                    const allSmall = document.querySelectorAll('small');
                    allSmall.forEach(el => {{
                        const text = el.textContent || el.innerText || '';
                        if (text.includes('Press Enter') || text.includes('submit form')) {{
                            el.style.display = 'none !important';
                            el.style.visibility = 'hidden !important';
                            el.style.height = '0 !important';
                            el.style.margin = '0 !important';
                            el.style.padding = '0 !important';
                            el.style.opacity = '0 !important';
                            el.style.fontSize = '0 !important';
                            el.style.lineHeight = '0 !important';
                            el.remove(); // Remove from DOM entirely
                        }}
                    }});
                    
                    // Method 2: Hide ALL small elements within forms (more aggressive)
                    const forms = document.querySelectorAll('form, [data-testid="stForm"]');
                    forms.forEach(form => {{
                        const smallElements = form.querySelectorAll('small');
                        smallElements.forEach(el => {{
                            const text = el.textContent || el.innerText || '';
                            if (text.includes('Enter') || text.includes('submit') || text.includes('form')) {{
                                el.style.display = 'none !important';
                                el.style.visibility = 'hidden !important';
                                el.style.height = '0 !important';
                                el.remove();
                            }}
                        }});
                    }});
                    
                    // Method 3: Find elements near text inputs
                    const textInputs = document.querySelectorAll('input[type="text"], input[placeholder]');
                    textInputs.forEach(input => {{
                        let parent = input.parentElement;
                        for (let i = 0; i < 5 && parent; i++) {{
                            const smalls = parent.querySelectorAll('small');
                            smalls.forEach(el => {{
                                const text = el.textContent || el.innerText || '';
                                if (text.includes('Enter') || text.includes('submit')) {{
                                    el.remove();
                                }}
                            }});
                            parent = parent.parentElement;
                        }}
                    }});
                }}
                
                // Run immediately and repeatedly
                hideFormHelpText();
                setTimeout(hideFormHelpText, 50);
                setTimeout(hideFormHelpText, 100);
                setTimeout(hideFormHelpText, 300);
                setTimeout(hideFormHelpText, 500);
                setTimeout(hideFormHelpText, 1000);
                
                // Use MutationObserver to catch dynamically added elements
                const observer = new MutationObserver(function(mutations) {{
                    hideFormHelpText();
                }});
                
                if (document.body) {{
                    observer.observe(document.body, {{
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true
                    }});
                }}
                
                // Also run on input focus/typing events
                document.addEventListener('input', hideFormHelpText);
                document.addEventListener('focus', hideFormHelpText, true);
            }})();
        </script>
        """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Activity Log Section - Full width at bottom
    # Agent Activity Log - compact, tabbed card
    st.markdown(
        """
        <div class="card">
            <div class="card-header"><span>Agent Activity Log</span></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Complete record of all agent actions and backend operations for this case")
    
    if selected_case.activity_log:
        # Summary Statistics
        total_logs = len(selected_case.activity_log)
        agent_counts = {}
        total_tokens = 0
        total_cost = 0.0
        cache_hits = 0
        
        for log_entry in selected_case.activity_log:
            agent_name = log_entry.agent_name
            agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
            total_tokens += log_entry.token_total
            total_cost += log_entry.estimated_cost_usd
            if log_entry.cache_hit:
                cache_hits += 1

        tabs = st.tabs(["Summary", "Timeline", "Payloads"])

        with tabs[0]:
            # Display summary metrics
            summary_col1, summary_col2, summary_col3, summary_col4, summary_col5 = st.columns(5)
            with summary_col1:
                st.metric("Total Actions", total_logs)
            with summary_col2:
                st.metric("Agents Called", len(agent_counts))
            with summary_col3:
                st.metric("Total Tokens", f"{total_tokens:,}")
            with summary_col4:
                st.metric("Total Cost", f"${total_cost:.4f}")
            with summary_col5:
                cache_hit_rate = (cache_hits / total_logs * 100) if total_logs > 0 else 0
                st.metric("Cache Hit Rate", f"{cache_hit_rate:.1f}%")

        with tabs[1]:
            # Quick table view for stakeholders
            table_data = []
            for log_entry in selected_case.activity_log:
                table_data.append({
                    "Time": log_entry.timestamp[:19],
                    "Agent": log_entry.agent_name,
                    "Task": log_entry.task_name,
                    "DTP": log_entry.dtp_stage,
                    "Tokens (in/out/total)": f"{log_entry.token_input}/{log_entry.token_output}/{log_entry.token_total}",
                    "Cost ($)": f"{log_entry.estimated_cost_usd:.4f}",
                    "Cache": "Hit" if log_entry.cache_hit else "Miss",
                    "Guardrails": ", ".join(log_entry.guardrail_events) if log_entry.guardrail_events else "",
                    "Summary": log_entry.output_summary[:80] + ("..." if len(log_entry.output_summary) > 80 else "")
                })
            st.dataframe(table_data, use_container_width=True, hide_index=True)

        with tabs[2]:
            # Detailed log entries and payloads
            st.markdown("**Detailed Payload View:**")
            for idx, log_entry in enumerate(reversed(selected_case.activity_log)):  # Show most recent first
                agent_emoji = {
                    "Supervisor": "🎯",
                    "Strategy": "📊",
                    "SupplierEvaluation": "🏭",
                    "NegotiationSupport": "🤝",
                    "SignalInterpretation": "📡",
                    "Workflow": "⚙️"
                }.get(log_entry.agent_name, "🤖")
                
                with st.expander(
                    f"{agent_emoji} {log_entry.timestamp[:19]} | {log_entry.agent_name} - {log_entry.task_name}",
                    expanded=(idx == 0),
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**DTP Stage:** {log_entry.dtp_stage}")
                        st.markdown(f"**Trigger Source:** {log_entry.trigger_source}")
                    with col2:
                        st.markdown(f"**Output Summary:** {log_entry.output_summary}")
                    with st.expander("📥 LLM Input Payload", expanded=False):
                        st.json(log_entry.llm_input_payload)
                    with st.expander("📤 Output Payload", expanded=False):
                        st.json(log_entry.output_payload)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No agent activity recorded yet. Agent actions will appear here as the workflow executes.")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    current_time = datetime.now().strftime("%I:%M %p EST")
    st.markdown(f"Last sync: {current_time}")
    st.markdown('</div>', unsafe_allow_html=True)
