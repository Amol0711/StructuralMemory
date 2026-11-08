"""Capped exact structural-memory benchmark worker.

The main timing boundary ends after both original full/growth horizons.
Pair certificates and checking are additional, separately timed stages.
The dense exterior representation is a reference implementation, not an
assertion about the best possible exact-algebra implementation.
"""
from pathlib import Path
from collections import deque
from functools import reduce
import argparse,hashlib,json,math,os,resource,struct,sys,time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'src'))
from compact_memory.model import Structure,initial_state,transition
from compact_memory.solver import _classify
from compact_memory.certificate_checker import check_certificate
from reference import auto_step,canonical_int,compound2,exterior_horizons_exact

LIMIT=1073741824

def normalize(value):
    return 'infinite' if isinstance(value,float) and math.isinf(value) else value


def classify(states,edges,bad):
    reverse=[[] for _ in states]
    for v,row in enumerate(edges):
        for child in row:reverse[child].append(v)
    relevant={i for i,flag in enumerate(bad) if flag}
    queue=deque(relevant)
    while queue:
        child=queue.popleft()
        for v in reverse[child]:
            if v not in relevant:relevant.add(v);queue.append(v)
    indeg={v:0 for v in relevant}
    for v in relevant:
        for w in edges[v]:
            if w in relevant:indeg[w]+=1
    queue=deque(v for v in relevant if not indeg[v]);order=[]
    while queue:
        v=queue.popleft();order.append(v)
        for w in edges[v]:
            if w in relevant:
                indeg[w]-=1
                if not indeg[w]:queue.append(w)
    if len(order)!=len(relevant):return 'infinite'
    rank=[-1]*len(states)
    for v in reversed(order):
        rank[v]=max([0 if bad[v] else -1]+[1+rank[w] for w in edges[v] if rank[w]>=0])
    return rank[0]+1


def explore(data,kind):
    structure=Structure.from_dict(data)
    start=initial_state(structure) if kind=='pair' else (frozenset(range(data['n'])),frozenset())
    states=[start];ids={start:0};edges=[];pred=[None]
    cursor=0
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
    bad_full=[bool(s.root) if kind=='pair' else bool(s[0]) for s in states]
    bad_growth=[bool(s.root&mask) if kind=='pair' else bool(s[0]&target) for s in states]
    answers={'full':classify(states,edges,bad_full),'growth':classify(states,edges,bad_growth)}
    return structure,states,edges,pred,answers


