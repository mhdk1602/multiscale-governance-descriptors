"""Screen pass A: repository metadata for the whole candidate population.

One batched GraphQL request per 40 repositories returns stars, disk usage,
creation and push dates, fork and archive flags, the default branch, its HEAD
SHA and its total commit count. Cheap enough to run on everything, which matters
because the population is several thousand repositories and most of them are
tutorials.

No inclusion rule is applied here. Thresholds are chosen afterwards, from the
distributions this pass measures.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

import argparse

HERE = os.path.dirname(os.path.abspath(__file__))

GQL_BATCH = """
query {
%s
}
fragment R on Repository {
  nameWithOwner url description stargazerCount diskUsage createdAt pushedAt
  isFork isArchived isEmpty
  licenseInfo { spdxId }
  primaryLanguage { name }
  defaultBranchRef {
    name
    target { ... on Commit { oid committedDate history { totalCount } } }
  }
}
"""


def gh_graphql(query):
    for attempt in range(4):
        p = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={query}'],
                           capture_output=True, text=True)
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                return None
        if 'rate limit' in p.stderr.lower():
            time.sleep(30 * (attempt + 1))
            continue
        # partial data with errors still comes back on stdout
        if p.stdout.strip().startswith('{'):
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                pass
        time.sleep(3)
    return None


def pass_a(names):
    """Batched GraphQL metadata for every candidate."""
    out = {}
    B = 40
    for i in range(0, len(names), B):
        chunk = names[i:i + B]
        aliases = []
        for j, fn in enumerate(chunk):
            owner, _, name = fn.partition('/')
            aliases.append(f'  r{j}: repository(owner: "{owner}", name: "{name}") '
                           f'{{ ...R }}')
        q = GQL_BATCH % '\n'.join(aliases)
        r = gh_graphql(q)
        if not r:
            print(f'  batch {i} failed', flush=True)
            continue
        data = r.get('data') or {}
        for j, fn in enumerate(chunk):
            node = data.get(f'r{j}')
            if not node:
                out[fn] = {'full_name': fn, 'screen_a': 'unavailable'}
                continue
            dbr = node.get('defaultBranchRef') or {}
            tgt = dbr.get('target') or {}
            out[fn] = {
                'full_name': node.get('nameWithOwner') or fn,
                'url': node.get('url'),
                'description': (node.get('description') or '')[:200],
                'stars': node.get('stargazerCount'),
                'disk_kb': node.get('diskUsage'),
                'created_at': node.get('createdAt'),
                'pushed_at': node.get('pushedAt'),
                'is_fork': node.get('isFork'),
                'is_archived': node.get('isArchived'),
                'is_empty': node.get('isEmpty'),
                'license': (node.get('licenseInfo') or {}).get('spdxId'),
                'language': (node.get('primaryLanguage') or {}).get('name'),
                'default_branch': dbr.get('name'),
                'head_sha': tgt.get('oid'),
                'head_date': tgt.get('committedDate'),
                'total_commits': ((tgt.get('history') or {}).get('totalCount')),
                'screen_a': 'ok',
            }
        print(f'  pass A {min(i+B, len(names))}/{len(names)}', flush=True)
        time.sleep(0.4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frame', required=True)
    a = ap.parse_args()
    cands = json.load(open(os.path.join(a.frame, 'candidates.json')))
    names = sorted({c['full_name'] for c in cands
                    if not c['full_name'].startswith('GITLAB:')})
    print(f'candidates: {len(names)}')
    meta = pass_a(names)
    out = os.path.join(a.frame, 'screen_a.json')
    json.dump(meta, open(out, 'w'), indent=1)
    ok = sum(1 for v in meta.values() if v.get('screen_a') == 'ok')
    print(f'resolved {ok} of {len(names)}, wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
