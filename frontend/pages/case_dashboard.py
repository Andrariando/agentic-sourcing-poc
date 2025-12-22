"""
Case Dashboard Page - Enterprise Grade

MIT Color System:
- MIT Navy (#003A8F): Structure and hierarchy
- MIT Cardinal Red (#A31F34): Actions and urgency only
"""
import streamlit as st
from typing import Optional

from frontend.api_client import get_api_client, APIError
from shared.constants import DTP_STAGES, DTP_STAGE_NAMES, CaseStatus


# MIT Color Constants
MIT_NAVY = "#003A8F"
MIT_CARDINAL = "#A31F34"
NEAR_BLACK = "#1F1F1F"
CHARCOAL = "#4A4A4A"
LIGHT_GRAY = "#D9D9D9"
WHITE = "#FFFFFF"


def inject_dashboard_styles():
    """Inject enterprise CSS for dashboard."""
    st.markdown(f"""
    <style>
        /* Page Header */
        .page-header {{
            color: {MIT_NAVY};
            font-size: 1.75rem;
            font-weight: 600;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid {MIT_NAVY};
        }}
        
        /* Case Card */
        .case-card {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 16px 20px;
            margin-bottom: 12px;
            transition: border-color 0.2s;
        }}
        .case-card:hover {{
            border-color: {MIT_NAVY};
        }}
        .case-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }}
        .case-title {{
            color: {NEAR_BLACK};
            font-size: 1rem;
            font-weight: 600;
            margin: 0;
        }}
        .case-id {{
            color: {CHARCOAL};
            font-size: 0.75rem;
            margin-top: 4px;
        }}
        .case-meta {{
            display: flex;
            gap: 20px;
            font-size: 0.8rem;
            color: {CHARCOAL};
        }}
        .case-meta-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        /* Stage Badge */
        .stage-badge {{
            background-color: {MIT_NAVY};
            color: {WHITE};
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        /* Status Indicator */
        .status-waiting {{
            color: {MIT_CARDINAL};
            font-weight: 600;
        }}
        .status-active {{
            color: #2E7D32;
        }}
        .status-open {{
            color: {MIT_NAVY};
        }}
        
        /* Signal Badge */
        .signal-badge {{
            background-color: #FFF3E0;
            color: #E65100;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 500;
        }}
        
        /* Filter Section */
        .filter-section {{
            background-color: #F8F9FA;
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 16px;
            margin-bottom: 24px;
        }}
        
        /* Stats Bar */
        .stats-bar {{
            display: flex;
            gap: 24px;
            margin-bottom: 24px;
        }}
        .stat-item {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 16px 24px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {MIT_NAVY};
        }}
        .stat-label {{
            font-size: 0.75rem;
            color: {CHARCOAL};
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 48px;
            color: {CHARCOAL};
        }}
        .empty-state h3 {{
            color: {MIT_NAVY};
            margin-bottom: 8px;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_case_dashboard():
    """Render the enterprise case dashboard."""
    
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        mode = health.get("mode", "unknown")
        error = health.get("error", "Unknown error")
        st.error(f"System not ready: {error}")
        st.info(f"Mode: {mode}")
        
        if "Import error" in error or "ModuleNotFound" in error:
            st.warning("Missing dependencies. Check that all backend modules are available.")
        elif mode == "integrated":
            st.warning("Integrated mode failed to initialize. Check the logs for details.")
        else:
            st.info("For local development: python -m uvicorn backend.main:app --reload")
        return
    
    # Inject styles
    inject_dashboard_styles()
    
    # Page Header
    st.markdown('<div class="page-header">Case Dashboard</div>', unsafe_allow_html=True)
    
    # Demo Data Section (collapsed by default)
    with st.expander("Demo Data Management", expanded=False):
        st.markdown("Load synthetic test data to explore the system.")
        col_seed1, col_seed2, col_spacer = st.columns([1, 1, 2])
        with col_seed1:
            if st.button("Load Demo Cases", help="Load sample cases at various DTP stages"):
                try:
                    from backend.seed_data import seed_all
                    seed_all()
                    st.success("Demo data loaded successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to seed data: {e}")
        with col_seed2:
            if st.button("Clear All Data", help="Remove all cases and data"):
                try:
                    from backend.persistence.database import get_db_session
                    from backend.persistence.models import CaseState, SupplierPerformance, SpendMetric, SLAEvent
                    session = get_db_session()
                    session.query(CaseState).delete()
                    session.query(SupplierPerformance).delete()
                    session.query(SpendMetric).delete()
                    session.query(SLAEvent).delete()
                    session.commit()
                    session.close()
                    st.success("All data cleared.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to clear data: {e}")
    
    # Filters
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All"] + [s.value for s in CaseStatus],
            key="dash_status",
            label_visibility="collapsed"
        )
        st.caption("Filter by Status")
    
    with col2:
        stage_filter = st.selectbox(
            "DTP Stage",
            ["All"] + DTP_STAGES,
            key="dash_stage",
            label_visibility="collapsed"
        )
        st.caption("Filter by DTP Stage")
    
    with col3:
        category_filter = st.text_input(
            "Category",
            key="dash_cat",
            placeholder="e.g. IT-SOFTWARE",
            label_visibility="collapsed"
        )
        st.caption("Filter by Category")
    
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("New Case", type="primary"):
            st.session_state.show_create_form = True
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create case form
    if st.session_state.get("show_create_form"):
        with st.container():
            st.markdown("### Create New Case")
            with st.form("create_case_form"):
                col_a, col_b = st.columns(2)
                with col_a:
                    new_category = st.text_input("Category ID", placeholder="IT-SOFTWARE")
                    new_name = st.text_input("Case Name", placeholder="Q1 License Renewal")
                with col_b:
                    new_contract = st.text_input("Contract ID (optional)")
                    new_supplier = st.text_input("Supplier ID (optional)")
                
                col_submit, col_cancel = st.columns([1, 1])
                with col_submit:
                    if st.form_submit_button("Create", type="primary"):
                        if not new_category:
                            st.error("Category ID is required")
                        else:
                            try:
                                result = client.create_case(
                                    category_id=new_category,
                                    name=new_name or None,
                                    contract_id=new_contract or None,
                                    supplier_id=new_supplier or None
                                )
                                st.success(f"Created: {result.case_id}")
                                st.session_state.show_create_form = False
                                st.rerun()
                            except APIError as e:
                                st.error(f"Failed: {e.message}")
                with col_cancel:
                    if st.form_submit_button("Cancel"):
                        st.session_state.show_create_form = False
                        st.rerun()
    
    # Load cases
    try:
        cases_response = client.list_cases(
            status=status_filter if status_filter != "All" else None,
            dtp_stage=stage_filter if stage_filter != "All" else None,
            category_id=category_filter or None
        )
        cases = cases_response.cases
    except APIError as e:
        st.error(f"Failed to load cases: {e.message}")
        return
    
    # Stats Bar
    total_cases = len(cases)
    waiting_cases = len([c for c in cases if c.status == "Waiting for Human Decision"])
    signal_cases = len([c for c in cases if c.trigger_source == "Signal"])
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    
    with col_s1:
        st.markdown(f"""
        <div class="stat-item">
            <div class="stat-value">{total_cases}</div>
            <div class="stat-label">Total Cases</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_s2:
        st.markdown(f"""
        <div class="stat-item">
            <div class="stat-value" style="color: {MIT_CARDINAL};">{waiting_cases}</div>
            <div class="stat-label">Awaiting Decision</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_s3:
        st.markdown(f"""
        <div class="stat-item">
            <div class="stat-value">{signal_cases}</div>
            <div class="stat-label">Signal Triggered</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_s4:
        active_cases = len([c for c in cases if c.status == "In Progress"])
        st.markdown(f"""
        <div class="stat-item">
            <div class="stat-value">{active_cases}</div>
            <div class="stat-label">In Progress</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Case list
    if not cases:
        st.markdown("""
        <div class="empty-state">
            <h3>No Cases Found</h3>
            <p>Create a new case or load demo data to get started.</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    st.markdown(f"**{len(cases)} cases**")
    
    for case in cases:
        # Determine status class
        status_class = "status-active"
        if case.status == "Waiting for Human Decision":
            status_class = "status-waiting"
        elif case.status == "Open":
            status_class = "status-open"
        
        # Get stage name
        stage_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
        
        # Create case card
        col_info, col_stage, col_action = st.columns([5, 2, 1])
        
        with col_info:
            signal_badge = ""
            if case.trigger_source == "Signal":
                signal_badge = '<span class="signal-badge">SIGNAL</span>'
            
            st.markdown(f"""
            <div class="case-card">
                <div class="case-card-header">
                    <div>
                        <div class="case-title">{case.name} {signal_badge}</div>
                        <div class="case-id">{case.case_id}</div>
                    </div>
                </div>
                <div class="case-meta">
                    <span class="case-meta-item">Category: {case.category_id}</span>
                    <span class="case-meta-item">Supplier: {case.supplier_id or 'N/A'}</span>
                    <span class="case-meta-item {status_class}">{case.status}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_stage:
            st.markdown(f"""
            <div style="padding-top: 20px;">
                <span class="stage-badge">{case.dtp_stage}</span>
                <div style="font-size: 0.75rem; color: {CHARCOAL}; margin-top: 4px;">{stage_name}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_action:
            st.markdown("<div style='padding-top: 16px;'></div>", unsafe_allow_html=True)
            if st.button("Open", key=f"open_{case.case_id}"):
                st.session_state.selected_case_id = case.case_id
                st.session_state.current_page = "copilot"
                st.rerun()


def render_case_detail(case_id: str):
    """Render case detail view - redirects to copilot."""
    st.session_state.selected_case_id = case_id
    st.session_state.current_page = "copilot"
    st.rerun()
