"""Label what kind of thing each corpus member is, and report the yield curve.

The corpus passes necessary conditions of the extraction method, which says
nothing about whether a repository is a production analytics estate or a dbt
package whose models are templates for somebody else's project. The research
questions presuppose estates, so the composition has to be visible rather than
assumed.

Two things were tried as classifiers and only one works.

Connectivity does not. `giant_component_frac` was the obvious candidate, since
an estate is connected by construction and a package is loose templates. On a
28-project hand-labelled sample the best single threshold reaches 0.643
accuracy. `fivetran/dbt_zendesk`, a package, has a giant component of 1.000,
higher than every estate in the sample, and `duneanalytics/spellbook`, an
estate, sits at 0.328. Fivetran's `_source` packages are staging-only and score
near zero while their downstream transform packages score near one, so what
connectivity separates is source packages from everything else, not packages
from estates.

What does work is `integration_tests/`, at 0.857 on the same sample and with no
circularity, since dbt packages ship an integration-test project and estates do
not. The repository-name rule reaches 1.000 but is circular on this sample,
because the labels were partly assigned from the names, so it is used only as a
supporting signal and the accuracy is reported with that caveat attached.

    python experiments/phase_4/dbt_corpus/classify_composition.py \\
        --release artifacts/phase_4_corpus --clones SCRATCH/clones
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

NAME_PACKAGE = re.compile(r'(^|[-_])dbt([-_]|$)|^dbt', re.IGNORECASE)
DOC_MARKERS = ('docs.getdbt.com', 'website', 'documentation')
DEMO_MARKERS = ('demo', 'tutorial', 'example', 'workshop', 'course', 'sample',
                'playground', 'zoomcamp', 'bootcamp')


def tree_at_head(clones, pid):
    p = os.path.join(clones, pid)
    if not os.path.isdir(os.path.join(p, '.git')):
        return []
    out = subprocess.run(['git', 'ls-tree', '-r', '--name-only', 'origin/HEAD'],
                         cwd=p, capture_output=True, text=True).stdout
    return out.splitlines()


def signals(clones, pid):
    paths = tree_at_head(clones, pid)
    repo = pid.split('__', 1)[-1].lower()
    owner = pid.split('__', 1)[0].lower()
    return {
        'has_integration_tests': any('integration_tests/' in x for x in paths),
        'consumes_packages': any(x.endswith('packages.yml') for x in paths),
        'name_looks_like_package': bool(NAME_PACKAGE.search(repo)),
        'name_looks_like_demo': any(m in repo or m in owner for m in DEMO_MARKERS),
        'name_looks_like_docs': any(m in repo for m in DOC_MARKERS),
        'tree_available': bool(paths),
    }


def classify(sig, row):
    """Ordered rules. First match wins, and the matched rule is recorded."""
    if sig['has_integration_tests']:
        return 'package', 'ships an integration_tests project'
    if sig['name_looks_like_docs']:
        return 'documentation', 'repository name indicates a docs site'
    if sig['name_looks_like_demo']:
        return 'demo', 'repository name indicates a demo or tutorial'
    if sig['name_looks_like_package']:
        return 'package', 'repository name matches the dbt package convention'
    return 'estate', 'no package, docs or demo signal'


def yield_curve(results_dir, min_nodes=10,
                floors=(3, 6, 9, 12, 18, 24, 36, 48)):
    """Corpus size against the snapshot floor, read from the raw extraction.

    Computing this from the built index would censor it, since the index only
    contains projects that already cleared the floor the release was built at.
    A reader who disagrees with the chosen floor should be able to read their
    own off the curve.
    """
    projects = []
    for fn in sorted(os.listdir(results_dir)):
        if not fn.endswith('.json'):
            continue
        r = json.load(open(os.path.join(results_dir, fn)))
        rows = r.get('snapshots') or []
        if not rows:
            continue
        projects.append({'n': len(rows),
                         'peak': max((x.get('N') or 0) for x in rows)})
    out = []
    for f in floors:
        keep = [p for p in projects if p['n'] >= f and p['peak'] >= min_nodes]
        peaks = sorted(p['peak'] for p in keep)
        out.append({
            'snapshot_floor': f,
            'projects': len(keep),
            'snapshots': sum(p['n'] for p in keep),
            'median_peak_nodes': peaks[len(peaks) // 2] if peaks else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release', required=True)
    ap.add_argument('--clones', required=True)
    ap.add_argument('--results', required=True,
                    help='per-project extraction JSON, for the uncensored '
                         'yield curve')
    ap.add_argument('--labels', default=None,
                    help='JSON of project_id -> hand label, to score the rules')
    a = ap.parse_args()

    idx_path = os.path.join(a.release, 'corpus_index.csv')
    rows = list(csv.DictReader(open(idx_path)))
    fields = list(rows[0].keys())

    with ThreadPoolExecutor(max_workers=12) as ex:
        sigs = list(ex.map(lambda r: signals(a.clones, r['project_id']), rows))

    for r, sig in zip(rows, sigs):
        comp, why = classify(sig, r)
        r['composition'] = comp
        r['composition_rule'] = why
        r['has_integration_tests'] = sig['has_integration_tests']
        r['consumes_packages'] = sig['consumes_packages']

    for extra in ('composition', 'composition_rule', 'has_integration_tests',
                  'consumes_packages'):
        if extra not in fields:
            fields.append(extra)
    with open(idx_path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    dist = Counter(r['composition'] for r in rows)
    print('composition of the corpus')
    for k, v in dist.most_common():
        print(f'  {k:14s} {v:4d}  ({100 * v / len(rows):.0f}%)')

    scored = None
    if a.labels and os.path.isfile(a.labels):
        labels = json.load(open(a.labels))
        by_id = {r['project_id']: r for r in rows}
        pairs = [(labels[k], by_id[k]['composition']) for k in labels if k in by_id]
        hit = sum(1 for t, p in pairs
                  if (t == 'estate') == (p == 'estate'))
        scored = {'n': len(pairs), 'accuracy_estate_vs_other': round(hit / len(pairs), 4)}
        print(f'\nagainst {len(pairs)} hand labels, estate versus everything else: '
              f'{hit}/{len(pairs)} = {hit / len(pairs):.3f}')

    curve = yield_curve(a.results)
    print('\nyield curve')
    print(f'  {"floor":>5s} {"projects":>8s} {"snapshots":>9s} {"med peak N":>10s}')
    for c in curve:
        print(f'  {c["snapshot_floor"]:>5d} {c["projects"]:>8d} {c["snapshots"]:>9d} '
              f'{str(c["median_peak_nodes"]):>10s}')

    out = {
        'composition_distribution': dict(dist),
        'classifier': {
            'rules_in_order': [
                'ships an integration_tests project -> package',
                'repository name indicates a docs site -> documentation',
                'repository name indicates a demo or tutorial -> demo',
                'repository name matches the dbt package convention -> package',
                'otherwise -> estate',
            ],
            'validation': scored,
            'caveat': ('The name rule is circular on the validation sample, '
                       'because the hand labels were partly assigned from the '
                       'names. The integration_tests rule is independent and '
                       'reaches 0.857 alone on the same sample.'),
            'rejected': {
                'giant_component_frac': (
                    'best single-threshold accuracy 0.643 on the same sample. '
                    'A package can be fully connected and an estate can be '
                    'sparse, so connectivity does not separate the classes.'),
            },
        },
        'yield_curve': curve,
    }
    path = os.path.join(a.release, 'composition_and_yield.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print(f'\nwrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
