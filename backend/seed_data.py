"""
Seed database with synthetic test data.

Creates:
1. Cases at various DTP stages for testing the chatbot
2. Signal-triggered cases (renewal alerts, performance decline)
3. Supporting data (supplier performance, spend, SLA events)
4. Sample documents for RAG testing
"""
import json
from datetime import datetime, timedelta
from uuid import uuid4

from backend.persistence.database import init_db, get_db_session
from backend.persistence.models import (
    CaseState, SupplierPerformance, SpendMetric, SLAEvent,
    IngestionLog, DocumentRecord
)


def generate_case_id() -> str:
    return f"CASE-{uuid4().hex[:6].upper()}"


def seed_all():
    """Seed all test data."""
    print("Seeding database with test data...")
    
    init_db()
    session = get_db_session()
    
    try:
        # Clear existing data
        session.query(CaseState).delete()
        session.query(SupplierPerformance).delete()
        session.query(SpendMetric).delete()
        session.query(SLAEvent).delete()
        session.commit()
        print("  - Cleared existing data")
        
        # Seed suppliers first
        seed_suppliers(session)
        print("  - Seeded supplier performance data")
        
        # Seed spend data
        seed_spend_data(session)
        print("  - Seeded spend data")
        
        # Seed SLA events
        seed_sla_events(session)
        print("  - Seeded SLA events")
        
        # Seed cases at various stages
        seed_manual_cases(session)
        print("  - Seeded manual cases at various DTP stages")
        
        # Seed signal-triggered cases
        seed_signal_cases(session)
        print("  - Seeded signal-triggered cases")
        
        # Seed example completed case with full conversation
        seed_example_case(session)
        print("  - Seeded example completed case (CASE-EXAMPLE-001)")
        
        session.commit()
        print("\nDatabase seeded successfully!")
        print("\nCreated cases:")
        
        cases = session.query(CaseState).all()
        for case in cases:
            print(f"  - {case.case_id}: {case.name} [{case.dtp_stage}] - {case.trigger_source}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding data: {e}")
        raise
    finally:
        session.close()


def seed_suppliers(session):
    """Seed supplier performance data."""
    suppliers = [
        {
            "supplier_id": "SUP-001",
            "supplier_name": "TechVendor Solutions",
            "category_id": "IT-SOFTWARE",
            "overall_score": 8.5,
            "quality_score": 9.0,
            "delivery_score": 8.0,
            "cost_variance": -2.5,
            "responsiveness_score": 8.5,
            "trend": "stable",
            "risk_level": "low"
        },
        {
            "supplier_id": "SUP-002",
            "supplier_name": "CloudFirst Inc",
            "category_id": "IT-CLOUD",
            "overall_score": 7.2,
            "quality_score": 7.5,
            "delivery_score": 7.0,
            "cost_variance": 5.0,
            "responsiveness_score": 7.0,
            "trend": "declining",
            "risk_level": "medium"
        },
        {
            "supplier_id": "SUP-003",
            "supplier_name": "SecureNet Systems",
            "category_id": "IT-SECURITY",
            "overall_score": 9.1,
            "quality_score": 9.5,
            "delivery_score": 8.8,
            "cost_variance": -1.0,
            "responsiveness_score": 9.0,
            "trend": "improving",
            "risk_level": "low"
        },
        {
            "supplier_id": "SUP-004",
            "supplier_name": "DataStore Corp",
            "category_id": "IT-INFRASTRUCTURE",
            "overall_score": 5.8,
            "quality_score": 6.0,
            "delivery_score": 5.5,
            "cost_variance": 12.0,
            "responsiveness_score": 6.0,
            "trend": "declining",
            "risk_level": "high"
        },
        {
            "supplier_id": "SUP-005",
            "supplier_name": "Office Supplies Plus",
            "category_id": "FACILITIES",
            "overall_score": 7.8,
            "quality_score": 8.0,
            "delivery_score": 7.5,
            "cost_variance": 3.0,
            "responsiveness_score": 8.0,
            "trend": "stable",
            "risk_level": "low"
        },
        # ===========================================
        # MARKETING SERVICES - Demo Golden Thread
        # ===========================================
        {
            "supplier_id": "SUP-MKT-GLOBAL",
            "supplier_name": "GlobalBrand Inc",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 6.5,
            "quality_score": 6.0,
            "delivery_score": 6.5,
            "cost_variance": 8.0,
            "responsiveness_score": 6.0,
            "trend": "declining",
            "risk_level": "medium"
        },
        {
            "supplier_id": "SUP-MKT-CREATIVE",
            "supplier_name": "CreativeJuice Agency",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 8.2,
            "quality_score": 8.5,
            "delivery_score": 8.0,
            "cost_variance": -5.0,
            "responsiveness_score": 8.0,
            "trend": "improving",
            "risk_level": "low"
        },
        {
            "supplier_id": "SUP-MKT-DIGITAL",
            "supplier_name": "DigitalFirst Marketing",
            "category_id": "MARKETING_SERVICES",
            "overall_score": 7.8,
            "quality_score": 7.5,
            "delivery_score": 8.0,
            "cost_variance": 2.0,
            "responsiveness_score": 8.5,
            "trend": "stable",
            "risk_level": "low"
        }
    ]
    
    now = datetime.now()
    for sup in suppliers:
        # Add current performance record
        record = SupplierPerformance(
            **sup,
            period_start=(now - timedelta(days=90)).isoformat(),
            period_end=now.isoformat(),
            measurement_date=now.isoformat()
        )
        session.add(record)
        
        # Add historical record (3 months ago)
        historical = SupplierPerformance(
            supplier_id=sup["supplier_id"],
            supplier_name=sup["supplier_name"],
            category_id=sup["category_id"],
            overall_score=sup["overall_score"] + (0.5 if sup["trend"] == "declining" else -0.3),
            quality_score=sup["quality_score"],
            delivery_score=sup["delivery_score"],
            cost_variance=sup["cost_variance"] - 2,
            responsiveness_score=sup["responsiveness_score"],
            trend="stable",
            risk_level="low" if sup["risk_level"] != "high" else "medium",
            period_start=(now - timedelta(days=180)).isoformat(),
            period_end=(now - timedelta(days=90)).isoformat(),
            measurement_date=(now - timedelta(days=90)).isoformat()
        )
        session.add(historical)


