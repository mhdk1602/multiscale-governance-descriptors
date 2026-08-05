"""Does documentation coverage decay as a dbt project grows?

The two-project release showed documentation falling monotonically with size,
Cal-ITP from 0.987 to 0.658 and Mattermost from 1.000 to 0.689. Two projects
cannot distinguish a general tendency from two projects that happen to do the
same thing, and there was no counterexample available to it and no error bar.

This fits one relationship per project between `doc_rate` and node count over
that project's own series, and reports the distribution of the results. Working
within project removes the between-project confound entirely: a project that is
both large and badly documented contributes nothing unless *its own* coverage
moved as *it* grew.

Two statistics per project, because they answer different questions. Spearman
rho is the direction and monotonicity, and it is robust to the fact that N grows
roughly geometrically. The OLS slope of `doc_rate` on log2(N) is the magnitude,
readable as coverage lost per doubling of the project.

    python experiments/phase_4/dbt_corpus/documentation_decay.py \\
        --release artifacts/phase_4_corpus
"""
import argparse
import csv
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

try:
    from scipy import stats as sps
except ImportError:  # pragma: no cover
    sps = None

MIN_POINTS = 8
MIN_DISTINCT_N = 4


def spearman(xs, ys):
    # A constant series has no defined correlation. scipy warns and returns nan,
    # and this repository has already shipped one result where a constant input
    # was read as the most significant row in a table, so the caller counts
    # these separately rather than letting them vanish into a dropped nan.
    if len(set(ys)) < 2 or len(set(xs)) < 2:
        return float('nan'), float('nan')
    if sps is not None:
        r = sps.spearmanr(xs, ys)
        return float(r.statistic), float(r.pvalue)

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = rank(xs), rank(ys)
    mx, my = st.fmean(rx), st.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx)
                    * sum((b - my) ** 2 for b in ry))
    return (num / den if den else float('nan')), float('nan')


