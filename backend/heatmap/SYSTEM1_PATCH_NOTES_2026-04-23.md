# System 1 Patch Notes (2026-04-23)

This document summarizes the recent System 1 patch across upload, heatmap table/review UX, score transparency, and admin operations.

## Scope

The patch addressed:

1. Upload preview rendering stability and data readability.
2. Heatmap table clarity (renewal vs new opportunity), search/filter/sort controls.
3. Review drawer score explainability and artifact usefulness.
4. Consistent score refresh behavior after human review updates.
5. Admin-only style cleanup mechanism for upload-staged data (temporary, no auth gate yet).

## Frontend Changes

### 1) Upload Preview Table Stability (`frontend-next/src/app/system-1/upload/page.tsx`)

- Replaced fragile table-row virtualization rendering that caused overlapping/misaligned rows.
- Switched to standard table row rendering with existing "Load more" pagination.
- Added warning text normalization and constrained warning cell overflow to prevent layout breakage.

Result:
- Large warning payloads no longer corrupt row rendering.
- Preview remains readable for mixed/dirty upload inputs.

### 2) Heatmap Table Improvements (`frontend-next/src/app/heatmap/page.tsx`)

- Added explicit **Type** display for each row:
  - `Renewal`
  - `New Opportunity`
- Added table controls:
  - Search (supplier/request/title/contract/category)
  - Type filter (`All`, `Renewal`, `New Opportunity`)
  - Sort (`Score`, `Spend`, `Expiry`, `Name`)
- Improved naming fallback for non-renewals:
  - Prefer `supplier_name`
  - Then `request_title`
  - Then safe fallback label

Result:
- Easier analysis and navigation in large pipelines.
- No more misleading supplier fallback labels for supplier-less new requests.

### 3) Review Drawer UX/Logic Updates (`frontend-next/src/app/heatmap/page.tsx`)

- Added **Scoring Inputs Used** section with key fields:
  - type, spend, contract end, months to expiry, implementation timeline, preferred supplier status.
- Replaced manual tier override selector with score-derived priority display.
  - Pursuit decision remains independent.
- On save, table data is now refreshed from backend `/api/heatmap/opportunities` to avoid stale local state.

Result:
- Priority alignment is consistent with score logic.
- Updated scores reliably show in the table after save.

### 4) Supporting Artifacts in Review Drawer (`frontend-next/src/app/heatmap/page.tsx`)

- Removed placeholder artifact list.
- Review drawer now shows real source artifacts from row provenance.
- Added artifact download/open links when available.

Result:
- Artifacts are usable and traceable to uploaded inputs.

### 5) Pipeline Value Behavior (`frontend-next/src/app/heatmap/page.tsx`)

- Removed demo fallback `$14.2M` when value is zero.
- Always shows computed value (`$0` if no spend rows).

Result:
- KPI card reflects actual data, not placeholder value.

## Backend Changes

### 1) Upload Artifact Persistence and Download (`backend/main.py`)

- Added persisted storage for System 1 uploaded files under `backend/data/system1_uploads`.
- Added filename sanitization and UUID-based stored names.
- Stored upload metadata (`stored_name`, `original_filename`, `download_url`, size) in upload job state.
- Added new endpoint:
  - `GET /api/system1/upload/files/{stored_name}`
  - Returns uploaded file as downloadable payload.

### 2) Provenance Enrichment on Approval (`backend/main.py`)

- During `/api/system1/upload/approve`, persisted opportunities now include richer `score_provenance_json`:
  - score components
  - row type/source metadata
  - scoring input fields
  - supporting artifacts list

### 3) Heatmap Opportunities Payload Enrichment (`backend/heatmap/heatmap_router.py`)

- `/api/heatmap/opportunities` now includes normalized fields for UI consumption:
  - `opportunity_type` (`renewal` / `new_business`)
  - parsed `score_provenance`
  - parsed `system1_warnings`
  - `supporting_artifacts` extracted from provenance

### 4) Clear Upload-Staged Data Endpoint (`backend/main.py`)

- Added temporary admin utility endpoint:
  - `POST /api/system1/admin/clear`
- Current behavior:
  - clears persisted upload artifact files
  - clears in-memory upload jobs
  - deletes `Opportunity` rows with `source = "upload_staged"`
  - deletes linked feedback/audit rows for those opportunities

Notes:
- This endpoint is intentionally low-visibility in UI.
- Authentication/authorization should be added before production use.

## Validation / Testing

Executed after patch:

- `python -m py_compile backend/main.py` -> passed.
- `python -m py_compile backend/heatmap/heatmap_router.py` -> passed.
- `python -m pytest tests/test_heatmap_api.py` -> passed (`28 passed`).
- Frontend lint on `src/app/heatmap/page.tsx` still shows pre-existing `no-explicit-any` debt in that file.

## Operational Notes

1. Restart backend and frontend after pulling this patch.
2. For artifact links to work, uploaded files must be created after this patch (new persisted upload flow).
3. The clear endpoint is currently unguarded; treat as non-production admin utility.

## Follow-Up Recommendations

1. Add role-based protection for `POST /api/system1/admin/clear`.
2. Add integration tests for:
   - artifact persistence + download endpoint
   - opportunities response enrichment fields
   - score-reflects-in-table flow after feedback save.
3. Reduce `any` usage in `frontend-next/src/app/heatmap/page.tsx` to satisfy lint policy.

