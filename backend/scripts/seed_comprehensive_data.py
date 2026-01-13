#!/usr/bin/env python3
"""
Comprehensive Seed Script for Realistic Sourcing Scenarios

Creates 5 complete cases with:
- Differentiated supplier performance data
- Realistic spend patterns
- SLA events
- Category-specific documents
- Pre-seeded conversation history for later-stage cases

Run: python backend/scripts/seed_comprehensive_data.py
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, select, delete
from backend.persistence.database import get_engine, init_db
from backend.persistence.models import (
    SupplierPerformance, SpendMetric, SLAEvent, CaseState, DocumentRecord
)
from backend.rag.vector_store import get_vector_store


def seed_cases(session: Session):
    """Seed 5 comprehensive cases across different categories and stages."""
    print("Seeding cases...")
    
    cases_data = [
        {
            "case_id": "CASE-0001",
            "category_id": "IT_SERVICES",
            "contract_id": "CTR-IT-001",
            "supplier_id": "SUP-IT-001",
            "trigger_source": "Signal",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "name": "IT Services Contract Renewal",
            "summary_text": "Annual IT Services contract approaching renewal in 35 days. Current supplier TechCorp Solutions showing stable performance.",
            "key_findings": [
                "Contract expires in 35 days",
                "Supplier performance trending stable at 7.8/10",
                "Spend within 5% of budget",
                "No major SLA breaches in past 6 months"
            ],
            "recommended_action": "Review contract terms and evaluate renewal vs. competitive bid"
        },
        {
            "case_id": "CASE-0002",
            "category_id": "OFFICE_SUPPLIES",
            "contract_id": "CTR-OFF-001",
            "supplier_id": "SUP-OFF-001",
            "trigger_source": "Signal",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "name": "Office Supplies Cost Reduction",
            "summary_text": "Spend anomaly detected: Office supplies costs 20% over budget for Q4. Current supplier OfficeMax Pro.",
            "key_findings": [
                "Q4 spend $48,000 vs budget $40,000 (20% over)",
                "Price increases on paper products (+15%)",
                "Delivery frequency increased (weekly vs bi-weekly)",
                "Alternative suppliers available with 10-15% savings"
            ],
            "recommended_action": "Conduct competitive bidding to reduce costs and optimize delivery schedule"
        },
        {
            "case_id": "CASE-0003",
            "category_id": "CLOUD_SERVICES",
            "contract_id": None,
            "supplier_id": None,
            "trigger_source": "User",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "name": "Cloud Infrastructure Migration",
            "summary_text": "Strategic initiative to migrate on-premise infrastructure to cloud. Evaluating AWS, Azure, and Google Cloud.",
            "key_findings": [
                "Current infrastructure: 50 servers, 200TB storage",
                "Estimated cloud spend: $180,000-$250,000 annually",
                "Migration timeline: 6-9 months",
                "Key requirements: Multi-region, 99.99% uptime, SOC2 compliance"
            ],
            "recommended_action": "Issue RFP to AWS, Azure, and GCP with detailed technical requirements"
        },
        {
            "case_id": "CASE-0004",
            "category_id": "MARKETING_SERVICES",
            "contract_id": None,
            "supplier_id": None,
            "trigger_source": "User",
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "name": "Marketing Agency Selection",
            "summary_text": "RFP issued for integrated marketing services. Received 4 proposals, evaluating for shortlist.",
            "key_findings": [
                "4 proposals received from qualified agencies",
                "Budget range: $300,000-$400,000 annually",
                "Key criteria: Digital expertise, B2B experience, creative quality",
                "Shortlist target: 2 agencies for final presentations"
            ],
            "recommended_action": "Evaluate proposals against criteria and prepare shortlist for stakeholder review"
        },
        {
            "case_id": "CASE-0005",
            "category_id": "FACILITIES_MANAGEMENT",
            "contract_id": "CTR-FAC-001",
            "supplier_id": "SUP-FAC-001",
            "trigger_source": "Signal",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "name": "Facilities Management Negotiation",
            "summary_text": "Facilities management contract renewal. Incumbent FacilityPro requesting 8% increase, market shows 3-5% is standard.",
            "key_findings": [
                "Incumbent requesting 8% increase ($96,000 additional)",
                "Market benchmark: 3-5% increases typical",
                "Performance: 8.5/10, strong relationship",
                "Alternative quotes: 5-7% lower than incumbent's ask"
            ],
            "recommended_action": "Negotiate to 4-5% increase using market data and alternative quotes as leverage"
        }
    ]
    
    for case_data in cases_data:
        existing = session.exec(
            select(CaseState).where(CaseState.case_id == case_data["case_id"])
        ).first()
        
        if existing:
            print(f"  Updating {case_data['case_id']}...")
            for key, value in case_data.items():
                if key == "key_findings":
                    setattr(existing, key, json.dumps(value))
                else:
                    setattr(existing, key, value)
            session.add(existing)
        else:
            print(f"  Creating {case_data['case_id']}...")
            case = CaseState(
                **{**case_data, "key_findings": json.dumps(case_data["key_findings"])}
            )
            session.add(case)
    
    session.commit()
    print(f"  [OK] Created/updated {len(cases_data)} cases")


def seed_suppliers(session: Session):
    """Seed supplier performance data for all categories."""
    print("Seeding supplier performance...")
    
    session.exec(delete(SupplierPerformance))
    
    now = datetime.now()
    
    # IT Services suppliers
    it_suppliers = [
        {
            "supplier_id": "SUP-IT-001",
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
            "supplier_id": "SUP-IT-002",
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
            "supplier_id": "SUP-IT-003",
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
    
    # Office Supplies suppliers
    office_suppliers = [
        {
            "supplier_id": "SUP-OFF-001",
            "supplier_name": "OfficeMax Pro",
            "category_id": "OFFICE_SUPPLIES",
            "overall_score": 7.0,
            "quality_score": 7.5,
            "delivery_score": 6.5,
            "responsiveness_score": 7.0,
            "cost_variance": 12.0,  # High variance (trigger)
            "trend": "declining",
            "risk_level": "medium",
        },
        {
            "supplier_id": "SUP-OFF-002",
            "supplier_name": "Corporate Supply Co",
            "category_id": "OFFICE_SUPPLIES",
            "overall_score": 8.0,
            "quality_score": 8.0,
            "delivery_score": 8.5,
            "responsiveness_score": 7.5,
            "cost_variance": -8.0,  # Better pricing
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-OFF-003",
            "supplier_name": "BulkOffice Direct",
            "category_id": "OFFICE_SUPPLIES",
            "overall_score": 7.5,
            "quality_score": 7.0,
            "delivery_score": 8.0,
            "responsiveness_score": 7.5,
            "cost_variance": -10.0,  # Best pricing
            "trend": "improving",
            "risk_level": "low",
        },
    ]
    
    # Cloud Services suppliers
    cloud_suppliers = [
        {
            "supplier_id": "SUP-CLOUD-001",
            "supplier_name": "Amazon Web Services",
            "category_id": "CLOUD_SERVICES",
            "overall_score": 8.8,
            "quality_score": 9.0,
            "delivery_score": 8.5,
            "responsiveness_score": 9.0,
            "cost_variance": 0.0,
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-CLOUD-002",
            "supplier_name": "Microsoft Azure",
            "category_id": "CLOUD_SERVICES",
            "overall_score": 8.7,
            "quality_score": 8.8,
            "delivery_score": 8.5,
            "responsiveness_score": 9.0,
            "cost_variance": -5.0,  # Better pricing
            "trend": "improving",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-CLOUD-003",
            "supplier_name": "Google Cloud Platform",
            "category_id": "CLOUD_SERVICES",
            "overall_score": 8.5,
            "quality_score": 8.5,
            "delivery_score": 8.5,
            "responsiveness_score": 8.5,
            "cost_variance": -8.0,  # Best pricing
            "trend": "improving",
            "risk_level": "low",
        },
    ]
    
    # Marketing Services suppliers
    marketing_suppliers = [
        {
            "supplier_id": "SUP-MKT-001",
            "supplier_name": "Creative Minds Agency",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 8.3,
            "quality_score": 9.0,
            "delivery_score": 7.5,
            "responsiveness_score": 8.5,
            "cost_variance": 10.0,  # Premium pricing
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-MKT-002",
            "supplier_name": "Digital First Marketing",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 8.0,
            "quality_score": 8.0,
            "delivery_score": 8.5,
            "responsiveness_score": 8.0,
            "cost_variance": 0.0,
            "trend": "improving",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-MKT-003",
            "supplier_name": "B2B Marketing Pros",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 7.8,
            "quality_score": 7.5,
            "delivery_score": 8.0,
            "responsiveness_score": 8.0,
            "cost_variance": -12.0,  # Value pricing
            "trend": "stable",
            "risk_level": "medium",
        },
        {
            "supplier_id": "SUP-MKT-004",
            "supplier_name": "Integrated Brand Solutions",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 7.5,
            "quality_score": 7.0,
            "delivery_score": 8.0,
            "responsiveness_score": 7.5,
            "cost_variance": -5.0,
            "trend": "stable",
            "risk_level": "medium",
        },
    ]
    
    # Facilities Management suppliers
    facilities_suppliers = [
        {
            "supplier_id": "SUP-FAC-001",
            "supplier_name": "FacilityPro Services",
            "category_id": "FACILITIES_MANAGEMENT",
            "overall_score": 8.5,
            "quality_score": 8.5,
            "delivery_score": 8.5,
            "responsiveness_score": 9.0,
            "cost_variance": 8.0,  # Requesting high increase
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-FAC-002",
            "supplier_name": "BuildingCare Plus",
            "category_id": "FACILITIES_MANAGEMENT",
            "overall_score": 7.8,
            "quality_score": 8.0,
            "delivery_score": 7.5,
            "responsiveness_score": 8.0,
            "cost_variance": 2.0,  # Market rate
            "trend": "stable",
            "risk_level": "low",
        },
        {
            "supplier_id": "SUP-FAC-003",
            "supplier_name": "Integrated Facilities Group",
            "category_id": "FACILITIES_MANAGEMENT",
            "overall_score": 7.5,
            "quality_score": 7.5,
            "delivery_score": 7.5,
            "responsiveness_score": 7.5,
            "cost_variance": 0.0,  # Competitive pricing
            "trend": "improving",
            "risk_level": "medium",
        },
    ]
    
    all_suppliers = it_suppliers + office_suppliers + cloud_suppliers + marketing_suppliers + facilities_suppliers
    
    for supplier in all_suppliers:
        # Create 6 months of history
        for i in range(6):
            month_date = (now - timedelta(days=30*i)).isoformat()
            
            # Adjust score based on trend
            score_adjustment = 0
            if supplier["trend"] == "improving":
                score_adjustment = 0.1 * (5-i)  # Improving over time
            elif supplier["trend"] == "declining":
                score_adjustment = -0.1 * i  # Declining over time
            
            perf = SupplierPerformance(
                supplier_id=supplier["supplier_id"],
                supplier_name=supplier["supplier_name"],
                category_id=supplier["category_id"],
                overall_score=max(1.0, min(10.0, supplier["overall_score"] + score_adjustment)),
                quality_score=supplier["quality_score"],
                delivery_score=supplier["delivery_score"],
                responsiveness_score=supplier["responsiveness_score"],
                cost_variance=supplier["cost_variance"],
                trend=supplier["trend"],
                risk_level=supplier["risk_level"],
                measurement_date=month_date,
            )
            session.add(perf)
    
    session.commit()
    print(f"  [OK] Created performance records for {len(all_suppliers)} suppliers")


def seed_spend(session: Session):
    """Seed realistic spend data for all cases."""
    print("Seeding spend data...")
    
    session.exec(delete(SpendMetric))
    
    now = datetime.now()
    
    spend_scenarios = [
        # IT Services - stable with one anomaly
        {
            "supplier_id": "SUP-IT-001",
            "category_id": "IT_SERVICES",
            "contract_id": "CTR-IT-001",
            "base_amount": 40000,
            "budget": 42000,
            "anomaly_month": 3,
            "anomaly_amount": 48000,
        },
        # Office Supplies - trending up (trigger case)
        {
            "supplier_id": "SUP-OFF-001",
            "category_id": "OFFICE_SUPPLIES",
            "contract_id": "CTR-OFF-001",
            "base_amount": 3500,
            "budget": 4000,
            "anomaly_month": None,
            "trend_increase": 150,  # Increasing each month
        },
        # Facilities - stable
        {
            "supplier_id": "SUP-FAC-001",
            "category_id": "FACILITIES_MANAGEMENT",
            "contract_id": "CTR-FAC-001",
            "base_amount": 100000,
            "budget": 105000,
            "anomaly_month": None,
        },
    ]
    
    for scenario in spend_scenarios:
        for i in range(12):
            month_date = now - timedelta(days=30*i)
            period = month_date.strftime("%Y-%m")
            
            # Calculate spend amount
            if scenario.get("anomaly_month") == i:
                spend_amount = scenario["anomaly_amount"]
            elif scenario.get("trend_increase"):
                spend_amount = scenario["base_amount"] + (scenario["trend_increase"] * (12-i))
            else:
                spend_amount = scenario["base_amount"] + (i * 50)  # Small variance
            
            budget = scenario["budget"]
            variance = spend_amount - budget
            variance_pct = (variance / budget) * 100
            
            spend = SpendMetric(
                supplier_id=scenario["supplier_id"],
                category_id=scenario["category_id"],
                contract_id=scenario.get("contract_id"),
                spend_amount=spend_amount,
                currency="USD",
                budget_amount=budget,
                variance_amount=variance,
                variance_percent=variance_pct,
                spend_type="direct",
                period=period,
            )
            session.add(spend)
    
    session.commit()
    print("  [OK] Created 12 months of spend data for 3 categories")


def seed_sla_events(session: Session):
    """Seed SLA events with realistic differentiation."""
    print("Seeding SLA events...")
    
    session.exec(delete(SLAEvent))
    
    now = datetime.now()
    
    # Define events for each supplier
    sla_scenarios = [
        # IT Services - SUP-IT-001: Few minor events (good)
        ("SUP-IT-001", "CTR-IT-001", "IT_SERVICES", [
            {"event_type": "warning", "sla_metric": "response_time", "severity": "low", "days_ago": 45},
            {"event_type": "compliance", "sla_metric": "uptime", "severity": "low", "days_ago": 30},
        ]),
        # IT Services - SUP-IT-002: Some breaches (differentiator)
        ("SUP-IT-002", None, "IT_SERVICES", [
            {"event_type": "breach", "sla_metric": "response_time", "severity": "medium", "days_ago": 20},
            {"event_type": "breach", "sla_metric": "delivery", "severity": "high", "days_ago": 40},
            {"event_type": "warning", "sla_metric": "quality", "severity": "medium", "days_ago": 15},
        ]),
        # IT Services - SUP-IT-003: Clean record (best)
        ("SUP-IT-003", None, "IT_SERVICES", [
            {"event_type": "compliance", "sla_metric": "uptime", "severity": "low", "days_ago": 60},
        ]),
        # Office Supplies - SUP-OFF-001: Delivery issues (trigger)
        ("SUP-OFF-001", "CTR-OFF-001", "OFFICE_SUPPLIES", [
            {"event_type": "breach", "sla_metric": "delivery", "severity": "medium", "days_ago": 10},
            {"event_type": "warning", "sla_metric": "delivery", "severity": "low", "days_ago": 25},
            {"event_type": "breach", "sla_metric": "delivery", "severity": "medium", "days_ago": 35},
        ]),
        # Facilities - SUP-FAC-001: Excellent record
        ("SUP-FAC-001", "CTR-FAC-001", "FACILITIES_MANAGEMENT", [
            {"event_type": "compliance", "sla_metric": "service_quality", "severity": "low", "days_ago": 90},
        ]),
    ]
    
    for supplier_id, contract_id, category_id, events in sla_scenarios:
        for e in events:
            event = SLAEvent(
                supplier_id=supplier_id,
                contract_id=contract_id,
                category_id=category_id,
                event_type=e["event_type"],
                sla_metric=e["sla_metric"],
                severity=e["severity"],
                status="resolved",
                event_date=(now - timedelta(days=e["days_ago"])).isoformat(),
            )
            session.add(event)
    
    session.commit()
    print("  [OK] Created SLA events for all suppliers")


def seed_documents(vector_store):
    """Seed comprehensive documents for all categories."""
    print("Seeding documents into ChromaDB...")
    
    documents = [
        # IT Services documents (existing + enhanced)
        {
            "doc_id": "doc-it-rfp-template",
            "filename": "RFP_Template_IT_Services.txt",
            "document_type": "RFx",
            "content": """
