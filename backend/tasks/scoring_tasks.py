"""
Scoring tasks for Supplier Scoring Agent.

Purpose: Convert human-defined evaluation criteria into structured score inputs;
process historical performance and risk data.
"""
from typing import Dict, Any, List
from sqlmodel import select

from backend.tasks.base_task import BaseTask
from backend.persistence.database import get_db_session
from backend.persistence.models import SupplierPerformance, SLAEvent
from shared.schemas import GroundingReference


class BuildEvaluationCriteriaTask(BaseTask):
    """Build evaluation criteria from user inputs and templates."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define default evaluation criteria."""
        # Default criteria if none provided
        default_criteria = [
            {"name": "Quality", "weight": 0.25, "description": "Product/service quality"},
            {"name": "Delivery", "weight": 0.20, "description": "On-time delivery performance"},
            {"name": "Price", "weight": 0.25, "description": "Cost competitiveness"},
            {"name": "Responsiveness", "weight": 0.15, "description": "Communication and support"},
            {"name": "Risk", "weight": 0.15, "description": "Financial and operational risk"},
        ]
        
        # Use provided criteria or defaults
        criteria = context.get("evaluation_criteria", default_criteria)
        
        return {
            "data": {"criteria": criteria},
            "grounded_in": [GroundingReference(
                ref_id="criteria-template-001",
                ref_type="template",
                source_name="Default Evaluation Template"
            )]
        }


class PullSupplierPerformanceTask(BaseTask):
    """Pull supplier performance data from SQLite."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve performance data for relevant suppliers."""
        session = get_db_session()
        category_id = context.get("category_id")
        supplier_ids = context.get("supplier_ids", [])
        
        # If specific suppliers not provided, get all for category
        query = select(SupplierPerformance)
        if category_id:
            query = query.where(SupplierPerformance.category_id == category_id)
        if supplier_ids:
            query = query.where(SupplierPerformance.supplier_id.in_(supplier_ids))
        
        query = query.order_by(SupplierPerformance.measurement_date.desc())
        results = session.exec(query).all()
        
        # Group by supplier, take latest
        supplier_data = {}
        grounded_in = []
        for r in results:
            if r.supplier_id not in supplier_data:
                supplier_data[r.supplier_id] = {
                    "supplier_id": r.supplier_id,
                    "supplier_name": r.supplier_name or r.supplier_id,
                    "overall_score": r.overall_score,
                    "quality_score": r.quality_score,
                    "delivery_score": r.delivery_score,
                    "cost_variance": r.cost_variance,
                    "responsiveness_score": r.responsiveness_score,
                    "trend": r.trend,
                    "risk_level": r.risk_level,
                }
                grounded_in.append(GroundingReference(
                    ref_id=r.record_id,
                    ref_type="structured_data",
                    source_name=f"Performance: {r.supplier_id}"
                ))
        
        session.close()
        
        return {
            "data": {"supplier_performance": list(supplier_data.values())},
            "grounded_in": grounded_in
        }


class PullRiskIndicatorsTask(BaseTask):
    """Pull risk indicator data from SQLite and docs."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve SLA events and risk data."""
        session = get_db_session()
        supplier_performance = context.get("supplier_performance", [])
        supplier_ids = [s["supplier_id"] for s in supplier_performance]
        
        risk_data = {}
        grounded_in = []
        
        for supplier_id in supplier_ids:
            query = select(SLAEvent).where(
                SLAEvent.supplier_id == supplier_id
            ).order_by(SLAEvent.event_date.desc()).limit(20)
            
            events = session.exec(query).all()
            
            breach_count = sum(1 for e in events if e.event_type == "breach")
            high_severity_count = sum(1 for e in events if e.severity in ["high", "critical"])
            
            risk_data[supplier_id] = {
                "supplier_id": supplier_id,
                "sla_breach_count": breach_count,
                "high_severity_events": high_severity_count,
                "total_events": len(events),
                "risk_score": min(10, breach_count * 2 + high_severity_count),
            }
            
            for e in events[:3]:
                grounded_in.append(GroundingReference(
                    ref_id=e.event_id,
                    ref_type="structured_data",
                    source_name=f"SLA Event: {e.event_type}"
                ))
        
        session.close()
        
        return {
            "data": {"risk_indicators": list(risk_data.values())},
            "grounded_in": grounded_in
        }


