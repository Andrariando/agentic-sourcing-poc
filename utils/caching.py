"""
Caching utilities with SHA-256 input hashing.
"""
from typing import Optional, Dict, Any
from utils.hashing import compute_input_hash, generate_cache_key
from utils.schemas import CaseSummary, CacheMeta


class Cache:
    """Simple in-memory cache for agent outputs"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    def get(self, cache_key: str) -> Optional[Any]:
        """Get cached value"""
        return self._cache.get(cache_key)
    
    def set(self, cache_key: str, value: Any):
        """Set cached value"""
        self._cache[cache_key] = value
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()


# Global cache instance
cache = Cache()


def get_cache_meta(
    case_id: str,
    agent_name: str,
    normalized_intent: str,
    case_summary: CaseSummary,
    question_text: str = "",
    additional_inputs: Dict[str, Any] = None
) -> tuple[CacheMeta, Optional[Any]]:
    """
    Check cache and return CacheMeta with hit/miss status.
    Returns (CacheMeta, cached_value or None)
    """
    # Compute input hash
    case_summary_dict = case_summary.model_dump() if hasattr(case_summary, "model_dump") else dict(case_summary)
    input_hash = compute_input_hash(case_summary_dict, question_text, additional_inputs)
    
    # Generate cache key
    cache_key = generate_cache_key(case_id, agent_name, normalized_intent, input_hash)
    
    # Check cache
    cached_value = cache.get(cache_key)
    cache_hit = cached_value is not None
    
    cache_meta = CacheMeta(
        cache_hit=cache_hit,
        cache_key=cache_key,
        input_hash=input_hash,
        schema_version="1.0"
    )
    
    return cache_meta, cached_value


def set_cache(cache_key: str, value: Any):
    """Store value in cache"""
    cache.set(cache_key, value)









