"""Clone ahead of the extractors. Network-bound, so run it wide."""
import json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
CLONES = None
def clone(job):
    pid, url = job['project_id'], job['clone_url']
    dest=os.path.join(CLONES,pid)
    if os.path.isdir(os.path.join(dest,'.git')): return pid,'present'
    tmp=dest+'.prefetch'
    shutil.rmtree(tmp, ignore_errors=True)
    env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='echo')
    try:
        p=subprocess.run(['git','clone','--quiet','--single-branch','--no-tags',url,tmp],
                         capture_output=True,text=True,timeout=1800,env=env)
    except subprocess.TimeoutExpired:
        shutil.rmtree(tmp,ignore_errors=True); return pid,'timeout'
    if p.returncode!=0:
        shutil.rmtree(tmp,ignore_errors=True); return pid,'fail'
    subprocess.run(['git','remote','set-head','origin','-a'],cwd=tmp,capture_output=True)
    if os.path.isdir(os.path.join(dest,'.git')):
        shutil.rmtree(tmp,ignore_errors=True); return pid,'raced'
    try: os.replace(tmp,dest)
    except OSError: shutil.rmtree(tmp,ignore_errors=True); return pid,'raced'
    return pid,'cloned'
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--clones', required=True)
ap.add_argument('--workers', type=int, default=24)
ap.add_argument('worklists', nargs='+')
args=ap.parse_args()
CLONES=args.clones
os.makedirs(CLONES, exist_ok=True)
jobs=[]
for wl in args.worklists:
    jobs.extend(json.load(open(wl)))
todo=[j for j in jobs if not os.path.isdir(os.path.join(CLONES,j['project_id'],'.git'))]
print(f'{len(todo)} to prefetch of {len(jobs)}',flush=True)
n=0
with ThreadPoolExecutor(max_workers=args.workers) as ex:
    for fut in as_completed([ex.submit(clone,j) for j in todo]):
        pid,st=fut.result(); n+=1
        if n%25==0: print(f'  {n}/{len(todo)}',flush=True)
print('prefetch done')