class NormalizeMetricsTask(BaseTask):
    """Normalize metrics for comparison across suppliers."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize all metrics to 0-10 scale."""
        performance = context.get("supplier_performance", [])
        risk = {r["supplier_id"]: r for r in context.get("risk_indicators", [])}
        
        normalized = []
        for p in performance:
            supplier_id = p["supplier_id"]
            risk_info = risk.get(supplier_id, {})
            
            # Normalize scores (already 0-10 in our data)
            normalized.append({
                "supplier_id": supplier_id,
                "supplier_name": p.get("supplier_name", supplier_id),
                "quality_normalized": min(10, max(0, p.get("quality_score", 5))),
                "delivery_normalized": min(10, max(0, p.get("delivery_score", 5))),
                "responsiveness_normalized": min(10, max(0, p.get("responsiveness_score", 5))),
                "risk_normalized": 10 - min(10, risk_info.get("risk_score", 0)),  # Invert risk
                "cost_normalized": 10 - min(10, abs(p.get("cost_variance", 0)) / 5),  # Lower variance = better
                "raw_data": p,
                "risk_data": risk_info,
            })
        
        return {
            "data": {"normalized_metrics": normalized},
            "grounded_in": []
        }


class ComputeScoresAndRankTask(BaseTask):
    """Compute final scores and ranking."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate weighted scores and rank suppliers."""
        criteria = context.get("criteria", [])
        normalized = context.get("normalized_metrics", [])
        
        # Map criteria to normalized fields
        field_map = {
            "Quality": "quality_normalized",
            "Delivery": "delivery_normalized",
            "Price": "cost_normalized",
            "Responsiveness": "responsiveness_normalized",
            "Risk": "risk_normalized",
        }
        
        scored = []
        for supplier in normalized:
            total_score = 0
            score_breakdown = {}
            
            for criterion in criteria:
                field = field_map.get(criterion["name"])
                if field and field in supplier:
                    weight = criterion.get("weight", 0.2)
                    value = supplier[field]
                    weighted = value * weight
                    total_score += weighted
                    score_breakdown[criterion["name"]] = {
                        "raw": value,
                        "weight": weight,
                        "weighted": weighted,
                    }
            
            scored.append({
                "supplier_id": supplier["supplier_id"],
                "supplier_name": supplier.get("supplier_name", supplier["supplier_id"]),
                "total_score": round(total_score, 2),
                "score_breakdown": score_breakdown,
                "raw_data": supplier.get("raw_data", {}),
                "risk_data": supplier.get("risk_data", {}),
            })
        
        # Sort by score descending
        ranked = sorted(scored, key=lambda x: x["total_score"], reverse=True)
        
        # Add rank
        for i, s in enumerate(ranked):
            s["rank"] = i + 1
        
        return {
            "data": {"ranked_suppliers": ranked},
            "grounded_in": []
        }


class EligibilityChecksTask(BaseTask):
    """Check supplier eligibility against rule thresholds."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define eligibility rules."""
        return {
            "data": {
                "min_score": 4.0,
                "max_breaches": 5,
                "required_capabilities": context.get("required_capabilities", []),
            },
            "grounded_in": [GroundingReference(
                ref_id="policy-eligibility-001",
                ref_type="policy",
                source_name="Supplier Eligibility Policy"
            )]
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply eligibility rules."""
        rules = rules_result.get("data", {})
        ranked = context.get("ranked_suppliers", [])
        
        min_score = rules.get("min_score", 4.0)
        max_breaches = rules.get("max_breaches", 5)
        
        eligible = []
        ineligible = []
        
        for supplier in ranked:
            issues = []
            
            if supplier["total_score"] < min_score:
                issues.append(f"Score {supplier['total_score']:.1f} below minimum {min_score}")
            
            breaches = supplier.get("risk_data", {}).get("sla_breach_count", 0)
            if breaches > max_breaches:
                issues.append(f"{breaches} SLA breaches exceeds limit of {max_breaches}")
            
            supplier["eligibility_issues"] = issues
            supplier["is_eligible"] = len(issues) == 0
            
            if supplier["is_eligible"]:
                eligible.append(supplier)
            else:
                ineligible.append(supplier)
        
        return {
            "data": {
                "eligible_suppliers": eligible,
                "ineligible_suppliers": ineligible,
            },
            "grounded_in": []
        }


class GenerateExplanationsTask(BaseTask):
    """Generate explanations for scores using LLM."""
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate narrative explanations for top suppliers."""
        eligible = context.get("eligible_suppliers", [])[:3]
        
        if not eligible:
            return {"data": {"explanations": {}}, "tokens_used": 0}
        
        explanations = {}
        total_tokens = 0
        
        for supplier in eligible:
            breakdown = supplier.get("score_breakdown", {})
            breakdown_text = ", ".join([
                f"{k}: {v['raw']:.1f}" for k, v in breakdown.items()
            ])
            
            prompt = f"""Write a 2-sentence explanation for why {supplier['supplier_name']} 
scored {supplier['total_score']:.1f}/10 in supplier evaluation.
Score breakdown: {breakdown_text}
Be specific and factual."""
            
            explanation, tokens = self._call_llm(prompt)
            explanations[supplier["supplier_id"]] = explanation.strip() if explanation else ""
            total_tokens += tokens
        
        return {
            "data": {"explanations": explanations},
            "tokens_used": total_tokens
        }