REQUEST FOR PROPOSAL (RFP) - IT MANAGED SERVICES

1. EXECUTIVE SUMMARY
Seeking comprehensive IT managed services including 24/7 help desk, network monitoring, security operations, and cloud infrastructure management.

2. SCOPE OF WORK
- 24/7 Tier 1-3 help desk support
- Network monitoring and management
- Security operations center (SOC)
- Cloud infrastructure management (AWS/Azure)
- Patch management and updates
- Backup and disaster recovery

3. TECHNICAL REQUIREMENTS
- Support for 500+ users across 3 locations
- 99.5% uptime SLA minimum
- 4-hour response time for P1 issues
- SOC2 Type II compliance required
- Integration with existing ITSM tools

4. PRICING STRUCTURE
- Monthly service fee (all-inclusive)
- Per-user pricing tiers
- Project-based pricing for migrations
- Volume discounts for multi-year contracts

5. EVALUATION CRITERIA
- Technical capability (30%)
- Pricing (25%)
- Experience with similar clients (20%)
- Service levels and support model (15%)
- Security and compliance (10%)
""",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-02", "DTP-03"],
        },
        {
            "doc_id": "doc-it-benchmark",
            "filename": "IT_Services_Market_Benchmark_2025.txt",
            "document_type": "Market Report",
            "content": """
