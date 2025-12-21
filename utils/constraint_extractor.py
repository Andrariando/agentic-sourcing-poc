"""
Deterministic Constraint Extractor - Rule-based extraction of binding constraints.

DESIGN PRINCIPLES:
- NO LLM usage - fully deterministic
- Ambiguous inputs do NOT become constraints
- Only clear, explicit statements are promoted to constraints
- All extractions are logged for auditability

This module converts collaboration inputs into authoritative ExecutionConstraints
that MUST be respected by all decision agents.
"""
from typing import List, Tuple, Optional
from dataclasses import dataclass
from utils.execution_constraints import (
    ExecutionConstraints,
    ToleranceLevel,
    BudgetFlexibility,
    NegotiationPosture,
    SupplierPreference,
)
import re


@dataclass
class ExtractionResult:
    """Result of constraint extraction from user input."""
    constraints_extracted: int
    acknowledgments: List[str]  # Human-like acknowledgments for each constraint
    constraint_details: List[Tuple[str, str, str]]  # (field, value, pattern_matched)


# ============================================================================
# PATTERN DEFINITIONS
# Each pattern maps user statements to constraint values.
# Only CLEAR, UNAMBIGUOUS statements should match.
# ============================================================================

# Disruption Tolerance Patterns
DISRUPTION_HIGH_PATTERNS = [
    r"(?:don'?t|do not|doesn'?t) mind disruption",
    r"disruption is (?:fine|ok|okay|acceptable|not a problem)",
    r"(?:open|willing|ready) to (?:change|switch|disrupt)",
    r"(?:we can|can) handle disruption",
    r"disruption (?:is |)acceptable",
    r"comfortable with (?:change|disruption|switching)",
    r"not (?:worried|concerned) about disruption",
    r"high tolerance for (?:change|disruption)",
]

DISRUPTION_LOW_PATTERNS = [
    r"(?:avoid|minimize|limit|reduce) disruption",
    r"disruption (?:is |)(?:a problem|not acceptable|concerning|worrying)",
    r"(?:can'?t|cannot|don'?t want to) (?:disrupt|change)",
    r"stability is (?:important|critical|key|priority)",
    r"(?:need|want|prefer) continuity",
    r"low tolerance for (?:change|disruption)",
    r"risk of disruption (?:concerns|worries)",
    r"minimize (?:change|risk|disruption)",
]

# Risk Appetite Patterns
RISK_HIGH_PATTERNS = [
    r"(?:willing|open|ready) to take (?:risks|chances)",
    r"(?:high|aggressive) risk (?:appetite|tolerance)",
    r"risk is (?:fine|ok|acceptable|not a concern)",
    r"(?:can|let'?s) be (?:aggressive|bold)",
    r"not (?:worried|concerned) about risk",
    r"comfortable with (?:risk|uncertainty)",
]

RISK_LOW_PATTERNS = [
    r"(?:low|conservative) risk (?:appetite|tolerance)",
    r"(?:minimize|avoid|reduce|limit) risk",
    r"risk (?:averse|sensitive)",
    r"(?:play it safe|be conservative|be careful)",
    r"(?:can'?t|cannot) afford (?:risk|to fail)",
    r"low risk (?:approach|strategy|option)",
]

# Time Sensitivity Patterns
TIME_HIGH_PATTERNS = [
    r"(?:urgent|asap|immediately|right away|as soon as possible)",
    r"(?:time|speed) is (?:critical|important|of the essence)",
    r"(?:need|must|have to) (?:move|act|decide) (?:fast|quickly|soon)",
    r"(?:tight|short|aggressive) (?:timeline|deadline|schedule)",
    r"(?:can'?t|cannot) wait",
    r"(?:running out of|limited) time",
]

TIME_LOW_PATTERNS = [
    r"(?:no rush|take (?:our |)time|not urgent)",
    r"(?:plenty of|enough) time",
    r"time is (?:not critical|flexible|not a concern)",
    r"(?:can|we can) wait",
    r"thoroughness over speed",
    r"(?:prefer|want) a thorough (?:process|evaluation)",
]

# Stakeholder Alignment Patterns
STAKEHOLDER_REQUIRED_PATTERNS = [
    r"(?:need|must|have to|should) (?:align|check|consult) with",
    r"(?:stakeholder|management|leadership|executive|board) (?:alignment|approval|buy-?in)",
    r"(?:get|need|require) (?:sign-?off|approval) from",
    r"(?:category management|finance|legal|procurement) (?:needs to|must|should) (?:approve|agree|align)",
    r"(?:can'?t|cannot) proceed without (?:approval|alignment)",
]

