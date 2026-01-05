"""
Constraint Compliance Checker - Hard enforcement of ExecutionConstraints.

ARCHITECTURAL INVARIANT (NON-NEGOTIABLE):
No execution output is valid unless it explicitly accounts for every active ExecutionConstraint.

"Accounting for" means:
- Either satisfying the constraint
- OR explicitly explaining why it cannot be satisfied

SILENCE IS FORBIDDEN.

This checker is:
- Rule-based (no LLM)
- Deterministic
- Machine-checkable
- Runs AFTER every agent execution, BEFORE Supervisor approval
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from utils.execution_constraints import (
    ExecutionConstraints,
    ToleranceLevel,
    BudgetFlexibility,
    NegotiationPosture,
    SupplierPreference,
)


class ComplianceStatus(str, Enum):
    """Status of constraint compliance check."""
    COMPLIANT = "COMPLIANT"  # All constraints addressed
    NON_COMPLIANT = "NON_COMPLIANT"  # Some constraints not addressed
    NO_CONSTRAINTS = "NO_CONSTRAINTS"  # No active constraints to check


@dataclass
class ConstraintViolation:
    """Represents a constraint that was not addressed in the output."""
    constraint_name: str
    constraint_value: str
    expected_behavior: str
    violation_type: str  # "missing_reference" | "contradicted" | "not_justified"


@dataclass
class ComplianceResult:
    """Result of constraint compliance check."""
    status: ComplianceStatus
    violations: List[ConstraintViolation]
    addressed_constraints: List[str]
    required_acknowledgment: str  # Mandatory text that must appear in response
    blocking: bool  # If True, execution must not proceed silently


class ConstraintComplianceChecker:
    """
    Deterministic checker that enforces constraint compliance.
    
    Runs after every agent execution to verify that the output
    explicitly addresses all active ExecutionConstraints.
    """
    
    def check_compliance(
        self,
        agent_output: Any,
        execution_constraints: ExecutionConstraints,
        agent_name: str
    ) -> ComplianceResult:
        """
        Check if agent output complies with all active constraints.
        
        Args:
            agent_output: The agent's output (StrategyRecommendation, SupplierShortlist, etc.)
            execution_constraints: Active constraints from collaboration
            agent_name: Name of the agent that produced the output
        
        Returns:
            ComplianceResult with violations and required acknowledgment
        """
        if not execution_constraints or not execution_constraints.has_any_constraints():
            return ComplianceResult(
                status=ComplianceStatus.NO_CONSTRAINTS,
                violations=[],
                addressed_constraints=[],
                required_acknowledgment="",
                blocking=False
            )
        
        violations = []
        addressed = []
        
        # Get output text for checking (rationale, recommendation, etc.)
        output_text = self._extract_output_text(agent_output)
        
        # Check each active constraint
        violations.extend(self._check_disruption_tolerance(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_risk_appetite(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_time_sensitivity(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_stakeholder_alignment(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_budget_flexibility(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_supplier_preference(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_negotiation_posture(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_priority_criteria(
            execution_constraints, output_text, agent_output
        ))
        violations.extend(self._check_excluded_suppliers(
            execution_constraints, output_text, agent_output
        ))
        
        # Build list of addressed constraints
        all_constraints = execution_constraints.get_active_constraints_summary()
        violation_names = {v.constraint_name for v in violations}
        addressed = [c for c in all_constraints if not any(v.constraint_name in c for v in violations)]
        
        # Build required acknowledgment
        required_acknowledgment = self._build_required_acknowledgment(
            execution_constraints, violations, agent_name
        )
        
        # Determine status and blocking
        if violations:
            return ComplianceResult(
                status=ComplianceStatus.NON_COMPLIANT,
                violations=violations,
                addressed_constraints=addressed,
                required_acknowledgment=required_acknowledgment,
                blocking=True  # Block silent progression
            )
        else:
            return ComplianceResult(
                status=ComplianceStatus.COMPLIANT,
                violations=[],
                addressed_constraints=addressed,
                required_acknowledgment=required_acknowledgment,
                blocking=False
            )
    
    def _extract_output_text(self, agent_output: Any) -> str:
        """Extract searchable text from agent output."""
        text_parts = []
        
        # Common fields across different output types
        if hasattr(agent_output, 'rationale'):
            rationale = getattr(agent_output, 'rationale', [])
            if isinstance(rationale, list):
                text_parts.extend(rationale)
            else:
                text_parts.append(str(rationale))
        
        if hasattr(agent_output, 'recommendation'):
            text_parts.append(str(getattr(agent_output, 'recommendation', '')))
        
        if hasattr(agent_output, 'risk_assessment'):
            text_parts.append(str(getattr(agent_output, 'risk_assessment', '')))
        
        if hasattr(agent_output, 'comparison_summary'):
            text_parts.append(str(getattr(agent_output, 'comparison_summary', '')))
        
        if hasattr(agent_output, 'timeline_recommendation'):
            text_parts.append(str(getattr(agent_output, 'timeline_recommendation', '')))
        
        if hasattr(agent_output, 'constraint_acknowledgments'):
            acks = getattr(agent_output, 'constraint_acknowledgments', [])
            if isinstance(acks, list):
                text_parts.extend(acks)
        
        return ' '.join(text_parts).lower()
    
    def _check_disruption_tolerance(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if disruption tolerance constraint is addressed."""
        if constraints.disruption_tolerance == ToleranceLevel.UNSPECIFIED:
            return []
        
        keywords = {
            ToleranceLevel.HIGH: ["disruption", "aggressive", "competitive", "change", "switch"],
            ToleranceLevel.LOW: ["stability", "continuity", "conservative", "maintain", "incumbent"],
            ToleranceLevel.MEDIUM: ["balanced", "moderate", "careful"]
        }
        
        expected_keywords = keywords.get(constraints.disruption_tolerance, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="disruption_tolerance",
                constraint_value=constraints.disruption_tolerance.value,
                expected_behavior=f"Output should reference {constraints.disruption_tolerance.value} disruption tolerance",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_risk_appetite(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if risk appetite constraint is addressed."""
        if constraints.risk_appetite == ToleranceLevel.UNSPECIFIED:
            return []
        
        keywords = {
            ToleranceLevel.HIGH: ["risk", "aggressive", "bold", "opportunity"],
            ToleranceLevel.LOW: ["risk", "conservative", "safe", "caution", "minimize risk"],
            ToleranceLevel.MEDIUM: ["balanced risk", "moderate risk", "measured"]
        }
        
        expected_keywords = keywords.get(constraints.risk_appetite, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="risk_appetite",
                constraint_value=constraints.risk_appetite.value,
                expected_behavior=f"Output should reference {constraints.risk_appetite.value} risk appetite",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_time_sensitivity(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if time sensitivity constraint is addressed."""
        if constraints.time_sensitivity == ToleranceLevel.UNSPECIFIED:
            return []
        
        keywords = {
            ToleranceLevel.HIGH: ["urgent", "fast", "quick", "immediate", "speed", "timeline"],
            ToleranceLevel.LOW: ["thorough", "time", "careful", "comprehensive"],
            ToleranceLevel.MEDIUM: ["balanced", "reasonable timeline"]
        }
        
        expected_keywords = keywords.get(constraints.time_sensitivity, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="time_sensitivity",
                constraint_value=constraints.time_sensitivity.value,
                expected_behavior=f"Output should reference {constraints.time_sensitivity.value} time sensitivity",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_stakeholder_alignment(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if stakeholder alignment constraint is addressed."""
        if constraints.stakeholder_alignment_required is None:
            return []
        
        keywords = ["stakeholder", "alignment", "approval", "buy-in", "sign-off"]
        found = any(kw in output_text for kw in keywords)
        
        if not found and constraints.stakeholder_alignment_required:
            return [ConstraintViolation(
                constraint_name="stakeholder_alignment_required",
                constraint_value="True",
                expected_behavior="Output should reference stakeholder alignment requirement",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_budget_flexibility(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if budget flexibility constraint is addressed."""
        if constraints.budget_flexibility == BudgetFlexibility.UNSPECIFIED:
            return []
        
        keywords = {
            BudgetFlexibility.FIXED: ["budget", "cost", "fixed", "limit", "constraint"],
            BudgetFlexibility.FLEXIBLE: ["budget", "flexible", "invest", "value"]
        }
        
        expected_keywords = keywords.get(constraints.budget_flexibility, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="budget_flexibility",
                constraint_value=constraints.budget_flexibility.value,
                expected_behavior=f"Output should reference {constraints.budget_flexibility.value} budget",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_supplier_preference(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if supplier preference constraint is addressed."""
        if constraints.supplier_preference == SupplierPreference.UNSPECIFIED:
            return []
        
        keywords = {
            SupplierPreference.PREFER_INCUMBENT: ["incumbent", "current supplier", "existing", "relationship", "continuity"],
            SupplierPreference.PREFER_NEW: ["new supplier", "alternative", "fresh", "competition", "switch"],
            SupplierPreference.NEUTRAL: ["objective", "neutral", "all options"]
        }
        
        expected_keywords = keywords.get(constraints.supplier_preference, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="supplier_preference",
                constraint_value=constraints.supplier_preference.value,
                expected_behavior=f"Output should reference {constraints.supplier_preference.value} supplier preference",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_negotiation_posture(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if negotiation posture constraint is addressed."""
        if constraints.negotiation_posture == NegotiationPosture.UNSPECIFIED:
            return []
        
        keywords = {
            NegotiationPosture.COMPETITIVE: ["leverage", "aggressive", "competitive", "push", "maximize"],
            NegotiationPosture.COLLABORATIVE: ["partnership", "collaborative", "relationship", "win-win"],
            NegotiationPosture.BALANCED: ["balanced", "moderate", "pragmatic"]
        }
        
        expected_keywords = keywords.get(constraints.negotiation_posture, [])
        found = any(kw in output_text for kw in expected_keywords)
        
        if not found:
            return [ConstraintViolation(
                constraint_name="negotiation_posture",
                constraint_value=constraints.negotiation_posture.value,
                expected_behavior=f"Output should reference {constraints.negotiation_posture.value} negotiation posture",
                violation_type="missing_reference"
            )]
        return []
    
    def _check_priority_criteria(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if priority criteria constraint is addressed."""
        if not constraints.priority_criteria:
            return []
        
        violations = []
        for criterion in constraints.priority_criteria:
            if criterion.lower() not in output_text:
                violations.append(ConstraintViolation(
                    constraint_name="priority_criteria",
                    constraint_value=criterion,
                    expected_behavior=f"Output should reference priority criterion: {criterion}",
                    violation_type="missing_reference"
                ))
        
        return violations
    
    def _check_excluded_suppliers(
        self,
        constraints: ExecutionConstraints,
        output_text: str,
        agent_output: Any
    ) -> List[ConstraintViolation]:
        """Check if excluded suppliers are actually excluded."""
        if not constraints.excluded_suppliers:
            return []
        
        violations = []
        
        # Check if agent output includes shortlisted suppliers
        if hasattr(agent_output, 'shortlisted_suppliers'):
            shortlisted = getattr(agent_output, 'shortlisted_suppliers', [])
            for excluded in constraints.excluded_suppliers:
                for supplier in shortlisted:
                    supplier_name = getattr(supplier, 'name', '') if hasattr(supplier, 'name') else str(supplier)
                    supplier_id = getattr(supplier, 'supplier_id', '') if hasattr(supplier, 'supplier_id') else ''
                    if excluded.lower() in supplier_name.lower() or excluded.lower() in supplier_id.lower():
                        violations.append(ConstraintViolation(
                            constraint_name="excluded_suppliers",
                            constraint_value=excluded,
                            expected_behavior=f"Supplier '{excluded}' should be excluded from shortlist",
                            violation_type="contradicted"
                        ))
        
        return violations
    
    def _build_required_acknowledgment(
        self,
        constraints: ExecutionConstraints,
        violations: List[ConstraintViolation],
        agent_name: str
    ) -> str:
        """
        Build the required acknowledgment text that MUST appear in the response.
        
        This is the mandatory behavioral reflection.
        """
        active = constraints.get_active_constraints_summary()
        if not active:
            return ""
        
        # Build acknowledgment preamble
        parts = ["**Based on your stated preferences:**"]
        
        # Add each constraint acknowledgment
        constraint_phrases = []
        
        if constraints.disruption_tolerance != ToleranceLevel.UNSPECIFIED:
            if constraints.disruption_tolerance == ToleranceLevel.HIGH:
                constraint_phrases.append("disruption is acceptable")
            elif constraints.disruption_tolerance == ToleranceLevel.LOW:
                constraint_phrases.append("minimizing disruption is a priority")
        
        if constraints.risk_appetite != ToleranceLevel.UNSPECIFIED:
            if constraints.risk_appetite == ToleranceLevel.HIGH:
                constraint_phrases.append("you're comfortable with risk")
            elif constraints.risk_appetite == ToleranceLevel.LOW:
                constraint_phrases.append("a conservative approach is preferred")
        
        if constraints.time_sensitivity != ToleranceLevel.UNSPECIFIED:
            if constraints.time_sensitivity == ToleranceLevel.HIGH:
                constraint_phrases.append("speed is critical")
            elif constraints.time_sensitivity == ToleranceLevel.LOW:
                constraint_phrases.append("thoroughness is valued over speed")
        
        if constraints.stakeholder_alignment_required:
            constraint_phrases.append("stakeholder alignment is required")
        
        if constraints.budget_flexibility != BudgetFlexibility.UNSPECIFIED:
            if constraints.budget_flexibility == BudgetFlexibility.FIXED:
                constraint_phrases.append("the budget is fixed")
            else:
                constraint_phrases.append("there's budget flexibility if justified")
        
        if constraints.supplier_preference != SupplierPreference.UNSPECIFIED:
            if constraints.supplier_preference == SupplierPreference.PREFER_INCUMBENT:
                constraint_phrases.append("the incumbent relationship is valued")
            elif constraints.supplier_preference == SupplierPreference.PREFER_NEW:
                constraint_phrases.append("you're open to new suppliers")
        
        if constraints.negotiation_posture != NegotiationPosture.UNSPECIFIED:
            if constraints.negotiation_posture == NegotiationPosture.COMPETITIVE:
                constraint_phrases.append("an aggressive negotiation approach is preferred")
            elif constraints.negotiation_posture == NegotiationPosture.COLLABORATIVE:
                constraint_phrases.append("relationship preservation is important")
        
        if constraints.priority_criteria:
            criteria_str = ", ".join(constraints.priority_criteria)
            constraint_phrases.append(f"{criteria_str} is/are the priority")
        
        if constraints.excluded_suppliers:
            excluded_str = ", ".join(constraints.excluded_suppliers)
            constraint_phrases.append(f"{excluded_str} is/are excluded from consideration")
        
        if constraint_phrases:
            # Join with proper grammar
            if len(constraint_phrases) == 1:
                parts.append(f"Since {constraint_phrases[0]}, I've factored this into my analysis.")
            elif len(constraint_phrases) == 2:
                parts.append(f"Since {constraint_phrases[0]} and {constraint_phrases[1]}, I've factored these into my analysis.")
            else:
                joined = ", ".join(constraint_phrases[:-1]) + f", and {constraint_phrases[-1]}"
                parts.append(f"Since {joined}, I've factored these into my analysis.")
        
        # Add violation warnings if any
        if violations:
            parts.append("")
            parts.append("⚠️ **Note:** Some constraints could not be fully addressed:")
            for v in violations[:3]:  # Limit to first 3
                parts.append(f"• {v.constraint_name}: {v.expected_behavior}")
        
        return "\n".join(parts)


def get_constraint_compliance_checker() -> ConstraintComplianceChecker:
    """Get the constraint compliance checker singleton."""
    return ConstraintComplianceChecker()


def generate_constraint_reflection(
    constraints: ExecutionConstraints,
    recommendation_unchanged: bool = False,
    reason_unchanged: str = ""
) -> str:
    """
    Generate mandatory behavioral reflection text.
    
    This MUST appear before any recommendation when constraints exist.
    """
    if not constraints or not constraints.has_any_constraints():
        return ""
    
    checker = get_constraint_compliance_checker()
    reflection = checker._build_required_acknowledgment(constraints, [], "")
    
    if recommendation_unchanged and reason_unchanged:
        reflection += f"\n\n_Even with these preferences, the recommendation remains the same because {reason_unchanged}._"
    
    return reflection





