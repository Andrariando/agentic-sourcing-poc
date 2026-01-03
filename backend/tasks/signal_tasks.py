"""
Signal tasks for Sourcing Signal Agent.

Purpose: Monitor contract metadata, spend patterns, supplier performance,
and approved external signals to proactively identify sourcing cases.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlmodel import select

from backend.tasks.base_task import BaseTask, TaskResult
from backend.persistence.database import get_db_session
from backend.persistence.models import SupplierPerformance, SpendMetric, SLAEvent
from shared.schemas import GroundingReference


class DetectContractExpiryTask(BaseTask):
    """Detect contracts expiring soon from SQLite contract data."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define expiry thresholds."""
        return {
            "data": {
                "urgent_threshold_days": 30,
                "warning_threshold_days": 90,
            },
            "grounded_in": []
        }
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Query contracts from database."""
        session = get_db_session()
        grounded_in = []
        
        # Check for contracts in case state data or retrieve from context
        contracts = context.get("contracts", [])
        
        # If no contracts in context, we simulate with case data
        category_id = context.get("category_id")
        supplier_id = context.get("supplier_id")
        
        # Simulated contract data for demo (will be replaced by actual DB query)
        if not contracts:
            contracts = [{
                "contract_id": context.get("contract_id", "CTR-001"),
                "supplier_id": supplier_id or "SUP-001",
                "category_id": category_id or "IT_SERVICES",
                "end_date": (datetime.now() + timedelta(days=35)).isoformat(),
                "annual_value": 500000,
            }]
        
        session.close()
        
        return {
            "data": {"contracts": contracts},
            "grounded_in": grounded_in
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any], 
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze contracts for expiry signals."""
        contracts = retrieval_result.get("data", {}).get("contracts", [])
        urgent_days = rules_result.get("data", {}).get("urgent_threshold_days", 30)
        warning_days = rules_result.get("data", {}).get("warning_threshold_days", 90)
        
        signals = []
        now = datetime.now()
        
        for contract in contracts:
            end_date_str = contract.get("end_date")
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    if end_date.tzinfo:
                        end_date = end_date.replace(tzinfo=None)
                    days_until = (end_date - now).days
                    
                    if days_until <= urgent_days:
                        signals.append({
                            "signal_type": "contract_expiry",
                            "severity": "high",
                            "contract_id": contract.get("contract_id"),
                            "days_until_expiry": days_until,
                            "annual_value": contract.get("annual_value", 0),
                            "message": f"Contract expires in {days_until} days",
                        })
                    elif days_until <= warning_days:
                        signals.append({
                            "signal_type": "contract_expiry",
                            "severity": "medium",
                            "contract_id": contract.get("contract_id"),
                            "days_until_expiry": days_until,
                            "annual_value": contract.get("annual_value", 0),
                            "message": f"Contract expires in {days_until} days",
                        })
                except (ValueError, TypeError):
                    pass
        
        return {
            "data": {"expiry_signals": signals},
            "grounded_in": [
                GroundingReference(
                    ref_id=s["contract_id"],
                    ref_type="contract",
                    source_name=f"Contract {s['contract_id']}"
                ) for s in signals
            ]
        }


