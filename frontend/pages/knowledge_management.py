"""
Knowledge & Data Management Page - Enterprise Grade

MIT Color System:
- MIT Navy (#003A8F): Structure and hierarchy
- MIT Cardinal Red (#A31F34): Actions and urgency only
"""
import streamlit as st
from typing import Optional
import json

from frontend.api_client import get_api_client, APIError
from shared.constants import DocumentType, DataType, DTP_STAGES


# MIT Color Constants
MIT_NAVY = "#003A8F"
MIT_CARDINAL = "#A31F34"
NEAR_BLACK = "#1F1F1F"
CHARCOAL = "#4A4A4A"
LIGHT_GRAY = "#D9D9D9"
WHITE = "#FFFFFF"


def inject_knowledge_styles():
    """Inject enterprise CSS for knowledge management."""
    st.markdown(f"""
    <style>
        .page-header {{
            color: {MIT_NAVY};
            font-size: 1.75rem;
            font-weight: 600;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid {MIT_NAVY};
        }}
        
        .section-header {{
            color: {MIT_NAVY};
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .upload-section {{
            background-color: {WHITE};
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        
        .info-text {{
            color: {CHARCOAL};
            font-size: 0.875rem;
            margin-bottom: 16px;
        }}
        
        .schema-box {{
            background-color: #F8F9FA;
            border: 1px solid {LIGHT_GRAY};
            border-radius: 4px;
            padding: 16px;
            font-size: 0.8rem;
            color: {NEAR_BLACK};
        }}
        
        .document-list-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid {LIGHT_GRAY};
            font-size: 0.875rem;
        }}
        .document-list-item:last-child {{
            border-bottom: none;
        }}
        
        .ingestion-success {{
            background-color: #E8F5E9;
            border: 1px solid #A5D6A7;
            border-radius: 4px;
            padding: 16px;
            margin-top: 16px;
        }}
        
        .ingestion-error {{
            background-color: #FFEBEE;
            border: 1px solid #EF9A9A;
            border-radius: 4px;
            padding: 16px;
            margin-top: 16px;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_knowledge_management():
    """
    Render the knowledge management page.
    
    Supports:
    - Document upload (PDF, DOCX, TXT) for RAG
    - Structured data upload (CSV, Excel) for data lake
    """
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        st.error("System not available")
        return
    
    # Inject styles
    inject_knowledge_styles()
    
    # Page Header
    st.markdown('<div class="page-header">Knowledge Management</div>', unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["Document Upload", "Data Upload", "Ingested Content"])
    
    # ==================== DOCUMENT UPLOAD ====================
    with tab1:
        st.markdown('<div class="section-header">Upload Documents for RAG</div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-text">
        Upload contracts, performance reports, policies, and other documents. 
        Documents are processed and made available for agent retrieval.
        <br><br>
        <strong>Supported formats:</strong> PDF, DOCX, TXT
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("document_upload_form"):
            # File upload
            uploaded_file = st.file_uploader(
                "Select document",
                type=["pdf", "docx", "txt"],
                key="doc_upload",
                label_visibility="collapsed"
            )
            
            # Metadata
            col1, col2 = st.columns(2)
            
            with col1:
                doc_type = st.selectbox(
                    "Document Type",
                    [dt.value for dt in DocumentType],
                    key="doc_type"
                )
                
                supplier_id = st.text_input(
                    "Supplier ID (optional)",
                    key="doc_supplier",
                    placeholder="e.g. SUP-001"
                )
                
                category_id = st.text_input(
                    "Category ID (optional)",
                    key="doc_category",
                    placeholder="e.g. IT-SOFTWARE"
                )
            
            with col2:
                region = st.text_input(
                    "Region (optional)",
                    key="doc_region",
                    placeholder="e.g. North America"
                )
                
                dtp_relevance = st.multiselect(
                    "Relevant DTP Stages",
                    DTP_STAGES,
                    key="doc_dtp"
                )
                
                case_id = st.text_input(
                    "Link to Case ID (optional)",
                    key="doc_case",
                    placeholder="e.g. CASE-001"
                )
            
            description = st.text_area(
                "Description (optional)",
                key="doc_desc",
                height=80
            )
            
            submitted = st.form_submit_button("Upload Document", type="primary")
            
            if submitted:
                if not uploaded_file:
                    st.error("Please select a file to upload")
                else:
                    try:
                        with st.spinner("Processing document..."):
                            result = client.ingest_document(
                                file_content=uploaded_file.read(),
                                filename=uploaded_file.name,
                                document_type=doc_type,
                                supplier_id=supplier_id or None,
                                category_id=category_id or None,
                                region=region or None,
                                dtp_relevance=dtp_relevance or None,
                                case_id=case_id or None,
                                description=description or None
                            )
                        
                        if result.success:
                            st.markdown(f"""
                            <div class="ingestion-success">
                                <strong>Document uploaded successfully</strong><br>
                                Document ID: {result.document_id}<br>
                                Chunks created: {result.chunks_created}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="ingestion-error">
                                <strong>Upload failed</strong><br>
                                {result.message}
                            </div>
                            """, unsafe_allow_html=True)
                            
                    except APIError as e:
                        st.error(f"Upload failed: {e.message}")
    
    # ==================== DATA UPLOAD ====================
    with tab2:
        st.markdown('<div class="section-header">Upload Structured Data</div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-text">
        Upload supplier performance data, spend data, or SLA events.
        Data is stored for agent queries and analysis.
        <br><br>
        <strong>Supported formats:</strong> CSV, Excel (XLS, XLSX)
        </div>
        """, unsafe_allow_html=True)
        
        # Data type selection
        data_type = st.selectbox(
            "Data Type",
            [dt.value for dt in DataType],
            key="data_type_select"
        )
        
        # Show expected schema
        with st.expander("Expected Schema", expanded=False):
            if data_type == "Supplier Performance":
                st.markdown("""
                <div class="schema-box">
                <strong>Required columns:</strong> supplier_id<br><br>
                <strong>Optional columns:</strong><br>
                supplier_name, category_id, overall_score, quality_score,
                delivery_score, cost_variance, responsiveness_score,
                trend, risk_level, period_start, period_end, measurement_date
                </div>
                """, unsafe_allow_html=True)
            elif data_type == "Spend Data":
                st.markdown("""
                <div class="schema-box">
                <strong>Optional columns:</strong><br>
                supplier_id, category_id, contract_id, spend_amount,
                currency, budget_amount, variance_amount, variance_percent,
                spend_type, cost_center, period, period_start, period_end
                </div>
                """, unsafe_allow_html=True)
            elif data_type == "SLA Events":
                st.markdown("""
                <div class="schema-box">
                <strong>Required columns:</strong> supplier_id, event_type, sla_metric, event_date<br><br>
                <strong>Optional columns:</strong><br>
                contract_id, category_id, target_value, actual_value, variance,
                severity, financial_impact, status, resolution
                </div>
                """, unsafe_allow_html=True)
        
        # File upload
        data_file = st.file_uploader(
            "Select data file",
            type=["csv", "xls", "xlsx"],
            key="data_upload",
            label_visibility="collapsed"
        )
        
        if data_file:
            # Preview button
            if st.button("Preview Data"):
                try:
                    preview = client.preview_data(
                        file_content=data_file.read(),
                        filename=data_file.name,
                        data_type=data_type
                    )
                    
                    # Reset file position
                    data_file.seek(0)
                    
                    st.markdown(f"**Total rows:** {preview.total_rows}")
                    st.markdown(f"**Columns:** {', '.join(preview.columns)}")
                    
                    if preview.schema_valid:
                        st.success("Schema validation passed")
                    else:
                        st.error("Schema validation failed")
                        for err in preview.validation_errors:
                            st.markdown(f"- {err}")
                    
                    if preview.sample_rows:
                        st.markdown("**Sample rows:**")
                        st.dataframe(preview.sample_rows)
                        
                except APIError as e:
                    st.error(f"Preview failed: {e.message}")
        
        # Upload form
        with st.form("data_upload_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                data_supplier = st.text_input(
                    "Default Supplier ID (optional)",
                    key="data_supplier"
                )
                data_category = st.text_input(
                    "Default Category ID (optional)",
                    key="data_category"
                )
            
            with col2:
                time_period = st.text_input(
                    "Time Period (optional)",
                    placeholder="e.g. 2024-Q1",
                    key="data_period"
                )
                data_desc = st.text_input(
                    "Description (optional)",
                    key="data_desc"
                )
            
            data_submitted = st.form_submit_button("Upload Data", type="primary")
            
            if data_submitted:
                if not data_file:
                    st.error("Please select a file to upload")
                else:
                    try:
                        with st.spinner("Processing data..."):
                            result = client.ingest_data(
                                file_content=data_file.read(),
                                filename=data_file.name,
                                data_type=data_type,
                                supplier_id=data_supplier or None,
                                category_id=data_category or None,
                                time_period=time_period or None,
                                description=data_desc or None
                            )
                        
                        if result.success:
                            st.markdown(f"""
                            <div class="ingestion-success">
                                <strong>Data uploaded successfully</strong><br>
                                Ingestion ID: {result.ingestion_id}<br>
                                Table: {result.table_name}<br>
                                Rows ingested: {result.rows_ingested}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if result.validation_warnings:
                                st.warning("Warnings: " + ", ".join(result.validation_warnings))
                        else:
                            st.error(f"Failed: {result.message}")
                            
                    except APIError as e:
                        st.error(f"Upload failed: {e.message}")
    
    # ==================== INGESTED CONTENT ====================
    with tab3:
        st.markdown('<div class="section-header">Ingested Content</div>', unsafe_allow_html=True)
        
        # Documents
        st.markdown("**Documents**")
        
        try:
            docs_response = client.list_documents()
            
            if docs_response.documents:
                for doc in docs_response.documents:
                    col1, col2, col3 = st.columns([4, 2, 1])
                    
                    with col1:
                        st.markdown(f"""
                        <div style="font-weight: 500;">{doc.filename}</div>
                        <div style="font-size: 0.75rem; color: {CHARCOAL};">
                            Type: {doc.document_type} | Chunks: {doc.chunk_count}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        meta_parts = []
                        if doc.supplier_id:
                            meta_parts.append(f"Supplier: {doc.supplier_id}")
                        if doc.category_id:
                            meta_parts.append(f"Category: {doc.category_id}")
                        st.markdown(f'<div style="font-size: 0.8rem; color: {CHARCOAL};">{" | ".join(meta_parts) if meta_parts else "-"}</div>', unsafe_allow_html=True)
                    
                    with col3:
                        if st.button("Delete", key=f"del_{doc.document_id}"):
                            try:
                                client.delete_document(doc.document_id)
                                st.success("Deleted")
                                st.rerun()
                            except APIError as e:
                                st.error(f"Delete failed: {e.message}")
                    
                    st.markdown(f'<hr style="margin: 8px 0; border-color: {LIGHT_GRAY};">', unsafe_allow_html=True)
            else:
                st.info("No documents ingested yet.")
                
        except APIError as e:
            st.error(f"Failed to load documents: {e.message}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Ingestion history
        st.markdown("**Data Ingestion History**")
        
        try:
            history = client.get_ingestion_history(limit=20)
            
            if history:
                for item in history:
                    status_icon = "check" if item["status"] == "completed" else "x"
                    status_color = "#2E7D32" if item["status"] == "completed" else MIT_CARDINAL
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {LIGHT_GRAY}; font-size: 0.875rem;">
                        <span>
                            <span style="color: {status_color}; font-weight: bold;">{'OK' if item['status'] == 'completed' else 'FAILED'}</span>
                            {item['filename']}
                        </span>
                        <span style="color: {CHARCOAL};">
                            {item['data_type']} | {item['rows_processed']} rows | {item['started_at'][:16]}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No data ingestion history yet.")
                
        except APIError as e:
            st.error(f"Failed to load history: {e.message}")
