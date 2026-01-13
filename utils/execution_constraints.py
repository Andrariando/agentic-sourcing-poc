"""
Execution Constraints - Authoritative, binding constraints from collaboration inputs.

CORE PRINCIPLE:
When a human states a preference, constraint, or requirement, it MUST override
default assumptions in all future reasoning. Collaboration is decision-shaping input.

DESIGN:
- ExecutionConstraints are first-class objects, not narrative memory
- They are binding constraints that agents MUST consume
- They are extracted deterministically (no LLM)
- Ambiguous inputs do NOT become constraints

DIFFERENCE FROM CaseMemory:
- CaseMemory: Narrative context, insights, history (informational)
- ExecutionConstraints: Hard inputs that override default logic (authoritative)
"""
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class ToleranceLevel(str, Enum):
    """Tolerance/sensitivity level for various constraints."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNSPECIFIED = "UNSPECIFIED"  # User hasn't indicated preference


class BudgetFlexibility(str, Enum):
    """Budget flexibility constraint."""
    FIXED = "FIXED"  # Hard budget limit, no flexibility
    FLEXIBLE = "FLEXIBLE"  # Can adjust if justified
    UNSPECIFIED = "UNSPECIFIED"


class NegotiationPosture(str, Enum):
    """Negotiation approach preference."""
    COLLABORATIVE = "COLLABORATIVE"  # Partnership-focused
    COMPETITIVE = "COMPETITIVE"  # Hard bargaining
    BALANCED = "BALANCED"  # Mix of both
    UNSPECIFIED = "UNSPECIFIED"


class SupplierPreference(str, Enum):
    """Preference for incumbent vs new suppliers."""
    PREFER_INCUMBENT = "PREFER_INCUMBENT"
    PREFER_NEW = "PREFER_NEW"
    NEUTRAL = "NEUTRAL"
    UNSPECIFIED = "UNSPECIFIED"


class ConstraintSource(BaseModel):
    """Records where a constraint came from for auditability."""
    user_input: str
    extracted_at: str
    dtp_stage: str
    pattern_matched: str


class ExecutionConstraints(BaseModel):
    """
    Authoritative, binding constraints extracted from collaboration inputs.
    
    These constraints MUST be consumed by all decision agents.
    Default logic MUST yield to these constraints when they conflict.
    """
    
    # Core tolerance/appetite constraints
    disruption_tolerance: ToleranceLevel = ToleranceLevel.UNSPECIFIED
    risk_appetite: ToleranceLevel = ToleranceLevel.UNSPECIFIED
    time_sensitivity: ToleranceLevel = ToleranceLevel.UNSPECIFIED
    
    # Stakeholder and process constraints
    stakeholder_alignment_required: Optional[bool] = None
    legal_review_required: Optional[bool] = None
    compliance_approval_required: Optional[bool] = None
    
    # Budget constraints
    budget_flexibility: BudgetFlexibility = BudgetFlexibility.UNSPECIFIED
    max_budget: Optional[float] = None  # Hard limit if specified
    target_savings_percent: Optional[float] = None
    
    # Supplier constraints
    supplier_preference: SupplierPreference = SupplierPreference.UNSPECIFIED
    excluded_suppliers: List[str] = Field(default_factory=list)
    required_suppliers: List[str] = Field(default_factory=list)  # Must include in evaluation
    
    # Negotiation constraints
    negotiation_posture: NegotiationPosture = NegotiationPosture.UNSPECIFIED
    walkaway_terms: List[str] = Field(default_factory=list)  # Deal-breakers
    must_have_terms: List[str] = Field(default_factory=list)  # Non-negotiable requirements
    nice_to_have_terms: List[str] = Field(default_factory=list)
    
    # Timeline constraints
    hard_deadline: Optional[str] = None  # ISO date if specified
    preferred_timeline: Optional[str] = None
    
    # Evaluation criteria preferences
    priority_criteria: List[str] = Field(default_factory=list)  # What matters most
    deprioritized_criteria: List[str] = Field(default_factory=list)  # What matters less
    
    # Custom constraints (for edge cases)
    custom_constraints: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit trail - where each constraint came from
    constraint_sources: List[ConstraintSource] = Field(default_factory=list)
    
    # Metadata
    last_updated: Optional[str] = None
    total_constraints_set: int = 0
    
    def has_any_constraints(self) -> bool:
        """Check if any constraints have been set."""
        return (
            self.disruption_tolerance != ToleranceLevel.UNSPECIFIED or
            self.risk_appetite != ToleranceLevel.UNSPECIFIED or
            self.time_sensitivity != ToleranceLevel.UNSPECIFIED or
            self.stakeholder_alignment_required is not None or
            self.budget_flexibility != BudgetFlexibility.UNSPECIFIED or
            self.supplier_preference != SupplierPreference.UNSPECIFIED or
            self.negotiation_posture != NegotiationPosture.UNSPECIFIED or
            len(self.excluded_suppliers) > 0 or
            len(self.required_suppliers) > 0 or
            len(self.walkaway_terms) > 0 or
            len(self.must_have_terms) > 0 or
            len(self.priority_criteria) > 0 or
            self.max_budget is not None or
            self.hard_deadline is not None
        )
    
    def get_active_constraints_summary(self) -> List[str]:
        """Get a human-readable summary of active constraints."""
        summary = []
        
        if self.disruption_tolerance != ToleranceLevel.UNSPECIFIED:
            summary.append(f"Disruption tolerance: {self.disruption_tolerance.value}")
        if self.risk_appetite != ToleranceLevel.UNSPECIFIED:
            summary.append(f"Risk appetite: {self.risk_appetite.value}")
        if self.time_sensitivity != ToleranceLevel.UNSPECIFIED:
            summary.append(f"Time sensitivity: {self.time_sensitivity.value}")
        if self.stakeholder_alignment_required is not None:
            summary.append(f"Stakeholder alignment required: {self.stakeholder_alignment_required}")
        if self.budget_flexibility != BudgetFlexibility.UNSPECIFIED:
            summary.append(f"Budget flexibility: {self.budget_flexibility.value}")
        if self.max_budget is not None:
            summary.append(f"Max budget: ${self.max_budget:,.0f}")
        if self.supplier_preference != SupplierPreference.UNSPECIFIED:
            summary.append(f"Supplier preference: {self.supplier_preference.value}")
        if self.excluded_suppliers:
            summary.append(f"Excluded suppliers: {', '.join(self.excluded_suppliers)}")
        if self.required_suppliers:
            summary.append(f"Required suppliers: {', '.join(self.required_suppliers)}")
        if self.negotiation_posture != NegotiationPosture.UNSPECIFIED:
            summary.append(f"Negotiation posture: {self.negotiation_posture.value}")
        if self.walkaway_terms:
            summary.append(f"Walkaway terms: {', '.join(self.walkaway_terms)}")
        if self.must_have_terms:
            summary.append(f"Must-have terms: {', '.join(self.must_have_terms)}")
        if self.priority_criteria:
            summary.append(f"Priority criteria: {', '.join(self.priority_criteria)}")
        if self.hard_deadline:
            summary.append(f"Hard deadline: {self.hard_deadline}")
        
        return summary
    
    def get_prompt_injection(self) -> str:
        """
        Generate constraint text for injection into agent prompts.
        
        This is the key method that ensures agents consume constraints.
        """
        if not self.has_any_constraints():
            return ""
        
        lines = [
            "=== BINDING USER CONSTRAINTS (MUST OVERRIDE DEFAULTS) ===",
            "The user has specified the following constraints during collaboration.",
            "These are AUTHORITATIVE and MUST be respected in your analysis.",
            "If these conflict with default logic, the CONSTRAINT WINS.",
            ""
        ]
        
        for constraint in self.get_active_constraints_summary():
            lines.append(f"• {constraint}")
        
        lines.append("")
        lines.append("Your recommendation MUST account for these constraints.")
        lines.append("If you cannot satisfy a constraint, you MUST explain why.")
        lines.append("=== END BINDING CONSTRAINTS ===")
        
        return "\n".join(lines)
    
    def record_constraint(
        self,
        user_input: str,
        dtp_stage: str,
        pattern_matched: str
    ) -> None:
        """Record the source of a constraint for auditability."""
        source = ConstraintSource(
            user_input=user_input[:200],  # Truncate for storage
            extracted_at=datetime.now().isoformat(),
            dtp_stage=dtp_stage,
            pattern_matched=pattern_matched
        )
        self.constraint_sources.append(source)
        self.last_updated = datetime.now().isoformat()
        self.total_constraints_set = len(self.get_active_constraints_summary())


def create_execution_constraints() -> ExecutionConstraints:
    """Factory function to create empty ExecutionConstraints."""
    return ExecutionConstraints()






