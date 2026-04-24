"""
Sample Data v2 — join feasibility + estimated PS_contract preview (baseline formula only).

Reads the three Capstone Excel extracts, applies normalized joins aligned with the heatmap
agents (no DB, no learning nudge). Writes a Markdown report under Sample Data v2/.

**SCS imputation (optional, default ON):** when category-matched supplier spend is missing,
uses (1) supplier share of **all** paid spend in the extract, else (2) a neutral concentration
band (15% share → SCS 5.0) for demo-only presentation. Flagged in `scs_impute_mode`.

Usage (from repo root):
  python backend/scripts/sample_data_v2_scoring_preview.py

Optional:
  python backend/scripts/sample_data_v2_scoring_preview.py --sample-csv sample_output.csv
  python backend/scripts/sample_data_v2_scoring_preview.py --no-impute
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.heatmap.context_builder import load_category_cards  # noqa: E402
from backend.heatmap.scoring_framework import (  # noqa: E402
    eus_from_months_to_expiry,
    fis_from_contract_value,
    months_until_expiry_from_iso,
    rss_from_supplier_risk_raw,
    scs_from_supplier_share_pct,
    sas_from_category_cards,
)

DEFAULT_DATA_DIR = ROOT / "Sample Data v2" / "Capstone Files"
CONTRACT_FILE = "IT Infrastructure Contract Data.xlsx"
SPEND_FILE = "IT Infra Spend.xlsx"
METRICS_FILE = "Supplier Metrics Data _ IT Inrastructure.xlsx"

W_EUS, W_FIS, W_RSS, W_SCS, W_SAS = 0.30, 0.25, 0.20, 0.15, 0.10

# When imputing SCS: synthetic 15% share maps to framework band (SCS ≈ 5.0).
_NEUTRAL_PROXY_SHARE_PCT = 15.0


def _norm(s: object) -> str:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    t = str(s).strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _money_row(row: pd.Series) -> float:
    for col in ("Contract Value", "Full Contract Value", "Value in USD"):
        if col not in row.index:
            continue
        v = row[col]
        try:
            if pd.isna(v):
                continue
            x = float(v)
            if x > 0:
                return x
        except (TypeError, ValueError):
            continue
    return 0.0


def _expiry_iso(row: pd.Series) -> str | None:
    if "Expiry Date" not in row.index:
        return None
    v = row["Expiry Date"]
    if pd.isna(v):
        return None
    if hasattr(v, "strftime"):
        try:
            return v.strftime("%Y-%m-%d")
        except Exception:
            pass
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def build_metrics_lookups(mdf: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Mean Supplier Risk Score by normalized Supplier and Supplier Parent."""
    rs = "Supplier Risk Score"
    by_sup: dict[str, list[float]] = {}
    by_par: dict[str, list[float]] = {}
    for _, row in mdf.iterrows():
        raw = row.get(rs)
        try:
            if pd.isna(raw):
                continue
            score = float(raw)
        except (TypeError, ValueError):
            continue
        ns = _norm(row.get("Supplier"))
        npa = _norm(row.get("Supplier Parent"))
        if ns:
            by_sup.setdefault(ns, []).append(score)
        if npa:
            by_par.setdefault(npa, []).append(score)

    def mean_dict(d: dict[str, list[float]]) -> dict[str, float]:
        return {k: sum(v) / len(v) for k, v in d.items()}

    return mean_dict(by_sup), mean_dict(by_par)


def lookup_rss(name: str, by_sup: dict[str, float], by_par: dict[str, float]) -> tuple[float | None, str]:
    n = _norm(name)
    if not n:
        return None, "missing supplier"
    if n in by_sup:
        return by_sup[n], "metrics.Supplier"
    if n in by_par:
        return by_par[n], "metrics.Supplier Parent"
    return None, "no_metrics_match"


