"""Clone and extract a worklist of repositories in parallel.

Reads a JSON worklist of {project_id, clone_url, [fixed_model_paths]} and, for
each entry, clones into the scratch clone directory then runs the extractor.
One repository failing never stops the run; every failure is recorded with its
reason in the per-project result JSON and in run_log.jsonl.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(REPO_ROOT, 'src')


def clone(url, dest, timeout=1800):
    if os.path.isdir(os.path.join(dest, '.git')):
        return True, 'already present'
    tmp = dest + '.partial'
    shutil.rmtree(tmp, ignore_errors=True)
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='echo')
    try:
        p = subprocess.run(
            ['git', 'clone', '--quiet', '--single-branch', '--no-tags', url, tmp],
            capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f'clone timed out after {timeout}s'
    if p.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, 'clone failed: ' + (p.stderr.strip().splitlines() or [''])[-1][:200]
    subprocess.run(['git', 'remote', 'set-head', 'origin', '-a'], cwd=tmp,
                   capture_output=True)
    os.replace(tmp, dest)
    return True, 'cloned'


def extract(project_id, repo_dir, url, out_dir, window_days, fixed_paths,
            timeout=3600, graph_only=False):
    cmd = [sys.executable, os.path.join(HERE, 'dbt_lineage_corpus.py'),
           '--repo', repo_dir, '--project-id', project_id, '--repo-url', url,
           '--out-dir', out_dir, '--window-days', str(window_days)]
    if graph_only:
        cmd.append('--graph-only')
    if fixed_paths:
        cmd.append('--fixed-model-paths')
        cmd.extend(fixed_paths)
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONHASHSEED='0',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env)
    except subprocess.TimeoutExpired:
        return False, f'extraction timed out after {timeout}s'
    if p.returncode != 0:
        return False, 'extractor crashed: ' + (p.stderr.strip().splitlines()
                                               or [''])[-1][:300]
    return True, 'ok'


def handle(job, clones, out_dir, window_days, graph_only=False):
    pid = job['project_id']
    url = job['clone_url']
    dest = os.path.join(clones, pid)
    rec = {'project_id': pid, 'clone_url': url,
           'started': datetime.utcnow().isoformat(timespec='seconds') + 'Z'}
    t0 = time.time()
    ok, msg = clone(url, dest)
    rec['clone_status'] = msg
    if not ok:
        rec['stage'] = 'clone'
        rec['status'] = 'failed'
        rec['error'] = msg
        rec['seconds'] = round(time.time() - t0, 1)
        return rec
    ok, msg = extract(pid, dest, url, out_dir, window_days,
                      job.get('fixed_model_paths'), graph_only=graph_only)
    rec['stage'] = 'extract'
    if not ok:
        rec['status'] = 'failed'
        rec['error'] = msg
    else:
        rpath = os.path.join(out_dir, f'{pid}.json')
        try:
            r = json.load(open(rpath))
            rec['status'] = r.get('status')
            rec['error'] = r.get('error')
            rec['n_snapshots'] = r.get('n_snapshots')
            rec['history_start'] = r.get('history_start')
            rec['history_end'] = r.get('history_end')
        except Exception as e:
            rec['status'] = 'failed'
            rec['error'] = f'result unreadable: {e}'
    rec['seconds'] = round(time.time() - t0, 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--worklist', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--workers', type=int, default=5)
    ap.add_argument('--window-days', type=int, default=30)
    ap.add_argument('--clones', required=True,
                    help='scratch directory to clone into, keep it out of the repo')
    ap.add_argument('--graph-only', action='store_true',
                    help='record graph size and connectivity only, skip D1-D4')
    a = ap.parse_args()

    os.makedirs(a.clones, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    jobs = json.load(open(a.worklist))
    done = set()
    if os.path.exists(a.log):
        with open(a.log) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get('status') in ('success', 'partial'):
                        done.add(r['project_id'])
                except json.JSONDecodeError:
                    pass
    jobs = [j for j in jobs if j['project_id'] not in done]
    print(f'{len(jobs)} jobs, {a.workers} workers', flush=True)

    logf = open(a.log, 'a')
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(handle, j, a.clones, a.out_dir, a.window_days,
                          a.graph_only): j for j in jobs}
        for i, fut in enumerate(as_completed(futs)):
            j = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {'project_id': j['project_id'], 'status': 'failed',
                       'error': f'orchestrator: {type(e).__name__}: {e}'}
            logf.write(json.dumps(rec) + '\n')
            logf.flush()
            print(f"[{i+1}/{len(jobs)}] {rec['project_id']}: {rec.get('status')} "
                  f"snapshots={rec.get('n_snapshots')} {rec.get('error') or ''}",
                  flush=True)
    logf.close()


if __name__ == '__main__':
    sys.exit(main())
