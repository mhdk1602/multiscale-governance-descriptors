"""Harvest the candidate population of public dbt projects from GitHub.

Three strata, unioned and deduplicated:
  S1  curated list  (InfuseAI/awesome-public-dbt-projects)
  S2  topic-tagged repo search, partitioned by star ranges to beat the 1000 cap
  S3  code search for dbt_project.yml, partitioned by repo size

Writes frame/candidates.json with provenance (which strata found each repo).
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict

import argparse

HERE = os.path.dirname(os.path.abspath(__file__))


def gh_api(path, retries=4):
    for attempt in range(retries):
        p = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                return None
        err = p.stderr.lower()
        if 'rate limit' in err or 'abuse' in err or '403' in err:
            time.sleep(20 * (attempt + 1))
            continue
        if '422' in err or '404' in err:
            return None
        time.sleep(3)
    return None


def search_repos(q, pages=10):
    """Enumerate a repo search query, up to pages*100 results."""
    out = []
    for page in range(1, pages + 1):
        url = ('search/repositories?q=' + urllib.parse.quote(q) +
               f'&per_page=100&page={page}&sort=updated&order=desc')
        r = gh_api(url)
        if not r or not r.get('items'):
            break
        out.extend(r['items'])
        if len(r['items']) < 100:
            break
        time.sleep(2)
    return out


def search_code(q, pages=10):
    out = []
    for page in range(1, pages + 1):
        url = 'search/code?q=' + urllib.parse.quote(q) + f'&per_page=100&page={page}'
        r = gh_api(url)
        if not r or not r.get('items'):
            break
        out.extend(r['items'])
        if len(r['items']) < 100:
            break
        time.sleep(3)
    return out


CURATED = [
    ('dbt-labs/jaffle_shop', 'Jaffle Shop'),
    ('duneanalytics/spellbook', 'Spellbook'),
    ('davidgasquez/filecoin-data-portal', 'Filecoin Data'),
    ('flyanakin/CountMoney', 'CountMoney'),
    ('bgarcevic/danish-democracy-data', 'Danish Parliament Data'),
    ('g0v/tw_campaign_finance', 'Taiwan Campaign Finance'),
    ('dagster-io/mdsfest-opensource-mds', 'Bird Data'),
    ('davidgasquez/datadex', 'Datadex'),
    ('matsonj/nba-monte-carlo', 'NBA Data'),
    ('GITLAB:gitlab-data/analytics', 'GitLab Data Team'),
    ('Levers-Labs/SOMA-B2B-SaaS', 'SOMA'),
    ('mattermost/mattermost-data-warehouse', 'Mattermost'),
    ('FlipsideCrypto/sql_models', 'Flipside'),
    ('danthelion/twitter-trending', 'Twitter Trending'),
    ('dagster-io/fake-star-detector', 'Fake Star Detector'),
    ('zsvoboda/ngods-stocks', 'ngods stock market demo'),
    ('datawaves-xyz/dbt_datawaves_wallet_labels', 'dbt_datawaves_wallet_labels'),
    ('cal-itp/data-infra', 'Cal-ITP'),
    ('cagov/data-infrastructure', 'CalData'),
    ('dagster-io/dagster-open-platform', 'Dagster Open Platform'),
]

STAR_BANDS = ['>=1000', '300..999', '100..299', '40..99', '20..39',
              '10..19', '5..9', '3..4', '2', '1']
TOPICS = ['dbt', 'dbt-core', 'dbt-project', 'analytics-engineering', 'dbt-models']
SIZE_BANDS = ['>50000', '20000..50000', '10000..19999', '5000..9999',
              '2000..4999', '1000..1999', '500..999', '200..499',
              '100..199', '50..99', '20..49', '<20']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', required=True,
                    help='scratch directory for the frame files')
    a = ap.parse_args()
    global FRAME
    FRAME = a.out_dir
    os.makedirs(FRAME, exist_ok=True)

    found = {}          # full_name -> record
    provenance = defaultdict(set)

    for fn, label in CURATED:
        key = fn
        found[key] = {'full_name': fn, 'curated_label': label}
        provenance[key].add('S1_curated')

    print('S2: topic-tagged repo search', flush=True)
    for topic in TOPICS:
        for band in STAR_BANDS:
            q = f'topic:{topic} stars:{band}'
            items = search_repos(q, pages=10)
            for it in items:
                key = it['full_name']
                found.setdefault(key, {}).update({
                    'full_name': key,
                    'stars': it.get('stargazers_count'),
                    'size_kb': it.get('size'),
                    'created_at': it.get('created_at'),
                    'pushed_at': it.get('pushed_at'),
                    'fork': it.get('fork'),
                    'archived': it.get('archived'),
                    'description': (it.get('description') or '')[:200],
                    'default_branch': it.get('default_branch'),
                    'clone_url': it.get('clone_url'),
                    'license': (it.get('license') or {}).get('spdx_id'),
                })
                provenance[key].add(f'S2_topic_{topic}')
            print(f'  {q}: {len(items)} (running union {len(found)})', flush=True)

    print('S3: code search for dbt_project.yml', flush=True)
    for band in SIZE_BANDS:
        q = f'filename:dbt_project.yml size:{band}' if band.startswith(('>', '<')) \
            else f'filename:dbt_project.yml size:{band}'
        items = search_code(q, pages=10)
        for it in items:
            repo = it.get('repository') or {}
            key = repo.get('full_name')
            if not key:
                continue
            rec = found.setdefault(key, {'full_name': key})
            rec.setdefault('dbt_project_paths', [])
            if it.get('path') not in rec['dbt_project_paths']:
                rec['dbt_project_paths'].append(it.get('path'))
            provenance[key].add('S3_code')
        print(f'  {q}: {len(items)} (running union {len(found)})', flush=True)

    for k in found:
        found[k]['strata'] = sorted(provenance[k])

    with open(os.path.join(FRAME, 'candidates.json'), 'w') as f:
        json.dump(list(found.values()), f, indent=1)
    print(f'\nTotal candidate population: {len(found)}')
    by_s = defaultdict(int)
    for k in found:
        for s in provenance[k]:
            by_s[s.split("_")[0]] += 1
    print(dict(by_s))


if __name__ == '__main__':
    main()
