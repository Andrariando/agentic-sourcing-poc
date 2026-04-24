# Data completeness & category guidance pipeline

This document captures how we **rank “complete” opportunities** from structured extracts and how **Word / policy guidance** feeds **richer scoring context** (especially **SAS** and optional **scoring_mix**). Use it when extending the heatmap or System 1 flows.

For the current System 1 upload implementation (LangGraph orchestration, top-N, rank modes, completeness/imputation suggestions), see: `backend/heatmap/SYSTEM1_AGENTIC_UPLOAD.md`.

## 1. Structured data (Excel / CSV) — “complete” cohorts

**Sources (Capstone-style):**

- `IT Infrastructure Contract Data.xlsx` — agreements, expiry, supplier, value fields.
- `IT Infra Spend.xlsx` — PO / payment lines, `SMD cleansed name`, `Booked category`, `(P) Payment amount (USD)`.
- `Supplier Metrics Data _ IT Inrastructure.xlsx` — `Supplier` / `Supplier Parent`, `Supplier Risk Score`, etc.

**Eligibility (renewal-style row):**

1. **Base eligible:** parsed **expiry**, non-empty **supplier**, **contract value** &gt; 0 (first positive among value columns).
2. **RSS join:** map contract `Supplier` to metrics `Supplier`, else **`Supplier Parent`** (normalized string match).
3. **SCS (observed):** roll up paid lines by **normalized (`SMD cleansed name`, `Booked category`)**; match contract **Category** to booked category; compute supplier share of category paid spend → **SCS** via `scs_from_supplier_share_pct`.
4. **Strict complete:** base + RSS + observed category-matched SCS (rare when names/keys don’t align across files).

**Known gaps in sample extracts:**

- Spend ↔ contract **keys** (MSA / contract sys id) often missing; **supplier string** overlap is weak → **SCS** often floor unless **imputed** (demo-only; see `backend/scripts/sample_data_v2_scoring_preview.py`).

**Reference implementation:** `backend/scripts/sample_data_v2_scoring_preview.py` (cohort counts, optional SCS imputation, `ps_observed_scs` / `ps_imputed_scs`).

## 2. Category guidance (Word / narrative) — scoring context

**Files:** e.g. `Category Guidance IT Infrastructure - *.docx` — narrative strategy, preferred suppliers, risk themes.

**How the app uses guidance today:**

- **Strategic Alignment (SAS)** and optional **weights** come from `data/heatmap/category_cards.json` (`default_preferred_status`, `supplier_preferred_status`, `category_strategy_sas`, `scoring_mix`).
- **Ingest path:** Heatmap ProcuraBot → **Category cards** tab → **Upload policy** → `POST /api/heatmap/category-cards/extract-upload`
  - Accepts **`.txt`, `.md`, `.docx`** (max 500KB).
  - **`.docx`:** plain text extracted in `backend/heatmap/services/upload_plain_text.py` (paragraphs + table rows).
  - Then **`assist_category_card_from_unstructured`** runs a **deterministic** pattern pass → `proposed_patch`.
- **If the Word doc is mostly narrative:** deterministic extract may return an **empty patch** → use **Suggest patch (LLM)** (`/api/heatmap/category-cards/assist`) with instructions referencing the same policy themes, or paste extracted text into assist.
- **Apply:** `POST /api/heatmap/category-cards/apply` or **`apply-and-rerun`** to merge into `category_cards.json` and refresh **batch** scores.

**Effect on “top complete” rows:**

- Does **not** fix **RSS/SCS joins** from Excel; it **enriches SAS** (and optionally formula weights) for the **category**, so high-FIS / high-EUS opportunities get **more accurate strategy alignment** once supplier names in data align with `supplier_preferred_status` keys.

## 3. Target end-state capability (product)

| Stage | Purpose |
|--------|--------|
| **A. Entity resolution** | Golden supplier ID or normalized parent across contract / spend / metrics. |
| **B. Eligibility & tiers** | Base / RSS / SCS-observed / strict-complete flags per opportunity (stored or computed at preview). |
| **C. Guidance binding** | Map subcategory (or commodity) → **which** guidance doc applies; extract or LLM-assist → **category_cards** (or per-subcategory keys if JSON schema extended). |
| **D. Presentation** | UI shows **data completeness** badges + **policy context** snippet (from cards or RAG over guidance text). |

## 4. Related code

- `backend/heatmap/context_builder.py` — loads `category_cards.json`.
- `backend/heatmap/scoring_framework.py` — `sas_from_category_cards`, SCS/FIS/EUS helpers.
- `backend/heatmap/services/heatmap_copilot.py` — unstructured extract + assist.
- `backend/heatmap/heatmap_router.py` — `category-cards/extract-upload`, `assist`, `apply`.
- `backend/heatmap/services/upload_plain_text.py` — **docx → text** for uploads.
