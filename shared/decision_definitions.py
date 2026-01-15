"""
Decision definitions for each DTP stage.
Includes questions, validation rules, and critical paths.
"""

DTP_DECISIONS = {
    "DTP-01": {
        "title": "Strategy Definition",
        "description": "Define the sourcing strategy and route.",
        "questions": [
            {
                "id": "sourcing_required",
                "text": "Is new sourcing required for this case?",
                "type": "choice",
                "options": [
                    {"value": "Yes", "label": "Yes, proceed to sourcing"},
                    {"value": "No", "label": "No, reuse existing arrangement"},
                    {"value": "Cancel", "label": "Cancel request"}
                ],
                "required": True,
                "critical_path": {
                    "No": "TERMINATE",
                    "Cancel": "TERMINATE"
                }
            },
            {
                "id": "sourcing_route",
                "text": "What is the recommended sourcing route?",
                "type": "choice",
                "options": [
                    {"value": "Strategic", "label": "Strategic Sourcing (Full DTP)"},
                    {"value": "Tactical", "label": "Tactical Finding (3 Bids)"},
                    {"value": "Spot", "label": "Spot Buy (Fast Track)"}
                ],
                "required": True,
                "dependency": {"sourcing_required": "Yes"} # Only ask if yes
            }
        ]
    },
    "DTP-02": {
        "title": "Supplier Identification",
        "description": "Confirm the supplier list for evaluation.",
        "questions": [
             {
                "id": "supplier_list_confirmed",
                "text": "Is the supplier shortlist complete and ready for RFI/RFP?",
                "type": "choice",
                "options": [
                    {"value": "Yes", "label": "Yes, proceed to RFx"},
                    {"value": "No", "label": "No, find more suppliers"}
                ],
                "required": True
            }
        ]
    },
    "DTP-03": {
        "title": "RFx & Evaluation",
        "description": "Select the winning supplier.",
        "questions": [
             {
                "id": "evaluation_complete",
                "text": "Has technical and commercial evaluation been completed?",
                "type": "choice",
                "options": [
                    {"value": "Yes", "label": "Yes"},
                    {"value": "No", "label": "No"}
                ],
                "required": True
            }
        ]
    },
    "DTP-04": {
        "title": "Negotiation & Award",
        "description": "Approve the final commercial terms and award to supplier.",
        "questions": [
            {
                "id": "award_supplier_id",
                "text": "Which supplier are we awarding to?",
                "type": "text", # In real app, this would be a dynamic select from shortlist
                "required": True
            },
            {
                "id": "final_savings_confirmed",
                "text": "Have the final savings been validated by Finance?",
                "type": "choice",
                "options": [
                    {"value": "Yes", "label": "Yes"},
                    {"value": "No", "label": "No (Provisional)"}
                ],
                "required": True
            },
            {
                "id": "legal_approval",
                "text": "Has Legal approved the final contract terms?",
                "type": "choice",
                "options": [
                    {"value": "Yes", "label": "Yes"},
                    {"value": "No", "label": "No"}
                ],
                "required": True
            }
        ]
    },
    "DTP-05": {
        "title": "Internal Approval",
        "description": "Get final sign-off from stakeholders.",
        "questions": [
            {
                "id": "stakeholder_signoff",
                "text": "Have all key stakeholders signed the approval memo?",
                "type": "choice",
                "options": [{"value": "Yes", "label": "Yes"}],
                "required": True
            }
        ]
    },
    "DTP-06": {
        "title": "Implementation",
        "description": "Confirm contract execution and handover.",
        "questions": [
            {
                "id": "contract_signed",
                "text": "Is the contract fully signed and stored in CLM?",
                "type": "choice",
                "options": [{"value": "Yes", "label": "Yes"}],
                "required": True
            }
        ]
    }
}