# Budget Flexibility Patterns
BUDGET_FIXED_PATTERNS = [
    r"(?:fixed|hard|strict|firm) budget",
    r"budget is (?:set|fixed|non-?negotiable|not flexible)",
    r"(?:can'?t|cannot) (?:exceed|go over|increase) (?:the |)budget",
    r"(?:no|zero) budget flexibility",
    r"(?:stay|remain) within budget",
]

BUDGET_FLEXIBLE_PATTERNS = [
    r"(?:flexible|soft) budget",
    r"budget (?:is |)(?:flexible|negotiable)",
    r"(?:can|could|might) (?:adjust|increase|stretch) (?:the |)budget",
    r"(?:some|have) budget flexibility",
    r"if (?:it'?s |)justified,? (?:we |)(?:can|could) (?:spend|invest) more",
]

# Supplier Preference Patterns
PREFER_INCUMBENT_PATTERNS = [
    r"(?:prefer|favor|lean toward|stick with) (?:the |)(?:current|existing|incumbent) supplier",
    r"(?:relationship|history) with (?:current|existing) supplier (?:matters|is important)",
    r"(?:keep|maintain|continue with) (?:the |)(?:current|existing) supplier",
    r"incumbent (?:advantage|preference)",
    r"(?:don'?t|do not) want to switch",
]

PREFER_NEW_PATTERNS = [
    r"(?:open|willing|want|prefer|need) (?:to |)(?:switch|change|try|explore) (?:new |)suppliers?",
    r"(?:fresh|new) (?:perspective|options|alternatives)",
    r"(?:not|no) (?:committed|attached|loyal) to (?:current|existing|incumbent)",
    r"(?:time|ready) for (?:a |)change",
]

# Negotiation Posture Patterns
NEGOTIATION_COMPETITIVE_PATTERNS = [
    r"(?:hard|tough|aggressive) (?:bargaining|negotiation|stance|posture)",
    r"(?:push|squeeze) (?:them |the supplier |)(?:hard|aggressively)",
    r"(?:maximize|optimize) (?:leverage|savings|terms)",
    r"(?:we have|got) leverage",
    r"competitive (?:approach|posture|stance)",
]

NEGOTIATION_COLLABORATIVE_PATTERNS = [
    r"(?:collaborative|partnership|win-?win) (?:approach|posture|stance|relationship)",
    r"(?:maintain|preserve|protect) (?:the |)relationship",
    r"(?:long-?term|strategic) partnership",
    r"(?:don'?t|do not) want to (?:damage|harm|strain) (?:the |)relationship",
    r"relationship (?:matters|is important|comes first)",
]

# Priority Criteria Patterns  
PRIORITY_PRICE_PATTERNS = [
    r"(?:price|cost) is (?:king|priority|most important|#1|number one)",
    r"(?:focus|prioritize|emphasize) (?:on |)(?:price|cost|savings)",
    r"(?:lowest|best) price (?:wins|matters most)",
    r"cost (?:reduction|savings) is (?:critical|key|priority)",
]

PRIORITY_QUALITY_PATTERNS = [
    r"quality (?:is |)(?:king|priority|most important|comes first)",
    r"(?:focus|prioritize|emphasize) (?:on |)quality",
    r"(?:can'?t|cannot) compromise (?:on |)quality",
    r"quality over (?:price|cost)",
]

PRIORITY_RELIABILITY_PATTERNS = [
    r"reliability (?:is |)(?:critical|key|priority|most important)",
    r"(?:need|require) (?:reliable|dependable) supplier",
    r"(?:can'?t|cannot) afford (?:downtime|delays|outages)",
    r"(?:service|delivery) reliability (?:matters|is critical)",
]