class DetectPerformanceDegradationTask(BaseTask):
    """Detect supplier performance degradation signals."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Pull supplier performance data."""
        session = get_db_session()
        supplier_id = context.get("supplier_id")
        
        grounded_in = []
        records = []
        
        if supplier_id:
            query = select(SupplierPerformance).where(
                SupplierPerformance.supplier_id == supplier_id
            ).order_by(SupplierPerformance.measurement_date.desc()).limit(10)
            
            results = session.exec(query).all()
            for r in results:
                records.append({
                    "record_id": r.record_id,
                    "overall_score": r.overall_score,
                    "quality_score": r.quality_score,
                    "delivery_score": r.delivery_score,
                    "trend": r.trend,
                    "risk_level": r.risk_level,
                    "measurement_date": r.measurement_date,
                })
                grounded_in.append(GroundingReference(
                    ref_id=r.record_id,
                    ref_type="structured_data",
                    source_name="supplier_performance"
                ))
        
        session.close()
        
        return {
            "data": {"performance_records": records},
            "grounded_in": grounded_in
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance for degradation signals."""
        records = retrieval_result.get("data", {}).get("performance_records", [])
        
        signals = []
        
        for record in records:
            if record.get("trend") == "declining":
                signals.append({
                    "signal_type": "performance_degradation",
                    "severity": "medium",
                    "supplier_id": context.get("supplier_id"),
                    "metric": "overall_score",
                    "current_value": record.get("overall_score"),
                    "message": f"Supplier performance declining (score: {record.get('overall_score', 0):.1f})",
                })
            
            if record.get("risk_level") in ["high", "critical"]:
                signals.append({
                    "signal_type": "risk_alert",
                    "severity": "high",
                    "supplier_id": context.get("supplier_id"),
                    "risk_level": record.get("risk_level"),
                    "message": f"Supplier at {record.get('risk_level')} risk level",
                })
        
        return {
            "data": {"performance_signals": signals},
            "grounded_in": []
        }


class DetectSpendAnomaliesTask(BaseTask):
    """Detect spend pattern anomalies."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Pull spend data."""
        session = get_db_session()
        supplier_id = context.get("supplier_id")
        category_id = context.get("category_id")
        
        query = select(SpendMetric)
        if supplier_id:
            query = query.where(SpendMetric.supplier_id == supplier_id)
        if category_id:
            query = query.where(SpendMetric.category_id == category_id)
        
        results = session.exec(query).all()
        records = [
            {
                "record_id": r.record_id,
                "spend_amount": r.spend_amount,
                "budget_amount": r.budget_amount,
                "variance_percent": r.variance_percent,
                "period": r.period,
            }
            for r in results
        ]
        
        session.close()
        
        return {
            "data": {"spend_records": records},
            "grounded_in": [
                GroundingReference(ref_id=r["record_id"], ref_type="structured_data", source_name="spend_metrics")
                for r in records
            ]
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalies via statistical deviation."""
        records = retrieval_result.get("data", {}).get("spend_records", [])
        
        signals = []
        
        # Calculate mean and std dev for anomaly detection
        if records:
            amounts = [r.get("spend_amount", 0) for r in records if r.get("spend_amount")]
            if len(amounts) >= 2:
                mean_spend = sum(amounts) / len(amounts)
                variance = sum((x - mean_spend) ** 2 for x in amounts) / len(amounts)
                std_dev = variance ** 0.5
                
                for record in records:
                    spend = record.get("spend_amount", 0)
                    if std_dev > 0 and abs(spend - mean_spend) > 2 * std_dev:
                        signals.append({
                            "signal_type": "spend_anomaly",
                            "severity": "medium",
                            "period": record.get("period"),
                            "spend_amount": spend,
                            "expected_range": f"${mean_spend - 2*std_dev:,.0f} - ${mean_spend + 2*std_dev:,.0f}",
                            "message": f"Spend anomaly detected: ${spend:,.0f} vs expected ${mean_spend:,.0f}",
                        })
        
        return {
            "data": {"spend_signals": signals},
            "grounded_in": []
        }


class ApplyRelevanceFiltersTask(BaseTask):
    """Apply category and DTP stage filters to signals."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define relevance rules."""
        return {
            "data": {
                "category_filter": context.get("category_id"),
                "dtp_stage_filter": context.get("dtp_stage"),
                "min_severity": "low",
            },
            "grounded_in": []
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Filter and prioritize signals."""
        # Collect all signals from previous tasks
        all_signals = []
        all_signals.extend(context.get("expiry_signals", []))
        all_signals.extend(context.get("performance_signals", []))
        all_signals.extend(context.get("spend_signals", []))
        
        # Priority mapping
        severity_priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        # Sort by severity
        sorted_signals = sorted(
            all_signals,
            key=lambda s: severity_priority.get(s.get("severity", "low"), 0),
            reverse=True
        )
        
        # Calculate urgency score
        urgency_score = 5  # Default moderate
        if sorted_signals:
            high_count = sum(1 for s in sorted_signals if s.get("severity") in ["high", "critical"])
            if high_count >= 2:
                urgency_score = 9
            elif high_count == 1:
                urgency_score = 7
            elif sorted_signals[0].get("severity") == "medium":
                urgency_score = 5
            else:
                urgency_score = 3
        
        return {
            "data": {
                "filtered_signals": sorted_signals[:10],
                "urgency_score": urgency_score,
                "total_signals": len(sorted_signals),
            },
            "grounded_in": []
        }


class SemanticGroundedSummaryTask(BaseTask):
    """Generate LLM narration grounded in signal data."""
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate narrative summary."""
        signals = context.get("filtered_signals", [])
        urgency_score = context.get("urgency_score", 5)
        
        if not signals:
            return {
                "data": {"summary": "No significant signals detected at this time."},
                "tokens_used": 0
            }
        
        # Build context for LLM
        signal_texts = []
        for s in signals[:5]:
            signal_texts.append(f"- {s.get('message', 'Signal detected')}")
        
        prompt = f"""Summarize these sourcing signals in 2-3 sentences for a procurement manager.
Be specific and actionable. Reference the data.

Signals:
{chr(10).join(signal_texts)}

Urgency Score: {urgency_score}/10

Summary:"""
        
        summary, tokens = self._call_llm(prompt)
        
        return {
            "data": {"summary": summary.strip() if summary else "Signal analysis complete."},
            "tokens_used": tokens
        }


class ProduceAutoprepRecommendationsTask(BaseTask):
    """Generate next actions and required inputs for case preparation."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations based on signals."""
        signals = context.get("filtered_signals", [])
        urgency_score = context.get("urgency_score", 5)
        dtp_stage = context.get("dtp_stage", "DTP-01")
        
        recommendations = []
        required_inputs = []
        
        # Check for expiry signals
        expiry_signals = [s for s in signals if s.get("signal_type") == "contract_expiry"]
        if expiry_signals:
            recommendations.append({
                "action": "Review contract terms",
                "priority": "high",
                "reason": f"Contract expiring in {expiry_signals[0].get('days_until_expiry', 'N/A')} days",
            })
            required_inputs.append("Current contract document")
            required_inputs.append("Supplier performance history")
        
        # Check for performance signals
        perf_signals = [s for s in signals if s.get("signal_type") in ["performance_degradation", "risk_alert"]]
        if perf_signals:
            recommendations.append({
                "action": "Evaluate alternative suppliers",
                "priority": "medium",
                "reason": "Current supplier showing performance issues",
            })
            required_inputs.append("Approved supplier list")
        
        # Default recommendation
        if not recommendations:
            recommendations.append({
                "action": "Continue monitoring",
                "priority": "low",
                "reason": "No immediate action required",
            })
        
        return {
            "data": {
                "recommendations": recommendations,
                "required_inputs": list(set(required_inputs)),
            },
            "grounded_in": []
        }