IT SERVICES MARKET BENCHMARK REPORT 2025

PRICING BENCHMARKS:
Managed IT Services (per user/month):
- Small Business (1-50 users): $75-$150
- Mid-Market (51-500 users): $50-$100
- Enterprise (500+ users): $40-$75

Help Desk Support:
- Tier 1: $15-$25/ticket
- Tier 2: $35-$55/ticket
- Tier 3: $75-$150/ticket

SLA STANDARDS:
- P1 (Critical): 4-hour response, 24-hour resolution
- P2 (High): 8-hour response, 48-hour resolution
- P3 (Medium): 24-hour response, 5-day resolution
- Uptime: 99.5%-99.9% monthly

CONTRACT TERMS:
- Duration: 24-36 months typical
- Annual increases: 3-5% standard
- Termination: 90-day notice typical
""",
            "category_id": "IT_SERVICES",
            "dtp_relevance": ["DTP-01", "DTP-04"],
        },
        # Office Supplies documents
        {
            "doc_id": "doc-office-catalog",
            "filename": "Office_Supplies_Catalog_Pricing.txt",
            "document_type": "Catalog",
            "content": """
OFFICE SUPPLIES CATALOG & PRICING GUIDE

PAPER PRODUCTS:
- Copy Paper (case/10 reams): $45-$55
- Printer Paper (premium): $60-$75
- Notebooks: $1.50-$3.00 each

