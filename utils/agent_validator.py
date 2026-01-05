"""
Agent Output Validator - Enforces agent boundaries in code.

PHASE 2 - OBJECTIVE C: Enforce Agent Boundaries in Code (Not Prompts)

This module provides:
- Centralized registry of allowed outputs per agent
- Validation of agent outputs at the Supervisor level
- Explicit rejection/flagging of invalid agent actions

DESIGN PRINCIPLE:
- Prompts may describe constraints
- Code MUST enforce them
"""
from typing import Any, Dict, List, Optional, Tuple, Type
from pydantic import BaseModel


# Canonical registry of allowed output types per agent
AGENT_OUTPUT_REGISTRY: Dict[str, List[str]] = {
    "Strategy": ["StrategyRecommendation"],
    "SupplierEvaluation": ["SupplierShortlist"],
    "RFxDraft": ["RFxDraft"],
    "NegotiationSupport": ["NegotiationPlan"],
    "ContractSupport": ["ContractExtraction"],
    "Implementation": ["ImplementationPlan"],
    "SignalInterpretation": ["SignalAssessment"],
    "CaseClarifier": ["ClarificationRequest"],
}

# Allowed strategy values (enforced, not just prompted)
ALLOWED_STRATEGIES = ["Renew", "Renegotiate", "RFx", "Terminate", "Monitor"]

# Allowed confidence range
CONFIDENCE_RANGE = (0.0, 1.0)


class ValidationResult(BaseModel):
    """Result of output validation."""
    is_valid: bool
    agent_name: str
    output_type: str
    violations: List[str] = []
    warnings: List[str] = []
    corrected_output: Optional[Any] = None  # Output after correction (if applicable)


