# System 1 Sponsor Migration Runbook

This runbook is for migrating Sponsor data into System 1 using staged bulk upload.

## 1) Prepare source files

- Use the downloadable templates from:
  - `/api/system1/upload/templates/renewals_template.csv`
  - `/api/system1/upload/templates/new_business_template.csv`
- You can use CSV or Excel (`.csv`, `.xls`, `.xlsx`).
- For mixed evidence, you can also upload PDF/DOCX/TXT in preview.

## 2) Optional column mapping

If sponsor headers differ from canonical names, provide `column_mapping_json` in preview.

Example:

```json
{
  "supplier": "supplier_name",
  "spend": "estimated_spend_usd",
  "expiry_months": "months_to_expiry"
}
```

## 3) Preview and scoring

Call `POST /api/system1/upload/preview` with files.

Each row returns:

- `score_components` (per component value/confidence/source_type)
- `computed_total_score`, `computed_tier`
- `readiness_status` (`ready`, `ready_with_warnings`, `needs_review`)
- `readiness_warnings`

## 4) Approval governance

- `needs_review` rows cannot be approved.
- `ready_with_warnings` rows require explicit acknowledgment:
  - send `acknowledge_warning_row_ids` in `POST /api/system1/upload/approve`.

## 5) Persist + refresh

On approve:

- opportunities are persisted into Heatmap DB with provenance:
  - `score_provenance_json`
  - `system1_readiness_status`
  - `system1_warnings_json`
- scoring refresh is triggered in background.

## 6) Validation checklist

- Confirm all approved rows have expected `computed_tier`.
- Spot-check 5-10 rows for component provenance (`provided` vs `derived` vs `defaulted`).
- Confirm warning rows were intentionally acknowledged.
- Confirm downstream review workflow (pursue / do not pursue) remains functional.

## 7) Rollback strategy

- Re-run preview with corrected files and approve only corrected rows.
- Keep upload job IDs for audit trace.
- If needed, remove affected rows from `opportunity` where `source = 'upload_staged'` and re-import.
