"""
Single source of truth for demo IT suppliers: seeded into ``supplier_performance``
and used as a fallback when building per-category supplier pools (e.g. DTP-02).

Cases do **not** embed their own supplier universe — they use ``category_id`` to slice this catalog.
"""
from __future__ import annotations

from typing import List, TypedDict


class SupplierMasterRecord(TypedDict):
    supplier_id: str
    supplier_name: str
    category_id: str
    baseline_score: float
    trend: str  # improving | stable | declining


# fmt: off
SUPPLIER_MASTER_CATALOG: List[SupplierMasterRecord] = [
    # IT services
    {"supplier_id": "SUP-IT-01", "supplier_name": "TechCorp Solutions", "category_id": "IT_SERVICES", "baseline_score": 7.8, "trend": "stable"},
    {"supplier_id": "SUP-IT-02", "supplier_name": "Global Systems Inc", "category_id": "IT_SERVICES", "baseline_score": 6.5, "trend": "declining"},
    {"supplier_id": "SUP-IT-03", "supplier_name": "Accenture", "category_id": "IT_SERVICES", "baseline_score": 8.2, "trend": "stable"},
    {"supplier_id": "SUP-IT-04", "supplier_name": "Infosys", "category_id": "IT_SERVICES", "baseline_score": 7.9, "trend": "improving"},
    # Hardware
    {"supplier_id": "SUP-HW-01", "supplier_name": "Dell Technologies", "category_id": "HARDWARE", "baseline_score": 8.5, "trend": "stable"},
    {"supplier_id": "SUP-HW-02", "supplier_name": "HP Inc", "category_id": "HARDWARE", "baseline_score": 8.0, "trend": "improving"},
    {"supplier_id": "SUP-HW-03", "supplier_name": "Lenovo", "category_id": "HARDWARE", "baseline_score": 7.5, "trend": "stable"},
    # Cloud (hyperscalers + migration-relevant names align with CASE-002 RFx narrative)
    {"supplier_id": "SUP-CL-01", "supplier_name": "AWS", "category_id": "CLOUD", "baseline_score": 9.0, "trend": "stable"},
    {"supplier_id": "SUP-CL-02", "supplier_name": "Microsoft Azure", "category_id": "CLOUD", "baseline_score": 8.8, "trend": "improving"},
    {"supplier_id": "SUP-CL-03", "supplier_name": "Google Cloud Platform", "category_id": "CLOUD", "baseline_score": 8.3, "trend": "improving"},
    # Security
    {"supplier_id": "SUP-SEC-01", "supplier_name": "SecureNet Defense", "category_id": "SECURITY", "baseline_score": 9.2, "trend": "stable"},
    {"supplier_id": "SUP-SEC-02", "supplier_name": "CyberGuard AI", "category_id": "SECURITY", "baseline_score": 7.5, "trend": "improving"},
    {"supplier_id": "SUP-SEC-03", "supplier_name": "Global InfoSec", "category_id": "SECURITY", "baseline_score": 8.1, "trend": "stable"},
    # Infrastructure / colo
    {"supplier_id": "SUP-DC-01", "supplier_name": "Equinix", "category_id": "INFRASTRUCTURE", "baseline_score": 8.9, "trend": "stable"},
    {"supplier_id": "SUP-DC-02", "supplier_name": "Digital Realty", "category_id": "INFRASTRUCTURE", "baseline_score": 8.5, "trend": "stable"},
    # Telecom
    {"supplier_id": "SUP-TEL-01", "supplier_name": "AT&T Business", "category_id": "TELECOM", "baseline_score": 7.2, "trend": "declining"},
    {"supplier_id": "SUP-TEL-02", "supplier_name": "Verizon Business", "category_id": "TELECOM", "baseline_score": 7.5, "trend": "stable"},
    {"supplier_id": "SUP-TEL-03", "supplier_name": "BT Global", "category_id": "TELECOM", "baseline_score": 7.0, "trend": "stable"},
    # Software
    {"supplier_id": "SUP-SW-01", "supplier_name": "Microsoft", "category_id": "SOFTWARE", "baseline_score": 8.5, "trend": "stable"},
    {"supplier_id": "SUP-SW-02", "supplier_name": "GitLab", "category_id": "SOFTWARE", "baseline_score": 8.2, "trend": "improving"},
    {"supplier_id": "SUP-SW-03", "supplier_name": "GitHub", "category_id": "SOFTWARE", "baseline_score": 9.1, "trend": "stable"},
    {"supplier_id": "SUP-SW-04", "supplier_name": "Jenkins (CloudBees)", "category_id": "SOFTWARE", "baseline_score": 7.5, "trend": "declining"},
    # Network / SD-WAN
    {"supplier_id": "SUP-NET-01", "supplier_name": "Cisco Viptela", "category_id": "NETWORK", "baseline_score": 8.7, "trend": "stable"},
    {"supplier_id": "SUP-NET-02", "supplier_name": "VMware VeloCloud", "category_id": "NETWORK", "baseline_score": 8.3, "trend": "improving"},
    {"supplier_id": "SUP-NET-03", "supplier_name": "Palo Alto Prisma", "category_id": "NETWORK", "baseline_score": 8.5, "trend": "stable"},
    # SaaS / HRIS (IDs align with CASE-003 evaluation seed)
    {"supplier_id": "SUP-SAAS-01", "supplier_name": "Workday", "category_id": "SAAS", "baseline_score": 9.0, "trend": "stable"},
    {"supplier_id": "SUP-SAAS-02", "supplier_name": "Oracle HCM Cloud", "category_id": "SAAS", "baseline_score": 8.2, "trend": "stable"},
    {"supplier_id": "SUP-SAAS-03", "supplier_name": "SAP SuccessFactors", "category_id": "SAAS", "baseline_score": 7.8, "trend": "declining"},
]
# fmt: on


def master_records_for_category(category_id: str) -> List[SupplierMasterRecord]:
    return [r for r in SUPPLIER_MASTER_CATALOG if r["category_id"] == category_id]


def supplier_master_catalog_count() -> int:
    return len(SUPPLIER_MASTER_CATALOG)


def compact_catalog_for_llm() -> str:
    """
    All demo suppliers in one block for LLM prompts (tab-separated: id, name, category, baseline score, trend).
    Use together with the case's ``category_id``, summary, and key findings to judge procurement fit.
    """
    lines: List[str] = []
    for r in SUPPLIER_MASTER_CATALOG:
        lines.append(
            f"{r['supplier_id']}\t{r['supplier_name']}\t{r['category_id']}\t{r['baseline_score']}\t{r['trend']}"
        )
    header = "supplier_id\tsupplier_name\tcategory_id\tbaseline_demo_score\ttrend"
    return header + "\n" + "\n".join(lines)
