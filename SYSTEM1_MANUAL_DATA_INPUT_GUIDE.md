# System 1 Manual Data Input Guide

This guide explains what data to manually input so System 1 can compute reliable scores with specialist-agent logic.

Use this when you are not doing bulk upload, or when you want to validate a few opportunities manually first.

If you are uploading multiple sponsor exports (contract + spend + metrics), use **bundle scan**
first (`POST /api/system1/upload/scan-bundle`) and then manually fix only exceptions.

## 1) Where to input manually

- Primary UI path: `frontend-next` Heatmap/Intake pages (single-opportunity input).
- API path (if needed): `POST /api/heatmap/intake` for new business requests.
- For renewals, use System 1 staged upload preview/approve and enter one row at a time if no dedicated renewal form is available.

For bulk sponsor ingestion:

- `POST /api/system1/upload/preview` = row-level parse of uploaded files
- `POST /api/system1/upload/scan-bundle` = fused/deduplicated multi-file candidate generation

## 2) Minimum data required per opportunity

These fields are the minimum for a valid scoring attempt:

- `category`
- `supplier_name` (or known supplier identifier)
- `estimated_spend_usd` (must be > 0)
- opportunity type context:
  - New business: `implementation_timeline_months`
  - Renewal: `contract_id` + (`contract_end_date` or `months_to_expiry`)

If any minimum field is missing, the row may become `needs_review` or produce low-confidence/defaulted components.

## 3) Recommended data for high-confidence scoring

Provide these when available to reduce defaults:

- `subcategory`
- `preferred_supplier_status` (`preferred`, `allowed`, `nonpreferred`)
- Renewal enrichers:
  - `contract_end_date` (YYYY-MM-DD)
  - `months_to_expiry` (if date is unavailable)
- Optional direct component inputs (only if trusted):
  - `rss_score`
  - `scs_score`
  - `sas_score`

## 4) Score components and what they depend on

System 1 computes/uses these components:

- Renewal path:
  - `EUS`: months to expiry / contract end date
  - `FIS`: normalized spend impact
  - `RSS`: provided risk or derived from supplier policy/risk signals
  - `SCS`: provided concentration or derived spend proxy
  - `SAS`: provided strategy score or derived from category cards + supplier status
- New business path:
  - `IUS`: implementation timeline
  - `ES`: normalized estimated spend
  - `CSIS`: category-spend proxy / category context
  - `SAS`: category strategy + supplier status

Each component is tracked as:

- `source_type`: `provided`, `derived`, or `defaulted`
- `confidence`
- `evidence_refs`
- `explanation`

## 5) Manual input checklist (per row)

Before saving/approving, verify:

1. Spend is positive and realistic (`estimated_spend_usd`).
2. Type is correct (`renewal` vs `new_business`).
3. Time field is present:
   - renewal: expiry context
   - new business: implementation timeline
4. Supplier and category are correctly spelled and normalized.
5. If setting direct scores (`rss/scs/sas`), values are on 0-10 scale and evidence-backed.

## 6) How to interpret readiness statuses

- `ready`: all required parts computed with acceptable confidence.
- `ready_with_warnings`: computation succeeded but some components are low-confidence/defaulted.
- `needs_review`: critical data is missing; do not proceed without fixes.

For warning rows, approval should include explicit acknowledgment and reviewer rationale.

## 7) Example manual payloads

### New business (API example)

```json
{
  "request_title": "Identity platform modernization",
  "category": "Software",
  "subcategory": "Security",
  "supplier_name": "VendorX",
  "estimated_spend_usd": 750000,
  "implementation_timeline_months": 5,
  "preferred_supplier_status": "allowed",
  "justification_summary_text": "Manual intake by sourcing manager."
}
```

### Renewal (single-row staged upload example)

```csv
row_type,category,subcategory,supplier_name,contract_id,contract_end_date,estimated_spend_usd,preferred_supplier_status
renewal,IT Infrastructure,Cloud Hosting,TechGlobal Inc,CNT-2026-100,2026-12-31,2500000,allowed
```

## 8) Data quality rules to enforce internally

- Use canonical category names (avoid free-text variants).
- Use consistent supplier names/IDs.
- Use ISO date format: `YYYY-MM-DD`.
- Keep monetary fields numeric only (no symbols or commas in API payloads).
- Document evidence source for any manually-entered component score.

## 9) Operational recommendation

For sponsor rollout:

- Start with 10-20 manually entered opportunities.
- Compare computed tiers with business expectations.
- Tune category cards/policies if systematic bias appears.
- Then move to bulk upload using templates and mapping.

At larger scale:

- Prefer **bundle scan** for initial candidate generation.
- Use manual edits only for `ready_with_warnings` / `needs_review` rows.

