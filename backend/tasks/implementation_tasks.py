"""
Implementation tasks for Implementation Agent.

Purpose: Produce rollout steps and early post-award indicators
(savings + service impacts).
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta

from backend.tasks.base_task import BaseTask
from shared.schemas import GroundingReference


class BuildRolloutChecklistTask(BaseTask):
    """Build rollout checklist from playbooks."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve rollout playbooks."""
        category_id = context.get("category_id", "")
        
        query = f"implementation rollout checklist {category_id}"
        results = self.retriever.retrieve_documents(
            query=query,
            document_types=["Policy", "RFx"],
            top_k=3
        )
        
        playbook_content = []
        grounded_in = []
        
        for chunk in results.get("chunks", []):
            playbook_content.append(chunk.get("content", ""))
            grounded_in.append(GroundingReference(
                ref_id=chunk.get("chunk_id", ""),
                ref_type="document",
                source_name=chunk.get("metadata", {}).get("filename", "Playbook")
            ))
        
        return {
            "data": {"playbook_content": playbook_content},
            "grounded_in": grounded_in
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build structured checklist."""
        start_date = datetime.now()
        
        checklist = [
            {
                "phase": "Preparation",
                "items": [
                    {"task": "Finalize contract execution", "owner": "Legal", "target_date": start_date.isoformat()[:10], "status": "pending"},
                    {"task": "Set up supplier in vendor system", "owner": "Finance", "target_date": (start_date + timedelta(days=3)).isoformat()[:10], "status": "pending"},
                    {"task": "Schedule kick-off meeting", "owner": "Procurement", "target_date": (start_date + timedelta(days=5)).isoformat()[:10], "status": "pending"},
                ],
            },
            {
                "phase": "Kick-off",
                "items": [
                    {"task": "Conduct kick-off meeting", "owner": "Project Manager", "target_date": (start_date + timedelta(days=7)).isoformat()[:10], "status": "pending"},
                    {"task": "Exchange contact information", "owner": "Procurement", "target_date": (start_date + timedelta(days=7)).isoformat()[:10], "status": "pending"},
                    {"task": "Review SLA and reporting requirements", "owner": "Operations", "target_date": (start_date + timedelta(days=7)).isoformat()[:10], "status": "pending"},
                ],
            },
            {
                "phase": "Transition",
                "items": [
                    {"task": "Begin service transition", "owner": "Operations", "target_date": (start_date + timedelta(days=14)).isoformat()[:10], "status": "pending"},
                    {"task": "Validate initial deliverables", "owner": "Quality", "target_date": (start_date + timedelta(days=30)).isoformat()[:10], "status": "pending"},
                    {"task": "Set up performance dashboards", "owner": "Analytics", "target_date": (start_date + timedelta(days=21)).isoformat()[:10], "status": "pending"},
                ],
            },
            {
                "phase": "Steady State",
                "items": [
                    {"task": "First monthly review", "owner": "Procurement", "target_date": (start_date + timedelta(days=30)).isoformat()[:10], "status": "pending"},
                    {"task": "First quarterly business review", "owner": "Procurement", "target_date": (start_date + timedelta(days=90)).isoformat()[:10], "status": "pending"},
                ],
            },
        ]
        
        total_items = sum(len(phase["items"]) for phase in checklist)
        
        return {
            "data": {
                "checklist": checklist,
                "total_items": total_items,
                "estimated_duration_days": 90,
            },
            "grounded_in": []
        }


class ComputeExpectedSavingsTask(BaseTask):
    """Compute expected savings from structured inputs."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate deterministic savings projections."""
        # Get financial inputs
        new_annual_value = context.get("new_contract_value", 0)
        old_annual_value = context.get("old_contract_value", 0)
        term_years = context.get("term_years", 3)
        
        # If no old value, estimate from new (10% savings assumed)
        if not old_annual_value and new_annual_value:
            old_annual_value = new_annual_value * 1.10
        
        # Calculate savings
        annual_savings = old_annual_value - new_annual_value
        total_savings = annual_savings * term_years
        savings_pct = (annual_savings / old_annual_value * 100) if old_annual_value > 0 else 0
        
        savings_breakdown = {
            "hard_savings": {
                "annual": annual_savings * 0.7,  # 70% assumed hard
                "total": annual_savings * 0.7 * term_years,
                "description": "Direct price reduction vs. previous contract",
            },
            "soft_savings": {
                "annual": annual_savings * 0.2,  # 20% soft
                "total": annual_savings * 0.2 * term_years,
                "description": "Improved SLA and reduced risk exposure",
            },
            "cost_avoidance": {
                "annual": annual_savings * 0.1,  # 10% avoidance
                "total": annual_savings * 0.1 * term_years,
                "description": "Avoided price increases based on market trends",
            },
        }
        
        return {
            "data": {
                "annual_savings": annual_savings,
                "total_savings": total_savings,
                "savings_percentage": savings_pct,
                "savings_breakdown": savings_breakdown,
                "term_years": term_years,
            },
            "grounded_in": [GroundingReference(
                ref_id="calc-savings-001",
                ref_type="calculation",
                source_name="Savings Calculator"
            )]
        }


class DefineEarlyIndicatorsTask(BaseTask):
    """Define early success indicators and KPIs."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define standard KPI frameworks."""
        return {
            "data": {
                "kpi_categories": ["Service Quality", "Delivery", "Cost", "Relationship"],
            },
            "grounded_in": [GroundingReference(
                ref_id="framework-kpi-001",
                ref_type="policy",
                source_name="Standard KPI Framework"
            )]
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build early indicator definitions."""
        sla = context.get("sla", {})
        
        early_indicators = [
            {
                "category": "Service Quality",
                "kpi": "SLA Compliance Rate",
                "target": "≥99%",
                "measurement": "Monthly",
                "first_check": "Day 30",
                "data_source": "Supplier reports + internal tracking",
            },
            {
                "category": "Service Quality",
                "kpi": "Response Time",
                "target": sla.get("response_time", "≤4 hours"),
                "measurement": "Per incident",
                "first_check": "Day 14",
                "data_source": "Ticket system",
            },
            {
                "category": "Delivery",
                "kpi": "On-Time Delivery",
                "target": "≥95%",
                "measurement": "Weekly",
                "first_check": "Day 21",
                "data_source": "Order tracking",
            },
            {
                "category": "Cost",
                "kpi": "Invoice Accuracy",
                "target": "100%",
                "measurement": "Per invoice",
                "first_check": "Day 30",
                "data_source": "AP system",
            },
            {
                "category": "Relationship",
                "kpi": "Stakeholder Satisfaction",
                "target": "≥4.0/5.0",
                "measurement": "Quarterly",
                "first_check": "Day 90",
                "data_source": "Survey",
            },
        ]
        
        # Risk triggers
        risk_triggers = [
            {"indicator": "SLA Compliance", "threshold": "<95%", "action": "Escalate to account manager"},
            {"indicator": "Response Time", "threshold": ">8 hours", "action": "Issue formal warning"},
            {"indicator": "Invoice Accuracy", "threshold": "<98%", "action": "Request process improvement plan"},
        ]
        
        return {
            "data": {
                "early_indicators": early_indicators,
                "risk_triggers": risk_triggers,
            },
            "grounded_in": []
        }


class ReportingTemplatesTask(BaseTask):
    """Generate reporting templates for value capture."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create value capture reporting templates."""
        savings = context.get("savings_breakdown", {})
        indicators = context.get("early_indicators", [])
        
        templates = {
            "monthly_report": {
                "name": "Monthly Performance Report",
                "sections": [
                    {
                        "title": "Executive Summary",
                        "fields": ["Period", "Overall Status", "Key Highlights", "Concerns"],
                    },
                    {
                        "title": "SLA Performance",
                        "fields": ["Metric", "Target", "Actual", "Variance", "Trend"],
                    },
                    {
                        "title": "Financial Summary",
                        "fields": ["Invoiced Amount", "Budget", "Variance", "YTD Spend", "YTD Savings"],
                    },
                    {
                        "title": "Action Items",
                        "fields": ["Item", "Owner", "Due Date", "Status"],
                    },
                ],
            },
            "quarterly_review": {
                "name": "Quarterly Business Review",
                "sections": [
                    {
                        "title": "Relationship Health",
                        "fields": ["Engagement Score", "Issue Resolution Rate", "Escalations"],
                    },
                    {
                        "title": "Value Delivered",
                        "fields": ["Contracted Value", "Actual Savings", "Additional Value"],
                    },
                    {
                        "title": "Forward Look",
                        "fields": ["Upcoming Milestones", "Risks", "Opportunities"],
                    },
                ],
            },
            "savings_tracker": {
                "name": "Savings Tracker",
                "columns": ["Category", "Target", "Actual", "Variance", "Evidence"],
                "rows": [
                    {"category": "Hard Savings", "target": savings.get("hard_savings", {}).get("annual", 0)},
                    {"category": "Soft Savings", "target": savings.get("soft_savings", {}).get("annual", 0)},
                    {"category": "Cost Avoidance", "target": savings.get("cost_avoidance", {}).get("annual", 0)},
                ],
            },
        }
        
        return {
            "data": {"reporting_templates": templates},
            "grounded_in": []
        }
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        """Enable LLM to generate Value Story."""
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate 'The Historian' Value Story."""
        savings = context.get("savings_breakdown", {})
        annual_savings = context.get("annual_savings", 0)
        total_savings = context.get("total_savings", 0)
        term_years = context.get("term_years", 3)
        supplier_id = context.get("supplier_id", "the supplier")
        category_id = context.get("category_id", "this category")
        
        prompt = f"""You are "THE HISTORIAN" - a value capture specialist for DTP-06.

Your job is to DEFEND THE VALUE of this sourcing project. Write a compelling narrative.

SOURCING OUTCOME:
- Category: {category_id}
- Supplier: {supplier_id}
- Contract Term: {term_years} years
- Annual Savings: ${annual_savings:,.0f}
- Total Savings Over Term: ${total_savings:,.0f}
- Hard Savings: ${savings.get('hard_savings', {}).get('annual', 0):,.0f}/year
- Cost Avoidance: ${savings.get('cost_avoidance', {}).get('annual', 0):,.0f}/year

Write a 3-4 sentence "Value Story" that:
1. States the total value delivered ("We secured $X in savings over Y years")
2. Highlights what was negotiated ("negotiated 5% below benchmark")
3. Mentions risk mitigation ("locked in pricing to avoid market volatility")
4. Ends with sourcing ROI if calculable ("Estimated sourcing ROI: Z%")

Value Story:"""
        
        response, tokens = self._call_llm(prompt)
        
        return {
            "data": {"value_story": response.strip() if response else f"Total value of ${total_savings:,.0f} secured over {term_years} years."},
            "tokens_used": tokens
        }




