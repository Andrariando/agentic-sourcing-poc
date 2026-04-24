# System 1 Complete Dataset Template

Use `complete_dataset_template.csv` from:

- `GET /api/system1/upload/templates`
- `GET /api/system1/upload/templates/complete_dataset_template.csv`

This template is designed so System 1 can:

- parse rows deterministically
- validate required fields
- score rows
- report completeness and suggested actions

## Columns

- `row_type`: `renewal` or `new_business`
- `category`: sourcing category (for example `IT Infrastructure`)
- `subcategory`: sourcing subcategory
- `supplier_name`: supplier legal/cleansed name
- `contract_id`: required for renewal rows, blank for new business rows
- `request_title`: required for new business rows, optional for renewals
- `contract_end_date`: `YYYY-MM-DD` (renewal path)
- `months_to_expiry`: numeric (renewal path, optional if `contract_end_date` is present)
- `estimated_spend_usd`: positive numeric value
- `implementation_timeline_months`: numeric for new business rows
- `preferred_supplier_status`: `preferred`, `allowed`, `nonpreferred` (or your accepted variants)
- `rss_score`: optional 0-10 (provide to avoid RSS default/derivation)
- `scs_score`: optional 0-10 (provide to avoid SCS default/derivation)
- `sas_score`: optional 0-10 (provide to avoid SAS derivation from policy cards)

## 100% complete guidance

For best completeness score and least fallback/defaulting:

- always provide: `row_type`, `category`, `subcategory`, `supplier_name`, `estimated_spend_usd`
- renewal rows: provide `contract_id` and either `months_to_expiry` or `contract_end_date`
- new business rows: provide `request_title` and `implementation_timeline_months`
- provide `preferred_supplier_status`
- provide `rss_score`, `scs_score`, `sas_score` when available

## Validation notes

- `estimated_spend_usd` must be > 0 for approval readiness
- unsupported or blank critical fields reduce completeness score and trigger suggested actions
- if `top_n` is used, ranking follows `rank_by` (`completeness`, `score`, `hybrid`)

