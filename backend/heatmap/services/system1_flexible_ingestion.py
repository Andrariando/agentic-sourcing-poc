"""
Flexible System 1 ingestion layer for bulk upload and future ERP/API feeds.

Design:
- Canonical row contract remains owned by system1_upload_import canonicalizer.
- Adapters normalize source payloads (file-based or API JSON) into canonical rows.
- Mapping profiles provide source-specific header aliases without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

from backend.heatmap.services.system1_upload_import import (
    canonicalize_system1_row,
    extract_rows_from_structured_file,
)


MAPPING_PROFILES: Dict[str, Dict[str, str]] = {
    "default": {},
    "capstone_v2": {
        "opportunity type": "row_type",
        "booked category": "category",
        "booked subcategory": "subcategory",
        "smd cleansed name": "supplier_name",
        "master agreement reference number": "contract_id",
        "contract name": "request_title",
        "invoice amount (usd)": "estimated_spend_usd",
        "value in usd": "estimated_spend_usd",
        "bpra vendor status": "preferred_supplier_status",
    },
    "erp_generic": {
        "vendor_id": "supplier_name",
        "vendor_name": "supplier_name",
        "agreement_number": "contract_id",
        "contract_number": "contract_id",
        "request_name": "request_title",
        "project_name": "request_title",
        "amount_usd": "estimated_spend_usd",
        "spend_usd": "estimated_spend_usd",
        "expiry_date": "contract_end_date",
        "months_remaining": "months_to_expiry",
        "implementation_months": "implementation_timeline_months",
        "preferred_status": "preferred_supplier_status",
        "opportunity_type": "row_type",
    },
}


def _merged_mapping(
    profile: Optional[str],
    explicit_mapping: Optional[Dict[str, str]],
) -> Dict[str, str]:
    base = dict(MAPPING_PROFILES.get((profile or "default").strip().lower(), {}))
    for k, v in (explicit_mapping or {}).items():
        base[str(k).strip().lower()] = str(v).strip().lower()
    return base


@dataclass
class IngestionResult:
    rows_by_source: Dict[str, List[Dict[str, Any]]]
    notes: List[str]
    diagnostics: Dict[str, Any]


class IngestionAdapter(Protocol):
    def ingest(self) -> IngestionResult:
        ...


class StructuredFileAdapter:
    def __init__(
        self,
        files: Sequence[Tuple[str, bytes]],
        *,
        profile: Optional[str] = None,
        explicit_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        self.files = list(files)
        self.profile = profile or "default"
        self.explicit_mapping = explicit_mapping or {}

    def ingest(self) -> IngestionResult:
        mapping = _merged_mapping(self.profile, self.explicit_mapping)
        rows_by_source: Dict[str, List[Dict[str, Any]]] = {}
        notes: List[str] = []
        total_raw_rows = 0
        total_canonical_rows = 0
        type_counts = {"renewal": 0, "new_business": 0, "unknown": 0}

        for filename, content in self.files:
            rows, file_notes = extract_rows_from_structured_file(
                content,
                filename,
                column_mapping=mapping if mapping else None,
            )
            notes.extend(file_notes)
            total_raw_rows += len(rows)
            if not rows:
                notes.append(f"No parseable rows found in {filename}")
                continue
            canonical_rows: List[Dict[str, Any]] = []
            for r in rows:
                c = canonicalize_system1_row(r)
                rt = str(c.get("row_type") or "").strip().lower()
                if rt in {"renewal", "new_business"}:
                    type_counts[rt] += 1
                else:
                    type_counts["unknown"] += 1
                canonical_rows.append(c)
            total_canonical_rows += len(canonical_rows)
            rows_by_source[filename] = canonical_rows

        diagnostics = {
            "adapter": "structured_file",
            "profile": self.profile,
            "total_sources": len(self.files),
            "total_raw_rows": total_raw_rows,
            "total_canonical_rows": total_canonical_rows,
            "row_type_counts": type_counts,
        }
        notes.append(
            "Flexible ingestion diagnostics: "
            f"profile={self.profile}, canonical_rows={total_canonical_rows}, "
            f"row_types={type_counts}"
        )
        return IngestionResult(rows_by_source=rows_by_source, notes=notes, diagnostics=diagnostics)


class ErpJsonAdapter:
    def __init__(
        self,
        source_system: str,
        rows: Sequence[Dict[str, Any]],
        *,
        profile: Optional[str] = None,
        explicit_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        self.source_system = source_system or "erp"
        self.rows = list(rows)
        self.profile = profile or "erp_generic"
        self.explicit_mapping = explicit_mapping or {}

    def ingest(self) -> IngestionResult:
        mapping = _merged_mapping(self.profile, self.explicit_mapping)
        canonical_rows: List[Dict[str, Any]] = []
        type_counts = {"renewal": 0, "new_business": 0, "unknown": 0}
        for raw in self.rows:
            normalized = {str(k).strip().lower(): v for k, v in dict(raw).items()}
            remapped: Dict[str, Any] = {}
            for k, v in normalized.items():
                remapped[mapping.get(k, k)] = v
            c = canonicalize_system1_row(remapped)
            rt = str(c.get("row_type") or "").strip().lower()
            if rt in {"renewal", "new_business"}:
                type_counts[rt] += 1
            else:
                type_counts["unknown"] += 1
            canonical_rows.append(c)

        source_name = f"erp:{self.source_system}"
        notes = [
            f"ERP adapter ingested {len(canonical_rows)} rows from source_system={self.source_system}.",
            f"Flexible ingestion diagnostics: profile={self.profile}, row_types={type_counts}",
        ]
        diagnostics = {
            "adapter": "erp_json",
            "profile": self.profile,
            "source_system": self.source_system,
            "total_canonical_rows": len(canonical_rows),
            "row_type_counts": type_counts,
        }
        return IngestionResult(
            rows_by_source={source_name: canonical_rows},
            notes=notes,
            diagnostics=diagnostics,
        )

