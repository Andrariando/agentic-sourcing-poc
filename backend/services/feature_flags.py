"""
Feature flags for controlled rollout of new functionality.

These flags allow quick enable/disable of new features without code changes.
Default ON in dev, can be turned OFF via environment variables.
"""
import os


# Response envelope - structured responses with trace_id, agent_id, etc.
ENABLE_ENVELOPE_RESPONSE = os.getenv("ENABLE_ENVELOPE_RESPONSE", "true").lower() == "true"

# Artifact routing map - route artifacts to UI sections by type
ENABLE_ARTIFACT_ROUTING_MAP = os.getenv("ENABLE_ARTIFACT_ROUTING_MAP", "true").lower() == "true"

# Enhanced logging for routing decisions
ENABLE_ROUTING_LOGS = os.getenv("ENABLE_ROUTING_LOGS", "true").lower() == "true"

# Use ClarifierAgent for uncertain intents instead of defaulting
ENABLE_CLARIFIER_FALLBACK = os.getenv("ENABLE_CLARIFIER_FALLBACK", "true").lower() == "true"
