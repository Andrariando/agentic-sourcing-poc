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
    
    def classify_request(
        self, 
        user_intent: str, 
        trigger_source: str = "User",
        matched_contract: Optional[Dict[str, Any]] = None
    ) -> Tuple[RequestType, float, List[str]]:
        """
        Classify the request type based on intent, trigger, and contract data.
        
        Returns: (RequestType, confidence, evidence_list)
        
        Confidence Scoring Logic (Rule-Based):
        - 0.9: Contract expiry match + no scope change (strongest signal)
        - 0.85: Signal-triggered OR scope change detected OR explicit keywords
        - 0.8: User mentioned "renew" keyword
        - 0.75: Mixed signals (e.g., "renew" + "change")
        - 0.6: Default guess (Demand-Based)
        
        Confidence is NOT ML-based. It's a heuristic based on evidence strength:
        - Contract data (expiry, keywords) > User keywords > Default guess
        """
        intent_lower = user_intent.lower()
        evidence = []
        confidence = 0.5
        
        # Check contract expiry for Renewal detection
        if matched_contract:
            expiry_str = matched_contract.get("end_date", "")
            if expiry_str:
                try:
                    from datetime import datetime
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
                    days_to_expiry = (expiry - datetime.now()).days
                    
                    if days_to_expiry <= 90:
                        evidence.append(f"Contract expires in {days_to_expiry} days")
                        evidence.append(f"Matched contract: {matched_contract.get('contract_id')}")
                        
                        # Check for scope change indicators
                        if any(kw in intent_lower for kw in ["change", "expand", "modify", "different", "new scope"]):
                            confidence = 0.85
                            evidence.append("User indicated scope changes")
                            return RequestType.RENEWAL_SCOPE_CHANGE, confidence, evidence
                        else:
                            confidence = 0.9
                            evidence.append("No scope changes indicated")
                            return RequestType.RENEWAL_NO_CHANGE, confidence, evidence
                except:
                    pass
        
        # Signal-triggered = Renewal
        if trigger_source == "Signal":
            evidence.append("Triggered by system signal")
            confidence = 0.85
            return RequestType.RENEWAL_NO_CHANGE, confidence, evidence
        
        # Keyword-based classification
        if any(kw in intent_lower for kw in ["renew", "renewal", "expir", "contract ending"]):
            evidence.append("User mentioned renewal keywords")
            
            if any(kw in intent_lower for kw in ["change", "expand", "modify"]):
                confidence = 0.75
                evidence.append("Scope change keywords detected")
                return RequestType.RENEWAL_SCOPE_CHANGE, confidence, evidence
            else:
                confidence = 0.8
                return RequestType.RENEWAL_NO_CHANGE, confidence, evidence
        
        # Fast-Pass keywords
        if any(kw in intent_lower for kw in ["fast-pass", "quick buy", "pre-approved", "catalog order"]):
            evidence.append("Pre-approved/catalog keywords detected")
            confidence = 0.85
            return RequestType.FAST_PASS, confidence, evidence
        
        # Ad-hoc keywords
        if any(kw in intent_lower for kw in ["urgent", "ad-hoc", "one-time", "emergency", "off-system"]):
            evidence.append("Urgency/ad-hoc keywords detected")
            confidence = 0.8
            return RequestType.AD_HOC, confidence, evidence
        
        # Default to Demand-Based
        evidence.append("Standard procurement request")
        confidence = 0.6
        return RequestType.DEMAND_BASED, confidence, evidence
    
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
    
    def get_routing_path(self, request_type: RequestType) -> Tuple[List[str], List[str]]:
        """
        Get the DTP routing path based on request type.
        
        Returns: (active_stages, skipped_stages)
        """
        all_stages = ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"]
        
        if request_type == RequestType.RENEWAL_NO_CHANGE:
            # Skip Supplier Eval and Sourcing
            active = ["DTP-01", "DTP-04", "DTP-05", "DTP-06"]
            skipped = ["DTP-02", "DTP-03"]
        elif request_type == RequestType.FAST_PASS:
            # Skip to Contracting
            active = ["DTP-01", "DTP-05", "DTP-06"]
            skipped = ["DTP-02", "DTP-03", "DTP-04"]
        else:
            # Full path for Demand-Based, Renewal with Scope Change, Ad-Hoc
            active = all_stages
            skipped = []
        
        return active, skipped
    
    def triage(
        self,
        case_id: str,
        user_intent: str,
        category_id: Optional[str] = None,
        trigger_source: str = "User",
        estimated_spend_usd: Optional[float] = None
    ) -> TriageResult:
        """
        Perform Smart Triage: propose category, provide evidence, await confirmation.
        """
        # Step 1: Check for coverage first (needed for classification)
        is_covered, matched_contract = self.check_coverage(user_intent, category_id)
        
        # Step 2: Classify with evidence
        request_type, confidence, evidence = self.classify_request(
            user_intent, trigger_source, matched_contract
        )
        
        # Step 3: Get routing path
        routing_path, skipped_stages = self.get_routing_path(request_type)
        
        # Step 4: Build coverage rationale
        contract_expiry_days = None
        if matched_contract:
            matched_contract_id = matched_contract.get("contract_id")
            matched_supplier_id = matched_contract.get("supplier_id")
            
            # Calculate expiry days
            expiry_str = matched_contract.get("end_date", "")
            if expiry_str:
                try:
                    from datetime import datetime
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
                    contract_expiry_days = (expiry - datetime.now()).days
                except:
                    pass
            
            coverage_rationale = (
                f"Matched contract {matched_contract_id} with supplier {matched_supplier_id}."
            )
            if not category_id:
                category_id = matched_contract.get("category_id")
        else:
            matched_contract_id = None
            matched_supplier_id = None
            coverage_rationale = "No existing contract match found."
        
        # Step 5: Apply global rules
        global_rules = self.global_defaults.get("sourcing_rules", {})
        spend_threshold = global_rules.get("spend_threshold_3_bids_usd", 1500000)
        requires_3_bids = bool(estimated_spend_usd and estimated_spend_usd >= spend_threshold)
        
        global_defaults = self.global_defaults.get("defaults", {})
        payment_terms = global_defaults.get("payment_terms", "Net 90")
        
        return TriageResult(
            case_id=case_id,
            proposed_request_type=request_type,
            confidence=confidence,
            evidence=evidence,
            routing_path=routing_path,
            skipped_stages=skipped_stages,
            matched_contract_id=matched_contract_id,
            matched_supplier_id=matched_supplier_id,
            contract_expiry_days=contract_expiry_days,
            status=TriageStatus.AWAITING_CONFIRMATION,
            coverage_rationale=coverage_rationale,
            category_strategy_card_id=category_id,
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
