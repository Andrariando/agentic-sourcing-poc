"""
DTP Stage definitions with human-readable names.
"""
DTP_STAGE_NAMES = {
    "DTP-01": "Strategy",
    "DTP-02": "Planning",
    "DTP-03": "Sourcing",
    "DTP-04": "Negotiation",
    "DTP-05": "Contracting",
    "DTP-06": "Execution"
}

DTP_STAGE_DESCRIPTIONS = {
    "DTP-01": "Strategy - Define sourcing strategy and approach",
    "DTP-02": "Planning - Develop sourcing plan and requirements",
    "DTP-03": "Sourcing - Identify and evaluate suppliers",
    "DTP-04": "Negotiation - Negotiate terms and pricing",
    "DTP-05": "Contracting - Finalize contract terms",
    "DTP-06": "Execution - Manage contract execution"
}


def get_dtp_stage_display(dtp_stage: str) -> str:
    """Get human-readable DTP stage name"""
    return DTP_STAGE_NAMES.get(dtp_stage, dtp_stage)


def get_dtp_stage_full(dtp_stage: str) -> str:
    """Get full DTP stage description"""
    return DTP_STAGE_DESCRIPTIONS.get(dtp_stage, dtp_stage)