def seed_spend_data(session):
    """Seed spend metrics."""
    spend_records = [
        {"supplier_id": "SUP-001", "category_id": "IT-SOFTWARE", "spend_amount": 450000, "period": "2024-Q1"},
        {"supplier_id": "SUP-001", "category_id": "IT-SOFTWARE", "spend_amount": 425000, "period": "2024-Q2"},
        {"supplier_id": "SUP-002", "category_id": "IT-CLOUD", "spend_amount": 280000, "period": "2024-Q1"},
        {"supplier_id": "SUP-002", "category_id": "IT-CLOUD", "spend_amount": 310000, "period": "2024-Q2"},
        {"supplier_id": "SUP-003", "category_id": "IT-SECURITY", "spend_amount": 180000, "period": "2024-Q1"},
        {"supplier_id": "SUP-004", "category_id": "IT-INFRASTRUCTURE", "spend_amount": 520000, "period": "2024-Q1"},
        {"supplier_id": "SUP-005", "category_id": "FACILITIES", "spend_amount": 95000, "period": "2024-Q1"},
        # Marketing Services - Demo Golden Thread
        {"supplier_id": "SUP-MKT-GLOBAL", "category_id": "MARKETING_SERVICES", "spend_amount": 520000, "period": "2024-Q1"},
        {"supplier_id": "SUP-MKT-GLOBAL", "category_id": "MARKETING_SERVICES", "spend_amount": 550000, "period": "2024-Q2"},
        {"supplier_id": "SUP-MKT-CREATIVE", "category_id": "MARKETING_SERVICES", "spend_amount": 0, "period": "2024-Q1"},
    ]
    
    for record in spend_records:
        session.add(SpendMetric(**record, currency="USD"))


def seed_sla_events(session):
    """Seed SLA compliance events."""
    now = datetime.now()
    events = [
        {
            "supplier_id": "SUP-002",
            "event_type": "breach",
            "sla_metric": "response_time",
            "target_value": 24,
            "actual_value": 48,
            "severity": "medium",
            "status": "open",
            "event_date": (now - timedelta(days=5)).isoformat()
        },
        {
            "supplier_id": "SUP-004",
            "event_type": "breach",
            "sla_metric": "uptime",
            "target_value": 99.9,
            "actual_value": 98.5,
            "severity": "high",
            "status": "open",
            "event_date": (now - timedelta(days=2)).isoformat()
        },
        {
            "supplier_id": "SUP-004",
            "event_type": "breach",
            "sla_metric": "delivery_time",
            "target_value": 5,
            "actual_value": 12,
            "severity": "high",
            "status": "acknowledged",
            "event_date": (now - timedelta(days=15)).isoformat()
        },
        {
            "supplier_id": "SUP-001",
            "event_type": "compliance",
            "sla_metric": "quality",
            "target_value": 95,
            "actual_value": 97,
            "severity": "low",
            "status": "resolved",
            "event_date": (now - timedelta(days=30)).isoformat()
        }
    ]
    
    for event in events:
        session.add(SLAEvent(**event))


