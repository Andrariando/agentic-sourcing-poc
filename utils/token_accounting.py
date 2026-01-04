"""
Token accounting and cost tracking with guardrails.
"""
from typing import Optional
from utils.schemas import BudgetState
import os


# Token pricing (as of 2024, approximate)
TIER_1_INPUT_COST_PER_1K = 0.15  # gpt-4o-mini input
TIER_1_OUTPUT_COST_PER_1K = 0.60  # gpt-4o-mini output
TIER_2_INPUT_COST_PER_1K = 5.00   # gpt-4o input
TIER_2_OUTPUT_COST_PER_1K = 15.00  # gpt-4o output

MAX_TOKENS_PER_CASE = 3000
TIER_1_MAX_OUTPUT_TOKENS = 500
TIER_2_MAX_OUTPUT_TOKENS = 900


def calculate_cost(tier: int, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD"""
    if tier == 1:
        input_cost = (input_tokens / 1000) * TIER_1_INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * TIER_1_OUTPUT_COST_PER_1K
    else:  # tier 2
        input_cost = (input_tokens / 1000) * TIER_2_INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * TIER_2_OUTPUT_COST_PER_1K
    
    return input_cost + output_cost


def update_budget_state(
    budget_state: BudgetState,
    tier: int,
    input_tokens: int,
    output_tokens: int
) -> tuple[BudgetState, bool]:
    """
    Update budget state and check if budget exceeded.
    Returns (updated_budget_state, budget_exceeded)
    """
    total_tokens = input_tokens + output_tokens
    cost = calculate_cost(tier, input_tokens, output_tokens)
    
    new_tokens_used = budget_state.tokens_used + total_tokens
    new_tokens_remaining = budget_state.tokens_remaining - total_tokens
    new_cost = budget_state.cost_usd + cost
    
    budget_exceeded = new_tokens_used > MAX_TOKENS_PER_CASE
    
    updated_budget = BudgetState(
        tokens_used=new_tokens_used,
        tokens_remaining=max(0, new_tokens_remaining),
        cost_usd=new_cost,
        model_calls=budget_state.model_calls + 1,
        tier_1_calls=budget_state.tier_1_calls + (1 if tier == 1 else 0),
        tier_2_calls=budget_state.tier_2_calls + (1 if tier == 2 else 0)
    )
    
    return updated_budget, budget_exceeded


def create_initial_budget_state() -> BudgetState:
    """Create initial budget state"""
    return BudgetState(
        tokens_used=0,
        tokens_remaining=MAX_TOKENS_PER_CASE,
        cost_usd=0.0,
        model_calls=0,
        tier_1_calls=0,
        tier_2_calls=0
    )










