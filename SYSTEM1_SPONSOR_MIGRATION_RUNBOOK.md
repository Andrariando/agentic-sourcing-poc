# System 1 Sponsor Migration Runbook

This runbook is for migrating Sponsor data into System 1 using staged bulk upload.

It now supports two preview modes:

- **Standard preview**: parse each file row-by-row (`/api/system1/upload/preview`)
- **Bundle scan preview**: parse + fuse contract/spend/metrics into deduplicated candidates (`/api/system1/upload/scan-bundle`)

## 1) Prepare source files

- Use the downloadable templates from:
  - `/api/system1/upload/templates/renewals_template.csv`
  - `/api/system1/upload/templates/new_business_template.csv`
- You can use CSV or Excel (`.csv`, `.xls`, `.xlsx`).
- For mixed evidence, you can also upload PDF/DOCX/TXT in **standard preview**.
- **Bundle scan** currently fuses **structured files only** (`csv/xls/xlsx`).

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

## 3) Choose preview mode

### A) Standard preview (existing behavior)

Call `POST /api/system1/upload/preview` with files.

Use this when:

- You want row-level control per source file
- You are uploading a single template-aligned file
- You want document extraction from PDF/DOCX/TXT

### B) Bundle scan preview (new)

Call `POST /api/system1/upload/scan-bundle` with multiple structured files.

Use this when:

- You have separate sponsor exports (for example contract + spend + supplier metrics)
- You want backend fusion before human review
- You want fewer duplicate/line-level candidates before approval

Fusion strategy in bundle scan:

- contract-led candidates first
- spend-led aggregated candidates for unmatched rows
- metrics-only candidates as low-confidence fallbacks

## 4) Preview output and scoring

Each row returns:

- `score_components` (per component value/confidence/source_type)
- `computed_total_score`, `computed_tier`
- `readiness_status` (`ready`, `ready_with_warnings`, `needs_review`)
- `readiness_warnings`
- `source_filename` and `row_id` for auditability

## 5) Approval governance

- `needs_review` rows cannot be approved.
- `ready_with_warnings` rows require explicit acknowledgment:
  - send `acknowledge_warning_row_ids` in `POST /api/system1/upload/approve`.

## 6) Persist + refresh

On approve:

- opportunities are persisted into Heatmap DB with provenance:
  - `score_provenance_json`
  - `system1_readiness_status`
  - `system1_warnings_json`
- scoring refresh is triggered in background.

## 7) Validation checklist

- Confirm all approved rows have expected `computed_tier`.
- Spot-check 5-10 rows for component provenance (`provided` vs `derived` vs `defaulted`).
- Confirm warning rows were intentionally acknowledged.
- Confirm downstream review workflow (pursue / do not pursue) remains functional.
- For bundle scan, verify sampled fused rows against source exports (supplier/category/spend merge quality).

## 8) Rollback strategy

- Re-run preview with corrected files and approve only corrected rows.
- Keep upload job IDs for audit trace.
- If needed, remove affected rows from `opportunity` where `source = 'upload_staged'` and re-import.

## 9) Recommended sponsor flow (high-volume)

1. Upload contract + spend + supplier metrics files together.
2. Run **bundle scan preview** (`/api/system1/upload/scan-bundle`).
3. Review `parsing_notes` and readiness mix.
4. Approve valid rows first.
5. Export/fix warning or review rows and re-run.