def seed_manual_cases(session):
    """Seed cases at various DTP stages for testing."""
    now = datetime.now()
    
    cases = [
        # DTP-01: Strategy - New case just started
        {
            "case_id": "CASE-DTP01A",
            "name": "IT Software License Strategy Review",
            "category_id": "IT-SOFTWARE",
            "supplier_id": "SUP-001",
            "contract_id": "CON-SW-2024-001",
            "dtp_stage": "DTP-01",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Annual review of software licensing strategy. Current contract with TechVendor Solutions expires in 90 days.",
            "key_findings": json.dumps([
                "Contract expires in 90 days",
                "Supplier performance is strong (8.5/10)",
                "Spend increased 5% YoY"
            ]),
            "recommended_action": "Recommend strategy analysis"
        },
        
        # DTP-01: Strategy - Waiting for human decision
        {
            "case_id": "CASE-DTP01B",
            "name": "Cloud Services Strategy Decision",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2023-015",
            "dtp_stage": "DTP-01",
            "status": "Waiting for Human Decision",
            "trigger_source": "User",
            "summary_text": "Cloud services contract review. Supplier showing declining performance.",
            "key_findings": json.dumps([
                "Supplier performance declining (7.2/10)",
                "Cost variance +5% over budget",
                "SLA breach on response time"
            ]),
            "recommended_action": "Review strategy recommendation",
            "latest_agent_name": "Strategy",
            "latest_agent_output": json.dumps({
                "recommended_strategy": "RFx",
                "confidence": 0.82,
                "rationale": [
                    "Declining supplier performance indicates need for market evaluation",
                    "Cost overruns suggest renegotiation leverage is limited",
                    "Multiple qualified vendors available in market"
                ]
            }),
            "human_decision": json.dumps({
                # No decision yet for DTP-01, that's why it's waiting
            })
        },
        
        # DTP-02: Planning
        {
            "case_id": "CASE-DTP02A",
            "name": "Security Software RFx Planning",
            "category_id": "IT-SECURITY",
            "supplier_id": "SUP-003",
            "contract_id": "CON-SEC-2024-008",
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Planning phase for security software competitive bid. Strategy approved: RFx.",
            "key_findings": json.dumps([
                "Strategy approved: Competitive RFx",
                "Budget allocated: $200,000",
                "Timeline: 60 days to award"
            ]),
            "recommended_action": "Define RFx requirements",
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes", "decided_by_role": "User", "timestamp": "2024-01-01T10:00:00", "status": "final"},
                    "sourcing_route": {"answer": "Strategic", "decided_by_role": "User", "timestamp": "2024-01-01T10:00:00", "status": "final"}
                }
            })
        },
        
        # DTP-03: Sourcing (Waiting)
        {
            "case_id": "CASE-DTP03A",
            "name": "Infrastructure Services Supplier Evaluation",
            "category_id": "IT-INFRASTRUCTURE",
            "supplier_id": None,  # Multiple suppliers being evaluated
            "contract_id": None,
            "dtp_stage": "DTP-03",
            "status": "Waiting for Human Decision",
            "trigger_source": "User",
            "summary_text": "Evaluating 4 suppliers for infrastructure services contract. RFx responses received.",
            "key_findings": json.dumps([
                "4 RFx responses received",
                "Price range: $450K - $620K",
                "Technical evaluation in progress"
            ]),
            "recommended_action": "Confirm evaluation completion",
            "latest_agent_name": "Sourcing",
            "latest_agent_output": json.dumps({
                "ranked_suppliers": [
                    {"name": "InfraTech", "score": 92, "price": 450000},
                    {"name": "GlobalNet", "score": 88, "price": 480000}
                ],
                "recommendation": "Advance InfraTech to negotiation"
            }),
            "human_decision": json.dumps({
                "DTP-01": {
                    "sourcing_required": {"answer": "Yes"},
                    "sourcing_route": {"answer": "Strategic"}
                },
                "DTP-02": {
                    "supplier_list_confirmed": {"answer": "Yes"}
                }
            })
        },
        
        # DTP-04: Negotiation (Waiting)
        {
            "case_id": "CASE-DTP04A",
            "name": "Facilities Contract Negotiation",
            "category_id": "FACILITIES",
            "supplier_id": "SUP-005",
            "contract_id": "CON-FAC-2024-003",
            "dtp_stage": "DTP-04",
            "status": "Waiting for Human Decision",
            "trigger_source": "User",
            "summary_text": "Negotiating renewal terms with Office Supplies Plus. Target: 5% cost reduction.",
            "key_findings": json.dumps([
                "Preferred supplier selected",
                "Target savings: 5%",
                "Key terms under negotiation"
            ]),
            "recommended_action": "Approve final award",
            "latest_agent_name": "Negotiation",
            "latest_agent_output": json.dumps({
                "negotiation_status": "Complete",
                "final_savings": "5.2%",
                "agreed_terms": ["Net 60 Payment", "3 Year Term"]
            }),
            "human_decision": json.dumps({
                "DTP-01": {"sourcing_required": {"answer": "Yes"}, "sourcing_route": {"answer": "Strategic"}},
                "DTP-02": {"supplier_list_confirmed": {"answer": "Yes"}},
                "DTP-03": {"evaluation_complete": {"answer": "Yes"}}
            })
        },
        
        # DTP-05: Contracting
        {
            "case_id": "CASE-DTP05A",
            "name": "Cloud Migration Contract Finalization",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2024-NEW",
            "dtp_stage": "DTP-05",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Finalizing contract terms for cloud migration project. Legal review in progress.",
            "key_findings": json.dumps([
                "Terms negotiated successfully",
                "Legal review: 80% complete",
                "Signature expected within 5 days"
            ]),
            "recommended_action": "Complete contract review"
        },
        
        # DTP-06: Execution/Implementation
        {
            "case_id": "CASE-DTP06A",
            "name": "Security Software Implementation",
            "category_id": "IT-SECURITY",
            "supplier_id": "SUP-003",
            "contract_id": "CON-SEC-2023-IMPL",
            "dtp_stage": "DTP-06",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Implementation phase for security software rollout. 60% complete.",
            "key_findings": json.dumps([
                "Implementation: 60% complete",
                "On schedule",
                "No major issues reported"
            ]),
            "recommended_action": "Monitor implementation progress"
        },
        
        # === DYNAMIC ROUTING DEMO CASES ===
        
        # RENEWAL (No Change) - Should skip DTP-02/03
        {
            "case_id": "CASE-RENEWAL-001",
            "name": "✨ Demo: Marketing Agency Renewal",
            "category_id": "MARKETING_SERVICES",
            "supplier_id": "SUP-MKT-GLOBAL",
            "contract_id": "CTR-MKT-001",
            "dtp_stage": "DTP-04",
            "status": "Waiting for Human Decision",
            "trigger_source": "Signal",
            "summary_text": "DEMO: Renewal scenario. Contract expires in 30 days. No scope change needed. SKIPPED DTP-02/03 and jumped to DTP-04.",
            "key_findings": json.dumps([
                "Contract expires in 30 days",
                "Incumbent GlobalBrand - strong relationship",
                "Category: Renewal (No Change) - 90% confidence",
                "Path: DTP-01 → DTP-04 (SKIPPED 02/03)"
            ]),
            "recommended_action": "Approve renewal terms",
            "latest_agent_output": json.dumps({
                "negotiation_plan": {
                    "strategy": "Renewal with minor price adjustment",
                    "target_savings": "3-5%",
                    "key_terms": ["Extend 12 months", "Net 60 payment", "Performance SLA"]
                }
            }),
            "chat_history": json.dumps([
                {"role": "assistant", "content": "🔔 **AUTOMATED SIGNAL DETECTED**\\n\\nContract CTR-MKT-001 with GlobalBrand expires in **30 days**.\\n\\n**Smart Triage Analysis:**\\n- **Proposed Category**: Renewal (No Change)\\n- **Confidence**: 90%\\n- **Evidence**: Contract expiry approaching, no scope change indicators\\n- **Routing Impact**: ⚠️ Will SKIP DTP-02 (Supplier Eval) and DTP-03 (Sourcing)\\n\\n**Next Step**: Jump directly to DTP-04 (Negotiation)?", "timestamp": (now - timedelta(hours=2)).isoformat()},
                {"role": "user", "content": "Yes, confirm this is a simple renewal. No changes needed.", "timestamp": (now - timedelta(hours=1, minutes=55)).isoformat()},
                {"role": "assistant", "content": "✅ **Category Confirmed: Renewal (No Change)**\\n\\n**Dynamic Routing Applied:**\\n- ✅ DTP-01: Triage Complete\\n- ⏭️ DTP-02: SKIPPED (No supplier evaluation needed)\\n- ⏭️ DTP-03: SKIPPED (No RFx needed)\\n- ➡️ DTP-04: Negotiation (CURRENT)\\n\\n**Negotiation Strategy:**\\n- Incumbent: GlobalBrand (performance: 8.5/10)\\n- Current price: $450K/year\\n- Target: 3-5% savings ($13.5K-$22.5K)\\n- Leverage: Long relationship + market alternatives\\n\\n**Recommended Approach**: Request price hold or minor reduction in exchange for 12-month extension.", "timestamp": (now - timedelta(hours=1, minutes=50)).isoformat()},
                {"role": "user", "content": "What's our negotiation leverage?", "timestamp": (now - timedelta(hours=1, minutes=30)).isoformat()},
                {"role": "assistant", "content": "⚔️ **Negotiation Leverage Analysis:**\\n\\n**Our Strengths:**\\n1. ✅ Long-term relationship (3 years)\\n2. ✅ Consistent payment history\\n3. ✅ Market alternatives available (2 competitors at $430K)\\n\\n**Their Motivations:**\\n1. 💰 Renewal revenue ($450K/year)\\n2. 📊 Performance score is strong (8.5/10) - they want to keep you\\n3. ⚠️ Losing you = reference loss\\n\\n**Recommended Counter-Offer:**\\n- Price: $437K/year (-3% = $13K savings)\\n- Term: 12 months (shorter = more leverage next year)\\n- SLA: Add 95% on-time delivery guarantee\\n\\n**BATNA**: Walk to competitor at $430K (only $7K more savings but relationship risk)", "timestamp": (now - timedelta(hours=1, minutes=25)).isoformat()},
                {"role": "user", "content": "Proceed with the $437K counter-offer", "timestamp": (now - timedelta(hours=1)).isoformat()},
                {"role": "assistant", "content": "✅ **Negotiation Complete**\\n\\n**Outcome:**\\n- GlobalBrand accepted $437K/year ✅\\n- Savings: $13K/year (3%)\\n- Term: 12 months\\n- SLA: 95% on-time delivery added\\n\\n**Fast-Track Benefit**: By skipping DTP-02/03, we saved ~2 weeks of sourcing time and completed renewal in **3 days** vs typical 15-20 days.\\n\\n📋 **Next Step**: Contract finalization (DTP-05)?", "timestamp": (now - timedelta(minutes=55)).isoformat()}
            ])
        },
        
        # AD-HOC - Full path with alerts
        {
            "case_id": "CASE-ADHOC-001",
            "name": "✨ Demo: Urgent Consulting Request",
            "category_id": "PROFESSIONAL_SERVICES",
            "supplier_id": None,
            "contract_id": None,
            "dtp_stage": "DTP-02",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "DEMO: Ad-hoc urgent request. No pre-approved supplier. Full DTP path with risk alerts.",
            "key_findings": json.dumps([
                "Urgent timeline: 2 weeks",
                "No existing contract coverage",
                "Category: Ad-Hoc - 80% confidence",
                "Path: Full DTP with alerts"
            ]),
            "recommended_action": "Proceed with caution - compressed timeline",
            "chat_history": json.dumps([
                {"role": "user", "content": "I need urgent consulting support for a compliance audit. We have 2 weeks to prepare.", "timestamp": (now - timedelta(hours=3)).isoformat()},
                {"role": "assistant", "content": "🧠 **Smart Triage Analysis:**\\n\\n**Detected Keywords**: 'urgent', 'compliance'\\n- **Proposed Category**: Ad-Hoc\\n- **Confidence**: 80%\\n- **Evidence**: Urgency keywords, no contract match found\\n- **Routing Impact**: ⚠️ Full DTP path required, but with ALERTS at each stage\\n\\n**Risk Flags:**\\n- 🚨 Compressed timeline (2 weeks)\\n- 🚨 No pre-approved supplier\\n- 🚨 Compliance-critical (high risk)\\n\\n**Recommendation**: Proceed with full sourcing but expect expedited timelines. Confirm Ad-Hoc classification?", "timestamp": (now - timedelta(hours=2, minutes=55)).isoformat()},
                {"role": "user", "content": "Yes, this is urgent. Proceed with Ad-Hoc.", "timestamp": (now - timedelta(hours=2, minutes=50)).isoformat()},
                {"role": "assistant", "content": "✅ **Category Confirmed: Ad-Hoc**\\n\\n**Dynamic Routing Applied:**\\n- ✅ DTP-01: Triage Complete\\n- ➡️ DTP-02: Requirements (CURRENT) ⚠️ ALERT: Compressed timeline\\n- → DTP-03: Sourcing ⚠️ ALERT: Limited supplier pool\\n- → DTP-04-06: Standard flow\\n\\n🏗️ **The Architect - Requirements Freeze:**\\n\\nBefore I can shortlist suppliers, I need clarity:\\n1. What type of compliance audit? (SOX, ISO, GDPR, etc.)\\n2. Do you need audit execution OR just preparation support?\\n3. Budget ceiling for 2-week engagement?\\n\\n⚠️ **Timeline Alert**: Normal requirements phase = 5 days. We have 2 weeks total. Recommend 24-hour turnaround on answers.", "timestamp": (now - timedelta(hours=2, minutes=45)).isoformat()},
                {"role": "user", "content": "SOX compliance audit. We need preparation support only - documentation review and gap analysis. Budget is $50K max.", "timestamp": (now - timedelta(hours=2, minutes=30)).isoformat()},
                {"role": "assistant", "content": "✅ **Requirements Frozen**\\n\\n**Scope:**\\n- SOX compliance prep (documentation + gap analysis)\\n- 2-week delivery\\n- Budget: $50K\\n\\n**Supplier Search (Ad-Hoc Mode):**\\n⚠️ **ALERT**: Only 2 suppliers in our network have SOX expertise:\\n1. CompliancePro ($45K, 7-day delivery)\\n2. AuditExperts ($52K, 10-day delivery - OVER BUDGET)\\n\\n**Risk Assessment:**\\n- 🚨 Limited options due to specialized need\\n- 🚨 CompliancePro is only viable option\\n- ✅ CompliancePro has strong SOX track record (8.9/10)\\n\\n**Recommendation**: Sole-source to CompliancePro given timeline + budget constraints?", "timestamp": (now - timedelta(hours=2, minutes=25)).isoformat()}
            ])
        },
        
        # FAST-PASS - Skip to DTP-05
        {
            "case_id": "CASE-FASTPASS-001",
            "name": "✨ Demo: Pre-Approved Laptop Purchase",
            "category_id": "IT-HARDWARE",
            "supplier_id": "SUP-HARDWARE-001",
            "contract_id": "CTR-CATALOG-HARDWARE",
            "dtp_stage": "DTP-05",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "DEMO: Fast-Pass scenario. Pre-approved catalog item. SKIPPED DTP-02/03/04 and jumped to DTP-05.",
            "key_findings": json.dumps([
                "Pre-approved supplier in catalog",
                "Standard pricing applies",
                "Category: Fast-Pass - 85% confidence",
                "Path: DTP-01 → DTP-05 (SKIPPED 02/03/04)"
            ]),
            "recommended_action": "Finalize PO and contract",
            "chat_history": json.dumps([
                {"role": "user", "content": "I need 10 laptops for new hires. Standard Dell models.", "timestamp": (now - timedelta(hours=1)).isoformat()},
                {"role": "assistant", "content": "🧠 **Smart Triage Analysis:**\\n\\n**Detected**: Catalog item request\\n- **Proposed Category**: Fast-Pass\\n- **Confidence**: 85%\\n- **Evidence**: 'Standard Dell models' matches pre-approved catalog\\n- **Routing Impact**: ⚠️ Will SKIP DTP-02/03/04 (Supplier Eval, Sourcing, Negotiation)\\n\\n**Catalog Match Found:**\\n- Supplier: TechSupply Inc (pre-approved)\\n- Contract: CTR-CATALOG-HARDWARE\\n- Standard pricing: $1,200/laptop\\n- Total: $12,000 (10 units)\\n\\n**Fast-Pass Benefit**: Order fulfilled in 2 days vs 15-20 days for full sourcing.\\n\\nConfirm Fast-Pass?", "timestamp": (now - timedelta(minutes=58)).isoformat()},
                {"role": "user", "content": "Yes, fast-pass this order", "timestamp": (now - timedelta(minutes=55)).isoformat()},
                {"role": "assistant", "content": "✅ **Category Confirmed: Fast-Pass**\\n\\n**Dynamic Routing Applied:**\\n- ✅ DTP-01: Triage Complete\\n- ⏭️ DTP-02: SKIPPED (Pre-approved supplier)\\n- ⏭️ DTP-03: SKIPPED (Catalog pricing)\\n- ⏭️ DTP-04: SKIPPED (No negotiation needed)\\n- ➡️ DTP-05: Contracting (CURRENT)\\n\\n🔒 **The Closer - Contract Validation:**\\n\\n**Order Summary:**\\n- 10x Dell Latitude 5540\\n- Unit Price: $1,200\\n- Total: $12,000\\n- Delivery: 5 business days\\n- Payment: Net 30 (standard terms)\\n\\n**Contract Check:**\\n- ✅ Pricing matches catalog\\n- ✅ Supplier pre-approved\\n- ✅ Standard warranty (3 years)\\n- ✅ No custom terms needed\\n\\n**Status**: READY TO SIGN\\n\\n📋 **Next Step**: Generate PO and submit?", "timestamp": (now - timedelta(minutes=50)).isoformat()},
                {"role": "user", "content": "Generate the PO", "timestamp": (now - timedelta(minutes=30)).isoformat()},
                {"role": "assistant", "content": "✅ **PO Generated: PO-2026-00142**\\n\\n**Order Details:**\\n- Supplier: TechSupply Inc\\n- Items: 10x Dell Latitude 5540\\n- Amount: $12,000\\n- Delivery: 5 business days\\n- Ship To: Main Office\\n\\n**Fast-Track Summary:**\\n- ⏱️ Time to PO: **15 minutes** (vs 15-20 days for full sourcing)\\n- 💰 Savings: $0 (catalog pricing)\\n- ✅ Compliance: Pre-approved supplier\\n\\n**Case Status**: ✅ COMPLETED\\n\\nThis demonstrates the Fast-Pass routing: DTP-01 → DTP-05 in under 1 hour!", "timestamp": (now - timedelta(minutes=25)).isoformat()}
            ])
        }
    ]
    
    for case_data in cases:
        case = CaseState(
            **case_data,
            created_at=(now - timedelta(days=30)).isoformat(),
            updated_at=now.isoformat()
        )
        session.add(case)


