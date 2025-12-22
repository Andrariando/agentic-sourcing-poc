"""
Case Copilot Page.

Interactive chat interface with Supervisor-governed agents.
"""
import streamlit as st
from typing import Optional, List

from frontend.api_client import get_api_client, APIError
from shared.constants import DTP_STAGES, DTP_STAGE_NAMES


def render_case_copilot(case_id: str):
    """
    Render the copilot chat interface for a case.
    
    All interactions go through the Supervisor for governance.
    """
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        st.error("⚠️ Backend is not available")
        return
    
    # Load case
    try:
        case = client.get_case(case_id)
    except APIError as e:
        st.error(f"Failed to load case: {e.message}")
        return
    
    # Header
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.title(f"💬 {case.name}")
    
    with col2:
        if st.button("← Back to Dashboard"):
            st.session_state.selected_case_id = None
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    # Case context sidebar
    with st.sidebar:
        st.markdown("### Case Context")
        st.markdown(f"**Case ID:** `{case.case_id}`")
        
        # DTP Progress
        st.markdown("**DTP Progress:**")
        current_idx = DTP_STAGES.index(case.dtp_stage) if case.dtp_stage in DTP_STAGES else 0
        
        for i, stage in enumerate(DTP_STAGES):
            if i < current_idx:
                st.markdown(f"✅ {stage} - {DTP_STAGE_NAMES.get(stage, stage)}")
            elif i == current_idx:
                st.markdown(f"🔵 **{stage} - {DTP_STAGE_NAMES.get(stage, stage)}** ← Current")
            else:
                st.markdown(f"⚪ {stage} - {DTP_STAGE_NAMES.get(stage, stage)}")
        
        st.markdown("---")
        st.markdown(f"**Status:** {case.status}")
        st.markdown(f"**Category:** `{case.category_id}`")
        
        if case.supplier_id:
            st.markdown(f"**Supplier:** `{case.supplier_id}`")
        
        # Latest output summary
        if case.latest_agent_name:
            st.markdown("---")
            st.markdown(f"**Last Agent:** {case.latest_agent_name}")
    
    # Chat container
    st.markdown("---")
    
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = {}
    
    if case_id not in st.session_state.chat_history:
        st.session_state.chat_history[case_id] = []
    
    chat_history = st.session_state.chat_history[case_id]
    
    # Display chat history
    for msg in chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Show metadata for assistant messages
            if msg["role"] == "assistant" and msg.get("metadata"):
                meta = msg["metadata"]
                with st.expander("📊 Details"):
                    st.markdown(f"**Intent:** {meta.get('intent', 'N/A')}")
                    st.markdown(f"**Agent:** {meta.get('agent', 'N/A')}")
                    st.markdown(f"**Tokens:** {meta.get('tokens', 0)}")
                    if meta.get("retrieval"):
                        st.markdown(f"**Retrieved docs:** {meta['retrieval'].get('documents_retrieved', 0)}")
    
    # Human decision required
    if case.status == "Waiting for Human Decision":
        st.warning("⚠️ **Awaiting your decision**")
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("✅ Approve", type="primary", key="approve_btn"):
                try:
                    result = client.approve_decision(case_id)
                    st.success(f"Approved! Advanced to {result.new_dtp_stage}")
                    
                    # Add to chat
                    chat_history.append({
                        "role": "user",
                        "content": "✅ **Approved**"
                    })
                    chat_history.append({
                        "role": "assistant",
                        "content": f"Decision approved. Case advanced to **{result.new_dtp_stage}**."
                    })
                    
                    st.rerun()
                except APIError as e:
                    st.error(f"Failed: {e.message}")
        
        with col2:
            if st.button("❌ Reject", key="reject_btn"):
                try:
                    result = client.reject_decision(case_id)
                    st.info("Decision rejected.")
                    
                    chat_history.append({
                        "role": "user",
                        "content": "❌ **Rejected**"
                    })
                    chat_history.append({
                        "role": "assistant", 
                        "content": "Decision rejected. You can continue exploring or try a different approach."
                    })
                    
                    st.rerun()
                except APIError as e:
                    st.error(f"Failed: {e.message}")
        
        with col3:
            reject_reason = st.text_input("Reason (optional)", key="reject_reason")
    
    # Chat input
    user_input = st.chat_input(
        "Ask about this case or request an action...",
        key="chat_input",
        disabled=case.status == "Waiting for Human Decision"
    )
    
    if user_input:
        # Add user message
        chat_history.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Get response from backend
        with st.chat_message("assistant"):
            with st.spinner("Processing..."):
                try:
                    response = client.send_message(
                        case_id=case_id,
                        message=user_input
                    )
                    
                    st.markdown(response.assistant_message)
                    
                    # Show metadata
                    with st.expander("📊 Details"):
                        st.markdown(f"**Intent:** {response.intent_classified}")
                        if response.agents_called:
                            st.markdown(f"**Agent:** {response.agents_called[0]}")
                        st.markdown(f"**Tokens:** {response.tokens_used}")
                        if response.retrieval_context:
                            st.markdown(f"**Retrieved docs:** {response.retrieval_context.get('documents_retrieved', 0)}")
                    
                    # Add to history
                    chat_history.append({
                        "role": "assistant",
                        "content": response.assistant_message,
                        "metadata": {
                            "intent": response.intent_classified,
                            "agent": response.agents_called[0] if response.agents_called else None,
                            "tokens": response.tokens_used,
                            "retrieval": response.retrieval_context
                        }
                    })
                    
                    # Check if waiting for decision
                    if response.waiting_for_human:
                        st.rerun()
                    
                except APIError as e:
                    st.error(f"Error: {e.message}")
    
    # Example prompts
    with st.expander("💡 Example prompts"):
        st.markdown("""
        **Exploration (no state change):**
        - What is the current contract status?
        - What are the alternatives to renewing?
        - Compare supplier performance
        
        **Request action (may require approval):**
        - Recommend a strategy for this case
        - Evaluate potential suppliers
        - Create a negotiation plan
        
        **Get status:**
        - What is the current status?
        - What are the next steps?
        """)

