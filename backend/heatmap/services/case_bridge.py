from typing import List
from backend.services.case_service import get_case_service
from backend.heatmap.persistence.heatmap_database import heatmap_db
from backend.heatmap.persistence.heatmap_models import Opportunity, AuditLog


class CaseBridgeService:
    """
    Bridge between the NEW Heatmap System and the LEGACY DTP Case System.
    This is the ONLY touchpoint between the two agentic systems.
    """
    
    def approve_opportunities(self, opportunity_ids: List[int], approver_id: str) -> int:
        session = heatmap_db.get_db_session()
        legacy_case_service = get_case_service()
        approved_count = 0
        
        try:
            for opp_id in opportunity_ids:
                opp = session.get(Opportunity, opp_id)
                if not opp or opp.status == "Approved":
                    continue
                    
                # Create Case in the Legacy System
                try:
                    case_id = legacy_case_service.create_case(
                        category_id=opp.category,
                        trigger_source="OpportunityHeatmap",
                        contract_id=opp.contract_id,
                        supplier_id=opp.supplier_id or opp.supplier_name,
                        name=f"Heatmap Approved: {opp.supplier_name or 'New Request'}"
                    )
                    
                    # Mark approved internally and link
                    opp.status = "Approved"
                    session.add(opp)
                    
                    # Audit trail
                    audit = AuditLog(
                        event_type="CASE_APPROVED",
                        entity_id=str(opp.id),
                        new_value=f"Linked to Case: {case_id}",
                        user_id=approver_id
                    )
                    session.add(audit)
                    approved_count += 1
                    
                except Exception as e:
                    print(f"Failed to bridge opportunity {opp_id} to legacy system: {e}")
                    
            session.commit()
        finally:
            session.close()
            
        return approved_count


def get_case_bridge_service() -> CaseBridgeService:
    return CaseBridgeService()

