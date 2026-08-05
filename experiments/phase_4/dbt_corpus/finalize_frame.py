"""Write the final screening decision for every entry in the candidate population.

The screen was revised once during the run and this file records the revised
version, which is the one the corpus was built under.

The first version excluded a repository when HEAD carried no `dbt_project.yml`
or fewer than ten model SQL files. That is wrong for a longitudinal corpus.
`davidgasquez/filecoin-data-portal` has no `dbt_project.yml` at HEAD and still
yields 27 monthly snapshots, because the project used dbt for two years and then
stopped. A HEAD-only test is blind to exactly the adoption-and-abandonment
lifecycle the corpus is meant to contain.

So the HEAD observations are recorded but no longer exclude. What excludes is
only what makes a monthly series impossible in principle:

  P3  at least 40 commits on the default branch
  P4  at least 12 months between repository creation and last push
  P5  not a fork
  P6  metadata resolvable, repository not empty, default branch present

Everything clearing P3 to P6 is cloned and extracted. Membership in the corpus
is then decided from the extraction, not from the screen.
"""
import json
import os
import sys
from datetime import datetime

import argparse

HERE = os.path.dirname(os.path.abspath(__file__))

MIN_COMMITS = 40
MIN_MONTHS = 12.0


def months(a, b):
    try:
        da = datetime.fromisoformat((a or '').replace('Z', '+00:00'))
        db = datetime.fromisoformat((b or '').replace('Z', '+00:00'))
    except Exception:
        return 0.0
    return (db - da).days / 30.44


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frame', required=True)
    ap.add_argument('--worklist', default=None,
                    help='where to write the clone-and-extract worklist')
    a = ap.parse_args()
    FRAME = a.frame
    recs = json.load(open(os.path.join(FRAME, 'screened.json')))
    decisions, counts = [], {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    for r in recs:
        fn = r.get('full_name')
        m = months(r.get('created_at'), r.get('pushed_at'))
        d = {'project_id': fn.replace('/', '__'), 'full_name': fn,
             'url': r.get('url') or f'https://github.com/{fn}',
             'stars': r.get('stars'), 'license': r.get('license'),
             'strata': r.get('strata', []),
             'total_commits': r.get('total_commits'),
             'months_active': round(m, 1),
             'is_archived': r.get('is_archived'),
             'n_model_sql': r.get('n_model_sql'),
             'n_dbt_projects': r.get('n_dbt_projects'),
             'dbt_project_yml_at_head': (r.get('screen_b') == 'ok'),
             'created_at': r.get('created_at'), 'pushed_at': r.get('pushed_at')}

        if r.get('screen_a') != 'ok':
            d['screen'], d['reason'] = 'excluded', 'P6 repository metadata unavailable'
            bump('P6_metadata_unavailable')
        elif r.get('is_fork'):
            d['screen'], d['reason'] = 'excluded', 'P5 fork of another repository'
            bump('P5_fork')
        elif r.get('is_empty') or not r.get('head_sha'):
            d['screen'], d['reason'] = 'excluded', 'P6 empty or no default branch'
            bump('P6_empty')
        elif (r.get('total_commits') or 0) < MIN_COMMITS:
            d['screen'] = 'excluded'
            d['reason'] = (f'P3 {r.get("total_commits")} commits on the default '
                           f'branch, below {MIN_COMMITS}')
            bump('P3_too_few_commits')
        elif m < MIN_MONTHS:
            d['screen'] = 'excluded'
            d['reason'] = (f'P4 {m:.1f} months between creation and last push, '
                           f'below {MIN_MONTHS:.0f}')
            bump('P4_history_too_short')
        else:
            d['screen'], d['reason'] = 'passed', ''
            bump('passed')
        decisions.append(d)

    json.dump(decisions, open(os.path.join(FRAME, 'decisions.json'), 'w'), indent=1)
    worklist = [{'project_id': d['project_id'],
                 'clone_url': d['url'].rstrip('/') + '.git'}
                for d in decisions if d['screen'] == 'passed']
    out = a.worklist or os.path.join(FRAME, 'worklist.json')
    json.dump(worklist, open(out, 'w'), indent=1)
    print(f'worklist of {len(worklist)} repositories written to {out}')
    print(f'candidate population : {len(recs)}')
    for k in sorted(counts, key=lambda k: -counts[k]):
        print(f'  {k:32s} {counts[k]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
