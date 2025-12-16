"""
Signal Aggregation Layer - Proactive scanning for renewal & savings opportunities.

This module scans contracts and supplier performance data to identify:
- Contract expiration windows (< 90 days)
- Performance degradation (SLA, quality, delivery)
- Spend anomalies or missed savings opportunities

Outputs CaseTrigger objects for Supervisor to create proactive cases.
"""
from typing import List, Dict, Any, Optional
from utils.schemas import CaseTrigger
from utils.data_loader import (
    load_json_data, get_contract, get_performance, 
    get_suppliers_by_category, get_market_data
)
from datetime import datetime, timedelta


class SignalAggregator:
    """
    Aggregates signals across contracts and suppliers to generate proactive case triggers.
    """
    
    def __init__(self):
        self.renewal_window_days = 90  # Contracts expiring within 90 days
        self.performance_threshold = 6.0  # Performance score below this triggers review
        self.spend_anomaly_threshold = 0.15  # 15% variance from expected spend
    
    def scan_for_renewals(self) -> List[CaseTrigger]:
        """
        Scan contracts for upcoming renewals.
        Returns list of CaseTrigger objects for contracts expiring soon.
        """
        triggers = []
        contracts = load_json_data("contracts.json")
        
        for contract in contracts:
            expiry_days = contract.get("expiry_days", 999)
            
            # Check if contract is expiring within renewal window
            if expiry_days <= self.renewal_window_days:
                # Determine urgency
                if expiry_days <= 30:
                    urgency = "High"
                elif expiry_days <= 60:
                    urgency = "Medium"
                else:
                    urgency = "Low"
                
                # Get performance data to assess risk
                supplier_id = contract.get("supplier_id")
                performance = None
                if supplier_id:
                    performance = get_performance(supplier_id)
                
                # Build triggering signals list
                triggering_signals = [
                    f"Contract {contract['contract_id']} expiring in {expiry_days} days"
                ]
                
                if performance:
                    perf_score = performance.get("overall_score", 0)
                    perf_trend = performance.get("trend", "")
                    
                    if perf_score < self.performance_threshold:
                        triggering_signals.append(f"Performance below threshold (score: {perf_score:.1f})")
                    
                    if perf_trend == "declining":
                        triggering_signals.append("Performance trend: declining")
                
                trigger = CaseTrigger(
                    trigger_type="Renewal",
                    category_id=contract.get("category_id", ""),
                    supplier_id=supplier_id,
                    contract_id=contract.get("contract_id"),
                    urgency=urgency,
                    triggering_signals=triggering_signals,
                    recommended_entry_stage="DTP-01",
                    metadata={
                        "expiry_days": expiry_days,
                        "annual_value_usd": contract.get("annual_value_usd", 0),
                        "performance_score": performance.get("overall_score") if performance else None,
                        "performance_trend": performance.get("trend") if performance else None
                    }
                )
                triggers.append(trigger)
        
        return triggers
    
    def scan_for_savings_opportunities(self) -> List[CaseTrigger]:
        """
        Scan for savings opportunities (spend anomalies, market shifts).
        Returns list of CaseTrigger objects for potential savings cases.
        """
        triggers = []
        contracts = load_json_data("contracts.json")
        
        for contract in contracts:
            category_id = contract.get("category_id")
            if not category_id:
                continue
            
            # Get market data for comparison
            market = get_market_data(category_id)
            if not market:
                continue
            
            # Check for spend anomalies
            contract_value = contract.get("annual_value_usd", 0)
            market_benchmark = market.get("average_annual_value", 0)
            
            if market_benchmark > 0:
                variance = abs(contract_value - market_benchmark) / market_benchmark
                
                if variance > self.spend_anomaly_threshold:
                    urgency = "Medium" if variance > 0.25 else "Low"
                    
                    trigger = CaseTrigger(
                        trigger_type="Savings",
                        category_id=category_id,
                        supplier_id=contract.get("supplier_id"),
                        contract_id=contract.get("contract_id"),
                        urgency=urgency,
                        triggering_signals=[
                            f"Spend variance: {variance:.1%} from market benchmark",
                            f"Contract value: ${contract_value:,.0f} vs benchmark: ${market_benchmark:,.0f}"
                        ],
                        recommended_entry_stage="DTP-01",
                        metadata={
                            "contract_value": contract_value,
                            "market_benchmark": market_benchmark,
                            "variance_percent": variance
                        }
                    )
                    triggers.append(trigger)
        
        return triggers
    
    def scan_for_risk_signals(self) -> List[CaseTrigger]:
        """
        Scan for risk signals (performance degradation, compliance issues).
        Returns list of CaseTrigger objects for risk cases.
        """
        triggers = []
        suppliers = load_json_data("suppliers.json")
        performance_data = load_json_data("performance.json")
        
        # Create performance lookup
        perf_by_supplier = {p["supplier_id"]: p for p in performance_data}
        
        for supplier in suppliers:
            supplier_id = supplier.get("supplier_id")
            if not supplier_id:
                continue
            
            performance = perf_by_supplier.get(supplier_id)
            if not performance:
                continue
            
            perf_score = performance.get("overall_score", 0)
            perf_trend = performance.get("trend", "")
            incidents = performance.get("incidents", [])
            
            # Check for significant performance issues
            if perf_score < 5.0 or (perf_trend == "declining" and perf_score < 6.0):
                urgency = "High" if perf_score < 5.0 else "Medium"
                
                triggering_signals = [
                    f"Performance score: {perf_score:.1f} (below threshold)",
                    f"Performance trend: {perf_trend}"
                ]
                
                if len(incidents) > 2:
                    triggering_signals.append(f"Multiple incidents: {len(incidents)}")
                
                # Get contracts for this supplier
                contracts = load_json_data("contracts.json")
                supplier_contracts = [c for c in contracts if c.get("supplier_id") == supplier_id]
                
                for contract in supplier_contracts:
                    trigger = CaseTrigger(
                        trigger_type="Risk",
                        category_id=contract.get("category_id", supplier.get("category_id", "")),
                        supplier_id=supplier_id,
                        contract_id=contract.get("contract_id"),
                        urgency=urgency,
                        triggering_signals=triggering_signals,
                        recommended_entry_stage="DTP-01",
                        metadata={
                            "performance_score": perf_score,
                            "performance_trend": perf_trend,
                            "incident_count": len(incidents),
                            "contract_value": contract.get("annual_value_usd", 0)
                        }
                    )
                    triggers.append(trigger)
        
        return triggers
    
    def aggregate_all_signals(self) -> List[CaseTrigger]:
        """
        Aggregate all signal types and return comprehensive list of case triggers.
        This is the main entry point for proactive scanning.
        """
        all_triggers = []
        
        # Scan for renewals
        renewal_triggers = self.scan_for_renewals()
        all_triggers.extend(renewal_triggers)
        
        # Scan for savings opportunities
        savings_triggers = self.scan_for_savings_opportunities()
        all_triggers.extend(savings_triggers)
        
        # Scan for risk signals
        risk_triggers = self.scan_for_risk_signals()
        all_triggers.extend(risk_triggers)
        
        # Sort by urgency (High -> Medium -> Low)
        urgency_order = {"High": 0, "Medium": 1, "Low": 2}
        all_triggers.sort(key=lambda t: urgency_order.get(t.urgency, 3))
        
        return all_triggers
    
    def create_case_from_trigger(self, trigger: CaseTrigger, existing_case_ids: List[str]) -> Optional[Dict[str, Any]]:
        """
        Convert a CaseTrigger into a case creation payload.
        Returns None if case already exists for this trigger.
        """
        # Check if case already exists for this contract/supplier combination
        # This prevents duplicate proactive cases
        for case_id in existing_case_ids:
            # Simple check - in production, would query case database
            if trigger.contract_id and case_id.endswith(trigger.contract_id[-3:]):
                return None  # Case likely exists
        
        # Generate case summary text
        summary_parts = [f"{trigger.trigger_type} opportunity detected"]
        if trigger.contract_id:
            summary_parts.append(f"Contract: {trigger.contract_id}")
        if trigger.supplier_id:
            summary_parts.append(f"Supplier: {trigger.supplier_id}")
        summary_parts.append(f"Urgency: {trigger.urgency}")
        
        return {
            "category_id": trigger.category_id,
            "contract_id": trigger.contract_id,
            "supplier_id": trigger.supplier_id,
            "trigger_source": "System",  # Proactive system-initiated
            "trigger_type": trigger.trigger_type,
            "urgency": trigger.urgency,
            "triggering_signals": trigger.triggering_signals,
            "summary_text": " | ".join(summary_parts),
            "metadata": trigger.metadata
        }
