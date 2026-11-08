"""Fresh-process worker for common-preprocessed original memory queries."""
from pathlib import Path
from collections import deque
import argparse,hashlib,json,resource,struct,sys,time
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'src'),str(ROOT/'src')]
from compact_memory.model import Structure,initial_state,transition
from compact_memory.solver import _classify
from compact_memory.certificate_checker import check_certificate as check_pair
from structural_frontend import precheck,check_certificate as check_precheck
from reference import auto_step,canonical_int,compound2
from benchmark_core import SparseIntegerRows,multiply,classify
from fixtures import MEMORY_BYTES

def require(ok,message):
    if not ok:raise RuntimeError(message)

def exterior_selected(bs,masses,pairs,queries):
    d=len(pairs);answers={};dimensions={}
    if 'full' in queries:
        space=SparseIntegerRows()
        for b in bs:
            for row in b:space.add(row)
        k=1;seq=[d,space.dim()]
        if not d:answers['full']=0
        while 'full' not in answers:
            if not space.dim():answers['full']=k;break
            nxt=SparseIntegerRows()
            for row in space.basis():
                for b in bs:nxt.add(multiply(row,b))
            require(nxt.dim()<=space.dim(),'Full descending-space invariant')
            seq.append(nxt.dim())
            if nxt.dim()==space.dim():answers['full']='infinite';break
            space=nxt;k+=1
        dimensions['full']=seq
    if 'growth' in queries:
        space=SparseIntegerRows()
        for mass in masses:space.add({k:mass[i]-mass[j] for k,(i,j) in enumerate(pairs) if mass[i]!=mass[j]})
        closure=[space.dim()]
        while True:
            before=space.dim()
            generated=[multiply(row,b) for row in space.basis() for b in bs]
            for row in generated:space.add(row)
            closure.append(space.dim())
            if space.dim()==before:break
        k=0;seq=[space.dim()]
        while True:
            if not space.dim():answers['growth']=k;break
            nxt=SparseIntegerRows()
            for row in space.basis():
                for b in bs:nxt.add(multiply(row,b))
            require(nxt.dim()<=space.dim(),'Growth descending-space invariant')
            seq.append(nxt.dim())
            if nxt.dim()==space.dim():answers['growth']='infinite';break
            space=nxt;k+=1
        dimensions['growth']=seq;dimensions['growth_closure']=closure
    return answers,dimensions

