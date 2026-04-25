export type DtpReadiness = "blocked" | "ready_with_warnings" | "ready";

export type DtpFieldSchema = {
  key: string;
  label: string;
  required: boolean;
  critical: boolean;
  optional?: boolean;
  source_priority?: Array<"case" | "summary" | "agent_output" | "human_decision">;
  ai_extractable?: boolean;
  document_dependency?: "rfx" | "supplier_response" | "contract" | "implementation";
  placeholder?: string;
  multiline?: boolean;
};

export const DTP_STAGE_SCHEMA: Record<string, DtpFieldSchema[]> = {
  "DTP-01": [
    { key: "request_title", label: "Request title", required: true, critical: true, ai_extractable: true, placeholder: "e.g. Global IT Service Desk Refresh" },
    { key: "business_unit", label: "Business unit", required: true, critical: true, ai_extractable: true, placeholder: "e.g. Global Operations" },
    { key: "scope_summary", label: "Scope summary", required: true, critical: true, ai_extractable: true, multiline: true, placeholder: "Summarize scope and constraints..." },
    { key: "estimated_annual_value_usd", label: "Estimated annual value (USD)", required: true, critical: true, ai_extractable: true, placeholder: "e.g. 4200000" },
    { key: "required_start_date", label: "Required start date", required: false, critical: false, optional: true, ai_extractable: true, placeholder: "e.g. 2026-08-01" },
    { key: "implementation_urgency", label: "Implementation urgency", required: false, critical: false, optional: true, ai_extractable: true, placeholder: "e.g. 6-12 months" },
  ],
  "DTP-02": [
    { key: "evaluation_criteria", label: "Evaluation criteria", required: true, critical: true, ai_extractable: true, multiline: true, placeholder: "Technical capability 30% ..." },
    { key: "mandatory_requirements", label: "Mandatory requirements", required: true, critical: true, ai_extractable: true, multiline: true, placeholder: "Pass/fail requirements..." },
    { key: "supplier_longlist", label: "Supplier longlist", required: true, critical: false, ai_extractable: true, multiline: true, placeholder: "Supplier A\nSupplier B" },
    { key: "risk_constraints", label: "Risk/compliance constraints", required: false, critical: false, optional: true, ai_extractable: true, multiline: true, placeholder: "Any non-negotiable controls..." },
  ],
  "DTP-03": [
    { key: "rfx_title", label: "RFx title", required: true, critical: true, ai_extractable: true, document_dependency: "rfx", placeholder: "RFP-2026-..." },
    { key: "rfx_issue_date", label: "RFx issue date", required: true, critical: true, ai_extractable: true, placeholder: "YYYY-MM-DD" },
    { key: "response_due_date", label: "Supplier response due date", required: true, critical: true, ai_extractable: true, placeholder: "YYYY-MM-DD" },
    { key: "supplier_clarification_feedback", label: "Supplier clarification feedback", required: false, critical: false, optional: true, ai_extractable: true, document_dependency: "supplier_response", multiline: true, placeholder: "Captured clarifications from suppliers..." },
  ],
  "DTP-04": [
    { key: "supplier_response_received", label: "Supplier responses received", required: true, critical: true, ai_extractable: true, placeholder: "e.g. 4/5" },
    { key: "supplier_evaluation_feedback", label: "Evaluation feedback notes", required: true, critical: true, ai_extractable: true, document_dependency: "supplier_response", multiline: true, placeholder: "Key evaluator observations..." },
    { key: "negotiation_feedback", label: "Negotiation feedback", required: true, critical: false, ai_extractable: true, multiline: true, placeholder: "Commercial and non-commercial feedback..." },
    { key: "award_recommendation", label: "Award recommendation", required: true, critical: true, ai_extractable: true, placeholder: "Recommended supplier / rationale" },
  ],
  "DTP-05": [
    { key: "contract_signed", label: "Contract signed confirmation", required: true, critical: true, ai_extractable: false, placeholder: "yes/no" },
    { key: "contract_owner_signoff", label: "Contract owner signoff", required: true, critical: true, ai_extractable: true, placeholder: "Name / date" },
    { key: "legal_signoff", label: "Legal signoff", required: true, critical: true, ai_extractable: true, placeholder: "Name / date" },
    { key: "contract_reference", label: "Contract reference", required: true, critical: false, ai_extractable: true, document_dependency: "contract", placeholder: "CT-..." },
  ],
  "DTP-06": [
    { key: "execution_started", label: "Execution started", required: true, critical: true, ai_extractable: false, placeholder: "yes/no" },
    { key: "implementation_milestones", label: "Implementation milestones", required: true, critical: true, ai_extractable: true, document_dependency: "implementation", multiline: true, placeholder: "Milestones and status..." },
    { key: "kpi_monitoring_status", label: "KPI monitoring status", required: true, critical: true, ai_extractable: true, multiline: true, placeholder: "Early KPI readout..." },
    { key: "execution_confirmed_by_human", label: "Human execution confirmation", required: true, critical: true, ai_extractable: false, placeholder: "yes/no" },
  ],
};

export function stageSchema(stage: string): DtpFieldSchema[] {
  return DTP_STAGE_SCHEMA[stage] || [];
}

export function computeStageReadiness(
  stage: string,
  values: Record<string, string>
): { readiness: DtpReadiness; missingCritical: DtpFieldSchema[]; missingRequired: DtpFieldSchema[] } {
  const schema = stageSchema(stage);
  const missingRequired = schema.filter((f) => f.required && !(values[f.key] || "").trim());
  const missingCritical = schema.filter((f) => f.critical && !(values[f.key] || "").trim());
  if (missingCritical.length > 0) return { readiness: "blocked", missingCritical, missingRequired };
  if (missingRequired.length > 0) return { readiness: "ready_with_warnings", missingCritical, missingRequired };
  return { readiness: "ready", missingCritical, missingRequired };
}

export function splitStageFields(stage: string, values: Record<string, string>) {
  const schema = stageSchema(stage);
  const prefilled = schema.filter((f) => (values[f.key] || "").trim().length > 0);
  const missing = schema.filter((f) => (values[f.key] || "").trim().length === 0 && (f.required || f.critical));
  const optional = schema.filter((f) => (values[f.key] || "").trim().length === 0 && !f.required && !f.critical);
  return { prefilled, missing, optional };
}