WRITING INSTRUMENTS:
- Pens (box/12): $8-$15
- Pencils (box/12): $5-$10
- Markers: $12-$20 per set

DESK SUPPLIES:
- Staplers: $8-$25
- Tape dispensers: $5-$15
- File folders (box/100): $15-$25

DELIVERY OPTIONS:
- Standard (5-7 days): Free over $50
- Express (2-3 days): $15 flat rate
- Next-day: $35 flat rate

VOLUME DISCOUNTS:
- $500-$1,000: 5% discount
- $1,000-$2,500: 10% discount
- $2,500+: 15% discount
""",
            "category_id": "OFFICE_SUPPLIES",
            "dtp_relevance": ["DTP-01", "DTP-02"],
        },
        {
            "doc_id": "doc-office-benchmark",
            "filename": "Office_Supplies_Market_Analysis.txt",
            "document_type": "Market Report",
            "content": """
OFFICE SUPPLIES MARKET ANALYSIS 2025

PRICING TRENDS:
- Overall market: Stable with 2-3% annual increases
- Paper products: +5-8% due to supply chain
- Technology accessories: -3-5% due to competition
- Sustainable products: Premium of 10-15%

DELIVERY MODELS:
- Weekly scheduled delivery: Most cost-effective
- Bi-weekly: Standard for mid-size offices
- On-demand: 15-20% premium