def explore(data,structure,kind,queries):
    start=initial_state(structure) if kind=='pair' else (frozenset(range(data['n'])),frozenset())
    states=[start];ids={start:0};edges=[];pred=[None];cursor=0
    while cursor<len(states):
        row=[]
        for action in range(data['U']):
            child=transition(structure,states[cursor],action) if kind=='pair' else auto_step(data,states[cursor],action)
            index=ids.get(child)
            if index is None:
                index=len(states);ids[child]=index;states.append(child);pred.append((cursor,action))
            row.append(index)
        edges.append(row);cursor+=1
    target=set(i for scopes in data['fac'] for scope in scopes for i in scope)
    mask=sum(1<<i for i in target)
    answers={}
    for query in queries:
        bad=[bool(s.root) if kind=='pair' else bool(s[0]) for s in states] if query=='full' else [bool(s.root&mask) if kind=='pair' else bool(s[0]&target) for s in states]
        answers[query]=classify(states,edges,bad)
    return states,edges,pred,answers

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--method',choices=('pair','antichain','exterior'),required=True)
    ap.add_argument('--mode',choices=('preprocessed','unpruned_stress'),default='preprocessed')
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    require(not(args.mode=='unpruned_stress' and args.method=='exterior'),'Stress protocol has structural methods only')
    require(not args.output.resolve().is_relative_to(ROOT/'data'), 'Frozen data are read-only; choose a separate output path')
    require(not args.output.exists(), 'Output file already exists')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS,(MEMORY_BYTES,MEMORY_BYTES))
    start=time.perf_counter();stage={k:0.0 for k in ('input_validation','precheck','matrix_construction','core_decision','certificate_generation','certificate_checking')}
    result={'schema':'structural-memory.benchmark-worker.v1','status':'running','semantics':'graphical-unrestricted',
       'method':args.method,'mode':args.mode,'horizons':{'full':None,'growth':None},'certificates':[],
       'stages_seconds':stage,'phase':'input_validation','resource_limit_bytes':MEMORY_BYTES,
       'reachable_states':None,'edges':None,'precheck_horizons':None}
    def save():
        result['worker_elapsed_seconds']=time.perf_counter()-start
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(result,sort_keys=True,allow_nan=False)+'\n');tmp.replace(args.output)
    save()
    try:
        t=time.perf_counter();raw=args.input.read_bytes();data=json.loads(raw);structure=Structure.from_dict(data)
        result.update(n=structure.n,actions=structure.U,input_sha256=hashlib.sha256(raw).hexdigest())
        stage['input_validation']=time.perf_counter()-t;result['phase']='precheck';save()
        if args.mode=='preprocessed':
            t=time.perf_counter();front=precheck(structure);stage['precheck']=time.perf_counter()-t
            result['precheck_horizons']=dict(front['horizons']);result['horizons'].update(front['horizons'])
            result['J']=front['J'];result['precheck_stats']=front['stats']
            certs=[c for c in front['certificates'].values() if c is not None]
            t=time.perf_counter()
            for cert in certs:
                require(cert['structure']==structure.to_dict(),'Precheck certificate input mismatch')
                require(check_precheck(cert,expected_structure=data),'Precheck certificate rejected')
            stage['certificate_checking']+=time.perf_counter()-t
            result['certificates'].extend(certs)
        queries=[q for q,v in result['horizons'].items() if v is None]
        result['core_queries']=queries;result['phase']='matrix_construction';save()
        if queries and args.method=='exterior':
            t=time.perf_counter();n=2**data['n'];d=n*(n-1)//2
            lower=data['U']*d*d*struct.calcsize('P')
            result['dense_compound_pointer_lower_bound_bytes']=lower;result['exterior_dimension']=d
            if lower>MEMORY_BYTES:
                stage['matrix_construction']=time.perf_counter()-t
                result.update(status='unknown_memory_preflight',phase='finished',reason='Dense compound pointer storage exceeds the common cap for this reference implementation.')
                save();return
            matrices,masses=canonical_int(data);dense=[];pairs=None
            for m in matrices:
                b,pairs=compound2(m);dense.append(b)
            sparse=[[{j:x for j,x in enumerate(row) if x} for row in b] for b in dense]
            stage['matrix_construction']=time.perf_counter()-t;result['phase']='core_decision';save()
            t=time.perf_counter();answers,dimensions=exterior_selected(sparse,masses,pairs,queries)
            stage['core_decision']=time.perf_counter()-t;result['horizons'].update(answers);result['dimensions']=dimensions
        elif queries:
            result['phase']='core_decision';save();t=time.perf_counter()
            states,edges,pred,answers=explore(data,structure,args.method,queries)
            stage['core_decision']=time.perf_counter()-t;result['horizons'].update(answers)
            result.update(reachable_states=len(states),edges=sum(map(len,edges)))
            result['peak_rss_decision_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            if args.method=='pair':
                result['phase']='certificate_generation';save();t=time.perf_counter()
                reverse=[[] for _ in states]
                for v,row in enumerate(edges):
                    for action,child in enumerate(row):reverse[child].append((v,action))
                certs=[]
                for query in queries:
                    item=_classify(structure,states,edges,pred,reverse,query)
                    horizon=item['horizon'] if item['status']=='finite' else 'infinite'
                    require(horizon==answers[query],'Certificate classification mismatch')
                    certs.append(item['certificate'])
                stage['certificate_generation']=time.perf_counter()-t;result['phase']='certificate_checking';save();t=time.perf_counter()
                for cert in certs:require(check_pair(cert),'Pair certificate rejected')
                stage['certificate_checking']+=time.perf_counter()-t;result['certificates'].extend(certs)
        if 'peak_rss_decision_bytes' not in result:result['peak_rss_decision_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        require(all(v is not None for v in result['horizons'].values()),'Completed worker has unresolved query')
        result['all_answers_certified']=set(c['query'] for c in result['certificates'])=={'full','growth'}
        result['decision_seconds']=sum(stage[k] for k in ('input_validation','precheck','matrix_construction','core_decision'))
        result['certified_total_seconds']=sum(stage.values()) if result['all_answers_certified'] else None
        result.update(status='completed',phase='finished');save()
    except MemoryError:
        result['interrupted_candidate_horizons']=dict(result['horizons'])
        result['horizons']=dict(result['precheck_horizons'] or {'full':None,'growth':None})
        result['certificates']=[c for c in result['certificates'] if c['schema']!='structural-memory.pair-certificate.v1']
        result.update(status='unknown_memory_limit',reason='MemoryError under common address-space cap');save()
    except BaseException as exc:
        result.update(status='error',error=type(exc).__name__+': '+str(exc));save();raise

if __name__=='__main__':main()
