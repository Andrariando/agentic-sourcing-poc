# Sample Data v2 — Scoring preview (estimated)

- Generated: **2026-04-22 09:32** (local)
- Data folder: `Sample Data v2\Capstone Files`

## What this report is

Estimated **PS_contract** using the baseline weights from the heatmap supervisor (0.3·EUS + 0.25·FIS + 0.2·RSS + 0.15·SCS + 0.1·SAS), **without** learning nudges or DB-backed feedback.

### SCS imputation (demo / presentation)

- **Default ON:** when category-matched spend share is **0%**, SCS is replaced by (1) **global supplier share** = that supplier’s paid total ÷ all paid spend in the extract (when the supplier has paid lines), else (2) **neutral band** = treat as **15%** share (framework SCS ≈ **5.0**). Modes are recorded in `scs_impute_mode` in the CSV.
- Among **base-eligible** rows: **0** used global-supplier imputation; **3,676** used the neutral band (includes suppliers with no paid lines in extract).

### Join rules (preview)

- **RSS**: match contract `Supplier` (normalized) to metrics `Supplier`, else to `Supplier Parent`.
- **SCS**: sum `(P) Payment amount (USD)` where `> 0`, grouped by normalized `SMD cleansed name` + `Booked category`; category total = sum of payments in that booked category.
- **FIS**: contract value = first positive among `Contract Value`, `Full Contract Value`, `Value in USD`; denominator = max of those values **within the same `Category`** in the contract file.
- **EUS**: months from `Expiry Date` using the same month convention as `months_until_expiry_from_iso` (expired agreements → 0 months → high urgency band).

### Definition: **strict complete**

Renewal row counts as **strict complete** when: (1) parsed expiry, supplier present, contract value > 0; (2) **RSS** joins to supplier metrics (non-null risk in file after lookup); (3) **SCS** has positive attributed spend for that supplier **and** matching booked category (same normalization as contract `Category`).

SAS always receives a numeric default from `category_cards.json` when preferred status is absent.

## Dataset sizes

| Table | Rows |
| --- | ---: |
| Contracts | 7,390 |
| Spend lines | 5,839 |
| Metrics lines | 32,925 |
| Unique metrics suppliers (normalized) | 851 |
| Unique metrics supplier parents (normalized) | 854 |

## Cohort counts (renewal opportunities)

> **Finding:** The set of agreements with **metrics-backed RSS** and the set with **paid spend** on a matching supplier name **do not overlap** in this extract. So there are **no** strict- or practical-complete rows until join rules or source data improve.

| Cohort | Count | % of all contracts |
| --- | ---: | ---: |
| All contract rows | 7,390 | 100% |
| **Base eligible** (expiry + supplier + contract value > 0) | 3,732 | 50.5% |
| Base + **RSS** joined from metrics | 811 | 11.0% |
| Base + **SCS** (supplier+category spend > 0) | 56 | 0.8% |
| Base + spend on **supplier name** (any category, paid lines) | 56 | 0.8% |
| **Strict complete** (base + RSS + category-matched SCS) | **0** | **0.0%** |
| **Practical join** (base + RSS + supplier-level paid spend — SCS band may rely on narrow category match) | **0** | **0.0%** |
| Base + RSS **without** category-matched spend | 811 | 11.0% |
| Base + category-matched spend **without** RSS join | 56 | 0.8% |

## Estimated PS distribution (base-eligible rows only)

- **PS with observed SCS only** — mean **5.11**, median **5.20**
- **PS with imputed SCS** — mean **5.55**, median **5.65**

| Tier (observed SCS) | Count |
| --- | ---: |
| T1 | 0 |
| T2 | 8 |
| T3 | 3,549 |
| T4 | 175 |

| Tier (imputed SCS) | Count |
| --- | ---: |
| T1 | 2 |
| T2 | 211 |
| T3 | 3,352 |
| T4 | 167 |

### Base-eligible + metrics RSS (subset)

- Rows: **811** — PS observed mean **5.23**, median **5.36**
- PS imputed mean **5.68**, median **5.81**

## Strict-complete subset

*No rows met strict complete criteria with current joins.*

## Notes for stakeholders

- Rows that are **base eligible** but not **strict complete** still receive a full formula output here; RSS defaults to **3.0** raw when metrics do not match, and SCS may reflect **0% share** if spend does not link.
- **Imputed SCS** is for **presentation only** until spend keys align with contracts; do not treat `ps_imputed_scs` as production audit scores.
- Improving **strict complete** volume usually requires better **supplier identity** alignment between contracts and spend (or an agreement ID on spend lines).
