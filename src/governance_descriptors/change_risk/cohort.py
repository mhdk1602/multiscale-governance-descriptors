"""Freeze a consecutive, outcome-blind candidate cohort before annotation."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping


REQUIRED_CANDIDATE_FIELDS = {
    "project",
    "change_id",
    "change_url",
    "merged_at",
    "before_ref",
    "after_ref",
    "sequence_index",
    "eligibility_status",
}
PROHIBITED_OUTCOME_FIELDS = {
    "outcome_primary",
    "adverse_event_type",
    "candidate_repair_url",
    "candidate_repair_signal",
    "annotation_notes",
    "annotator_1",
    "annotator_2",
    "adjudicator",
}
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def freeze_candidate_cohort(
    records: Iterable[Mapping[str, Any]],
    *,
    protocol_version: str,
    feature_spec_version: str,
) -> dict[str, Any]:
    """Validate and hash a complete pre-outcome candidate ledger.

    The ledger includes both eligible and pre-outcome excluded changes so a
    project sequence cannot be silently thinned after labels are inspected.
    """

    normalized = []
    seen = set()
    for raw in records:
        record = dict(raw)
        missing = REQUIRED_CANDIDATE_FIELDS - set(record)
        if missing:
            raise ValueError(f"Candidate is missing {sorted(missing)}")
        prohibited = PROHIBITED_OUTCOME_FIELDS & set(record)
        if prohibited:
            raise ValueError(
                "Outcome information is prohibited before cohort freeze: "
                f"{sorted(prohibited)}"
            )
        key = (str(record["project"]), str(record["change_id"]))
        if key in seen:
            raise ValueError(f"Duplicate candidate {key[0]}:{key[1]}")
        seen.add(key)
        for ref_name in ("before_ref", "after_ref"):
            ref = str(record[ref_name]).lower()
            if not COMMIT_SHA.fullmatch(ref):
                raise ValueError(f"{key[0]}:{key[1]} has a non-immutable {ref_name}")
            record[ref_name] = ref
        try:
            merged_at = datetime.fromisoformat(str(record["merged_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{key[0]}:{key[1]} has invalid merged_at") from exc
        if merged_at.tzinfo is None:
            raise ValueError(f"{key[0]}:{key[1]} merged_at must include a timezone")
        record["merged_at"] = merged_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        try:
            record["sequence_index"] = int(record["sequence_index"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key[0]}:{key[1]} has invalid sequence_index") from exc
        if record["sequence_index"] < 1:
            raise ValueError(f"{key[0]}:{key[1]} sequence_index must be positive")
        status = str(record["eligibility_status"])
        if status not in {"include", "exclude"}:
            raise ValueError(f"{key[0]}:{key[1]} has invalid eligibility_status")
        reason = record.get("exclusion_reason")
        if status == "exclude" and not reason:
            raise ValueError(f"{key[0]}:{key[1]} exclusion requires a reason")
        if status == "include" and reason:
            raise ValueError(f"{key[0]}:{key[1]} included candidate has an exclusion reason")
        normalized.append(record)

    normalized.sort(
        key=lambda row: (
            str(row["project"]),
            int(row["sequence_index"]),
            str(row["change_id"]),
        )
    )
    by_project: dict[str, list[int]] = {}
    for record in normalized:
        by_project.setdefault(str(record["project"]), []).append(record["sequence_index"])
    for project, indices in by_project.items():
        expected = list(range(1, len(indices) + 1))
        if indices != expected:
            raise ValueError(
                f"{project} sequence indices must be contiguous from 1; "
                f"observed {indices}"
            )

    frozen_content = {
        "protocol_version": str(protocol_version),
        "feature_spec_version": str(feature_spec_version),
        "selection": "consecutive_pre_outcome",
        "records": normalized,
    }
    cohort_id = sha256(_canonical_json(frozen_content).encode("utf-8")).hexdigest()
    included = [row for row in normalized if row["eligibility_status"] == "include"]
    return {
        **frozen_content,
        "cohort_id": cohort_id,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "n_projects": len(by_project),
            "n_candidates": len(normalized),
            "n_included": len(included),
            "n_excluded_pre_outcome": len(normalized) - len(included),
        },
    }
