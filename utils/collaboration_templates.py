"""
DTP-Specific Collaboration Templates.

Provides stage-aware collaboration prompts, questions, and framing.
Each DTP stage has its own collaboration focus and question types.

Design Principles:
- Not via agent prompts (separate from agent logic)
- Frames options without recommendation
- Asks clarifying questions appropriate to the DTP stage
- First-person, collaborative tone ("Let's think this through...")
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class CollaborationTemplate:
    """Template for DTP-specific collaboration."""
    stage: str
    stage_name: str
    focus_areas: List[str]
    clarifying_questions: List[str]
    tradeoff_prompts: List[str]
    option_framing: str
    transition_prompt: str


# DTP-01: Strategy - Focus on strategy framing, risk tolerance
DTP_01_TEMPLATE = CollaborationTemplate(
    stage="DTP-01",
    stage_name="Strategy",
    focus_areas=[
        "Sourcing strategy direction",
        "Risk tolerance and appetite",
        "Business priorities and constraints",
        "Market dynamics and timing",
    ],
    clarifying_questions=[
        "What's driving the urgency here — is it cost pressure, service issues, or contract timing?",
        "How much disruption are you comfortable with if we pursue a competitive approach?",
        "Are there any internal stakeholders whose preferences we should factor in early?",
        "What would success look like for you in this sourcing decision?",
        "Is maintaining the current supplier relationship important, or are we open to change?",
        "What's your risk appetite here — conservative, moderate, or aggressive?",
    ],
    tradeoff_prompts=[
        "There's often a tension between speed and thoroughness. Which matters more right now?",
        "We could optimize for cost savings or relationship continuity — these sometimes pull in different directions.",
        "A competitive RFx might get better pricing but takes longer. A direct renewal is faster but may leave value on the table.",
        "The incumbent knows your business well, but fresh competition could surface better options.",
    ],
    option_framing=(
        "At this stage, we're shaping the overall approach. There are typically a few paths: "
        "renewing with the current supplier, renegotiating terms, running a competitive process, "
        "or in some cases, consolidating or exiting the category entirely. "
        "Each has different risk/reward profiles."
    ),
    transition_prompt=(
        "Once we've aligned on the strategic direction and key priorities, "
        "I can run the analysis and provide a formal recommendation. Want me to do that now?"
    ),
)

# DTP-02: Planning - Focus on evaluation criteria, weighting
DTP_02_TEMPLATE = CollaborationTemplate(
    stage="DTP-02",
    stage_name="Planning",
    focus_areas=[
        "Evaluation criteria definition",
        "Criteria weighting and priorities",
        "Requirements clarity",
        "Market approach planning",
    ],
    clarifying_questions=[
        "When evaluating suppliers, what matters most — price, quality, reliability, or something else?",
        "Are there any must-have requirements that would disqualify a supplier if missing?",
        "How should we weight the different evaluation factors? Is cost king, or are other factors equally important?",
        "Are there specific capabilities or certifications we need to require?",
        "What's the timeline pressure here — do we have room for a thorough evaluation?",
        "Should we consider regional suppliers, or is global reach required?",
    ],
    tradeoff_prompts=[
        "Stricter requirements give us better fit but may limit our options. How selective should we be?",
        "We can weight heavily on price, but that might favor suppliers who cut corners elsewhere.",
        "A longer evaluation gives better data but delays the decision. What's the right balance?",
        "Including more evaluation criteria is thorough but can make the decision more complex.",
    ],
    option_framing=(
        "In the planning phase, we're defining what 'good' looks like. "
        "This includes the evaluation criteria, their relative weights, and any hard requirements. "
        "Getting this right shapes everything downstream."
    ),
    transition_prompt=(
        "Once we're aligned on the evaluation framework, "
        "I can evaluate the available suppliers against these criteria. Ready for me to proceed?"
    ),
)

# DTP-03: Sourcing - Focus on supplier evaluation, market scan
DTP_03_TEMPLATE = CollaborationTemplate(
    stage="DTP-03",
    stage_name="Sourcing",
    focus_areas=[
        "Supplier identification and screening",
        "Market scan completeness",
        "Preliminary evaluation",
        "Shortlist development",
    ],
    clarifying_questions=[
        "Are there any suppliers you'd specifically like included or excluded from consideration?",
        "How important is incumbent advantage — should we give extra weight to known quantities?",
        "Should we cast a wide net or focus on a targeted shortlist?",
        "Are there any emerging suppliers or market entrants we should be aware of?",
        "How much do we value innovation versus proven track record?",
        "Is geographic proximity or local presence a factor?",
    ],
    tradeoff_prompts=[
        "A larger shortlist gives more options but requires more evaluation effort.",
        "Newer suppliers might offer innovation but carry more execution risk.",
        "The incumbent has relationship value but may not offer the best terms.",
        "Focusing on tier-1 suppliers is safer but may miss value from smaller players.",
    ],
    option_framing=(
        "We're now looking at the actual supplier landscape. "
        "I can provide a structured comparison of qualified suppliers, "
        "highlighting their strengths, concerns, and how they score against our criteria. "
        "The final selection will be yours."
    ),
    transition_prompt=(
        "I have the data ready to evaluate and score the suppliers. "
        "Would you like me to run the analysis and present a structured comparison?"
    ),
)

# DTP-04: Negotiation - Focus on negotiation posture, flexibility
DTP_04_TEMPLATE = CollaborationTemplate(
    stage="DTP-04",
    stage_name="Negotiation",
    focus_areas=[
        "Negotiation strategy and posture",
        "Leverage points identification",
        "Flexibility boundaries",
        "BATNA and walkaway positions",
    ],
    clarifying_questions=[
        "How aggressive should our negotiation posture be — collaborative partnership or hard bargaining?",
        "What are your absolute must-haves versus nice-to-haves in the negotiation?",
        "Is there flexibility on price if we get better terms elsewhere (payment, SLAs, etc.)?",
        "What's our walkaway point — at what terms would you rather restart the process?",
        "Are there relationship considerations that should temper our approach?",
        "How important is a long-term partnership versus optimizing this single deal?",
    ],
    tradeoff_prompts=[
        "Pushing hard on price might strain the relationship. How much relationship capital are we willing to spend?",
        "We can lock in better rates now versus building in flexibility for the future.",
        "A longer contract gets better pricing but reduces our ability to adapt.",
        "Aggressive terms might win this negotiation but affect future dealings.",
    ],
    option_framing=(
        "As we enter negotiation, we need to define our posture and boundaries. "
        "I can identify leverage points, suggest target terms, and outline fallback positions. "
        "But the negotiation style — collaborative versus competitive — is a strategic choice."
    ),
    transition_prompt=(
        "I can prepare a detailed negotiation plan with target terms and leverage points. "
        "Want me to put that together for your review?"
    ),
)

# DTP-05: Contracting - Focus on implementation risk, timing
DTP_05_TEMPLATE = CollaborationTemplate(
    stage="DTP-05",
    stage_name="Contracting",
    focus_areas=[
        "Contract terms validation",
        "Implementation risk assessment",
        "Transition planning",
        "Compliance and governance",
    ],
    clarifying_questions=[
        "Are there any contract terms that require special attention or legal review?",
        "What's your comfort level with the implementation timeline being proposed?",
        "Are there specific risks in the transition we should build protections for?",
        "Do we need any special provisions for performance guarantees or penalties?",
        "How should we handle disputes if they arise during the contract period?",
        "Are there compliance or regulatory requirements we need to explicitly address?",
    ],
    tradeoff_prompts=[
        "Tighter SLAs give us protection but may come with higher costs.",
        "Longer payment terms help cash flow but the supplier may price that in.",
        "More detailed contract terms reduce ambiguity but can slow down finalization.",
        "Aggressive penalties protect us but may affect supplier motivation.",
    ],
    option_framing=(
        "We're at the contracting stage where terms become binding. "
        "I can extract and validate the key terms against our standards, "
        "flag any inconsistencies, and highlight areas that may need negotiation or legal review."
    ),
    transition_prompt=(
        "I can analyze the contract terms and prepare a structured extraction for review. "
        "Should I proceed with that analysis?"
    ),
)

# DTP-06: Execution - Focus on value realization, monitoring
DTP_06_TEMPLATE = CollaborationTemplate(
    stage="DTP-06",
    stage_name="Execution",
    focus_areas=[
        "Implementation rollout",
        "Value realization tracking",
        "Performance monitoring",
        "Continuous improvement",
    ],
    clarifying_questions=[
        "What's the most critical metric for measuring success in this implementation?",
        "How frequently should we review performance — monthly, quarterly?",
        "Are there early warning indicators we should watch for?",
        "Who should be the primary contact for escalations?",
        "What would trigger a contract review or renegotiation?",
        "How should we document and share learnings from this process?",
    ],
    tradeoff_prompts=[
        "More frequent monitoring catches issues early but requires more effort.",
        "Tight KPIs keep the supplier accountable but may strain the relationship.",
        "Detailed tracking gives visibility but adds administrative overhead.",
        "Quick escalation protects us but may not give the supplier room to course-correct.",
    ],
    option_framing=(
        "We're now in execution mode — the contract is live and it's about delivering value. "
        "I can help structure the monitoring approach, track savings realization, "
        "and flag any early warning signs."
    ),
    transition_prompt=(
        "I can create an implementation plan with rollout steps and monitoring KPIs. "
        "Would you like me to prepare that now?"
    ),
)

# Template registry
DTP_TEMPLATES: Dict[str, CollaborationTemplate] = {
    "DTP-01": DTP_01_TEMPLATE,
    "DTP-02": DTP_02_TEMPLATE,
    "DTP-03": DTP_03_TEMPLATE,
    "DTP-04": DTP_04_TEMPLATE,
    "DTP-05": DTP_05_TEMPLATE,
    "DTP-06": DTP_06_TEMPLATE,
}


def get_collaboration_template(dtp_stage: str) -> CollaborationTemplate:
    """Get the collaboration template for a DTP stage."""
    return DTP_TEMPLATES.get(dtp_stage, DTP_01_TEMPLATE)


def get_stage_questions(dtp_stage: str, count: int = 2) -> List[str]:
    """Get clarifying questions for a DTP stage."""
    template = get_collaboration_template(dtp_stage)
    return template.clarifying_questions[:count]


def get_stage_tradeoffs(dtp_stage: str, count: int = 2) -> List[str]:
    """Get tradeoff prompts for a DTP stage."""
    template = get_collaboration_template(dtp_stage)
    return template.tradeoff_prompts[:count]


def get_option_framing(dtp_stage: str) -> str:
    """Get option framing text for a DTP stage."""
    template = get_collaboration_template(dtp_stage)
    return template.option_framing


def get_transition_prompt(dtp_stage: str) -> str:
    """Get the transition-to-execution prompt for a DTP stage."""
    template = get_collaboration_template(dtp_stage)
    return template.transition_prompt


