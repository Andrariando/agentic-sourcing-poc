"""
RFx tasks for RFx Draft Agent.

Purpose: Assemble RFx drafts using templates, past examples, and structured
generation based on sourcing manager inputs.
"""
from typing import Dict, Any, List
from datetime import datetime

from backend.tasks.base_task import BaseTask
from shared.schemas import GroundingReference


class DetermineRfxPathTask(BaseTask):
    """Determine RFI/RFP/RFQ path based on rules and missing info."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply rules to determine RFx type."""
        category_id = context.get("category_id", "")
        estimated_value = context.get("estimated_value", 0)
        supplier_known = context.get("supplier_id") is not None
        requirements_defined = context.get("requirements_defined", False)
        specifications_complete = context.get("specifications_complete", False)
        
        rfx_type = "RFP"  # Default
        rationale = []
        
        # Rule-based determination
        if not requirements_defined:
            rfx_type = "RFI"
            rationale.append("Requirements not fully defined - RFI to gather information")
        elif specifications_complete and estimated_value < 50000:
            rfx_type = "RFQ"
            rationale.append("Specifications complete and value under $50K - RFQ appropriate")
        else:
            rfx_type = "RFP"
            rationale.append("Full proposal evaluation needed")
        
        return {
            "data": {
                "rfx_type": rfx_type,
                "rationale": rationale,
                "missing_info": [] if requirements_defined else ["Detailed requirements"],
            },
            "grounded_in": [GroundingReference(
                ref_id="policy-rfx-selection-001",
                ref_type="policy",
                source_name="RFx Selection Guidelines"
            )]
        }


class RetrieveTemplatesTask(BaseTask):
    """Retrieve RFx templates and past examples from ChromaDB."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Search for relevant templates."""
        rfx_type = rules_result.get("data", {}).get("rfx_type", "RFP")
        category_id = context.get("category_id", "")
        
        # Query vector store for templates
        query = f"{rfx_type} template {category_id}"
        results = self.retriever.retrieve_documents(
            query=query,
            document_types=["RFx", "Policy"],
            top_k=5
        )
        
        templates = []
        past_examples = []
        grounded_in = []
        
        for chunk in results.get("chunks", []):
            metadata = chunk.get("metadata", {})
            doc_type = metadata.get("document_type", "")
            
            if "template" in chunk.get("content", "").lower():
                templates.append({
                    "source": metadata.get("filename", "Template"),
                    "content_preview": chunk.get("content", "")[:500],
                })
            else:
                past_examples.append({
                    "source": metadata.get("filename", "Example"),
                    "content_preview": chunk.get("content", "")[:500],
                })
            
            grounded_in.append(GroundingReference(
                ref_id=chunk.get("chunk_id", ""),
                ref_type="document",
                source_name=metadata.get("filename", "Unknown"),
                excerpt=chunk.get("content", "")[:200]
            ))
        
        return {
            "data": {
                "templates": templates,
                "past_examples": past_examples,
            },
            "grounded_in": grounded_in
        }


class AssembleRfxSectionsTask(BaseTask):
    """Assemble RFx document sections from templates."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble standard RFx sections."""
        rfx_type = context.get("rfx_type", "RFP")
        category_id = context.get("category_id", "")
        templates = context.get("templates", [])
        
        # Standard sections by RFx type
        section_templates = {
            "RFI": [
                {"section": "Introduction", "required": True},
                {"section": "Company Background", "required": True},
                {"section": "Information Requested", "required": True},
                {"section": "Response Format", "required": True},
                {"section": "Timeline", "required": True},
            ],
            "RFP": [
                {"section": "Executive Summary", "required": True},
                {"section": "Scope of Work", "required": True},
                {"section": "Technical Requirements", "required": True},
                {"section": "Pricing Structure", "required": True},
                {"section": "Evaluation Criteria", "required": True},
                {"section": "Terms and Conditions", "required": True},
                {"section": "Submission Instructions", "required": True},
            ],
            "RFQ": [
                {"section": "Item Specifications", "required": True},
                {"section": "Quantity Requirements", "required": True},
                {"section": "Delivery Requirements", "required": True},
                {"section": "Pricing Format", "required": True},
                {"section": "Submission Deadline", "required": True},
            ],
        }
        
        sections = section_templates.get(rfx_type, section_templates["RFP"])
        
        # Mark sections as draft
        for section in sections:
            section["status"] = "draft"
            section["content"] = f"[Draft {section['section']} content for {category_id}]"
        
        return {
            "data": {"sections": sections},
            "grounded_in": []
        }