def seed_signal_cases(session):
    """Seed cases triggered by proactive signals."""
    now = datetime.now()
    
    signal_cases = [
        # Contract Renewal Signal - Urgent
        {
            "case_id": "CASE-SIG-REN01",
            "name": "URGENT: Software License Renewal Due",
            "category_id": "IT-SOFTWARE",
            "supplier_id": "SUP-001",
            "contract_id": "CON-SW-2024-RENEW",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Contract CON-SW-2024-RENEW expires in 45 days. Immediate action required.",
            "key_findings": json.dumps([
                "Contract expires in 45 days",
                "Annual value: $450,000",
                "Supplier performance: Strong (8.5/10)",
                "Auto-renewal clause: No"
            ]),
            "recommended_action": "Initiate renewal strategy assessment"
        },
        
        # Declining Performance Signal
        {
            "case_id": "CASE-SIG-PERF01",
            "name": "Performance Alert: DataStore Corp",
            "category_id": "IT-INFRASTRUCTURE",
            "supplier_id": "SUP-004",
            "contract_id": "CON-INF-2023-005",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Supplier performance has declined below threshold. Multiple SLA breaches detected.",
            "key_findings": json.dumps([
                "Performance score dropped to 5.8/10",
                "2 active SLA breaches",
                "Cost variance: +12% over budget",
                "Risk level: HIGH"
            ]),
            "recommended_action": "Evaluate supplier remediation or replacement"
        },
        
        # SLA Breach Signal
        {
            "case_id": "CASE-SIG-SLA01",
            "name": "SLA Breach: CloudFirst Response Time",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2023-015",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: SLA breach detected. Response time exceeded 24-hour target.",
            "key_findings": json.dumps([
                "SLA breach: Response time",
                "Target: 24 hours, Actual: 48 hours",
                "Pattern: 2nd breach this quarter",
                "Financial impact: Potential penalty clause"
            ]),
            "recommended_action": "Review SLA compliance and escalation"
        },
        
        # Spend Anomaly Signal
        {
            "case_id": "CASE-SIG-SPEND01",
            "name": "Spend Alert: Cloud Services Overage",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2023-015",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Q2 spend exceeded forecast by 15%. Cost optimization review recommended.",
            "key_findings": json.dumps([
                "Q2 spend: $310,000 (forecast: $270,000)",
                "Variance: +15%",
                "Primary driver: Usage growth",
                "Optimization potential identified"
            ]),
            "recommended_action": "Analyze spend drivers and optimization options"
        },
        
        # Market Opportunity Signal
        {
            "case_id": "CASE-SIG-MKT01",
            "name": "Market Alert: New Security Vendors",
            "category_id": "IT-SECURITY",
            "supplier_id": None,
            "contract_id": None,
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "MARKET INTELLIGENCE: 3 new vendors entered the enterprise security market with competitive pricing.",
            "key_findings": json.dumps([
                "3 new market entrants identified",
                "Average pricing 20% below current contract",
                "Current contract renewal in 6 months",
                "Opportunity for competitive evaluation"
            ]),
            "recommended_action": "Assess market alternatives before renewal"
        }
    ]
    
    for case_data in signal_cases:
        case = CaseState(
            **case_data,
            created_at=(now - timedelta(days=random_days(1, 10))).isoformat(),
            updated_at=now.isoformat()
        )
        session.add(case)


