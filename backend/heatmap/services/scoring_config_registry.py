from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.heatmap.persistence.heatmap_models import ScoringConfigVersion
from backend.heatmap.services.learned_weights import DEFAULT_WEIGHTS_FLAT


class ScoringParameterConfig(BaseModel):
    key: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=120)
    applies_to: List[Literal["renewal", "new_business"]] = Field(min_length=1)
    input_fields: List[str] = Field(default_factory=list)
    rule_type: Literal["direct_numeric", "banded_score", "lookup_map", "normalized", "formula"]
    rule_config: Dict[str, Any] = Field(default_factory=dict)
    default_policy: Dict[str, Any] = Field(default_factory=dict)
    weight_key: str = Field(min_length=2, max_length=64)
    prompt_template: Optional[str] = None
    explanation_template: Optional[str] = None


class ScoringConfigDoc(BaseModel):
    name: str = Field(default="default_scoring_config", min_length=3, max_length=120)
    parameters: List[ScoringParameterConfig] = Field(default_factory=list)
    formulas: Dict[str, Any] = Field(default_factory=dict)


def _default_config_doc() -> Dict[str, Any]:
    return {
        "name": "default_scoring_config",
        "parameters": [
            {
                "key": "eus_score",
                "label": "Expiry Urgency Score",
                "applies_to": ["renewal"],
                "input_fields": ["months_to_expiry", "contract_end_date"],
                "rule_type": "banded_score",
                "rule_config": {"source": "months_to_expiry", "bands": [[3, 10], [6, 9], [12, 8], [18, 5], [9999, 2]]},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_eus",
                "explanation_template": "Derived from months to expiry.",
            },
            {
                "key": "fis_score",
                "label": "Financial Impact Score",
                "applies_to": ["renewal"],
                "input_fields": ["estimated_spend_usd"],
                "rule_type": "normalized",
                "rule_config": {"source": "estimated_spend_usd", "normalizer": "batch_max_renewal_spend"},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_fis",
            },
            {
                "key": "rss_score",
                "label": "Supplier Risk Score",
                "applies_to": ["renewal"],
                "input_fields": ["rss_score", "preferred_supplier_status"],
                "rule_type": "lookup_map",
                "rule_config": {"source": "preferred_supplier_status"},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_rss",
            },
            {
                "key": "scs_score",
                "label": "Spend Concentration Score",
                "applies_to": ["renewal"],
                "input_fields": ["estimated_spend_usd"],
                "rule_type": "normalized",
                "rule_config": {"source": "estimated_spend_usd", "normalizer": "batch_max_renewal_spend"},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_scs",
            },
            {
                "key": "sas_score",
                "label": "Strategic Alignment Score (Renewal)",
                "applies_to": ["renewal"],
                "input_fields": ["category", "supplier_name", "preferred_supplier_status"],
                "rule_type": "lookup_map",
                "rule_config": {"source": "category_cards"},
                "default_policy": {"strategy": "category_default"},
                "weight_key": "w_sas_contract",
                "prompt_template": "Extract policy alignment rationale for renewal.",
            },
            {
                "key": "ius_score",
                "label": "Implementation Urgency Score",
                "applies_to": ["new_business"],
                "input_fields": ["implementation_timeline_months"],
                "rule_type": "banded_score",
                "rule_config": {"source": "implementation_timeline_months", "bands": [[3, 10], [6, 8], [12, 6], [9999, 3]]},
                "default_policy": {"strategy": "constant", "value": 6.0},
                "weight_key": "w_ius",
            },
            {
                "key": "es_score",
                "label": "Estimated Spend Score",
                "applies_to": ["new_business"],
                "input_fields": ["estimated_spend_usd"],
                "rule_type": "normalized",
                "rule_config": {"source": "estimated_spend_usd", "normalizer": "batch_max_new_spend"},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_es",
            },
            {
                "key": "csis_score",
                "label": "Category Spend Impact Score",
                "applies_to": ["new_business"],
                "input_fields": ["estimated_spend_usd"],
                "rule_type": "formula",
                "rule_config": {"formula": "0.7*es+1.5"},
                "default_policy": {"strategy": "constant", "value": 5.0},
                "weight_key": "w_csis",
            },
            {
                "key": "sas_score_new",
                "label": "Strategic Alignment Score (New)",
                "applies_to": ["new_business"],
                "input_fields": ["category", "supplier_name", "preferred_supplier_status"],
                "rule_type": "lookup_map",
                "rule_config": {"source": "category_cards"},
                "default_policy": {"strategy": "category_default"},
                "weight_key": "w_sas_new",
                "prompt_template": "Extract policy alignment rationale for new sourcing request.",
            },
        ],
        "formulas": {
            "renewal": {
                "weight_keys": ["w_eus", "w_fis", "w_rss", "w_scs", "w_sas_contract"],
                "weight_values": {
                    "w_eus": 0.30,
                    "w_fis": 0.25,
                    "w_rss": 0.20,
                    "w_scs": 0.15,
                    "w_sas_contract": 0.10,
                },
            },
            "new_business": {
                "weight_keys": ["w_ius", "w_es", "w_csis", "w_sas_new"],
                "weight_values": {
                    "w_ius": 0.30,
                    "w_es": 0.30,
                    "w_csis": 0.25,
                    "w_sas_new": 0.15,
                },
            },
        },
    }


