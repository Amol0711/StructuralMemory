"""Run frozen cases with explicit resource limits and per-component checkpoints.

Normal and optimized executions use identical frozen parameter files. Errors
are distinct from resource-limited unknowns. No outcome triggers resampling.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import importlib
import json
import os
import resource
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def worker(args):
    protocol=json.loads((ROOT/'protocol.json').read_text())
    limit=protocol['limits']['address_space_bytes_per_worker']
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    t=time.monotonic()
    try:
        case=json.loads(Path(args.case).read_text())
        module=importlib.import_module(args.backend)
        ans=module.solve(case,components=(args.component,))
        value=ans.get(args.component)
        if not ((isinstance(value,int) and not isinstance(value,bool) and value>=0) or value=='infinity'):
            raise RuntimeError('Invalid resolved horizon value')
        out={'status':'resolved','horizon':value,'result':ans}
    except MemoryError:
        out={'status':'unknown','reason':'address_space_limit'}
    except Exception:
        out={'status':'error','traceback':traceback.format_exc()}
    out.update(wall_seconds=time.monotonic()-t,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               optimized=bool(sys.flags.optimize))
    dump(Path(args.output),out)
    return 1 if out['status']=='error' else 0

def main(args):
    protocol=json.loads((ROOT/'protocol.json').read_text())
    manifest=json.loads((ROOT/'case_manifest.json').read_text())
    if sha(ROOT/'protocol.json')!=manifest['protocol_sha256']:raise RuntimeError('Protocol changed after freeze')
    records=manifest['cases']+manifest['controls']
    if args.select:
        selected=set(args.select)
        if not selected <= {r['case_id'] for r in records}:raise RuntimeError('Unknown selected case')
        records=[r for r in records if r['case_id'] in selected]
    if not args.output_dir:raise RuntimeError('--output-dir is required for reruns')
    dest=Path(args.output_dir).resolve()
    if dest==ROOT or ROOT in dest.parents:raise RuntimeError('Rerun output must be outside this frozen component')
    for r in records:
        if sha(ROOT/r['path'])!=r['sha256']:raise RuntimeError('Case changed after freeze')
    runroot=Path(args.output_dir).resolve()/args.mode
    if runroot.exists():raise RuntimeError('Run directory already exists; preserve original runs')
    runroot.mkdir(parents=True)
    code_hashes={name:sha(ROOT/'code'/name) for name in ['primary.py','independent.py','run_study.py']}
    start={'mode':args.mode,'protocol_sha256':sha(ROOT/'protocol.json'),
           'case_manifest_sha256':sha(ROOT/'case_manifest.json'),'code_sha256':code_hashes,
           'limits':protocol['limits'],'python':sys.version,'started_unix':time.time()}
    dump(runroot/'run_manifest.json',start)
    jobs=[(r,b,c) for r in records for b in ['primary','independent'] for c in ['full','growth']]
    seconds=protocol['limits']['wall_seconds_per_component_backend']
    def run(job):
        r,b,c=job;out=runroot/b/c/f"{r['case_id']}.json"
        out.parent.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable]+(['-O'] if args.mode=='optimized' else [])+[
            str(Path(__file__).resolve()),'--worker','--case',str(ROOT/r['path']),
            '--backend',b,'--component',c,'--output',str(out)]
        t=time.monotonic()
        try:
            done=subprocess.run(cmd,capture_output=True,text=True,timeout=seconds)
            if out.exists():
                result=json.loads(out.read_text())
                if done.returncode not in [0,1] or (done.returncode==1 and result['status']!='error'):
                    result={'status':'error','reason':'inconsistent_worker_exit','returncode':done.returncode}
            else:
                result={'status':'error','reason':'worker_without_result','returncode':done.returncode,
                        'stderr':done.stderr[-8000:]}
        except subprocess.TimeoutExpired:
            result={'status':'unknown','reason':'wall_time_limit','wall_seconds':time.monotonic()-t}
        result.update(case_id=r['case_id'],backend=b,component=c,mode=args.mode,
                      case_sha256=r['sha256'],backend_sha256=code_hashes[b+'.py'])
        dump(out,result)
        return {'case_id':r['case_id'],'backend':b,'component':c,'status':result['status'],
                'horizon':result.get('horizon'),'reason':result.get('reason'),
                'path':out.relative_to(runroot).as_posix(),'sha256':sha(out)}
    results=[]
    with ThreadPoolExecutor(max_workers=protocol['limits']['maximum_workers']) as pool:
        futures=[pool.submit(run,j) for j in jobs]
        for f in as_completed(futures):
            results.append(f.result())
            if len(results)%32==0:print(json.dumps({'mode':args.mode,'completed':len(results),'total':len(jobs)}),flush=True)
    for p in (ROOT/'code').glob('*.py'):
        if p.name in code_hashes and sha(p)!=code_hashes[p.name]:raise RuntimeError('Code changed during run: '+p.name)
    counts={s:sum(r['status']==s for r in results) for s in ['resolved','unknown','error']}
    summary={'mode':args.mode,'counts':counts,'results':sorted(results,key=lambda x:(x['case_id'],x['backend'],x['component']))}
    dump(runroot/'summary.json',summary)
    print(json.dumps({'mode':args.mode,'counts':counts}),flush=True)
    return 1 if counts['error'] else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['normal','optimized'],default='normal')
    p.add_argument('--output-dir');p.add_argument('--select',nargs='+');p.add_argument('--worker',action='store_true');p.add_argument('--case');p.add_argument('--backend');p.add_argument('--component');p.add_argument('--output')
    a=p.parse_args();sys.exit(worker(a) if a.worker else main(a))
