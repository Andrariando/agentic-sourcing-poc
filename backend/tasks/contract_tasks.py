"""
Contract tasks for Contract Support Agent.

Purpose: Extract key award terms and prepare structured inputs for
contracting and implementation.
"""
from typing import Dict, Any, List

from backend.tasks.base_task import BaseTask
from shared.schemas import GroundingReference


class ExtractKeyTermsTask(BaseTask):
    """Extract key terms from contract documents."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve contract documents for extraction."""
        contract_id = context.get("contract_id")
        supplier_id = context.get("supplier_id")
        
        query = "contract terms pricing SLA payment liability"
        results = self.retriever.retrieve_documents(
            query=query,
            supplier_id=supplier_id,
            document_types=["Contract"],
            top_k=5
        )
        
        grounded_in = []
        contract_chunks = []
        
        for chunk in results.get("chunks", []):
            contract_chunks.append(chunk.get("content", ""))
            grounded_in.append(GroundingReference(
                ref_id=chunk.get("chunk_id", ""),
                ref_type="document",
                source_name=chunk.get("metadata", {}).get("filename", "Contract"),
                excerpt=chunk.get("content", "")[:200]
            ))
        
        return {
            "data": {"contract_text": "\n\n".join(contract_chunks)},
            "grounded_in": grounded_in
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured terms from contract text."""
        contract_text = retrieval_result.get("data", {}).get("contract_text", "")
        
        # Template-guided extraction (would use NER/LLM in production)
        key_terms = {
            "pricing": {
                "annual_value": context.get("estimated_value", 0),
                "payment_terms": "Net 30",
                "price_adjustment": "Fixed for term",
            },
            "term": {
                "start_date": "",
                "end_date": "",
                "duration_months": 36,
                "renewal_clause": "Auto-renew with 90-day notice",
            },
            "sla": {
                "response_time": "4 hours",
                "uptime_guarantee": "99.5%",
                "penalties": "Service credits for SLA breach",
            },
            "liability": {
                "limitation": "12 months of fees",
                "indemnification": "Standard mutual indemnity",
            },
            "termination": {
                "for_convenience": "90 days notice",
                "for_cause": "30 days cure period",
            },
        }
        
        return {
            "data": {"key_terms": key_terms},
            "grounded_in": []
        }


class TermValidationTask(BaseTask):
    """Validate contract terms against rules and policies."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define term validation rules."""
        return {
            "data": {
                "rules": [
                    {"field": "liability.limitation", "rule": "Must be at least 12 months of fees"},
                    {"field": "sla.uptime_guarantee", "rule": "Must be 99% or higher"},
                    {"field": "termination.for_cause", "rule": "Cure period required"},
                    {"field": "pricing.payment_terms", "rule": "Net 30 or better"},
                ],
            },
            "grounded_in": [GroundingReference(
                ref_id="policy-contract-terms-001",
                ref_type="policy",
                source_name="Contract Terms Policy"
            )]
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate terms against rules."""
        key_terms = context.get("key_terms", {})
        rules = rules_result.get("data", {}).get("rules", [])
        
        validation_results = []
        issues = []
        
        for rule in rules:
            field_path = rule["field"].split(".")
            value = key_terms
            for field in field_path:
                value = value.get(field, {}) if isinstance(value, dict) else None
            
            # Simple validation (would be more sophisticated in production)
            is_valid = value is not None and value != ""
            
            validation_results.append({
                "field": rule["field"],
                "rule": rule["rule"],
                "current_value": str(value) if value else "Not found",
                "is_valid": is_valid,
            })
            
            if not is_valid:
                issues.append({
                    "field": rule["field"],
                    "issue": f"Missing or invalid: {rule['rule']}",
                    "severity": "medium",
                })
        
        return {
            "data": {
                "validation_results": validation_results,
                "issues": issues,
                "is_compliant": len(issues) == 0,
            },
            "grounded_in": []
        }


class TermAlignmentSummaryTask(BaseTask):
    """Summarize term alignment using LLM."""
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate alignment summary."""
        key_terms = context.get("key_terms", {})
        issues = context.get("issues", [])
        
        terms_text = f"""
Pricing: ${key_terms.get('pricing', {}).get('annual_value', 0):,}
Term: {key_terms.get('term', {}).get('duration_months', 0)} months
SLA: {key_terms.get('sla', {}).get('response_time', 'N/A')} response, {key_terms.get('sla', {}).get('uptime_guarantee', 'N/A')} uptime
"""
        
        issues_text = "\n".join([f"- {i['issue']}" for i in issues]) if issues else "None identified"
        
        prompt = f"""Summarize this contract term review in 2-3 sentences for a procurement manager.

Terms:
{terms_text}

Issues:
{issues_text}

Summary:"""
        
        response, tokens = self._call_llm(prompt)
        
        return {
            "data": {"alignment_summary": response.strip() if response else "Contract terms reviewed."},
            "tokens_used": tokens
        }


class ImplementationHandoffPacketTask(BaseTask):
    """Create implementation handoff packet with structured fields."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compile handoff packet."""
        key_terms = context.get("key_terms", {})
        supplier_id = context.get("supplier_id", "")
        
        handoff_packet = {
            "contract_summary": {
                "supplier_id": supplier_id,
                "annual_value": key_terms.get("pricing", {}).get("annual_value", 0),
                "term_months": key_terms.get("term", {}).get("duration_months", 0),
                "start_date": key_terms.get("term", {}).get("start_date", "TBD"),
            },
            "key_contacts": {
                "supplier_account_manager": "TBD",
                "internal_owner": context.get("case_owner", "Procurement Team"),
                "escalation_path": ["Account Manager", "Regional Director", "VP Sales"],
            },
            "sla_summary": key_terms.get("sla", {}),
            "payment_schedule": {
                "terms": key_terms.get("pricing", {}).get("payment_terms", "Net 30"),
                "frequency": "Monthly",
                "first_payment_due": "Upon contract execution",
            },
            "critical_dates": [
                {"date": "Contract start", "action": "Kick-off meeting"},
                {"date": "Start + 30 days", "action": "First deliverable review"},
                {"date": "Start + 90 days", "action": "First quarterly review"},
            ],
            "risk_items": context.get("issues", []),
        }
        
        return {
            "data": {"handoff_packet": handoff_packet},
            "grounded_in": []
        }

