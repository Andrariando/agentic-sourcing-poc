# Implementation Plan — Product Hardening & Metrics

This document consolidates **proposed improvements** from technical and product review, **quick wins** (minimal effort), **medium-effort** work, and **KPI/KLI** implementation tracks. It complements:

- **[Opportunity_Scope_implementation_plan.md](Opportunity_Scope_implementation_plan.md)** — original phased build for the Opportunity Heatmap system
- **[BUSINESS_OVERVIEW.md](BUSINESS_OVERVIEW.md)** — business narrative and Azure long-term direction
- **[TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md)** — architecture reference

---

## 1. Strategic themes (from product / architecture review)

These themes address gaps between a **solo-analyst POC** and a **team production** system: data quality, concurrency, intent safety, configuration governance, evidence quality, and operational pull vs push.

| Theme | Problem | Direction |
|-------|---------|-----------|
| **Data quality** | Scoring is deterministic but inputs (dates, spend, supplier names, categories) are not enforced upstream. | Introduce validation flags, normalization pipeline over time, and honest UX copy. |
| **Outcome feedback** | Bridge is one-way (Heatmap → DTP); realized savings / cycle time / award outcomes do not recalibrate heatmap. | Capture outcome events and feed evaluation / future model calibration. |
| **Multi-user / concurrency** | No assignment or locking; duplicate approvals can create duplicate cases. | Claim/assign model, idempotent approve UX, optimistic concurrency. |
| **Intent routing** | Chat flow depends on LLM classification; misroutes can stall or skip steps. | Confidence thresholds, clarify prompts, structured audit logs. |
| **Category strategy config** | `category_cards.json` is manual and can go stale. | Versioning, editor workflow, audit of changes. |
| **Artifact verification** | Binary VERIFIED/UNVERIFIED is thin vs source quality and freshness. | Stronger evidence metadata over time. |
| **Notifications** | Pull-only UI; T1 and pending approvals can stall unnoticed. | Webhooks / email / Teams in later phases. |

---

## 2. Short-term / medium-term / longer-term (review roadmap)

These align with **[BUSINESS_OVERVIEW.md](BUSINESS_OVERVIEW.md)** (Azure pilot and production). They are **not** all implemented; treat as a prioritized backlog.

### 2.1 Short-term (before or during pilot)

| ID | Item | Rationale |
|----|------|-----------|
| S1 | **Data quality scoring layer** — flag opportunities with missing or suspicious inputs *before* tiers are trusted | Reduces false T1/T4 from bad ERP fields |
| S2 | **Idempotency + assignment** — prevent duplicate case creation; optional “claimed by” | Addresses concurrent category managers |
| S3 | **Intent confidence** — when `LLMResponder` is uncertain, ask a **clarification** question instead of guessing | Reduces silent workflow stalls |
| S4 | **Structured logging** for routing decisions (`intent`, `case_id`, `trace_id`) | Debug misroutes without exhaustive intent tests |
| S5 | **Category cards version** exposed via API (hash or `last_loaded`) | Ops knows if policy config is stale |
| S6 | **In-product copy** on fragile inputs (heatmap / intake) | Sets expectations without new backend |

### 2.2 Medium-term (pilot phase)

| ID | Item | Rationale |
|----|------|-----------|
| M1 | **Category cards editor** with history + approval workflow | SAS depends on config; reduce silent drift |
| M2 | **Outcome feedback loop** — savings realized, time-to-award, final outcomes from DTP → analytics / calibration dataset | Moves from self-referential learning to outcome-validated |
| M3 | **Webhook notifications** for T1 opportunities and stale pending approvals | Operational urgency |
| M4 | **Model drift / override dashboard** — overrides per category, component-level patterns | Admin visibility |

### 2.3 Longer-term (production)

| ID | Item | Rationale |
|----|------|-----------|
| L1 | **PostgreSQL** (or Azure SQL) before multi-user scale-out | SQLite limits concurrency and HA story |
| L2 | **MDM-style normalization** — supplier IDs, canonical categories, date parsing pipeline | Foundation for trustworthy scores |
| L3 | **Azure-aligned hosting** (see BUSINESS_OVERVIEW) | Identity, private endpoints, observability |

---

## 3. Quick wins (minimal effort)

High leverage vs effort; several need only copy + small API/UI changes.

