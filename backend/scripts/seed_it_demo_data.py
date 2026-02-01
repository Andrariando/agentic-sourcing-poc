#!/usr/bin/env python3
"""
IT Infrastructure Demo Seed Script
10+ Robust, End-to-End Playable Cases (ALL STAGES DTP-01 to DTP-06)

FIXES APPLIED:
- Added missing suppliers (NETWORK, SAAS, additional SOFTWARE, TELECOM, IT_SERVICES)
- Added case_context with candidate_suppliers to DTP-01 cases
- Fixed candidate_suppliers to use supplier IDs consistently
- Added sourcing_route decision to DTP-02 cases
- Added DTP-05 and DTP-06 test cases
- Added missing RFP templates (IT Services, SD-WAN, DevOps, HRIS)
- Added missing proposals (Oracle HCM, SAP SuccessFactors)
- Added IT Services Market Report
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from sqlmodel import Session, select, delete

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.persistence.database import get_engine, init_db
from backend.persistence.models import (
    SupplierPerformance, SpendMetric, SLAEvent, CaseState, DocumentRecord
)
from backend.rag.vector_store import get_vector_store

def seed_cases(session: Session):
    """Seed 12 comprehensive IT cases (DTP-01 through DTP-06)."""
    print("Seeding 12 IT cases...")
    
    # Clear existing cases
    session.exec(delete(CaseState))
    session.commit()
    print("  [OK] Cleared existing cases.")
    
    cases_data = [
        # ============================================================
        # DTP-01 Cases (Strategy) - No prerequisites needed
        # FIXED: Added case_context with candidate_suppliers
        # ============================================================
        {
            "case_id": "CASE-001",
            "name": "IT Managed Services Renewal",
            "category_id": "IT_SERVICES",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Global IT Managed Services contract with TechCorp expiring in 90 days. Performance has been stable but pricing is above market.",
            "recommended_action": "Initiate renewal negotiation with competitive pressure",
            "trigger_source": "Signal (Contract Expiry)",
            # FIX: Add case_context with candidate_suppliers for DTP-02 advance
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-IT-01", "SUP-IT-02", "SUP-IT-03", "SUP-IT-04"],
                "contract_value": 2400000,
                "contract_end_date": "2026-04-30",
                "incumbent_supplier": "TechCorp Solutions",
                "incumbent_supplier_id": "SUP-IT-01"
            })
        },
        {
            "case_id": "CASE-002",
            "name": "End-User Hardware Refresh",
            "category_id": "HARDWARE",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Global laptop/desktop refresh cycle (2,500 units). Current standard is Dell. Evaluating move to Lenovo or HP for cost reduction.",
            "recommended_action": "Conduct competitive RFP for 3-year refresh program",
            "trigger_source": "User (Budget Cycle)",
            # FIX: Add case_context with candidate_suppliers
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-HW-01", "SUP-HW-02", "SUP-HW-03"],
                "estimated_value": 1500000,
                "unit_count": 2500,
                "current_standard": "Dell"
            })
        },
        {
            "case_id": "CASE-009",
            "name": "Global Telecom Consolidation",
            "category_id": "TELECOM",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Fragmented telecom spend across 15 countries. Goal to consolidate to 1-2 global carriers (AT&T/Verizon/BT) for 20% savings.",
            "recommended_action": "Strategic sourcing event for global consolidation",
            "trigger_source": "Signal (Spend Anomaly)",
            # FIX: Add case_context with candidate_suppliers
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-TEL-01", "SUP-TEL-02", "SUP-TEL-03"],
                "current_spend": 3000000,
                "countries_covered": 15,
                "target_savings_percent": 20
            })
        },

        # ============================================================
        # DTP-02 Cases (Planning) - Need DTP-01 decisions + candidate_suppliers
        # FIXED: Added sourcing_route decision, used supplier IDs
        # ============================================================
        {
            "case_id": "CASE-003",
            "name": "Cloud Migration (AWS/Azure)",
            "category_id": "CLOUD",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Strategic initiative to migrate 40% of on-prem workloads to cloud. Defining technical requirements for AWS vs Azure pilot.",
            "recommended_action": "Finalize RFP technical requirements and selection criteria",
            "trigger_source": "User (Strategic)",
            # FIX: Added sourcing_route decision
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-CL-01", "SUP-CL-02"]
            })
        },
        {
            "case_id": "CASE-007",
            "name": "SD-WAN Upgrade",
            "category_id": "NETWORK",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Replacing MPLS circuits with SD-WAN. Requirements gathering phase. Vendors: Cisco Viptela, VMware VeloCloud, Palo Alto Prisma.",
            "recommended_action": "Draft RFP for SD-WAN solution and managed services",
            "trigger_source": "User (Performance)",
            # FIX: Added sourcing_route, use supplier IDs
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                }
            }),
            # FIX: Use supplier IDs instead of text names
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-NET-01", "SUP-NET-02", "SUP-NET-03"]
            })
        },
        {
            "case_id": "CASE-010",
            "name": "DevOps Toolchain Standards",
            "category_id": "SOFTWARE",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Standardizing CI/CD pipeline tools (GitHub vs GitLab vs Jenkins). Need to align engineering teams on single platform.",
            "recommended_action": "Prepare evaluation matrix for toolchain consolidation",
            "trigger_source": "User (Standardization)",
            # FIX: Added sourcing_route
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Tactical", "decided_by_role": "User", "status": "final"}
                }
            }),
            # FIX: Use supplier IDs instead of text names
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-SW-02", "SUP-SW-03", "SUP-SW-04"]
            })
        },

        # ============================================================
        # DTP-03 Cases (Sourcing/Evaluation) - Need DTP-01 + DTP-02 decisions
        # FIXED: Use supplier IDs consistently
        # ============================================================
        {
            "case_id": "CASE-004",
            "name": "Cybersecurity SOC Services",
            "category_id": "SECURITY",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "summary_text": "RFP active for 24/7 SOC services. Proposals received from SecureNet, CyberGuard AI, and Global InfoSec. Scoring in progress.",
            "recommended_action": "Complete technical scoring and down-select to 2 finalists",
            "trigger_source": "User (Compliance)",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-SEC-01", "SUP-SEC-02", "SUP-SEC-03"]
            })
        },
        {
            "case_id": "CASE-008",
            "name": "HRIS Platform Selection",
            "category_id": "SAAS",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "summary_text": "Evaluating Workday vs Oracle HCM vs SAP SuccessFactors. Demos completed. Pricing proposals under review.",
            "recommended_action": "Synthesize scores and pricing for finalist selection",
            "trigger_source": "User (New Selection)",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            # FIX: Use supplier IDs instead of text names
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-SAAS-01", "SUP-SAAS-02", "SUP-SAAS-03"]
            })
        },

        # ============================================================
        # DTP-04 Cases (Negotiation) - Need DTP-01 + DTP-02 + DTP-03 decisions + finalists
        # ============================================================
        {
            "case_id": "CASE-005",
            "name": "Data Center Co-location",
            "category_id": "INFRASTRUCTURE",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "summary_text": "Expansion of US East region. Equinix selected as preferred. Negotiating power rates and cross-connect fees.",
            "recommended_action": "Finalize terms. leverage Digital Realty quote to reduce Equinix NRCs.",
            "trigger_source": "User (Expansion)",
            "supplier_id": "Equinix",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-03": {
                    "evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "finalist_suppliers": [
                    {"id": "SUP-DC-01", "name": "Equinix", "score": 8.9},
                    {"id": "SUP-DC-02", "name": "Digital Realty", "score": 8.5}
                ],
                "selected_supplier_id": "SUP-DC-01",
                "selected_supplier_name": "Equinix"
            })
        },
        {
            "case_id": "CASE-006",
            "name": "Microsoft EA Renewal",
            "category_id": "SOFTWARE",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "summary_text": "3-year Enterprise Agreement renewal. Moving from E3 to E5 licenses. Microsoft proposing 15% uplift.",
            "recommended_action": "Negotiate discount on E5 step-up and Azure commit credits",
            "trigger_source": "Signal (Renewal)",
            "supplier_id": "Microsoft",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Tactical", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-03": {
                    "evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "finalist_suppliers": [
                    {"id": "SUP-SW-01", "name": "Microsoft", "score": 8.5}
                ],
                "selected_supplier_id": "SUP-SW-01",
                "selected_supplier_name": "Microsoft"
            })
        },

        # ============================================================
        # DTP-05 Case (Internal Approval) - NEW
        # ============================================================
        {
            "case_id": "CASE-011",
            "name": "Cloud Migration - Internal Approval",
            "category_id": "CLOUD",
            "dtp_stage": "DTP-05",
            "status": "In Progress",
            "summary_text": "AWS selected as cloud provider. Contract terms negotiated ($2.1M/3yr). Awaiting CFO and CIO sign-off.",
            "recommended_action": "Complete stakeholder approval checklist",
            "trigger_source": "System (Stage Advance)",
            "supplier_id": "AWS",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-03": {
                    "evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-04": {
                    "award_supplier_id": {"answer": "AWS", "decided_by_role": "User", "status": "final"},
                    "final_savings_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "legal_approval": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "selected_supplier_id": "SUP-CL-01",
                "selected_supplier_name": "AWS",
                "negotiated_value": 2100000,
                "contract_term_years": 3,
                "savings_achieved": 400000,
                "approvers_required": ["CFO", "CIO", "VP IT Operations"]
            })
        },

        # ============================================================
        # DTP-06 Case (Implementation) - NEW
        # ============================================================
        {
            "case_id": "CASE-012",
            "name": "SOC Services - Implementation",
            "category_id": "SECURITY",
            "dtp_stage": "DTP-06",
            "status": "In Progress",
            "summary_text": "SecureNet Defense contract signed. Implementation in progress. Go-live scheduled for Q2 2026.",
            "recommended_action": "Monitor implementation milestones and KPIs",
            "trigger_source": "System (Stage Advance)",
            "supplier_id": "SecureNet Defense",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-03": {
                    "evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-04": {
                    "award_supplier_id": {"answer": "SecureNet Defense", "decided_by_role": "User", "status": "final"},
                    "final_savings_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "legal_approval": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-05": {
                    "stakeholder_signoff": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "selected_supplier_id": "SUP-SEC-01",
                "selected_supplier_name": "SecureNet Defense",
                "contract_signed_date": "2026-01-15",
                "go_live_date": "2026-04-01",
                "contract_value": 241000,
                "implementation_milestones": [
                    {"name": "Onboarding Complete", "due": "2026-02-15", "status": "pending"},
                    {"name": "Log Integration", "due": "2026-03-01", "status": "pending"},
                    {"name": "Go-Live", "due": "2026-04-01", "status": "pending"}
                ]
            })
        }
    ]


    for case_data in cases_data:
        existing = session.exec(select(CaseState).where(CaseState.case_id == case_data["case_id"])).first()
        if existing:
            # Update
            for k, v in case_data.items():
                setattr(existing, k, v)
        else:
            # Create with findings
            findings = []
            
            if case_data["case_id"] == "CASE-001":  # IT Managed Services
                findings = [
                    {"type": "market_data", "text": "Benchmark: IT Managed Services $800-1,200/user/year for full outsourcing."},
                    {"type": "pricing", "text": "Current contract at $1,100/user - above market median."},
                    {"type": "leverage", "text": "Accenture and Infosys actively bidding in this space with competitive rates."}
                ]
            elif case_data["case_id"] == "CASE-005":  # Data Center
                findings = [
                    {"type": "market_data", "text": "Benchmark: $180-220/kW is standard for NJ market."},
                    {"type": "quote", "text": "Alternative Quote: Digital Realty offering $42,000 MRC (vs Equinix $45,000)."},
                    {"type": "leverage", "text": "Equinix has 15% vacancy in NY4, potentially open to aggressive terms."}
                ]
            elif case_data["case_id"] == "CASE-006":  # Microsoft EA
                findings = [
                    {"type": "usage_data", "text": "E3 License utilization at 98%."},
                    {"type": "pricing", "text": "Azure commit shortfall of $50k in previous term."},
                    {"type": "leverage", "text": "Microsoft fiscal year end is June 30 - likely to offer deep discount for early sign-off."}
                ]
            elif case_data["case_id"] == "CASE-002":  # Hardware
                findings = [
                    {"type": "quote", "text": "Lenovo Quote: 18% off list for 2500 units."},
                    {"type": "quote", "text": "HP Quote: 12% off list but includes 3-year onsite support."},
                    {"type": "market_data", "text": "Laptop component prices trending down (SSD/RAM)."}
                ]
            elif case_data["case_id"] == "CASE-007":  # SD-WAN
                findings = [
                    {"type": "market_data", "text": "SD-WAN hardware: $200-400/site/month; licensing: $100-300/site/month."},
                    {"type": "leverage", "text": "Cisco and VMware competing aggressively for enterprise deals."}
                ]
            elif case_data["case_id"] == "CASE-011":  # Cloud Approval
                findings = [
                    {"type": "approval_status", "text": "CFO approval pending - budget allocation confirmed."},
                    {"type": "approval_status", "text": "CIO approval pending - technical review complete."}
                ]
            elif case_data["case_id"] == "CASE-012":  # SOC Implementation
                findings = [
                    {"type": "implementation", "text": "Onboarding kickoff scheduled for 2026-02-01."},
                    {"type": "implementation", "text": "Log integration design document received."}
                ]
                
            case_data["key_findings"] = json.dumps(findings)
            session.add(CaseState(**case_data))
    
    session.commit()
    print(f"  [OK] Seeded 12 cases (DTP-01 through DTP-06).")


def seed_suppliers(session: Session):
    """Seed comprehensive list of IT Suppliers - ALL CATEGORIES."""
    print("Seeding IT suppliers...")
    
    suppliers = [
        # ============================================================
        # IT Services (CASE-001)
        # ============================================================
        {"id": "SUP-IT-01", "name": "TechCorp Solutions", "cat": "IT_SERVICES", "score": 7.8, "trend": "stable"},
        {"id": "SUP-IT-02", "name": "Global Systems Inc", "cat": "IT_SERVICES", "score": 6.5, "trend": "declining"},
        # NEW: Additional IT Services suppliers for competitive landscape
        {"id": "SUP-IT-03", "name": "Accenture", "cat": "IT_SERVICES", "score": 8.2, "trend": "stable"},
        {"id": "SUP-IT-04", "name": "Infosys", "cat": "IT_SERVICES", "score": 7.9, "trend": "improving"},
        
        # ============================================================
        # Hardware (CASE-002)
        # ============================================================
        {"id": "SUP-HW-01", "name": "Dell Technologies", "cat": "HARDWARE", "score": 8.5, "trend": "stable"},
        {"id": "SUP-HW-02", "name": "HP Inc", "cat": "HARDWARE", "score": 8.0, "trend": "improving"},
        {"id": "SUP-HW-03", "name": "Lenovo", "cat": "HARDWARE", "score": 7.5, "trend": "stable"},
        
        # ============================================================
        # Cloud (CASE-003, CASE-011)
        # ============================================================
        {"id": "SUP-CL-01", "name": "AWS", "cat": "CLOUD", "score": 9.0, "trend": "stable"},
        {"id": "SUP-CL-02", "name": "Microsoft Azure", "cat": "CLOUD", "score": 8.8, "trend": "improving"},
        
        # ============================================================
        # Security (CASE-004, CASE-012)
        # ============================================================
        {"id": "SUP-SEC-01", "name": "SecureNet Defense", "cat": "SECURITY", "score": 9.2, "trend": "stable"},
        {"id": "SUP-SEC-02", "name": "CyberGuard AI", "cat": "SECURITY", "score": 7.5, "trend": "improving"},
        {"id": "SUP-SEC-03", "name": "Global InfoSec", "cat": "SECURITY", "score": 8.1, "trend": "stable"},

        # ============================================================
        # Infrastructure (CASE-005)
        # ============================================================
        {"id": "SUP-DC-01", "name": "Equinix", "cat": "INFRASTRUCTURE", "score": 8.9, "trend": "stable"},
        {"id": "SUP-DC-02", "name": "Digital Realty", "cat": "INFRASTRUCTURE", "score": 8.5, "trend": "stable"},
        
        # ============================================================
        # Telecom (CASE-009)
        # ============================================================
        {"id": "SUP-TEL-01", "name": "AT&T Business", "cat": "TELECOM", "score": 7.2, "trend": "declining"},
        {"id": "SUP-TEL-02", "name": "Verizon Business", "cat": "TELECOM", "score": 7.5, "trend": "stable"},
        # NEW: Additional telecom for global consolidation
        {"id": "SUP-TEL-03", "name": "BT Global", "cat": "TELECOM", "score": 7.0, "trend": "stable"},
        
        # ============================================================
        # Software (CASE-006, CASE-010)
        # ============================================================
        {"id": "SUP-SW-01", "name": "Microsoft", "cat": "SOFTWARE", "score": 8.5, "trend": "stable"},
        {"id": "SUP-SW-02", "name": "GitLab", "cat": "SOFTWARE", "score": 8.2, "trend": "improving"},
        # NEW: Additional SOFTWARE suppliers for DevOps case
        {"id": "SUP-SW-03", "name": "GitHub", "cat": "SOFTWARE", "score": 9.1, "trend": "stable"},
        {"id": "SUP-SW-04", "name": "Jenkins (CloudBees)", "cat": "SOFTWARE", "score": 7.5, "trend": "declining"},
        
        # ============================================================
        # NETWORK - NEW CATEGORY (CASE-007 SD-WAN)
        # ============================================================
        {"id": "SUP-NET-01", "name": "Cisco Viptela", "cat": "NETWORK", "score": 8.7, "trend": "stable"},
        {"id": "SUP-NET-02", "name": "VMware VeloCloud", "cat": "NETWORK", "score": 8.3, "trend": "improving"},
        {"id": "SUP-NET-03", "name": "Palo Alto Prisma", "cat": "NETWORK", "score": 8.5, "trend": "stable"},
        
        # ============================================================
        # SAAS - NEW CATEGORY (CASE-008 HRIS)
        # ============================================================
        {"id": "SUP-SAAS-01", "name": "Workday", "cat": "SAAS", "score": 9.0, "trend": "stable"},
        {"id": "SUP-SAAS-02", "name": "Oracle HCM Cloud", "cat": "SAAS", "score": 8.2, "trend": "stable"},
        {"id": "SUP-SAAS-03", "name": "SAP SuccessFactors", "cat": "SAAS", "score": 7.8, "trend": "declining"},
    ]
    
    # Clear old performance data
    session.exec(delete(SupplierPerformance))
    
    current_date = datetime.now()
    
    for s in suppliers:
        # Generate 6 months of data
        for i in range(6):
            date = (current_date - timedelta(days=30*i)).isoformat()
            # Add some jitter
            score = s["score"]
            if i > 0 and s["trend"] == "declining": score += 0.2 * i  # Was better before
            if i > 0 and s["trend"] == "improving": score -= 0.1 * i  # Was worse before
            
            perf = SupplierPerformance(
                supplier_id=s["id"],
                supplier_name=s["name"],
                category_id=s["cat"],
                overall_score=min(10, max(1, score)),
                measurement_date=date,
                quality_score=score,
                delivery_score=score,
                responsiveness_score=score,
                risk_level="low" if score > 7 else "medium"
            )
            session.add(perf)
            
    session.commit()
    print(f"  [OK] Seeded {len(suppliers)} suppliers across all categories.")


def seed_documents(vector_store):
    """Seed comprehensive text documents (Simulated RAG) - ALL CASES COVERED."""
    print("Seeding documents (this may take a moment)...")
    
    # Reset to ensure valid state
    try:
        vector_store.reset()
        print("  [OK] Reset vector store collection.")
    except Exception as e:
        print(f"  [Warning] Could not reset vector store: {e}")
    
    documents = [
        # ============================================================
        # RFP TEMPLATES (DTP-02 Support)
        # ============================================================
        
        # NEW: IT Managed Services RFP Template (CASE-001)
        {
            "id": "DOC-TMP-ITS-01",
            "name": "RFP Template - IT Managed Services",
            "type": "Template",
            "cat": "IT_SERVICES",
            "content": """
            RFP TEMPLATE: IT MANAGED SERVICES
            
            1. SERVICE SCOPE
            - Service Desk (Tier 1/2/3 Support): 24/7 phone, chat, email
            - Infrastructure Management (Servers, Network, Storage)
            - End-User Computing Support (Laptops, Desktops, Mobile)
            - Security Operations (Patching, Monitoring, Incident Response)
            
            2. SERVICE LEVEL AGREEMENTS
            - P1 Incidents: 15-minute response, 4-hour resolution
            - P2 Incidents: 30-minute response, 8-hour resolution
            - P3 Incidents: 2-hour response, 24-hour resolution
            - Availability: 99.9% uptime SLA for critical systems
            - Customer Satisfaction (CSAT): Target > 85%
            
            3. PRICING MODEL
            - Option A: Fixed Monthly Retainer (per-user)
            - Option B: Per-Device Pricing
            - CSAT Bonus/Penalty provisions (+/- 5% of monthly fee)
            - Transition assistance: Request 60-day overlap period
            
            4. EVALUATION CRITERIA
            - Technical capability (30%)
            - Price (25%)
            - References/Experience (20%)
            - Transition plan (15%)
            - Innovation/Automation (10%)
            """
        },
        {
            "id": "DOC-TMP-SEC-01",
            "name": "RFP Template - Cybersecurity SOC",
            "type": "Template",
            "cat": "SECURITY",
            "content": """
            RFP TEMPLATE: MANAGED SECURITY OPERATIONS CENTER (SOC)
            
            1. SERVICE SCOPE
            - 24/7/365 Security Monitoring
            - Threat Hunting and Incidence Response
            - Log Management (SIEM)
            - Compliance Reporting (SOC2, ISO27001)
            
            2. TECHNICAL REQUIREMENTS
            - Integration with AWS/Azure Cloud Logs
            - Integration with CrowdStrike EDR
            - Mean Time to Detect (MTTD) < 15 minutes
            - Mean Time to Respond (MTTR) < 60 minutes
            
            3. PRICING MODEL
            - Base Monthly Retainer
            - Cost per EPS (Events Per Second) or GB Ingestion
            - Hourly rate for Incident Response (Retainer vs Ad-Hoc)
            """
        },
        {
            "id": "DOC-TMP-CLD-01",
            "name": "RFP Template - Cloud Migration",
            "type": "Template",
            "cat": "CLOUD",
            "content": """
            RFP TEMPLATE: CLOUD MIGRATION SERVICES
            
            1. MIGRATION SCOPE
            - Assessment of On-Prem Workloads (VMware)
            - "Lift and Shift" vs Refactoring Strategy
            - Target Environments: AWS and Azure
            
            2. DELIVERABLES
            - TCO Analysis Report
            - Detailed Migration Plan (Waves 1-5)
            - Landing Zone Design (Security/Networking)
            - Post-Migration Hypercare Period (30 Days)
            
            3. EVALUATION CRITERIA
            - Partner Status (MSP/Advanced Partner)
            - Migration Velocity (VMs per week)
            - Cost Optimization Strategy (Reserved Instances/Savings Plans)
            """
        },
        {
            "id": "DOC-TMP-HW-01",
            "name": "RFP Template - End User Computing (Hardware)",
            "type": "Template",
            "cat": "HARDWARE",
            "content": """
            RFP TEMPLATE: LAPTOP & DESKTOP REFRESH
            
            1. PRODUCT SPECIFICATIONS
            - Standard User Laptop: i5/16GB RAM/512GB SSD
            - Power User Laptop: i7/32GB RAM/1TB SSD
            - Docking Stations (USB-C/Thunderbolt)
            
            2. SERVICES
            - Factory Imaging (Autopilot/Intune)
            - Asset Tagging
            - Global Logistics (Delivery to 15 Countries)
            - E-Waste Disposal / Buyback Program
            
            3. SLA REQUIREMENTS
            - Delivery: < 5 Business Days (Major Hubs)
            - Repair/Replace: Next Business Day Onsite
            """
        },
        {
            "id": "DOC-TMP-DC-01",
            "name": "RFP Template - Data Center Co-location",
            "type": "Template",
            "cat": "INFRASTRUCTURE",
            "content": """
            RFP TEMPLATE: DATA CENTER CO-LOCATION
            
            1. FACILITY REQUIREMENTS
            - Tier III or Tier IV Classification
            - Power Density: 10kW per rack average
            - Redundancy: 2N UPS, N+1 Cooling
            - Compliance: SOC2 Type II, ISO 27001
            
            2. INTERCONNECTION
            - Carrier Neutral Facility
            - Direct Connect availability (AWS/Azure)
            - Cross-Connect SLAs < 24 hours
            
            3. PHYSICAL SECURITY
            - 24/7 Manned Security
            - Biometric Access
            - Man-trap Entry
            """
        },
        
        # NEW: SD-WAN RFP Template (CASE-007)
        {
            "id": "DOC-TMP-SDWAN-01",
            "name": "RFP Template - SD-WAN Solution",
            "type": "Template",
            "cat": "NETWORK",
            "content": """
            RFP TEMPLATE: SD-WAN SOLUTION
            
            1. TECHNICAL REQUIREMENTS
            - Application-aware routing with QoS policies
            - Zero-touch provisioning (ZTP) for branch deployment
            - Integrated security (NGFW, SWG, CASB)
            - Cloud connectivity: AWS Direct Connect, Azure ExpressRoute
            - WAN Optimization and compression
            
            2. DEPLOYMENT SCOPE
            - 150 branch sites globally
            - Replace existing MPLS circuits (maintain as backup)
            - Hybrid overlay with broadband + LTE backup
            - Central orchestration platform
            
            3. PRICING MODEL
            - Per-site licensing (CPE hardware + software)
            - Managed service optional (NOC monitoring)
            - Implementation professional services
            
            4. EVALUATION CRITERIA
            - Technical architecture (30%)
            - Security capabilities (25%)
            - Total Cost of Ownership (25%)
            - Vendor stability and support (20%)
            """
        },
        
        # NEW: DevOps Toolchain RFP Template (CASE-010)
        {
            "id": "DOC-TMP-DEVOPS-01",
            "name": "RFP Template - DevOps Toolchain",
            "type": "Template",
            "cat": "SOFTWARE",
            "content": """
            RFP TEMPLATE: DEVOPS TOOLCHAIN STANDARDIZATION
            
            1. CAPABILITIES REQUIRED
            - Source Control: Git-based with branching strategies
            - CI/CD Pipelines: Build, test, deploy automation
            - Artifact Management: Container registry, package management
            - Security Scanning: SAST/DAST integration
            - Container Orchestration: Kubernetes support
            
            2. INTEGRATION REQUIREMENTS
            - Azure DevOps / AWS CodePipeline compatibility
            - Kubernetes deployment support (EKS/AKS/GKE)
            - JIRA / ServiceNow integration for tracking
            - SSO via SAML/OIDC
            
            3. LICENSING MODEL
            - Per-developer seat (named vs concurrent)
            - Enterprise self-hosted vs SaaS cloud-hosted
            - Support tier (Standard/Premium/Enterprise)
            
            4. EVALUATION CRITERIA
            - Feature completeness (30%)
            - Developer experience/adoption (25%)
            - Security and compliance (25%)
            - Total cost (20%)
            """
        },
        
        # NEW: HRIS RFP Template (CASE-008)
        {
            "id": "DOC-TMP-HRIS-01",
            "name": "RFP Template - HRIS Platform",
            "type": "Template",
            "cat": "SAAS",
            "content": """
            RFP TEMPLATE: HUMAN RESOURCES INFORMATION SYSTEM (HRIS)
            
            1. FUNCTIONAL REQUIREMENTS
            - Core HR: Employee Records, Org Charts, Workflows
            - Payroll Processing: Global/Multi-country support
            - Benefits Administration: Open enrollment, life events
            - Talent Management: Recruiting, Performance, Learning
            - Workforce Analytics: Dashboards, reporting, predictive
            
            2. TECHNICAL REQUIREMENTS
            - Single Sign-On (SSO) via SAML/OIDC
            - API integrations: Payroll providers, benefits vendors
            - Mobile app for employee self-service
            - Data residency options (US, EU, APAC)
            
            3. EVALUATION CRITERIA
            - Total Cost of Ownership (5-year) - 25%
            - Implementation timeline and risk - 20%
            - User experience (Gartner Peer Insights) - 20%
            - Global payroll coverage - 20%
            - Integration flexibility - 15%
            """
        },

        # ============================================================
        # PROPOSALS (DTP-03/04 Support)
        # ============================================================
        
        # Cloud Proposals (CASE-003)
        {
            "id": "DOC-PROP-CASE-003-AWS",
            "name": "Proposal - AWS Professional Services",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-003",
            "content": """
            PROPOSAL: MIGRATION ACCELERATION PROGRAM (MAP)
            SUPPLIER: AWS
            
            APPROACH:
            We propose a 3-phase migration using the "Migration Acceleration Program" (MAP).
            
            1. ASSESS: Migration Readiness Assessment (MRA) - Funded 100% by AWS
            2. MOBILIZE: Landing Zone creation and Pilot Apps - Funded 50% by AWS
            3. MIGRATE: Wave-based migration factory
            
            FINANCIALS:
            - Estimated Annual Spend: $2.5M
            - MAP Credits: $400,000 in credits based on commitment
            - Professional Services Estimate: $500,000 (net of funding)
            """
        },
        {
            "id": "DOC-PROP-CASE-003-AZURE",
            "name": "Proposal - Microsoft Azure",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-003",
            "content": """
            PROPOSAL: AZURE MIGRATION & MODERNIZATION
            SUPPLIER: Microsoft
            
            VALUE PROPOSITION:
            Leverage your existing Windows Server/SQL licensing with Azure Hybrid Benefit (AHB) for 40% savings.
            
            PROGRAM:
            Azure Migration & Modernization Program (AMMP) provides direct engineering support and partner funding.
            
            FINANCIALS:
            - Estimated Annual Spend: $2.4M
            - AHB Savings: ~$800,000 per year
            - Partner Funding: $100,000 for assessment
            """
        },
        
        # Data Center Proposal (CASE-005)
        {
            "id": "DOC-PROP-CASE-005-EQ",
            "name": "Proposal - Equinix (Preferred)",
            "type": "Proposal",
            "cat": "INFRASTRUCTURE",
            "case_id": "CASE-005",
            "content": """
            PROPOSAL: DC EXPANSION (US-EAST)
            SUPPLIER: Equinix
            
            SITE: NY4 (Secaucus, NJ)
            
            SPACE & POWER:
            - 20 Cabinets (Standard 4kW)
            - 5 Cabinets (High Density 10kW)
            
            PRICING:
            - MRC (Monthly): $45,000
            - NRC (Setup): $25,000
            - Cross Connects: $300/month each
            
            TERMS:
            - 36 Month Initial Term
            - 3% Annual Escalator
            """
        },
        
        # Cybersecurity Proposals (CASE-004)
        {
            "id": "DOC-PROP-CASE-004-A",
            "name": "Proposal - SecureNet Defense (Premium)",
            "type": "Proposal",
            "cat": "SECURITY",
            "case_id": "CASE-004",
            "content": """
            PROPOSAL: MANAGED SOC SERVICES
            SUPPLIER: SecureNet Defense
            
            EXECUTIVE SUMMARY:
            SecureNet offers a white-glove, 24/7 SOC service utilizing our US-based analysts.
            
            SOLUTION:
            - Tooling: Proprietary "SecureOne" Platform + Splunk
            - Staffing: Dedicated Tier 3 Analyst assigned to account
            
            SLA COMMITMENTS:
            - MTTD: 10 minutes
            - MTTR: 30 minutes
            
            PRICING:
            - Setup: $25,000
            - Monthly Service: $18,000
            - Total Year 1: $241,000
            """
        },
        {
            "id": "DOC-PROP-CASE-004-B",
            "name": "Proposal - CyberGuard AI (Budget)",
            "type": "Proposal",
            "cat": "SECURITY",
            "case_id": "CASE-004",
            "content": """
            PROPOSAL: AI-DRIVEN MDR
            SUPPLIER: CyberGuard AI
            
            EXECUTIVE SUMMARY:
            CyberGuard leverages automation to deliver high-speed detection at a fraction of the cost.
            
            SOLUTION:
            - Tooling: Cloud-Native SIEM (Elastic)
            - Staffing: Shared Analyst Pool (Global)
            
            SLA COMMITMENTS:
            - MTTD: 5 minutes (Automated)
            - MTTR: 2 hours (Human verification)
            
            PRICING:
            - Setup: $5,000
            - Monthly Service: $9,500
            - Total Year 1: $119,000
            """
        },
        
        # HRIS Proposals (CASE-008) - ALL THREE VENDORS
        {
            "id": "DOC-PROP-CASE-008-A",
            "name": "Proposal - Workday",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-008",
            "content": """
            PROPOSAL: HUMAN CAPITAL MANAGEMENT
            SUPPLIER: Workday
            
            SCOPE:
            Core HR, Benefits, Compensation, Talent Management.
            
            PRICING:
            - Subscription: $45 PEPM (Per Employee Per Month)
            - Implementation: $1.2M Fixed Fee (Partner led)
            
            KEY DIFFERENTIATORS:
            - Unified Data Core (single source of truth)
            - Best-in-class Mobile App
            - Strong in North America market
            """
        },
        # NEW: Oracle HCM Proposal (CASE-008)
        {
            "id": "DOC-PROP-CASE-008-B",
            "name": "Proposal - Oracle HCM Cloud",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-008",
            "content": """
            PROPOSAL: ORACLE HCM CLOUD
            SUPPLIER: Oracle
            
            SOLUTION OVERVIEW:
            Oracle HCM Cloud provides a complete suite with native financials integration.
            
            SCOPE:
            Core HR, Global Payroll, Talent, Workforce Management
            
            PRICING:
            - Subscription: $38 PEPM
            - Implementation: $950,000 (Oracle Consulting)
            
            DIFFERENTIATORS:
            - Deep ERP Integration (if using Oracle Financials)
            - Strong global payroll coverage (190+ countries)
            - AI-powered analytics
            """
        },
        # NEW: SAP SuccessFactors Proposal (CASE-008)
        {
            "id": "DOC-PROP-CASE-008-C",
            "name": "Proposal - SAP SuccessFactors",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-008",
            "content": """
            PROPOSAL: SAP SUCCESSFACTORS
            SUPPLIER: SAP
            
            SOLUTION OVERVIEW:
            SuccessFactors excels in talent management with strong analytics.
            
            SCOPE:
            Employee Central, Recruiting, Performance & Goals, Learning
            
            PRICING:
            - Subscription: $35 PEPM
            - Implementation: $800,000 (Partner led - Deloitte/Accenture)
            
            DIFFERENTIATORS:
            - Best-in-class Learning Management System
            - SAP S/4HANA integration for ERP customers
            - Strong in EMEA compliance (GDPR native)
            """
        },
        
        # Microsoft EA Proposal (CASE-006)
        {
            "id": "DOC-PROP-CASE-006-MSFT",
            "name": "Proposal - Microsoft EA Renewal (2025)",
            "type": "Proposal",
            "cat": "SOFTWARE",
            "case_id": "CASE-006",
            "content": """
            PROPOSAL: MICROSOFT ENTERPRISE AGREEMENT RENEWAL
            SUPPLIER: Microsoft
            
            EXECUTIVE SUMMARY:
            Renewal of EA Enrollment #12345678 for 3-year term.
            
            BOM (Bill of Materials):
            1. Microsoft 365 E3 - 5,000 Users (Step-up to E5 available)
            2. Azure Monetary Commitment - $2.4M (Annual)
            3. Github Enterprise - 500 Users
            
            PRICING:
            - M365 E3: $32/user/month (Prior term was $30)
            - M365 E5 Step-up: Add $25/user/month
            - Azure P1: Standard consumption rates (No additional discount)
            
            TERMS:
            - 3 Year Term, Annual Payments
            - Price Protection: Yes for Year 1, 5% cap Y2/Y3
            """
        },
        
        # ============================================================
        # MARKET REPORTS (DTP-01 Support)
        # ============================================================
        
        # NEW: IT Managed Services Market Report (CASE-001)
        {
            "id": "DOC-MKT-ITS-01",
            "name": "IT Managed Services Market Report 2025",
            "type": "Market Report",
            "cat": "IT_SERVICES",
            "content": """
            2025 IT MANAGED SERVICES MARKET INTELLIGENCE
            
            PRICING BENCHMARKS:
            - Full IT Outsourcing: $800-1,200 per user/year
            - Service Desk Only: $150-250 per user/year
            - Infrastructure Management: $50-100 per device/month
            - Security Operations Add-on: $100-200 per user/year
            
            NEGOTIATION LEVERS:
            - Multi-year commitment (3-5 years) for 10-15% discount
            - CSAT-linked pricing (bonus/penalty provisions)
            - Transition assistance credits (60-90 days overlap)
            - Automation investment commitments from provider
            
            KEY PROVIDERS:
            - TechCorp Solutions: Mid-market focus, competitive pricing
            - Accenture: Enterprise scale, premium pricing
            - Infosys: Cost-competitive, strong automation
            - Global Systems Inc: Regional player, declining market share
            """
        },
        {
            "id": "DOC-MKT-TEL-01",
            "name": "Telecom Market Report 2025",
            "type": "Market Report",
            "cat": "TELECOM",
            "content": """
            2025 TELECOM SOURCING REPORT
            
            PRICE BENCHMARKS for SD-WAN:
            - Hardware: $200-400 per site/month
            - Licensing: $100-300 per site/month
            
            SIP TRUNKING:
            - US: $4-6 per concurrent call path
            - EU: €5-8 per concurrent call path
            
            NEGOTIATION LEVERS:
            - Commit to 36-month term for 15-20% discount.
            - Waive NRCs (Non-Recurring Costs) is standard market practice for deals >$50k.
            """
        },
        {
            "id": "DOC-MKT-FLT-01",
            "name": "Global Fleet Market Report 2025",
            "type": "Market Report",
            "cat": "LOGISTICS",
            "content": """
            2025 FLEET MANAGEMENT MARKET INTELLIGENCE
            
            KEY TRENDS:
            1. EV Transition: Corporate fleets targeting 40% EV mix by 2027.
            2. Lease vs Buy: Operating Leases remaining preferred for flexibility.
            
            BENCHMARK PRICING:
            - Sedan (Mid-size): $450-550/month (36mo/45k miles)
            - SUV (Compact): $550-650/month
            - Maintenance Management: $30-50/vehicle/month
            
            MAJOR PLAYERS:
            - Enterprise Fleet Management
            - Wheels Donlen
            - LeasePlan
            """
        },
        
        # ============================================================
        # CONTRACT TEMPLATES (DTP-05 Support)
        # ============================================================
        {
            "id": "DOC-CTR-MSA-TMP",
            "name": "Template - Master Services Agreement (MSA)",
            "type": "Contract Template",
            "cat": "LEGAL",
            "content": """
            MASTER SERVICES AGREEMENT (MSA) TEMPLATE
            
            1. DEFINITIONS
            "Services" means the professional services to be performed by Supplier.
            "Deliverables" means the work product created by Supplier.
            
            2. INTELLECTUAL PROPERTY
            Client shall own all right, title, and interest in and to all Deliverables.
            
            3. CONFIDENTIALITY
            Each party agrees to hold the other's Confidential Information in strict confidence.
            
            4. TERM AND TERMINATION
            This Agreement shall commence on the Effective Date and continue for a period of 36 months.
            Client may terminate for convenience with 30 days prior written notice.
            """
        },
        {
            "id": "DOC-CTR-SOW-SD-01",
            "name": "Template - Service Desk SOW",
            "type": "Contract Template",
            "cat": "IT_SERVICES",
            "content": """
            STATEMENT OF WORK (SOW): GLOBAL SERVICE DESK
            
            1. SCOPE OF SERVICES
            - Tier 1 Support (24/7/365) via Phone, Chat, Email
            - Tier 2 Support (Business Hours)
            - Incident Management & Request Fulfillment
            
            2. SERVICE LEVEL AGREEMENTS (SLAs)
            - Speed to Answer (Phone): 80% within 30 seconds
            - First Contact Resolution (FCR): > 70%
            - Abandonment Rate: < 5%
            
            3. PRICING MODEL
            - Per Ticket Pricing or Per User Per Month
            """
        },
        
        # ============================================================
        # IMPLEMENTATION GUIDES (DTP-06 Support)
        # ============================================================
        {
            "id": "DOC-IMPL-CLD-01",
            "name": "Cloud Migration Implementation Guide",
            "type": "Implementation Guide",
            "cat": "CLOUD",
            "content": """
            PROJECT IMPLEMENTATION GUIDE: CLOUD MIGRATION
            
            PHASE 1: LANDING ZONE SETUP (Weeks 1-4)
            - Configure AWS Control Tower / Azure Management Groups
            - Establish Transit Gateway / ExpressRoute
            - Implement IAM Policies and Guardrails
            
            PHASE 2: PILOT MIGRATION (Weeks 5-8)
            - Select 5 non-critical applications
            - Perform migration using CloudEndure / Azure Migrate
            - Validate functionality and performance
            
            Success Criteria:
            - Landing Zone passes CIS Benchmark
            - Pilot apps operational with < 100ms latency
            """
        },
        {
            "id": "DOC-IMPL-SOC-01",
            "name": "SOC Onboarding Checklist",
            "type": "Implementation Guide",
            "cat": "SECURITY",
            "content": """
            ONBOARDING CHECKLIST: MANAGED SOC
            
            1. ACCESS & PERMISSIONS
            [ ] Create readonly user accounts for SOC analysts
            [ ] Whitelist SOC IP addresses
            [ ] Establish secure VPN tunnel
            
            2. LOG INTEGRATION
            [ ] Configure CloudTrail/VPC Flow Logs forwarding
            [ ] Install Endpoint Agents (CrowdStrike/SentinelOne)
            [ ] Configure Firewall/WAF Syslog forwarding
            
            3. PLAYBOOK DEFINITION
            [ ] Define Severity Levels (P1-P4)
            [ ] Establish Escalation Matrix (Phone/Email/SMS)
            [ ] Define Automatic Containment Rules
            """
        }
    ]
    
    for doc in documents:
        try:
            chunks = [doc["content"].strip()]
            vector_store.add_chunks(
                chunks=chunks,
                document_id=doc["id"],
                metadata={
                    "filename": doc["name"],
                    "document_type": doc["type"],
                    "category_id": doc["cat"],
                    "case_id": doc.get("case_id", "")
                }
            )
            print(f"  [OK] Added {doc['name']}")
        except Exception as e:
            print(f"  [Error] Failed to add {doc['name']}: {e}")


def main():
    print("=" * 60)
    print("Initializing IT Demo Data (v2 - ALL FIXES APPLIED)")
    print("=" * 60)
    init_db()
    engine = get_engine()
    
    with Session(engine) as session:
        seed_cases(session)
        seed_suppliers(session)
    
    try:
        vector_store = get_vector_store()
        seed_documents(vector_store)
    except Exception as e:
        print(f"Warning: ChromaDB seeding failed (is Chroma running?): {e}")
    
    print("=" * 60)
    print("Seed complete. 12 cases, 28 suppliers, 20+ documents.")
    print("=" * 60)

if __name__ == "__main__":
    main()