def random_days(min_days: int, max_days: int) -> int:
    """Generate random number of days."""
    import random
    return random.randint(min_days, max_days)


def seed_example_case(session):
    """
    Create a COMPLETED example case with full AI-Human conversation.
    
    Scenario: IT Infrastructure - Cloud Data Center Migration
    Showcases all 6 DTP Mindsets in a complex technical category.
    """
    now = datetime.now()
    
    # Pre-built conversation history showing all 6 DTP Mindsets
    conversation = [
        # === DTP-01: THE GATEKEEPER (Smart Intake) ===
        {"role": "user", "content": "We need to migrate our Singapore data center to the cloud before the lease expires in 6 months.", "timestamp": (now - timedelta(days=45, hours=8)).isoformat()},
        {"role": "assistant", "content": "🧠 **Smart Intake**: I see this is a critical infrastructure project with a hard deadline.\n\n**Clarifying Questions:**\n1. Are you looking for a **Lift & Shift** (IaaS) or **Refactoring** (PaaS/SaaS) strategy?\n2. What is the estimated compute/storage volume (e.g., 500+ VMs, 1PB+ data)?\n3. Do we have specific data sovereignty requirements for Singapore?\n\nThis helps me determine if we need a major strategic sourcing event.", "timestamp": (now - timedelta(days=45, hours=7, minutes=55)).isoformat()},
        {"role": "user", "content": "Mostly Lift & Shift for 800 VMs. About 2PB of data. Yes, data must stay in SG region. Budget is ~$2M/year.", "timestamp": (now - timedelta(days=45, hours=7, minutes=50)).isoformat()},
        {"role": "assistant", "content": "✅ **Understood.** Strategic Cloud Migration.\n\n**Strategy Recommendation: Strategic Sourcing (RFP)**\n- **Confidence**: 95%\n- **Rationale**: High spend ($2M/yr) + Complex Technical Requirements + Data Sovereignty Risk\n- **Impact**: Full DTP Flow required.\n\n📋 **Next Step**: Proceed to detailed requirements gathering (DTP-02)?", "timestamp": (now - timedelta(days=45, hours=7, minutes=45)).isoformat()},
        
        # === DTP-02: THE ARCHITECT (Requirements) ===
        {"role": "user", "content": "Yes, let's define requirements.", "timestamp": (now - timedelta(days=44)).isoformat()},
        {"role": "assistant", "content": "🏗️ **The Architect**: I need to freeze the technical constraints before we go to market.\n\n**Critical Requirements Check:**\n1. **Uptime SLA**: Is 99.9% acceptable, or do we need 99.99% (High Availability)?\n2. **Compliance**: Do we need PCI-DSS or SOC2 Type II reports attached?\n3. **Connectivity**: Direct Connect/ExpressRoute required?\n\n*Suggestion: For critical banking apps, 99.99% HA is standard.*", "timestamp": (now - timedelta(days=44, hours=6)).isoformat()},
        {"role": "user", "content": "Need 99.99% HA. Must be SOC2 compliant. Direct Connect 10Gbps is required.", "timestamp": (now - timedelta(days=44, hours=5)).isoformat()},
        {"role": "assistant", "content": "✅ **Requirements Frozen.**\n\n**Evaluation Criteria:**\n1. Technical Capability & HA Architecture (35%)\n2. Security & Compliance (SOC2) (30%)\n3. Total Cost of Ownership (TCO) (25%)\n4. Migration Support Services (10%)\n\n**Shortlist (3 Hyper-scalers):**\n| Provider | Strength | Flag |\n|----------|----------|------|\n| AWS | Strongest SG presence | Market Leader |\n| Azure | Better hybrid integration | Good for .NET stats |\n| GCP | Best data analytics capability | Pricing aggressive |\n\n📋 **Next Step:** Draft RFP for Cloud Services (DTP-03)?", "timestamp": (now - timedelta(days=44, hours=4)).isoformat()},
        
        # === DTP-03: THE CONTROLLER (Sourcing) ===
        {"role": "user", "content": "Yes, send RFP to all three.", "timestamp": (now - timedelta(days=40)).isoformat()},
        {"role": "assistant", "content": "✈️ **RFP Drafted & Sent.**\n\n**RFP: Singapore DC Migration**\n- **Scope**: 800 VMs, 2PB Storage, 10Gbps Direct Connect\n- **Term**: 3 Years Committed Use\n- **Timeline**: Proposals due in 10 days.\n\n*(...10 days later...)*\n\n📊 **Bid Analysis Complete:**\n\n| Provider | 3-Yr TCO | Technical Score | Compliance | Recommendation |\n|----------|----------|-----------------|------------|----------------|\n| **AWS** | $5.8M | 92/100 | ✅ Pass | **Strongest Tech** |\n| **Azure** | $6.2M | 88/100 | ✅ Pass | Expensive |\n| **GCP** | $5.1M | 85/100 | ✅ Pass | **Best Price** |\n\n📋 **Next Step:** Negotiate with AWS (Leader) and GCP (Challenger) (DTP-04)?", "timestamp": (now - timedelta(days=30)).isoformat()},
        
        # === DTP-04: THE CHALLENGER (Negotiation) ===
        {"role": "user", "content": "We prefer AWS technicals but GCP price. Negotiate with AWS.", "timestamp": (now - timedelta(days=28)).isoformat()},
        {"role": "assistant", "content": "⚔️ **The Challenger**: I need to challenge the AWS quote. They are 14% more expensive than GCP ($5.8M vs $5.1M).\n\n**Negotiation Strategy:**\n1. **Anchor**: Feature GCP's $5.1M TCO bid.\n2. **Leverage**: 'We want to go AWS, but Finance is pushing for GCP due to $700k delta.'\n3. **Request**: Ask for **Enterprise Discount Program (EDP)** tier upgrade + fully funded migration credits.\n\n**Script**: \"We have a technically viable offer from GCP at $5.1M. Can you match the TCO or offer Migration Acceleration Program (MAP) credits to offset the difference?\"", "timestamp": (now - timedelta(days=28, hours=2)).isoformat()},
        {"role": "user", "content": "AWS came back. They offered $5.5M + $300k in migration credits.", "timestamp": (now - timedelta(days=25)).isoformat()},
        {"role": "assistant", "content": "✅ **Negotiation Analysis**:\n- **New Net TCO**: $5.2M ($5.5M - $300k credits)\n- **Delta vs GCP**: Only $100k difference now (approx 2%)\n- **Value**: AWS has better SG presence (Lower Latency).\n\n**Recommendation**: **ACCEPT AWS offer.** The technical premium is worth the small 2% cost delta for 99.99% HA requirements.\n\n📋 **Next Step:** Finalize Contract (DTP-05)?", "timestamp": (now - timedelta(days=25, hours=4)).isoformat()},
        
        # === DTP-05: THE CLOSER (Contracting) ===
        {"role": "user", "content": "Proceed with AWS contract.", "timestamp": (now - timedelta(days=20)).isoformat()},
        {"role": "assistant", "content": "🔒 **The Closer**: Scanning Enterprise Agreement (EA)...\n\n**Validation Checklist:**\n- [x] Pricing: EDP Discount applied (12% off list)\n- [x] Credits: $300k MAP credits included in Order Form\n- [x] SLA: 99.99% availability for Multi-AZ\n- [ ] **Data Residency**: Clause 8.2 says \"Data may be replicated globally for durability\".\n\n⚠️ **RISK ALERT**: Clause 8.2 violates your **Data Sovereignty Requirement** (Must stay in SG).\n\n**Action Required**: Request legal amendment to restrict data replication to `ap-southeast-1` (Singapore) region only.", "timestamp": (now - timedelta(days=20, hours=2)).isoformat()},
        {"role": "user", "content": "AWS Legal agreed to the region restriction amendment. We signed.", "timestamp": (now - timedelta(days=15)).isoformat()},
        {"role": "assistant", "content": "✅ **Contract Safe & Signed.**\n- **Data Sovereignty**: LOCKED to Singapore.\n- **Credits**: Activated.\n\n📋 **Next Step:** Implementation Tracking (DTP-06)?", "timestamp": (now - timedelta(days=15, hours=1)).isoformat()},
        
        # === DTP-06: THE HISTORIAN (Execution) ===
        {"role": "user", "content": "Migration is complete. Generate value report.", "timestamp": (now).isoformat()},
        {"role": "assistant", "content": "📜 **The Historian**: Generating Value Story...\n\n**Project Success Summary:**\n- **Timeline**: Completed 2 weeks ahead of data center lease expiry.\n- **Technical**: 100% Uptime during transition.\n\n**Value Captured:**\n1. **Hard Savings**: Negotiated $600k reduction from initial AWS quote ($5.8M → $5.2M net).\n2. **Cost Avoidance**: Avoided $2M capital refresh for on-prem hardware.\n3. **Risk Mitigation**: Caught Data Residency clause that would have violated SG banking regulations.\n\n**Final ROI**: 340%\n\n**Case Status: ✅ COMPLETED** (IT-INFRASTRUCTURE)", "timestamp": (now).isoformat()}
    ]
    
    example_case = CaseState(
        case_id="CASE-EXAMPLE-001",
        name="✨ Singapore DC Cloud Migration",
        category_id="IT-INFRASTRUCTURE",
        contract_id="CTR-AWS-2026-SG",
        supplier_id="SUP-AWS-CLOUD",
        trigger_source="User",
        dtp_stage="DTP-06",
        status="Completed",
        summary_text="End-to-end migration of 800 VMs to AWS Singapore. Achieved 99.99% HA and $600k negotiated savings.",
        key_findings=json.dumps([
            "Selected AWS over GCP/Azure for technical fit",
            "Negotiated $300k migration credits",
            "Fixed critical Data Sovereignty clause in contract",
            "Net TCO: $5.2M (3-year term)"
        ]),
        recommended_action="Monitor cloud spend vs committed usage",
        chat_history=json.dumps(conversation),
        created_at=(now - timedelta(days=45)).isoformat(),
        updated_at=now.isoformat()
    )
    session.add(example_case)
    

    # Seed associated artifacts for richness
    seed_example_artifacts(session, example_case.case_id, now)


