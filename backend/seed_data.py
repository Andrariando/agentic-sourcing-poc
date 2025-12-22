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
    print("🌱 Seeding database with test data...")
    
    init_db()
    session = get_db_session()
    
    try:
        # Clear existing data
        session.query(CaseState).delete()
        session.query(SupplierPerformance).delete()
        session.query(SpendMetric).delete()
        session.query(SLAEvent).delete()
        session.commit()
        print("  ✓ Cleared existing data")
        
        # Seed suppliers first
        seed_suppliers(session)
        print("  ✓ Seeded supplier performance data")
        
        # Seed spend data
        seed_spend_data(session)
        print("  ✓ Seeded spend data")
        
        # Seed SLA events
        seed_sla_events(session)
        print("  ✓ Seeded SLA events")
        
        # Seed cases at various stages
        seed_manual_cases(session)
        print("  ✓ Seeded manual cases at various DTP stages")
        
        # Seed signal-triggered cases
        seed_signal_cases(session)
        print("  ✓ Seeded signal-triggered cases")
        
        session.commit()
        print("\n✅ Database seeded successfully!")
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
            "recommended_action": "Define RFx requirements"
        },
        
        # DTP-03: Sourcing
        {
            "case_id": "CASE-DTP03A",
            "name": "Infrastructure Services Supplier Evaluation",
            "category_id": "IT-INFRASTRUCTURE",
            "supplier_id": None,  # Multiple suppliers being evaluated
            "contract_id": None,
            "dtp_stage": "DTP-03",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Evaluating 4 suppliers for infrastructure services contract. RFx responses received.",
            "key_findings": json.dumps([
                "4 RFx responses received",
                "Price range: $450K - $620K",
                "Technical evaluation in progress"
            ]),
            "recommended_action": "Complete supplier evaluation"
        },
        
        # DTP-04: Negotiation
        {
            "case_id": "CASE-DTP04A",
            "name": "Facilities Contract Negotiation",
            "category_id": "FACILITIES",
            "supplier_id": "SUP-005",
            "contract_id": "CON-FAC-2024-003",
            "dtp_stage": "DTP-04",
            "status": "In Progress",
            "trigger_source": "User",
            "summary_text": "Negotiating renewal terms with Office Supplies Plus. Target: 5% cost reduction.",
            "key_findings": json.dumps([
                "Preferred supplier selected",
                "Target savings: 5%",
                "Key terms under negotiation"
            ]),
            "recommended_action": "Review negotiation plan"
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
            "name": "🔔 URGENT: Software License Renewal Due",
            "category_id": "IT-SOFTWARE",
            "supplier_id": "SUP-001",
            "contract_id": "CON-SW-2024-RENEW",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Contract CON-SW-2024-RENEW expires in 45 days. Immediate action required.",
            "key_findings": json.dumps([
                "⚠️ Contract expires in 45 days",
                "Annual value: $450,000",
                "Supplier performance: Strong (8.5/10)",
                "Auto-renewal clause: No"
            ]),
            "recommended_action": "Initiate renewal strategy assessment"
        },
        
        # Declining Performance Signal
        {
            "case_id": "CASE-SIG-PERF01",
            "name": "🔔 Performance Alert: DataStore Corp",
            "category_id": "IT-INFRASTRUCTURE",
            "supplier_id": "SUP-004",
            "contract_id": "CON-INF-2023-005",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Supplier performance has declined below threshold. Multiple SLA breaches detected.",
            "key_findings": json.dumps([
                "⚠️ Performance score dropped to 5.8/10",
                "2 active SLA breaches",
                "Cost variance: +12% over budget",
                "Risk level: HIGH"
            ]),
            "recommended_action": "Evaluate supplier remediation or replacement"
        },
        
        # SLA Breach Signal
        {
            "case_id": "CASE-SIG-SLA01",
            "name": "🔔 SLA Breach: CloudFirst Response Time",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2023-015",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: SLA breach detected. Response time exceeded 24-hour target.",
            "key_findings": json.dumps([
                "⚠️ SLA breach: Response time",
                "Target: 24 hours, Actual: 48 hours",
                "Pattern: 2nd breach this quarter",
                "Financial impact: Potential penalty clause"
            ]),
            "recommended_action": "Review SLA compliance and escalation"
        },
        
        # Spend Anomaly Signal
        {
            "case_id": "CASE-SIG-SPEND01",
            "name": "🔔 Spend Alert: Cloud Services Overage",
            "category_id": "IT-CLOUD",
            "supplier_id": "SUP-002",
            "contract_id": "CON-CLD-2023-015",
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "AUTOMATED ALERT: Q2 spend exceeded forecast by 15%. Cost optimization review recommended.",
            "key_findings": json.dumps([
                "⚠️ Q2 spend: $310,000 (forecast: $270,000)",
                "Variance: +15%",
                "Primary driver: Usage growth",
                "Optimization potential identified"
            ]),
            "recommended_action": "Analyze spend drivers and optimization options"
        },
        
        # Market Opportunity Signal
        {
            "case_id": "CASE-SIG-MKT01",
            "name": "🔔 Market Alert: New Security Vendors",
            "category_id": "IT-SECURITY",
            "supplier_id": None,
            "contract_id": None,
            "dtp_stage": "DTP-01",
            "status": "Open",
            "trigger_source": "Signal",
            "summary_text": "MARKET INTELLIGENCE: 3 new vendors entered the enterprise security market with competitive pricing.",
            "key_findings": json.dumps([
                "📊 3 new market entrants identified",
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


# Entry point for running directly
if __name__ == "__main__":
    seed_all()

