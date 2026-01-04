"""
Negotiation tasks for Negotiation Support Agent.

Purpose: Highlight bid differences, identify negotiation levers, provide
structured insights WITHOUT making award decisions.
"""
from typing import Dict, Any, List

from backend.tasks.base_task import BaseTask
from shared.schemas import GroundingReference


class CompareBidsTask(BaseTask):
    """Compare supplier bids in structured format."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve bid data."""
        # Bids would come from context or database
        bids = context.get("bids", [])
        
        # If no bids in context, use sample data for demo
        if not bids:
            bids = [
                {
                    "supplier_id": "SUP-001",
                    "supplier_name": "TechCorp Solutions",
                    "price_usd": 450000,
                    "term_months": 36,
                    "sla_response_time": "4 hours",
                    "included_services": ["24/7 support", "Training", "Upgrades"],
                },
                {
                    "supplier_id": "SUP-002",
                    "supplier_name": "Global IT Partners",
                    "price_usd": 425000,
                    "term_months": 24,
                    "sla_response_time": "8 hours",
                    "included_services": ["Business hours support", "Training"],
                },
            ]
        
        return {
            "data": {"bids": bids},
            "grounded_in": [
                GroundingReference(
                    ref_id=f"bid-{b['supplier_id']}",
                    ref_type="bid",
                    source_name=b.get("supplier_name", b["supplier_id"])
                ) for b in bids
            ]
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured bid comparison."""
        bids = retrieval_result.get("data", {}).get("bids", [])
        
        if len(bids) < 2:
            return {"data": {"comparison": {}}, "grounded_in": []}
        
        # Calculate price spread
        prices = [b.get("price_usd", 0) for b in bids]
        min_price = min(prices)
        max_price = max(prices)
        spread = max_price - min_price
        spread_pct = (spread / min_price * 100) if min_price > 0 else 0
        
        # Identify differences
        differences = []
        
        # Price difference
        differences.append({
            "dimension": "Price",
            "variance": f"${spread:,.0f} ({spread_pct:.1f}%)",
            "low": min(bids, key=lambda x: x.get("price_usd", 0)).get("supplier_name"),
            "high": max(bids, key=lambda x: x.get("price_usd", 0)).get("supplier_name"),
        })
        
        # Term difference
        terms = [b.get("term_months", 0) for b in bids]
        if max(terms) != min(terms):
            differences.append({
                "dimension": "Contract Term",
                "variance": f"{max(terms) - min(terms)} months",
                "low": min(bids, key=lambda x: x.get("term_months", 0)).get("supplier_name"),
                "high": max(bids, key=lambda x: x.get("term_months", 0)).get("supplier_name"),
            })
        
        return {
            "data": {
                "comparison": {
                    "bid_count": len(bids),
                    "price_spread": spread,
                    "price_spread_pct": spread_pct,
                    "differences": differences,
                },
                "bids": bids,
            },
            "grounded_in": []
        }


class LeveragePointExtractionTask(BaseTask):
    """Extract negotiation leverage points from performance and alternatives."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Get supplier performance for leverage."""
        bids = context.get("bids", [])
        
        # Query performance data for bidding suppliers
        supplier_ids = [b["supplier_id"] for b in bids]
        performance_data = {}
        
        for supplier_id in supplier_ids:
            perf = self.retriever.get_supplier_performance(supplier_id)
            if perf.get("summary"):
                performance_data[supplier_id] = perf["summary"]
        
        return {
            "data": {"performance_by_supplier": performance_data},
            "grounded_in": []
        }
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Identify leverage points."""
        bids = context.get("bids", [])
        comparison = context.get("comparison", {})
        performance = retrieval_result.get("data", {}).get("performance_by_supplier", {})
        
        leverage_points = []
        
        # Price competition leverage
        if comparison.get("price_spread_pct", 0) > 10:
            leverage_points.append({
                "type": "price_competition",
                "description": f"Significant price variance ({comparison.get('price_spread_pct', 0):.0f}%) creates negotiation room",
                "strength": "high",
                "use_with": "higher-priced bidders",
            })
        
        # Performance-based leverage
        for bid in bids:
            supplier_perf = performance.get(bid["supplier_id"], {})
            if supplier_perf.get("trend") == "declining":
                leverage_points.append({
                    "type": "performance_concern",
                    "description": f"{bid['supplier_name']} has declining performance trend",
                    "strength": "medium",
                    "use_with": bid["supplier_name"],
                })
        
        # Alternative supplier leverage
        if len(bids) >= 3:
            leverage_points.append({
                "type": "competition",
                "description": f"Multiple competitive bids ({len(bids)}) strengthens buyer position",
                "strength": "high",
                "use_with": "all suppliers",
            })
        
        return {
            "data": {"leverage_points": leverage_points},
            "grounded_in": []
        }


class BenchmarkRetrievalTask(BaseTask):
    """Retrieve market benchmarks from documents."""
    
    def run_retrieval(self, context: Dict[str, Any], rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Search for market rate benchmarks."""
        category_id = context.get("category_id", "")
        
        query = f"market rates benchmark pricing {category_id}"
        results = self.retriever.retrieve_documents(
            query=query,
            document_types=["Market Report"],
            top_k=3
        )
        
        benchmarks = []
        grounded_in = []
        
        for chunk in results.get("chunks", []):
            benchmarks.append({
                "source": chunk.get("metadata", {}).get("filename", "Unknown"),
                "content": chunk.get("content", "")[:500],
            })
            grounded_in.append(GroundingReference(
                ref_id=chunk.get("chunk_id", ""),
                ref_type="document",
                source_name=chunk.get("metadata", {}).get("filename", "Market Report"),
                excerpt=chunk.get("content", "")[:200]
            ))
        
        return {
            "data": {"benchmarks": benchmarks},
            "grounded_in": grounded_in
        }


class PriceAnomalyDetectionTask(BaseTask):
    """Detect pricing anomalies through statistical analysis."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Detect anomalies in bid pricing."""
        bids = context.get("bids", [])
        
        anomalies = []
        
        if len(bids) >= 2:
            prices = [b.get("price_usd", 0) for b in bids]
            mean_price = sum(prices) / len(prices)
            
            for bid in bids:
                price = bid.get("price_usd", 0)
                deviation = abs(price - mean_price) / mean_price * 100 if mean_price > 0 else 0
                
                if deviation > 20:  # More than 20% from mean
                    anomalies.append({
                        "supplier": bid.get("supplier_name", bid["supplier_id"]),
                        "price": price,
                        "deviation_pct": deviation,
                        "direction": "above" if price > mean_price else "below",
                        "concern": "Price significantly differs from market" if price > mean_price else "Unusually low - verify scope"
                    })
        
        return {
            "data": {"price_anomalies": anomalies},
            "grounded_in": []
        }


class ProposeTargetsAndFallbacksTask(BaseTask):
    """Propose target terms and fallback positions."""
    
    def run_analytics(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                      retrieval_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate target and fallback positions."""
        bids = context.get("bids", [])
        comparison = context.get("comparison", {})
        
        if not bids:
            return {"data": {"targets": {}, "fallbacks": {}}, "grounded_in": []}
        
        prices = [b.get("price_usd", 0) for b in bids]
        min_price = min(prices)
        max_price = max(prices)
        
        # Target: 5% below lowest bid
        target_price = min_price * 0.95
        
        # Fallback: lowest bid
        fallback_price = min_price
        
        # Walk-away: 10% above lowest bid
        walkaway_price = min_price * 1.10
        
        targets = {
            "price_target": target_price,
            "term_target_months": 36,  # Standard target
            "sla_target": "4 hours response",
            "additional_asks": ["Free training", "Extended warranty", "Price lock"],
        }
        
        fallbacks = {
            "price_fallback": fallback_price,
            "term_fallback_months": 24,
            "sla_fallback": "8 hours response",
            "walkaway_price": walkaway_price,
            "walkaway_triggers": ["Price above walkaway", "SLA > 12 hours", "No performance guarantees"],
        }
        
        return {
            "data": {
                "targets": targets,
                "fallbacks": fallbacks,
            },
            "grounded_in": []
        }


class NegotiationPlaybookTask(BaseTask):
    """Generate negotiation playbook with talk tracks."""
    
    def needs_llm_narration(self, context: Dict[str, Any], analytics_result: Dict[str, Any]) -> bool:
        return True
    
    def run_llm(self, context: Dict[str, Any], rules_result: Dict[str, Any],
                retrieval_result: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate negotiation talking points."""
        leverage_points = context.get("leverage_points", [])
        targets = context.get("targets", {})
        
        leverage_text = "\n".join([f"- {lp.get('description', '')}" for lp in leverage_points[:3]])
        
        prompt = f"""Create a brief negotiation playbook (3-4 bullet points) for a procurement negotiation.

Leverage points:
{leverage_text}

Target price: ${targets.get('price_target', 0):,.0f}

Include:
1. Opening position
2. Key give/get trades
3. Closing technique

Playbook:"""
        
        response, tokens = self._call_llm(prompt)
        
        # Structure the response
        playbook = {
            "summary": response.strip() if response else "Negotiate based on competitive bids",
            "give_get_options": [
                {"give": "Longer term commitment", "get": "Lower price"},
                {"give": "Faster payment terms", "get": "Price discount"},
                {"give": "Volume commitment", "get": "Service level upgrade"},
            ],
        }
        
        return {
            "data": {"playbook": playbook},
            "tokens_used": tokens
        }


