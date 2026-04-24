# System 1 Agentic Upload (LangGraph)

This document describes the current System 1 upload analysis flow and how to use it for top-N prioritization with completeness and imputation guidance.

## What is implemented

- Endpoint: `POST /api/system1/upload/scan-bundle`
- Endpoint: `POST /api/system1/upload/preview`
- Optional controls:
  - `top_n` (integer)
  - `rank_by` (`completeness`, `score`, `hybrid`)

Both endpoints return:

- `candidates` (ranked rows)
- `analysis` (dataset-level completeness and suggested actions)

For a high-quality input format, use `complete_dataset_template.csv` and the fill guide in `backend/heatmap/SYSTEM1_COMPLETE_DATASET_TEMPLATE.md`.

## LangGraph flow (scan-bundle)

`scan-bundle` runs through `backend/heatmap/services/system1_ingestion_graph.py`:

1. `fuse_bundle_rows`
2. `score_and_enrich_candidates`
3. `summarize_completeness`
4. `prioritize_top_n`

The execution path is returned in `analysis.execution_trace`.

## Ranking behavior

`rank_by` controls sorting before `top_n` is applied:

- `completeness`:
  - completeness score, confidence, total score, spend
- `score`:
  - total score, completeness score, confidence, spend
- `hybrid`:
  - weighted mix favoring completeness and confidence, then score/spend tie-breakers

`analysis.rank_by_applied` confirms which ranking mode was used.

## Completeness and action suggestions

Per-row fields:

- `completeness_score`
- `defaulted_components`
- `low_confidence_components`
- `missing_critical_fields`
- `suggested_actions` (includes imputation-oriented recommendations)

Dataset-level `analysis` fields:

- `total_rows_analyzed`
- `scoreable_rows`
- `readiness_breakdown`
- `defaulted_component_counts`
- `imputation_action_candidates`
- `returned_rows`
- `top_n_applied`
- `rank_by_applied`

## UI behavior (System 1 upload page)

- User can choose:
  - Top rows (`top_n`)
  - Rank by (`completeness`, `score`, `hybrid`)
- UI displays:
  - Agentic completeness summary panel
  - LangGraph execution trace
  - Common imputation/suggested actions
  - Per-row completeness and suggested actions

## Example usage

`scan-bundle` with top 50 ranked by completeness:

- `top_n=50`
- `rank_by=completeness`

`scan-bundle` with top 50 ranked by score:

- `top_n=50`
- `rank_by=score`

## Notes for ERP integration

The same flow can be used for ERP/API ingestion by replacing file parsing inputs with API-sourced normalized rows, then invoking the same scoring/completeness/ranking steps. This keeps behavior consistent across file and API channels.