COST OPTIMIZATION STRATEGIES:
1. Consolidate suppliers (reduce from 3+ to 1-2)
2. Implement just-in-time delivery
3. Standardize product selections
4. Negotiate volume discounts
5. Consider sustainable alternatives

TYPICAL SAVINGS OPPORTUNITIES:
- Supplier consolidation: 10-15%
- Volume discounts: 5-10%
- Delivery optimization: 5-8%
""",
            "category_id": "OFFICE_SUPPLIES",
            "dtp_relevance": ["DTP-01", "DTP-04"],
        },
        # Cloud Services documents
        {
            "doc_id": "doc-cloud-comparison",
            "filename": "Cloud_Provider_Comparison_Guide.txt",
            "document_type": "Technical Guide",
            "content": """
CLOUD PROVIDER COMPARISON GUIDE

AWS (Amazon Web Services):
Strengths:
- Largest market share and ecosystem
- Most comprehensive service portfolio
- Strong enterprise support
- Extensive global infrastructure

Pricing: Moderate to high
Typical costs: $0.10-$0.20/GB storage, $0.05-$0.15/hour compute

MICROSOFT AZURE:
Strengths:
- Best integration with Microsoft products
- Strong hybrid cloud capabilities
- Enterprise-grade security
- Good for .NET applications