class AgentOutputValidator:
    """
    Validates agent outputs against defined boundaries.
    
    Called by Supervisor after each agent execution to ensure
    agents stay within their defined scope.
    """
    
    def __init__(self):
        self.output_registry = AGENT_OUTPUT_REGISTRY.copy()
        self.allowed_strategies = ALLOWED_STRATEGIES.copy()
    
    def validate_output(
        self,
        agent_name: str,
        output: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate an agent's output against its allowed boundaries.
        
        Args:
            agent_name: Name of the agent that produced the output
            output: The output object to validate
            context: Optional context (e.g., policy constraints)
        
        Returns:
            ValidationResult with validity status and any violations
        """
        violations = []
        warnings = []
        corrected_output = None
        
        if output is None:
            return ValidationResult(
                is_valid=True,
                agent_name=agent_name,
                output_type="None",
                violations=[],
                warnings=["Agent produced no output"]
            )
        
        output_type = type(output).__name__
        
        # CHECK 1: Is this output type allowed for this agent?
        allowed_types = self.output_registry.get(agent_name, [])
        if output_type not in allowed_types:
            violations.append(
                f"Agent '{agent_name}' produced '{output_type}' but is only allowed to produce: {allowed_types}"
            )
        
        # CHECK 2: Type-specific validations
        type_violations, type_warnings, corrected = self._validate_by_type(
            output, output_type, context
        )
        violations.extend(type_violations)
        warnings.extend(type_warnings)
        if corrected is not None:
            corrected_output = corrected
        
        return ValidationResult(
            is_valid=len(violations) == 0,
            agent_name=agent_name,
            output_type=output_type,
            violations=violations,
            warnings=warnings,
            corrected_output=corrected_output
        )
    
    def _validate_by_type(
        self,
        output: Any,
        output_type: str,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Optional[Any]]:
        """Type-specific validation rules."""
        violations = []
        warnings = []
        corrected = None
        
        if output_type == "StrategyRecommendation":
            violations, warnings, corrected = self._validate_strategy(output, context)
        elif output_type == "SupplierShortlist":
            violations, warnings, corrected = self._validate_supplier_shortlist(output, context)
        elif output_type == "NegotiationPlan":
            violations, warnings, corrected = self._validate_negotiation_plan(output, context)
        elif output_type == "ClarificationRequest":
            violations, warnings, corrected = self._validate_clarification(output, context)
        
        return violations, warnings, corrected
    
    def _validate_strategy(
        self,
        output: Any,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Optional[Any]]:
        """Validate StrategyRecommendation."""
        violations = []
        warnings = []
        corrected = None
        
        strategy = getattr(output, "recommended_strategy", None)
        confidence = getattr(output, "confidence", None)
        
        # Validate strategy is in allowed list
        if strategy and strategy not in self.allowed_strategies:
            violations.append(
                f"Invalid strategy '{strategy}'. Allowed: {self.allowed_strategies}"
            )
        
        # Validate confidence is in range
        if confidence is not None:
            if not (CONFIDENCE_RANGE[0] <= confidence <= CONFIDENCE_RANGE[1]):
                warnings.append(
                    f"Confidence {confidence} out of range {CONFIDENCE_RANGE}. Clamping."
                )
                # Clamp confidence
                corrected = output.model_copy() if hasattr(output, 'model_copy') else output
                if hasattr(corrected, 'confidence'):
                    corrected.confidence = max(CONFIDENCE_RANGE[0], min(CONFIDENCE_RANGE[1], confidence))
        
        # Check policy constraints if provided
        if context:
            allowed_by_policy = context.get("allowed_strategies")
            if allowed_by_policy and strategy and strategy not in allowed_by_policy:
                violations.append(
                    f"Strategy '{strategy}' not allowed by policy. Policy allows: {allowed_by_policy}"
                )
        
        # Validate rationale is not empty
        rationale = getattr(output, "rationale", [])
        if not rationale:
            warnings.append("Strategy recommendation has no rationale provided")
        
        return violations, warnings, corrected
    
    def _validate_supplier_shortlist(
        self,
        output: Any,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Optional[Any]]:
        """Validate SupplierShortlist."""
        violations = []
        warnings = []
        
        suppliers = getattr(output, "shortlisted_suppliers", [])
        top_choice = getattr(output, "top_choice_supplier_id", None)
        
        # Validate supplier IDs format
        for s in suppliers:
            supplier_id = s.get("supplier_id", "")
            if supplier_id and not supplier_id.startswith("SUP-"):
                warnings.append(f"Supplier ID '{supplier_id}' doesn't follow SUP-xxx format")
        
        # Validate top choice is in shortlist
        if top_choice:
            supplier_ids = [s.get("supplier_id") for s in suppliers]
            if top_choice not in supplier_ids:
                violations.append(
                    f"Top choice '{top_choice}' is not in the shortlisted suppliers"
                )
        
        # Validate scores are in range
        for s in suppliers:
            score = s.get("score")
            if score is not None and not (0.0 <= score <= 10.0):
                warnings.append(f"Score {score} for {s.get('supplier_id')} out of range 0-10")
        
        return violations, warnings, None
    
    def _validate_negotiation_plan(
        self,
        output: Any,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Optional[Any]]:
        """Validate NegotiationPlan."""
        violations = []
        warnings = []
        
        supplier_id = getattr(output, "supplier_id", None)
        objectives = getattr(output, "negotiation_objectives", [])
        
        # Validate supplier ID is present
        if not supplier_id:
            violations.append("Negotiation plan must specify a supplier_id")
        
        # Validate objectives are present
        if not objectives:
            warnings.append("Negotiation plan has no objectives defined")
        
        return violations, warnings, None
    
    def _validate_clarification(
        self,
        output: Any,
        context: Optional[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Optional[Any]]:
        """Validate ClarificationRequest."""
        violations = []
        warnings = []
        
        questions = getattr(output, "questions", [])
        reason = getattr(output, "reason", "")
        
        # Validate at least one question
        if not questions:
            violations.append("Clarification request must contain at least one question")
        
        # Validate reason is provided
        if not reason:
            warnings.append("Clarification request should specify a reason")
        
        return violations, warnings, None
    
    def get_allowed_outputs(self, agent_name: str) -> List[str]:
        """Get the list of allowed output types for an agent."""
        return self.output_registry.get(agent_name, [])
    
    def is_output_allowed(self, agent_name: str, output_type: str) -> bool:
        """Check if an output type is allowed for an agent."""
        allowed = self.output_registry.get(agent_name, [])
        return output_type in allowed


# Singleton instance
_validator = None

def get_agent_validator() -> AgentOutputValidator:
    """Get the singleton AgentOutputValidator instance."""
    global _validator
    if _validator is None:
        _validator = AgentOutputValidator()
    return _validator


def validate_agent_output(
    agent_name: str,
    output: Any,
    context: Optional[Dict[str, Any]] = None
) -> ValidationResult:
    """Convenience function to validate an agent output."""
    return get_agent_validator().validate_output(agent_name, output, context)





