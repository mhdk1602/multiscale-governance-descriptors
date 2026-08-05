"""Pass B of the screen: one recursive tree call per candidate, run in parallel.

Everything the pre-clone screen needs comes out of a single tree listing at the
default branch. Locating dbt_project.yml is exact. Model paths are inferred from
the tree rather than by fetching and parsing each yml, because the default
`models` layout covers the overwhelming majority and a wrong guess here only
affects which repositories get cloned, never what the extractor measures. The
extractor resolves model-paths properly from each commit's own config.
"""
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import argparse

HERE = os.path.dirname(os.path.abspath(__file__))

VENDOR = ('dbt_modules/', 'dbt_packages/', 'target/', 'integration_tests/',
          'dbt_internal_packages/', 'node_modules/')
_lock = threading.Lock()


def gh_rest(path):
    for attempt in range(3):
        p = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
        if p.returncode == 0:
            return p.stdout
        low = p.stderr.lower()
        if '404' in low or '409' in low or '451' in low or '403' in low and 'rate' not in low:
            return None
        if 'rate limit' in low or 'secondary' in low:
            time.sleep(20 * (attempt + 1))
            continue
        time.sleep(1.5)
    return None


def vendored(p):
    q = p if p.endswith('/') else p + '/'
    return any(m in q for m in VENDOR)


def screen_one(rec):
    fn = rec['full_name']
    sha = rec.get('head_sha')
    if not sha:
        rec['screen_b'] = 'no default branch'
        return rec
    body = gh_rest(f'repos/{fn}/git/trees/{sha}?recursive=1')
    if not body:
        rec['screen_b'] = 'tree unavailable'
        return rec
    try:
        tree = json.loads(body)
    except json.JSONDecodeError:
        rec['screen_b'] = 'tree unparseable'
        return rec
    rec['tree_truncated'] = bool(tree.get('truncated'))
    paths = [e['path'] for e in tree.get('tree', []) if e.get('type') == 'blob']
    cfgs = [p for p in paths
            if p == 'dbt_project.yml' or p.endswith('/dbt_project.yml')]
    cfgs = [c for c in cfgs if not vendored(c)]
    rec['n_dbt_projects'] = len(cfgs)
    rec['dbt_project_configs'] = cfgs[:12]
    if not cfgs:
        rec['screen_b'] = 'no dbt_project.yml'
        rec['n_model_sql'] = 0
        return rec

    bases = {c[:-len('dbt_project.yml')].rstrip('/') for c in cfgs}
    sql = set()
    for b in bases:
        prefix = f'{b}/models/' if b else 'models/'
        for p in paths:
            if p.startswith(prefix) and p.endswith('.sql') and not vendored(p) \
                    and 'macros' not in p and '/tests/' not in p \
                    and '/snapshots/' not in p:
                sql.add(p)
    rec['n_model_sql'] = len(sql)
    if not sql:
        # non-default model-paths, count any .sql that is not obviously support code
        alt = {p for p in paths if p.endswith('.sql') and not vendored(p)
               and 'macros' not in p and '/tests/' not in p
               and '/snapshots/' not in p}
        rec['n_model_sql_any_sql'] = len(alt)
    rec['screen_b'] = 'ok'
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frame', required=True)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    FRAME = a.frame
    meta = json.load(open(os.path.join(FRAME, 'screen_a.json')))
    cands = json.load(open(os.path.join(FRAME, 'candidates.json')))
    strata = {c['full_name']: c.get('strata', []) for c in cands}
    for fn, r in meta.items():
        r['strata'] = strata.get(fn, [])

    def worth_b(r):
        if r.get('screen_a') != 'ok' or r.get('is_empty') or r.get('is_fork'):
            return False
        if 'S1_curated' in r.get('strata', []):
            return True
        return (r.get('total_commits') or 0) >= 40

    todo = [r for r in meta.values() if worth_b(r)]
    print(f'pass B queue: {len(todo)}', flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(screen_one, r): r for r in todo}
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                futs[fut]['screen_b'] = f'error {type(e).__name__}'
            done += 1
            if done % 100 == 0:
                print(f'  {done}/{len(todo)}', flush=True)
    out = os.path.join(FRAME, 'screened.json')
    json.dump(list(meta.values()), open(out, 'w'), indent=1)
    ok = sum(1 for r in meta.values() if r.get('screen_b') == 'ok')
    with_dbt = sum(1 for r in meta.values() if (r.get('n_dbt_projects') or 0) > 0)
    print(f'screened ok: {ok}, with a dbt_project.yml: {with_dbt}')
    print('wrote', out)


if __name__ == '__main__':
    sys.exit(main())
