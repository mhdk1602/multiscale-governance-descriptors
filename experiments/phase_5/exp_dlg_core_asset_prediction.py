"""Experiment 7: Cross-graph core-asset prediction on DLG-DG-23.

The DLG-DG-23 dataset (Chen et al., Visual Informatics 2024) includes expert-
labeled "core data assets" for 6 of the 18 production lineage graphs from
Huawei Cloud. We extracted the labels from Table 5 of the published paper
(36 core assets across DLG1, DLG2, DLG9, DLG11, DLG13, DLG15). Every
labeled core asset is of type 'Data Table'.

Question: do topological descriptors computed at the node level predict
which Data Tables are flagged as core by domain experts?

This is a binary node classification task restricted to Data Table nodes.
Features are computed on the full heterogeneous graph (including Data Job
and Data Field nodes) to preserve graph structure, then extracted per Data
Table node.

Evaluation: leave-one-graph-out cross-validation. Train on 5 graphs,
predict core status on the 6th. Compare against:
  - Random baseline (binomial proportion)
  - Out-degree only baseline
  - Logistic regression on all topological features
  - Random forest on all topological features

This analysis reproduces the node-centrality signal reported for these
graphs. It does not evaluate the paper's graph-level D1--D4 descriptors.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import ttest_1samp
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from sklearn.model_selection import LeaveOneGroupOut
import warnings
warnings.filterwarnings('ignore')


def bootstrap_auc(y_true, scores, n_resamples=2000, seed=42):
    """Return a percentile bootstrap interval for ROC AUC."""
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    rng = np.random.default_rng(seed)
    estimates = []
    for _ in range(n_resamples):
        sample = rng.integers(0, len(y_true), len(y_true))
        if len(np.unique(y_true[sample])) < 2:
            continue
        estimates.append(roc_auc_score(y_true[sample], scores[sample]))
    return tuple(np.quantile(estimates, [0.025, 0.975]))


def load_dlg(graph_id, data_dir):
    """Load a DLG with full asset types and edge types as a DiGraph."""
    nodes_file = data_dir / 'Node' / f'{graph_id}-node.json'
    edges_file = data_dir / 'Edge' / f'{graph_id}-edge.json'
    with open(nodes_file) as f:
        nodes_data = json.load(f)['nodes']
    with open(edges_file) as f:
        edges_data = json.load(f)['edges']

    g = nx.DiGraph()
    for n in nodes_data:
        g.add_node(n['asset_id'], asset_type=n['asset_type'])
    for e in edges_data:
        src, tgt = e['source'], e['target']
        rtype = e.get('relation_type', 'UNKNOWN')
        if src in g and tgt in g:
            g.add_edge(src, tgt, relation_type=rtype)
    return g


def compute_node_features(g):
    """Compute node-level topological features on a DLG.

    Returns DataFrame indexed by node_id, with features and asset_type.
    """
    n_total = g.number_of_nodes()
    print(f"    Computing features for {n_total} nodes, {g.number_of_edges()} edges...", flush=True)

    # Edge subgraphs by type
    dataflow_edges = [(u, v) for u, v, d in g.edges(data=True)
                      if d.get('relation_type') == 'DATA_FLOW']
    parent_child_edges = [(u, v) for u, v, d in g.edges(data=True)
                          if d.get('relation_type') == 'PARENT_CHILD']
    g_dataflow = nx.DiGraph()
    g_dataflow.add_nodes_from(g.nodes(data=True))
    g_dataflow.add_edges_from(dataflow_edges)

    # Degree (full graph)
    in_deg = dict(g.in_degree())
    out_deg = dict(g.out_degree())

    # Degree on DATA_FLOW subgraph (the meaningful "data movement" graph)
    df_in_deg = dict(g_dataflow.in_degree())
    df_out_deg = dict(g_dataflow.out_degree())

    # PARENT_CHILD count (number of fields a table has)
    pc_children = {n: 0 for n in g.nodes()}
    for u, v in parent_child_edges:
        pc_children[u] = pc_children.get(u, 0) + 1

    # PageRank on DATA_FLOW only
    if g_dataflow.number_of_edges() > 0:
        try:
            pr_df = nx.pagerank(g_dataflow, alpha=0.85)
        except Exception:
            pr_df = {n: 1.0 / n_total for n in g.nodes()}
    else:
        pr_df = {n: 1.0 / n_total for n in g.nodes()}

    # Reverse-PageRank: probability of being a "source" of flows
    g_dataflow_rev = g_dataflow.reverse(copy=True)
    if g_dataflow_rev.number_of_edges() > 0:
        try:
            pr_df_rev = nx.pagerank(g_dataflow_rev, alpha=0.85)
        except Exception:
            pr_df_rev = {n: 1.0 / n_total for n in g.nodes()}
    else:
        pr_df_rev = {n: 1.0 / n_total for n in g.nodes()}

    # Betweenness on DATA_FLOW (sampled if large)
    if g_dataflow.number_of_edges() == 0:
        bw_df = {n: 0.0 for n in g.nodes()}
    elif n_total > 1000:
        try:
            bw_df = nx.betweenness_centrality(g_dataflow, k=min(100, n_total), seed=42)
        except Exception:
            bw_df = {n: 0.0 for n in g.nodes()}
    else:
        try:
            bw_df = nx.betweenness_centrality(g_dataflow)
        except Exception:
            bw_df = {n: 0.0 for n in g.nodes()}

    # Reachability counts on DATA_FLOW
    descendants_count = {}
    ancestors_count = {}
    for n in g.nodes():
        try:
            descendants_count[n] = len(nx.descendants(g_dataflow, n))
        except Exception:
            descendants_count[n] = 0
        try:
            ancestors_count[n] = len(nx.ancestors(g_dataflow, n))
        except Exception:
            ancestors_count[n] = 0

    # Local clustering on undirected
    g_undirected = g.to_undirected()
    try:
        clustering = nx.clustering(g_undirected)
    except Exception:
        clustering = {n: 0.0 for n in g.nodes()}

    # Build DataFrame
    rows = []
    for nid in g.nodes():
        rows.append({
            'asset_id': nid,
            'asset_type': g.nodes[nid].get('asset_type'),
            'in_degree': in_deg.get(nid, 0),
            'out_degree': out_deg.get(nid, 0),
            'total_degree': in_deg.get(nid, 0) + out_deg.get(nid, 0),
            'df_in_degree': df_in_deg.get(nid, 0),
            'df_out_degree': df_out_deg.get(nid, 0),
            'pc_child_count': pc_children.get(nid, 0),
            'pagerank_df': pr_df.get(nid, 0.0),
            'pagerank_df_reverse': pr_df_rev.get(nid, 0.0),
            'betweenness_df': bw_df.get(nid, 0.0),
            'descendants_df': descendants_count.get(nid, 0),
            'ancestors_df': ancestors_count.get(nid, 0),
            'clustering': clustering.get(nid, 0.0),
        })
    return pd.DataFrame(rows)


def main():
    data_dir = Path(__file__).resolve().parent.parent.parent / 'data' / 'external' / 'dlg-dg-23'
    art_dir = Path(__file__).resolve().parent.parent.parent / 'artifacts' / 'phase_5'
    art_dir.mkdir(parents=True, exist_ok=True)

    with open(data_dir / 'core_assets.json') as f:
        core_data = json.load(f)
    core_assets = core_data['core_assets']

    all_frames = []
    print("=" * 70)
    print("EXTRACTING NODE-LEVEL FEATURES FOR 6 ANNOTATED DLGs")
    print("=" * 70)
    for graph_id in ['DLG1', 'DLG2', 'DLG9', 'DLG11', 'DLG13', 'DLG15']:
        print(f"\n  {graph_id}:")
        g = load_dlg(graph_id, data_dir)
        df = compute_node_features(g)
        df['graph'] = graph_id
        df['is_core'] = df['asset_id'].isin(core_assets[graph_id]).astype(int)
        all_frames.append(df)
    all_df = pd.concat(all_frames, ignore_index=True)

    # Filter to Data Tables only (where the binary task lives)
    tables = all_df[all_df['asset_type'] == 'Data Table'].copy()
    print("\n" + "=" * 70)
    print(f"DATA TABLE NODES: {len(tables)} (across 6 graphs)")
    print(f"Core labelled: {tables['is_core'].sum()}")
    print(f"Non-core: {(~tables['is_core'].astype(bool)).sum()}")
    print(f"Class balance: {tables['is_core'].mean():.3f}")
    print("=" * 70)

    # Per-graph summary
    print("\nPer-graph class balance (Data Tables only):")
    print(f"{'Graph':<8} {'Tables':>8} {'Core':>6} {'Non-core':>10} {'Core %':>8}")
    for g_id in ['DLG1', 'DLG2', 'DLG9', 'DLG11', 'DLG13', 'DLG15']:
        sub = tables[tables['graph'] == g_id]
        print(f"  {g_id:<6} {len(sub):>8} {sub['is_core'].sum():>6} "
              f"{(~sub['is_core'].astype(bool)).sum():>10} "
              f"{100*sub['is_core'].mean():>7.1f}%")

    # === Per-feature univariate ROC-AUC ===
    print("\n" + "=" * 70)
    print("PER-FEATURE ROC-AUC (Data Tables only, pooled across 6 graphs)")
    print("=" * 70)
    features = ['in_degree', 'out_degree', 'total_degree',
                'df_in_degree', 'df_out_degree', 'pc_child_count',
                'pagerank_df', 'pagerank_df_reverse', 'betweenness_df',
                'descendants_df', 'ancestors_df', 'clustering']
    y = tables['is_core'].values
    print(f"\n  {'Feature':<22} {'AUC':>8} {'PR-AUC':>8}")
    print(f"  {'-' * 40}")
    feature_aucs = {}
    for feat in features:
        x = tables[feat].values
        if np.var(x) == 0:
            continue
        try:
            auc = roc_auc_score(y, x)
            pr_auc = average_precision_score(y, x)
            feature_aucs[feat] = auc
            sig = "***" if auc > 0.85 or auc < 0.15 else "**" if auc > 0.75 or auc < 0.25 else "*" if auc > 0.65 or auc < 0.35 else ""
            print(f"  {feat:<22} {auc:>8.3f} {pr_auc:>8.3f} {sig}")
        except Exception as e:
            print(f"  {feat:<22} ERROR {e}")

    # === Leave-one-graph-out classification ===
    print("\n" + "=" * 70)
    print("LEAVE-ONE-GRAPH-OUT CROSS-VALIDATION")
    print("=" * 70)
    print("Train on 5 graphs, predict core-asset status on held-out 6th.\n")

    groups = tables['graph'].values
    X = tables[features].values
    core_id_counts = Counter(
        asset_id
        for graph_assets in core_assets.values()
        for asset_id in graph_assets
    )
    shared_core_ids = sorted(
        asset_id for asset_id, count in core_id_counts.items() if count > 1
    )

    logo = LeaveOneGroupOut()
    results = {'logreg': [], 'rf': [], 'baseline_outdeg': [], 'baseline_random': []}
    fold_details = []
    fold_curves = []
    hardening_folds = []
    sensitivity_results = []
    for fold_number, (train_idx, test_idx) in enumerate(
        logo.split(X, y, groups), start=1,
    ):
        held_out = groups[test_idx][0]
        y_train, y_test = y[train_idx], y[test_idx]
        X_train, X_test = X[train_idx], X[test_idx]

        # Fit the scaler inside each fold so the held-out graph does not
        # influence preprocessing.
        lr = Pipeline([
            ('scale', StandardScaler()),
            ('model', LogisticRegression(
                class_weight='balanced', max_iter=1000, C=1.0,
            )),
        ])
        lr.fit(X_train, y_train)
        lr_scores = lr.predict_proba(X_test)[:, 1]
        lr_auc = roc_auc_score(y_test, lr_scores) if len(np.unique(y_test)) > 1 else np.nan
        results['logreg'].append(lr_auc)
        if len(np.unique(y_test)) > 1:
            fpr, tpr, _ = roc_curve(y_test, lr_scores)
            fold_curves.append((held_out, len(y_test), lr_auc, fpr, tpr))
        ci_low, ci_high = bootstrap_auc(
            y_test, lr_scores, seed=42 + fold_number,
        )

        # Random forest
        rf = RandomForestClassifier(n_estimators=200, class_weight='balanced',
                                    random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)
        rf_scores = rf.predict_proba(X_test)[:, 1]
        rf_auc = roc_auc_score(y_test, rf_scores) if len(np.unique(y_test)) > 1 else np.nan
        results['rf'].append(rf_auc)

        # Out-degree-only baseline (best single feature)
        od_scores = tables.iloc[test_idx]['df_out_degree'].values
        od_auc = roc_auc_score(y_test, od_scores) if len(np.unique(y_test)) > 1 else np.nan
        results['baseline_outdeg'].append(od_auc)

        # Random baseline
        rng = np.random.default_rng(42)
        rand_auc = roc_auc_score(y_test, rng.random(len(y_test))) if len(np.unique(y_test)) > 1 else np.nan
        results['baseline_random'].append(rand_auc)

        fold_details.append({
            'held_out': held_out,
            'n_test': len(y_test),
            'core_in_test': int(y_test.sum()),
            'logreg_auc': float(lr_auc) if not np.isnan(lr_auc) else None,
            'rf_auc': float(rf_auc) if not np.isnan(rf_auc) else None,
            'outdeg_auc': float(od_auc) if not np.isnan(od_auc) else None,
            'random_auc': float(rand_auc) if not np.isnan(rand_auc) else None,
        })
        hardening_folds.append({
            'held_out': held_out,
            'n_test': len(y_test),
            'core_in_test': int(y_test.sum()),
            'lr_auc': float(lr_auc),
            'lr_ci_low': float(ci_low),
            'lr_ci_high': float(ci_high),
            'rf_auc': float(rf_auc),
        })
        retained = ~tables.iloc[test_idx]['asset_id'].isin(shared_core_ids).to_numpy()
        y_filtered = y_test[retained]
        scores_filtered = lr_scores[retained]
        filtered_auc = (
            roc_auc_score(y_filtered, scores_filtered)
            if len(np.unique(y_filtered)) > 1 else np.nan
        )
        sensitivity_results.append({
            'held_out': held_out,
            'n_filtered': int(retained.sum()),
            'removed': int((~retained).sum()),
            'lr_auc_filtered': float(filtered_auc),
        })
        print(f"  Held-out {held_out}: n_test={len(y_test):>5}, core={int(y_test.sum()):>2}  "
              f"LR={lr_auc:.3f}  RF={rf_auc:.3f}  out-deg={od_auc:.3f}  random={rand_auc:.3f}")

    print("\nMean AUCs across folds (leave-one-graph-out):")
    print(f"  Logistic regression:    {np.nanmean(results['logreg']):.3f} ± {np.nanstd(results['logreg']):.3f}")
    print(f"  Random forest:          {np.nanmean(results['rf']):.3f} ± {np.nanstd(results['rf']):.3f}")
    print(f"  Out-degree only:        {np.nanmean(results['baseline_outdeg']):.3f} ± {np.nanstd(results['baseline_outdeg']):.3f}")
    print(f"  Random baseline:        {np.nanmean(results['baseline_random']):.3f} ± {np.nanstd(results['baseline_random']):.3f}")

    # === Random forest feature importance ===
    print("\n" + "=" * 70)
    print("RANDOM FOREST FEATURE IMPORTANCE (trained on all 6 graphs)")
    print("=" * 70)
    rf_full = RandomForestClassifier(n_estimators=500, class_weight='balanced',
                                     random_state=42, n_jobs=-1)
    rf_full.fit(X, y)
    importances = sorted(zip(features, rf_full.feature_importances_), key=lambda kv: -kv[1])
    print(f"  {'Feature':<22} {'Importance':>12}")
    for feat, imp in importances:
        print(f"  {feat:<22} {imp:>12.4f}")

    # Regenerate the manuscript figure from the corrected fold-local model.
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    ax = axes[0]
    for held_out, n_test, auc, fpr, tpr in fold_curves:
        ax.step(fpr, tpr, where='post', linewidth=2,
                label=f'{held_out} (AUC={auc:.2f}, n={n_test})')
    ax.plot([0, 1], [0, 1], linestyle='--', color='0.55', label='random')
    ax.set(
        xlabel='False positive rate',
        ylabel='True positive rate',
        title=('(a) ROC per held-out graph '
               f'(mean AUC = {np.nanmean(results["logreg"]):.3f})'),
    )
    ax.grid(alpha=0.25)
    ax.legend(loc='lower right', fontsize=9)

    ax = axes[1]
    importance_features = [feature for feature, _ in importances][::-1]
    importance_values = [importance for _, importance in importances][::-1]
    ax.barh(importance_features, importance_values, color='#4c78a8')
    ax.set(
        xlabel='Random forest feature importance',
        title='(b) Feature importance (Gini, trained on all 6 graphs)',
    )
    ax.grid(axis='x', alpha=0.25)
    fig.tight_layout()
    figure_dir = Path(__file__).resolve().parent.parent.parent / 'paper' / 'figures'
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / 'dlg_core_asset_prediction.pdf', bbox_inches='tight')
    fig.savefig(figure_dir / 'dlg_core_asset_prediction.png', dpi=200,
                bbox_inches='tight')
    plt.close(fig)

    lr_ttest = ttest_1samp(results['logreg'], popmean=0.5)
    rf_ttest = ttest_1samp(results['rf'], popmean=0.5)
    hardening = {
        'experiment_7_hardening': {
            'preprocessing': {
                'logistic_regression': 'StandardScaler fitted within each training fold',
                'random_forest': 'unscaled features',
            },
            'shared_core_ids': shared_core_ids,
            'n_shared': len(shared_core_ids),
            'fold_results_with_bootstrap': hardening_folds,
            'lr_mean_auc': float(np.nanmean(results['logreg'])),
            'lr_std_auc': float(np.nanstd(results['logreg'])),
            'rf_mean_auc': float(np.nanmean(results['rf'])),
            'rf_std_auc': float(np.nanstd(results['rf'])),
            'lr_t_vs_chance': float(lr_ttest.statistic),
            'lr_p_vs_chance': float(lr_ttest.pvalue),
            'rf_t_vs_chance': float(rf_ttest.statistic),
            'rf_p_vs_chance': float(rf_ttest.pvalue),
            'sensitivity_excl_shared_ids': sensitivity_results,
            'sensitivity_mean_auc': float(np.nanmean([
                fold['lr_auc_filtered'] for fold in sensitivity_results
            ])),
        },
    }
    with open(art_dir / 'exp7_hardening.json', 'w') as f:
        json.dump(hardening, f, indent=2)

    # Save outputs
    tables.to_csv(art_dir / 'dlg_node_features_tables.csv', index=False)
    all_df.to_csv(art_dir / 'dlg_node_features_all.csv', index=False)
    summary = {
        'experiment': '7_dlg_core_asset_prediction',
        'n_graphs': 6,
        'n_data_tables': int(len(tables)),
        'n_core_labels': int(tables['is_core'].sum()),
        'class_balance': float(tables['is_core'].mean()),
        'preprocessing': {
            'logistic_regression': 'StandardScaler fitted within each training fold',
            'random_forest': 'unscaled features',
        },
        'per_feature_auc': {k: float(v) for k, v in feature_aucs.items()},
        'leave_one_out_results': {
            'logreg_mean_auc': float(np.nanmean(results['logreg'])),
            'logreg_std_auc': float(np.nanstd(results['logreg'])),
            'rf_mean_auc': float(np.nanmean(results['rf'])),
            'rf_std_auc': float(np.nanstd(results['rf'])),
            'outdeg_mean_auc': float(np.nanmean(results['baseline_outdeg'])),
            'outdeg_std_auc': float(np.nanstd(results['baseline_outdeg'])),
            'random_mean_auc': float(np.nanmean(results['baseline_random'])),
            'random_std_auc': float(np.nanstd(results['baseline_random'])),
        },
        'fold_details': fold_details,
        'feature_importance': {f: float(i) for f, i in importances},
    }
    with open(art_dir / 'dlg_core_asset_prediction_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved to {art_dir}/")


if __name__ == '__main__':
    main()
