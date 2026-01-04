"""
Structured data ingestion pipeline for the data lake simulation.
Handles CSV/Excel files and stores in SQLite.
"""
import io
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4
from datetime import datetime
import pandas as pd

from backend.persistence.database import get_db_session
from backend.persistence.models import (
    SupplierPerformance, SpendMetric, SLAEvent, IngestionLog
)
from backend.ingestion.validators import SchemaValidator


class DataIngester:
    """
    Structured data ingestion pipeline.
    
    Flow:
    1. Accept CSV/Excel file + metadata
    2. Parse into DataFrame
    3. Validate schema
    4. Transform and normalize data
    5. Store in appropriate SQLite table
    6. Log ingestion event
    """
    
    # Map data types to models
    MODEL_MAP = {
        "Supplier Performance": SupplierPerformance,
        "Spend Data": SpendMetric,
        "SLA Events": SLAEvent
    }
    
    def preview(
        self,
        file_content: bytes,
        filename: str,
        data_type: str
    ) -> Dict[str, Any]:
        """
        Preview data before ingestion.
        
        Returns:
            Dict with columns, sample_rows, validation status
        """
        try:
            df = self._parse_file(file_content, filename)
            
            # Validate schema
            is_valid, messages = SchemaValidator.validate_schema(df, data_type)
            
            # Get sample rows
            sample_rows = df.head(5).to_dict(orient="records")
            
            return {
                "columns": list(df.columns),
                "sample_rows": sample_rows,
                "total_rows": len(df),
                "schema_valid": is_valid,
                "validation_errors": messages if not is_valid else [],
                "validation_warnings": messages if is_valid else []
            }
            
        except Exception as e:
            return {
                "columns": [],
                "sample_rows": [],
                "total_rows": 0,
                "schema_valid": False,
                "validation_errors": [str(e)],
                "validation_warnings": []
            }
    
    def ingest(
        self,
        file_content: bytes,
        filename: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest structured data into the data lake.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            metadata: Includes data_type, supplier_id, category_id, etc.
            
        Returns:
            Dict with ingestion_id, success, rows_ingested, message
        """
        data_type = metadata.get("data_type")
        if data_type not in self.MODEL_MAP:
            return {
                "ingestion_id": None,
                "filename": filename,
                "success": False,
                "rows_ingested": 0,
                "table_name": "",
                "message": f"Unknown data type: {data_type}",
                "validation_warnings": []
            }
        
        ingestion_id = str(uuid4())
        
        # Start ingestion log
        session = get_db_session()
        log = IngestionLog(
            ingestion_id=ingestion_id,
            source_type="structured_data",
            data_type=data_type,
            filename=filename,
            file_size_bytes=len(file_content),
            status="processing",
            supplier_id=metadata.get("supplier_id"),
            category_id=metadata.get("category_id")
        )
        session.add(log)
        session.commit()
        
        try:
            # 1. Parse file
            df = self._parse_file(file_content, filename)
            
            # 2. Validate schema
            is_valid, messages = SchemaValidator.validate_schema(df, data_type)
            if not is_valid:
                raise ValueError(f"Schema validation failed: {', '.join(messages)}")
            
            # 3. Normalize columns
            df = SchemaValidator.normalize_columns(df, data_type)
            
            # 4. Add metadata columns
            df["ingestion_id"] = ingestion_id
            
            # Apply metadata defaults if columns exist in model but not data
            if metadata.get("supplier_id") and "supplier_id" not in df.columns:
                df["supplier_id"] = metadata["supplier_id"]
            if metadata.get("category_id") and "category_id" not in df.columns:
                df["category_id"] = metadata["category_id"]
            
            # 5. Insert into database
            model_class = self.MODEL_MAP[data_type]
            rows_inserted = self._insert_records(df, model_class, session)
            
            # 6. Update log
            log.status = "completed"
            log.rows_processed = rows_inserted
            log.validation_warnings = str(messages) if messages else None
            log.completed_at = datetime.now().isoformat()
            session.commit()
            
            return {
                "ingestion_id": ingestion_id,
                "filename": filename,
                "success": True,
                "rows_ingested": rows_inserted,
                "table_name": model_class.__tablename__,
                "message": f"Successfully ingested {rows_inserted} rows into {model_class.__tablename__}",
                "validation_warnings": messages
            }
            
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = datetime.now().isoformat()
            session.commit()
            session.close()
            
            return {
                "ingestion_id": ingestion_id,
                "filename": filename,
                "success": False,
                "rows_ingested": 0,
                "table_name": "",
                "message": f"Ingestion failed: {str(e)}",
                "validation_warnings": []
            }
        finally:
            session.close()
    
    def _parse_file(self, content: bytes, filename: str) -> pd.DataFrame:
        """Parse CSV or Excel file into DataFrame."""
        file_ext = filename.lower().split(".")[-1]
        
        if file_ext == "csv":
            return pd.read_csv(io.BytesIO(content))
        elif file_ext in ["xls", "xlsx"]:
            return pd.read_excel(io.BytesIO(content))
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def _insert_records(
        self,
        df: pd.DataFrame,
        model_class,
        session
    ) -> int:
        """Insert DataFrame records into database."""
        # Get model field names
        model_fields = set(model_class.__fields__.keys())
        
        # Filter DataFrame to only include valid columns
        valid_cols = [c for c in df.columns if c in model_fields]
        df_filtered = df[valid_cols]
        
        # Convert to records and insert
        records = df_filtered.to_dict(orient="records")
        inserted = 0
        
        for record in records:
            # Clean up NaN values
            clean_record = {
                k: (None if pd.isna(v) else v)
                for k, v in record.items()
            }
            
            try:
                obj = model_class(**clean_record)
                session.add(obj)
                inserted += 1
            except Exception:
                # Skip invalid records
                continue
        
        session.commit()
        return inserted
    
    def get_ingestion_history(
        self,
        data_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent ingestion history."""
        from sqlmodel import select
        
        session = get_db_session()
        query = select(IngestionLog).where(
            IngestionLog.source_type == "structured_data"
        )
        
        if data_type:
            query = query.where(IngestionLog.data_type == data_type)
        
        query = query.order_by(IngestionLog.started_at.desc()).limit(limit)
        
        results = session.exec(query).all()
        session.close()
        
        return [
            {
                "ingestion_id": r.ingestion_id,
                "data_type": r.data_type,
                "filename": r.filename,
                "status": r.status,
                "rows_processed": r.rows_processed,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "error_message": r.error_message
            }
            for r in results
        ]


# Singleton instance
_data_ingester = None


def get_data_ingester() -> DataIngester:
    """Get or create data ingester singleton."""
    global _data_ingester
    if _data_ingester is None:
        _data_ingester = DataIngester()
    return _data_ingester





