#!/usr/bin/env python3
"""Bounded exact feasibility study for terminal-fitness response cascades.

This is a synthetic model study, not biological calibration or a comparative
performance benchmark. All coordinates are fitness-ancestral. Exact product
propagation is valid only for the explicitly checked terminal-fitness cascade.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import product
import argparse, csv, hashlib, importlib.util, json, platform, sys, time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'checks'))
from compact_memory.model import Structure
from compact_memory.solver import solve as structural_solve
from compact_memory.certificate_checker import check_certificate
from scheduling_tools.model import HistoryModel
from profiled_solver import solve as schedule_solve

SPEC = importlib.util.spec_from_file_location('cascade_independent_oracles', ROOT / 'checks/control_validation/oracles.py')
ORACLE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ORACLE)
from verify_instrumentation import verify as verify_timing_copy
OUT = ROOT / 'reruns/feasibility'
LIMITS = {'max_states':5000, 'max_edges':20000, 'max_cycles':5000,
          'max_warmup_steps':20000, 'max_cycle_steps':50000}


def require(ok, message):
    if not ok: raise RuntimeError(message)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def source_hashes():
    names = ['studies/feasibility/run_feasibility.py',
             'checks/compact_memory/model.py','checks/compact_memory/solver.py',
             'checks/compact_memory/certificate_checker.py',
             'checks/scheduling_tools/model.py','checks/scheduling_tools/solver.py',
             'checks/control_validation/oracles.py',
             'studies/feasibility/profiled_solver.py','studies/feasibility/instrumentation.json',
             'studies/feasibility/verify_instrumentation.py']
    return {n:sha(ROOT/n) for n in names}


def make_model(name, depth, branches=1, actions=2, adjacent=False):
    n=depth*branches; parents=[]
    for b in range(branches):
        for j in range(depth): parents.append([] if j==0 else [b*depth+j-1])
    terminals=[b*depth+depth-1 for b in range(branches)]
    scope=[n-2,n-1] if adjacent else terminals
    structure={'n':n,'U':actions,'pa':[[list(p) for p in parents] for _ in range(actions)],
               'fac':[[scope] for _ in range(actions)]}
    roots=['1/4','3/4'] if actions==2 else ['1/4','1/2','3/4']
    fitness=[['6/5','3/5'],['3/5','6/5'],['9/10','4/5']][:actions]
    return {'name':name,'depth':depth,'branches':branches,'structure':structure,
            'terminal_coordinates':terminals,'scope':scope,
            'root_probabilities':roots,'downstream_probabilities':['1/4','3/4'],
            'fitness_non_all_ones_and_all_ones':fitness,
            'expected_graphical_horizon':'infinite' if adjacent else depth,
            'factorization_allowed':not adjacent}


def frozen_protocol():
    return {'schema':'structural-memory.control-feasibility.v1',
       'scope':'Synthetic terminal-fitness response cascades; no calibrated biological claim.',
       'models':[make_model('serial_2_u2',2),make_model('serial_4_u2',4),
                 make_model('serial_6_u2',6),make_model('serial_4_u3',4,actions=3),
                 make_model('parallel_2x2_u2',2,branches=2),make_model('parallel_2x3_u2',3,branches=2),
                 make_model('serial_4_adjacent_joint_negative',4,adjacent=True)],
       'parameter_family':'Fixed numerical points in free positive local tables with matching-context downstream entries shared across coordinates/actions. No complement relation is imposed on the family.',
       'constraints':['unrestricted','one_recovery_step','two_recovery_steps'],
       'scheduling_limits':LIMITS,'independent_cycle_oracle_max_viable_vertices':24,
       'dense_verification':'For n=2 all length-L histories and all pure columns. Otherwise four deterministic histories and four deterministic columns (duplicates removed); also correlated endpoint mixture for those histories.',
       'timing_scope':'One serial illustrative run. Stage times are descriptive, neither repeated comparative benchmarks nor complexity bounds.',
       'negative_case':'Graphically infinite case is retained and stops before weight construction/optimization; no assertion about every numerical point.'}


def constraints(actions):
    high=actions-1
    return {
       'unrestricted':{'states':1,'initial':[0],'next':[[0]*actions]},
       'one_recovery_step':{'states':2,'initial':[0],
          'next':[[1 if a==high else 0 for a in range(actions)],
                  [None if a==high else 0 for a in range(actions)]]},
       'two_recovery_steps':{'states':3,'initial':[0],
          'next':[[1 if a==high else 0 for a in range(actions)],
                  [None if a==high else 2 for a in range(actions)],
                  [None if a==high else 0 for a in range(actions)]]}}


def fitness_ancestry(data):
    target=set(x for fs in data['fac'] for f in fs for x in f)
    J=set(target); todo=list(target)
    while todo:
        i=todo.pop()
        for ps in data['pa']:
            for p in ps[i]:
                if p not in J:J.add(p);todo.append(p)
    return sorted(J)


def check_factorization_domain(model):
    data=model['structure'];n=data['n'];terminal=set(model['terminal_coordinates'])
    require(model['factorization_allowed'],'Factorized computation excluded for this scope')
    used=[]
    for i,p in enumerate(data['pa'][0]):
        require(len(p)<=1,'More than one parent is not allowed by shortcut')
        used.extend(p)
    require(len(used)==len(set(used)),'Fan-out is not allowed by shortcut')
    require(not (terminal & set(used)),'A selected terminal is a transition parent')
    require(all(row==data['pa'][0] for row in data['pa']),'Action-dependent parent graph excluded')
    require(all(set(f)<=terminal for fs in data['fac'] for f in fs),'Nonterminal selection excluded')
    require(all(len(fs)==1 for fs in data['fac']),'Expected exactly one terminal fitness factor')
    require(len(model['root_probabilities'])==data['U'],'Root probability count')
    require(all(0<F(x)<1 for x in model['root_probabilities']+model['downstream_probabilities']), 'Positive CPTs')
    require(all(F(x)>0 for pair in model['fitness_non_all_ones_and_all_ones'] for x in pair),'Positive fitness')


def mass_factor(model,q,action):
    p=F(1)
    for i in model['scope']:p*=q[i]
    lo,hi=map(F,model['fitness_non_all_ones_and_all_ones'][action])
    return lo+(hi-lo)*p


def next_product(model,q,action):
    lo,hi=map(F,model['downstream_probabilities'])
    root=F(model['root_probabilities'][action])
    return tuple(root if not p else lo+(hi-lo)*q[p[0]] for p in model['structure']['pa'][action])


def product_propagate(model,column,word):
    n=model['structure']['n']; q=tuple(F((column>>(n-1-i))&1) for i in range(n)); mass=F(1)
    for action in word:
        mass*=mass_factor(model,q,action)
        q=next_product(model,q,action)
    return q,mass


def weights(model,L):
    check_factorization_domain(model)
    n=model['structure']['n'];U=model['structure']['U'];records=[];checks=0
    for word in product(range(U),repeat=L):
        reference=None
        for column in range(1<<n):
            q,mass=product_propagate(model,column,word)
            require(mass>0,'Nonpositive column mass')
            values=tuple(mass_factor(model,q,a) for a in range(U))
            checks+=U
            if reference is None: reference=values
            require(values==reference,'Failure of exact all-column growth reset')
        for action,value in enumerate(reference):records.append({'history':list(word),'action':action,'value':str(value)})
    # A direct positive point witness that shorter uniform memory fails.
    witness=None
    if L:
        for word in product(range(U),repeat=L-1):
            for action in range(U):
                first=mass_factor(model,product_propagate(model,0,word)[0],action)
                for column in range(1,1<<n):
                    other=mass_factor(model,product_propagate(model,column,word)[0],action)
                    if other!=first:
                        witness={'history':list(word),'action':action,'columns':[0,column],'ratios':[str(first),str(other)]};break
                if witness:break
            if witness:break
        require(witness is not None,'No shorter-memory failure witness')
    return records,{'histories':U**L,'weights':len(records),'all_column_ratio_evaluations':checks,
                    'shorter_uniform_memory_failure':witness,'factorization_domain_checked':True}


def build_dense(model):
    data=model['structure'];n=data['n'];states=list(product((0,1),repeat=n));matrices=[]
    for action in range(data['U']):
        rows=[]
        root=F(model['root_probabilities'][action]);lo,hi=map(F,model['downstream_probabilities'])
        fl,fh=map(F,model['fitness_non_all_ones_and_all_ones'][action])
        for y in states:
            row=[]
            for x in states:
                fit=fh if all(x[i] for i in model['scope']) else fl
                prob=F(1)
                for i,p in enumerate(data['pa'][action]):
                    theta=root if not p else (hi if x[p[0]] else lo)
                    prob*=theta if y[i] else 1-theta
                row.append(prob*fit)
            rows.append(row)
        matrices.append(rows)
    return matrices,states


def matvec(M,z):
    return [sum((x*y for x,y in zip(row,z)),F(0)) for row in M]


def dense_validate(model,L,records):
    matrices,states=build_dense(model);N=len(states);U=len(matrices)
    if model['structure']['n']==2:
        words=list(product(range(U),repeat=L));columns=list(range(N))
    else:
        words=sorted(set([(0,)*L,(U-1,)*L,tuple(i%U for i in range(L)),tuple((L-1-i)%U for i in range(L))]))
        columns=sorted(set([0,1,N//2,N-1]))
    lookup={(tuple(r['history']),r['action']):F(r['value']) for r in records}
    vector_checks=0;ratio_checks=0;correlated=0
    for word in words:
        for column in columns:
            z=[F(i==column) for i in range(N)]
            for a in word:z=matvec(matrices[a],z)
            q,mass=product_propagate(model,column,word)
            expected=[]
            for y in states:
                py=mass
                for i,bit in enumerate(y):py*=q[i] if bit else 1-q[i]
                expected.append(py)
            require(z==expected,'Dense vector disagrees with factorized propagation')
            vector_checks+=1
            denominator=sum(z)
            for a in range(U):
                require(sum(matvec(matrices[a],z))/denominator==lookup[word,a],'Dense ratio mismatch')
                ratio_checks+=1
        z=[F(1,2) if i in (0,N-1) else F(0) for i in range(N)]
        for a in word:z=matvec(matrices[a],z)
        for a in range(U):
            require(sum(matvec(matrices[a],z))/sum(z)==lookup[word,a],'Correlated initial population mismatch')
            correlated+=1
    return {'histories':[list(w) for w in words],'columns':columns,'full_vector_comparisons':vector_checks,
            'pure_column_growth_ratio_comparisons':ratio_checks,'correlated_endpoint_mixture_ratio_comparisons':correlated,
            'scope':'Dense checks cover these explicit subsets; the factorized all-column check covers every length-L history.'}


def verify_graph_and_cycles(data,result):
    initial,ref_edges,viable=ORACLE.reference_graph(data)
    require(result['exploration']['graph_complete'],'This study expects graph construction below its cap')
    graph=result['graph'];states=[(tuple(x['history']),x['constraint']) for x in graph['states']]
    require(set(states)==set(ref_edges),'Independent reachable state disagreement')
    require({states[i] for i in graph['initial']}==initial,'Independent initial history-state disagreement')
    actual={(states[e['source']],e['action'],states[e['target']],F(e['weight'])) for e in graph['edges']}
    expected={(s,a,t,g) for s,row in ref_edges.items() for a,t,g in row}
    require(actual==expected,'Independent reachable edge/weight disagreement')
    require({states[i] for i in graph['viable']}==viable,'Independent viability disagreement')
    compared=False;witnesses=0
    if result['status']=='optimal':
        for key in ('minimum','maximum'):
            require(ORACLE.replay_witness(data,result[key]),'Invalid legal periodic-tail witness');witnesses+=1
        if len(viable)<=24:
            ref=ORACLE.closed_walk_extrema(data)
            for key,bound in zip(('minimum','maximum'),ref):
                got=result[key]
                require(ORACLE.compare_roots((F(got['product']),got['length']),bound)==0,'Independent closed-walk optimum mismatch')
            compared=True
    else:
        require(result['status']=='unknown' and result['reason'] in ('max_cycles','max_cycle_steps'),'Unexpected scheduling status')
        require(result['minimum'] is None and result['maximum'] is None,'Capped optimization must not report an optimum')
    return {'reachable_graph_and_weights_match':True,'legal_periodic_tail_witnesses_checked':witnesses,
            'independent_closed_walk_extrema_checked':compared,'viable_vertices':len(viable),
            'cycle_oracle_limit':24}


def freeze(out):
    out.mkdir(parents=True,exist_ok=True)
    data=frozen_protocol();path=out/'protocol.json'
    if path.exists():require(json.loads(path.read_text())==data,'Frozen protocol differs; use a fresh output directory')
    else:dump(path,data)
    return data


def run(out):
    sys.path.insert(0,str(ROOT/"studies"))
    from output_guard import fresh_output
    out=fresh_output(out)
    protocol=freeze(out);verify_timing_copy();sources=source_hashes();started=time.perf_counter()
    dump(out/'run_status.json',{'status':'running','source_sha256':sources})
    (out/'manifest.json').unlink(missing_ok=True)
    results=[];schedules=[]
    for model in protocol['models']:
        name=model['name'];stages={};t=time.perf_counter()
        J=fitness_ancestry(model['structure']);require(J==list(range(model['structure']['n'])),'Irrelevant coordinate padding detected')
        stages['fitness_ancestry_and_identity_quotient']=time.perf_counter()-t
        t=time.perf_counter();structural=structural_solve(model['structure']);stages['structural_decision_and_certificate_generation']=time.perf_counter()-t
        t=time.perf_counter()
        for query in ('full','growth'):
            require(check_certificate(structural[query]['certificate']),'Structural certificate rejected')
            got=structural[query]['horizon'] if structural[query]['status']=='finite' else structural[query]['status']
            require(got==model['expected_graphical_horizon'],'Unexpected graphical horizon')
        stages['structural_certificate_checking']=time.perf_counter()-t
        dump(out/'structural'/f'{name}.json',structural)
        row={'name':name,'n':model['structure']['n'],'fitness_ancestry_size':len(J),'actions':model['structure']['U'],
             'max_fitness_scope_arity':max(map(len,model['structure']['fac'][0])),
             'graphical_full_horizon':model['expected_graphical_horizon'],'graphical_growth_horizon':model['expected_graphical_horizon'],
             'reachable_pair_states':structural['exploration']['states_discovered'],'stages_seconds':stages}
        if model['expected_graphical_horizon']=='infinite':
            row.update(status='structurally_infinite_stop',weight_construction='not attempted',scheduling='not attempted',
                       interpretation='The graphical horizon is infinite; this check does not classify the selected numerical parameter point.')
            results.append(row);continue
        L=structural['growth']['horizon'];t=time.perf_counter();records,evidence=weights(model,L);stages['exact_history_weight_construction_and_all_column_verification']=time.perf_counter()-t
        dump(out/'weights'/f'{name}.json',{'model':model,'memory':L,'weights':records,'evidence':evidence})
        t=time.perf_counter();dense=dense_validate(model,L,records);stages['independent_dense_verification']=time.perf_counter()-t
        row.update(status='exact_weights_certified',weight_evidence=evidence,dense_verification=dense)
        for cname,con in constraints(model['structure']['U']).items():
            data={'actions':model['structure']['U'],'memory':L,'weights':records,'constraint':con}
            # The exact solver has reversible timing-only instrumentation;
            # an independent graph construction and all checks are timed separately.
            t=time.perf_counter();reference=ORACLE.reference_graph(data);graph_seconds=time.perf_counter()-t
            t=time.perf_counter();answer=schedule_solve(data,**LIMITS);combined_seconds=time.perf_counter()-t
            t=time.perf_counter();checked=verify_graph_and_cycles(data,answer);verification_seconds=time.perf_counter()-t
            answer['independent_checks']=checked
            dump(out/'scheduling'/f'{name}__{cname}.json',answer)
            schedules.append({'model':name,'constraint':cname,'constraint_states':con['states'],'memory':L,
                'status':answer['status'],'reason':answer['reason'],'reachable_history_states':answer['exploration']['states'],
                'history_edges':answer['exploration']['edges'],'viable_states':checked['viable_vertices'],
                'cycles_enumerated':answer['exploration']['cycles'],'cycle_steps':answer['exploration']['cycle_steps'],
                'minimum':answer['minimum'],'maximum':answer['maximum'],'independent_checks':checked,
                'stages_seconds':{'independent_graph_construction':graph_seconds,
                                  'model_and_graph_construction':answer['stage_seconds']['model_and_graph_construction'],
                                  'cycle_optimization':answer['stage_seconds']['cycle_optimization'],
                                  'combined_solver_wall':combined_seconds,
                                  'independent_graph_cycle_verification':verification_seconds}})
        results.append(row)
    require(source_hashes()==sources,'Sources changed during run')
    summary={'status':'completed','models':results,'scheduling':schedules,'source_sha256':sources,
       'environment':{'python':sys.version,'platform':platform.platform()},'elapsed_seconds':time.perf_counter()-started,
       'counts':{'structures':len(results),'finite_structures':sum(r['status']=='exact_weights_certified' for r in results),
                 'structurally_infinite_stops':sum(r['status']=='structurally_infinite_stop' for r in results),
                 'scheduling_cases':len(schedules),'optimal_scheduling_cases':sum(s['status']=='optimal' for s in schedules),
                 'unknown_scheduling_cases':sum(s['status']=='unknown' for s in schedules),
                 'weight_count':sum(r.get('weight_evidence',{}).get('weights',0) for r in results),
                 'all_column_ratio_evaluations':sum(r.get('weight_evidence',{}).get('all_column_ratio_evaluations',0) for r in results),
                 'dense_full_vector_comparisons':sum(r.get('dense_verification',{}).get('full_vector_comparisons',0) for r in results),
                 'dense_pure_growth_ratio_comparisons':sum(r.get('dense_verification',{}).get('pure_column_growth_ratio_comparisons',0) for r in results),
                 'dense_correlated_growth_ratio_comparisons':sum(r.get('dense_verification',{}).get('correlated_endpoint_mixture_ratio_comparisons',0) for r in results),
                 'independent_closed_walk_optimum_comparisons':sum(s['independent_checks']['independent_closed_walk_extrema_checked'] for s in schedules)},
       'limits_and_interpretation':protocol}
    dump(out/'summary.json',summary)
    with (out/'summary.csv').open('w',newline='') as f:
        keys=['name','n','fitness_ancestry_size','actions','max_fitness_scope_arity','graphical_full_horizon','graphical_growth_horizon','reachable_pair_states','status']
        writer=csv.DictWriter(f,keys);writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in results)
    with (out/'scheduling_summary.csv').open('w',newline='') as f:
        keys=['model','constraint','constraint_states','memory','status','reason','reachable_history_states','history_edges','viable_states','cycles_enumerated','cycle_steps']
        writer=csv.DictWriter(f,keys);writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in schedules)
    dump(out/'run_status.json',{'status':'completed','source_sha256':sources,'counts':summary['counts']})
    payloads={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    dump(out/'manifest.json',{'status':'sealed','source_sha256':sources,'artifact_sha256':payloads})
    print(json.dumps(summary['counts'],indent=2))


def verify(out):
    verify_timing_copy()
    manifest=json.loads((out/'manifest.json').read_text());require(manifest['status']=='sealed','Unsealed run')
    require(manifest['source_sha256']==source_hashes(),'Source provenance changed')
    for name,h in manifest['artifact_sha256'].items():require(sha(out/name)==h,'Recorded payload changed: '+name)
    require(json.loads((out/'run_status.json').read_text())['status']=='completed','Incomplete run')
    summary=json.loads((out/'summary.json').read_text())
    require(summary['source_sha256']==source_hashes(),'Summary source mismatch')
    require(summary['limits_and_interpretation']==json.loads((out/'protocol.json').read_text()),'Protocol mismatch')
    for r in summary['models']:
        data=json.loads((out/'structural'/f"{r['name']}.json").read_text())
        for query in ('full','growth'):require(check_certificate(data[query]['certificate']),'Recorded certificate rejected')
    print(json.dumps({'status':'verified','artifact_count':len(manifest['artifact_sha256']),'counts':summary['counts']}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUT);ap.add_argument('--freeze-only',action='store_true');ap.add_argument('--verify-recorded',action='store_true');args=ap.parse_args()
    if args.freeze_only:
        sys.path.insert(0,str(ROOT/"studies"))
        from output_guard import fresh_output
        freeze(fresh_output(args.output));print('Protocol frozen')
    elif args.verify_recorded:verify(args.output)
    else:run(args.output)

if __name__=='__main__':main()
