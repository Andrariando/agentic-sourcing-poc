#!/usr/bin/env python3
"""
Seed script for synthetic data - Happy Path Demo

This script:
1. Creates/overwrites data/datalake.db with synthetic schema and records
2. Ingests sample docs into ChromaDB at data/chroma_db/
3. Creates CASE-0001 with IT Services category for demo

Run: python backend/scripts/seed_synthetic_data.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session
from backend.persistence.database import get_engine, init_db
from backend.persistence.models import (
    SupplierPerformance, SpendMetric, SLAEvent, CaseState, DocumentRecord
)
from backend.rag.vector_store import get_vector_store


def seed_cases(session: Session):
    """Seed the cases table with CASE-0001."""
    print("Seeding cases...")
    
    # Check if case exists
    from sqlmodel import select
    existing = session.exec(
        select(CaseState).where(CaseState.case_id == "CASE-0001")
    ).first()
    
    if existing:
        print("  CASE-0001 already exists, updating...")
        existing.dtp_stage = "DTP-01"
        existing.status = "In Progress"
        existing.name = "IT Services Contract Renewal"
        existing.summary_text = "Annual IT Services contract approaching renewal. Current supplier TechCorp Solutions."
        existing.key_findings = json.dumps([
            "Contract expires in 35 days",
            "Supplier performance trending stable",
            "Spend within 5% of budget"
        ])
        session.add(existing)
    else:
        case = CaseState(
            case_id="CASE-0001",
            category_id="IT_SERVICES",
            contract_id="CTR-001",
            supplier_id="SUP-001",
            trigger_source="Signal",
            dtp_stage="DTP-01",
            status="In Progress",
            name="IT Services Contract Renewal",
            summary_text="Annual IT Services contract approaching renewal. Current supplier TechCorp Solutions.",
            key_findings=json.dumps([
                "Contract expires in 35 days",
                "Supplier performance trending stable", 
                "Spend within 5% of budget"
            ]),
            recommended_action="Review contract terms and evaluate renewal vs. competitive bid",
        )
        session.add(case)
    
    session.commit()
    print("  ✓ CASE-0001 created/updated")


def seed_suppliers(session: Session):
    """Seed supplier performance data."""
    print("Seeding supplier performance...")
    
    # Clear existing
    from sqlmodel import select, delete
    session.exec(delete(SupplierPerformance))
    
    now = datetime.now()
    
    suppliers = [
        {
            "supplier_id": "SUP-001",
            "supplier_name": "TechCorp Solutions",
            "category_id": "IT_SERVICES",
            "overall_score": 7.8,
            "quality_score": 8.0,
            "delivery_score": 7.5,
            "responsiveness_score": 8.2,
            "cost_variance": 3.5,
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-002",
            "supplier_name": "Global IT Partners",
            "category_id": "IT_SERVICES",
            "overall_score": 7.2,
            "quality_score": 7.0,
            "delivery_score": 7.5,
            "responsiveness_score": 7.0,
            "cost_variance": -2.0,
            "trend": "improving",
            "risk_level": "medium",
        },
        {
            "supplier_id": "SUP-003",
            "supplier_name": "CloudFirst Systems",
            "category_id": "IT_SERVICES",
            "overall_score": 8.2,
            "quality_score": 8.5,
            "delivery_score": 8.0,
            "responsiveness_score": 8.0,
            "cost_variance": 5.0,
            "trend": "stable",
            "risk_level": "low",
        },
    ]
    
    for s in suppliers:
        # Create 6 months of history
        for i in range(6):
            month_date = (now - timedelta(days=30*i)).isoformat()
            perf = SupplierPerformance(
                supplier_id=s["supplier_id"],
                supplier_name=s["supplier_name"],
                category_id=s["category_id"],
                overall_score=s["overall_score"] + (0.1 * (5-i) if s["trend"] == "improving" else 0),
                quality_score=s["quality_score"],
                delivery_score=s["delivery_score"],
                responsiveness_score=s["responsiveness_score"],
                cost_variance=s["cost_variance"],
                trend=s["trend"],
                risk_level=s["risk_level"],
                measurement_date=month_date,
            )
            session.add(perf)
    
    session.commit()
    print(f"  ✓ Created performance records for {len(suppliers)} suppliers")


def seed_spend(session: Session):
    """Seed spend data with one anomaly month."""
    print("Seeding spend data...")
    
    from sqlmodel import delete
    session.exec(delete(SpendMetric))
    
    now = datetime.now()
    
    # Monthly spend for SUP-001 (with one anomaly)
    for i in range(12):
        month_date = now - timedelta(days=30*i)
        period = month_date.strftime("%Y-%m")
        
        # Normal spend ~40,000, anomaly month at index 3
        spend_amount = 48000 if i == 3 else 40000 + (i * 100)
        
        spend = SpendMetric(
            supplier_id="SUP-001",
            category_id="IT_SERVICES",
            contract_id="CTR-001",
            spend_amount=spend_amount,
            currency="USD",
            budget_amount=42000,
            variance_amount=spend_amount - 42000,
            variance_percent=((spend_amount - 42000) / 42000) * 100,
            spend_type="direct",
            period=period,
        )
        session.add(spend)
    
    session.commit()
    print("  ✓ Created 12 months of spend data (with anomaly)")


def seed_sla_events(session: Session):
    """Seed SLA events with some breaches for differentiation."""
    print("Seeding SLA events...")
    
    from sqlmodel import delete
    session.exec(delete(SLAEvent))
    
    now = datetime.now()
    
    # SUP-001: Few minor events
    events_sup1 = [
        {"event_type": "warning", "sla_metric": "response_time", "severity": "low", "days_ago": 45},
        {"event_type": "compliance", "sla_metric": "uptime", "severity": "low", "days_ago": 30},
    ]
    
    # SUP-002: Some breaches (differentiator)
    events_sup2 = [
        {"event_type": "breach", "sla_metric": "response_time", "severity": "medium", "days_ago": 20},
        {"event_type": "breach", "sla_metric": "delivery", "severity": "high", "days_ago": 40},
        {"event_type": "warning", "sla_metric": "quality", "severity": "medium", "days_ago": 15},
    ]
    
    # SUP-003: Clean record
    events_sup3 = [
        {"event_type": "compliance", "sla_metric": "uptime", "severity": "low", "days_ago": 60},
    ]
    
    for supplier_id, events in [("SUP-001", events_sup1), ("SUP-002", events_sup2), ("SUP-003", events_sup3)]:
        for e in events:
            event = SLAEvent(
                supplier_id=supplier_id,
                contract_id="CTR-001" if supplier_id == "SUP-001" else None,
                category_id="IT_SERVICES",
                event_type=e["event_type"],
                sla_metric=e["sla_metric"],
                severity=e["severity"],
                status="resolved",
                event_date=(now - timedelta(days=e["days_ago"])).isoformat(),
            )
            session.add(event)
    
    session.commit()
    print("  ✓ Created SLA events for all suppliers")


def seed_documents(vector_store):
    """Seed ChromaDB with sample documents."""
    print("Seeding documents into ChromaDB...")
    
    docs = [
        {
            "doc_id": "doc-rfx-template-001",
            "filename": "RFP_Template_IT_Services.txt",
            "document_type": "RFx",
            "content": """
