"""
Agentic Sourcing Copilot - Enterprise Frontend

MIT Color System:
- MIT Navy (#003A8F): Structure and hierarchy
- MIT Cardinal Red (#A31F34): Actions and urgency only
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


# MIT Colors
MIT_NAVY = "#003A8F"
MIT_CARDINAL = "#A31F34"
CHARCOAL = "#4A4A4A"
LIGHT_GRAY = "#D9D9D9"


# Page config
st.set_page_config(
    page_title="Agentic Sourcing Copilot",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global Styles
st.markdown(f"""
<style>
    /* Hide Streamlit's default page picker if it exists */
    [data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
        display: none !important;
    }}
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {{
        background-color: #FAFAFA;
        border-right: 1px solid {LIGHT_GRAY};
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        font-size: 0.9rem;
    }}
    
    /* Search input styling */
    [data-testid="stSidebar"] [data-baseweb="input"] {{
        background-color: white;
        border: 1px solid {LIGHT_GRAY};
        border-radius: 4px;
    }}
    [data-testid="stSidebar"] [data-baseweb="input"]:focus {{
        border-color: {MIT_NAVY};
    }}
    
    /* Navigation buttons */
    [data-testid="stSidebar"] .stButton > button {{
        width: 100%;
        text-align: left;
        padding: 12px 16px;
        border: 1px solid {LIGHT_GRAY};
        background-color: white;
        color: {CHARCOAL};
        font-weight: 500;
        border-radius: 4px;
        margin-bottom: 4px;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        border-color: {MIT_NAVY};
        color: {MIT_NAVY};
    }}
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background-color: {MIT_NAVY};
        border-color: {MIT_NAVY};
        color: white;
    }}
    
    /* Main content area */
    .main .block-container {{
        padding-top: 2rem;
        max-width: 1400px;
    }}
    
    /* Headers */
    h1, h2, h3 {{
        color: {MIT_NAVY};
    }}
    
    /* Primary buttons */
    .stButton > button[kind="primary"] {{
        background-color: {MIT_CARDINAL};
        border-color: {MIT_CARDINAL};
    }}
    
    /* Remove emoji from page title */
    .stApp header {{
        background-color: transparent;
    }}
    
    /* Status indicators */
    .status-healthy {{
        color: #2E7D32;
        font-weight: 500;
    }}
    .status-error {{
        color: {MIT_CARDINAL};
        font-weight: 500;
    }}
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point."""
    
    # Initialize session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
    
    if "selected_case_id" not in st.session_state:
        st.session_state.selected_case_id = None
    
    # Sidebar
    with st.sidebar:
        # Logo/Title
        st.markdown(f"""
        <div style="padding: 16px 0 24px 0; border-bottom: 2px solid {MIT_NAVY}; margin-bottom: 24px;">
            <div style="font-size: 1.25rem; font-weight: 700; color: {MIT_NAVY};">
                Agentic Sourcing
            </div>
            <div style="font-size: 0.75rem; color: {CHARCOAL}; margin-top: 4px;">
                Decision Support System
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Page search/filter
        pages = {
            "dashboard": "Case Dashboard",
            "copilot": "Case Copilot", 
            "knowledge": "Knowledge Management"
        }
        
        # Search input with functional suggestions
        search_query = st.text_input(
            "",
            value=st.session_state.get("page_search", ""),
            placeholder="app",
            key="page_search_input",
            label_visibility="collapsed"
        )
        
        # Update session state
        if search_query != st.session_state.get("page_search", ""):
            st.session_state.page_search = search_query
        
        # Filter pages based on search
        filtered_pages = {}
        if search_query:
            query_lower = search_query.lower()
            for page_id, page_name in pages.items():
                # Match against page name or keywords
                if (query_lower in page_name.lower() or 
                    query_lower in page_id.lower() or
                    (query_lower == "app" and page_id == "dashboard") or
                    (query_lower in ["case", "copilot"] and page_id == "copilot") or
                    (query_lower in ["case", "dashboard"] and page_id == "dashboard") or
                    (query_lower in ["knowledge", "management"] and page_id == "knowledge")):
                    filtered_pages[page_id] = page_name
        
        # Show clickable suggestions
        if search_query and filtered_pages:
            st.markdown(f'<div style="font-size: 0.7rem; color: {CHARCOAL}; margin-top: 8px; margin-bottom: 4px;">Suggestions:</div>', unsafe_allow_html=True)
            for page_id, page_name in filtered_pages.items():
                if st.button(
                    f"→ {page_name}",
                    key=f"search_suggestion_{page_id}",
                    use_container_width=True
                ):
                    st.session_state.current_page = page_id
                    st.session_state.page_search = ""  # Clear search
                    st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)
        elif search_query and not filtered_pages:
            st.markdown(f'<div style="font-size: 0.75rem; color: {CHARCOAL}; font-style: italic; margin-top: 8px;">No matches found</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
        
        # Navigation
        st.markdown(f'<div style="font-size: 0.7rem; color: {CHARCOAL}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Navigation</div>', unsafe_allow_html=True)
        
        for page_id, page_name in pages.items():
            is_current = st.session_state.current_page == page_id
            if st.button(
                page_name,
                key=f"nav_{page_id}",
                use_container_width=True,
                type="primary" if is_current else "secondary"
            ):
                st.session_state.current_page = page_id
                st.rerun()
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # System Status
        st.markdown(f'<div style="font-size: 0.7rem; color: {CHARCOAL}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">System Status</div>', unsafe_allow_html=True)
        
        client = get_api_client()
        health = client.health_check()
        
        if health.get("status") == "healthy":
            mode = health.get("mode", "api")
            mode_label = "Integrated" if mode == "integrated" else "API"
            st.markdown(f'<div class="status-healthy">Connected ({mode_label})</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-error">Offline</div>', unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Info section
        with st.expander("About", expanded=False):
            st.markdown(f"""
            <div style="font-size: 0.8rem; color: {CHARCOAL};">
                <p><strong>Agentic Sourcing Copilot</strong></p>
                <p>A human-in-the-loop decision support system for procurement sourcing.</p>
                <br>
                <p><strong>DTP Stages:</strong></p>
                <ul style="padding-left: 16px; margin: 4px 0;">
                    <li>DTP-01: Strategy</li>
                    <li>DTP-02: Planning</li>
                    <li>DTP-03: Sourcing</li>
                    <li>DTP-04: Negotiation</li>
                    <li>DTP-05: Contracting</li>
                    <li>DTP-06: Execution</li>
                </ul>
                <br>
                <p><strong>Governance:</strong></p>
                <ul style="padding-left: 16px; margin: 4px 0;">
                    <li>All decisions require approval</li>
                    <li>Full audit trail</li>
                    <li>Evidence-based recommendations</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # Main content
    if st.session_state.current_page == "dashboard":
        render_case_dashboard()
        
    elif st.session_state.current_page == "copilot":
        case_id = st.session_state.get("selected_case_id")
        
        if not case_id:
            st.markdown(f"""
            <div style="text-align: center; padding: 48px; color: {CHARCOAL};">
                <h3 style="color: {MIT_NAVY};">No Case Selected</h3>
                <p>Select a case from the Dashboard to open the Copilot.</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            case_input = st.text_input("Or enter Case ID directly:", key="direct_case_id")
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
