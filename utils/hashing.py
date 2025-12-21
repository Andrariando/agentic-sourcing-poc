"""
SHA-256 input hashing for cache key generation.
"""
import hashlib
import json
from typing import Dict, Any


def compute_input_hash(case_summary: Dict[str, Any], question_text: str = "", additional_inputs: Dict[str, Any] = None) -> str:
    """
    Compute SHA-256 hash over:
    - serialized case_summary JSON
    - question text
    - additional inputs
    """
    hash_input = {
        "case_summary": case_summary,
        "question_text": question_text,
        "additional_inputs": additional_inputs or {}
    }
    
    # Serialize to JSON with sorted keys for consistency
    json_str = json.dumps(hash_input, sort_keys=True, ensure_ascii=False)
    
    # Compute SHA-256
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def generate_cache_key(case_id: str, agent_name: str, normalized_intent: str, input_hash: str, schema_version: str = "1.0") -> str:
    """Generate cache key: (case_id, agent_name, normalized_user_intent, input_hash, schema_version)"""
    components = [case_id, agent_name, normalized_intent, input_hash, schema_version]
    return "|".join(components)






