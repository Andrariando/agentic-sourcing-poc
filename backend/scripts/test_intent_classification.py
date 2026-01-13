#!/usr/bin/env python3
"""
Test script for intent classification improvements.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.supervisor.router import IntentRouter
from shared.constants import UserIntent, UserGoal

# Test cases
test_cases = [
    ("Scan signals", {"dtp_stage": "DTP-01", "has_existing_output": False}, "Should be DECIDE/CREATE"),
    ("What signals do we have?", {"dtp_stage": "DTP-01", "has_existing_output": True}, "Should be EXPLAIN/UNDERSTAND"),
    ("Score suppliers", {"dtp_stage": "DTP-02", "has_existing_output": False}, "Should be DECIDE/CREATE"),
    ("Explain the scoring methodology", {"dtp_stage": "DTP-02", "has_existing_output": True}, "Should be EXPLAIN/UNDERSTAND"),
    ("Can you draft an RFx?", {"dtp_stage": "DTP-03", "has_existing_output": False}, "Should be DECIDE/CREATE"),
    ("Check supplier eligibility", {"dtp_stage": "DTP-02", "has_existing_output": False}, "Should be DECIDE/CHECK"),
    ("What is the current status?", {"dtp_stage": "DTP-01", "has_existing_output": False}, "Should be STATUS/TRACK"),
]

print("\n" + "="*70)
print("INTENT CLASSIFICATION TEST")
print("="*70 + "\n")

for message, context, expected in test_cases:
    single = IntentRouter.classify_intent(message, context)
    two_level = IntentRouter.classify_intent_two_level(message, context)
    
    print(f"Message: '{message}'")
    print(f"  Context: {context}")
    print(f"  Single-level: {single.value}")
    print(f"  Two-level: {two_level.user_goal} + {two_level.work_type} (conf: {two_level.confidence:.2f})")
    print(f"  Expected: {expected}")
    print()

print("="*70)
print("Test complete!")
print("="*70)