def seed_example_artifacts(session, case_id: str, now: datetime):
    """Seed key artifacts for the example case as both Artifacts and Documents."""
    
    # 1. Strategy Artifact
    strategy = Artifact(
        artifact_id=f"ART-{case_id}-STRAT",
        case_id=case_id,
        type="strategy_recommendation",
        title="Cloud Migration Strategy: Strategic Sourcing",
        content_text="STRATEGY RECOMMENDATION\n\n1. SCOPE: Migration of SG Data Center (800 VMs)\n2. APPROACH: Competitive RFx with Big 3 CSPs\n3. RATIONALE: High spend ($2M+) and complex data sovereignty requirements justify full strategic sourcing.",
        content_json=json.dumps({
            "recommended_action": "Strategic Sourcing (RFx)",
            "key_factors": ["High Spend", "Risk: Data Sovereignty", "Technical Complexity"],
            "confidence": 0.95
        }),
        created_by_agent="StrategyAgent",
        verification_status="VERIFIED",
        created_at=(now - timedelta(days=45)).isoformat()
    )
    session.add(strategy)
    
    # Add as Document for UI visibility
    doc_strat = DocumentRecord(
        document_id=f"DOC-{case_id}-STRAT",
        filename="Strategy_Recommendation_Brief.pdf",
        file_type="pdf",
        document_type="Strategy",
        case_id=case_id,
        supplier_id="SUP-AWS-CLOUD",
        category_id="IT-INFRASTRUCTURE",
        dtp_relevance=json.dumps(["DTP-01"]),
        ingested_at=(now - timedelta(days=45)).isoformat()
    )
    session.add(doc_strat)
    
    # 2. RFP Analysis Artifact
    rfp = Artifact(
        artifact_id=f"ART-{case_id}-RFP",
        case_id=case_id,
        type="supplier_evaluation",
        title="CSP Evaluation Matrix (AWS vs GCP vs Azure)",
        content_text="RFP ANALYSIS SUMMARY\n\nWinner: AWS (Technical Leader)\nChallenger: GCP (Price Leader)\n\nAWS scored highest on Technical (92/100) and SG Presence. GCP offers 14% lower TCO. Recommendation: Negotiate with AWS to bridge price gap.",
        content_json=json.dumps({
            "scores": {"AWS": 92, "Azure": 88, "GCP": 85},
            "pricing": {"AWS": 5800000, "Azure": 6200000, "GCP": 5100000},
            "recommendation": "Negotiate with AWS"
        }),
        created_by_agent="SourcingAgent",
        verification_status="VERIFIED",
        created_at=(now - timedelta(days=30)).isoformat()
    )
    session.add(rfp)

    # Add as Document
    doc_rfp = DocumentRecord(
        document_id=f"DOC-{case_id}-RFP",
        filename="RFP_Analysis_Cloud_Migration.xlsx",
        file_type="xlsx",
        document_type="Scorecard",
        case_id=case_id,
        supplier_id="SUP-AWS-CLOUD",
        category_id="IT-INFRASTRUCTURE",
        dtp_relevance=json.dumps(["DTP-02", "DTP-03"]),
        ingested_at=(now - timedelta(days=30)).isoformat()
    )
    session.add(doc_rfp)
    
    # 3. Contract Artifact
    contract = Artifact(
        artifact_id=f"ART-{case_id}-CONT",
        case_id=case_id,
        type="contract_review",
        title="Annotated Contract: AWS Enterprise Agreement",
        content_text="CONTRACT VALIDATION\n\nStatus: SIGNED\n\nKey Terms:\n- Term: 3 Years\n- Discount: 12% EDP\n- Credits: $300k MAP\n- Data Residency: Amended to SG-Only (Clause 8.2 overridden)",
        content_json=json.dumps({
            "status": "Signed",
            "value": 5200000,
            "term_months": 36,
            "risk_flags_cleared": ["Data Residency", "Liability Cap"]
        }),
        created_by_agent="ContractingAgent",
        verification_status="VERIFIED",
        created_at=(now - timedelta(days=15)).isoformat()
    )
    session.add(contract)

    # Add as Document
    doc_cont = DocumentRecord(
        document_id=f"DOC-{case_id}-CONT",
        filename="AWS_Enterprise_Agreement_SIGNED.pdf",
        file_type="pdf",
        document_type="Contract",
        case_id=case_id,
        supplier_id="SUP-AWS-CLOUD",
        contract_id="CTR-AWS-2026-SG",
        category_id="IT-INFRASTRUCTURE",
        dtp_relevance=json.dumps(["DTP-05"]),
        ingested_at=(now - timedelta(days=15)).isoformat()
    )
    session.add(doc_cont)

    # 4. Value Report Artifact
    value = Artifact(
        artifact_id=f"ART-{case_id}-VAL",
        case_id=case_id,
        type="implementation_plan",
        title="Value Capture Report: SG Cloud Migration",
        content_text="PROJECT SUCCESS REPORT\n\nFinal ROI: 340%\n\nHard Savings: $600,000 negotiated reduction\nSoft Savings: $2M capex avoidance\nRisk: 100% Data Sovereignty Compliance",
        content_json=json.dumps({
            "roi_percent": 340,
            "hard_savings": 600000,
            "soft_savings": 2000000
        }),
        created_by_agent="ExecutionAgent",
        verification_status="VERIFIED",
        created_at=now.isoformat()
    )
    session.add(value)
    
    # Add as Document
    doc_val = DocumentRecord(
        document_id=f"DOC-{case_id}-VAL",
        filename="Value_Capture_Report_Final.pdf",
        file_type="pdf",
        document_type="Report",
        case_id=case_id,
        supplier_id="SUP-AWS-CLOUD",
        category_id="IT-INFRASTRUCTURE",
        dtp_relevance=json.dumps(["DTP-06"]),
        ingested_at=now.isoformat()
    )
    session.add(doc_val)


# Entry point for running directly
if __name__ == "__main__":
    seed_all()







