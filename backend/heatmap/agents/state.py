from typing import TypedDict, List, Dict, Any, Optional

class ContractData(TypedDict):
    contract_id: Optional[str]
    request_id: Optional[str]
    supplier_name: Optional[str]
    category: str
    subcategory: Optional[str]
    spend_data: List[Dict[str, Any]]
    contract_details: Optional[Dict[str, Any]]
    metrics_data: Optional[Dict[str, Any]]

class SpendSignal(TypedDict):
    fis_score: Optional[float]
    es_score: Optional[float]
    scs_score: Optional[float]
    csis_score: Optional[float]
    evidence: str

class ContractSignal(TypedDict):
    eus_score: Optional[float]
    ius_score: Optional[float]
    action_window: Optional[str]
    evidence: str

class StrategySignal(TypedDict):
    sas_score: Optional[float]
    evidence: str

class RiskSignal(TypedDict):
    rss_score: Optional[float]
    evidence: str

class ScoredOpportunity(TypedDict):
    contract_id: Optional[str]
    request_id: Optional[str]
    supplier_name: Optional[str]
    category: str
    subcategory: Optional[str]
    
    eus_score: Optional[float]
    ius_score: Optional[float]
    fis_score: Optional[float]
    es_score: Optional[float]
    rss_score: Optional[float]
    scs_score: Optional[float]
    csis_score: Optional[float]
    sas_score: Optional[float]
    
    total_score: float
    tier: str
    action_window: Optional[str]
    justification_summary: str

class HeatmapState(TypedDict):
    run_id: str
    weights: Dict[str, float]
    
    # Input
    contracts: List[ContractData]
    
    # Internal Tracking (index aligns with contracts)
    current_index: int
    spend_signals: List[SpendSignal]
    contract_signals: List[ContractSignal]
    strategy_signals: List[StrategySignal]
    risk_signals: List[RiskSignal]
    
    # Output
    scored_opportunities: List[ScoredOpportunity]
    errors: List[str]