Pricing: Competitive with AWS
Typical costs: $0.08-$0.18/GB storage, $0.04-$0.14/hour compute

GOOGLE CLOUD PLATFORM:
Strengths:
- Best for data analytics and AI/ML
- Competitive pricing
- Strong Kubernetes support
- Innovative technology

Pricing: Generally 10-15% lower than AWS
Typical costs: $0.07-$0.15/GB storage, $0.04-$0.12/hour compute

MIGRATION CONSIDERATIONS:
- Data transfer costs
- Training requirements
- Vendor lock-in risks
- Compliance requirements
- Support models
""",
            "category_id": "CLOUD_SERVICES",
            "dtp_relevance": ["DTP-01", "DTP-02", "DTP-03"],
        },
        {
            "doc_id": "doc-cloud-migration",
            "filename": "Cloud_Migration_Best_Practices.txt",
            "document_type": "Technical Guide",
            "content": """
CLOUD MIGRATION BEST PRACTICES

ASSESSMENT PHASE:
1. Inventory current infrastructure
2. Identify dependencies
3. Assess application compatibility
4. Calculate TCO (Total Cost of Ownership)

PLANNING PHASE:
1. Define migration strategy (lift-and-shift vs. re-architect)
2. Establish timeline and milestones
3. Plan for data migration
4. Define rollback procedures

EXECUTION PHASE:
1. Start with non-critical workloads
2. Implement in waves
3. Monitor performance closely
4. Validate functionality

POST-MIGRATION:
1. Optimize resource allocation
2. Implement cost controls
3. Train staff
4. Establish governance

TYPICAL TIMELINE:
- Assessment: 4-6 weeks
- Planning: 6-8 weeks
- Execution: 3-6 months
- Optimization: Ongoing
""",
            "category_id": "CLOUD_SERVICES",
            "dtp_relevance": ["DTP-02", "DTP-06"],
        },
        # Marketing Services documents
        {
            "doc_id": "doc-marketing-rfp",
            "filename": "Marketing_Agency_RFP_Template.txt",
            "document_type": "RFx",
            "content": """
REQUEST FOR PROPOSAL - INTEGRATED MARKETING SERVICES

SCOPE OF WORK:
- Brand strategy and positioning
- Digital marketing (SEO, SEM, social media)
- Content creation (blog, video, infographics)
- Email marketing campaigns
- Marketing automation
- Analytics and reporting

DELIVERABLES:
- Quarterly marketing strategy
- Monthly content calendar
- Weekly social media posts
- Monthly performance reports
- Campaign creative assets

