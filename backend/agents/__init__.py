"""
Backend agents module.

OFFICIAL AGENTS (7 first-class agents):
1) Supervisor Agent - Orchestrates workflow, validates inputs
2) Sourcing Signal Agent - Monitors for sourcing opportunities
3) Supplier Scoring Agent - Evaluates and ranks suppliers
4) RFx Draft Agent - Assembles RFx documents
5) Negotiation Support Agent - Provides negotiation insights
6) Contract Support Agent - Extracts terms, prepares handoff
7) Implementation Agent - Rollout planning and value capture
"""
# New official agents
from backend.agents.supervisor_agent import SupervisorAgent
from backend.agents.sourcing_signal_agent import SourcingSignalAgent
from backend.agents.supplier_scoring_agent import SupplierScoringAgent
from backend.agents.rfx_draft_agent import RfxDraftAgent
from backend.agents.negotiation_support_agent import NegotiationSupportAgent
from backend.agents.contract_support_agent import ContractSupportAgent
from backend.agents.implementation_agent import ImplementationAgent

# Legacy imports for backward compatibility
from backend.agents.base import BaseAgent
from backend.agents.strategy import StrategyAgent
from backend.agents.supplier_eval import SupplierEvaluationAgent
from backend.agents.negotiation import NegotiationAgent
from backend.agents.signal import SignalAgent

__all__ = [
    # Official agents
    "SupervisorAgent",
    "SourcingSignalAgent",
    "SupplierScoringAgent",
    "RfxDraftAgent",
    "NegotiationSupportAgent",
    "ContractSupportAgent",
    "ImplementationAgent",
    # Legacy
    "BaseAgent",
    "StrategyAgent",
    "SupplierEvaluationAgent",
    "NegotiationAgent",
    "SignalAgent",
]