REQUEST FOR PROPOSAL (RFP) TEMPLATE - IT SERVICES

1. EXECUTIVE SUMMARY
This section provides an overview of the procurement need, including objectives, scope, and expected outcomes.

2. SCOPE OF WORK
Define the services required, including:
- Technical requirements
- Service levels
- Delivery expectations

3. TECHNICAL REQUIREMENTS
- System compatibility
- Integration needs
- Security requirements
- Performance standards

4. PRICING STRUCTURE
Suppliers should provide:
- Unit pricing
- Volume discounts
- Payment terms
- Price validity period

5. EVALUATION CRITERIA
Proposals will be evaluated based on:
- Technical capability (30%)
- Price (25%)
- Experience (20%)
- Service levels (15%)
- Risk factors (10%)

6. TERMS AND CONDITIONS
Standard terms including:
- Liability limitations
- Indemnification
- Termination clauses
- Confidentiality

7. SUBMISSION INSTRUCTIONS
- Deadline: [Date]
- Format: Electronic submission
- Contact: procurement@company.com
""",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-02", "DTP-03"],
        },
        {
            "doc_id": "doc-benchmark-001",
            "filename": "Market_Benchmark_IT_Services_2025.txt",
            "document_type": "Market Report",
            "content": """
IT SERVICES MARKET BENCHMARK REPORT 2025