class ConstraintExtractor:
    """
    Extracts binding constraints from user collaboration inputs.
    
    Uses rule-based pattern matching (no LLM).
    Only clear, unambiguous statements become constraints.
    """
    
    def extract_constraints(
        self,
        user_input: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> ExtractionResult:
        """
        Extract constraints from user input and update the constraints object.
        
        Args:
            user_input: The user's collaboration input
            dtp_stage: Current DTP stage
            constraints: ExecutionConstraints object to update
        
        Returns:
            ExtractionResult with extraction details and acknowledgments
        """
        text = user_input.lower()
        acknowledgments = []
        details = []
        
        # Extract disruption tolerance
        ack, detail = self._extract_disruption_tolerance(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract risk appetite
        ack, detail = self._extract_risk_appetite(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract time sensitivity
        ack, detail = self._extract_time_sensitivity(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract stakeholder alignment
        ack, detail = self._extract_stakeholder_alignment(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract budget flexibility
        ack, detail = self._extract_budget_flexibility(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract supplier preference
        ack, detail = self._extract_supplier_preference(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract negotiation posture
        ack, detail = self._extract_negotiation_posture(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract priority criteria
        ack, detail = self._extract_priority_criteria(text, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        # Extract excluded suppliers (specific names)
        ack, detail = self._extract_excluded_suppliers(user_input, dtp_stage, constraints)
        if ack:
            acknowledgments.append(ack)
            details.append(detail)
        
        return ExtractionResult(
            constraints_extracted=len(acknowledgments),
            acknowledgments=acknowledgments,
            constraint_details=details
        )
    
    def _match_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Check if text matches any of the patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern
        return None
    
    def _extract_disruption_tolerance(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract disruption tolerance constraint."""
        # Check for HIGH tolerance
        pattern = self._match_patterns(text, DISRUPTION_HIGH_PATTERNS)
        if pattern:
            constraints.disruption_tolerance = ToleranceLevel.HIGH
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Got it — disruption is acceptable, so I'll include more aggressive options in my analysis.",
                ("disruption_tolerance", "HIGH", pattern)
            )
        
        # Check for LOW tolerance
        pattern = self._match_patterns(text, DISRUPTION_LOW_PATTERNS)
        if pattern:
            constraints.disruption_tolerance = ToleranceLevel.LOW
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — minimizing disruption is a priority, so I'll favor lower-risk options.",
                ("disruption_tolerance", "LOW", pattern)
            )
        
        return None, None
    
    def _extract_risk_appetite(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract risk appetite constraint."""
        pattern = self._match_patterns(text, RISK_HIGH_PATTERNS)
        if pattern:
            constraints.risk_appetite = ToleranceLevel.HIGH
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Noted — you're comfortable with risk, so I'll consider bolder strategies.",
                ("risk_appetite", "HIGH", pattern)
            )
        
        pattern = self._match_patterns(text, RISK_LOW_PATTERNS)
        if pattern:
            constraints.risk_appetite = ToleranceLevel.LOW
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — I'll prioritize conservative, lower-risk approaches.",
                ("risk_appetite", "LOW", pattern)
            )
        
        return None, None
    
    def _extract_time_sensitivity(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract time sensitivity constraint."""
        pattern = self._match_patterns(text, TIME_HIGH_PATTERNS)
        if pattern:
            constraints.time_sensitivity = ToleranceLevel.HIGH
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Got it — speed is critical, so I'll prioritize faster paths forward.",
                ("time_sensitivity", "HIGH", pattern)
            )
        
        pattern = self._match_patterns(text, TIME_LOW_PATTERNS)
        if pattern:
            constraints.time_sensitivity = ToleranceLevel.LOW
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — we have time for a thorough process, so I'll favor completeness over speed.",
                ("time_sensitivity", "LOW", pattern)
            )
        
        return None, None
    
    def _extract_stakeholder_alignment(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract stakeholder alignment requirement."""
        pattern = self._match_patterns(text, STAKEHOLDER_REQUIRED_PATTERNS)
        if pattern:
            constraints.stakeholder_alignment_required = True
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Noted — stakeholder alignment is required, so I'll factor that into the timeline and approach.",
                ("stakeholder_alignment_required", "True", pattern)
            )
        
        return None, None
    
    def _extract_budget_flexibility(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract budget flexibility constraint."""
        pattern = self._match_patterns(text, BUDGET_FIXED_PATTERNS)
        if pattern:
            constraints.budget_flexibility = BudgetFlexibility.FIXED
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — the budget is fixed, so I'll only consider options within that limit.",
                ("budget_flexibility", "FIXED", pattern)
            )
        
        pattern = self._match_patterns(text, BUDGET_FLEXIBLE_PATTERNS)
        if pattern:
            constraints.budget_flexibility = BudgetFlexibility.FLEXIBLE
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Good to know — there's budget flexibility if justified, so I'll flag high-value options even if they cost more.",
                ("budget_flexibility", "FLEXIBLE", pattern)
            )
        
        return None, None
    
    def _extract_supplier_preference(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract supplier preference constraint."""
        pattern = self._match_patterns(text, PREFER_INCUMBENT_PATTERNS)
        if pattern:
            constraints.supplier_preference = SupplierPreference.PREFER_INCUMBENT
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — the relationship with the current supplier is important, so I'll weight continuity in my analysis.",
                ("supplier_preference", "PREFER_INCUMBENT", pattern)
            )
        
        pattern = self._match_patterns(text, PREFER_NEW_PATTERNS)
        if pattern:
            constraints.supplier_preference = SupplierPreference.PREFER_NEW
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Got it — you're open to new suppliers, so I'll cast a wider net in the evaluation.",
                ("supplier_preference", "PREFER_NEW", pattern)
            )
        
        return None, None
    
    def _extract_negotiation_posture(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract negotiation posture constraint."""
        pattern = self._match_patterns(text, NEGOTIATION_COMPETITIVE_PATTERNS)
        if pattern:
            constraints.negotiation_posture = NegotiationPosture.COMPETITIVE
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Noted — I'll structure the negotiation strategy aggressively to maximize leverage.",
                ("negotiation_posture", "COMPETITIVE", pattern)
            )
        
        pattern = self._match_patterns(text, NEGOTIATION_COLLABORATIVE_PATTERNS)
        if pattern:
            constraints.negotiation_posture = NegotiationPosture.COLLABORATIVE
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — I'll prioritize relationship preservation in the negotiation approach.",
                ("negotiation_posture", "COLLABORATIVE", pattern)
            )
        
        return None, None
    
    def _extract_priority_criteria(
        self,
        text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract priority criteria constraint."""
        pattern = self._match_patterns(text, PRIORITY_PRICE_PATTERNS)
        if pattern:
            if "price" not in constraints.priority_criteria:
                constraints.priority_criteria.append("price")
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Got it — cost/price is the top priority, so I'll weight that heavily in the evaluation.",
                ("priority_criteria", "price", pattern)
            )
        
        pattern = self._match_patterns(text, PRIORITY_QUALITY_PATTERNS)
        if pattern:
            if "quality" not in constraints.priority_criteria:
                constraints.priority_criteria.append("quality")
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Understood — quality is the priority, so I'll emphasize that over cost savings.",
                ("priority_criteria", "quality", pattern)
            )
        
        pattern = self._match_patterns(text, PRIORITY_RELIABILITY_PATTERNS)
        if pattern:
            if "reliability" not in constraints.priority_criteria:
                constraints.priority_criteria.append("reliability")
            constraints.record_constraint(text, dtp_stage, pattern)
            return (
                "Noted — reliability is critical, so I'll prioritize suppliers with strong track records.",
                ("priority_criteria", "reliability", pattern)
            )
        
        return None, None
    
    def _extract_excluded_suppliers(
        self,
        original_text: str,
        dtp_stage: str,
        constraints: ExecutionConstraints
    ) -> Tuple[Optional[str], Optional[Tuple[str, str, str]]]:
        """Extract explicitly excluded suppliers."""
        text = original_text.lower()
        
        # Patterns for exclusion
        exclusion_patterns = [
            r"(?:exclude|remove|don'?t (?:include|consider)|not (?:interested in|consider)) (?:supplier |)([A-Za-z0-9\s]+?)(?:\.|,|$| from)",
            r"(?:no|never|avoid) (?:supplier |)([A-Za-z0-9\s]+?)(?:\.|,|$| )",
        ]
        
        for pattern in exclusion_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                supplier_name = match.group(1).strip()
                if len(supplier_name) > 2 and supplier_name not in constraints.excluded_suppliers:
                    constraints.excluded_suppliers.append(supplier_name)
                    constraints.record_constraint(original_text, dtp_stage, pattern)
                    return (
                        f"Noted — I'll exclude **{supplier_name}** from consideration.",
                        ("excluded_suppliers", supplier_name, pattern)
                    )
        
        return None, None


# Singleton instance
_constraint_extractor: Optional[ConstraintExtractor] = None


def get_constraint_extractor() -> ConstraintExtractor:
    """Get or create the constraint extractor singleton."""
    global _constraint_extractor
    if _constraint_extractor is None:
        _constraint_extractor = ConstraintExtractor()
    return _constraint_extractor


def generate_constraint_acknowledgment(result: ExtractionResult) -> str:
    """
    Generate a natural, human-like acknowledgment of extracted constraints.
    
    This acknowledgment MUST happen immediately after extraction.
    It builds trust by showing the user their input was heard.
    """
    if not result.acknowledgments:
        return ""
    
    if len(result.acknowledgments) == 1:
        return result.acknowledgments[0]
    
    # Multiple constraints - combine naturally
    combined = "**I've noted several things from what you said:**\n\n"
    combined += "\n".join(f"• {ack}" for ack in result.acknowledgments)
    combined += "\n\n_These will shape my analysis going forward._"
    
    return combined
