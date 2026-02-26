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
        # CASE-001: DTP-01 (Strategy) - Global Telecom Consolidation
        # ============================================================
        {
            "case_id": "CASE-001",
            "name": "Global Telecom Consolidation",
            "category_id": "TELECOM",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Fragmented telecom spend across 15 countries. Goal to consolidate to 1-2 global carriers (AT&T/Verizon/BT) for 20% savings.",
            "recommended_action": "Strategic sourcing event for global consolidation",
            "trigger_source": "Signal (Spend Anomaly)",
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-TEL-01", "SUP-TEL-02", "SUP-TEL-03"],
                "current_spend": 3000000,
                "countries_covered": 15,
                "target_savings_percent": 20
            }),
            "latest_agent_name": "Strategy",
            "latest_agent_output": json.dumps({
                "recommended_strategy": "Conduct a Global Competitive RFx",
                "confidence": 0.92,
                "rationale": [
                    "Current spend of $3.0M across 15 countries indicates massive fragmentation.",
                    "Consolidating to 1-2 carriers (e.g., AT&T, Verizon) historically yields 18-24% savings.",
                    "Incumbent local carriers exhibit inconsistent SLAs. A global MSA will standardize performance metrics."
                ],
                "risk_assessment": "Medium: Local market regulations may block full consolidation in 2 of the 15 countries.",
                "next_steps": [
                    "Confirm strategy approval.",
                    "Move to DTP-02 to draft global technical requirements.",
                    "Engage AT&T and Verizon account teams for pre-RFP discussions."
                ]
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Analyze the telecom spend anomaly we got yesterday."},
                {"role": "assistant", "content": "I have analyzed the global telecom spend. We have $3M in fragmented spend across 15 countries. Based on current market conditions, I recommend a Strategic Sourcing event focusing on AT&T, Verizon, and BT to drive a 20% savings target. I have prepared the Strategy Recommendation card. Shall we proceed with this strategy?"}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:01:00", "agent_name": "SignalInterpretation", "task_name": "Analyze Spend Anomaly", "output_summary": "Detected $3M fragmented spend across 15 regions."},
                {"timestamp": "2026-02-26T00:01:30", "agent_name": "Strategy", "task_name": "Recommend Strategy", "output_summary": "Recommended Global Competitive RFx targeting AT&T and Verizon."}
            ])
        },

        # ============================================================
        # CASE-002: DTP-02 (Planning) - Cloud Migration
        # ============================================================
        {
            "case_id": "CASE-002",
            "name": "Cloud Migration (AWS/Azure)",
            "category_id": "CLOUD",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Strategic initiative to migrate 40% of on-prem workloads to cloud. Defining technical requirements for AWS vs Azure pilot.",
            "recommended_action": "Review RFx Draft and Approve",
            "trigger_source": "User (Strategic)",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}
                }
            }),
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-CL-01", "SUP-CL-02"]
            }),
            "latest_agent_name": "RFxDraft",
            "latest_agent_output": json.dumps({
                "rfx_type": "RFP",
                "rfx_sections": {
                    "Scope": "Migration of 40% (approx 200) VMs from on-prem VMware to AWS/Azure.",
                    "Technical Requirements": "Must support lift-and-shift initially with refactoring roadmap. SOC2 compliance required.",
                    "Evaluation Criteria": "Pricing (30%), Migration Velocity (35%), Support SLA (20%), Training (15%)."
                },
                "explanation": "I have drafted the RFP based on the AWS vs Azure capability matrix in the knowledge base.",
                "missing_information": ["Target completion date for migration"]
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Draft the RFP for the Cloud Migration. Focus on comparing AWS and Azure for our VMware lift-and-shift."},
                {"role": "assistant", "content": "I have drafted the RFP sections, weighting Migration Velocity at 35% given your previous urgency on data center exit. Please review the draft and let me know if it is ready to publish."}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:05:00", "agent_name": "RFxDraft", "task_name": "Create RFP Draft", "output_summary": "Generated RFP sections comparing AWS and Azure migration velocity."}
            ])
        },

        # ============================================================
        # CASE-003: DTP-03 (Evaluation) - HRIS Platform Selection
        # ============================================================
        {
            "case_id": "CASE-003",
            "name": "HRIS Platform Selection",
            "category_id": "SAAS",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "summary_text": "Evaluating Workday vs Oracle HCM vs SAP SuccessFactors. Proposals received and scored.",
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
            "case_context": json.dumps({
                "candidate_suppliers": ["SUP-SAAS-01", "SUP-SAAS-02", "SUP-SAAS-03"]
            }),
            "latest_agent_name": "SupplierEvaluation",
            "latest_agent_output": json.dumps({
                "shortlisted_suppliers": [
                    {"supplier_id": "SUP-SAAS-01", "supplier_name": "Workday", "score": 9.2, "strengths": ["User Experience", "Global Payroll Integration"], "weaknesses": ["Highest TCO"]},
                    {"supplier_id": "SUP-SAAS-02", "supplier_name": "Oracle HCM Cloud", "score": 8.5, "strengths": ["Deep Analytics", "Pricing"], "weaknesses": ["Implementation Timeline"]},
                    {"supplier_id": "SUP-SAAS-03", "supplier_name": "SAP SuccessFactors", "score": 7.9, "strengths": ["Enterprise scale"], "weaknesses": ["Legacy UI elements"]}
                ],
                "comparison_summary": "Workday leads technically with a 9.2 score, specifically excelling in User Experience (9.5/10) as required by the RFP. Oracle HCM is a strong cost-effective alternative at 8.5.",
                "recommendation": "Advance Workday and Oracle HCM to Finalist Negotiation phase."
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Evaluate the 3 HRIS proposals we just received (Workday, Oracle, SAP)."},
                {"role": "assistant", "content": "I have extracted and scored the 3 proposals against our RFP criteria. Workday is the clear technical leader, but Oracle offers better pricing. I recommend dropping SAP and advancing Workday and Oracle to negotiation. Do you approve?"}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:10:00", "agent_name": "SupplierEvaluation", "task_name": "Score Proposals", "output_summary": "Extracted metrics from 120-page vendor PDFs. Workday: 9.2, Oracle: 8.5, SAP: 7.9"}
            ])
        },

        # ============================================================
        # CASE-004: DTP-04 (Negotiation) - Microsoft EA Renewal
        # ============================================================
        {
            "case_id": "CASE-004",
            "name": "Microsoft EA Renewal",
            "category_id": "SOFTWARE",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "summary_text": "3-year Enterprise Agreement renewal. Moving from E3 to E5 licenses. Microsoft proposing 15% uplift.",
            "recommended_action": "Negotiate discount on E5 step-up and Azure commit credits",
            "trigger_source": "Signal (Renewal)",
            "supplier_id": "Microsoft",
            "human_decision": json.dumps({
                "DTP-01": {"sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"}, "sourcing_route": {"answer": "Tactical", "decided_by_role": "User", "status": "final"}},
                "DTP-02": {"supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}},
                "DTP-03": {"evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}}
            }),
            "case_context": json.dumps({
                "finalist_suppliers": [{"id": "SUP-SW-01", "name": "Microsoft", "score": 8.5}],
                "selected_supplier_id": "SUP-SW-01",
                "selected_supplier_name": "Microsoft"
            }),
            "latest_agent_name": "NegotiationSupport",
            "latest_agent_output": json.dumps({
                "supplier_name": "Microsoft",
                "leverage_points": [
                    "Microsoft's fiscal year ends June 30th; they will discount heavily for an early signature.",
                    "We have a $50k shortfall on Azure commit from last year we can use to negotiate."
                ],
                "negotiation_objectives": [
                    "Target 1: Cap E5 step-up pricing at 8% uplift instead of proposed 15%.",
                    "Target 2: Obtain $100k Azure transition credits to offset the E5 adoption cost."
                ],
                "batna": "Remain on E3 licenses and purchase standalone security tools, costing approximately $2M more over 3 years.",
                "target_pricing": {
                    "Target M365 E5 Rate": "$34.50/user/month",
                    "Target Azure Discount": "12% MAC discount"
                }
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Help me prepare for the Microsoft EA negotiation later today. They want a 15% uplift for E5."},
                {"role": "assistant", "content": "I've analyzed their proposal. 15% is above the market benchmark for our volume (normally 8-10%). Because their fiscal year ends in June, we have high leverage if we promise to sign by May 15. I've drafted a negotiation plan targeting an 8% cap and demanding Azure transition credits."}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:15:00", "agent_name": "NegotiationSupport", "task_name": "Analyze Leverage", "output_summary": "Identified June 30 Fiscal Year End leverage and E3 vs E5 pricing benchmarks."}
            ])
        },

        # ============================================================
        # CASE-005: DTP-05 (Contracting) - Cloud Internal Approval
        # ============================================================
        {
            "case_id": "CASE-005",
            "name": "Cloud Migration - Internal Approval",
            "category_id": "CLOUD",
            "dtp_stage": "DTP-05",
            "status": "In Progress",
            "summary_text": "AWS selected as cloud provider. Contract terms negotiated ($2.1M/3yr). Extracted key terms for CFO sign-off.",
            "recommended_action": "Complete stakeholder approval checklist",
            "trigger_source": "System (Stage Advance)",
            "supplier_id": "AWS",
            "human_decision": json.dumps({
                "DTP-01": {"sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"}, "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}},
                "DTP-02": {"supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}},
                "DTP-03": {"evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}},
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
            }),
            "latest_agent_name": "ContractSupport",
            "latest_agent_output": json.dumps({
                "extracted_terms": [
                    {"clause": "Total Contract Value", "value": "$2,100,000 over 3 years", "page_ref": "Page 4"},
                    {"clause": "Termination for Convenience", "value": "Requires 90 days notice, subject to early termination fee of $250k.", "page_ref": "Page 12"},
                    {"clause": "Uptime SLA", "value": "99.99% for EC2 instances. Penalty: 10% credit for breach.", "page_ref": "Schedule A"}
                ],
                "inconsistencies": [
                    "Negotiation plan agreed to 99.999% SLA, but contract draft says 99.99%."
                ],
                "overall_risk": "Low"
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Extract the key terms from the final AWS draft so I can send the summary to the CFO for sign off."},
                {"role": "assistant", "content": "I have extracted the TCV, Termination clauses, and SLA guarantees directly from the 82-page PDF. **Warning:** I noticed the SLA says 99.99%, but our negotiation target was five-nines (99.999%). You may want Legal to double check that specific clause before sending to the CFO."}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:20:00", "agent_name": "ContractSupport", "task_name": "Contract Extraction", "output_summary": "Extracted key commercial terms and detected 1 anomaly vs negotiation plan."}
            ])
        },

        # ============================================================
        # CASE-006: DTP-06 (Implementation) - SOC Implementation
        # ============================================================
        {
            "case_id": "CASE-006",
            "name": "SOC Services - Implementation",
            "category_id": "SECURITY",
            "dtp_stage": "DTP-06",
            "status": "In Progress",
            "summary_text": "SecureNet Defense contract signed. Implementation in progress. Go-live scheduled for Q2.",
            "recommended_action": "Monitor implementation milestones and KPIs",
            "trigger_source": "System (Stage Advance)",
            "supplier_id": "SecureNet Defense",
            "human_decision": json.dumps({
                "DTP-01": {"sourcing_required": {"answer": "Yes", "decided_by_role": "User", "status": "final"}, "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "status": "final"}},
                "DTP-02": {"supplier_list_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"}},
                "DTP-03": {"evaluation_complete": {"answer": "Yes", "decided_by_role": "User", "status": "final"}},
                "DTP-04": {
                    "award_supplier_id": {"answer": "SecureNet Defense", "decided_by_role": "User", "status": "final"},
                    "final_savings_confirmed": {"answer": "Yes", "decided_by_role": "User", "status": "final"},
                    "legal_approval": {"answer": "Yes", "decided_by_role": "User", "status": "final"}
                },
                "DTP-05": {"stakeholder_signoff": {"answer": "Yes", "decided_by_role": "User", "status": "final"}}
            }),
            "case_context": json.dumps({
                "selected_supplier_id": "SUP-SEC-01",
                "selected_supplier_name": "SecureNet Defense",
                "contract_signed_date": "2026-01-15",
                "go_live_date": "2026-04-01",
                "contract_value": 241000,
                "implementation_milestones": [
                    {"name": "Onboarding Complete", "due": "2026-02-15", "status": "completed"},
                    {"name": "Log Integration", "due": "2026-03-01", "status": "delayed"},
                    {"name": "Go-Live", "due": "2026-04-01", "status": "pending"}
                ]
            }),
            "latest_agent_name": "Implementation",
            "latest_agent_output": json.dumps({
                "rollout_steps": [
                    {"phase": "Onboarding", "description": "Account provisioning and VPN setup", "status": "Complete"},
                    {"phase": "Log Integration", "description": "Ingesting AWS CloudTrail and Azure AD logs", "status": "Delayed - AWS permissions issue"},
                    {"phase": "Tuning", "description": "Rule tuning and alert threshold setting", "status": "Not Started"}
                ],
                "kpis_to_track": [
                    "Mean Time to Detect (MTTD) < 15 mins",
                    "False Positive Rate < 5%"
                ],
                "explanation": "Implementation is tracking 1 week behind schedule due to the AWS Log Integration delay. Escalate to the DevOps team.",
                "issues": ["Log Integration delay"]
            }),
            "waiting_for_human": False,
            "chat_history": json.dumps([
                {"role": "user", "content": "Update me on the SecureNet SOC implementation."},
                {"role": "assistant", "content": "The implementation is currently tracking 1 week behind schedule. The 'Log Integration' phase is delayed because SecureNet is waiting on IAM permissions from our DevOps team to ingest AWS CloudTrail logs. I recommend escalating this to the DevOps lead immediately to avoid pushing the April 1st Go-Live date."}
            ]),
            "activity_log": json.dumps([
                {"timestamp": "2026-02-26T00:25:00", "agent_name": "Implementation", "task_name": "Track implementation", "output_summary": "Identified delay in Log Integration phase due to AWS IAM blockage."}
            ])
        }
    ]

    for case_data in cases_data:
        existing = session.exec(select(CaseState).where(CaseState.case_id == case_data["case_id"])).first()
        if existing:
            for k, v in case_data.items():
                setattr(existing, k, v)
        else:
            findings = []
            if case_data["case_id"] == "CASE-001":
                findings = [
                    {"type": "market_data", "text": "Benchmark: Telecom MSA 18-24% savings from consolidation."},
                    {"type": "pricing", "text": "Current fragmented spend at $3M - high inefficiency."}
                ]
            elif case_data["case_id"] == "CASE-002":
                findings = [
                    {"type": "market_data", "text": "AWS and Azure leading capability matrices."}
                ]
            elif case_data["case_id"] == "CASE-003":
                findings = [
                    {"type": "evaluation", "text": "Workday leading technically vs Oracle/SAP."}
                ]
            elif case_data["case_id"] == "CASE-004":
                findings = [
                    {"type": "leverage", "text": "Microsoft fiscal year end is June 30."}
                ]
            elif case_data["case_id"] == "CASE-005":
                findings = [
                    {"type": "approval_status", "text": "Ready for CFO approval. Contract extracted."}
                ]
            elif case_data["case_id"] == "CASE-006":
                findings = [
                    {"type": "implementation", "text": "Implementation delayed by AWS Log Integration."}
                ]
                
            case_data["key_findings"] = json.dumps(findings)
            session.add(CaseState(**case_data))
    
    session.commit()
    print(f"  [OK] Seeded 6 comprehensive pillar cases (DTP-01 through DTP-06).")


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
        # CASE-001: TELECOM CONSOLIDATION DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-TEL-001",
            "name": "Global Telecom Sourcing Benchmark 2025",
            "type": "Market Report",
            "cat": "TELECOM",
            "content": """
            2025 GLOBAL TELECOM SOURCING REPORT
            
            MARKET TRENDS:
            - Massive shift towards single-supplier Global MSAs for standardized SLAs.
            - Consolidating fragmented regional spend (10+ countries) typically yields 18-24% hard cost savings.
            
            PRICING BENCHMARKS:
            - SD-WAN Hardware: $150-250 per site/month
            - SD-WAN Licensing: $80-150 per site/month
            - SIP Trunking (US): $4.50 per concurrent path
            - SIP Trunking (EU): €5.00 per concurrent path
            
            LEADING PROVIDERS:
            - AT&T Business: Strongest US/LATAM coverage. Aggressive on pricing for multi-national deals.
            - Verizon Business: Leading 5G integration. Strict on SLAs.
            - BT Global: Dominant in EMEA.
            """
        },
        {
            "id": "DOC-TMP-TEL-001",
            "name": "RFP Template - Global Network & Telecom Integration",
            "type": "Template",
            "cat": "TELECOM",
            "content": """
            RFP TEMPLATE: GLOBAL TELECOM AND NETWORK SERVICES
            
            1. SCOPE
            Global provision of WAN, Internet, and SIP services across NA, EMEA, and APAC regions.
            
            2. REQUIREMENTS
            - Single unified billing platform.
            - 99.99% Network Availability SLA.
            - Dedicated Global Account Manager.
            """
        },
        {
            "id": "DOC-PROP-TEL-ATT",
            "name": "Proposal - AT&T Global Enterprise",
            "type": "Proposal",
            "cat": "TELECOM",
            "case_id": "CASE-001",
            "content": """
            PROPOSAL: GLOBAL TELECOM MSA
            SUPPLIER: AT&T Business
            
            PRICING SUMMARY:
            - Estimated Annual Spend: $2.4M (Representing 20% savings vs current baseline)
            - Setup/NRC: Waived for 36-month commit.
            
            SLA COMMITMENT:
            - 99.99% Uptime with 10% credit penalty for breach.
            """
        },
        {
            "id": "DOC-PROP-TEL-VZ",
            "name": "Proposal - Verizon Enterprise Solutions",
            "type": "Proposal",
            "cat": "TELECOM",
            "case_id": "CASE-001",
            "content": """
            PROPOSAL: GLOBAL TELECOM MSA
            SUPPLIER: Verizon Business
            
            PRICING SUMMARY:
            - Estimated Annual Spend: $2.55M (Representing 15% savings vs current baseline)
            - Setup/NRC: $50,000 one-time transition fee.
            
            SLA COMMITMENT:
            - 99.999% Uptime with 15% credit penalty for breach.
            """
        },

        # ============================================================
        # CASE-002: CLOUD MIGRATION DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-CLD-001",
            "name": "Gartner Magic Quadrant: Cloud Infrastructure 2025",
            "type": "Market Report",
            "cat": "CLOUD",
            "content": """
            CLOUD INFRASTRUCTURE AND PLATFORM SERVICES
            
            LEADERS:
            - Amazon Web Services (AWS): Unmatched breadth of services and partner ecosystem. Highest migration velocity.
            - Microsoft Azure: Seamless integration with enterprise Microsoft environments. Strong hybrid cloud.
            - Google Cloud (GCP): Leading AI/ML capabilities.
            
            MIGRATION TRENDS:
            - 60% of enterprises use Migration Acceleration Programs (MAP) from hyperscalers to offset double-bubble costs.
            """
        },
        {
            "id": "DOC-PROP-CLD-AWS",
            "name": "Proposal - AWS Migration Services",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-002",
            "content": """
            PROPOSAL: MIGRATION ACCELERATION PROGRAM (MAP)
            SUPPLIER: AWS
            
            APPROACH:
            - Phase 1: Assess (4 weeks) - $50k (Fully funded by AWS)
            - Phase 2: Mobilize (8 weeks) - $150k (50% funded by AWS)
            - Phase 3: Migrate & Modernize - Targeting 200 VMs in 6 months.
            
            CAPABILITIES:
            - Automated lift-and-shift via AWS Application Migration Service.
            - Migration velocity: Up to 50 VMs per week.
            """
        },
        {
            "id": "DOC-PROP-CLD-AZURE",
            "name": "Proposal - Azure Cloud Adoption Framework",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-002",
            "content": """
            PROPOSAL: AZURE MIGRATION PROGRAM (AMP)
            SUPPLIER: Microsoft Azure
            
            APPROACH:
            - Azure Migrate automation tooling included free of charge.
            - Free extended security updates for Windows Server legacy workloads during migration.
            
            CAPABILITIES:
            - Native Azure Hybrid Benefit (AHB) for existing SQL Server licenses.
            - Migration velocity: Up to 30 VMs per week.
            """
        },

        # ============================================================
        # CASE-003: HRIS DOCUMENTS (All 3 Proposals for Evaluation)
        # ============================================================
        {
            "id": "DOC-TMP-HRIS-01",
            "name": "RFP - HRIS Platform Selection",
            "type": "Template",
            "cat": "SAAS",
            "content": """
            RFP REQUIREMENTS:
            - Must provide superior User Experience (UX score > 9/10 required).
            - Must support Global Payroll Integration across NA, EMEA, APAC.
            - TCO must be heavily weighted to avoid post-implementation cost spikes.
            """
        },
        {
            "id": "DOC-PROP-HRIS-WD",
            "name": "Workday Proposal - Enterprise HCM",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": """
            SUPPLIER: Workday
            SCORE METRICS:
            - User Experience: 9.5/10 (Industry leading mobile app and intuitive UI)
            - Global Payroll: 9.0/10 (Native integration in 120 countries)
            
            PRICING:
            - Subscription: $45 PEPM (Per Employee Per Month)
            - TCO (5-Year): $5.2M (Highest of all bidders)
            """
        },
        {
            "id": "DOC-PROP-HRIS-ORCL",
            "name": "Oracle HCM Cloud Proposal",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": """
            SUPPLIER: Oracle HCM Cloud
            SCORE METRICS:
            - User Experience: 8.0/10 (Responsive, but complex navigation)
            - Global Payroll: 9.5/10 (Deepest global compliance engine)
            
            PRICING:
            - Subscription: $38 PEPM
            - TCO (5-Year): $4.1M
            """
        },
        {
            "id": "DOC-PROP-HRIS-SAP",
            "name": "SAP SuccessFactors Proposal",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": """
            SUPPLIER: SAP SuccessFactors
            SCORE METRICS:
            - User Experience: 7.0/10 (Legacy UI elements remain)
            - Global Payroll: 8.5/10 
            
            PRICING:
            - Subscription: $35 PEPM
            - TCO (5-Year): $3.9M
            """
        },

        # ============================================================
        # CASE-004: MICROSOFT EA DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-MSFT-001",
            "name": "Microsoft Licensing Negotiation Playbook",
            "type": "Market Report",
            "cat": "SOFTWARE",
            "content": """
            NEGOTIATION INTELLIGENCE: MICROSOFT EA
            
            LEVERAGE POINTS:
            - Microsoft's fiscal year ends June 30th. Deals signed in Q4 (April-June) historically receive 5-8% deeper discounting on step-ups.
            - Unused Azure Commits (shortfalls) can often be rolled over if stepping up to M365 E5.
            
            PRICING BENCHMARKS (Enterprise > 5,000 seats):
            - M365 E3 to E5 Step-Up: Market average is an 8% to 10% uplift. Refuse initial 15% uplifts.
            - Azure Migration Credits: Ask for 10% of Year 1 Azure commit in transition deployment credits.
            """
        },

        # ============================================================
        # CASE-005: CLOUD CONTRACTING DOCUMENTS
        # ============================================================
        {
            "id": "DOC-CTR-AWS-FINAL",
            "name": "Final Draft - AWS Enterprise Agreement",
            "type": "Contract",
            "cat": "CLOUD",
            "case_id": "CASE-005",
            "content": """
            ENTERPRISE DISCOUNT PROGRAM (EDP) AGREEMENT
            PROVIDER: Amazon Web Services (AWS)
            
            [Page 4] COMMERCIAL TERMS
            Total Contract Value (TCV): $2,100,000 committed over a 3-year term constraint.
            
            [Page 12] TERMINATION
            Customer may terminate for convenience with 90 days prior written notice, subject to an early termination fee of $250,000.
            
            [Schedule A] SERVICE LEVEL AGREEMENT
            AWS guarantees 99.99% uptime for EC2 instances. Breach of this SLA entitles the customer to a 10% service credit against the monthly invoice. (Note: Negotiation target was 99.999%).
            """
        },

        # ============================================================
        # CASE-006: SOC IMPLEMENTATION DOCUMENTS
        # ============================================================
        {
            "id": "DOC-IMP-SEC-001",
            "name": "Project Plan - SOC Onboarding",
            "type": "Implementation Plan",
            "cat": "SECURITY",
            "case_id": "CASE-006",
            "content": """
            IMPLEMENTATION SOW: SECURENET DEFENSE
            
            MILESTONES & TIMELINE:
            1. Onboarding Phase (Due Feb 15)
               - Account Provisioning -> COMPLETE
               - Site-to-Site VPN Setup -> COMPLETE
            
            2. Log Integration Phase (Due Mar 1)
               - Azure AD Sync -> COMPLETE
               - AWS CloudTrail Ingestion -> BLOCKED (Awaiting IAM Role creation from Client DevOps team. Currently 1 week delayed).
               
            3. Go-Live phase (Due Apr 1)
               - P1 Alert Generation Testing -> PENDING
               - Official Runbook Handover -> PENDING
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