class CompletenessChecksTask(BaseTask):
    """Rule-based completeness checks on RFx draft."""
    
    def run_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Define completeness requirements."""
        rfx_type = context.get("rfx_type", "RFP")
        
        requirements = {
            "RFI": ["Introduction", "Information Requested", "Timeline"],
            "RFP": ["Scope of Work", "Technical Requirements", "Pricing Structure", "Evaluation Criteria"],
            "RFQ": ["Item Specifications", "Quantity Requirements", "Pricing Format"],
        }
        
        return {
            "data": {"required_sections": requirements.get(rfx_type, [])},
            "grounded_in": []
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Check completeness against requirements."""
        sections = context.get("sections", [])
        required = rules_result.get("data", {}).get("required_sections", [])
        
        section_names = [s["section"] for s in sections]
        
        missing = []
        incomplete = []
        
        for req in required:
            if req not in section_names:
                missing.append(req)
            else:
                # Check if section has content beyond placeholder
                for s in sections:
                    if s["section"] == req and "[Draft" in s.get("content", ""):
                        incomplete.append(req)
        
        is_complete = len(missing) == 0
        completeness_score = 100 - (len(missing) * 15 + len(incomplete) * 5)
        
        return {
            "data": {
                "is_complete": is_complete,
                "completeness_score": max(0, completeness_score),
                "missing_sections": missing,
                "incomplete_sections": incomplete,
            },
            "grounded_in": []
        }


class DraftQuestionsTask(BaseTask):
    """Draft questions and requirements using LLM."""
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate draft questions for RFx."""
        rfx_type = context.get("rfx_type", "RFP")
        category_id = context.get("category_id", "")
        templates = context.get("templates", [])
        
        # Use template content if available
        template_context = ""
        if templates:
            template_context = f"Reference template:\n{templates[0].get('content_preview', '')[:500]}"
        
        prompt = f"""Generate 5 key questions for a {rfx_type} in the {category_id} category.
{template_context}

Format each as:
Q[n]: [Question]
Purpose: [Why this question matters]

Questions:"""
        
        response, tokens = self._call_llm(prompt)
        
        # Parse questions
        questions = []
        if response:
            lines = response.strip().split("\n")
            current_q = None
            for line in lines:
                if line.startswith("Q"):
                    if current_q:
                        questions.append(current_q)
                    current_q = {"question": line, "purpose": ""}
                elif line.startswith("Purpose:") and current_q:
                    current_q["purpose"] = line.replace("Purpose:", "").strip()
            if current_q:
                questions.append(current_q)
        
        return {
            "data": {"draft_questions": questions},
            "tokens_used": tokens
        }


class CreateQaTrackerTask(BaseTask):
    """Create Q&A tracking table for RFx process."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured Q&A tracker."""
        questions = context.get("draft_questions", [])
        
        tracker = []
        for i, q in enumerate(questions):
            tracker.append({
                "id": f"Q-{i+1:03d}",
                "question": q.get("question", ""),
                "purpose": q.get("purpose", ""),
                "status": "pending",
                "response": "",
                "source_supplier": "",
                "received_date": "",
            })
        
        return {
            "data": {
                "qa_tracker": tracker,
                "total_questions": len(tracker),
            },
            "grounded_in": []
        }