class SparseIntegerRows:
    """Exact fraction-free row basis; dictionary zeros are implicit."""
    def __init__(self):self.rows={}
    def add(self,row):
        v=dict(row)
        for pivot in sorted(self.rows):
            b=v.get(pivot)
            if not b:continue
            r=self.rows[pivot];a=r[pivot]
            keys=v.keys()|r.keys()
            v={k:value for k in keys if (value:=a*v.get(k,0)-b*r.get(k,0))}
            if not v:return False
            gcd=reduce(math.gcd,v.values(),0)
            if gcd>1:v={k:value//gcd for k,value in v.items()}
        if not v:return False
        gcd=reduce(math.gcd,v.values(),0)
        if gcd>1:v={k:value//gcd for k,value in v.items()}
        self.rows[min(v)]=v;return True
    def dim(self):return len(self.rows)
    def basis(self):return list(self.rows.values())


def multiply(row,B):
    out={}
    for i,x in row.items():
        for j,y in B[i].items():out[j]=out.get(j,0)+x*y
    return {j:value for j,value in out.items() if value}


def exterior_horizons(Bs,ms,pairs):
    D=len(pairs);answers={};dimensions={}
    S=SparseIntegerRows()
    for B in Bs:
        for row in B:S.add(row)
    k=1;seq=[D,S.dim()]
    if D==0:answers['full']=0
    while 'full' not in answers:
        if not S.dim():answers['full']=k;break
        T=SparseIntegerRows()
        for v in S.basis():
            for B in Bs:T.add(multiply(v,B))
        seq.append(T.dim())
        if T.dim()==S.dim():answers['full']='infinite';break
        S=T;k+=1
    dimensions['full']=seq
    R=SparseIntegerRows()
    for m in ms:R.add({k:m[i]-m[j] for k,(i,j) in enumerate(pairs) if m[i]!=m[j]})
    closure=[R.dim()]
    while True:
        before=R.dim()
        generated=[multiply(v,B) for v in R.basis() for B in Bs]
        for v in generated:R.add(v)
        closure.append(R.dim())
        if R.dim()==before:break
    S=R;k=0;seq=[S.dim()]
    while True:
        if not S.dim():answers['growth']=k;break
        T=SparseIntegerRows()
        for v in S.basis():
            for B in Bs:T.add(multiply(v,B))
        seq.append(T.dim())
        if T.dim()==S.dim():answers['growth']='infinite';break
        S=T;k+=1
    dimensions['growth']=seq;dimensions['growth_closure']=closure
    return answers,dimensions


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--method',choices=['pair','antichain','exterior'],required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--verify-dense',action='store_true');args=ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    resource.setrlimit(resource.RLIMIT_AS,(LIMIT,LIMIT))
    data=json.loads(args.input.read_text());stage={};start=time.perf_counter()
    result={'status':'running','method':args.method,'n':data['n'],'actions':data['U'],'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'stages_seconds':stage,'horizons':None,'phase':'input_construction','peak_rss_units':'bytes; Linux ru_maxrss *1024','resource_limit_bytes':LIMIT}
    def save():
        result['worker_elapsed_seconds']=time.perf_counter()-start
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        temp=args.output.with_suffix('.tmp');temp.write_text(json.dumps(result,sort_keys=True,allow_nan=False)+'\n');temp.replace(args.output)
    save()
    try:
        t=time.perf_counter()
        Structure.from_dict(data)
        if args.method=='exterior':
            N=2**data['n'];D=N*(N-1)//2
            # These cell references alone are mandatory for retained dense Bs.
            lower=data['U']*D*D*struct.calcsize('P')
            result['dense_compound_pointer_lower_bound_bytes']=lower
            result['exterior_dimension']=D
            if lower>LIMIT:
                result.update(status='unknown_memory_preflight',phase='finished',reason='Mandatory dense-compound list cell references exceed memory cap; no algebra run.')
                stage['input_construction']=time.perf_counter()-t;save();return
            matrices,masses=canonical_int(data)
            dense=[];pairs=None
            for M in matrices:B,pairs=compound2(M);dense.append(B)
            sparse=[[{j:x for j,x in enumerate(row) if x} for row in B] for B in dense]
            stage['input_construction']=time.perf_counter()-t
            result['phase']='horizon_computation';save();t=time.perf_counter()
            answers,dimensions=exterior_horizons(sparse,masses,pairs)
            stage['horizon_computation']=time.perf_counter()-t
            result.update(horizons=answers,dimensions=dimensions,reachable_states=None,edges=None)
            result['peak_rss_core_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            stage['certificate_generation']=None;stage['certificate_checking']=None
            if args.verify_dense:
                expected,_=exterior_horizons_exact(matrices,masses)
                if answers!={'full':normalize(expected['f']),'growth':normalize(expected['g'])}:raise RuntimeError('Sparse/dense exact algebra mismatch')
                result['dense_reference_agreement']=True
        else:
            stage['input_construction']=time.perf_counter()-t
            result['phase']='horizon_computation';save();t=time.perf_counter()
            structure,states,edges,pred,answers=explore(data,args.method)
            stage['horizon_computation']=time.perf_counter()-t
            result.update(horizons=answers,reachable_states=len(states),edges=sum(map(len,edges)))
            result['peak_rss_core_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
            if args.method=='pair':
                result['phase']='certificate_generation';save();t=time.perf_counter()
                reverse=[[] for _ in states]
                for v,row in enumerate(edges):
                    for action,child in enumerate(row):reverse[child].append((v,action))
                certificates=[]
                for q in ('full','growth'):
                    item=_classify(structure,states,edges,pred,reverse,q)
                    got=item['horizon'] if item['status']=='finite' else 'infinite'
                    if got!=answers[q]:raise RuntimeError('Production certificate/classifier disagreement')
                    certificates.append(item['certificate'])
                stage['certificate_generation']=time.perf_counter()-t
                result['phase']='certificate_checking';save();t=time.perf_counter()
                if not all(check_certificate(cert) for cert in certificates):raise RuntimeError('Certificate rejected')
                stage['certificate_checking']=time.perf_counter()-t
                result['certificates_accepted']=2
            else:stage['certificate_generation']=None;stage['certificate_checking']=None
        stage['weight_construction']=None;stage['scheduling']=None
        result['status']='completed';result['phase']='finished';save()
    except MemoryError:
        result.update(status='unknown_memory_limit',reason='MemoryError under 1 GiB address-space cap');save()
    except Exception as exc:
        result.update(status='error',error=type(exc).__name__+': '+str(exc));save();raise

if __name__=='__main__':main()
