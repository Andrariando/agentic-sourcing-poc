"""
Category-scoped supplier pools for UI and copilot (DTP-02).

Uses latest ``supplier_performance`` row per supplier for the case's ``category_id``.
Falls back to ``shared.supplier_master_catalog`` when the DB has no rows (fresh env).
"""
from __future__ import annotations

from typing import List

from sqlmodel import select

from backend.persistence.database import get_db_session
from backend.persistence.models import SupplierPerformance
from shared.schemas import CategorySupplierPoolRow
from shared.supplier_master_catalog import master_records_for_category


def _dtp02_fit_for_rank(index: int) -> str:
    """Deterministic demo tiers: mimic prioritization an agent would surface for RFx targeting."""
    if index < 2:
        return "primary"
    if index < 4:
        return "secondary"
    return "included"


def _pool_rows_from_performance(records: List[SupplierPerformance]) -> List[CategorySupplierPoolRow]:
    ordered = sorted(
        records,
        key=lambda r: (-(r.overall_score or 0.0), r.supplier_id or ""),
    )
    rows: List[CategorySupplierPoolRow] = []
    for i, r in enumerate(ordered):
        cid = r.category_id or ""
        rows.append(
            CategorySupplierPoolRow(
                supplier_id=r.supplier_id,
                supplier_name=r.supplier_name,
                category_id=cid,
                overall_score=float(r.overall_score or 0.0),
                risk_level=r.risk_level,
                dtp02_fit=_dtp02_fit_for_rank(i),
            )
        )
    return rows


def _pool_rows_from_master_catalog(category_id: str) -> List[CategorySupplierPoolRow]:
    master = master_records_for_category(category_id)
    ordered = sorted(master, key=lambda r: (-r["baseline_score"], r["supplier_id"]))
    rows: List[CategorySupplierPoolRow] = []
    for i, r in enumerate(ordered):
        sc = r["baseline_score"]
        rows.append(
            CategorySupplierPoolRow(
                supplier_id=r["supplier_id"],
                supplier_name=r["supplier_name"],
                category_id=category_id,
                overall_score=float(sc),
                risk_level="low" if sc >= 7.0 else "medium",
                dtp02_fit=_dtp02_fit_for_rank(i),
            )
        )
    return rows


def get_category_supplier_pool(category_id: str) -> List[CategorySupplierPoolRow]:
    """All suppliers in the IT catalog for this category, with demo DTP-02 fit tiers."""
    if not category_id:
        return []

    session = get_db_session()
    try:
        raw = session.exec(
            select(SupplierPerformance)
            .where(SupplierPerformance.category_id == category_id)
            .order_by(SupplierPerformance.supplier_id, SupplierPerformance.measurement_date.desc())
        ).all()
    finally:
        session.close()

    latest_by_id: dict[str, SupplierPerformance] = {}
    for row in raw:
        sid = row.supplier_id
        if sid and sid not in latest_by_id:
            latest_by_id[sid] = row

    if not latest_by_id:
        return _pool_rows_from_master_catalog(category_id)

    return _pool_rows_from_performance(list(latest_by_id.values()))