def validate_scoring_config(doc: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        parsed = ScoringConfigDoc.model_validate(doc)
    except Exception as e:
        return False, [f"Schema validation failed: {e}"]

    seen: set[str] = set()
    valid_weight_keys = set(DEFAULT_WEIGHTS_FLAT.keys())
    for p in parsed.parameters:
        if p.key in seen:
            errors.append(f"Duplicate parameter key: {p.key}")
        seen.add(p.key)
        if p.weight_key not in valid_weight_keys:
            errors.append(f"Unknown weight key '{p.weight_key}' for parameter '{p.key}'")
        if not p.default_policy:
            errors.append(f"default_policy is required for parameter '{p.key}'")
        if p.prompt_template and len(p.prompt_template.strip()) < 12:
            errors.append(f"prompt_template is too short for parameter '{p.key}'")
        if p.rule_type == "banded_score" and not isinstance(p.rule_config.get("bands"), list):
            errors.append(f"banded_score requires rule_config.bands for parameter '{p.key}'")

    formulas = parsed.formulas or {}
    for group in ("renewal", "new_business"):
        group_cfg = formulas.get(group) or {}
        weight_keys = (group_cfg.get("weight_keys") or [])
        if not weight_keys:
            errors.append(f"formulas.{group}.weight_keys is required")
            continue
        for k in weight_keys:
            if k not in valid_weight_keys:
                errors.append(f"Unknown weight key '{k}' in formulas.{group}.weight_keys")
        weight_values = group_cfg.get("weight_values") or {}
        if weight_values:
            if not isinstance(weight_values, dict):
                errors.append(f"formulas.{group}.weight_values must be an object")
            else:
                for wk, wv in weight_values.items():
                    if wk not in weight_keys:
                        errors.append(f"formulas.{group}.weight_values contains key '{wk}' not present in weight_keys")
                        continue
                    try:
                        float(wv)
                    except (TypeError, ValueError):
                        errors.append(f"formulas.{group}.weight_values.{wk} must be numeric")

    return (len(errors) == 0), errors


def ensure_default_scoring_config(session: Session) -> ScoringConfigVersion:
    active = session.exec(
        select(ScoringConfigVersion).where(ScoringConfigVersion.status == "active")
    ).first()
    if active:
        return active
    now = datetime.now(timezone.utc)
    row = ScoringConfigVersion(
        version=1,
        status="active",
        title="Default scoring config",
        config_json=json.dumps(_default_config_doc()),
        created_by="system",
        created_at=now,
        updated_at=now,
        published_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def parse_config_json(raw: str) -> Dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise ValueError("Config payload must be a JSON object.")
    return payload


def extract_weight_overrides(doc: Dict[str, Any]) -> Dict[str, float]:
    formulas = (doc or {}).get("formulas") or {}
    out: Dict[str, float] = {}
    for group in ("renewal", "new_business"):
        group_cfg = formulas.get(group) or {}
        keys = list(group_cfg.get("weight_keys") or [])
        vals = group_cfg.get("weight_values") or {}
        if not isinstance(vals, dict):
            continue
        for k in keys:
            if k not in vals:
                continue
            try:
                out[k] = float(vals[k])
            except (TypeError, ValueError):
                continue
    return out
