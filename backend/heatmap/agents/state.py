from typing import TypedDict, List, Dict, Any, Optional, NotRequired, Required

class ContractData(TypedDict, total=False):
    contract_id: Optional[str]
    request_id: Optional[str]
    supplier_name: Optional[str]
    category: Required[str]
    subcategory: Optional[str]
    spend_data: List[Dict[str, Any]]
    contract_details: NotRequired[Dict[str, Any]]
    metrics_data: Optional[Dict[str, Any]]
    estimated_spend_usd: NotRequired[float]
    implementation_timeline_months: NotRequired[float]
    preferred_supplier_status: NotRequired[str]
    category_strategy: NotRequired[Dict[str, Any]]

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

class HeatmapState(TypedDict, total=False):
    run_id: str
    weights: Dict[str, float]
    heatmap_context: Dict[str, Any]
    contracts: Required[List[ContractData]]
    current_index: Required[int]
    spend_signals: Required[List[SpendSignal]]
    contract_signals: Required[List[ContractSignal]]
    strategy_signals: Required[List[StrategySignal]]
    risk_signals: Required[List[RiskSignal]]
    scored_opportunities: Required[List[ScoredOpportunity]]
    errors: List[str]
