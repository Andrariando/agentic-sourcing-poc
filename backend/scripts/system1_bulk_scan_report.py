"""
Generate a System 1 bulk-scan report from sponsor files.

Outputs:
- candidate count by file
- readiness breakdown
- score distribution
- top opportunities by score
"""
from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from backend.heatmap.services.system1_upload_import import extract_rows_from_structured_file
from backend.heatmap.services.system1_scoring_orchestrator import enrich_rows_for_preview
from backend.main import _build_preview_row


ALLOWED_EXT = {".csv", ".xls", ".xlsx"}


def _scan_file(path: Path) -> List[Dict[str, Any]]:
    content = path.read_bytes()
    raw_rows, _notes = extract_rows_from_structured_file(content, path.name)
    rows = []
    for idx, raw in enumerate(raw_rows, start=1):
        rows.append(_build_preview_row(raw, path.name, "structured", idx).model_dump())
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing sponsor files (xlsx/csv).",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of top opportunities to print.",
    )
    args = ap.parse_args()

    root = Path(args.input_dir)
    if not root.exists():
        print(f"[ERROR] Input directory not found: {root}")
        return 2

    files = [p for p in sorted(root.iterdir()) if p.is_file() and p.suffix.lower() in ALLOWED_EXT]
    if not files:
        print(f"[ERROR] No structured files found in: {root}")
        return 2

    by_file_count: Dict[str, int] = {}
    candidates: List[Dict[str, Any]] = []
    for f in files:
        rows = _scan_file(f)
        by_file_count[f.name] = len(rows)
        candidates.extend(rows)

    if not candidates:
        print("[INFO] No candidate rows extracted.")
        return 0

    scored = enrich_rows_for_preview(candidates)
    readiness = Counter(r.get("readiness_status") or "unknown" for r in scored)
    tiers = Counter(r.get("computed_tier") or "NA" for r in scored)
    valid = sum(1 for r in scored if bool(r.get("valid_for_approval")) and r.get("readiness_status") != "needs_review")

    print("=== FILE CANDIDATE COUNTS ===")
    for name, cnt in by_file_count.items():
        print(f"- {name}: {cnt}")

    print("\n=== SYSTEM 1 PREVIEW SUMMARY ===")
    print(f"total_candidates: {len(scored)}")
    print(f"valid_candidates: {valid}")
    print(f"readiness: {dict(readiness)}")
    print(f"tier_distribution: {dict(tiers)}")

    # Top scores
    scored_sorted = sorted(scored, key=lambda r: float(r.get("computed_total_score") or 0.0), reverse=True)
    print(f"\n=== TOP {args.top} BY SCORE ===")
    for r in scored_sorted[: args.top]:
        ident = r.get("contract_id") or r.get("request_title") or r.get("row_id")
        print(
            f"- score={float(r.get('computed_total_score') or 0.0):.2f} "
            f"tier={r.get('computed_tier')} supplier={r.get('supplier_name')} "
            f"category={r.get('category')} id={ident}"
        )

    # Optional rough dedupe view (contract_id preferred)
    grouped: Dict[str, Dict[str, Any]] = {}
    for r in scored:
        key = (
            str(r.get("contract_id") or "").strip().lower()
            or f"{str(r.get('supplier_name') or '').strip().lower()}|{str(r.get('subcategory') or '').strip().lower()}|{r.get('row_type')}"
        )
        prev = grouped.get(key)
        if prev is None or float(r.get("computed_total_score") or 0.0) > float(prev.get("computed_total_score") or 0.0):
            grouped[key] = r
    print(f"\n=== DEDUPED VIEW (MAX SCORE PER KEY) ===\nkeys={len(grouped)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

