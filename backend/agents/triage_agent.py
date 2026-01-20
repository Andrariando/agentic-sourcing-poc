"""
Triage Agent (DTP-01 Gatekeeper)

Performs the initial classification and coverage check for incoming sourcing requests.
This is the FIRST step in DTP-01 before Strategy is determined.

Logic:
1. Classify request type (Demand-Based, Renewal, Ad-Hoc, Fast-Pass)
2. Check for existing coverage (matching contracts/suppliers)
3. If covered -> REDIRECT to buying channel
4. If not covered -> PROCEED to Strategy Agent
5. Load applicable Category Strategy Card

This is a deterministic agent - NO LLM calls.
"""
from typing import Dict, Any, Optional, List, Tuple
import json
from pathlib import Path

from utils.schemas import (
    TriageResult, RequestType, TriageStatus, CategoryStrategyCard
)

# Data paths
DATA_DIR = Path(__file__).parent.parent / "data"


def load_contracts() -> List[Dict[str, Any]]:
    """Load contracts data"""
    contracts_path = DATA_DIR / "contracts.json"
    if contracts_path.exists():
        return json.loads(contracts_path.read_text())
    return []


def load_category_strategies() -> List[Dict[str, Any]]:
    """Load category strategy cards"""
    strategies_path = DATA_DIR / "category_strategies.json"
    if strategies_path.exists():
        return json.loads(strategies_path.read_text())
    return []


def get_global_defaults() -> Dict[str, Any]:
    """Get global strategy defaults from GLOBAL card"""
    strategies = load_category_strategies()
    for strategy in strategies:
        if strategy.get("category_id") == "GLOBAL":
            return strategy
    # Fallback defaults
    return {
        "sourcing_rules": {"spend_threshold_3_bids_usd": 1500000, "min_suppliers_above_threshold": 3},
        "defaults": {"payment_terms": "Net 90"}
    }


class TriageAgent:
    """
    DTP-01 Triage Agent - Gatekeeper for sourcing requests.
    
    This agent determines:
    1. Is this request covered by an existing contract? (Coverage Check)
    2. What type of request is this? (Classification)
    3. Should we proceed to sourcing or redirect to catalog?
    """
    
    def __init__(self):
        self.contracts = load_contracts()
        self.category_strategies = load_category_strategies()
        self.global_defaults = get_global_defaults()
    
    def classify_request(self, user_intent: str, trigger_source: str = "User") -> RequestType:
        """
        Classify the request type based on intent and trigger.
        
        Returns: RequestType enum value
        """
        intent_lower = user_intent.lower()
        
        # Renewal keywords
        if trigger_source == "Signal" or any(kw in intent_lower for kw in ["renew", "renewal", "expir", "contract ending"]):
            return RequestType.RENEWAL
        
        # Fast-Pass keywords (pre-approved, quick buys)
        if any(kw in intent_lower for kw in ["fast-pass", "quick buy", "pre-approved", "catalog order"]):
            return RequestType.FAST_PASS
        
        # Ad-hoc keywords (off-system, urgent)
        if any(kw in intent_lower for kw in ["urgent", "ad-hoc", "one-time", "emergency", "off-system"]):
            return RequestType.AD_HOC
        
        # Default to Demand-Based
        return RequestType.DEMAND_BASED
    
    def check_coverage(self, user_intent: str, category_id: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if the request is covered by an existing contract.
        
        Returns: (is_covered, matched_contract or None)
        """
        intent_lower = user_intent.lower()
        
        for contract in self.contracts:
            # Skip inactive contracts
            if contract.get("status") != "Active":
                continue
            
            # Check category match first (if provided)
            if category_id and contract.get("category_id") != category_id:
                continue
            
            # Check keyword coverage
            coverage_keywords = contract.get("coverage_keywords", [])
            for keyword in coverage_keywords:
                if keyword.lower() in intent_lower:
                    return True, contract
        
        return False, None
    
    def get_category_strategy_card(self, category_id: str) -> Optional[CategoryStrategyCard]:
        """
        Load the category strategy card for the given category.
        
        Returns: CategoryStrategyCard or None
        """
        for strategy in self.category_strategies:
            if strategy.get("category_id") == category_id:
                return CategoryStrategyCard(
                    category_id=strategy.get("category_id"),
                    category_name=strategy.get("category_name", "Unknown"),
                    sourcing_rules=strategy.get("sourcing_rules", {}),
                    defaults=strategy.get("defaults", {}),
                    evaluation_criteria=strategy.get("sourcing_rules", {}).get("evaluation_criteria", []),
                    preferred_route=strategy.get("sourcing_rules", {}).get("preferred_route", "RFP")
                )
        return None
    
    def triage(
        self,
        case_id: str,
        user_intent: str,
        category_id: Optional[str] = None,
        trigger_source: str = "User",
        estimated_spend_usd: Optional[float] = None
    ) -> TriageResult:
        """
        Perform full triage on a sourcing request.
        
        This is the main entry point for DTP-01 Triage.
        
        Returns: TriageResult with classification, coverage status, and strategy card
        """
        # Step 1: Classify request type
        request_type = self.classify_request(user_intent, trigger_source)
        
        # Step 2: Check for coverage
        is_covered, matched_contract = self.check_coverage(user_intent, category_id)
        
        # Step 3: Determine status and build rationale
        if is_covered and matched_contract:
            status = TriageStatus.REDIRECT_TO_CATALOG
            coverage_rationale = (
                f"Request is covered by existing contract {matched_contract.get('contract_id')} "
                f"with supplier {matched_contract.get('supplier_id')}. "
                f"Redirect to buying channel."
            )
            matched_contract_id = matched_contract.get("contract_id")
            matched_supplier_id = matched_contract.get("supplier_id")
            # Use category from matched contract if not provided
            if not category_id:
                category_id = matched_contract.get("category_id")
        else:
            status = TriageStatus.PROCEED_TO_STRATEGY
            coverage_rationale = (
                f"No existing contract found covering this request. "
                f"Proceeding to sourcing strategy determination."
            )
            matched_contract_id = None
            matched_supplier_id = None
        
        # Step 4: Apply global rules
        global_rules = self.global_defaults.get("sourcing_rules", {})
        spend_threshold = global_rules.get("spend_threshold_3_bids_usd", 1500000)
        requires_3_bids = False
        if estimated_spend_usd and estimated_spend_usd >= spend_threshold:
            requires_3_bids = True
        
        # Step 5: Get payment terms default
        global_defaults = self.global_defaults.get("defaults", {})
        payment_terms = global_defaults.get("payment_terms", "Net 90")
        
        # Step 6: Link strategy card
        strategy_card_id = category_id if category_id else None
        
        return TriageResult(
            case_id=case_id,
            request_type=request_type,
            status=status,
            matched_contract_id=matched_contract_id,
            matched_supplier_id=matched_supplier_id,
            coverage_rationale=coverage_rationale,
            category_strategy_card_id=strategy_card_id,
            estimated_spend_usd=estimated_spend_usd,
            requires_3_bids=requires_3_bids,
            recommended_payment_terms=payment_terms
        )


# Convenience function for direct usage
def run_triage(
    case_id: str,
    user_intent: str,
    category_id: Optional[str] = None,
    trigger_source: str = "User",
    estimated_spend_usd: Optional[float] = None
) -> TriageResult:
    """
    Run triage on a sourcing request.
    
    This is the public API for the Triage Agent.
    """
    agent = TriageAgent()
    return agent.triage(
        case_id=case_id,
        user_intent=user_intent,
        category_id=category_id,
        trigger_source=trigger_source,
        estimated_spend_usd=estimated_spend_usd
    )
