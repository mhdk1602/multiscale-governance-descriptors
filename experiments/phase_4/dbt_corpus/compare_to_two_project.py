"""Compare the expanded corpus against the two-project release.

Every claim the two-project artifacts make about growth, contraction, drift rate
and descriptor distribution is recomputed on the expanded corpus and printed
side by side, so a claim that does not survive is visible rather than inferred.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
DESCRIPTORS = ['N', 'M', 'D1_csi', 'D1_n_comm', 'D2_max_gini', 'D3_alg_conn',
               'D3_norm_gap', 'D3_fiedler_bim', 'D4_cycle_rank_norm']


def q(s, p):
    return float(np.nanpercentile(s.dropna().astype(float), p)) if len(s.dropna()) else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', required=True)
    a = ap.parse_args()

    snaps = pd.read_csv(os.path.join(a.release, 'snapshots.csv'))
    idx = pd.read_csv(os.path.join(a.release, 'corpus_index.csv'))
    drift = pd.read_csv(os.path.join(a.release, 'drift_events.csv'))

    print('=' * 78)
    print('CORPUS SIZE')
    print('=' * 78)
    print(f'  projects            2  ->  {len(idx)}')
    print(f'  snapshots         106  ->  {len(snaps)}')
    cum = idx['span_years'].sum()
    print(f'  cumulative years  9.05 ->  {cum:.1f}')
    print(f'  window start   2020-01-13 ->  {idx["date_start"].min()}')
    print(f'  window end     2026-05-08 ->  {idx["date_end"].max()}')

    print()
    print('=' * 78)
    print('CLAIM 1  growth. The two-project release reports 8.53x and 14.69x node')
    print('         growth, which reads as "dbt lineage graphs grow steeply".')
    print('=' * 78)
    g = idx['node_growth_multiple'].astype(float).dropna()
    gv = idx['node_growth_from_first_viable'].astype(float).dropna()
    print(f'  n projects with a growth multiple : {len(g)}')
    print(f'  min {g.min():.2f}  p25 {q(g,25):.2f}  median {g.median():.2f}  '
          f'p75 {q(g,75):.2f}  max {g.max():.2f}')
    print(f'  shrank or flat (<= 1.0x)          : {(g <= 1.0).sum()} '
          f'({100*(g<=1.0).mean():.0f}%)')
    print(f'  grew more than 5x                 : {(g > 5).sum()} '
          f'({100*(g>5).mean():.0f}%)')
    print(f'  both original projects sit at the {100*(g < 8.53).mean():.0f}th and '
          f'{100*(g < 14.69).mean():.0f}th percentile of the corpus')
    print('  measured from the first snapshot at or above the N>=10 inclusion floor,')
    print('  which removes the multiple a project gets just for starting empty:')
    print(f'    min {gv.min():.2f}  p25 {q(gv,25):.2f}  median {gv.median():.2f}  '
          f'p75 {q(gv,75):.2f}  max {gv.max():.2f}')
    print(f'    shrank or flat : {(gv <= 1.0).sum()} ({100*(gv<=1.0).mean():.0f}%)')

    print()
    print('=' * 78)
    print('CLAIM 2  contraction. The release reports Cal-ITP 0% and Mattermost')
    print('         21.9% net contraction from peak.')
    print('=' * 78)
    c = idx['net_contraction_from_peak_pct'].astype(float).dropna()
    print(f'  min {c.min():.1f}  median {c.median():.1f}  p75 {q(c,75):.1f}  '
          f'max {c.max():.1f}')
    print(f'  no contraction at all (0%)        : {(c == 0).sum()} '
          f'({100*(c==0).mean():.0f}%)')
    print(f'  contracted more than 20% off peak : {(c > 20).sum()} '
          f'({100*(c>20).mean():.0f}%)')

    print()
    print('=' * 78)
    print('CLAIM 3  drift rate. 44 events over 106 snapshots is 0.415 per snapshot.')
    print('=' * 78)
    rate = len(drift) / len(snaps) if len(snaps) else 0
    print(f'  events {len(drift)} over {len(snaps)} snapshots = {rate:.3f} per snapshot')
    print('  by descriptor:')
    for d, n in drift['descriptor'].value_counts().items():
        print(f'    {d:22s} {n:5d}  ({100*n/len(drift):.0f}%)')
    per = drift.groupby('project_id').size().reindex(idx['project_id']).fillna(0)
    pr = (per / idx.set_index('project_id')['snapshots'].reindex(per.index))
    print(f'  per-project rate: min {pr.min():.3f}  median {pr.median():.3f}  '
          f'max {pr.max():.3f}')
    print(f'  projects with zero drift events  : {(per == 0).sum()} of {len(idx)}')

    print()
    print('=' * 78)
    print('CLAIM 4  layer composition. Not reported in the two-project release.')
    print('=' * 78)
    last = snaps.sort_values('date').groupby('project_id').tail(1)
    tot = last[['n_staging', 'n_intermediate', 'n_mart', 'n_unclassified']].sum(axis=1)
    for col in ['n_staging', 'n_intermediate', 'n_mart', 'n_unclassified']:
        share = (last[col] / tot.replace(0, np.nan)).dropna()
        print(f'  {col:17s} corpus share  median {share.median():.2f}  '
              f'p25 {q(share,25):.2f}  p75 {q(share,75):.2f}')
    unc = (last['n_unclassified'] / tot.replace(0, np.nan)).dropna()
    print(f'  projects where over half the models match no layer rule: '
          f'{(unc > 0.5).sum()} of {len(unc)}')

    print()
    print('=' * 78)
    print('CLAIM 5  descriptor distributions, against table3_summary_statistics.csv')
    print('=' * 78)
    t3p = os.path.join(REPO, 'paper', 'dolap_dataset', 'tables',
                       'table3_summary_statistics.csv')
    old = {}
    if os.path.exists(t3p):
        t3 = pd.read_csv(t3p)
        for _, r in t3.iterrows():
            old[r['field']] = r
    print('  D1_csi and D1_n_comm are marked because the n=106 column was')
    print('  produced under randomised node ordering and is not reproducible.')
    print('  The two columns are not comparable for those two rows.')
    print(f'  {"descriptor":22s} {"n=106 median":>13s} {"corpus median":>14s} '
          f'{"n=106 sd":>10s} {"corpus sd":>10s}')
    for d in DESCRIPTORS:
        s = pd.to_numeric(snaps[d], errors='coerce')
        o = old.get(d)
        om = float(o['median']) if o is not None and pd.notna(o['median']) else float('nan')
        osd = float(o['sd']) if o is not None and pd.notna(o['sd']) else float('nan')
        mark = ' *' if d.startswith('D1_') else ''
        print(f'  {d:22s} {om:13.4f} {s.median():14.4f} {osd:10.4f} '
              f'{s.std():10.4f}{mark}')

    print()
    print('=' * 78)
    print('TIERS. `core` is the subset where the descriptors describe most of N.')
    print('=' * 78)
    for tier, grp in idx.groupby('tier'):
        sub = snaps[snaps['project_id'].isin(grp['project_id'])]
        print(f'  {tier:9s} projects {len(grp):4d}  snapshots {len(sub):5d}  '
              f'median N {sub["N"].median():6.0f}  '
              f'median giant frac {sub["giant_component_frac"].median():.3f}  '
              f'median growth {grp["node_growth_from_first_viable"].median():.2f}x')

    print()
    print('=' * 78)
    print('CADENCE')
    print('=' * 78)
    print(f'  median snapshot gap, corpus : '
          f'{idx["median_snapshot_gap_days"].median():.0f} days '
          f'(two-project release: 29)')
    print(f'  max gap seen                : {idx["max_snapshot_gap_days"].max():.0f} days '
          f'(two-project release: 125)')
    print(f'  snapshots per project       : min {idx["snapshots"].min()}  '
          f'median {idx["snapshots"].median():.0f}  max {idx["snapshots"].max()}')
    print(f'  N per snapshot              : min {snaps["N"].min()}  '
          f'median {snaps["N"].median():.0f}  max {snaps["N"].max()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
