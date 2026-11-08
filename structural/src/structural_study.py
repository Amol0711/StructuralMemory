"""Exact structural comparison of feedforward chains and fitness scopes.

Run from any directory. Uses the supplied pair solver, its separately coded
certificate checker, a support/antichain comparator, direct unrolled-DAG
moralization, and exact canonical-boundary algebra on bounded small cases.
The outcomes certify these finite instances; they do not establish a new
closed-form formula for all dimensions.
"""
from pathlib import Path
import argparse,csv,hashlib,itertools,json,math,platform,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'src'))
from compact_memory.solver import solve
from compact_memory.certificate_checker import check_certificate
from compact_memory.model import initial_state,transition,Structure
from graph_validation.oracles import raw_initial,raw_step,collapsed_pair,connected_by_moralization
from reference import auto_horizons,canonical_int,exterior_horizons_exact


def require(condition,message):
    if not condition:raise RuntimeError(message)


def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n')


def structure(n,variant):
    scopes=[[n-2],[n-1]] if variant=='separate' else [[n-2,n-1]]
    return {'n':n,'U':2,
            'pa':[[[] if i==0 else [i-1] for i in range(n)] for _ in range(2)],
            'fac':[[list(scope) for scope in scopes] for _ in range(2)]}


def normalized(value):
    return {'status':'infinite','horizon':None} if math.isinf(value) else {'status':'finite','horizon':value}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();out=args.output.resolve()
    require(not out.is_relative_to(ROOT/'data'), 'Frozen data are read-only; choose a separate output path')
    require(not out.exists(), 'Output directory already exists; choose a new path')
    out.mkdir(parents=True,exist_ok=True)
    dump(out/'summary.json',{'status':'running','success':False})
    rows=[];detailed=[];checks={'certificates':0,'antichain_instances':0,'raw_state_comparisons':0,'moralized_endpoint_queries':0,'canonical_algebra_instances':0}
    instances=[(n,kind,structure(n,kind)) for n in [2,4,6,8,10,12] for kind in ['separate','joint']]
    # Freeze all complete declared structures before evaluating any instance.
    for n,kind,data in instances:dump(out/'inputs'/f'chain_{n:02}_{kind}.json',data)
    try:
        for n,kind,data in instances:
            name=f'chain_{n:02}_{kind}'
            result=solve(data)
            require(result['exploration']['complete'],name+': unresolved pair search')
            for query in ['full','growth']:
                cert=result[query]['certificate'];require(check_certificate(cert),name+': rejected '+query+' certificate')
                dump(out/'certificates'/(name+'_'+query+'.json'),cert);checks['certificates']+=1
            independent=auto_horizons(data,Lcap=1000)
            for query,value in zip(['full','growth'],independent[:2]):
                require(normalized(value)=={k:result[query][k] for k in ['status','horizon']},name+': support/antichain disagreement')
            checks['antichain_instances']+=1
            st=Structure.from_dict(data);state=initial_state(st);raw=raw_initial(n)
            trajectory=[]
            for depth in range(2*n+3):
                projected=collapsed_pair(raw,n)
                require((state.root,state.pairs)==projected,name+': raw component state disagreement at '+str(depth))
                checks['raw_state_comparisons']+=1
                trajectory.append({'length':depth,'marked_coordinates':[i for i in range(n) if state.root>>i&1],
                                   'full_connected':bool(state.root),'growth_connected':bool(state.root & ((1<<(n-2))|(1<<(n-1))))})
                # The two declared actions are identical. Check both operators.
                for action in [0,1]:
                    nxt=transition(st,state,action)
                    raw_next=raw_step(raw,data['pa'][action],data['fac'][action],n)
                    require((nxt.root,nxt.pairs)==collapsed_pair(raw_next,n),name+': action-specific component disagreement')
                state=transition(st,state,0);raw=raw_step(raw,data['pa'][0],data['fac'][0],n)
            # Exhaustive action words for small chains; selected repeated words
            # for larger chains. Full horizon certification is independent of
            # these bounded DAG checks and comes from the checked certificates.
            for length in range(n+3):
                words=itertools.product(range(2),repeat=length) if n<=4 else [tuple([0]*length),tuple([1]*length)]
                for word in words:
                    current=initial_state(st)
                    for action in word:current=transition(st,current,action)
                    for query,target in [('full',set(range(n))),('growth',{n-2,n-1})]:
                        expected=bool(current.root & sum(1<<i for i in target))
                        actual=connected_by_moralization(data,word,target)
                        require(expected==actual,name+': direct moralization disagreement')
                        checks['moralized_endpoint_queries']+=1
            algebra=None
            if n<=4:
                matrices,masses=canonical_int(data)
                values,dimensions=exterior_horizons_exact(matrices,masses)
                algebra={'arithmetic':'exact integers and rational row reduction; actionwise positive scalar scaling is immaterial to reset',
                         'full':normalized(values['f']),'growth':normalized(values['g']),
                         'descending_dimensions':dimensions}
                for query in ['full','growth']:
                    require(algebra[query]=={k:result[query][k] for k in ['status','horizon']},name+': canonical exterior disagreement')
                checks['canonical_algebra_instances']+=1
            detail={'instance':name,'dimension':n,'fitness_scopes':kind,'pair_result':result,
                    'support_antichain':{'full':normalized(independent[0]),'growth':normalized(independent[1]),'last_inspected_length':independent[2]},
                    'marked_trajectory':trajectory,'canonical_algebra':algebra}
            dump(out/'instances'/(name+'.json'),detail)
            detailed.append({'instance':name,'dimension':n,'fitness_scopes':kind,
                             'full':{k:result['full'][k] for k in ['status','horizon']},
                             'growth':{k:result['growth'][k] for k in ['status','horizon']},
                             'reachable_pair_states':result['exploration']['states_discovered'],
                             'transitions':result['exploration']['transitions_stored']})
            rows.append({'dimension':n,'fitness_scopes':kind,'full_horizon':result['full']['horizon'] if result['full']['status']=='finite' else 'infinity',
                         'growth_horizon':result['growth']['horizon'] if result['growth']['status']=='finite' else 'infinity',
                         'reachable_pair_states':result['exploration']['states_discovered'],
                         'transitions':result['exploration']['transitions_stored']})
        with (out/'horizons.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
        with (out/'horizons.dat').open('w') as f:
            f.write('dimension separate_full separate_growth joint_full_infinite joint_growth_infinite separate_states joint_states\n')
            for n in [2,4,6,8,10,12]:
                a,b=[r for r in rows if r['dimension']==n]
                f.write(f"{n} {a['full_horizon']} {a['growth_horizon']} 1 1 {a['reachable_pair_states']} {b['reachable_pair_states']}\n")
        source_paths=[Path(__file__),ROOT/'src/compact_memory/model.py',ROOT/'src/compact_memory/solver.py',ROOT/'src/compact_memory/certificate_checker.py',ROOT/'src/graph_validation/oracles.py',ROOT/'src/reference.py']
        summary={'status':'passed','success':True,'question':'Same feedforward transition scopes, separate final-two unary fitness scopes versus one joint scope',
                 'instances':detailed,'checks':checks,'python_version':platform.python_version(),
                 'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
                 'interpretation':'For the six tested dimensions, separate scopes yield both horizons equal to the dimension; joint scopes yield both infinite. All 24 horizon answers have separately accepted certificates.',
                 'scope_caveat':'These are different declared free fitness families. Refactorizing an identical numerical fitness function leaves its numerical dynamics unchanged. No new all-dimension formula or statistical inference is asserted.',
                 'canonical_boundary_caveat':'The algebra comparison uses fixed rational boundary matrices whose transition entries can vanish. These matrices are distinct from strictly positive parameter draws.',
                 'query_caveat':'Both queries are on the original full chain; every coordinate is fitness-ancestral here, so no coordinate was discarded.'}
        dump(out/'summary.json',summary)
        manifests={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}
        dump(out/'manifest.json',{'sha256':manifests})
        print(json.dumps({'status':'passed','instances':len(instances),'checks':checks}))
    except BaseException as exc:
        dump(out/'summary.json',{'status':'failed','success':False,'error_type':type(exc).__name__,'error':str(exc),'completed_instances':detailed})
        raise

if __name__=='__main__':main()
