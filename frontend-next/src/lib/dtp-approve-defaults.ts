/**
 * Mirrors `shared/decision_definitions.py` — values sent with "Approve" so
 * `process_decision` semantic validation passes for each DTP stage.
 */
export function buildDecisionDataForStage(
  stage: string,
  supplierId: string | undefined
): Record<string, string> | null {
  const sid = (supplierId && supplierId.trim()) || "Primary supplier";

  switch (stage) {
    case "DTP-01":
      return {
        sourcing_required: "Yes",
        sourcing_route: "Strategic",
      };
    case "DTP-02":
      return { supplier_list_confirmed: "Yes" };
    case "DTP-03":
      return { evaluation_complete: "Yes" };
    case "DTP-04":
      return {
        award_supplier_id: sid,
        final_savings_confirmed: "Yes",
        legal_approval: "Yes",
      };
    case "DTP-05":
      return { stakeholder_signoff: "Yes" };
    case "DTP-06":
      return { contract_signed: "Yes" };
    default:
      return null;
  }
}
