"""
Streamlit Frontend Application.

This is the main entry point for the frontend.
All backend communication goes through the API client.
"""
import streamlit as st
import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from frontend.api_client import get_api_client
from frontend.pages.case_dashboard import render_case_dashboard, render_case_detail
from frontend.pages.case_copilot import render_case_copilot
from frontend.pages.knowledge_management import render_knowledge_management


# Page config
st.set_page_config(
    page_title="Agentic Sourcing Copilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-top: 0;
    }
    .stButton button {
        border-radius: 8px;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    
    # Initialize session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
    
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🤖 Agentic Sourcing")
        st.markdown("---")
        
        # Navigation
        pages = {
            "dashboard": "📋 Case Dashboard",
            "copilot": "💬 Case Copilot",
            "knowledge": "📚 Knowledge & Data"
        }
        
        for page_id, page_name in pages.items():
            if st.button(
                page_name,
                key=f"nav_{page_id}",
                use_container_width=True,
                type="primary" if st.session_state.current_page == page_id else "secondary"
            ):
                st.session_state.current_page = page_id
                st.rerun()
        
        st.markdown("---")
        
        # Backend status
        client = get_api_client()
        health = client.health_check()
        
        if health.get("status") == "healthy":
            st.success("✅ Backend connected")
        else:
            st.error("❌ Backend offline")
            st.markdown("Start with:")
            st.code("python -m uvicorn backend.main:app --reload", language="bash")
        
        st.markdown("---")
        
        # Quick help
        with st.expander("ℹ️ About"):
            st.markdown("""
            **Agentic Sourcing Copilot**
            
            A human-in-the-loop, multi-agent 
            decision-support system for 
            procurement sourcing.
            
            **DTP Stages:**
            - DTP-01: Strategy
            - DTP-02: Planning
            - DTP-03: Sourcing
            - DTP-04: Negotiation
            - DTP-05: Contracting
            - DTP-06: Execution
            
            **Governance:**
            - All decisions require approval
            - Agents can explore, not decide
            - Full traceability
            """)
    
    # Main content
    if st.session_state.current_page == "dashboard":
        render_case_dashboard()
        
    elif st.session_state.current_page == "copilot":
        case_id = st.session_state.get("selected_case_id")
        
        if not case_id:
            st.info("👈 Select a case from the Dashboard to start the copilot")
            st.markdown("Or enter a case ID directly:")
            case_input = st.text_input("Case ID", key="direct_case_id")
            if st.button("Open Case"):
                if case_input:
                    st.session_state.selected_case_id = case_input
                    st.rerun()
        else:
            render_case_copilot(case_id)
            
    elif st.session_state.current_page == "knowledge":
        render_knowledge_management()


if __name__ == "__main__":
    main()

