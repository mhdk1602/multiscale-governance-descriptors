"""Typed lineage extraction from dbt ``manifest.json`` artifacts.

The longitudinal phase-four experiment inferred dependencies from SQL with a
regular expression. That was adequate for exploration but cannot support
commit-level attribution. This module instead consumes dbt's parsed artifact,
preserves canonical ``unique_id`` values and dependency direction, and records
the controls that are observable at the change boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import networkx as nx


GRAPH_SECTIONS = (
    "nodes",
    "sources",
    "exposures",
    "metrics",
    "semantic_models",
    "saved_queries",
)

LINEAGE_RESOURCE_TYPES = {
    "analysis",
    "exposure",
    "metric",
    "model",
    "seed",
    "semantic_model",
    "snapshot",
    "source",
    "saved_query",
}


@dataclass(frozen=True)
class ManifestSnapshot:
    """A parsed dbt artifact plus extraction and governance metadata."""

    graph: nx.DiGraph
    governance: Mapping[str, float]
    metadata: Mapping[str, Any]
    fingerprints: Mapping[str, str]
    source_path: str
    sha256: str


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _truthy_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contract_enforced(record: Mapping[str, Any]) -> bool:
    contract = _as_mapping(record.get("contract"))
    config = _as_mapping(record.get("config"))
    config_contract = _as_mapping(config.get("contract"))
    return bool(contract.get("enforced") or config_contract.get("enforced"))


def _owner_defined(record: Mapping[str, Any]) -> bool:
    owner = _as_mapping(record.get("owner"))
    meta = _as_mapping(record.get("meta"))
    config_meta = _as_mapping(_as_mapping(record.get("config")).get("meta"))
    return any(
        _truthy_text(value)
        for value in (
            owner.get("name"),
            owner.get("email"),
            meta.get("owner"),
            config_meta.get("owner"),
        )
    )


def _freshness_defined(record: Mapping[str, Any]) -> bool:
    freshness = _as_mapping(record.get("freshness"))
    return bool(freshness.get("warn_after") or freshness.get("error_after"))


def _canonical_fingerprint(record: Mapping[str, Any]) -> str:
    """Hash fields whose change can alter lineage, code, or governance state."""

    selected = {
        "resource_type": record.get("resource_type"),
        "checksum": record.get("checksum"),
        "depends_on": _as_mapping(record.get("depends_on")).get("nodes", []),
        "access": record.get("access") or _as_mapping(record.get("config")).get("access"),
        "contract": record.get("contract") or _as_mapping(record.get("config")).get("contract"),
        "description": record.get("description"),
        "columns": record.get("columns"),
        "owner": record.get("owner"),
        "freshness": record.get("freshness"),
        "meta": record.get("meta") or _as_mapping(record.get("config")).get("meta"),
        "materialized": _as_mapping(record.get("config")).get("materialized"),
        "raw_code": record.get("raw_code"),
    }
    payload = json.dumps(selected, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _node_attributes(record: Mapping[str, Any]) -> dict[str, Any]:
    resource_type = str(record.get("resource_type") or "unknown")
    config = _as_mapping(record.get("config"))
    return {
        "resource_type": resource_type,
        "package_name": str(record.get("package_name") or ""),
        "original_file_path": str(record.get("original_file_path") or ""),
        "database": str(record.get("database") or ""),
        "schema": str(record.get("schema") or ""),
        "access": str(record.get("access") or config.get("access") or ""),
        "contract_enforced": _contract_enforced(record),
        "owner_defined": _owner_defined(record),
        "description_defined": _truthy_text(record.get("description")),
        "freshness_defined": _freshness_defined(record),
        "test_count": 0,
    }


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _governance_coverage(graph: nx.DiGraph) -> dict[str, float]:
    model_ids = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("resource_type") in {"model", "seed", "snapshot"}
    ]
    source_ids = [
        node for node, data in graph.nodes(data=True) if data.get("resource_type") == "source"
    ]
    governed_ids = [node for node in graph if graph.nodes[node].get("resource_type") != "test"]

    return {
        "model_test_coverage": _safe_ratio(
            sum(graph.nodes[node].get("test_count", 0) > 0 for node in model_ids), len(model_ids)
        ),
        "model_contract_coverage": _safe_ratio(
            sum(bool(graph.nodes[node].get("contract_enforced")) for node in model_ids),
            len(model_ids),
        ),
        "owner_coverage": _safe_ratio(
            sum(bool(graph.nodes[node].get("owner_defined")) for node in governed_ids),
            len(governed_ids),
        ),
        "description_coverage": _safe_ratio(
            sum(bool(graph.nodes[node].get("description_defined")) for node in governed_ids),
            len(governed_ids),
        ),
        "source_freshness_coverage": _safe_ratio(
            sum(bool(graph.nodes[node].get("freshness_defined")) for node in source_ids),
            len(source_ids),
        ),
    }


def _iter_records(manifest: Mapping[str, Any]):
    for section in GRAPH_SECTIONS:
        for unique_id, record in _as_mapping(manifest.get(section)).items():
            if isinstance(record, Mapping):
                yield str(unique_id), record


def load_manifest(path: str | Path) -> ManifestSnapshot:
    """Load one dbt manifest into a typed dependency graph.

    Tests are represented as controls on their dependencies rather than lineage
    nodes. Every other supported resource is retained when it participates in
    the artifact. Edges point from dependency to consumer.
    """

    source = Path(path)
    raw = source.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, Mapping):
        raise ValueError(f"Manifest must contain a JSON object: {source}")

    graph = nx.DiGraph()
    fingerprints: dict[str, str] = {}
    records: dict[str, Mapping[str, Any]] = {}
    tests: list[Mapping[str, Any]] = []

    for unique_id, record in _iter_records(manifest):
        resource_type = str(record.get("resource_type") or unique_id.split(".", 1)[0])
        if resource_type == "test":
            tests.append(record)
            continue
        if resource_type not in LINEAGE_RESOURCE_TYPES:
            continue
        records[unique_id] = record
        graph.add_node(unique_id, **_node_attributes(record))
        fingerprints[unique_id] = _canonical_fingerprint(record)

    for unique_id, record in records.items():
        dependencies = _as_list(_as_mapping(record.get("depends_on")).get("nodes"))
        for dependency in dependencies:
            dependency = str(dependency)
            if dependency in graph:
                graph.add_edge(
                    dependency,
                    unique_id,
                    dependency_type="lineage",
                    consumer_type=graph.nodes[unique_id].get("resource_type"),
                )

    for test in tests:
        for dependency in _as_list(_as_mapping(test.get("depends_on")).get("nodes")):
            dependency = str(dependency)
            if dependency in graph:
                graph.nodes[dependency]["test_count"] += 1

    metadata = _as_mapping(manifest.get("metadata"))
    return ManifestSnapshot(
        graph=graph,
        governance=_governance_coverage(graph),
        metadata={
            "dbt_schema_version": metadata.get("dbt_schema_version"),
            "dbt_version": metadata.get("dbt_version"),
            "generated_at": metadata.get("generated_at"),
            "invocation_id": metadata.get("invocation_id"),
            "n_nodes": graph.number_of_nodes(),
            "n_edges": graph.number_of_edges(),
        },
        fingerprints=fingerprints,
        source_path=str(source.resolve()),
        sha256=sha256(raw).hexdigest(),
    )
