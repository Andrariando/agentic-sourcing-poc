"""
Schema validators for structured data ingestion.
"""
from typing import List, Dict, Any, Tuple
import pandas as pd


class SchemaValidator:
    """Validates uploaded data against expected schemas."""
    
    # Expected columns for each data type
    SCHEMAS = {
        "Supplier Performance": {
            "required": ["supplier_id"],
            "optional": [
                "supplier_name", "category_id", "overall_score", "quality_score",
                "delivery_score", "cost_variance", "responsiveness_score",
                "trend", "risk_level", "period_start", "period_end", "measurement_date"
            ],
            "types": {
                "overall_score": "float",
                "quality_score": "float",
                "delivery_score": "float",
                "cost_variance": "float",
                "responsiveness_score": "float"
            }
        },
        "Spend Data": {
            "required": [],
            "optional": [
                "supplier_id", "category_id", "contract_id", "spend_amount",
                "currency", "budget_amount", "variance_amount", "variance_percent",
                "spend_type", "cost_center", "period", "period_start", "period_end"
            ],
            "types": {
                "spend_amount": "float",
                "budget_amount": "float",
                "variance_amount": "float",
                "variance_percent": "float"
            }
        },
        "SLA Events": {
            "required": ["supplier_id", "event_type", "sla_metric", "event_date"],
            "optional": [
                "contract_id", "category_id", "target_value", "actual_value",
                "variance", "severity", "financial_impact", "status", "resolution"
            ],
            "types": {
                "target_value": "float",
                "actual_value": "float",
                "variance": "float",
                "financial_impact": "float"
            }
        }
    }
    
    @classmethod
    def validate_schema(
        cls,
        df: pd.DataFrame,
        data_type: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate dataframe against expected schema.
        
        Returns:
            Tuple of (is_valid, list of errors/warnings)
        """
        errors = []
        
        if data_type not in cls.SCHEMAS:
            errors.append(f"Unknown data type: {data_type}")
            return False, errors
        
        schema = cls.SCHEMAS[data_type]
        columns = set(df.columns.str.lower())
        
        # Check required columns
        for req_col in schema["required"]:
            if req_col.lower() not in columns:
                errors.append(f"Missing required column: {req_col}")
        
        if errors:
            return False, errors
        
        # Check for empty required columns
        for req_col in schema["required"]:
            matching_col = [c for c in df.columns if c.lower() == req_col.lower()]
            if matching_col and df[matching_col[0]].isna().all():
                errors.append(f"Required column '{req_col}' is all empty")
        
        if errors:
            return False, errors
        
        # Warnings for type mismatches (not errors)
        warnings = []
        for col, expected_type in schema.get("types", {}).items():
            matching_col = [c for c in df.columns if c.lower() == col.lower()]
            if matching_col:
                col_name = matching_col[0]
                if expected_type == "float":
                    try:
                        pd.to_numeric(df[col_name], errors='raise')
                    except:
                        warnings.append(f"Column '{col}' may have non-numeric values")
        
        return True, warnings
    
    @classmethod
    def get_expected_columns(cls, data_type: str) -> List[str]:
        """Get list of expected columns for a data type."""
        if data_type not in cls.SCHEMAS:
            return []
        
        schema = cls.SCHEMAS[data_type]
        return schema["required"] + schema["optional"]
    
    @classmethod
    def normalize_columns(cls, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Normalize column names to lowercase and match expected schema."""
        # Create column mapping
        df_cols_lower = {c.lower(): c for c in df.columns}
        schema = cls.SCHEMAS.get(data_type, {})
        expected = schema.get("required", []) + schema.get("optional", [])
        
        # Rename columns to expected names
        rename_map = {}
        for expected_col in expected:
            if expected_col.lower() in df_cols_lower:
                original_col = df_cols_lower[expected_col.lower()]
                if original_col != expected_col:
                    rename_map[original_col] = expected_col
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        return df




