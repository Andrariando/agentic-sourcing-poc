"""
Policy Loader - Dynamic policy loading for DTP stages and categories.

Loads policy constraints from configuration, supporting:
- Category-specific overrides
- Renewal-specific constraints
- Stage-specific mandatory checks
"""
from typing import Optional, Dict, Any, List
from utils.schemas import DTPPolicyContext
from utils.data_loader import get_category


class PolicyLoader:
    """
    Loads policy constraints dynamically based on DTP stage and category.
    Supports category-specific overrides and renewal constraints.
    """
    
    def __init__(self):
        # Default policy configurations
        self.default_policies = {
            "DTP-01": {
                "allowed_actions": ["DTP-02"],
                "mandatory_checks": ["Ensure category strategy exists"],
                "human_required_for": ["High-impact strategy shifts"],
                "allowed_strategies": None,  # None means all strategies allowed
                "allow_rfx_for_renewals": False
            },
            "DTP-02": {
                "allowed_actions": ["DTP-03", "DTP-04"],
                "mandatory_checks": ["FMV check", "Market localization"],
                "human_required_for": ["Approach to market decisions"],
                "allowed_strategies": None,
                "allow_rfx_for_renewals": False
            },
            "DTP-03": {
                "allowed_actions": ["DTP-04"],
                "mandatory_checks": ["Supplier MCDM criteria defined"],
                "human_required_for": [],
                "allowed_strategies": None,
                "allow_rfx_for_renewals": False
            },
            "DTP-04": {
                "allowed_actions": ["DTP-05"],
                "mandatory_checks": ["DDR/HCC flags resolved", "Compliance approvals"],
                "human_required_for": ["Supplier award / negotiation mandate"],
                "allowed_strategies": None,
                "allow_rfx_for_renewals": False
            },
            "DTP-05": {
                "allowed_actions": ["DTP-06"],
                "mandatory_checks": ["Contracting guardrails"],
                "human_required_for": [],
                "allowed_strategies": None,
                "allow_rfx_for_renewals": False
            },
            "DTP-06": {
                "allowed_actions": ["DTP-06"],  # Terminal
                "mandatory_checks": ["Savings validation & reporting"],
                "human_required_for": ["Savings sign-off"],
                "allowed_strategies": None,
                "allow_rfx_for_renewals": False
            }
        }
        
        # Category-specific overrides
        self.category_overrides = {
            # Example: CAT-01 might have different renewal policies
            "CAT-01": {
                "DTP-01": {
                    "allow_rfx_for_renewals": True  # IT services allow RFx for renewals
                }
            }
        }
    
    def load_policy_for_stage(
        self,
        dtp_stage: str,
        category_id: Optional[str] = None,
        trigger_type: Optional[str] = None
    ) -> DTPPolicyContext:
        """
        Load policy context for a given DTP stage, with optional category and trigger type.
        
        Args:
            dtp_stage: DTP stage (e.g., "DTP-01")
            category_id: Optional category ID for category-specific overrides
            trigger_type: Optional trigger type (e.g., "Renewal") for renewal-specific constraints
        
        Returns:
            DTPPolicyContext with policy constraints
        """
        # Start with default policy for stage
        policy = self.default_policies.get(dtp_stage, {}).copy()
        
        # Apply category-specific overrides if provided
        if category_id and category_id in self.category_overrides:
            category_policy = self.category_overrides[category_id].get(dtp_stage, {})
            policy.update(category_policy)
        
        # Apply renewal-specific constraints if trigger is Renewal
        if trigger_type == "Renewal" and dtp_stage == "DTP-01":
            # Renewal cases: constrain strategy options
            policy["allowed_strategies"] = ["Renew", "Renegotiate", "Terminate"]
            
            # Only allow RFx if explicitly permitted by category policy
            if not policy.get("allow_rfx_for_renewals", False):
                # Ensure RFx is not in allowed strategies
                if policy["allowed_strategies"] and "RFx" in policy["allowed_strategies"]:
                    policy["allowed_strategies"].remove("RFx")
            else:
                # RFx explicitly allowed for this category
                if "RFx" not in policy["allowed_strategies"]:
                    policy["allowed_strategies"].append("RFx")
        
        # Build DTPPolicyContext
        return DTPPolicyContext(
            allowed_actions=policy.get("allowed_actions", []),
            mandatory_checks=policy.get("mandatory_checks", []),
            human_required_for=policy.get("human_required_for", []),
            allowed_strategies=policy.get("allowed_strategies"),
            allow_rfx_for_renewals=policy.get("allow_rfx_for_renewals", False)
        )
    
    def is_strategy_allowed(
        self,
        strategy: str,
        dtp_stage: str,
        category_id: Optional[str] = None,
        trigger_type: Optional[str] = None
    ) -> bool:
        """
        Check if a specific strategy is allowed for the given context.
        
        Args:
            strategy: Strategy to check (e.g., "RFx", "Renew")
            dtp_stage: DTP stage
            category_id: Optional category ID
            trigger_type: Optional trigger type
        
        Returns:
            True if strategy is allowed, False otherwise
        """
        policy = self.load_policy_for_stage(dtp_stage, category_id, trigger_type)
        
        # If allowed_strategies is None, all strategies are allowed
        if policy.allowed_strategies is None:
            return True
        
        # Check if strategy is in allowed list
        return strategy in policy.allowed_strategies
    
    def get_renewal_constraints(
        self,
        category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get renewal-specific constraints for a category.
        
        Returns:
            Dictionary with renewal constraints
        """
        policy = self.load_policy_for_stage("DTP-01", category_id, "Renewal")
        
        return {
            "allowed_strategies": policy.allowed_strategies or ["Renew", "Renegotiate", "RFx", "Terminate", "Monitor"],
            "allow_rfx": policy.allow_rfx_for_renewals,
            "default_strategies": ["Renew", "Renegotiate", "Terminate"]
        }

