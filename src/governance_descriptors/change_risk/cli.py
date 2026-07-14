"""Command-line interface for the governance-change-risk study."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from .collection import collect_manifest_pair
from .cohort import freeze_candidate_cohort
from .evaluation import evaluate_study
from .study import (
    BASELINE_REGISTRY_COVARIATES,
    FEATURE_SPEC_VERSION,
    build_study_dataset,
    load_pair_records,
)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _build(args) -> int:
    registry = Path(args.registry).resolve()
    records = load_pair_records(registry)
    frame = build_study_dataset(records, base_dir=registry.parent)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    digest = sha256(output.read_bytes()).hexdigest()
    _write_json(
        output.with_suffix(output.suffix + ".audit.json"),
        {
            "feature_spec_version": FEATURE_SPEC_VERSION,
            "registry": str(registry),
            "dataset": str(output.resolve()),
            "dataset_sha256": digest,
            "n_changes": len(frame),
            "n_projects": int(frame["project"].nunique()) if len(frame) else 0,
            "n_adjudicated": int(frame["label_status"].eq("adjudicated").sum()) if len(frame) else 0,
            "n_events": int(frame["outcome_primary"].fillna(0).sum()) if len(frame) else 0,
        },
    )
    return 0


def _evaluate(args) -> int:
    frame = pd.read_csv(args.dataset)
    report = evaluate_study(
        frame,
        n_bootstrap=args.bootstrap,
        seed=args.seed,
        review_budget=args.review_budget,
    )
    _write_json(Path(args.output), report)
    return 0


def _collect(args) -> int:
    baseline_covariates = {}
    for item in args.baseline_covariate:
        name, separator, raw_value = item.partition("=")
        if not separator or name not in BASELINE_REGISTRY_COVARIATES:
            allowed = ", ".join(BASELINE_REGISTRY_COVARIATES)
            raise ValueError(f"Baseline covariate must be one of {allowed}, formatted name=value")
        baseline_covariates[name] = float(raw_value)
    record = collect_manifest_pair(
        repo=args.repo,
        project=args.project,
        change_id=args.change_id,
        change_url=args.change_url,
        merged_at=args.merged_at,
        before_ref=args.before_ref,
        after_ref=args.after_ref,
        output_dir=args.output_dir,
        project_subdir=args.project_subdir,
        commands=args.command or ["dbt parse --no-partial-parse"],
        manifest_relative_path=args.manifest_path,
        outcome_window_days=args.outcome_window_days,
        baseline_covariates=baseline_covariates,
    )
    print(json.dumps(record, indent=2))
    return 0


def _freeze_cohort(args) -> int:
    records = load_pair_records(args.candidates)
    frozen = freeze_candidate_cohort(
        records,
        protocol_version=args.protocol_version,
        feature_spec_version=FEATURE_SPEC_VERSION,
    )
    _write_json(Path(args.output), frozen)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="governance-change-risk")
    commands = parser.add_subparsers(dest="subcommand", required=True)

    collect = commands.add_parser("collect", help="Generate an exact manifest pair from git refs")
    collect.add_argument("--repo", required=True)
    collect.add_argument("--project", required=True)
    collect.add_argument("--change-id", required=True)
    collect.add_argument("--change-url")
    collect.add_argument("--merged-at", required=True)
    collect.add_argument("--before-ref", required=True)
    collect.add_argument("--after-ref", required=True)
    collect.add_argument("--project-subdir", default=".")
    collect.add_argument("--manifest-path", default="target/manifest.json")
    collect.add_argument("--command", action="append")
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--outcome-window-days", type=int, default=30)
    collect.add_argument(
        "--baseline-covariate",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Locked pre-outcome repository covariate; repeat for each value",
    )
    collect.set_defaults(handler=_collect)

    freeze = commands.add_parser(
        "freeze-cohort",
        help="Validate and hash a consecutive pre-outcome candidate ledger",
    )
    freeze.add_argument("--candidates", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--protocol-version", default="0.3")
    freeze.set_defaults(handler=_freeze_cohort)

    build = commands.add_parser("build", help="Build a feature table from a JSONL pair registry")
    build.add_argument("--registry", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=_build)

    evaluate = commands.add_parser("evaluate", help="Run locked project and temporal validation")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument("--bootstrap", type=int, default=2_000)
    evaluate.add_argument("--seed", type=int, default=42)
    evaluate.add_argument("--review-budget", type=float, default=0.10)
    evaluate.set_defaults(handler=_evaluate)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ValueError as exc:
        parser.error(str(exc))
