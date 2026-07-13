from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from governance_descriptors.change_risk.evaluation import evaluate_study
from governance_descriptors.change_risk.features import extract_change_features
from governance_descriptors.change_risk.labels import candidate_repair_signal
from governance_descriptors.change_risk.manifest import load_manifest
from governance_descriptors.change_risk.study import build_study_dataset


FIXTURES = Path(__file__).parent / "fixtures" / "change_risk"
BEFORE = FIXTURES / "before_manifest.json"
AFTER = FIXTURES / "after_manifest.json"


def test_manifest_preserves_typed_lineage_and_attaches_tests_as_controls():
    before = load_manifest(BEFORE)
    after = load_manifest(AFTER)

    assert before.graph.number_of_nodes() == 6
    assert before.graph.number_of_edges() == 4
    assert "test.demo.not_null_orders_id" not in before.graph
    assert before.graph.has_edge("source.demo.raw_orders", "model.demo.stg_orders")
    assert before.graph.has_edge("model.demo.orders", "exposure.demo.executive_dashboard")
    assert before.graph.nodes["model.demo.orders"]["test_count"] == 1

    assert after.graph.number_of_nodes() == 7
    assert after.graph.number_of_edges() == 6
    assert after.graph.has_edge("model.demo.orders", "model.demo.customer_orders")
    assert after.graph.has_edge("model.demo.customers", "model.demo.customer_orders")
    assert after.governance["model_test_coverage"] == pytest.approx(0.5)
    assert after.governance["model_contract_coverage"] == pytest.approx(0.5)
    assert after.governance["source_freshness_coverage"] == pytest.approx(1.0)


def test_change_features_separate_baselines_controls_and_multiscale_deltas():
    features = extract_change_features(load_manifest(BEFORE), load_manifest(AFTER))

    assert features["baseline__nodes_added"] == 1
    assert features["baseline__edges_added"] == 3
    assert features["baseline__edges_removed"] == 1
    assert features["baseline__changed_descendants_after"] >= 2
    assert features["governance__delta__model_contract_coverage"] == pytest.approx(0.5)
    assert "governance__interaction__blast_fraction_x_model_test_coverage" in features
    assert "multiscale__delta__d2_gini_auc" in features
    assert "multiscale__delta__d4_cycle_rank_norm" in features
    assert all(np.isfinite(value) for value in features.values())


def test_dataset_records_manifest_hashes_and_refuses_duplicate_changes(tmp_path):
    record = {
        "project": "demo",
        "change_id": "42",
        "merged_at": "2026-01-02T00:00:00Z",
        "before_manifest": str(BEFORE),
        "after_manifest": str(AFTER),
        "label_status": "unreviewed",
        "outcome_primary": None,
    }
    frame = build_study_dataset([record])
    assert len(frame) == 1
    assert len(frame.loc[0, "before_manifest_sha256"]) == 64
    assert frame.loc[0, "feature_spec_version"] == "governance-change-risk-v1"
    assert bool(frame.loc[0, "manifest_visible_change"])
    assert np.isnan(frame.loc[0, "baseline__repo__lines_added"])

    with pytest.raises(ValueError, match="Duplicate change"):
        build_study_dataset([record, record])


def test_dataset_verifies_declared_hashes_and_marks_manifest_noops():
    record = {
        "project": "demo",
        "change_id": "same-manifest",
        "merged_at": "2026-01-02T00:00:00Z",
        "before_manifest": str(BEFORE),
        "after_manifest": str(BEFORE),
        "label_status": "unreviewed",
        "outcome_primary": None,
    }
    frame = build_study_dataset([record])
    assert not bool(frame.loc[0, "manifest_visible_change"])

    record["before_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="before manifest hash mismatch"):
        build_study_dataset([record])


def test_adjudicated_records_require_locked_repository_covariates():
    record = {
        "project": "demo",
        "change_id": "42",
        "merged_at": "2026-01-02T00:00:00Z",
        "before_manifest": str(BEFORE),
        "after_manifest": str(AFTER),
        "label_status": "adjudicated",
        "outcome_primary": 0,
        "baseline_covariates": {"lines_added": 12},
    }
    with pytest.raises(ValueError, match="every locked baseline covariate"):
        build_study_dataset([record])

    record["baseline_covariates"] = {
        "lines_added": 12,
        "lines_deleted": 3,
        "files_changed": 4,
        "author_prior_merged_changes": 9,
        "prior_30d_failed_workflows": 1,
    }
    frame = build_study_dataset([record])
    assert frame.loc[0, "baseline__repo__lines_added"] == 12


def _evaluation_frame():
    rows = []
    rng = np.random.default_rng(12)
    for project_index, project in enumerate(["alpha", "beta", "gamma", "delta"]):
        for change_index in range(12):
            event = int(change_index in {2, 7, 10})
            risk = event + rng.normal(0, 0.15)
            coverage = 0.8 if change_index % 3 else 0.2
            rows.append(
                {
                    "project": project,
                    "change_id": f"{project}-{change_index}",
                    "merged_at": pd.Timestamp("2025-01-01", tz="UTC")
                    + pd.Timedelta(days=project_index * 100 + change_index),
                    "label_status": "adjudicated",
                    "outcome_primary": event,
                    "baseline__changed_descendant_fraction_after": risk,
                    "baseline__nodes_modified": change_index % 4,
                    "governance__after__model_test_coverage": coverage,
                    "governance__interaction__blast_fraction_x_model_test_coverage": risk
                    * coverage,
                    "multiscale__delta__d2_gini_auc": risk + rng.normal(0, 0.05),
                }
            )
    return pd.DataFrame(rows)


def test_evaluation_is_project_held_out_and_requires_adjudication():
    frame = _evaluation_frame()
    report = evaluate_study(frame, n_bootstrap=50, seed=4, review_budget=0.25)
    assert set(report["leave_project_out"]) == {
        "baseline",
        "baseline_governance",
        "baseline_multiscale",
        "full",
    }
    assert report["leave_project_out"]["full"]["n"] == len(frame)
    assert report["primary_incremental_multiscale_vs_baseline"]["n_bootstrap_valid"] > 0

    frame.loc[0, "label_status"] = "single_review"
    with pytest.raises(ValueError, match="refuses non-adjudicated"):
        evaluate_study(frame, n_bootstrap=10)


def test_evaluation_refuses_manifest_noops():
    frame = _evaluation_frame()
    frame["manifest_visible_change"] = True
    frame.loc[0, "manifest_visible_change"] = False
    with pytest.raises(ValueError, match="no manifest-visible exposure"):
        evaluate_study(frame, n_bootstrap=10)


def test_repair_keyword_is_only_a_candidate_signal():
    assert candidate_repair_signal(["Hotfix downstream customer model"])
    assert not candidate_repair_signal(["Add customer lifetime value mart"])
