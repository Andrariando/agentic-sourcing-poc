"""
Case Copilot Page - Enterprise Decision Console (Redesigned)

Design Philosophy:
- The decision is the focal point
- The AI is an advisor via conversation (not buttons)
- The human is accountable
- Content first (case details), action second (chat), outputs last (artifacts)

Layout:
- Top: Condensed case header
- Middle: Case Details (60%) | Chat (40%)
- Bottom: Full-width artifacts panel

MIT Color System:
- MIT Navy (#003A8F): Structure and hierarchy
- MIT Cardinal Red (#A31F34): Actions and urgency only
"""
import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime

from frontend.api_client import get_api_client, APIError
from shared.constants import DTP_STAGES, DTP_STAGE_NAMES, ArtifactType
from backend.artifacts.placement import get_artifact_placement, ArtifactPlacement, get_artifacts_by_placement


# MIT Color Constants
MIT_NAVY = "#003A8F"
MIT_CARDINAL = "#A31F34"
NEAR_BLACK = "#1F1F1F"
CHARCOAL = "#4A4A4A"
LIGHT_GRAY = "#D9D9D9"
WHITE = "#FFFFFF"
SUCCESS_GREEN = "#2E7D32"
WARNING_YELLOW = "#F9A825"


def inject_styles():
    """Inject enterprise CSS styles for the new layout."""
    st.markdown(f"""
    <style>
        /* Case Header - Condensed */
        .case-header-condensed {{
            background: linear-gradient(135deg, {MIT_NAVY} 0%, #002D6D 100%);
            color: {WHITE};
            padding: 16px 24px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .case-header-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0;
        }}
        .case-header-metrics {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 0.85rem;
        }}
        .case-header-metrics .metric {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .case-header-metrics .metric-label {{
            opacity: 0.8;
        }}
        .case-header-metrics .metric-value {{
            font-weight: 600;
        }}
        .status-pill {{
            background-color: {MIT_CARDINAL};
            padding: 4px 12px;
            border-radius: 16px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-pill.success {{
            background-color: {SUCCESS_GREEN};
        }}
        
        /* Section Cards */
        .section-card {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .section-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid {LIGHT_GRAY};
        }}
        .section-card-title {{
            color: {MIT_NAVY};
            font-size: 0.9rem;
            font-weight: 600;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-card-content {{
            font-size: 0.875rem;
            color: {NEAR_BLACK};
        }}
        
        /* Detail Rows */
        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #F0F0F0;
            font-size: 0.875rem;
        }}
        .detail-row:last-child {{
            border-bottom: none;
        }}
        .detail-label {{
            color: {CHARCOAL};
        }}
        .detail-value {{
            color: {NEAR_BLACK};
            font-weight: 500;
        }}
        
        /* Signal Indicators */
        .signal-indicator {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }}
        .signal-indicator.green {{ background-color: {SUCCESS_GREEN}; }}
        .signal-indicator.yellow {{ background-color: {WARNING_YELLOW}; }}
        .signal-indicator.red {{ background-color: {MIT_CARDINAL}; }}
        
        /* Artifacts Panel */
        .artifacts-panel {{
            background-color: #FAFBFC;
            border: 1px solid {LIGHT_GRAY};
            border-radius: 8px;
            padding: 16px;
            margin-top: 20px;
        }}
        .artifacts-header {{
            color: {MIT_NAVY};
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .artifact-card {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 8px;
        }}
        .artifact-card:hover {{
            border-color: {MIT_NAVY};
        }}
        
        /* Chat Interface */
        .chat-header {{
            color: {MIT_NAVY};
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .chat-subtitle {{
            color: {CHARCOAL};
            font-size: 0.8rem;
            margin-bottom: 16px;
        }}
        
        /* Governance inline */
        .governance-inline {{
            background-color: #FFF8E1;
            border: 1px solid {WARNING_YELLOW};
            border-radius: 6px;
            padding: 12px;
            margin-top: 16px;
            font-size: 0.85rem;
        }}
        .governance-inline.waiting {{
            background-color: #FFEBEE;
            border-color: {MIT_CARDINAL};
        }}
        
        /* Override Streamlit defaults */
        .stButton > button {{
            border-radius: 6px;
            font-weight: 500;
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid {LIGHT_GRAY};
            border-radius: 6px;
        }}
        
        /* Timeline styles */
        .timeline-item {{
            display: flex;
            gap: 12px;
            padding: 8px 0;
            border-left: 2px solid {LIGHT_GRAY};
            padding-left: 16px;
            margin-left: 8px;
        }}
        .timeline-item:last-child {{
            border-left-color: transparent;
        }}
        .timeline-dot {{
            width: 10px;
            height: 10px;
            background-color: {MIT_NAVY};
            border-radius: 50%;
            margin-left: -21px;
            margin-top: 4px;
        }}
        .timeline-content {{
            flex: 1;
        }}
        .timeline-time {{
            font-size: 0.75rem;
            color: {CHARCOAL};
        }}
        .timeline-action {{
            font-size: 0.85rem;
            color: {NEAR_BLACK};
        }}
        
        /* Chat Message Styling */
        div[data-testid="stChatMessage"] {{
            background-color: #F8F9FA;
            border: 1px solid #E0E0E0;
            border-radius: 12px;
            padding: 10px;
            margin-bottom: 10px;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_case_header_condensed(case) -> None:
    """Render condensed case header with key metrics only."""
    dtp_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
    is_waiting = case.status == "Waiting for Human Decision"
    
    # Determine status class
    status_class = "status-pill" if is_waiting else "status-pill success"
    
    st.markdown(f"""
    <div class="case-header-condensed">
        <div>
            <h1 class="case-header-title">{case.name}</h1>
            <div style="font-size: 0.8rem; opacity: 0.8; margin-top: 4px;">
                {case.case_id} • {case.category_id}
            </div>
        </div>
        <div class="case-header-metrics">
            <div class="metric">
                <span class="metric-label">Stage:</span>
                <span class="metric-value">{case.dtp_stage}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Supplier:</span>
                <span class="metric-value">{case.supplier_id or 'Not Assigned'}</span>
            </div>
            <span class="{status_class}">{case.status}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_case_details_panel(case, client) -> None:
    """
    Render unified Case Details Panel (left 60%).
    Consolidates all case information into a single scrollable panel.
    
    Sections:
    1. Quick Overview
    2. Strategy Rationale
    3. Supporting Context
    4. Governance Status
    5. Documents & Timeline
    """
    
    # ===== Section 1: Quick Overview =====
    st.markdown("""
    <div class="section-card">
        <div class="section-card-header">
            <h3 class="section-card-title">📋 Quick Overview</h3>
        </div>
        <div class="section-card-content">
    """, unsafe_allow_html=True)
    
    # Get recommendation from latest agent output
    recommendation = "Pending Analysis"
    confidence = 0.0
    if case.latest_agent_output:
        output = case.latest_agent_output
        rec = output.get("recommended_strategy") if isinstance(output, dict) else getattr(output, "recommended_strategy", None)
        if rec:
            recommendation = rec
        conf = output.get("confidence") if isinstance(output, dict) else getattr(output, "confidence", None)
        if conf:
            confidence = conf
    
    # Overview details
    st.markdown(f"""
        <div class="detail-row">
            <span class="detail-label">Case ID</span>
            <span class="detail-value">{case.case_id}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Category</span>
            <span class="detail-value">{case.category_id}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Supplier</span>
            <span class="detail-value">{case.supplier_id or 'Not Assigned'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Contract</span>
            <span class="detail-value">{case.contract_id or 'Not Specified'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Trigger Source</span>
            <span class="detail-value">{case.trigger_source}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Created</span>
            <span class="detail-value">{case.created_date}</span>
        </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ===== Section 2: Strategy Rationale =====
    st.markdown(f"""
    <div class="section-card">
        <div class="section-card-header">
            <h3 class="section-card-title">🎯 Recommended Strategy</h3>
        </div>
        <div class="section-card-content">
            <div style="font-size: 1.25rem; font-weight: 600; color: {MIT_NAVY}; margin-bottom: 12px;">
                {recommendation}
            </div>
            <div style="display: flex; gap: 16px; margin-bottom: 12px;">
                <span style="font-size: 0.85rem;">
                    <strong>Confidence:</strong> {confidence:.0%}
                </span>
                <span style="font-size: 0.85rem;">
                    <strong>Stage:</strong> {case.dtp_stage}
                </span>
            </div>
    """, unsafe_allow_html=True)
    
    # Show rationale if available
    rationale = []
    if case.latest_agent_output:
        output = case.latest_agent_output
        rationale = output.get("rationale", []) if isinstance(output, dict) else getattr(output, "rationale", [])
    
    if rationale:
        st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)
        for item in rationale[:5]:
            st.markdown(f"""
            <div style="display: flex; align-items: flex-start; gap: 8px; padding: 4px 0; font-size: 0.85rem;">
                <span style="color: {SUCCESS_GREEN};">✓</span>
                <span>{item}</span>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    
    # ===== Section 3: Supporting Context (Signals & Findings) =====
    st.markdown("""
    <div class="section-card">
        <div class="section-card-header">
            <h3 class="section-card-title">📊 Signals & Key Findings</h3>
        </div>
        <div class="section-card-content">
    """, unsafe_allow_html=True)
    
    # Parse key findings for signals
    if case.summary and case.summary.key_findings:
        for finding in case.summary.key_findings[:5]:
            indicator = "yellow"
            if "high" in finding.lower() or "breach" in finding.lower() or "decline" in finding.lower():
                indicator = "red"
            elif "strong" in finding.lower() or "improving" in finding.lower() or "good" in finding.lower():
                indicator = "green"
            
            st.markdown(f"""
            <div style="display: flex; align-items: flex-start; padding: 6px 0; font-size: 0.85rem;">
                <span class="signal-indicator {indicator}"></span>
                <span>{finding}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="color: {CHARCOAL}; font-size: 0.85rem;">No signals detected yet. Ask the copilot to scan for signals.</div>', unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)
    
    # ===== Section 4: Governance Status =====
    is_waiting = case.status == "Waiting for Human Decision"
    dtp_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
    
    governance_class = "governance-inline waiting" if is_waiting else "governance-inline"
    
    st.markdown(f"""
    <div class="{governance_class}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong>🔐 Governance Status</strong>
                <div style="margin-top: 4px; font-size: 0.8rem;">
                    Stage: {case.dtp_stage} - {dtp_name} | 
                    Last Agent: {case.latest_agent_name or 'None'}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-weight: 600; color: {MIT_CARDINAL if is_waiting else SUCCESS_GREEN};">
                    {'⚠️ Approval Required' if is_waiting else '✓ In Progress'}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show approval buttons if waiting
    if is_waiting:
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ APPROVE", key="details_approve", use_container_width=True):
                try:
                    result = client.approve_decision(case.case_id)
                    st.success(f"Approved! Advanced to {result.new_dtp_stage}")
                    st.rerun()
                except APIError as e:
                    st.error(f"Error: {e.message}")
        with col2:
            if st.button("↩️ REVISE", key="details_reject", use_container_width=True):
                try:
                    client.reject_decision(case.case_id)
                    st.info("Revision requested")
                    st.rerun()
                except APIError as e:
                    st.error(f"Error: {e.message}")
    
    # ===== Section 5: Documents & Timeline =====
    with st.expander("📁 Documents & Activity Timeline", expanded=False):
        # Documents
        st.markdown(f"<div style='font-weight: 600; color: {MIT_NAVY}; margin-bottom: 8px;'>Documents</div>", unsafe_allow_html=True)
        
        # Try to get documents from API
        try:
            docs = client.list_documents(category_id=case.category_id)
            if docs and docs.documents:
                for doc in docs.documents[:5]:
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85rem; border-bottom: 1px solid #F0F0F0;">
                        <span>📄 {doc.filename}</span>
                        <span style="color: {SUCCESS_GREEN}; font-size: 0.75rem;">Ingested</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="color: {CHARCOAL}; font-size: 0.85rem;">No documents ingested yet.</div>', unsafe_allow_html=True)
        except:
            st.markdown(f'<div style="color: {CHARCOAL}; font-size: 0.85rem;">No documents ingested yet.</div>', unsafe_allow_html=True)
        
        # Timeline
        st.markdown(f"<div style='font-weight: 600; color: {MIT_NAVY}; margin: 16px 0 8px 0;'>Recent Activity</div>", unsafe_allow_html=True)
        
        if case.activity_log and len(case.activity_log) > 0:
            for entry in case.activity_log[-5:]:
                timestamp = entry.get('timestamp', '')[:16] if isinstance(entry, dict) else str(entry)[:16]
                action = entry.get('action', 'Action') if isinstance(entry, dict) else 'Activity'
                agent = entry.get('agent_name', '') if isinstance(entry, dict) else ''
                
                st.markdown(f"""
                <div class="timeline-item">
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-time">{timestamp}</div>
                        <div class="timeline-action">{action} {f'({agent})' if agent else ''}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color: {CHARCOAL}; font-size: 0.85rem;">No activity yet. Start by asking the copilot a question.</div>', unsafe_allow_html=True)


def render_chat_interface(case, client) -> None:
    """
    Render the Chat Interface (right 40%).
    
    Features:
    - Scrollable chat history (Cursor-like)
    - No action buttons (conversation-driven)
    - Chat input at bottom
    - Auto-scroll to latest message
    """
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = {}
    
    # ISSUE #5 FIX: Force sync from backend when case changes
    # Previously, frontend session_state could drift from backend activity_log
    # Now we force reload when case ID changes to ensure consistency
    if "_last_case_id" not in st.session_state:
        st.session_state._last_case_id = None
    
    force_reload = st.session_state._last_case_id != case.case_id
    
    if case.case_id not in st.session_state.chat_history or force_reload:
        st.session_state._last_case_id = case.case_id
        
        # Try to load chat history from activity log
        chat_history = []
        
        if case.activity_log:
            # Extract chat messages from activity log
            for entry in case.activity_log:
                if isinstance(entry, dict) and entry.get("action", "").startswith("Chat:"):
                    role = "user" if "user" in entry.get("action", "").lower() else "assistant"
                    details = entry.get("details", {})
                    message = details.get("message", "")
                    metadata = details.get("metadata", {})
                    
                    if message:
                        chat_history.append({
                            "role": role,
                            "content": message,
                            "timestamp": entry.get("timestamp", ""),
                            "metadata": metadata if metadata else None
                        })
        
        # If no chat history found, add welcome message
        if not chat_history:
            welcome_content = f"""👋 Hello! I'm your Case Copilot for **{case.case_id}**.

I can help you with:
- Scanning for sourcing signals
- Scoring and evaluating suppliers
- Drafting RFx documents
- Preparing for negotiations
- Extracting contract terms
- Creating implementation plans

What would you like to do?"""
            chat_history = [{
                "role": "assistant",
                "content": welcome_content,
                "metadata": {"agent": "System", "intent": "Welcome"}
            }]
        
        st.session_state.chat_history[case.case_id] = chat_history
    
    chat_history = st.session_state.chat_history[case.case_id]
    
    # Header
    st.markdown(f"""
    <div class="chat-header">
        💬 Case Copilot
    </div>
    <div class="chat-subtitle">
        Ask questions or request actions for {case.case_id}
    </div>
    """, unsafe_allow_html=True)
    
    # Scrollable chat container with fixed height
    chat_container = st.container(height=500)
    
    with chat_container:
        for msg in chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
    
    # Transparency footer - show last metadata
    last_meta = None
    for msg in reversed(chat_history):
        if msg.get("metadata"):
            last_meta = msg["metadata"]
            break
    
    if last_meta:
        agent_display = last_meta.get('agent', 'System')
        intent_display = last_meta.get('intent', 'N/A')
        docs_display = last_meta.get('docs_retrieved', 0)
        
        st.markdown(f"""
        <div style="background-color: #F8F9FA; border: 1px solid {LIGHT_GRAY}; border-radius: 4px; padding: 6px 10px; margin-top: 8px; font-size: 0.7rem; color: {CHARCOAL};">
            <span>Agent: <strong>{agent_display}</strong></span> • 
            <span>Intent: <strong>{intent_display}</strong></span> • 
            <span>Docs: <strong>{docs_display}</strong></span>
        </div>
        """, unsafe_allow_html=True)
    
    # Chat input at bottom
    user_input = st.chat_input(
        "Ask about this case...",
        key="copilot_input"
    )
    
    if user_input:
        process_chat_message(case.case_id, user_input, client, chat_history)
        st.rerun()

    # Render Agent Logs (Internal Monologue) - Separate from Chat
    _render_agent_logs(case)


def _render_agent_logs(case):
    """Render internal agent dialogue logs (reasoning/critique) separately."""
    if not case.activity_log:
        return

    # Filter for Agent Dialogue logs
    dialogue_logs = [
        entry for entry in case.activity_log 
        if (isinstance(entry, dict) and entry.get("task_name") == "Agent Dialogue") or
           (hasattr(entry, "task_name") and entry.task_name == "Agent Dialogue")
    ]
    
    if not dialogue_logs:
        return
        
    with st.expander("🔍 Agent Logs (Internal Monologue)", expanded=False):
        for entry in reversed(dialogue_logs): # Newest first
            if isinstance(entry, dict):
                agent = entry.get("agent_name", "Unknown")
                timestamp = entry.get("timestamp", "")[:19]
                summary = entry.get("output_summary", "")
                payload = entry.get("output_payload", {})
            else:
                agent = entry.agent_name
                timestamp = entry.timestamp[:19]
                summary = entry.output_summary
                payload = entry.output_payload
            
            # Extract reasoning/message from payload if available
            reasoning = payload.get("reasoning", "No reasoning provided")
            status = payload.get("status", "Info")
            
            st.markdown(f"""
            <div style="background-color: #F8F9FA; border-left: 3px solid {MIT_NAVY}; padding: 8px 12px; margin-bottom: 8px; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <strong>{agent}</strong>
                    <span style="color: {CHARCOAL}; font-size: 0.75rem;">{timestamp}</span>
                </div>
                <div style="font-weight: 600; font-size: 0.8rem; color: {MIT_NAVY}; margin-bottom: 4px;">
                    Status: {status}
                </div>
                <div style="color: {NEAR_BLACK}; margin-bottom: 6px;">
                    {summary}
                </div>
                <div style="font-size: 0.8rem; color: {CHARCOAL}; font-style: italic; background-color: #EEE; padding: 4px; border-radius: 4px;">
                    Reasoning: {reasoning}
                </div>
            </div>
            """, unsafe_allow_html=True)


def process_chat_message(case_id: str, message: str, client, chat_history: list) -> None:
    """Process a chat message and get response from backend."""
    chat_history.append({
        "role": "user",
        "content": message
    })
    
    try:
        with st.spinner("Thinking..."):
            response = client.send_message(
                case_id=case_id,
                message=message
            )
        
        chat_history.append({
            "role": "assistant",
            "content": response.assistant_message,
            "metadata": {
                "intent": response.intent_classified,
                "agent": response.agents_called[0] if response.agents_called else "System",
                "docs_retrieved": response.retrieval_context.get("documents_retrieved", 0) if response.retrieval_context else 0
            }
        })
    except APIError as e:
        chat_history.append({
            "role": "assistant",
            "content": f"I encountered an error processing your request: {e.message}\n\nPlease try again or rephrase your question."
        })


def render_artifacts_panel_full_width(case, client) -> None:
    """
    Render full-width Artifacts Panel at the bottom.
    
    Features:
    - Horizontal tabs for artifact types
    - Expandable cards with full details
    - Status badges (VERIFIED, PARTIAL, UNVERIFIED)
    """
    
    st.markdown(f"""
    <div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid {LIGHT_GRAY};">
        <div class="artifacts-header">
            📦 Artifacts & Outputs
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # NEW: Fetch all artifact packs for the case
    try:
        artifact_packs = client.get_artifact_packs(case.case_id)
    except Exception as e:
        st.warning(f"Could not load artifact history: {e}")
        artifact_packs = []
    
    # Extract all artifacts from all packs
    all_artifacts = []
    for pack in artifact_packs:
        if isinstance(pack, dict):
            all_artifacts.extend(pack.get("artifacts", []))
        else:
            all_artifacts.extend(getattr(pack, "artifacts", []))
    
    # Horizontal tabs for artifact types
    tabs = st.tabs([
        "📊 Signals", 
        "⭐ Scoring", 
        "📝 RFx Drafts", 
        "🤝 Negotiation", 
        "📄 Contract", 
        "🚀 Implementation", 
        "📜 History",
        "🔍 Audit Trail"
    ])
    
    # Get latest agent info for context
    output = case.latest_agent_output
    agent_name = case.latest_agent_name
    
    with tabs[0]:  # Signals
        _render_signals_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[1]:  # Scoring
        _render_scoring_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[2]:  # RFx Drafts
        _render_rfx_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[3]:  # Negotiation
        _render_negotiation_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[4]:  # Contract
        _render_contract_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[5]:  # Implementation
        _render_implementation_artifacts(case, output, agent_name, all_artifacts)
    
    with tabs[6]:  # History
        _render_activity_history(case)
    
    with tabs[7]:  # Audit Trail
        _render_audit_history_from_packs(artifact_packs)


def _render_signals_artifacts(case, output, agent_name, all_artifacts):
    """Render signals tab content."""
    # Filter artifacts that belong in Decision Console or Case Summary
    signals_artifacts = [a for a in all_artifacts if get_artifact_placement(a.get("type")) in [ArtifactPlacement.DECISION_CONSOLE, ArtifactPlacement.CASE_SUMMARY]]
    # Further filter by signal types
    signals_artifacts = [a for a in signals_artifacts if "SIGNAL" in a.get("type", "")]
    
    if signals_artifacts:
        for art in signals_artifacts:
            st.markdown(f"#### {art.get('title')}")
            content = art.get("content_text") or str(art.get("content", ""))
            st.markdown(content)
            
            # Show grounding if available
            if art.get("grounded_in"):
                with st.expander("🔍 Grounding Sources"):
                    for g in art["grounded_in"]:
                        st.markdown(f"- **{g.get('source_name')}**: {g.get('excerpt')[:200]}...")
            st.markdown("---")
    else:
        st.info("No signals detected yet. Ask the copilot: \"Scan for sourcing signals\"")


def _render_scoring_artifacts(case, output, agent_name, all_artifacts):
    """Render scoring tab content."""
    # Filter for Supplier Compare section
    scoring_artifacts = [a for a in all_artifacts if get_artifact_placement(a.get("type")) == ArtifactPlacement.SUPPLIER_COMPARE]
    
    if scoring_artifacts:
        for art in scoring_artifacts:
            st.markdown(f"#### {art.get('title')}")
            
            # Special handling for evaluation scorecard
            content = art.get("content")
            if isinstance(content, dict) and "shortlisted_suppliers" in content:
                suppliers = content["shortlisted_suppliers"]
                # Create a table-like display
                st.markdown(f"""
                <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 8px; padding: 8px 12px; background-color: {MIT_NAVY}; color: white; font-weight: 600; font-size: 0.8rem; border-radius: 4px 4px 0 0;">
                    <span>Supplier</span>
                    <span>Score</span>
                    <span>Status</span>
                    <span>Comments</span>
                </div>
                """, unsafe_allow_html=True)
                
                for s in suppliers:
                    name = s.get('name', s.get('supplier_name', 'Unknown'))
                    score = s.get('score', s.get('total_score', 0))
                    status = s.get('status', 'Eligible')
                    comments = s.get('comments', '')[:50]
                    
                    st.markdown(f"""
                    <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 8px; padding: 12px; border: 1px solid {LIGHT_GRAY}; border-top: none; font-size: 0.85rem;">
                        <span style="font-weight: 500;">{name}</span>
                        <span style="color: {MIT_NAVY}; font-weight: bold;">{score if isinstance(score, (int, float)) else 0:.1f}/10</span>
                        <span>{status}</span>
                        <span style="color: {CHARCOAL}; font-size: 0.75rem;">{comments}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(art.get("content_text") or str(art.get("content", "")))
            st.markdown("---")
    else:
        st.info("No supplier scores available yet. Ask the copilot: \"Score suppliers\"")


def _render_rfx_artifacts(case, output, agent_name, all_artifacts):
    """Render RFx drafts tab content."""
    # RFx artifacts usually in Decision Console or Activity Log
    rfx_artifacts = [a for a in all_artifacts if "RFX" in a.get("type", "")]
    
    if rfx_artifacts:
        for art in rfx_artifacts:
            with st.expander(f"📄 {art.get('title')}"):
                st.markdown(art.get("content_text") or str(art.get("content", "")))
    else:
        st.info("No RFx drafts created yet. Ask the copilot: \"Draft RFx\"")


def _render_negotiation_artifacts(case, output, agent_name, all_artifacts):
    """Render negotiation tab content."""
    neg_artifacts = [a for a in all_artifacts if any(t in a.get("type", "") for t in ["NEGOTIATION", "LEVERAGE", "TARGET_TERMS"])]
    
    if neg_artifacts:
        for art in neg_artifacts:
            st.markdown(f"#### {art.get('title')}")
            st.markdown(art.get("content_text") or str(art.get("content", "")))
            st.markdown("---")
    else:
        st.info("No negotiation plan created yet. Ask the copilot: \"Prepare negotiation plan\"")


def _render_contract_artifacts(case, output, agent_name, all_artifacts):
    """Render contract tab content."""
    # Contract artifacts in Risk Panel
    contract_artifacts = [a for a in all_artifacts if get_artifact_placement(a.get("type")) == ArtifactPlacement.RISK_PANEL]
    
    if contract_artifacts:
        for art in contract_artifacts:
            st.markdown(f"#### {art.get('title')}")
            st.markdown(art.get("content_text") or str(art.get("content", "")))
            st.markdown("---")
    else:
        st.info("No contract analysis available yet. Ask the copilot: \"Review contract\"")


def _render_implementation_artifacts(case, output, agent_name, all_artifacts):
    """Render implementation tab content."""
    # Implementation artifacts in Timeline
    impl_artifacts = [a for a in all_artifacts if get_artifact_placement(a.get("type")) == ArtifactPlacement.TIMELINE]
    
    if impl_artifacts:
        for art in impl_artifacts:
            st.markdown(f"#### {art.get('title')}")
            st.markdown(art.get("content_text") or str(art.get("content", "")))
            st.markdown("---")
    else:
        st.info("No implementation plan ready yet. Ask the copilot: \"Draft implementation plan\"")


def _render_audit_history_from_packs(packs):
    """Render the detailed audit trail of all agent executions."""
    if not packs:
        st.info("No historical data available for this case.")
        return
        
    st.markdown("### 🔍 Agent Execution Audit Trail")
    st.markdown("Full history of all agent calls, reasoning, and produced artifacts.")
    
    for i, pack in enumerate(reversed(packs)):
        with st.expander(f"Execution {len(packs)-i}: {pack.get('agent_name')} ({pack.get('created_at', '')[:16]})"):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"**Agent:** {pack.get('agent_name')}")
                st.markdown(f"**Timestamp:** {pack.get('created_at')}")
                st.markdown(f"**Pack ID:** `{pack.get('pack_id')}`")
            
            with col2:
                # Show execution metadata if available
                meta = pack.get("execution_metadata")
                if meta:
                    st.markdown(f"**User Message:** {meta.get('user_message', 'N/A')}")
                    st.markdown(f"**Tokens:** {meta.get('total_tokens_used', 0)}")
                    st.markdown(f"**Tasks:** {meta.get('completed_tasks', 0)}/{meta.get('total_tasks', 0)}")
            
            # Show tasks
            st.markdown("#### Tasks Executed")
            tasks = pack.get("tasks_executed", [])
            for t in tasks:
                st.markdown(f"- {t}")
                
            # Show artifacts
            st.markdown("#### Artifacts Produced")
            for art in pack.get("artifacts", []):
                st.info(f"📄 {art.get('title')} ({art.get('type')})")


def _render_activity_history(case):
    """Render activity history tab."""
    if case.activity_log and len(case.activity_log) > 0:
        for entry in case.activity_log[-10:]:
            timestamp = entry.get('timestamp', '')[:19] if isinstance(entry, dict) else str(entry)[:19]
            action = entry.get('action', 'Activity') if isinstance(entry, dict) else 'Activity'
            agent = entry.get('agent_name', '') if isinstance(entry, dict) else ''
            
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid {LIGHT_GRAY}; font-size: 0.85rem;">
                <span style="color: {CHARCOAL};">{timestamp}</span>
                <span style="flex: 1; margin-left: 16px;">{action}</span>
                <span style="color: {MIT_NAVY}; font-weight: 500;">{agent}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Activity log will appear here as you work on the case.")


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
    Render the Procurement Workbench interface (Redesigned).
    
    New Layout:
    - Top: Condensed case header (key metrics only)
    - Middle: Case Details (60%) | Chat (40%)
    - Bottom: Full-width artifacts panel
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
    
    # Welcome Title
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 30px; padding: 20px 0;">
        <h1 style="color: {MIT_CARDINAL}; font-size: 2.2rem; margin-bottom: 8px; font-weight: 700;">Welcome to MIT SCALE Expo</h1>
        <h3 style="color: {MIT_NAVY}; font-size: 1.4rem; font-weight: 400; margin-top: 0;">Dynamic Sourcing Pipelines Using Agentic AI</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Back navigation
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("← Dashboard", key="back_btn"):
            st.session_state.selected_case_id = None
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    # Condensed Case Header (full width)
    render_case_header_condensed(case)
    
    # Main layout: Case Details (60%) | Chat (40%)
    col_details, col_chat = st.columns([0.6, 0.4], gap="medium")
    
    with col_details:
        render_case_details_panel(case, client)
    
    with col_chat:
        render_chat_interface(case, client)
    
    # Full-width Artifacts Panel at bottom
    render_artifacts_panel_full_width(case, client)
