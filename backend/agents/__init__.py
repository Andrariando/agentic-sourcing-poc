"""
Backend agents module.
UNIFIED SOURCE OF TRUTH: All agents now point to the advanced root-level implementations.

OFFICIAL AGENTS (7 first-class agents):
1) Supervisor Agent - Orchestrates workflow, validates inputs
2) Sourcing Signal Agent - Monitors for sourcing opportunities
3) Supplier Scoring Agent - Evaluates and ranks suppliers
4) RFx Draft Agent - Assembles RFx documents
5) Negotiation Support Agent - Provides negotiation insights
6) Contract Support Agent - Extracts terms, prepares handoff
7) Implementation Agent - Rollout planning and value capture
"""
# Unified exports from root agents folder
# This ensures ChatService and LangGraph use the IDENTICAL classes and logic
from agents.supervisor import SupervisorAgent
from agents.signal_agent import SignalInterpretationAgent as SourcingSignalAgent
from agents.supplier_agent import SupplierEvaluationAgent as SupplierScoringAgent
from agents.rfx_draft_agent import RFxDraftAgent as RfxDraftAgent
from agents.negotiation_agent import NegotiationSupportAgent
from agents.contract_support_agent import ContractSupportAgent
from agents.implementation_agent import ImplementationAgent

# Legacy/Alternative logic for backward compatibility
from agents.strategy_agent import StrategyAgent
from agents.supplier_agent import SupplierEvaluationAgent
from agents.negotiation_agent import NegotiationSupportAgent as NegotiationAgent
from agents.signal_agent import SignalInterpretationAgent as SignalAgent
from agents.base_agent import BaseAgent

__all__ = [
    # Official agents
    "SupervisorAgent",
    "SourcingSignalAgent",
    "SupplierScoringAgent",
    "RfxDraftAgent",
    "NegotiationSupportAgent",
    "ContractSupportAgent",
    "ImplementationAgent",
    # Legacy/Mapping
    "BaseAgent",
    "StrategyAgent",
    "SupplierEvaluationAgent",
    "NegotiationAgent",
    "SignalAgent",
]
