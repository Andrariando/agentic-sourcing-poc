"""
Contradiction Detector - Identifies conflicts between agent outputs.

PHASE 2 - OBJECTIVE E: Make Contradictions Visible (Not Auto-Resolved)

This module provides:
- Detection of conflicting recommendations between agents
- Logging of conflicts in the case memory
- Surfacing conflicts to humans in chat

DESIGN PRINCIPLE:
- Transparency > automation
- DO NOT attempt automatic resolution
- Let humans decide how to handle conflicts
"""
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Contradiction:
    """Represents a detected contradiction."""
    description: str
    agents_involved: List[str]
    severity: str  # "low", "medium", "high"
    details: Dict[str, Any]
    suggestion: Optional[str] = None


class ContradictionDetector:
    """
    Detects contradictions between agent outputs.
    
    Checks for:
    - Strategy contradictions (different recommendations for same case)
    - Supplier preference conflicts
    - Risk/opportunity misalignment
    - Timeline inconsistencies
    """
    
    def check_for_contradictions(
        self,
        new_output: Any,
        new_agent_name: str,
        previous_outputs: List[Tuple[str, Any]],  # List of (agent_name, output) tuples
        case_memory_state: Optional[Dict[str, Any]] = None
    ) -> List[Contradiction]:
        """
        Check if the new output contradicts any previous outputs.
        
        Args:
            new_output: The new agent output to check
            new_agent_name: Name of the agent that produced new_output
            previous_outputs: List of (agent_name, output) from prior runs
            case_memory_state: Optional memory state for context
        
        Returns:
            List of detected contradictions
        """
        contradictions = []
        
        if new_output is None:
            return contradictions
        
        new_type = type(new_output).__name__
        
        for prev_agent, prev_output in previous_outputs:
            if prev_output is None:
                continue
            
            prev_type = type(prev_output).__name__
            
            # Check strategy vs strategy
            if new_type == "StrategyRecommendation" and prev_type == "StrategyRecommendation":
                c = self._check_strategy_contradiction(
                    new_output, new_agent_name, prev_output, prev_agent
                )
                if c:
                    contradictions.append(c)
            
            # Check strategy vs supplier shortlist
            if new_type == "StrategyRecommendation" and prev_type == "SupplierShortlist":
                c = self._check_strategy_supplier_mismatch(
                    new_output, new_agent_name, prev_output, prev_agent
                )
                if c:
                    contradictions.append(c)
            
            # Check supplier shortlist vs negotiation
            if new_type == "NegotiationPlan" and prev_type == "SupplierShortlist":
                c = self._check_supplier_negotiation_mismatch(
                    new_output, new_agent_name, prev_output, prev_agent
                )
                if c:
                    contradictions.append(c)
        
        # Check against memory state if provided
        if case_memory_state:
            memory_contradictions = self._check_against_memory(
                new_output, new_type, new_agent_name, case_memory_state
            )
            contradictions.extend(memory_contradictions)
        
        return contradictions
    
    def _check_strategy_contradiction(
        self,
        new_output: Any,
        new_agent: str,
        prev_output: Any,
        prev_agent: str
    ) -> Optional[Contradiction]:
        """Check if two strategy recommendations contradict."""
        new_strategy = getattr(new_output, "recommended_strategy", None)
        prev_strategy = getattr(prev_output, "recommended_strategy", None)
        
        if new_strategy and prev_strategy and new_strategy != prev_strategy:
            # Check if this is a significant change
            major_shifts = [
                ("Renew", "Terminate"),
                ("Terminate", "Renew"),
                ("RFx", "Renew"),
                ("Renew", "RFx"),
            ]
            
            is_major = (new_strategy, prev_strategy) in major_shifts
            severity = "high" if is_major else "medium"
            
            return Contradiction(
                description=f"Strategy changed from '{prev_strategy}' to '{new_strategy}'",
                agents_involved=[prev_agent, new_agent],
                severity=severity,
                details={
                    "previous_strategy": prev_strategy,
                    "new_strategy": new_strategy,
                    "previous_confidence": getattr(prev_output, "confidence", None),
                    "new_confidence": getattr(new_output, "confidence", None),
                },
                suggestion="Please confirm which strategy direction to pursue."
            )
        
        return None
    
    def _check_strategy_supplier_mismatch(
        self,
        strategy_output: Any,
        strategy_agent: str,
        supplier_output: Any,
        supplier_agent: str
    ) -> Optional[Contradiction]:
        """Check if strategy recommendation conflicts with supplier shortlist."""
        strategy = getattr(strategy_output, "recommended_strategy", None)
        suppliers = getattr(supplier_output, "shortlisted_suppliers", [])
        
        # If strategy is "Terminate" but we have suppliers shortlisted
        if strategy == "Terminate" and len(suppliers) > 0:
            return Contradiction(
                description=f"Strategy recommends 'Terminate' but {len(suppliers)} suppliers were shortlisted",
                agents_involved=[strategy_agent, supplier_agent],
                severity="medium",
                details={
                    "strategy": strategy,
                    "supplier_count": len(suppliers),
                },
                suggestion="If terminating, supplier evaluation may not be needed. Please clarify direction."
            )
        
        # If strategy is "Renew" (current supplier) but different supplier is top choice
        if strategy == "Renew":
            top_choice = getattr(supplier_output, "top_choice_supplier_id", None)
            # We'd need current supplier ID from context to check this properly
            # For now, just flag if top choice exists and might differ
            if top_choice and len(suppliers) > 1:
                return Contradiction(
                    description=f"Strategy recommends 'Renew' but multiple suppliers were evaluated",
                    agents_involved=[strategy_agent, supplier_agent],
                    severity="low",
                    details={
                        "strategy": strategy,
                        "top_choice": top_choice,
                        "alternatives_count": len(suppliers) - 1,
                    },
                    suggestion="Renewal typically stays with current supplier. Confirm if alternatives should be considered."
                )
        
        return None
    
    def _check_supplier_negotiation_mismatch(
        self,
        negotiation_output: Any,
        negotiation_agent: str,
        supplier_output: Any,
        supplier_agent: str
    ) -> Optional[Contradiction]:
        """Check if negotiation plan supplier doesn't match shortlist."""
        negotiation_supplier = getattr(negotiation_output, "supplier_id", None)
        top_choice = getattr(supplier_output, "top_choice_supplier_id", None)
        shortlisted = [s.get("supplier_id") for s in getattr(supplier_output, "shortlisted_suppliers", [])]
        
        # Negotiation with a supplier not in shortlist
        if negotiation_supplier and negotiation_supplier not in shortlisted:
            return Contradiction(
                description=f"Negotiating with '{negotiation_supplier}' who was not in the shortlist",
                agents_involved=[supplier_agent, negotiation_agent],
                severity="high",
                details={
                    "negotiation_supplier": negotiation_supplier,
                    "shortlisted_suppliers": shortlisted,
                },
                suggestion="Negotiation should typically be with a shortlisted supplier. Please verify."
            )
        
        # Negotiation with non-top-choice (warning only)
        if negotiation_supplier and top_choice and negotiation_supplier != top_choice:
            return Contradiction(
                description=f"Negotiating with '{negotiation_supplier}' instead of top choice '{top_choice}'",
                agents_involved=[supplier_agent, negotiation_agent],
                severity="low",
                details={
                    "negotiation_supplier": negotiation_supplier,
                    "top_choice": top_choice,
                },
                suggestion="This may be intentional. Just confirming you want to proceed with this supplier."
            )
        
        return None
    
    def _check_against_memory(
        self,
        new_output: Any,
        new_type: str,
        new_agent: str,
        memory_state: Dict[str, Any]
    ) -> List[Contradiction]:
        """Check new output against memory state."""
        contradictions = []
        
        # Check if strategy changed from what's in memory
        if new_type == "StrategyRecommendation":
            new_strategy = getattr(new_output, "recommended_strategy", None)
            memory_strategy = memory_state.get("current_strategy")
            
            if memory_strategy and new_strategy and memory_strategy != new_strategy:
                # Check if human already approved the previous strategy
                human_decisions = memory_state.get("human_decisions", [])
                was_approved = any(
                    "Approve" in d and memory_strategy in d 
                    for d in human_decisions
                )
                
                if was_approved:
                    contradictions.append(Contradiction(
                        description=f"New recommendation '{new_strategy}' contradicts previously approved strategy '{memory_strategy}'",
                        agents_involved=["Memory", new_agent],
                        severity="high",
                        details={
                            "approved_strategy": memory_strategy,
                            "new_strategy": new_strategy,
                        },
                        suggestion="You previously approved a different strategy. Please confirm if you want to change direction."
                    ))
        
        return contradictions
    
    def format_contradictions_for_chat(self, contradictions: List[Contradiction]) -> List[str]:
        """Format contradictions for display in chat."""
        formatted = []
        for c in contradictions:
            icon = "⚠️" if c.severity in ["medium", "high"] else "ℹ️"
            text = f"{icon} {c.description}"
            if c.suggestion:
                text += f" — {c.suggestion}"
            formatted.append(text)
        return formatted


# Singleton instance
_detector = None

def get_contradiction_detector() -> ContradictionDetector:
    """Get the singleton ContradictionDetector instance."""
    global _detector
    if _detector is None:
        _detector = ContradictionDetector()
    return _detector


def detect_contradictions(
    new_output: Any,
    new_agent_name: str,
    previous_outputs: List[Tuple[str, Any]],
    case_memory_state: Optional[Dict[str, Any]] = None
) -> List[Contradiction]:
    """Convenience function to detect contradictions."""
    return get_contradiction_detector().check_for_contradictions(
        new_output, new_agent_name, previous_outputs, case_memory_state
    )