BUDGET: $300,000 - $400,000 annually

EVALUATION CRITERIA:
- Creative quality and innovation (25%)
- Digital marketing expertise (20%)
- B2B experience (20%)
- Strategic thinking (15%)
- Pricing (10%)
- Team composition (10%)

SUBMISSION REQUIREMENTS:
- Agency credentials and case studies
- Proposed team and bios
- Sample creative work
- Pricing breakdown
- References (3 minimum)
""",
            "category_id": "MARKETING_SERVICES",
            "dtp_relevance": ["DTP-02", "DTP-03"],
        },
        {
            "doc_id": "doc-marketing-evaluation",
            "filename": "Marketing_Agency_Evaluation_Rubric.txt",
            "document_type": "Evaluation Guide",
            "content": """
MARKETING AGENCY EVALUATION RUBRIC

CREATIVE QUALITY (25 points):
- Originality and innovation: 10 points
- Brand alignment: 8 points
- Production quality: 7 points

DIGITAL EXPERTISE (20 points):
- SEO/SEM capabilities: 7 points
- Social media strategy: 7 points
- Marketing automation: 6 points

B2B EXPERIENCE (20 points):
- Relevant case studies: 10 points
- Industry knowledge: 10 points

STRATEGIC THINKING (15 points):
- Strategic approach: 8 points
- Measurement framework: 7 points

PRICING (10 points):
- Value for money: 5 points
- Pricing transparency: 5 points

TEAM (10 points):
- Team experience: 5 points
- Account management: 5 points

SCORING:
- 90-100: Excellent, strong finalist
- 75-89: Good, consider for shortlist
- 60-74: Acceptable, backup option
- Below 60: Not recommended
""",
            "category_id": "MARKETING_SERVICES",
            "dtp_relevance": ["DTP-03"],
        },
        # Facilities Management documents
        {
            "doc_id": "doc-facilities-sow",
            "filename": "Facilities_Management_SOW.txt",
            "document_type": "Contract",
            "content": """
FACILITIES MANAGEMENT - STATEMENT OF WORK

SCOPE OF SERVICES:
1. Building Maintenance
   - HVAC maintenance and repair
   - Plumbing and electrical
   - Structural repairs
   - Preventive maintenance schedule

2. Janitorial Services
   - Daily cleaning of common areas
   - Restroom maintenance
   - Floor care and carpet cleaning
   - Window cleaning (quarterly)

3. Grounds Maintenance
   - Landscaping and lawn care
   - Snow removal (seasonal)
   - Parking lot maintenance
   - Exterior lighting

4. Security Services
   - Access control management
   - Security patrol (after hours)
   - CCTV monitoring
   - Incident response

SERVICE LEVELS:
- Emergency response: 2-hour response time
- Routine maintenance: 24-hour response
- Scheduled maintenance: Per agreed calendar
- Availability: 24/7 emergency contact

PERFORMANCE METRICS:
- Response time compliance: 95%
- Preventive maintenance completion: 100%
- Customer satisfaction: 4.0/5.0 minimum
- Safety incidents: Zero tolerance
""",
            "category_id": "FACILITIES_MANAGEMENT",
            "dtp_relevance": ["DTP-05", "DTP-06"],
        },
        {
            "doc_id": "doc-facilities-benchmark",
            "filename": "Facilities_Management_Market_Rates.txt",
            "document_type": "Market Report",
            "content": """
FACILITIES MANAGEMENT MARKET RATES 2025

PRICING BENCHMARKS (per sq ft/year):
- Class A Office: $8-$12
- Class B Office: $6-$9
- Industrial: $4-$7
- Retail: $7-$11

TYPICAL ANNUAL INCREASES:
- Market standard: 3-5%
- CPI-based: 2-4%
- Fixed (multi-year): 2-3%

SERVICE BREAKDOWN:
- Janitorial: 35-40% of total cost
- Maintenance: 25-30%
- Grounds: 15-20%
- Security: 10-15%
- Management fee: 5-10%

COST OPTIMIZATION:
- Multi-year contracts: 5-8% savings
- Bundled services: 10-15% savings
- Performance-based pricing: Variable
- Technology integration: 8-12% efficiency gain

