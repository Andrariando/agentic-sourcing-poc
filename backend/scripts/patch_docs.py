import sys
import json

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    start_str = "documents = ["
    start_idx = content.find(start_str)
    
    # Find the end of the documents array by looking for the for loop
    end_str = "    for doc in documents:"
    end_idx = content.find(end_str, start_idx)

    if start_idx == -1 or end_idx == -1:
        print("Could not find boundaries for documents list")
        return

    new_docs_code = """documents = [
        # ============================================================
        # CASE-001: TELECOM CONSOLIDATION DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-TEL-001",
            "name": "Global Telecom Sourcing Benchmark 2025",
            "type": "Market Report",
            "cat": "TELECOM",
            "content": \"\"\"
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
            \"\"\"
        },
        {
            "id": "DOC-TMP-TEL-001",
            "name": "RFP Template - Global Network & Telecom Integration",
            "type": "Template",
            "cat": "TELECOM",
            "content": \"\"\"
            RFP TEMPLATE: GLOBAL TELECOM AND NETWORK SERVICES
            
            1. SCOPE
            Global provision of WAN, Internet, and SIP services across NA, EMEA, and APAC regions.
            
            2. REQUIREMENTS
            - Single unified billing platform.
            - 99.99% Network Availability SLA.
            - Dedicated Global Account Manager.
            \"\"\"
        },
        {
            "id": "DOC-PROP-TEL-ATT",
            "name": "Proposal - AT&T Global Enterprise",
            "type": "Proposal",
            "cat": "TELECOM",
            "case_id": "CASE-001",
            "content": \"\"\"
            PROPOSAL: GLOBAL TELECOM MSA
            SUPPLIER: AT&T Business
            
            PRICING SUMMARY:
            - Estimated Annual Spend: $2.4M (Representing 20% savings vs current baseline)
            - Setup/NRC: Waived for 36-month commit.
            
            SLA COMMITMENT:
            - 99.99% Uptime with 10% credit penalty for breach.
            \"\"\"
        },
        {
            "id": "DOC-PROP-TEL-VZ",
            "name": "Proposal - Verizon Enterprise Solutions",
            "type": "Proposal",
            "cat": "TELECOM",
            "case_id": "CASE-001",
            "content": \"\"\"
            PROPOSAL: GLOBAL TELECOM MSA
            SUPPLIER: Verizon Business
            
            PRICING SUMMARY:
            - Estimated Annual Spend: $2.55M (Representing 15% savings vs current baseline)
            - Setup/NRC: $50,000 one-time transition fee.
            
            SLA COMMITMENT:
            - 99.999% Uptime with 15% credit penalty for breach.
            \"\"\"
        },

        # ============================================================
        # CASE-002: CLOUD MIGRATION DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-CLD-001",
            "name": "Gartner Magic Quadrant: Cloud Infrastructure 2025",
            "type": "Market Report",
            "cat": "CLOUD",
            "content": \"\"\"
            CLOUD INFRASTRUCTURE AND PLATFORM SERVICES
            
            LEADERS:
            - Amazon Web Services (AWS): Unmatched breadth of services and partner ecosystem. Highest migration velocity.
            - Microsoft Azure: Seamless integration with enterprise Microsoft environments. Strong hybrid cloud.
            - Google Cloud (GCP): Leading AI/ML capabilities.
            
            MIGRATION TRENDS:
            - 60% of enterprises use Migration Acceleration Programs (MAP) from hyperscalers to offset double-bubble costs.
            \"\"\"
        },
        {
            "id": "DOC-PROP-CLD-AWS",
            "name": "Proposal - AWS Migration Services",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-002",
            "content": \"\"\"
            PROPOSAL: MIGRATION ACCELERATION PROGRAM (MAP)
            SUPPLIER: AWS
            
            APPROACH:
            - Phase 1: Assess (4 weeks) - $50k (Fully funded by AWS)
            - Phase 2: Mobilize (8 weeks) - $150k (50% funded by AWS)
            - Phase 3: Migrate & Modernize - Targeting 200 VMs in 6 months.
            
            CAPABILITIES:
            - Automated lift-and-shift via AWS Application Migration Service.
            - Migration velocity: Up to 50 VMs per week.
            \"\"\"
        },
        {
            "id": "DOC-PROP-CLD-AZURE",
            "name": "Proposal - Azure Cloud Adoption Framework",
            "type": "Proposal",
            "cat": "CLOUD",
            "case_id": "CASE-002",
            "content": \"\"\"
            PROPOSAL: AZURE MIGRATION PROGRAM (AMP)
            SUPPLIER: Microsoft Azure
            
            APPROACH:
            - Azure Migrate automation tooling included free of charge.
            - Free extended security updates for Windows Server legacy workloads during migration.
            
            CAPABILITIES:
            - Native Azure Hybrid Benefit (AHB) for existing SQL Server licenses.
            - Migration velocity: Up to 30 VMs per week.
            \"\"\"
        },

        # ============================================================
        # CASE-003: HRIS DOCUMENTS (All 3 Proposals for Evaluation)
        # ============================================================
        {
            "id": "DOC-TMP-HRIS-01",
            "name": "RFP - HRIS Platform Selection",
            "type": "Template",
            "cat": "SAAS",
            "content": \"\"\"
            RFP REQUIREMENTS:
            - Must provide superior User Experience (UX score > 9/10 required).
            - Must support Global Payroll Integration across NA, EMEA, APAC.
            - TCO must be heavily weighted to avoid post-implementation cost spikes.
            \"\"\"
        },
        {
            "id": "DOC-PROP-HRIS-WD",
            "name": "Workday Proposal - Enterprise HCM",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": \"\"\"
            SUPPLIER: Workday
            SCORE METRICS:
            - User Experience: 9.5/10 (Industry leading mobile app and intuitive UI)
            - Global Payroll: 9.0/10 (Native integration in 120 countries)
            
            PRICING:
            - Subscription: $45 PEPM (Per Employee Per Month)
            - TCO (5-Year): $5.2M (Highest of all bidders)
            \"\"\"
        },
        {
            "id": "DOC-PROP-HRIS-ORCL",
            "name": "Oracle HCM Cloud Proposal",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": \"\"\"
            SUPPLIER: Oracle HCM Cloud
            SCORE METRICS:
            - User Experience: 8.0/10 (Responsive, but complex navigation)
            - Global Payroll: 9.5/10 (Deepest global compliance engine)
            
            PRICING:
            - Subscription: $38 PEPM
            - TCO (5-Year): $4.1M
            \"\"\"
        },
        {
            "id": "DOC-PROP-HRIS-SAP",
            "name": "SAP SuccessFactors Proposal",
            "type": "Proposal",
            "cat": "SAAS",
            "case_id": "CASE-003",
            "content": \"\"\"
            SUPPLIER: SAP SuccessFactors
            SCORE METRICS:
            - User Experience: 7.0/10 (Legacy UI elements remain)
            - Global Payroll: 8.5/10 
            
            PRICING:
            - Subscription: $35 PEPM
            - TCO (5-Year): $3.9M
            \"\"\"
        },

        # ============================================================
        # CASE-004: MICROSOFT EA DOCUMENTS
        # ============================================================
        {
            "id": "DOC-MKT-MSFT-001",
            "name": "Microsoft Licensing Negotiation Playbook",
            "type": "Market Report",
            "cat": "SOFTWARE",
            "content": \"\"\"
            NEGOTIATION INTELLIGENCE: MICROSOFT EA
            
            LEVERAGE POINTS:
            - Microsoft's fiscal year ends June 30th. Deals signed in Q4 (April-June) historically receive 5-8% deeper discounting on step-ups.
            - Unused Azure Commits (shortfalls) can often be rolled over if stepping up to M365 E5.
            
            PRICING BENCHMARKS (Enterprise > 5,000 seats):
            - M365 E3 to E5 Step-Up: Market average is an 8% to 10% uplift. Refuse initial 15% uplifts.
            - Azure Migration Credits: Ask for 10% of Year 1 Azure commit in transition deployment credits.
            \"\"\"
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
            "content": \"\"\"
            ENTERPRISE DISCOUNT PROGRAM (EDP) AGREEMENT
            PROVIDER: Amazon Web Services (AWS)
            
            [Page 4] COMMERCIAL TERMS
            Total Contract Value (TCV): $2,100,000 committed over a 3-year term constraint.
            
            [Page 12] TERMINATION
            Customer may terminate for convenience with 90 days prior written notice, subject to an early termination fee of $250,000.
            
            [Schedule A] SERVICE LEVEL AGREEMENT
            AWS guarantees 99.99% uptime for EC2 instances. Breach of this SLA entitles the customer to a 10% service credit against the monthly invoice. (Note: Negotiation target was 99.999%).
            \"\"\"
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
            "content": \"\"\"
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
            \"\"\"
        }
    ]
"""
    
    modified_content = content[:start_idx] + new_docs_code + content[end_idx:]
    
    with open(filepath, 'w') as f:
        f.write(modified_content)

if __name__ == "__main__":
    patch_file(sys.argv[1])
