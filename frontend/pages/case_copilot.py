"""
Case Copilot Page - Enterprise Decision Console

Design Philosophy:
- The decision is the focal point
- The AI is an advisor
- The human is accountable

MIT Color System:
- MIT Navy (#003A8F): Structure and hierarchy
- MIT Cardinal Red (#A31F34): Actions and urgency only
"""
import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime

from frontend.api_client import get_api_client, APIError
from shared.constants import DTP_STAGES, DTP_STAGE_NAMES


# MIT Color Constants
MIT_NAVY = "#003A8F"
MIT_CARDINAL = "#A31F34"
NEAR_BLACK = "#1F1F1F"
CHARCOAL = "#4A4A4A"
LIGHT_GRAY = "#D9D9D9"
WHITE = "#FFFFFF"


def inject_styles():
    """Inject enterprise CSS styles."""
    st.markdown(f"""
    <style>
        /* Case Header */
        .case-header {{
            background-color: {MIT_NAVY};
            color: {WHITE};
            padding: 20px 24px;
            border-radius: 4px;
            margin-bottom: 24px;
        }}
        .case-header h1 {{
            color: {WHITE};
            margin: 0 0 8px 0;
            font-size: 1.5rem;
            font-weight: 600;
        }}
        .case-header-meta {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            font-size: 0.875rem;
            opacity: 0.9;
        }}
        .case-header-meta span {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .status-badge {{
            background-color: transparent;
            border: 2px solid {MIT_CARDINAL};
            color: {WHITE};
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
        }}
        .status-badge.active {{
            background-color: {MIT_CARDINAL};
        }}
        
        /* Context Cards */
        .context-card {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .context-card h3 {{
            color: {MIT_NAVY};
            font-size: 0.875rem;
            font-weight: 600;
            margin: 0 0 12px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .context-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid {LIGHT_GRAY};
            font-size: 0.875rem;
        }}
        .context-item:last-child {{
            border-bottom: none;
        }}
        .context-label {{
            color: {CHARCOAL};
        }}
        .context-value {{
            color: {NEAR_BLACK};
            font-weight: 500;
        }}
        
        /* Evidence Items in Expanders */
        .evidence-value {{
            color: {NEAR_BLACK};
            font-weight: 500;
            font-size: 0.875rem;
        }}
        .evidence-source {{
            color: {CHARCOAL};
            font-size: 0.75rem;
            margin-top: 8px;
        }}
        
        /* Copilot Section */
        .copilot-header {{
            color: {MIT_NAVY};
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .copilot-subtitle {{
            color: {CHARCOAL};
            font-size: 0.75rem;
            margin-bottom: 16px;
        }}
        .suggested-prompt {{
            background-color: #F8F9FA;
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 8px 12px;
            margin-bottom: 8px;
            font-size: 0.8rem;
            color: {NEAR_BLACK};
            cursor: pointer;
            transition: border-color 0.2s;
        }}
        .suggested-prompt:hover {{
            border-color: {MIT_NAVY};
        }}
        
        /* Transparency Footer */
        .transparency-footer {{
            background-color: #F8F9FA;
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 12px;
            margin-top: 16px;
            font-size: 0.75rem;
            color: {CHARCOAL};
        }}
        .transparency-item {{
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
        }}
        
        /* Document List */
        .document-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid {LIGHT_GRAY};
            font-size: 0.875rem;
        }}
        .document-item:last-child {{
            border-bottom: none;
        }}
        .document-status {{
            color: #2E7D32;
            font-size: 0.75rem;
        }}
        
        /* Signal Row */
        .signal-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid {LIGHT_GRAY};
            font-size: 0.875rem;
        }}
        .signal-row:last-child {{
            border-bottom: none;
        }}
        .signal-indicator {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .signal-indicator.green {{ background-color: #2E7D32; }}
        .signal-indicator.yellow {{ background-color: #F9A825; }}
        .signal-indicator.red {{ background-color: {MIT_CARDINAL}; }}
        
        /* Override Streamlit defaults */
        .stButton > button {{
            border-radius: 4px;
            font-weight: 500;
            padding: 8px 24px;
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_case_header(case) -> None:
    """Render full-width case status header."""
    dtp_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
    is_waiting = case.status == "Waiting for Human Decision"
    
    # Determine urgency
    urgency = "Standard"
    if "URGENT" in case.name.upper():
        urgency = "High"
    elif case.trigger_source == "Signal":
        urgency = "Elevated"
    
    # Determine risk level from key findings
    risk_level = "Medium"
    if case.summary and case.summary.key_findings:
        findings_text = " ".join(case.summary.key_findings).lower()
        if "high" in findings_text or "critical" in findings_text:
            risk_level = "High"
        elif "low" in findings_text:
            risk_level = "Low"
    
    status_class = "status-badge active" if is_waiting else "status-badge"
    
    st.markdown(f"""
    <div class="case-header">
        <h1>{case.name}</h1>
        <div class="case-header-meta">
            <span><strong>ID:</strong> {case.case_id}</span>
            <span><strong>Category:</strong> {case.category_id}</span>
            <span><strong>Supplier:</strong> {case.supplier_id or 'Not Assigned'}</span>
            <span><strong>Stage:</strong> {case.dtp_stage} - {dtp_name}</span>
            <span><strong>Risk:</strong> {risk_level}</span>
            <span><strong>Urgency:</strong> {urgency}</span>
            <span class="{status_class}">{case.status}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_context_column(case) -> None:
    """Render left column - Case Context (read-only)."""
    
    # Case Summary Card
    st.markdown("""
    <div class="context-card">
        <h3>Case Summary</h3>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown(f"""
        <div class="context-item">
            <span class="context-label">Case ID</span>
            <span class="context-value">{case.case_id}</span>
        </div>
        <div class="context-item">
            <span class="context-label">Category</span>
            <span class="context-value">{case.category_id}</span>
        </div>
        <div class="context-item">
            <span class="context-label">Supplier</span>
            <span class="context-value">{case.supplier_id or 'Not Assigned'}</span>
        </div>
        <div class="context-item">
            <span class="context-label">Contract</span>
            <span class="context-value">{case.contract_id or 'Not Specified'}</span>
        </div>
        <div class="context-item">
            <span class="context-label">Trigger Source</span>
            <span class="context-value">{case.trigger_source}</span>
        </div>
        <div class="context-item">
            <span class="context-label">Created</span>
            <span class="context-value">{case.created_date}</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Signals & Triggers Card
    st.markdown("""
    <div class="context-card">
        <h3>Signals & Triggers</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Parse key findings for signals
    signals = []
    if case.summary and case.summary.key_findings:
        for finding in case.summary.key_findings:
            indicator = "yellow"
            if "high" in finding.lower() or "breach" in finding.lower() or "decline" in finding.lower():
                indicator = "red"
            elif "strong" in finding.lower() or "improving" in finding.lower():
                indicator = "green"
            signals.append({"text": finding, "indicator": indicator})
    
    if signals:
        for signal in signals[:5]:
            st.markdown(f"""
            <div class="signal-row">
                <span>
                    <span class="signal-indicator {signal['indicator']}"></span>
                    {signal['text'][:60]}{'...' if len(signal['text']) > 60 else ''}
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="color: #4A4A4A; font-size: 0.875rem;">No signals detected</div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Documents Card
    st.markdown("""
    <div class="context-card">
        <h3>Documents (RAG Sources)</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Simulated document list - in production, query from ingestion service
    documents = [
        {"name": "Contract_Agreement.pdf", "status": "Ingested"},
        {"name": "Performance_Q3.pdf", "status": "Ingested"},
        {"name": "SLA_Terms.pdf", "status": "Pending"},
    ]
    
    for doc in documents:
        status_mark = "check" if doc["status"] == "Ingested" else "clock"
        st.markdown(f"""
        <div class="document-item">
            <span>{doc['name']}</span>
            <span class="document-status">{'Ingested' if doc['status'] == 'Ingested' else 'Pending'}</span>
        </div>
        """, unsafe_allow_html=True)


def render_decision_column(case, client) -> None:
    """Render center column - Decision & Evidence."""
    
    # Get recommendation from latest agent output
    recommendation = "PENDING ANALYSIS"
    confidence = 0.0
    agent_name = "Awaiting"
    rationale = []
    has_recommendation = False
    
    if case.latest_agent_output:
        output = case.latest_agent_output
        rec = output.get("recommended_strategy")
        if rec:
            recommendation = rec.upper()
            has_recommendation = True
        confidence = output.get("confidence", 0.0)
        rationale = output.get("rationale", [])
    
    if case.latest_agent_name:
        agent_name = case.latest_agent_name
    
    # Decision Card - Complete HTML block
    st.markdown(f"""
    <div style="background-color: #FFFFFF; border: 2px solid #003A8F; border-radius: 4px; padding: 24px; margin-bottom: 20px;">
        <div style="color: #003A8F; font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px;">
            Strategy Recommendation
        </div>
        <div style="font-size: 1.75rem; font-weight: 700; color: #1F1F1F; margin-bottom: 16px;">
            {recommendation}
        </div>
        <div style="display: flex; gap: 24px; font-size: 0.875rem; color: #4A4A4A;">
            <span><strong>Confidence:</strong> {confidence:.0%}</span>
            <span><strong>Producing Agent:</strong> {agent_name}</span>
            <span><strong>DTP Stage:</strong> {case.dtp_stage}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Action Buttons with improved styling
    is_waiting = case.status == "Waiting for Human Decision"
    
    # Custom button styling
    st.markdown("""
    <style>
        div[data-testid="column"]:first-child .stButton > button {
            background-color: #A31F34 !important;
            color: white !important;
            font-weight: 700 !important;
            border: none !important;
            padding: 12px 32px !important;
        }
        div[data-testid="column"]:nth-child(2) .stButton > button {
            background-color: #FFFFFF !important;
            color: #1F1F1F !important;
            font-weight: 700 !important;
            border: 2px solid #4A4A4A !important;
            padding: 12px 32px !important;
        }
        div[data-testid="column"]:nth-child(2) .stButton > button:hover {
            border-color: #003A8F !important;
            color: #003A8F !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    col_approve, col_reject, col_spacer = st.columns([1.2, 1.5, 2])
    
    with col_approve:
        if st.button(
            "APPROVE",
            key="approve_decision",
            disabled=not is_waiting
        ):
            try:
                result = client.approve_decision(case.case_id)
                st.success(f"Decision approved. Advanced to {result.new_dtp_stage}")
                st.rerun()
            except APIError as e:
                st.error(f"Error: {e.message}")
    
    with col_reject:
        if st.button(
            "REQUEST REVISION",
            key="reject_decision",
            disabled=not is_waiting
        ):
            try:
                result = client.reject_decision(case.case_id)
                st.info("Revision requested. Case remains at current stage.")
                st.rerun()
            except APIError as e:
                st.error(f"Error: {e.message}")
    
    # Governance Gate
    next_stage = get_next_stage(case.dtp_stage)
    st.markdown(f"""
    <div style="background-color: #FFFFFF; border: 1px solid #A31F34; border-left: 4px solid #A31F34; padding: 16px; margin: 20px 0; font-size: 0.875rem;">
        <strong style="color: #A31F34;">Governance Notice:</strong> This recommendation will not advance to {next_stage} without explicit human approval. All decisions are logged for audit.
    </div>
    """, unsafe_allow_html=True)
    
    # Evidence Breakdown Header
    st.markdown("""
    <div style="background-color: #F8F9FA; border: 1px solid #D9D9D9; border-radius: 4px 4px 0 0; padding: 12px 16px; font-weight: 600; font-size: 0.875rem; color: #003A8F; margin-top: 8px;">
        Evidence Breakdown
    </div>
    """, unsafe_allow_html=True)
    
    # Display rationale as evidence items
    if rationale:
        for i, item in enumerate(rationale):
            with st.expander(f"Evidence {i+1}: {item[:50]}...", expanded=False):
                st.markdown(f"""
                <div class="evidence-item">
                    <div class="evidence-value">{item}</div>
                    <div class="evidence-source">Source: Agent Analysis | Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        with st.expander("Case Summary", expanded=True):
            st.markdown(f"""
            <div class="evidence-item">
                <div class="evidence-value">{case.summary.summary_text if case.summary else 'No summary available'}</div>
                <div class="evidence-source">Source: Case Data | Type: Summary</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Show key findings as additional evidence
    if case.summary and case.summary.key_findings:
        with st.expander("Key Findings", expanded=False):
            for finding in case.summary.key_findings:
                st.markdown(f"""
                <div class="evidence-item">
                    <div class="evidence-value">{finding}</div>
                    <div class="evidence-source">Source: Signal Detection | Type: Finding</div>
                </div>
                """, unsafe_allow_html=True)


def render_copilot_column(case, client) -> None:
    """Render right column - Case Copilot."""
    
    # Copilot Header
    st.markdown(f"""
    <div class="copilot-header">Case Copilot</div>
    <div class="copilot-subtitle">Ask questions about {case.case_id}</div>
    """, unsafe_allow_html=True)
    
    # Suggested Prompts
    st.markdown("**Suggested Questions**")
    
    suggested_prompts = [
        "Explain why this strategy is recommended",
        "What are the key risks?",
        "What alternatives were considered?",
        "What information is missing?"
    ]
    
    for prompt in suggested_prompts:
        if st.button(prompt, key=f"prompt_{prompt[:20]}", use_container_width=True):
            st.session_state.pending_prompt = prompt
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = {}
    
    if case.case_id not in st.session_state.chat_history:
        st.session_state.chat_history[case.case_id] = []
    
    chat_history = st.session_state.chat_history[case.case_id]
    
    # Chat container with fixed height
    chat_container = st.container()
    
    with chat_container:
        # Display chat history
        for msg in chat_history[-10:]:  # Show last 10 messages
            if msg["role"] == "user":
                st.markdown(f"""
                <div style="background-color: #F0F4F8; padding: 10px; border-radius: 4px; margin-bottom: 8px;">
                    <strong style="color: {MIT_NAVY};">You:</strong> {msg['content']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: white; border: 1px solid {LIGHT_GRAY}; padding: 10px; border-radius: 4px; margin-bottom: 8px;">
                    <strong style="color: {MIT_NAVY};">Copilot:</strong><br>{msg['content']}
                </div>
                """, unsafe_allow_html=True)
    
    # Check for pending prompt from button
    if st.session_state.get("pending_prompt"):
        user_input = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        process_chat_message(case.case_id, user_input, client, chat_history)
        st.rerun()
    
    # Chat input
    user_input = st.chat_input(
        "Ask about this case...",
        key="copilot_input"
    )
    
    if user_input:
        process_chat_message(case.case_id, user_input, client, chat_history)
        st.rerun()
    
    # Transparency Footer
    last_meta = None
    for msg in reversed(chat_history):
        if msg.get("metadata"):
            last_meta = msg["metadata"]
            break
    
    st.markdown(f"""
    <div class="transparency-footer">
        <div class="transparency-item">
            <span>Active Agent</span>
            <span>{last_meta.get('agent', 'None') if last_meta else 'None'}</span>
        </div>
        <div class="transparency-item">
            <span>Intent Classification</span>
            <span>{last_meta.get('intent', 'N/A') if last_meta else 'N/A'}</span>
        </div>
        <div class="transparency-item">
            <span>Documents Retrieved</span>
            <span>{last_meta.get('docs_retrieved', 0) if last_meta else 0}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def process_chat_message(case_id: str, message: str, client, chat_history: list) -> None:
    """Process a chat message."""
    chat_history.append({
        "role": "user",
        "content": message
    })
    
    try:
        response = client.send_message(
            case_id=case_id,
            message=message
        )
        
        chat_history.append({
            "role": "assistant",
            "content": response.assistant_message,
            "metadata": {
                "intent": response.intent_classified,
                "agent": response.agents_called[0] if response.agents_called else None,
                "docs_retrieved": response.retrieval_context.get("documents_retrieved", 0) if response.retrieval_context else 0
            }
        })
    except APIError as e:
        chat_history.append({
            "role": "assistant",
            "content": f"Unable to process request: {e.message}"
        })


def get_next_stage(current_stage: str) -> str:
    """Get the next DTP stage."""
    transitions = {
        "DTP-01": "DTP-02",
        "DTP-02": "DTP-03",
        "DTP-03": "DTP-04",
        "DTP-04": "DTP-05",
        "DTP-05": "DTP-06",
        "DTP-06": "DTP-06"
    }
    return transitions.get(current_stage, "Next Stage")


def render_case_copilot(case_id: str):
    """
    Render the enterprise case copilot interface.
    """
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        st.error("System not available. Please try again later.")
        return
    
    # Load case
    try:
        case = client.get_case(case_id)
    except APIError as e:
        st.error(f"Failed to load case: {e.message}")
        return
    
    # Inject enterprise styles
    inject_styles()
    
    # Back navigation
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("Back to Dashboard", key="back_btn"):
            st.session_state.selected_case_id = None
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    # Full-width Case Header
    render_case_header(case)
    
    # Three-column layout
    col_context, col_decision, col_copilot = st.columns([2.5, 4.5, 3])
    
    with col_context:
        render_context_column(case)
    
    with col_decision:
        render_decision_column(case, client)
    
    with col_copilot:
        render_copilot_column(case, client)