def build_spend_rollups(sf: pd.DataFrame) -> tuple[
    dict[tuple[str, str], float],
    dict[str, float],
    dict[str, float],
]:
    """Returns (supplier+category spend, category totals, supplier totals across categories)."""
    pay_col = "(P) Payment amount (USD)"
    smd = "SMD cleansed name"
    booked = "Booked category"
    if pay_col not in sf.columns or smd not in sf.columns or booked not in sf.columns:
        return {}, {}, {}

    pay = pd.to_numeric(sf[pay_col], errors="coerce").fillna(0.0)
    sub = sf.assign(_pay=pay).loc[pay > 0].copy()
    sub["_s"] = sub[smd].map(_norm)
    sub["_c"] = sub[booked].map(_norm)
    sub_cat = sub[(sub["_s"] != "") & (sub["_c"] != "")]
    sub_sup_only = sub[sub["_s"] != ""]

    sup_cat: dict[tuple[str, str], float] = {}
    for (_, r) in sub_cat.iterrows():
        key = (r["_s"], r["_c"])
        sup_cat[key] = sup_cat.get(key, 0.0) + float(r["_pay"])

    cat_tot: dict[str, float] = {}
    for (_, r) in sub_cat.iterrows():
        cat_tot[r["_c"]] = cat_tot.get(r["_c"], 0.0) + float(r["_pay"])

    sup_tot: dict[str, float] = {}
    for (_, r) in sub_sup_only.iterrows():
        sup_tot[r["_s"]] = sup_tot.get(r["_s"], 0.0) + float(r["_pay"])

    return sup_cat, cat_tot, sup_tot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-md", type=Path, default=ROOT / "Sample Data v2" / "Scoring_Preview_Report.md")
    parser.add_argument("--sample-csv", type=Path, default=None, help="Write strict-complete rows to CSV")
    parser.add_argument(
        "--no-impute",
        action="store_true",
        help="Disable SCS imputation; ps_contract_imputed equals observed path only.",
    )
    args = parser.parse_args()
    data_dir = args.data_dir
    today = datetime.today()

    paths = {
        "contracts": data_dir / CONTRACT_FILE,
        "spend": data_dir / SPEND_FILE,
        "metrics": data_dir / METRICS_FILE,
    }
    for label, p in paths.items():
        if not p.is_file():
            print(f"Missing file ({label}): {p}", file=sys.stderr)
            return 1

    print("Loading Excel files (may take ~30–60s)...")
    contracts = pd.read_excel(paths["contracts"], sheet_name=0)
    spend = pd.read_excel(paths["spend"], sheet_name=0)
    metrics = pd.read_excel(paths["metrics"], sheet_name=0)

    by_sup, by_par = build_metrics_lookups(metrics)
    sup_cat_spend, cat_total_spend, sup_total_spend = build_spend_rollups(spend)
    total_paid_global = float(sum(sup_total_spend.values()))

    impute_on = not args.no_impute

    # Max TCV per category (same cohort as pipeline init)
    cat_max: dict[str, float] = {}
    for _, row in contracts.iterrows():
        cat = _norm(row.get("Category")) or "uncategorized"
        cat_max[cat] = max(cat_max.get(cat, 0.0), _money_row(row))

    category_cards = load_category_cards()

    rows_out: list[dict] = []
    # Counters
    n_contract = len(contracts)
    n_base = 0  # expiry + supplier + money + months parse
    n_rss_join = 0
    n_scs_join = 0  # supplier+category has spend > 0 in rollup
    n_scs_supplier_any = 0  # any payment-backed spend on supplier name (all categories)
    n_strict = 0
    n_relaxed_rss_only = 0  # base + RSS, no category-matched spend
    n_relaxed_scs_only = 0  # base + category SCS, metrics miss
    n_practical = 0  # base + RSS + any supplier-level paid spend (name match)
    n_imputed_global = 0
    n_imputed_neutral = 0

    for idx, row in contracts.iterrows():
        money = _money_row(row)
        iso = _expiry_iso(row)
        sup_raw = row.get("Supplier")
        sup = _norm(sup_raw)
        cat_raw = row.get("Category")
        cat = _norm(cat_raw)

        months = months_until_expiry_from_iso(iso, today) if iso else None
        base_ok = bool(sup and money > 0 and months is not None)
        if base_ok:
            n_base += 1

        rss_raw, rss_src = lookup_rss(str(sup_raw or ""), by_sup, by_par)
        rss_join_ok = rss_raw is not None
        if base_ok and rss_join_ok:
            n_rss_join += 1

        key_sc = (sup, cat)
        sc_spend = sup_cat_spend.get(key_sc, 0.0)
        cat_tot = cat_total_spend.get(cat, 0.0)
        scs_join_ok = base_ok and sc_spend > 0 and cat_tot > 0
        if base_ok and scs_join_ok:
            n_scs_join += 1

        sup_any = sup_total_spend.get(sup, 0.0)
        if base_ok and sup_any > 0:
            n_scs_supplier_any += 1

        strict = base_ok and rss_join_ok and scs_join_ok
        if strict:
            n_strict += 1
        if base_ok and rss_join_ok and not scs_join_ok:
            n_relaxed_rss_only += 1
        if base_ok and scs_join_ok and not rss_join_ok:
            n_relaxed_scs_only += 1
        if base_ok and rss_join_ok and sup_any > 0:
            n_practical += 1

        if not base_ok:
            continue

        eus = eus_from_months_to_expiry(float(months))
        max_tcv = cat_max.get(cat, 0.0)
        fis = fis_from_contract_value(money, max_tcv)
        rss = rss_from_supplier_risk_raw(rss_raw if rss_raw is not None else 3.0)
        share_pct_obs = (100.0 * sc_spend / cat_tot) if cat_tot > 0 else 0.0
        scs_observed = scs_from_supplier_share_pct(share_pct_obs)

        if share_pct_obs > 0:
            scs_impute_mode = "observed"
            share_effective_pct = share_pct_obs
            scs_effective = scs_observed
        elif not impute_on:
            scs_impute_mode = "no_imputation"
            share_effective_pct = share_pct_obs
            scs_effective = scs_observed
        else:
            if total_paid_global > 0 and sup_any > 0:
                share_effective_pct = min(100.0, 100.0 * sup_any / total_paid_global)
                scs_effective = scs_from_supplier_share_pct(share_effective_pct)
                scs_impute_mode = "imputed_global_supplier_share"
                n_imputed_global += 1
            else:
                share_effective_pct = _NEUTRAL_PROXY_SHARE_PCT
                scs_effective = scs_from_supplier_share_pct(_NEUTRAL_PROXY_SHARE_PCT)
                scs_impute_mode = (
                    "imputed_neutral_no_paid_denominator" if total_paid_global <= 0 else "imputed_neutral_band"
                )
                n_imputed_neutral += 1

        sas, _ = sas_from_category_cards(
            str(cat_raw or "IT Infrastructure"),
            str(sup_raw or "").strip() or None,
            False,
            None,
            category_cards,
        )

        ps_observed_scs = (W_EUS * eus) + (W_FIS * fis) + (W_RSS * rss) + (W_SCS * scs_observed) + (W_SAS * sas)
        ps_imputed_scs = (W_EUS * eus) + (W_FIS * fis) + (W_RSS * rss) + (W_SCS * scs_effective) + (W_SAS * sas)

        cid = row.get("Master Agreement Reference Number") or row.get("Contract Sys ID") or f"row_{idx}"

        rows_out.append(
            {
                "contract_key": str(cid),
                "supplier": str(sup_raw or "")[:120],
                "category": str(cat_raw or ""),
                "months_to_expiry": round(float(months), 2),
                "contract_value_usd": round(money, 2),
                "eus": round(eus, 2),
                "fis": round(fis, 2),
                "rss_raw": rss_raw,
                "rss_src": rss_src,
                "rss": round(rss, 2),
                "scs_observed": round(scs_observed, 2),
                "supplier_share_observed_pct": round(share_pct_obs, 2),
                "scs_effective": round(scs_effective, 2),
                "supplier_share_effective_pct": round(share_effective_pct, 2),
                "scs_impute_mode": scs_impute_mode,
                "sas": round(sas, 2),
                "ps_observed_scs": round(ps_observed_scs, 2),
                "ps_imputed_scs": round(ps_imputed_scs, 2),
                "tier_observed": (
                    "T1" if ps_observed_scs >= 8 else "T2" if ps_observed_scs >= 6 else "T3" if ps_observed_scs >= 4 else "T4"
                ),
                "tier_imputed": (
                    "T1" if ps_imputed_scs >= 8 else "T2" if ps_imputed_scs >= 6 else "T3" if ps_imputed_scs >= 4 else "T4"
                ),
                "strict_complete": strict,
                "supplier_total_spend_usd": round(sup_any, 2),
                "practical_complete": bool(base_ok and rss_join_ok and sup_any > 0),
            }
        )

    strict_df = pd.DataFrame([r for r in rows_out if r.get("strict_complete")])
    practical_df = pd.DataFrame([r for r in rows_out if r.get("practical_complete")])
    all_df = pd.DataFrame(rows_out)

    # --- Report ---
    lines: list[str] = []
    lines.append("# Sample Data v2 — Scoring preview (estimated)")
    lines.append("")
    lines.append(f"- Generated: **{datetime.now().strftime('%Y-%m-%d %H:%M')}** (local)")
    lines.append(f"- Data folder: `{data_dir.relative_to(ROOT)}`")
    lines.append("")
    lines.append("## What this report is")
    lines.append("")
    lines.append(
        "Estimated **PS_contract** using the baseline weights from the heatmap supervisor "
        f"({W_EUS}·EUS + {W_FIS}·FIS + {W_RSS}·RSS + {W_SCS}·SCS + {W_SAS}·SAS), **without** "
        "learning nudges or DB-backed feedback."
    )
    lines.append("")
    if impute_on:
        lines.append("### SCS imputation (demo / presentation)")
        lines.append("")
        lines.append(
            "- **Default ON:** when category-matched spend share is **0%**, SCS is replaced by "
            "(1) **global supplier share** = that supplier’s paid total ÷ all paid spend in the extract "
            "(when the supplier has paid lines), else (2) **neutral band** = treat as **15%** share "
            f"(framework SCS ≈ **{scs_from_supplier_share_pct(_NEUTRAL_PROXY_SHARE_PCT):.1f}**). "
            "Modes are recorded in `scs_impute_mode` in the CSV."
        )
        lines.append(
            f"- Among **base-eligible** rows: **{n_imputed_global:,}** used global-supplier imputation; "
            f"**{n_imputed_neutral:,}** used the neutral band (includes suppliers with no paid lines in extract)."
        )
        lines.append("")
    lines.append("### Join rules (preview)")
    lines.append("")
    lines.append("- **RSS**: match contract `Supplier` (normalized) to metrics `Supplier`, else to `Supplier Parent`.")
    lines.append(
        "- **SCS**: sum `(P) Payment amount (USD)` where `> 0`, grouped by normalized "
        "`SMD cleansed name` + `Booked category`; category total = sum of payments in that booked category."
    )
    lines.append(
        "- **FIS**: contract value = first positive among `Contract Value`, `Full Contract Value`, `Value in USD`; "
        "denominator = max of those values **within the same `Category`** in the contract file."
    )
    lines.append(
        "- **EUS**: months from `Expiry Date` using the same month convention as `months_until_expiry_from_iso` "
        "(expired agreements → 0 months → high urgency band)."
    )
    lines.append("")
    lines.append("### Definition: **strict complete**")
    lines.append("")
    lines.append(
        "Renewal row counts as **strict complete** when: (1) parsed expiry, supplier present, contract value > 0; "
        "(2) **RSS** joins to supplier metrics (non-null risk in file after lookup); "
        "(3) **SCS** has positive attributed spend for that supplier **and** matching booked category "
        "(same normalization as contract `Category`)."
    )
    lines.append("")
    lines.append("SAS always receives a numeric default from `category_cards.json` when preferred status is absent.")
    lines.append("")
    lines.append("## Dataset sizes")
    lines.append("")
    lines.append(f"| Table | Rows |")
    lines.append(f"| --- | ---: |")
    lines.append(f"| Contracts | {n_contract:,} |")
    lines.append(f"| Spend lines | {len(spend):,} |")
    lines.append(f"| Metrics lines | {len(metrics):,} |")
    lines.append(f"| Unique metrics suppliers (normalized) | {len(by_sup):,} |")
    lines.append(f"| Unique metrics supplier parents (normalized) | {len(by_par):,} |")
    lines.append("")
    lines.append("## Cohort counts (renewal opportunities)")
    lines.append("")
    if n_strict == 0 and n_practical == 0 and n_rss_join > 0 and n_scs_supplier_any > 0:
        lines.append(
            "> **Finding:** The set of agreements with **metrics-backed RSS** and the set with **paid spend** "
            "on a matching supplier name **do not overlap** in this extract. So there are **no** "
            "strict- or practical-complete rows until join rules or source data improve."
        )
        lines.append("")
    lines.append("| Cohort | Count | % of all contracts |")
    lines.append("| --- | ---: | ---: |")
    pct = lambda c: (100.0 * c / n_contract) if n_contract else 0.0
    lines.append(f"| All contract rows | {n_contract:,} | 100% |")
    lines.append(f"| **Base eligible** (expiry + supplier + contract value > 0) | {n_base:,} | {pct(n_base):.1f}% |")
    lines.append(f"| Base + **RSS** joined from metrics | {n_rss_join:,} | {pct(n_rss_join):.1f}% |")
    lines.append(f"| Base + **SCS** (supplier+category spend > 0) | {n_scs_join:,} | {pct(n_scs_join):.1f}% |")
    lines.append(f"| Base + spend on **supplier name** (any category, paid lines) | {n_scs_supplier_any:,} | {pct(n_scs_supplier_any):.1f}% |")
    lines.append(f"| **Strict complete** (base + RSS + category-matched SCS) | **{n_strict:,}** | **{pct(n_strict):.1f}%** |")
    lines.append(
        f"| **Practical join** (base + RSS + supplier-level paid spend — SCS band may rely on narrow category match) "
        f"| **{n_practical:,}** | **{pct(n_practical):.1f}%** |"
    )
    lines.append("| Base + RSS **without** category-matched spend | {:,} | {:.1f}% |".format(n_relaxed_rss_only, pct(n_relaxed_rss_only)))
    lines.append("| Base + category-matched spend **without** RSS join | {:,} | {:.1f}% |".format(n_relaxed_scs_only, pct(n_relaxed_scs_only)))
    lines.append("")

    if len(all_df):
        lines.append("## Estimated PS distribution (base-eligible rows only)")
        lines.append("")
        lines.append(
            f"- **PS with observed SCS only** — mean **{all_df['ps_observed_scs'].mean():.2f}**, "
            f"median **{all_df['ps_observed_scs'].median():.2f}**"
        )
        if impute_on:
            lines.append(
                f"- **PS with imputed SCS** — mean **{all_df['ps_imputed_scs'].mean():.2f}**, "
                f"median **{all_df['ps_imputed_scs'].median():.2f}**"
            )
        lines.append("")
        tc_o = all_df["tier_observed"].value_counts()
        lines.append("| Tier (observed SCS) | Count |")
        lines.append("| --- | ---: |")
        for tier in ["T1", "T2", "T3", "T4"]:
            lines.append(f"| {tier} | {int(tc_o.get(tier, 0)):,} |")
        lines.append("")
        if impute_on:
            tc_i = all_df["tier_imputed"].value_counts()
            lines.append("| Tier (imputed SCS) | Count |")
            lines.append("| --- | ---: |")
            for tier in ["T1", "T2", "T3", "T4"]:
                lines.append(f"| {tier} | {int(tc_i.get(tier, 0)):,} |")
            lines.append("")

        rss_df = all_df[all_df["rss_raw"].notna()]
        if len(rss_df):
            lines.append("### Base-eligible + metrics RSS (subset)")
            lines.append("")
            lines.append(
                f"- Rows: **{len(rss_df):,}** — PS observed mean **{rss_df['ps_observed_scs'].mean():.2f}**, "
                f"median **{rss_df['ps_observed_scs'].median():.2f}**"
            )
            if impute_on:
                lines.append(
                    f"- PS imputed mean **{rss_df['ps_imputed_scs'].mean():.2f}**, "
                    f"median **{rss_df['ps_imputed_scs'].median():.2f}**"
                )
            lines.append("")

    if len(strict_df):
        lines.append("## Strict-complete subset")
        lines.append("")
        lines.append(f"- Rows: **{len(strict_df):,}**")
        lines.append(f"- Mean PS (observed SCS): **{strict_df['ps_observed_scs'].mean():.2f}**")
        if impute_on:
            lines.append(f"- Mean PS (imputed SCS): **{strict_df['ps_imputed_scs'].mean():.2f}**")
        lines.append("")
        lines.append("### Sample (up to 15 rows)")
        lines.append("")
        lines.append("| Supplier (truncated) | PS obs | PS imp | EUS | FIS | RSS | SCS eff | SAS |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        sample = strict_df.sort_values("ps_imputed_scs" if impute_on else "ps_observed_scs", ascending=False).head(15)
        for _, r in sample.iterrows():
            su = str(r["supplier"])[:40]
            lines.append(
                f"| {su} | {r['ps_observed_scs']:.2f} | {r['ps_imputed_scs']:.2f} | {r['eus']:.2f} | {r['fis']:.2f} | "
                f"{r['rss']:.2f} | {r['scs_effective']:.2f} | {r['sas']:.2f} |"
            )
        lines.append("")
    else:
        lines.append("## Strict-complete subset")
        lines.append("")
        lines.append("*No rows met strict complete criteria with current joins.*")
        lines.append("")

    if len(practical_df):
        lines.append("## Practical join subset (RSS + any paid spend on supplier name)")
        lines.append("")
        lines.append(
            "These agreements have **metrics-backed RSS** and at least one paid spend row whose "
            "`SMD cleansed name` matches the contract supplier (after normalization). "
            "**PS_contract** in the tables above still uses **category-matched** share for SCS — "
            "often **0%** when booked category alignment is missing — so headline PS may **understate** "
            "concentration vs spend reality."
        )
        lines.append("")
        lines.append(f"- Rows: **{len(practical_df):,}**")
        lines.append(f"- Mean PS (observed SCS): **{practical_df['ps_observed_scs'].mean():.2f}**")
        if impute_on:
            lines.append(f"- Mean PS (imputed SCS): **{practical_df['ps_imputed_scs'].mean():.2f}**")
        lines.append("")
        lines.append("### Sample (up to 15 rows by PS imputed)")
        lines.append("")
        lines.append("| Supplier (truncated) | PS imp | RSS | SCS eff | Spend on name (USD) | Eff. share % |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        sample_p = practical_df.sort_values("ps_imputed_scs" if impute_on else "ps_observed_scs", ascending=False).head(15)
        for _, r in sample_p.iterrows():
            su = str(r["supplier"])[:36]
            lines.append(
                f"| {su} | {r['ps_imputed_scs']:.2f} | {r['rss']:.2f} | {r['scs_effective']:.2f} | "
                f"{r['supplier_total_spend_usd']:,.0f} | {r['supplier_share_effective_pct']:.2f} |"
            )
        lines.append("")

    lines.append("## Notes for stakeholders")
    lines.append("")
    lines.append(
        "- Rows that are **base eligible** but not **strict complete** still receive a full formula output here; "
        "RSS defaults to **3.0** raw when metrics do not match, and SCS may reflect **0% share** if spend does not link."
    )
    if impute_on:
        lines.append(
            "- **Imputed SCS** is for **presentation only** until spend keys align with contracts; "
            "do not treat `ps_imputed_scs` as production audit scores."
        )
    lines.append(
        "- Improving **strict complete** volume usually requires better **supplier identity** alignment between "
        "contracts and spend (or an agreement ID on spend lines)."
    )
    lines.append("")

    out_md = args.out_md
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_md.relative_to(ROOT)}")

    if args.sample_csv and len(all_df):
        if len(strict_df):
            export_df, label = strict_df, "strict_complete"
        elif len(practical_df):
            export_df, label = practical_df, "practical_join"
        else:
            has_rss = all_df["rss_raw"].notna()
            export_df = all_df[has_rss] if has_rss.any() else all_df
            label = "base_plus_rss" if has_rss.any() else "base_eligible"
        out_c = Path(args.sample_csv).resolve()
        out_c.parent.mkdir(parents=True, exist_ok=True)
        sort_key = "ps_imputed_scs" if impute_on else "ps_observed_scs"
        export_df.sort_values(sort_key, ascending=False).head(200).to_csv(out_c, index=False, encoding="utf-8")
        try:
            rel = out_c.relative_to(ROOT.resolve())
        except ValueError:
            rel = out_c
        print(f"Wrote {rel} ({min(200, len(export_df))} rows, {label})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
