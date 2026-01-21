#!/usr/bin/env python3
"""
IT Infrastructure Demo Seed Script
10 Robust, End-to-End Playable Cases
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
    """Seed 10 comprehensive IT cases."""
    print("Seeding 10 IT cases...")
    
    cases_data = [
        # DTP-01 Cases (Strategy)
        {
            "case_id": "CASE-001",
            "name": "IT Managed Services Renewal",
            "category_id": "IT_SERVICES",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Global IT Managed Services contract with TechCorp expiring in 90 days. Performance has been stable but pricing is above market.",
            "recommended_action": "Initiate renewal negotiation with competitive pressure",
            "trigger_source": "Signal (Contract Expiry)"
        },
        {
            "case_id": "CASE-002",
            "name": "End-User Hardware Refresh",
            "category_id": "HARDWARE",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Global laptop/desktop refresh cycle (2,500 units). Current standard is Dell. Evaluating move to Lenovo or HP for cost reduction.",
            "recommended_action": "Conduct competitive RFP for 3-year refresh program",
            "trigger_source": "User (Budget Cycle)"
        },
        {
            "case_id": "CASE-009",
            "name": "Global Telecom Consolidation",
            "category_id": "TELECOM",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "summary_text": "Fragmented telecom spend across 15 countries. Goal to consolidate to 1-2 global carriers (AT&T/Verizon/BT) for 20% savings.",
            "recommended_action": "Strategic sourcing event for global consolidation",
            "trigger_source": "Signal (Spend Anomaly)"
        },

        # DTP-02 Cases (Planning)
        {
            "case_id": "CASE-003",
            "name": "Cloud Migration (AWS/Azure)",
            "category_id": "CLOUD",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Strategic initiative to migrate 40% of on-prem workloads to cloud. Defining technical requirements for AWS vs Azure pilot.",
            "recommended_action": "Finalize RFP technical requirements and selection criteria",
            "trigger_source": "User (Strategic)"
        },
        {
            "case_id": "CASE-007",
            "name": "SD-WAN Upgrade",
            "category_id": "NETWORK",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Replacing MPLS circuits with SD-WAN. Requirements gathering phase. Vendors: Cisco Viptela, VMware VeloCloud, Palo Alto Prisma.",
            "recommended_action": "Draft RFP for SD-WAN solution and managed services",
            "trigger_source": "User (Performance)"
        },
        {
            "case_id": "CASE-010",
            "name": "DevOps Toolchain Standards",
            "category_id": "SOFTWARE",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "summary_text": "Standardizing CI/CD pipeline tools (GitHub vs GitLab vs Jenkins). Need to align engineering teams on single platform.",
            "recommended_action": "Prepare evaluation matrix for toolchain consolidation",
            "trigger_source": "User (Standardization)"
        },

        # DTP-03 Cases (Sourcing/Evaluation)
        {
            "case_id": "CASE-004",
            "name": "Cybersecurity SOC Services",
            "category_id": "SECURITY",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "summary_text": "RFP active for 24/7 SOC services. Proposals received from SecureNet, CyberGuard AI, and Global InfoSec. Scoring in progress.",
            "recommended_action": "Complete technical scoring and down-select to 2 finalists",
            "trigger_source": "User (Compliance)"
        },
        {
            "case_id": "CASE-008",
            "name": "HRIS Platform Selection",
            "category_id": "SAAS",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "summary_text": "Evaluating Workday vs Oracle HCM vs SAP SuccessFactors. Demos completed. Pricing proposals under review.",
            "recommended_action": "Synthesize scores and pricing for finalist selection",
            "trigger_source": "User (New Selection)"
        },

        # DTP-04 Cases (Negotiation)
        {
            "case_id": "CASE-005",
            "name": "Data Center Co-location",
            "category_id": "INFRASTRUCTURE",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "summary_text": "Expansion of US East region. Equinix selected as preferred. Negotiating power rates and cross-connect fees.",
            "recommended_action": "Finalize terms. leverage Digital Realty quote to reduce Equinix NRCs.",
            "trigger_source": "User (Expansion)"
        },
        {
            "case_id": "CASE-006",
            "name": "Microsoft EA Renewal",
            "category_id": "SOFTWARE",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "summary_text": "3-year Enterprise Agreement renewal. Moving from E3 to E5 licenses. Microsoft proposing 15% uplift.",
            "recommended_action": "Negotiate discount on E5 step-up and Azure commit credits",
            "trigger_source": "Signal (Renewal)"
        }
    ]

    for case_data in cases_data:
        existing = session.exec(select(CaseState).where(CaseState.case_id == case_data["case_id"])).first()
        if existing:
            # Update
            for k, v in case_data.items():
                setattr(existing, k, v)
        else:
            # Create
            # Initialize empty findings
            # Initialize specific findings based on case ID
            findings = []
            
            if case_data["case_id"] == "CASE-005": # Data Center
                findings = [
                    {"type": "market_data", "text": "Benchmark: $180-220/kW is standard for NJ market."},
                    {"type": "quote", "text": "Alternative Quote: Digital Realty offering $42,000 MRC (vs Equinix $45,000)."},
                    {"type": "leverage", "text": "Equinix has 15% vacancy in NY4, potentially open to aggressive terms."}
                ]
            elif case_data["case_id"] == "CASE-006": # Microsoft EA
                findings = [
                    {"type": "usage_data", "text": "E3 License utilization at 98%."},
                    {"type": "pricing", "text": "Azure commit shortfall of $50k in previous term."},
                    {"type": "leverage", "text": "Microsoft fiscal year end is June 30 - likely to offer deep discount for early sign-off."}
                ]
            elif case_data["case_id"] == "CASE-002": # Hardware
                findings = [
                    {"type": "quote", "text": "Lenovo Quote: 18% off list for 2500 units."},
                    {"type": "quote", "text": "HP Quote: 12% off list but includes 3-year onsite support."},
                    {"type": "market_data", "text": "Laptop component prices trending down (SSD/RAM)."}
                ]
                
            case_data["key_findings"] = json.dumps(findings)
            session.add(CaseState(**case_data))
    
    session.commit()
    print(f"  [OK] Seeded 10 cases.")

def seed_suppliers(session: Session):
    """Seed comprehensive list of IT Suppliers."""
    print("Seeding IT suppliers...")
    
    suppliers = [
        # IT Services
        {"id": "SUP-IT-01", "name": "TechCorp Solutions", "cat": "IT_SERVICES", "score": 7.8, "trend": "stable"},
        {"id": "SUP-IT-02", "name": "Global Systems Inc", "cat": "IT_SERVICES", "score": 6.5, "trend": "declining"},
        
        # Hardware
        {"id": "SUP-HW-01", "name": "Dell Technologies", "cat": "HARDWARE", "score": 8.5, "trend": "stable"},
        {"id": "SUP-HW-02", "name": "HP Inc", "cat": "HARDWARE", "score": 8.0, "trend": "improving"},
        {"id": "SUP-HW-03", "name": "Lenovo", "cat": "HARDWARE", "score": 7.5, "trend": "stable"},
        
        # Cloud
        {"id": "SUP-CL-01", "name": "AWS", "cat": "CLOUD", "score": 9.0, "trend": "stable"},
        {"id": "SUP-CL-02", "name": "Microsoft Azure", "cat": "CLOUD", "score": 8.8, "trend": "improving"},
        
        # Security
        {"id": "SUP-SEC-01", "name": "SecureNet Defense", "cat": "SECURITY", "score": 9.2, "trend": "stable"},
        {"id": "SUP-SEC-02", "name": "CyberGuard AI", "cat": "SECURITY", "score": 7.5, "trend": "improving"}, # New entrant
        {"id": "SUP-SEC-03", "name": "Global InfoSec", "cat": "SECURITY", "score": 8.1, "trend": "stable"},

        # Infrastructure
        {"id": "SUP-DC-01", "name": "Equinix", "cat": "INFRASTRUCTURE", "score": 8.9, "trend": "stable"},
        {"id": "SUP-DC-02", "name": "Digital Realty", "cat": "INFRASTRUCTURE", "score": 8.5, "trend": "stable"},
        
        # Telecom
        {"id": "SUP-TEL-01", "name": "AT&T Business", "cat": "TELECOM", "score": 7.2, "trend": "declining"},
        {"id": "SUP-TEL-02", "name": "Verizon Business", "cat": "TELECOM", "score": 7.5, "trend": "stable"},
        
        # Software
        {"id": "SUP-SW-01", "name": "Microsoft", "cat": "SOFTWARE", "score": 8.5, "trend": "stable"},
        {"id": "SUP-SW-02", "name": "GitLab", "cat": "SOFTWARE", "score": 8.2, "trend": "improving"},
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
            if i > 0 and s["trend"] == "declining": score += 0.2 * i # Was better before
            if i > 0 and s["trend"] == "improving": score -= 0.1 * i # Was worse before
            
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
    print("  [OK] Seeded suppliers.")

def seed_documents(vector_store):
    """Seed comprehensive text documents (Simulated RAG)."""
    print("Seeding documents (this may take a moment)...")
    
    # Reset to ensure valid state
    try:
        vector_store.reset()
        print("  [OK] Reset vector store collection.")
    except Exception as e:
        print(f"  [Warning] Could not reset vector store: {e}")
    
    documents = [
        # --- RFP TEMPLATES (DTP-02 Support) ---
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

        # --- PROPOSALS (CLOUD - CASE-003) ---
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
        
        # --- PROPOSALS (DATA CENTER - CASE-005) ---
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
        
        # --- PROPOSALS (DTP-03 Support for CASE-004 Cybersecurity) ---
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
        
        # --- PROPOSALS (DTP-03 Support for CASE-008 HRIS) ---
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
            - Unified Data Core
            - Best-in-class Mobile App
            """
        },
        
        
        # --- MARKET REPORTS (DTP-01 Support) ---
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
        
        # --- CONTRACT TEMPLATES (DTP-05 Support) ---
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
        
        # --- IMPLEMENTATION GUIDES (DTP-06 Support) ---
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
    print("Initializing IT Demo Data...")
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
    
    print("Seed complete.")

if __name__ == "__main__":
    main()
