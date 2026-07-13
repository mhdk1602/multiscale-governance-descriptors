"""Hermetic collection of exact before/after dbt manifests from git refs."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from typing import Mapping, Sequence

from .manifest import load_manifest


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _run_commands(cwd: Path, commands: Sequence[str]) -> None:
    for command in commands:
        argv = shlex.split(command)
        if not argv:
            continue
        subprocess.run(argv, cwd=cwd, check=True)


def _change_summary(before, after) -> dict[str, int | bool]:
    before_nodes = set(before.graph)
    after_nodes = set(after.graph)
    shared_nodes = before_nodes & after_nodes
    modified_nodes = {
        node
        for node in shared_nodes
        if before.fingerprints.get(node) != after.fingerprints.get(node)
    }
    before_edges = set(before.graph.edges())
    after_edges = set(after.graph.edges())
    summary = {
        "nodes_before": len(before_nodes),
        "nodes_after": len(after_nodes),
        "nodes_added": len(after_nodes - before_nodes),
        "nodes_removed": len(before_nodes - after_nodes),
        "nodes_modified": len(modified_nodes),
        "edges_before": len(before_edges),
        "edges_after": len(after_edges),
        "edges_added": len(after_edges - before_edges),
        "edges_removed": len(before_edges - after_edges),
    }
    summary["manifest_visible_change"] = any(
        summary[key]
        for key in (
            "nodes_added",
            "nodes_removed",
            "nodes_modified",
            "edges_added",
            "edges_removed",
        )
    )
    return summary


def _materialize_manifest(
    repo: Path,
    ref: str,
    *,
    project_subdir: str,
    commands: Sequence[str],
    manifest_relative_path: str,
    destination: Path,
) -> str:
    resolved_ref = _git(repo, "rev-parse", f"{ref}^{{commit}}")
    with tempfile.TemporaryDirectory(prefix="governance-change-risk-") as temp:
        worktree = Path(temp) / "checkout"
        _git(repo, "worktree", "add", "--detach", str(worktree), resolved_ref)
        try:
            project_dir = worktree / project_subdir
            if not project_dir.exists():
                raise FileNotFoundError(f"dbt project directory does not exist: {project_dir}")
            _run_commands(project_dir, commands)
            manifest = project_dir / manifest_relative_path
            if not manifest.exists():
                raise FileNotFoundError(
                    f"Commands completed but did not create {manifest_relative_path} at {resolved_ref}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(manifest, destination)
        finally:
            _git(repo, "worktree", "remove", "--force", str(worktree))
    return resolved_ref


def collect_manifest_pair(
    *,
    repo: str | Path,
    project: str,
    change_id: str,
    merged_at: str,
    before_ref: str,
    after_ref: str,
    output_dir: str | Path,
    project_subdir: str = ".",
    commands: Sequence[str] = ("dbt parse --no-partial-parse",),
    manifest_relative_path: str = "target/manifest.json",
    change_url: str | None = None,
    outcome_window_days: int = 30,
    baseline_covariates: Mapping[str, float] | None = None,
) -> dict:
    """Generate and preserve an exact manifest pair with immutable provenance."""

    repository = Path(repo).resolve()
    if not (repository / ".git").exists():
        raise ValueError(f"Not a git repository: {repository}")
    destination = Path(output_dir) / project / str(change_id)
    before_manifest = destination / "before_manifest.json"
    after_manifest = destination / "after_manifest.json"

    resolved_before = _materialize_manifest(
        repository,
        before_ref,
        project_subdir=project_subdir,
        commands=commands,
        manifest_relative_path=manifest_relative_path,
        destination=before_manifest,
    )
    resolved_after = _materialize_manifest(
        repository,
        after_ref,
        project_subdir=project_subdir,
        commands=commands,
        manifest_relative_path=manifest_relative_path,
        destination=after_manifest,
    )

    before = load_manifest(before_manifest)
    after = load_manifest(after_manifest)
    record = {
        "project": project,
        "change_id": str(change_id),
        "change_url": change_url,
        "merged_at": merged_at,
        "before_ref": resolved_before,
        "after_ref": resolved_after,
        "before_manifest": str(before_manifest.resolve()),
        "after_manifest": str(after_manifest.resolve()),
        "before_manifest_sha256": before.sha256,
        "after_manifest_sha256": after.sha256,
        "extraction_summary": _change_summary(before, after),
        "collection": {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "repository": str(repository),
            "project_subdir": project_subdir,
            "commands": list(commands),
            "manifest_relative_path": manifest_relative_path,
        },
        "label_status": "unreviewed",
        "outcome_primary": None,
        "outcome_window_days": int(outcome_window_days),
        "baseline_covariates": dict(baseline_covariates or {}),
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "pair.json").write_text(json.dumps(record, indent=2) + "\n")
    return record
