"""Experiment 4: Predictive comparison against baselines.

Uses Experiment 1 data to test whether multi-scale descriptors (D1-D4)
predict governance quality better than single-scale baselines
(degree stats, betweenness, PageRank, diameter, density).

Models: logistic regression (well vs poor classification) and
linear regression (MTTD prediction).
Feature sets: (a) baselines only, (b) multi-scale only, (c) combined.
Evaluation: cross-validated AUC and RMSE with permutation importance.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score, KFold
from sklearn.metrics import roc_auc_score, mean_squared_error
from sklearn.inspection import permutation_importance


def load_data():
    """Load Experiment 1 results."""
    csv_path = os.path.join(os.path.dirname(__file__), '..', '..',
                            'artifacts', 'phase_2', 'exp_1_governance_differentiation.csv')
    return pd.read_csv(csv_path)


def get_feature_sets(df):
    """Define feature sets."""
    multiscale_cols = [
        "D1_csi", "D1_frag_onset", "D1_stab_var",
        "D2_max_gini", "D2_transition",
        "D3_norm_gap", "D3_fiedler_bim", "D3_entropy",
        "D4_h1_bars_norm", "D4_h1_persist", "D4_h1_entropy",
    ]
    baseline_cols = [
        "BL_mean_degree", "BL_std_degree", "BL_max_in_degree", "BL_max_out_degree",
        "BL_mean_betweenness", "BL_max_betweenness", "BL_max_pagerank",
        "BL_diameter", "BL_density",
    ]

    multiscale_cols = [c for c in multiscale_cols if c in df.columns]
    baseline_cols = [c for c in baseline_cols if c in df.columns]

    return multiscale_cols, baseline_cols


def classification_experiment(df):
    """Classify well vs poor governance using descriptors."""
    print("=" * 70)
    print("CLASSIFICATION: well vs poor governance")
    print("=" * 70)

    sub = df[df["governance"].isin(["well", "poor"])].copy()
    sub["label"] = (sub["governance"] == "well").astype(int)

    multiscale_cols, baseline_cols = get_feature_sets(sub)
    combined_cols = multiscale_cols + baseline_cols

    y = sub["label"].values
    results = []

    feature_sets = {
        "baselines_only": baseline_cols,
        "multiscale_only": multiscale_cols,
        "combined": combined_cols,
    }

    for fs_name, cols in feature_sets.items():
        X = sub[cols].values
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        for model_name, model in [
            ("logistic", LogisticRegression(max_iter=1000, random_state=42)),
            ("random_forest", RandomForestClassifier(n_estimators=100, random_state=42)),
        ]:
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            aucs = cross_val_score(model, X_scaled, y, cv=cv, scoring="roc_auc")

            result = {
                "features": fs_name,
                "model": model_name,
                "mean_auc": np.mean(aucs),
                "std_auc": np.std(aucs),
                "n_features": len(cols),
            }
            results.append(result)
            print(f"  {fs_name:20s} + {model_name:15s}: AUC={np.mean(aucs):.3f} +/- {np.std(aucs):.3f}")

    df_results = pd.DataFrame(results)
    print(f"\n{df_results.to_string(index=False)}\n")

    # Permutation importance for combined RF
    X_combined = np.nan_to_num(sub[combined_cols].values, nan=0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_combined)
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_scaled, y)
    perm = permutation_importance(rf, X_scaled, y, n_repeats=30, random_state=42)

    print("Feature importance (permutation, combined RF):")
    sorted_idx = perm.importances_mean.argsort()[::-1]
    for i in sorted_idx[:10]:
        print(f"  {combined_cols[i]:25s}: {perm.importances_mean[i]:.4f} +/- {perm.importances_std[i]:.4f}")

    return df_results


def regression_experiment(df):
    """Predict MTTD using descriptors."""
    print("\n" + "=" * 70)
    print("REGRESSION: Predict MTTD (stewardship monitors)")
    print("=" * 70)

    multiscale_cols, baseline_cols = get_feature_sets(df)
    combined_cols = multiscale_cols + baseline_cols

    y = df["MTTD_stew_mean"].values
    results = []

    feature_sets = {
        "baselines_only": baseline_cols,
        "multiscale_only": multiscale_cols,
        "combined": combined_cols,
    }

    for fs_name, cols in feature_sets.items():
        X = df[cols].values
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        for model_name, model in [
            ("ridge", Ridge(alpha=1.0)),
            ("random_forest", RandomForestRegressor(n_estimators=100, random_state=42)),
        ]:
            cv = KFold(n_splits=5, shuffle=True, random_state=42)
            neg_mse = cross_val_score(model, X_scaled, y, cv=cv, scoring="neg_mean_squared_error")
            rmses = np.sqrt(-neg_mse)

            r2 = cross_val_score(model, X_scaled, y, cv=cv, scoring="r2")

            result = {
                "features": fs_name,
                "model": model_name,
                "mean_rmse": np.mean(rmses),
                "std_rmse": np.std(rmses),
                "mean_r2": np.mean(r2),
                "std_r2": np.std(r2),
                "n_features": len(cols),
            }
            results.append(result)
            print(f"  {fs_name:20s} + {model_name:15s}: RMSE={np.mean(rmses):.3f} +/- {np.std(rmses):.3f}, R2={np.mean(r2):.3f}")

    df_results = pd.DataFrame(results)
    print(f"\n{df_results.to_string(index=False)}\n")
    return df_results


def scale_stratified_analysis(df):
    """Run classification per scale to check if results hold across sizes."""
    print("\n" + "=" * 70)
    print("SCALE-STRATIFIED CLASSIFICATION (well vs poor)")
    print("=" * 70)

    multiscale_cols, baseline_cols = get_feature_sets(df)

    for scale in df["scale"].unique():
        sub = df[(df["scale"] == scale) & (df["governance"].isin(["well", "poor"]))].copy()
        if len(sub) < 10:
            continue
        sub["label"] = (sub["governance"] == "well").astype(int)
        y = sub["label"].values

        for fs_name, cols in [("baselines", baseline_cols), ("multiscale", multiscale_cols)]:
            X = np.nan_to_num(sub[cols].values, nan=0.0)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Leave-one-out for small samples
            from sklearn.model_selection import LeaveOneOut
            loo = LeaveOneOut()
            rf = RandomForestClassifier(n_estimators=50, random_state=42)

            preds = []
            trues = []
            for train_idx, test_idx in loo.split(X_scaled):
                rf.fit(X_scaled[train_idx], y[train_idx])
                preds.append(rf.predict_proba(X_scaled[test_idx])[0, 1])
                trues.append(y[test_idx][0])

            try:
                auc = roc_auc_score(trues, preds)
            except ValueError:
                auc = 0.5

            print(f"  {scale:8s} + {fs_name:12s}: LOO-AUC={auc:.3f} (n={len(sub)})")


def main():
    print("Experiment 4: Predictive Comparison (Multi-Scale vs Baselines)")
    print("=" * 70)

    df = load_data()
    print(f"Loaded {len(df)} rows, {df['scale'].nunique()} scales, "
          f"{df['governance'].nunique()} governance levels\n")

    df_class = classification_experiment(df)
    df_reg = regression_experiment(df)
    scale_stratified_analysis(df)

    out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'artifacts', 'phase_2')
    os.makedirs(out_dir, exist_ok=True)
    df_class.to_csv(os.path.join(out_dir, "exp_4_classification.csv"), index=False)
    df_reg.to_csv(os.path.join(out_dir, "exp_4_regression.csv"), index=False)

    # Delta-AUC check for Phase 3 gate
    print("\n" + "=" * 70)
    print("PHASE 3 GATE CHECK")
    print("=" * 70)
    bl_auc = df_class[(df_class["features"] == "baselines_only") &
                       (df_class["model"] == "random_forest")]["mean_auc"].values[0]
    ms_auc = df_class[(df_class["features"] == "multiscale_only") &
                       (df_class["model"] == "random_forest")]["mean_auc"].values[0]
    comb_auc = df_class[(df_class["features"] == "combined") &
                         (df_class["model"] == "random_forest")]["mean_auc"].values[0]

    print(f"  Baselines RF AUC:   {bl_auc:.3f}")
    print(f"  Multiscale RF AUC:  {ms_auc:.3f}")
    print(f"  Combined RF AUC:    {comb_auc:.3f}")
    print(f"  Delta (combined - baselines): {comb_auc - bl_auc:+.3f}")
    print(f"  Gate (delta > 0.05): {'PASS' if (comb_auc - bl_auc) > 0.05 else 'FAIL'}")

    print(f"\nCSV artifacts saved to {out_dir}")


if __name__ == "__main__":
    main()
