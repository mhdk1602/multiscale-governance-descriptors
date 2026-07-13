"""Leakage-resistant evaluation for the PR-level change-risk study."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features import select_feature_columns
from .labels import validate_annotation_table


MODEL_GROUPS = {
    "baseline": ("baseline",),
    "baseline_governance": ("baseline", "governance"),
    "baseline_multiscale": ("baseline", "multiscale"),
    "full": ("baseline", "governance", "multiscale"),
}


@dataclass
class PredictionBundle:
    row_indices: np.ndarray
    y_true: np.ndarray
    y_score: np.ndarray
    projects: np.ndarray
    fold_coefficients: list[dict[str, float]]


def _pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2_000,
                    random_state=42,
                    solver="liblinear",
                ),
            ),
        ]
    )


def _validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"project", "change_id", "merged_at", "label_status", "outcome_primary"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Study dataset is missing {sorted(missing)}")
    if "manifest_visible_change" in frame and not frame[
        "manifest_visible_change"
    ].astype(bool).all():
        invalid = frame.loc[
            ~frame["manifest_visible_change"].astype(bool), ["project", "change_id"]
        ]
        keys = ", ".join(
            f"{row.project}:{row.change_id}" for row in invalid.itertuples(index=False)
        )
        raise ValueError(f"Evaluation contains changes with no manifest-visible exposure: {keys}")
    records = frame[list(required)].to_dict(orient="records")
    validate_annotation_table(records, require_adjudicated=True)
    data = frame.copy()
    data["outcome_primary"] = data["outcome_primary"].astype(int)
    if data["outcome_primary"].nunique() != 2:
        raise ValueError("Evaluation requires both adverse and non-adverse changes")
    if data["project"].nunique() < 3:
        raise ValueError("Leave-project-out evaluation requires at least three projects")
    data["merged_at"] = pd.to_datetime(data["merged_at"], utc=True, errors="raise")
    return data.reset_index(drop=True)


def _coefficients(estimator: Pipeline, feature_columns: list[str]) -> dict[str, float]:
    model = estimator.named_steps["model"]
    values = model.coef_[0]
    if len(values) != len(feature_columns):
        return {}
    return {name: float(value) for name, value in zip(feature_columns, values)}


def leave_project_out_predictions(
    frame: pd.DataFrame,
    feature_groups: Iterable[str],
) -> PredictionBundle:
    """Predict every change using a model that never saw its repository."""

    data = _validate_frame(frame)
    columns = select_feature_columns(data.columns, feature_groups)
    if not columns:
        raise ValueError(f"No features found for groups {tuple(feature_groups)}")

    scores = np.full(len(data), np.nan)
    coefficients = []
    for project in sorted(data["project"].unique()):
        test_mask = data["project"].eq(project).to_numpy()
        train_mask = ~test_mask
        y_train = data.loc[train_mask, "outcome_primary"].to_numpy()
        if len(np.unique(y_train)) < 2:
            raise ValueError(f"Training fold without both outcomes while holding out {project}")
        estimator = _pipeline()
        estimator.fit(data.loc[train_mask, columns], y_train)
        scores[test_mask] = estimator.predict_proba(data.loc[test_mask, columns])[:, 1]
        coefficients.append(_coefficients(estimator, columns))

    return PredictionBundle(
        row_indices=np.arange(len(data)),
        y_true=data["outcome_primary"].to_numpy(),
        y_score=scores,
        projects=data["project"].astype(str).to_numpy(),
        fold_coefficients=coefficients,
    )


def terminal_temporal_predictions(
    frame: pd.DataFrame,
    feature_groups: Iterable[str],
    *,
    holdout_fraction: float = 0.20,
) -> PredictionBundle:
    """Hold out the terminal fraction of each project as one pooled future set."""

    data = _validate_frame(frame)
    columns = select_feature_columns(data.columns, feature_groups)
    holdout_indices = []
    for _, group in data.sort_values("merged_at").groupby("project", sort=True):
        n_holdout = max(1, int(math.ceil(len(group) * holdout_fraction)))
        holdout_indices.extend(group.tail(n_holdout).index.tolist())
    test_mask = data.index.isin(holdout_indices)
    train_mask = ~test_mask
    y_train = data.loc[train_mask, "outcome_primary"].to_numpy()
    if len(np.unique(y_train)) < 2:
        raise ValueError("Temporal training set does not contain both outcomes")
    estimator = _pipeline()
    estimator.fit(data.loc[train_mask, columns], y_train)
    scores = estimator.predict_proba(data.loc[test_mask, columns])[:, 1]
    return PredictionBundle(
        row_indices=data.index[test_mask].to_numpy(),
        y_true=data.loc[test_mask, "outcome_primary"].to_numpy(),
        y_score=scores,
        projects=data.loc[test_mask, "project"].astype(str).to_numpy(),
        fold_coefficients=[_coefficients(estimator, columns)],
    )


def _recall_at_budget(y_true: np.ndarray, y_score: np.ndarray, budget: float) -> float:
    positives = int(y_true.sum())
    if positives == 0:
        return float("nan")
    selected = max(1, int(math.ceil(len(y_true) * budget)))
    top = np.argsort(-y_score)[:selected]
    return float(y_true[top].sum() / positives)


def prediction_metrics(bundle: PredictionBundle, *, review_budget: float = 0.10) -> dict:
    y_true, y_score = bundle.y_true, bundle.y_score
    return {
        "n": int(len(y_true)),
        "n_events": int(y_true.sum()),
        "event_rate": float(y_true.mean()),
        "average_precision": float(average_precision_score(y_true, y_score)),
        "roc_auc": (
            float(roc_auc_score(y_true, y_score)) if len(np.unique(y_true)) == 2 else None
        ),
        "brier_score": float(brier_score_loss(y_true, y_score)),
        "review_budget": float(review_budget),
        "recall_at_review_budget": _recall_at_budget(y_true, y_score, review_budget),
    }


def _cluster_bootstrap_ap_difference(
    baseline: PredictionBundle,
    candidate: PredictionBundle,
    *,
    n_bootstrap: int,
    seed: int,
) -> dict:
    if not np.array_equal(baseline.row_indices, candidate.row_indices):
        raise ValueError("Prediction bundles do not cover the same rows")
    projects = np.unique(baseline.projects)
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(n_bootstrap):
        sampled_projects = rng.choice(projects, size=len(projects), replace=True)
        sampled_indices = np.concatenate(
            [np.flatnonzero(baseline.projects == project) for project in sampled_projects]
        )
        y = baseline.y_true[sampled_indices]
        if len(np.unique(y)) < 2:
            continue
        base_ap = average_precision_score(y, baseline.y_score[sampled_indices])
        candidate_ap = average_precision_score(y, candidate.y_score[sampled_indices])
        differences.append(float(candidate_ap - base_ap))
    values = np.asarray(differences)
    if not len(values):
        return {"estimate": None, "ci95": [None, None], "n_bootstrap_valid": 0}
    observed = average_precision_score(candidate.y_true, candidate.y_score) - average_precision_score(
        baseline.y_true, baseline.y_score
    )
    return {
        "estimate": float(observed),
        "ci95": [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))],
        "probability_positive": float(np.mean(values > 0)),
        "n_bootstrap_valid": int(len(values)),
    }


def _moderation_summary(bundle: PredictionBundle) -> dict[str, dict[str, float]]:
    names = sorted(
        {
            name
            for fold in bundle.fold_coefficients
            for name in fold
            if name.startswith("governance__interaction__")
        }
    )
    result = {}
    for name in names:
        values = np.asarray([fold[name] for fold in bundle.fold_coefficients if name in fold])
        if len(values):
            result[name] = {
                "median_standardized_coefficient": float(np.median(values)),
                "iqr": [float(np.quantile(values, 0.25)), float(np.quantile(values, 0.75))],
                "fraction_negative": float(np.mean(values < 0)),
            }
    return result


def evaluate_study(
    frame: pd.DataFrame,
    *,
    n_bootstrap: int = 2_000,
    seed: int = 42,
    review_budget: float = 0.10,
) -> dict:
    """Run the locked model comparisons and return a JSON-safe report."""

    logo = {
        name: leave_project_out_predictions(frame, groups)
        for name, groups in MODEL_GROUPS.items()
    }
    temporal = {
        name: terminal_temporal_predictions(frame, groups)
        for name, groups in MODEL_GROUPS.items()
    }
    return {
        "protocol": {
            "models": {name: list(groups) for name, groups in MODEL_GROUPS.items()},
            "classifier": "median-impute + standardize + class-balanced logistic regression",
            "regularization_C": 1.0,
            "primary_metric": "leave-project-out incremental average precision",
            "review_budget": review_budget,
            "n_cluster_bootstrap": n_bootstrap,
        },
        "leave_project_out": {
            name: prediction_metrics(bundle, review_budget=review_budget)
            for name, bundle in logo.items()
        },
        "terminal_temporal_holdout": {
            name: prediction_metrics(bundle, review_budget=review_budget)
            for name, bundle in temporal.items()
        },
        "primary_incremental_multiscale_vs_baseline": _cluster_bootstrap_ap_difference(
            logo["baseline"], logo["baseline_multiscale"], n_bootstrap=n_bootstrap, seed=seed
        ),
        "incremental_multiscale_given_governance": _cluster_bootstrap_ap_difference(
            logo["baseline_governance"], logo["full"], n_bootstrap=n_bootstrap, seed=seed + 1
        ),
        "governance_moderation_direction": _moderation_summary(logo["full"]),
    }