NEGOTIATION LEVERAGE:
- Market comparisons
- Performance history
- Competitive quotes
- Contract term length
- Service scope flexibility
""",
            "category_id": "FACILITIES_MANAGEMENT",
            "dtp_relevance": ["DTP-01", "DTP-04"],
        },
        # General procurement documents
        {
            "doc_id": "doc-procurement-policy",
            "filename": "Procurement_Policy_DTP_Gates.txt",
            "document_type": "Policy",
            "content": """
PROCUREMENT POLICY - DTP STAGE GATE REQUIREMENTS

DTP-01 STRATEGY:
Requirements:
- Category analysis complete
- Spend data reviewed
- Market assessment conducted
- Sourcing strategy documented
Approval: Category Manager

DTP-02 PLANNING:
Requirements:
- Evaluation criteria defined
- Timeline established
- RFx documents prepared
- Stakeholder alignment
Approval: Procurement Manager

DTP-03 SOURCING:
Requirements:
- RFx issued and responses received
- Supplier evaluations complete
- Shortlist prepared with justification
- Risk assessment completed
Approval: Sourcing Lead

DTP-04 NEGOTIATION:
Requirements:
- Preferred supplier identified
- Negotiation targets set
- BATNA established
- Legal review initiated
Approval: Senior Procurement Manager

DTP-05 CONTRACTING:
Requirements:
- Terms validated against policy
- Legal review complete
- Contract execution ready
- Transition plan approved
Approval: Legal + CPO

DTP-06 EXECUTION:
Requirements:
- Implementation plan approved
- KPIs defined and baselined
- Governance structure established
- Stakeholder communication plan
Approval: Contract Owner

GOVERNANCE:
- All stage transitions require explicit human approval
- No automated advancement between stages
- Audit trail required for all decisions
""",
            "category_id": None,
            "dtp_relevance": ["DTP-01", "DTP-02", "DTP-03", "DTP-04", "DTP-05", "DTP-06"],
        },
    ]
    
    for doc in documents:
        try:
            # Split content into chunks (simple split by paragraphs)
            content = doc["content"].strip()
            # Split by double newlines to get paragraphs
            chunks = [chunk.strip() for chunk in content.split('\n\n') if chunk.strip()]
            
            # If no chunks, use whole content
            if not chunks:
                chunks = [content]
            
            vector_store.add_chunks(
                chunks=chunks,
                document_id=doc["doc_id"],
                metadata={
                    "filename": doc["filename"],
                    "document_type": doc["document_type"],
                    "category_id": doc.get("category_id"),
                    "dtp_relevance": doc.get("dtp_relevance", []),
                }
            )
            print(f"  [OK] Added {doc['filename']} ({len(chunks)} chunks)")
        except Exception as e:
            print(f"  [WARNING] Error adding {doc['filename']}: {e}")
    
    print(f"  [OK] Seeded {len(documents)} documents into ChromaDB")


def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE SYNTHETIC DATA SEED SCRIPT")
    print("="*70 + "\n")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    engine = get_engine()
    
    with Session(engine) as session:
        # Seed all structured data
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
    
    print("\n" + "="*70)
    print("SEED COMPLETE - 5 COMPREHENSIVE CASES CREATED")
    print("="*70)
    print("\nAvailable cases:")
    print("  1. CASE-0001 - IT Services Contract Renewal (DTP-01)")
    print("  2. CASE-0002 - Office Supplies Cost Reduction (DTP-01)")
    print("  3. CASE-0003 - Cloud Infrastructure Migration (DTP-02)")
    print("  4. CASE-0004 - Marketing Agency Selection (DTP-03)")
    print("  5. CASE-0005 - Facilities Management Negotiation (DTP-04)")
    
    print("\nSample chatbot interactions:")
    print("  CASE-0001: 'What's the renewal strategy?'")
    print("  CASE-0002: 'Why are costs increasing?'")
    print("  CASE-0003: 'Compare the cloud providers'")
    print("  CASE-0004: 'Evaluate the marketing proposals'")
    print("  CASE-0005: 'What's our negotiation position?'")
    print("")


if __name__ == "__main__":
    main()
