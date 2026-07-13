"""Dataset assembly with immutable change and extraction provenance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from .features import extract_change_features
from .labels import validate_annotation_table
from .manifest import load_manifest


FEATURE_SPEC_VERSION = "governance-change-risk-v1"
BASELINE_REGISTRY_COVARIATES = (
    "lines_added",
    "lines_deleted",
    "files_changed",
    "author_prior_merged_changes",
    "prior_30d_failed_workflows",
)
REQUIRED_PAIR_FIELDS = {
    "project",
    "change_id",
    "merged_at",
    "before_manifest",
    "after_manifest",
}


def load_pair_records(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL manifest-pair registry."""

    source = Path(path)
    records = []
    for line_number, line in enumerate(source.read_text().splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on {source}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object on {source}:{line_number}")
        records.append(record)
    return records


def _resolve(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def _baseline_covariates(record: Mapping[str, Any]) -> dict[str, float]:
    raw = record.get("baseline_covariates") or {}
    if not isinstance(raw, Mapping):
        raise ValueError("baseline_covariates must be an object")
    unknown = set(raw) - set(BASELINE_REGISTRY_COVARIATES)
    if unknown:
        raise ValueError(f"Unknown baseline covariates: {sorted(unknown)}")
    values = {}
    for name, value in raw.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"baseline_covariates.{name} must be numeric") from exc
        if numeric < 0:
            raise ValueError(f"baseline_covariates.{name} must be nonnegative")
        values[name] = numeric
    if record.get("label_status") == "adjudicated":
        missing = set(BASELINE_REGISTRY_COVARIATES) - set(values)
        if missing:
            raise ValueError(
                "Adjudicated records require every locked baseline covariate; "
                f"missing {sorted(missing)}"
            )
    return values


def build_study_dataset(
    records: Iterable[Mapping[str, Any]],
    *,
    base_dir: str | Path = ".",
) -> pd.DataFrame:
    """Build one feature row per exact before/after manifest pair."""

    rows = [dict(record) for record in records]
    validate_annotation_table(rows)
    root = Path(base_dir)
    output = []

    for record in rows:
        missing = REQUIRED_PAIR_FIELDS - set(record)
        if missing:
            raise ValueError(
                f"{record.get('project', '?')}:{record.get('change_id', '?')} "
                f"is missing {sorted(missing)}"
            )
        before_path = _resolve(root, record["before_manifest"])
        after_path = _resolve(root, record["after_manifest"])
        before = load_manifest(before_path)
        after = load_manifest(after_path)
        for side, snapshot in (("before", before), ("after", after)):
            expected = record.get(f"{side}_manifest_sha256")
            if expected and expected != snapshot.sha256:
                raise ValueError(
                    f"{record['project']}:{record['change_id']} {side} manifest hash "
                    f"mismatch: expected {expected}, observed {snapshot.sha256}"
                )
        features = extract_change_features(before, after)
        registry_covariates = _baseline_covariates(record)
        for name in BASELINE_REGISTRY_COVARIATES:
            features[f"baseline__repo__{name}"] = registry_covariates.get(name, float("nan"))
        manifest_visible_change = bool(
            features["baseline__nodes_added"]
            or features["baseline__nodes_removed"]
            or features["baseline__nodes_modified"]
            or features["baseline__edges_added"]
            or features["baseline__edges_removed"]
        )

        metadata = {
            "feature_spec_version": FEATURE_SPEC_VERSION,
            "project": str(record["project"]),
            "change_id": str(record["change_id"]),
            "change_url": record.get("change_url"),
            "merged_at": str(record["merged_at"]),
            "before_ref": record.get("before_ref"),
            "after_ref": record.get("after_ref"),
            "before_manifest": str(record["before_manifest"]),
            "after_manifest": str(record["after_manifest"]),
            "before_manifest_sha256": before.sha256,
            "after_manifest_sha256": after.sha256,
            "before_dbt_version": before.metadata.get("dbt_version"),
            "after_dbt_version": after.metadata.get("dbt_version"),
            "manifest_visible_change": manifest_visible_change,
            "label_status": str(record.get("label_status") or "unreviewed"),
            "outcome_primary": record.get("outcome_primary"),
            "outcome_window_days": record.get("outcome_window_days"),
            "adverse_event_type": record.get("adverse_event_type"),
            "annotation_notes": record.get("annotation_notes"),
            "annotator_1": record.get("annotator_1"),
            "annotator_2": record.get("annotator_2"),
            "adjudicator": record.get("adjudicator"),
        }
        output.append({**metadata, **features})

    frame = pd.DataFrame(output)
    if not frame.empty:
        resource_delta_columns = [
            column
            for column in frame.columns
            if column.startswith("baseline__resource_delta__")
        ]
        frame[resource_delta_columns] = frame[resource_delta_columns].fillna(0)
        frame["merged_at"] = pd.to_datetime(frame["merged_at"], utc=True, errors="raise")
        frame = frame.sort_values(["project", "merged_at", "change_id"]).reset_index(drop=True)
    return frame
