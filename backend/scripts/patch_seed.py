import sys
import json

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the start of cases_data = [
    start_idx = content.find('cases_data = [')
    
    # Find the end of the seed_cases function (where print("  [OK] Seeded... is))
    end_msg = 'print(f"  [OK] Seeded'
    end_idx = content.find(end_msg, start_idx)
    end_line_idx = content.find('\n', end_idx) + 1

    if start_idx == -1 or end_idx == -1:
        print("Could not find boundaries")
        return

    new_cases_code = """cases_data = [
        # ============================================================
        # CASE-001: DTP-01 (Strategy) - Global Telecom Consolidation
        # ============================================================
        {
            "case_id": "CASE-001",
            "name": "Global Telecom Consolidation",
            "category_id": "TELECOM",
            "dtp_stage": "DTP-01",
            "status": "Waiting for Human Decision",
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
            "waiting_for_human": True,
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
            "waiting_for_human": True,
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
            "status": "Waiting for Human Decision",
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
            "waiting_for_human": True,
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
            "waiting_for_human": True,
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
            "status": "Waiting for Human Decision",
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
            "waiting_for_human": True,
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
"""
    
    modified_content = content[:start_idx] + new_cases_code + content[end_line_idx:]
    
    with open(filepath, 'w') as f:
        f.write(modified_content)

if __name__ == "__main__":
    patch_file(sys.argv[1])