EXECUTIVE SUMMARY
The IT services market continues to show competitive pricing with rates stabilizing after the pandemic period.

PRICING BENCHMARKS:

Managed IT Services:
- Small Business: $1,500 - $3,000/month
- Mid-Market: $5,000 - $15,000/month
- Enterprise: $20,000 - $100,000/month

Help Desk Support:
- Tier 1: $15 - $25/ticket
- Tier 2: $35 - $55/ticket
- Tier 3: $75 - $150/ticket

SLA STANDARDS:
- Response Time: 4-8 hours for critical issues
- Uptime Guarantee: 99.5% - 99.9%
- Resolution Time: 24-48 hours for standard issues

CONTRACT TERMS:
- Typical Duration: 24-36 months
- Price Adjustments: 3-5% annual increases common
- Payment Terms: Net 30-45 days standard

KEY TRENDS:
1. Cloud-first approaches driving managed services growth
2. Security services commanding premium pricing
3. AI/automation reducing operational costs
4. Multi-vendor strategies increasing
""",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-01", "DTP-04"],
        },
        {
            "doc_id": "doc-policy-001",
            "filename": "Procurement_Policy_Stage_Gates.txt",
            "document_type": "Policy",
            "content": """
PROCUREMENT POLICY - STAGE GATE REQUIREMENTS

DTP-01 STRATEGY STAGE
Requirements:
- Category analysis complete
- Spend data reviewed
- Market assessment conducted
Approval: Category Manager

DTP-02 PLANNING STAGE  
Requirements:
- Sourcing strategy documented
- Evaluation criteria defined
- Timeline established
Approval: Procurement Manager

DTP-03 SOURCING STAGE
Requirements:
- RFx issued and responses received
- Supplier evaluations complete
- Shortlist prepared
Approval: Sourcing Lead

DTP-04 NEGOTIATION STAGE
Requirements:
- Preferred supplier identified
- Negotiation targets set
- BATNA established
Approval: Senior Procurement Manager

DTP-05 CONTRACTING STAGE
Requirements:
- Terms validated against policy
- Legal review complete
- Contract execution ready
Approval: Legal + CPO

DTP-06 EXECUTION STAGE
Requirements:
- Implementation plan approved
- KPIs defined
- Governance structure established
Approval: Contract Owner

HUMAN APPROVAL REQUIRED:
All stage transitions require explicit human approval.
No automated advancement between stages.
""",
            "category_id": None,
            "dtp_relevance": ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"],
        },
        {
            "doc_id": "doc-contract-001",
            "filename": "Sample_Contract_Terms_IT_Services.txt",
            "document_type": "Contract",
            "content": """
MASTER SERVICES AGREEMENT - SAMPLE KEY TERMS

ARTICLE 1: TERM
- Initial Term: 36 months from Effective Date
- Renewal: Auto-renewal for successive 12-month periods
- Notice Period: 90 days written notice to terminate

ARTICLE 2: PRICING
- Annual Service Fee: $450,000
- Payment Terms: Net 30 days
- Price Adjustment: Fixed for initial term

