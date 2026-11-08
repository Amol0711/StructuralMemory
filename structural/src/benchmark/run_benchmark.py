"""Freeze, run, or verify the capped benchmark.

No outcome-based selection. Official timings start only through --run after
--freeze has sealed all inputs and imported implementation sources.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,io,json,os,platform,statistics,subprocess,sys,time
from fixtures import instances,protocol,encode,METHODS,CAP_SECONDS,MEMORY_BYTES,REPETITIONS
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
FROZEN=ROOT/'data/benchmark'
DEFAULT=FROZEN
ALLOWED={'completed','unknown_timeout','unknown_memory_limit','unknown_memory_preflight'}
FIELDS=['instance','family','mode','method','status','completed_repetitions','full','growth','J_size','reachable_states','edges','decision_median_seconds','decision_min_seconds','decision_max_seconds','certified_total_median_seconds','parent_wall_median_seconds','matrix_median_seconds','core_median_seconds','certificate_generation_median_seconds','certificate_checking_median_seconds','peak_rss_median_bytes']

def require(ok,message):
    if not ok:raise RuntimeError(message)

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text())
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(encode(v));tmp.replace(p)

def source_hashes():
    names=['src/benchmark/fixtures.py','src/benchmark/worker.py','src/benchmark/run_benchmark.py','src/benchmark/verify_recorded.py','src/benchmark/test_protocol.py',
      'src/benchmark_core.py','src/reference.py','src/compact_memory/model.py',
      'src/compact_memory/solver.py','src/compact_memory/certificate_checker.py',
      'src/structural_frontend/__init__.py','src/structural_frontend/precheck.py','src/structural_frontend/certificate_checker.py']
    return {n:digest(ROOT/n) for n in names}

def jobs():
    answer=[]
    for item in instances():
        for method in METHODS:answer.append((item,'preprocessed',method))
    for item in instances():
        if item['family']=='refresh':
            for method in ('pair','antichain'):answer.append((item,'unpruned_stress',method))
    require(len(answer)==95,'Job count')
    return answer

def environment():
    cpu=Path('/proc/cpuinfo')
    return {'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
        'logical_cpu_count':os.cpu_count(),'cpu_model':next((l.split(':',1)[1].strip() for l in cpu.read_text().splitlines() if l.startswith('model name')),'unavailable') if cpu.exists() else 'unavailable',
        'shared_host':True,'cpu_isolated':False}

def freeze(out):
    out.mkdir(parents=True,exist_ok=True)
    require(not(out/'summary.json').exists(),'A run is already recorded; use a new output directory')
    record={'schema':'structural-memory.benchmark-freeze.v1','frozen_utc':stamp(),
      'protocol':protocol(),'source_sha256':source_hashes(),'inputs':[]}
    for item in instances():
        path=out/'inputs'/(item['name']+'.json')
        expected=encode(item['structure'])
        if path.exists():require(path.read_text()==expected,'Existing input differs from generator: '+item['name'])
        else:path.parent.mkdir(exist_ok=True,parents=True);path.write_text(expected)
        record['inputs'].append({k:v for k,v in item.items() if k!='structure'}|{'path':'inputs/'+path.name,'sha256':digest(path)})
    if (out/'protocol.json').exists():
        old=read(out/'protocol.json')
        require({k:v for k,v in old.items() if k!='frozen_utc'}=={k:v for k,v in record.items() if k!='frozen_utc'},'Frozen protocol/source mismatch; do not reseal after outcomes')
        print('Existing frozen protocol unchanged')
    else:dump(out/'protocol.json',record);print('Frozen 29 inputs and source hashes before timing')

def check_frozen(out):
    frozen=read(out/'protocol.json')
    require(frozen['protocol']==protocol(),'Protocol differs from preregistration')
    if out.resolve()==FROZEN.resolve():
        expected=read(ROOT/'recorded_execution_sources.json')['benchmark']
        require(frozen['source_sha256']==expected,'Historical execution-source record changed')
    else:
        require(frozen['source_sha256']==source_hashes(),'Imported implementation changed after freeze')
    require(len(frozen['inputs'])==29,'Frozen input inventory')
    for item,rec in zip(instances(),frozen['inputs']):
        require(item['name']==rec['name'] and item['metadata']==rec['metadata'] and item['family']==rec['family'],'Input metadata differs')
        path=out/rec['path']
        require(path.read_text()==encode(item['structure']) and digest(path)==rec['sha256'],'Frozen input changed')
    return frozen

def run_worker(item,mode,method,iteration,out,input_path=None):
    path=out/'raw'/f"{item['name']}__{mode}__{method}__{iteration}.json"
    require(not path.exists(),'Refusing to overwrite existing raw trial: '+path.name)
    path.parent.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,str(HERE/'worker.py'),'--input',str(input_path or out/'inputs'/(item['name']+'.json')),
      '--method',method,'--mode',mode,'--output',str(path)]
    started=stamp();t=time.perf_counter();timed_out=False
    try:process=subprocess.run(command,capture_output=True,text=True,timeout=CAP_SECONDS)
    except subprocess.TimeoutExpired:timed_out=True;process=None
    elapsed=time.perf_counter()-t
    r=read(path) if path.exists() else {'horizons':{'full':None,'growth':None},'certificates':[],'stages_seconds':{}}
    if timed_out:
        r['interrupted_candidate_horizons']=dict(r['horizons'])
        r['horizons']=dict(r.get('precheck_horizons') or {'full':None,'growth':None})
        r['certificates']=[c for c in r.get('certificates',[]) if c['query'] in r['horizons'] and r['horizons'][c['query']] is not None and c['schema']!='structural-memory.pair-certificate.v1']
        r.update(status='unknown_timeout',reason='Common10-second subprocess wall cap; unfinished queries unresolved',timed_out_phase=r.get('phase'))
        r.pop('decision_seconds',None);r.pop('certified_total_seconds',None)
    elif process.returncode:
        r.update(status='error',reason='Unexpected worker exit '+str(process.returncode),stderr=process.stderr)
        dump(path,r);raise RuntimeError(path.name+' '+process.stderr)
    require(r['status'] in ALLOWED,'Unrecognized trial outcome')
    r.update(instance=item['name'],family=item['family'],mode=mode,method=method,iteration=iteration,
      measured=iteration!='warmup',parent_wall_seconds=elapsed,parent_started_utc=started,parent_finished_utc=stamp(),
      wall_cap_seconds=CAP_SECONDS,address_space_cap_bytes=MEMORY_BYTES)
    dump(path,r);return r

def stat(values):return {'median':statistics.median(values),'min':min(values),'max':max(values)}
def summarize(item,mode,method,records):
    measured=[r for r in records if r['measured']]
    require(len(measured)==REPETITIONS,'Measured repetition count')
    completed=[r for r in measured if r['status']=='completed'];statuses=sorted({r['status'] for r in measured})
    answers={}
    for q in ('full','growth'):
        seen={r['horizons'][q] for r in records if r['horizons'][q] is not None}
        require(len(seen)<=1,'Repeated horizon disagreement')
        answers[q]=next(iter(seen)) if seen else None
    result={'instance':item['name'],'family':item['family'],'mode':mode,'method':method,
      'n':item['structure']['n'],'actions':item['structure']['U'],
      'status':statuses[0] if len(statuses)==1 else 'mixed','statuses':statuses,
      'completed_repetitions':len(completed),'measured_repetitions':REPETITIONS,'discarded_warmups':1,
      'horizons':answers,'J_size':len(records[0].get('J',[])) if mode=='preprocessed' else None,
      'precheck_horizons':records[0].get('precheck_horizons'),'reachable_states':None,'edges':None,
      'decision_seconds':None,'certified_total_seconds':None,'parent_wall_seconds':None,
      'peak_rss_bytes':None,'stages_seconds':{}}
    if completed:
        for key in ('reachable_states','edges'):
            seen={r.get(key) for r in completed};require(len(seen)==1,'Repeated graph size mismatch')
            result[key]=next(iter(seen))
    if len(completed)==REPETITIONS:
        for key in ('decision_seconds','parent_wall_seconds','peak_rss_bytes'):
            result[key]=stat([r[key] for r in completed])
        if all(r.get('all_answers_certified') for r in completed):
            result['certified_total_seconds']=stat([r['certified_total_seconds'] for r in completed])
        result['stages_seconds']={k:stat([r['stages_seconds'][k] for r in completed]) for k in completed[0]['stages_seconds']}
    else:result['censoring_reasons']=sorted({r.get('reason','unspecified') for r in measured if r['status']!='completed'})
    return result

def csv_text(summaries):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
    for s in summaries:
        r={k:s.get(k) for k in FIELDS}
        r['full']=s['horizons']['full'];r['growth']=s['horizons']['growth']
        for key in ('median','min','max'):r['decision_'+key+'_seconds']=(s['decision_seconds'] or {}).get(key)
        r['certified_total_median_seconds']=(s['certified_total_seconds'] or {}).get('median')
        r['parent_wall_median_seconds']=(s['parent_wall_seconds'] or {}).get('median')
        r['peak_rss_median_bytes']=(s['peak_rss_bytes'] or {}).get('median')
        for field,key in [('matrix','matrix_construction'),('core','core_decision'),('certificate_generation','certificate_generation'),('certificate_checking','certificate_checking')]:
            r[field+'_median_seconds']=(s['stages_seconds'].get(key) or {}).get('median')
        writer.writerow(r)
    return stream.getvalue()

def derived_tables(summaries):
    by={(x['instance'],x['mode'],x['method']):x for x in summaries}
    items={x['name']:x for x in instances()}
    cases=[]
    for item in instances():
        pair=by[(item['name'],'preprocessed','pair')]
        cases.append({'instance':item['name'],'family':item['family'],'n':item['structure']['n'],
          'actions':item['structure']['U'],'J_size':pair['J_size'],'horizons':pair['horizons'],
          'precheck_horizons':pair['precheck_horizons'],
          'pair_states':pair['reachable_states'],'support_states':by[(item['name'],'preprocessed','antichain')]['reachable_states']})
    landmarks=[]
    for name in protocol()['main_table_landmarks']:
        row=next(x for x in cases if x['instance']==name)
        landmarks.append({**row,'methods':{m:{k:by[(name,'preprocessed',m)][k] for k in ('status','horizons','decision_seconds','certified_total_seconds','parent_wall_seconds','peak_rss_bytes','stages_seconds')} for m in METHODS}})
    outcome_counts={q:{'finite':sum(type(x['horizons'][q]) is int for x in cases),
       'infinite':sum(x['horizons'][q]=='infinite' for x in cases),
       'unresolved':sum(x['horizons'][q] is None for x in cases)} for q in ('full','growth')}
    precheck_counts={str(k):sum(sum(v is not None for v in x['precheck_horizons'].values())==k for x in cases) for k in (0,1,2)}
    method_counts={m:{'completed':sum(s['mode']=='preprocessed' and s['method']==m and s['status']=='completed' for s in summaries),
      'unresolved':sum(s['mode']=='preprocessed' and s['method']==m and s['status']!='completed' for s in summaries),
      'statuses':{status:sum(s['mode']=='preprocessed' and s['method']==m and s['status']==status for s in summaries) for status in sorted({s['status'] for s in summaries if s['mode']=='preprocessed' and s['method']==m})}} for m in METHODS}
    return {'schema':'structural-memory.benchmark-derived-tables.v1','time_units':'seconds; convert to milliseconds only for display',
      'scope':'All29 original full/growth queries; fixed8 landmarks; no outcome filtering',
      'inputs':cases,'main_landmarks':landmarks,'outcome_counts':outcome_counts,'precheck_resolved_query_counts':precheck_counts,
      'method_completion_counts':method_counts,'unpruned_refresh':[s for s in summaries if s['mode']=='unpruned_stress']}

def run(out):
    frozen=check_frozen(out);require(not(out/'summary.json').exists(),'Run already exists; do not silently overwrite timings')
    status={'schema':'structural-memory.benchmark-summary.v1','status':'running','started_utc':stamp(),'environment':environment(),
       'protocol_sha256':digest(out/'protocol.json'),'summaries':[]}
    dump(out/'summary.json',status)
    try:
        for item,mode,method in jobs():
            records=[run_worker(item,mode,method,it,out) for it in ['warmup',*range(1,REPETITIONS+1)]]
            summary=summarize(item,mode,method,records);status['summaries'].append(summary)
            dump(out/'progress.json',{'completed_jobs':len(status['summaries']),'last':summary})
            print(json.dumps({k:summary[k] for k in ('instance','mode','method','status','horizons','reachable_states','decision_seconds')}),flush=True)
        check_frozen(out)
        for item in instances():
            for q in ('full','growth'):
                answers={s['horizons'][q] for s in status['summaries'] if s['instance']==item['name'] and s['horizons'][q] is not None}
                require(len(answers)<=1,'Cross-method or stress disagreement: '+item['name']+' '+q)
                if 'expected_horizons' in item['metadata']:require(answers=={item['metadata']['expected_horizons'][q]},'Fixture expectation mismatch')
        status.update(status='passed',finished_utc=stamp(),source_stable_during_run=True,
            method_instances=len(status['summaries']),fresh_process_runs=4*len(status['summaries']),
            unknown_method_instances=sum(s['status']!='completed' for s in status['summaries']))
        dump(out/'summary.json',status);(out/'benchmark.csv').write_text(csv_text(status['summaries']))
        dump(out/'derived_tables.json',derived_tables(status['summaries']))
        artifacts=[p for p in out.rglob('*') if p.is_file() and p.name not in ('manifest.json','verification.json')]
        dump(out/'manifest.json',{'schema':'structural-memory.benchmark-manifest.v1',
            'source_sha256':frozen['source_sha256'],'artifact_sha256':{p.relative_to(out).as_posix():digest(p) for p in sorted(artifacts)}})
        print('BENCHMARK_COMPLETE',out/'summary.json',flush=True)
    except BaseException as exc:
        status.update(status='failed',error=type(exc).__name__+': '+str(exc));dump(out/'summary.json',status);raise


def main():
    ap=argparse.ArgumentParser(description=__doc__);group=ap.add_mutually_exclusive_group(required=True)
    for mode in ('freeze','run','verify-recorded'):group.add_argument('--'+mode,action='store_true')
    ap.add_argument('--output',type=Path,default=DEFAULT);args=ap.parse_args();out=args.output.resolve()
    require(args.verify_recorded or not out.is_relative_to(ROOT/'data'), 'Frozen published records are read-only; choose a separate output directory')
    if args.freeze:freeze(out)
    elif args.run:run(out)
    else:
        from verify_recorded import verify
        print(encode(verify(out)))

if __name__=='__main__':main()
