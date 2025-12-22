"""
Knowledge & Data Management Page.

Upload documents and structured data for RAG and analytics.
"""
import streamlit as st
from typing import Optional
import json

from frontend.api_client import get_api_client, APIError
from shared.constants import DocumentType, DataType, DTP_STAGES


def render_knowledge_management():
    """
    Render the knowledge management page.
    
    Supports:
    - Document upload (PDF, DOCX, TXT) for RAG
    - Structured data upload (CSV, Excel) for data lake
    """
    st.title("📚 Knowledge & Data Management")
    
    client = get_api_client()
    
    # Check backend health
    health = client.health_check()
    if health.get("status") != "healthy":
        st.error("⚠️ Backend is not available")
        return
    
    # Tabs for different upload types
    tab1, tab2, tab3 = st.tabs(["📄 Document Upload", "📊 Data Upload", "📋 Ingested Content"])
    
    # ==================== DOCUMENT UPLOAD ====================
    with tab1:
        st.markdown("""
        ### Upload Documents for RAG
        
        Upload contracts, performance reports, policies, and other documents.
        These will be processed and made available for agent retrieval.
        
        **Supported formats:** PDF, DOCX, TXT
        """)
        
        with st.form("document_upload_form"):
            # File upload
            uploaded_file = st.file_uploader(
                "Select document",
                type=["pdf", "docx", "txt"],
                key="doc_upload"
            )
            
            # Metadata
            col1, col2 = st.columns(2)
            
            with col1:
                doc_type = st.selectbox(
                    "Document Type *",
                    [dt.value for dt in DocumentType],
                    key="doc_type"
                )
                
                supplier_id = st.text_input(
                    "Supplier ID (optional)",
                    key="doc_supplier"
                )
                
                category_id = st.text_input(
                    "Category ID (optional)",
                    key="doc_category"
                )
            
            with col2:
                region = st.text_input(
                    "Region (optional)",
                    key="doc_region"
                )
                
                dtp_relevance = st.multiselect(
                    "Relevant DTP Stages",
                    DTP_STAGES,
                    key="doc_dtp"
                )
                
                case_id = st.text_input(
                    "Link to Case ID (optional)",
                    key="doc_case"
                )
            
            description = st.text_area(
                "Description (optional)",
                key="doc_desc"
            )
            
            submitted = st.form_submit_button("📤 Upload Document")
            
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
                            st.success(f"""
                            ✅ **Document uploaded successfully!**
                            
                            - Document ID: `{result.document_id}`
                            - Chunks created: {result.chunks_created}
                            """)
                        else:
                            st.error(f"Failed: {result.message}")
                            
                    except APIError as e:
                        st.error(f"Upload failed: {e.message}")
    
    # ==================== DATA UPLOAD ====================
    with tab2:
        st.markdown("""
        ### Upload Structured Data
        
        Upload supplier performance data, spend data, or SLA events.
        This data will be stored in the data lake for agent queries.
        
        **Supported formats:** CSV, Excel (XLS, XLSX)
        """)
        
        # Data type selection
        data_type = st.selectbox(
            "Data Type *",
            [dt.value for dt in DataType],
            key="data_type_select"
        )
        
        # Show expected schema
        with st.expander("📋 Expected Schema"):
            if data_type == "Supplier Performance":
                st.markdown("""
                **Required columns:**
                - `supplier_id`
                
                **Optional columns:**
                - `supplier_name`, `category_id`
                - `overall_score`, `quality_score`, `delivery_score`
                - `cost_variance`, `responsiveness_score`
                - `trend`, `risk_level`
                - `period_start`, `period_end`, `measurement_date`
                """)
            elif data_type == "Spend Data":
                st.markdown("""
                **Optional columns:**
                - `supplier_id`, `category_id`, `contract_id`
                - `spend_amount`, `currency`, `budget_amount`
                - `variance_amount`, `variance_percent`
                - `spend_type`, `cost_center`
                - `period`, `period_start`, `period_end`
                """)
            elif data_type == "SLA Events":
                st.markdown("""
                **Required columns:**
                - `supplier_id`, `event_type`, `sla_metric`, `event_date`
                
                **Optional columns:**
                - `contract_id`, `category_id`
                - `target_value`, `actual_value`, `variance`
                - `severity`, `financial_impact`
                - `status`, `resolution`
                """)
        
        # File upload
        data_file = st.file_uploader(
            "Select data file",
            type=["csv", "xls", "xlsx"],
            key="data_upload"
        )
        
        if data_file:
            # Preview button
            if st.button("👁️ Preview Data"):
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
                        st.success("✅ Schema validation passed")
                    else:
                        st.error("❌ Schema validation failed")
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
                    placeholder="e.g., 2024-Q1",
                    key="data_period"
                )
                data_desc = st.text_input(
                    "Description (optional)",
                    key="data_desc"
                )
            
            data_submitted = st.form_submit_button("📤 Upload Data")
            
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
                            st.success(f"""
                            ✅ **Data uploaded successfully!**
                            
                            - Ingestion ID: `{result.ingestion_id}`
                            - Table: `{result.table_name}`
                            - Rows ingested: {result.rows_ingested}
                            """)
                            
                            if result.validation_warnings:
                                st.warning("⚠️ Warnings:")
                                for w in result.validation_warnings:
                                    st.markdown(f"- {w}")
                        else:
                            st.error(f"Failed: {result.message}")
                            
                    except APIError as e:
                        st.error(f"Upload failed: {e.message}")
    
    # ==================== INGESTED CONTENT ====================
    with tab3:
        st.markdown("### Ingested Content")
        
        # Documents
        st.markdown("#### 📄 Documents")
        
        try:
            docs_response = client.list_documents()
            
            if docs_response.documents:
                for doc in docs_response.documents:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.markdown(f"**{doc.filename}**")
                            st.markdown(f"Type: {doc.document_type} | Chunks: {doc.chunk_count}")
                        
                        with col2:
                            if doc.supplier_id:
                                st.markdown(f"Supplier: `{doc.supplier_id}`")
                            if doc.category_id:
                                st.markdown(f"Category: `{doc.category_id}`")
                        
                        with col3:
                            if st.button("🗑️", key=f"del_{doc.document_id}"):
                                try:
                                    client.delete_document(doc.document_id)
                                    st.success("Deleted")
                                    st.rerun()
                                except APIError as e:
                                    st.error(f"Delete failed: {e.message}")
                        
                        st.markdown("---")
            else:
                st.info("No documents ingested yet.")
                
        except APIError as e:
            st.error(f"Failed to load documents: {e.message}")
        
        # Ingestion history
        st.markdown("#### 📊 Data Ingestion History")
        
        try:
            history = client.get_ingestion_history(limit=20)
            
            if history:
                for item in history:
                    status_icon = "✅" if item["status"] == "completed" else "❌"
                    st.markdown(
                        f"{status_icon} **{item['filename']}** | "
                        f"Type: {item['data_type']} | "
                        f"Rows: {item['rows_processed']} | "
                        f"{item['started_at'][:16]}"
                    )
            else:
                st.info("No data ingestion history yet.")
                
        except APIError as e:
            st.error(f"Failed to load history: {e.message}")