ARTICLE 3: SERVICE LEVELS
- Response Time: 4 hours for Priority 1 issues
- Resolution Time: 24 hours for Priority 1 issues
- System Uptime: 99.5% monthly minimum
- Penalties: Service credits for SLA breaches

ARTICLE 4: LIABILITY
- Limitation: 12 months of fees maximum
- Exclusions: Gross negligence, willful misconduct
- Insurance: $5M comprehensive coverage required

ARTICLE 5: TERMINATION
- For Convenience: 90 days notice
- For Cause: 30 days cure period
- Effect: Data return, transition assistance

ARTICLE 6: CONFIDENTIALITY
- Duration: 3 years post-termination
- Scope: All non-public information
- Exceptions: Public information, legal requirements
""",
            "supplier_id": "SUP-001",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-05", "DTP-06"],
        },
        {
            "doc_id": "doc-past-rfx-001",
            "filename": "Past_RFP_IT_Services_2024.txt",
            "document_type": "RFx",
            "content": """
PREVIOUS RFP - IT MANAGED SERVICES 2024

SCOPE SUMMARY:
- 24/7 help desk support
- Network monitoring and management
- Security operations center
- Cloud infrastructure management

KEY QUESTIONS ASKED:
1. Describe your escalation process for critical incidents.
2. What certifications do your technicians hold?
3. How do you ensure data security and compliance?
4. What is your approach to proactive monitoring?
5. Describe your disaster recovery capabilities.

EVALUATION RESULTS:
- Received 5 proposals
- Shortlisted 3 vendors
- Award to TechCorp Solutions

LESSONS LEARNED:
- Clearly define SLA metrics upfront
- Include specific security requirements
- Request references from similar-sized clients
- Define transition timeline explicitly
""",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-02", "DTP-03"],
        },
    ]
    
    for doc in docs:
        try:
            vector_store.add_document(
                document_id=doc["doc_id"],
                content=doc["content"],
                metadata={
                    "filename": doc["filename"],
                    "document_type": doc["document_type"],
                    "supplier_id": doc.get("supplier_id"),
                    "category_id": doc.get("category_id"),
                    "dtp_relevance": json.dumps(doc.get("dtp_relevance", [])),
                }
            )
            print(f"  ✓ Added {doc['filename']}")
        except Exception as e:
            print(f"  ⚠ Error adding {doc['filename']}: {e}")
    
    print("  ✓ Documents seeded into ChromaDB")


def main():
    print("\n" + "="*60)
    print("SYNTHETIC DATA SEED SCRIPT - Happy Path Demo")
    print("="*60 + "\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    engine = get_engine()
    
    with Session(engine) as session:
        # Seed structured data
        seed_cases(session)
        seed_suppliers(session)
        seed_spend(session)
        seed_sla_events(session)
    
    # Seed documents
    try:
        vector_store = get_vector_store()
        seed_documents(vector_store)
    except Exception as e:
        print(f"  ⚠ ChromaDB seeding skipped: {e}")
    
    print("\n" + "="*60)
    print("SEED COMPLETE")
    print("="*60)
    print("\nAvailable cases for demo:")
    print("  • CASE-0001 - IT Services Contract Renewal")
    print("\nHappy Path Demo Sequence:")
    print("  1. 'Scan signals' -> Signal Report appears")
    print("  2. 'Score suppliers' -> Scorecard + shortlist")
    print("  3. 'Draft RFx' -> RFx pack + QA tracker")
    print("  4. 'Support negotiation' -> Negotiation plan + targets")
    print("  5. 'Extract key terms' -> Contract handoff packet")
    print("  6. 'Generate implementation plan' -> Checklist + indicators")
    print("\nTo run:")
    print("  1. Start backend: python backend/main.py")
    print("  2. Start frontend: streamlit run frontend/app.py")
    print("  3. Open CASE-0001 and run the prompts above")
    print("")


if __name__ == "__main__":
    main()

