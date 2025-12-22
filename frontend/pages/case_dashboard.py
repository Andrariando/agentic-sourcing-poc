"""
Case Dashboard Page.

Displays list of cases with filtering and case details.
"""
import streamlit as st
from typing import Optional

from frontend.api_client import get_api_client, APIError
from shared.constants import DTP_STAGES, DTP_STAGE_NAMES, CaseStatus


def render_case_dashboard():
    """Render the case dashboard page."""
    st.title("📋 Case Dashboard")
    
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        st.error(f"⚠️ Backend is not available: {health.get('error', 'Unknown error')}")
        st.info("Please start the backend server: `python -m uvicorn backend.main:app --reload`")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All"] + [s.value for s in CaseStatus],
            key="dash_status"
        )
    
    with col2:
        stage_filter = st.selectbox(
            "DTP Stage",
            ["All"] + DTP_STAGES,
            key="dash_stage"
        )
    
    with col3:
        category_filter = st.text_input("Category ID", key="dash_cat")
    
    # Create new case button
    if st.button("➕ Create New Case", key="create_case"):
        st.session_state.show_create_form = True
    
    # Create case form
    if st.session_state.get("show_create_form"):
        with st.expander("Create New Case", expanded=True):
            with st.form("create_case_form"):
                new_category = st.text_input("Category ID *", placeholder="IT-SOFTWARE")
                new_name = st.text_input("Case Name", placeholder="Q1 Software License Renewal")
                new_contract = st.text_input("Contract ID (optional)")
                new_supplier = st.text_input("Supplier ID (optional)")
                
                if st.form_submit_button("Create Case"):
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
                            st.success(f"✅ Created case: {result.case_id}")
                            st.session_state.show_create_form = False
                            st.rerun()
                        except APIError as e:
                            st.error(f"Failed to create case: {e.message}")
    
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
    
    st.markdown(f"**{len(cases)} cases found**")
    
    # Case list
    if not cases:
        st.info("No cases found. Create a new case to get started.")
        return
    
    for case in cases:
        with st.container():
            # Case card
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"### {case.name}")
                st.markdown(f"**{case.case_id}** | Category: `{case.category_id}`")
                if case.supplier_id:
                    st.markdown(f"Supplier: `{case.supplier_id}`")
            
            with col2:
                # DTP stage badge
                stage_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
                st.markdown(f"**Stage:** {case.dtp_stage} - {stage_name}")
                
                # Status badge
                status_color = {
                    "Open": "🔵",
                    "In Progress": "🟢",
                    "Waiting for Human Decision": "🟠",
                    "Completed": "✅",
                    "Rejected": "🔴"
                }
                st.markdown(f"**Status:** {status_color.get(case.status, '⚪')} {case.status}")
            
            with col3:
                if st.button("Open →", key=f"open_{case.case_id}"):
                    st.session_state.selected_case_id = case.case_id
                    st.session_state.current_page = "copilot"
                    st.rerun()
            
            st.markdown("---")


def render_case_detail(case_id: str):
    """Render case detail view."""
    client = get_api_client()
    
    try:
        case = client.get_case(case_id)
    except APIError as e:
        st.error(f"Failed to load case: {e.message}")
        return
    
    # Header
    st.title(f"📁 {case.name}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Case ID:** `{case.case_id}`")
        st.markdown(f"**Category:** `{case.category_id}`")
        if case.supplier_id:
            st.markdown(f"**Supplier:** `{case.supplier_id}`")
        if case.contract_id:
            st.markdown(f"**Contract:** `{case.contract_id}`")
    
    with col2:
        stage_name = DTP_STAGE_NAMES.get(case.dtp_stage, case.dtp_stage)
        st.markdown(f"**DTP Stage:** {case.dtp_stage} - {stage_name}")
        st.markdown(f"**Status:** {case.status}")
        st.markdown(f"**Created:** {case.created_date}")
        st.markdown(f"**Updated:** {case.updated_date}")
    
    # Summary
    st.markdown("### Summary")
    st.markdown(case.summary.summary_text)
    
    if case.summary.key_findings:
        st.markdown("**Key Findings:**")
        for finding in case.summary.key_findings:
            st.markdown(f"- {finding}")
    
    if case.summary.recommended_action:
        st.info(f"**Recommended Action:** {case.summary.recommended_action}")
    
    # Latest agent output
    if case.latest_agent_output:
        st.markdown(f"### Latest Output from {case.latest_agent_name}")
        st.json(case.latest_agent_output)
    
    # Activity log
    if case.activity_log:
        st.markdown("### Activity Log")
        for log in reversed(case.activity_log[-10:]):
            st.markdown(f"- **{log.get('timestamp', '')}** | {log.get('action', '')} by {log.get('agent_name', '')}")