def ols_slope(xs, ys):
    mx, my = st.fmean(xs), st.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return float('nan')
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    idx = {r['project_id']: r for r in
           csv.DictReader(open(os.path.join(a.release, 'corpus_index.csv')))}
    series = defaultdict(list)
    for s in csv.DictReader(open(os.path.join(a.release, 'snapshots.csv'))):
        try:
            n = int(s['N'])
            dr = float(s['doc_rate']) if s['doc_rate'] not in ('', 'None') else None
            tr = float(s['test_rate']) if s['test_rate'] not in ('', 'None') else None
        except (ValueError, KeyError):
            continue
        if dr is None or n <= 0:
            continue
        series[s['project_id']].append((s['date'], n, dr, tr))

    results = []
    skipped = 0
    for pid, rows in series.items():
        rows.sort()
        ns = [r[1] for r in rows]
        if len(rows) < MIN_POINTS or len(set(ns)) < MIN_DISTINCT_N:
            skipped += 1
            continue
        logn = [math.log2(n) for n in ns]
        docs = [r[2] for r in rows]
        tests = [r[3] for r in rows if r[3] is not None]
        rho, p = spearman(ns, docs)
        rec = {
            'doc_rate_constant': len(set(docs)) < 2,
            'doc_rate_constant_value': (round(docs[0], 4)
                                        if len(set(docs)) < 2 else None),
            'project_id': pid,
            'composition': idx.get(pid, {}).get('composition'),
            'tier': idx.get(pid, {}).get('tier'),
            'n_points': len(rows),
            'n_first': ns[0], 'n_last': ns[-1],
            'doc_first': round(docs[0], 4), 'doc_last': round(docs[-1], 4),
            'doc_spearman_rho': round(rho, 4) if rho == rho else None,
            'doc_spearman_p': round(p, 6) if p == p else None,
            'doc_slope_per_doubling': round(ols_slope(logn, docs), 4),
        }
        if len(tests) == len(rows):
            trho, _tp = spearman(ns, tests)
            rec['test_spearman_rho'] = round(trho, 4) if trho == trho else None
            rec['test_slope_per_doubling'] = round(ols_slope(logn, tests), 4)
        results.append(rec)

    const = [r for r in results if r['doc_rate_constant']]
    print(f'projects with a usable series: {len(results)}   '
          f'(skipped {skipped} with under {MIN_POINTS} points or under '
          f'{MIN_DISTINCT_N} distinct sizes)')
    print(f'of those, {len(const)} hold doc_rate constant across their whole '
          f'series, so no correlation is defined for them')
    if const:
        vals = sorted(r['doc_rate_constant_value'] for r in const)
        at_zero = sum(1 for v in vals if v == 0.0)
        at_one = sum(1 for v in vals if v == 1.0)
        print(f'  constant at 0.0: {at_zero}   constant at 1.0: {at_one}   '
              f'constant elsewhere: {len(vals) - at_zero - at_one}')

    def summarise(label, recs, key='doc_spearman_rho'):
        v = [r[key] for r in recs if r.get(key) is not None]
        if not v:
            print(f'  {label:26s} no usable projects')
            return None
        neg = sum(1 for x in v if x < 0)
        strong_neg = sum(1 for x in v if x <= -0.5)
        pos = sum(1 for x in v if x > 0)
        strong_pos = sum(1 for x in v if x >= 0.5)
        print(f'  {label:26s} n={len(v):3d}  median rho {st.median(v):+.3f}  '
              f'negative {neg:3d} ({100 * neg / len(v):3.0f}%)  '
              f'rho<=-0.5 {strong_neg:3d} ({100 * strong_neg / len(v):3.0f}%)  '
              f'positive {pos:3d}  rho>=+0.5 {strong_pos:3d}')
        return {'n': len(v), 'median_rho': round(st.median(v), 4),
                'pct_negative': round(100 * neg / len(v), 1),
                'pct_rho_le_minus_0_5': round(100 * strong_neg / len(v), 1),
                'pct_rho_ge_plus_0_5': round(100 * strong_pos / len(v), 1)}

    print()
    print('doc_rate against node count, within project, Spearman rho')
    out = {'all': summarise('all projects', results)}
    for comp in sorted({r['composition'] for r in results if r['composition']}):
        out[comp] = summarise(f'composition = {comp}',
                              [r for r in results if r['composition'] == comp])
    for tier in sorted({r['tier'] for r in results if r['tier']}):
        out['tier_' + tier] = summarise(f'tier = {tier}',
                                        [r for r in results if r['tier'] == tier])

    print()
    print('magnitude, OLS slope of doc_rate on log2(N), coverage per doubling')
    sl = [r['doc_slope_per_doubling'] for r in results
          if r['doc_slope_per_doubling'] == r['doc_slope_per_doubling']]
    if sl:
        sl.sort()
        print(f'  median {st.median(sl):+.4f}   p25 {sl[len(sl)//4]:+.4f}   '
              f'p75 {sl[3*len(sl)//4]:+.4f}   min {sl[0]:+.4f}   max {sl[-1]:+.4f}')
        out['slope_per_doubling'] = {
            'median': round(st.median(sl), 4), 'min': round(sl[0], 4),
            'max': round(sl[-1], 4)}

    print()
    print('the two anchor projects, which motivated the question')
    for pid in ('cal-itp__data-infra', 'mattermost__mattermost-data-warehouse'):
        r = next((x for x in results if x['project_id'] == pid), None)
        if r:
            print(f"  {pid[:44]:44s} doc {r['doc_first']:.3f} -> {r['doc_last']:.3f}  "
                  f"rho {r['doc_spearman_rho']:+.3f}  "
                  f"slope {r['doc_slope_per_doubling']:+.4f}/doubling")

    tv = [r.get('test_spearman_rho') for r in results
          if r.get('test_spearman_rho') is not None]
    if tv:
        print()
        print('test_rate against node count, same method')
        summarise('all projects', results, key='test_spearman_rho')

    payload = {'constant_doc_rate': {
        'n': len(const),
        'note': ('Spearman is undefined on a constant series. These projects '
                 'are counted here and excluded from the rho distribution '
                 'rather than contributing a nan.'),
    }, 'method': {
        'unit': 'one relationship per project over its own series',
        'min_points': MIN_POINTS, 'min_distinct_sizes': MIN_DISTINCT_N,
        'statistics': ['Spearman rho of doc_rate against N',
                       'OLS slope of doc_rate on log2(N)'],
        'why_within_project': ('a between-project correlation would confound '
                               'size with whoever happens to document well'),
    }, 'summary': out, 'per_project': results}
    path = a.out or os.path.join(a.release, 'documentation_decay.json')
    with open(path, 'w') as f:
        json.dump(payload, f, indent=1)
    print(f'\nwrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