| ID | Item | Notes |
|----|------|-------|
| QW1 | **Document “fragile input” in-product** — short copy on Heatmap / Intake that scores depend on contract dates, spend, category | Trust / expectation setting; no backend |
| QW2 | **Surface data-quality flags** — simple rules (missing expiry, default risk, unknown category, zero spend); `warnings[]` on opportunity or list API | Small backend helper + optional badges |
| QW3 | **Approve UX hardening** — disable button after submit; refresh opportunities; show “already linked to CASE-…” when bridged | Mostly frontend; pairs with server idempotency |
| QW4 | **Intent “clarify” path** — if classification is low-confidence or conflicting, force one disambiguation prompt | `chat_service` + prompt branch |
| QW5 | **Category cards version in API** — e.g. `category_cards_version` on `/api/heatmap/intake/categories` or context | Tiny backend change |
| QW6 | **Routing audit grep** — one structured log line per chat turn for intent + trace | Small logging change |
| QW7 | **Pilot / demo checklist in README** — seed data, pipeline run, env vars, known concurrency limits | Documentation only |

---

## 4. KPI / KLI — current state

| Surface | Status |
|---------|--------|
| **Heatmap “Sourcing Opportunity Matrix”** (KPI/KLI columns) | **Not functional** — deterministic mock values from `supplier_name` / `request_id` (see `frontend-next/src/app/heatmap/page.tsx`) |
| **`/dashboard/heatmap`** | **Not functional** — static numbers and placeholder charts |

Glossary tooltips (KPI vs KLI) are real; the **numbers are not** tied to telemetry.

---

## 5. KPI / KLI — quick wins (minimal backend)

| ID | Item | Notes |
|----|------|-------|
| KQ1 | **Derive what we already have** — per `opportunity_id`: count `ReviewFeedback` rows; flag “had human adjustment”; simple aggregates | Uses existing `heatmap.db` tables |
| KQ2 | **Optional API** — `GET /api/heatmap/metrics/summary` or `include_kli=true` on opportunities | Returns real derived fields only; replace mock columns in UI |
| KQ3 | **Honest labeling** — UI label: “Derived from feedback” vs “Demo metrics” until telemetry exists | Avoids false confidence |

---

## 6. KPI / KLI — medium effort

| ID | Item | Notes |
|----|------|-------|
| KM1 | **Persist pipeline telemetry** — per-opportunity or per-run: LangGraph duration, node list, timestamps in `AuditLog` or `heatmap_run_metrics` | Enables Agents Run / Exec Time |
| KM2 | **Dashboard aggregates** — replace static cards with rollups (feedback rate, avg time from `run/status` history if stored, approvals per week) | Requires stored events or daily rollups |
| KM3 | **Cycle time** — anchor timestamps: opportunity created → approved → `case_bridge` creates case | Needs consistent event recording |
| KM4 | **Charts** — replace placeholders with data from KM2 (simple bar/line from API) | Frontend + API |

---

## 7. KPI / KLI — longer / harder (outcome-linked)

| ID | Item | Notes |
|----|------|-------|
| KL1 | **True cycle time & savings** | Requires DTP-side events and/or **Heatmap ↔ DTP outcome loop** (see §2.2 M2) |
| KL2 | **“AI Reliability” as accepted-tier rate** | Needs definition + data from feedback vs original tier |

---

## 8. Suggested implementation order

1. **QW1 + QW2 + QW7** — expectations, flags, docs (days)
2. **QW3 + QW4 + QW6** — concurrency/intent safety and observability (small sprint)
3. **KQ1–KQ3** — replace mock KPI/KLI matrix with feedback-derived metrics (small sprint)
4. **S5 + M1** (split: version API first, editor later)
5. **KM1 → KM4** — telemetry then dashboard
6. **M2, M3, L1–L3** — per BUSINESS_OVERVIEW and pilot readiness

---

## 9. Traceability

| This plan section | Related docs |
|-------------------|--------------|
| Strategic themes | User assessment + [BUSINESS_OVERVIEW.md](BUSINESS_OVERVIEW.md) |
| §2 roadmap | Same + Azure subsection in BUSINESS_OVERVIEW |
| §3 Quick wins | Prior “quick win” engineering list |
| §4–7 KPI/KLI | Heatmap UI audit (`page.tsx`, `dashboard/heatmap/page.tsx`) |
| Original heatmap build phases | [Opportunity_Scope_implementation_plan.md](Opportunity_Scope_implementation_plan.md) |

---

*Last updated: March 2026*
