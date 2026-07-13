"""Outcome-label contracts for the change-risk study.

Automated heuristics may nominate changes for review, but they do not create the
primary outcome. Only a descriptor-blind, adjudicated label can enter the
confirmatory evaluation.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


LABEL_STATUSES = {"unreviewed", "single_review", "double_review", "adjudicated"}
PRIMARY_OUTCOMES = {0, 1}

_REPAIR_TERMS = re.compile(
    r"\b(revert(?:ed|s)?|rollback|hotfix|regression|fix(?:ed|es)?|restore(?:d)?|"
    r"break(?:ing|age)?|incident)\b",
    re.IGNORECASE,
)


def candidate_repair_signal(commit_messages: Sequence[str]) -> bool:
    """High-recall nomination signal; never a final adverse-event label."""

    return any(_REPAIR_TERMS.search(message or "") for message in commit_messages)


def validate_annotation(record: Mapping[str, Any], *, require_adjudicated: bool = False) -> None:
    status = str(record.get("label_status") or "unreviewed")
    if status not in LABEL_STATUSES:
        raise ValueError(f"Unknown label_status={status!r}")
    outcome = record.get("outcome_primary")
    if outcome is not None and outcome not in PRIMARY_OUTCOMES:
        raise ValueError("outcome_primary must be 0, 1, or null")
    if status == "adjudicated" and outcome not in PRIMARY_OUTCOMES:
        raise ValueError("An adjudicated record requires outcome_primary in {0, 1}")
    if require_adjudicated and status != "adjudicated":
        raise ValueError(
            f"Confirmatory evaluation refuses non-adjudicated label for "
            f"{record.get('project')}:{record.get('change_id')}"
        )


def validate_annotation_table(records: Sequence[Mapping[str, Any]], *, require_adjudicated=False):
    seen: set[tuple[str, str]] = set()
    for record in records:
        validate_annotation(record, require_adjudicated=require_adjudicated)
        key = (str(record.get("project")), str(record.get("change_id")))
        if key in seen:
            raise ValueError(f"Duplicate change record: {key[0]}:{key[1]}")
        seen.add(key)
