"""Exact seeded local-table perturbation study for delayed population growth.

Only the Python standard library is required. The complete rational sample
artifact is written (or checked against the prescribed generator) before any
population or cycle calculation. The reported samples cover the fixed
parameter draws; separate exact corner calculations check the parameter box.
"""
from pathlib import Path
from fractions import Fraction as F
from itertools import product, permutations
from functools import cmp_to_key
import argparse,csv,hashlib,json,random

ROOT=Path(__file__).resolve().parent.parent
STATES8=tuple(product(range(2),repeat=3))
STATES4=tuple(product(range(2),repeat=2))
SEED=4612026
SAMPLES=256
DV=F(1,40)
DH=F(1,16)
ROOT_BITS=48


def require(test,message):
    if not test:raise RuntimeError(message)


def baseline():
    return {
      'x':[F(1,10),F(9,10)],
      'c':[[F(1,10),F(9,10)] for _ in range(2)],
      'f':[[F(3,2),F(1,4)],[F(1,4),F(3,2)]],
      'q':[[[(1+F(1,4)*(2*b-1)+F(1,8)*(2*a-1)+F(1,8)*(2*c-1))/2
              for b in range(2)] for c in range(2)] for a in range(2)]
    }


def make_sample_artifact():
    rng=random.Random(SEED);base=baseline();records=[]
    for sample_id in range(SAMPLES):
        draws=[rng.randint(-1024,1024) for _ in range(26)]
        k=0;x=[];c=[];f=[];q=[]
        for u in range(2):
            x.append(str(base['x'][u]+F(draws[k],1024)*DV));k+=1
        for u in range(2):
            row=[]
            for i in range(2):row.append(str(base['c'][u][i]+F(draws[k],1024)*DV));k+=1
            c.append(row)
        for u in range(2):
            row=[]
            for i in range(2):row.append(str(base['f'][u][i]+F(draws[k],1024)*DV));k+=1
            f.append(row)
        for u in range(2):
            action=[]
            for a in range(2):
                ar=[]
                for cc in range(2):
                    cr=[]
                    for b in range(2):
                        cr.append(str(base['q'][a][cc][b]+F(draws[k],1024)*DH));k+=1
                    ar.append(cr)
                action.append(ar)
            q.append(action)
        require(k==26,'sample generator dimension')
        records.append({'sample_id':sample_id,'integer_draws':draws,'x':x,'c':c,'f':f,'q':q})
    return {'schema':'population-growth.local-table-samples.v1','count':SAMPLES,'seed':SEED,
      'generator':'random.Random(seed).randint(-1024,1024), one draw per free entry',
      'draw_order':'x[u]; c[u,i]; f[u,i]; q[u,A,C,B], each index in lexicographic binary order',
      'visible_fitness_radius':str(DV),'hidden_radius':str(DH),
      'perturbation':'integer_draw / 1024 * entry radius','samples':records}


def load_tables(record):
    return ([F(x) for x in record['x']],[[F(x) for x in row] for row in record['c']],
      [[F(x) for x in row] for row in record['f']],
      [[[[F(x) for x in br] for br in cr] for cr in ar] for ar in record['q']])


def original_matrices(tables):
    x,c,f,q=tables;ms=[]
    for u in range(2):
        matrix=[]
        for A,C,B in STATES8:
            row=[]
            for a,cc,b in STATES8:
                px=x[u] if A else 1-x[u]
                pc=c[u][a] if C else 1-c[u][a]
                pb=q[u][a][cc][b] if B else 1-q[u][a][cc][b]
                row.append(f[u][cc]*px*pc*pb)
            matrix.append(row)
        ms.append(matrix)
    return ms


def visible_matrices(tables):
    # Built directly on four visible states: no marginalization of the 8-state
    # matrices and no call to the two-step edge formula.
    x,c,f,_=tables;ms=[]
    for u in range(2):
        matrix=[[F(0) for _ in STATES4] for _ in STATES4]
        for old_index,(old_a,old_c) in enumerate(STATES4):
            law_a=(1-x[u],x[u]);law_c=(1-c[u][old_a],c[u][old_a])
            for new_index,(new_a,new_c) in enumerate(STATES4):
                matrix[new_index][old_index]=f[u][old_c]*law_a[new_a]*law_c[new_c]
        ms.append(matrix)
    return ms


def matvec(m,z):
    return [sum((a*b for a,b in zip(row,z)),F(0)) for row in m]


def marginal(z):
    return [z[2*k]+z[2*k+1] for k in range(4)]


def dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))


def canonical_cycle(path):return min(path[i:]+path[:i] for i in range(len(path)))


def cycle_list(regime):
    vertices=STATES4
    if regime=='no11':vertices=tuple(v for v in vertices if v!=(1,1))
    if regime=='alternating':vertices=((0,1),(1,0))
    found=set()
    for length in range(1,len(vertices)+1):
        for path in permutations(vertices,length):
            closed=path+(path[0],);good=True
            for source,target in zip(closed,closed[1:]):
                if source[1]!=target[0]:good=False
                if regime=='no11' and source[1]==target[1]==1:good=False
                if regime=='alternating' and source[1]==target[1]:good=False
            if good:found.add(canonical_cycle(path))
    return sorted(found,key=lambda p:(len(p),p))


CYCLES={regime:cycle_list(regime) for regime in ('unrestricted','no11','alternating')}


def compare_roots(left,right):
    p,n=left;q,m=right
    a,b=p**m,q**n
    return (a>b)-(a<b)


def root_interval(value,degree,bits=ROOT_BITS):
    require(value>0 and degree>0,'positive root expected')
    # A dyadic bisection on an enclosing interval. All bound decisions are
    # exact rational power comparisons, not floating-point root estimates.
    lo=F(0);hi=F(1)
    while hi**degree<value:hi*=2
    for _ in range(bits):
        mid=(lo+hi)/2
        if mid**degree<=value:lo=mid
        else:hi=mid
    require(lo**degree<=value<=hi**degree,'invalid root enclosure')
    return lo,hi


def interval_record(interval):
    lo,hi=interval
    return {'lower':str(lo),'upper':str(hi),'decimal_lower':float(lo),'decimal_upper':float(hi)}


def evaluate(record):
    tables=load_tables(record);x,c,f,q=tables
    require(all(0<v<1 for v in x),'x positivity')
    require(all(0<v<1 for row in c for v in row),'c positivity')
    require(all(v>0 for row in f for v in row),'fitness positivity')
    require(all(0<q[u][a][cc][b]<1 for u,a,cc,b in product(range(2),repeat=4)),'q positivity')
    ms8=original_matrices(tables);ms4=visible_matrices(tables)
    # Matrix intertwining proves agreement for every initial vector and every
    # finite word at this numerical sample; direct two-step checks below also
    # verify the particular observable-memory identities used in scheduling.
    intertwining_checks=0
    for u in range(2):
        for j,(a,cc,b) in enumerate(STATES8):
            col8=[row[j] for row in ms8[u]];col4=[row[2*a+cc] for row in ms4[u]]
            require(marginal(col8)==col4,'matrix intertwining disagreement')
            require(sum(col8,F(0))==f[u][cc],'matrix fitness column sum')
            intertwining_checks+=4
    lower_one=min(abs(c[t][1]-c[t][0])*abs(f[a][1]-f[a][0]) for t,a in product(range(2),repeat=2))
    require(lower_one>=F(9,10),'one-step growth lower difference')
    one_step_checks=0
    for t,a in product(range(2),repeat=2):
        ratios=[]
        for initial_a in range(2):
            j=4*initial_a # deterministic visible A, C=0 and B=0
            col=[row[j] for row in ms8[t]]
            after=matvec(ms8[a],col)
            ratios.append(sum(after,F(0))/sum(col,F(0)))
        require(abs(ratios[1]-ratios[0])==abs(c[t][1]-c[t][0])*abs(f[a][1]-f[a][0]),'one-step witness mismatch')
        require(ratios[0]!=ratios[1],'unexpected horizon-one reset');one_step_checks+=1
    hidden_beta=min(q[u][a][cc][1]-q[u][a][cc][0] for u,a,cc in product(range(2),repeat=3))
    require(hidden_beta>=F(1,8),'hidden persistence coefficient')
    edges={};edge_records=[];initial_column_checks=0;mass_checks=0
    fitness_rows8=[[f[u][cc] for a,cc,b in STATES8] for u in range(2)]
    fitness_rows4=[[f[u][cc] for a,cc in STATES4] for u in range(2)]
    for s,t in product(range(2),repeat=2):
        r=(1-x[s])*c[t][0]+x[s]*c[t][1]
        for a in range(2):
            weight=(1-r)*f[a][0]+r*f[a][1];edges[(s,t),a]=weight
            baseline_weight=F(51,40) if a==s else F(19,40)
            require(abs(weight-baseline_weight)<=F(13,160),'analytic edge bound')
            edge_records.append({'history':[s,t],'action':a,'weight':str(weight),'absolute_error':str(abs(weight-baseline_weight))})
        for j,(old_a,old_c,old_b) in enumerate(STATES8):
            z8=matvec(ms8[t],[row[j] for row in ms8[s]])
            z4=matvec(ms4[t],[row[2*old_a+old_c] for row in ms4[s]])
            require(marginal(z8)==z4,'two-step quotient disagreement')
            den8=sum(z8,F(0));den4=sum(z4,F(0));require(den8==den4>0,'two-step mass disagreement');mass_checks+=1
            for a in range(2):
                # Summing a transition after selection gives the fitness row;
                # matrix column sums above independently establish this identity.
                num8=dot(fitness_rows8[a],z8);num4=dot(fitness_rows4[a],z4)
                require(num8==num4,'three-step quotient mass disagreement');mass_checks+=1
                require(num8/den8==edges[(s,t),a],'original two-step memory disagreement')
                require(num4/den4==edges[(s,t),a],'quotient two-step memory disagreement')
                initial_column_checks+=1
    regimes={}
    for regime,cycles in CYCLES.items():
        values=[]
        for path in cycles:
            pp=F(1);closed=path+(path[0],);labels=[]
            for src,dst in zip(closed,closed[1:]):pp*=edges[src,dst[1]];labels.append(dst[1])
            value=(pp,len(path));bounds=root_interval(*value)
            values.append({'histories':[''.join(map(str,v)) for v in path],'labels':labels,'product':str(pp),'length':len(path),
                           'geometric_mean_interval':interval_record(bounds),'_value':value,'_bounds':bounds})
        values.sort(key=cmp_to_key(lambda a,b:compare_roots(a['_value'],b['_value'])))
        lo,hi=values[0],values[-1]
        minimizers=[v for v in values if compare_roots(v['_value'],lo['_value'])==0]
        maximizers=[v for v in values if compare_roots(v['_value'],hi['_value'])==0]
        expected={'unrestricted':4,'no11':3,'alternating':2}[regime]
        require(len(minimizers)==1 and lo['length']==expected,'optimizing cycle failed to persist')
        if regime in ('unrestricted','no11'):require(lo['_value'][0]<1,'minimum lost decay')
        else:require(lo['_value'][0]>1,'alternation lost growth')
        if len(values)>1:
            gap=(values[1]['_bounds'][0]-lo['_bounds'][1],values[1]['_bounds'][1]-lo['_bounds'][0])
            require(gap[0]>0,'uncertified positive multiplier gap')
            gaprec=interval_record(gap)
            gaprec['expression']={'competitor_product':values[1]['product'],'competitor_length':values[1]['length'],
               'optimizer_product':lo['product'],'optimizer_length':lo['length'],'operation':'competitor positive root minus optimizer positive root'}
        else:gaprec={'status':'no_competing_simple_cycle'}
        regimes[regime]={'minimum':{k:v for k,v in lo.items() if not k.startswith('_')},
          'maximum':{k:v for k,v in hi.items() if not k.startswith('_')},'minimizing_cycle_count':len(minimizers),
          'maximizing_cycle_count':len(maximizers),'optimizer_gap_interval':gaprec,
          'cycles':[{k:v for k,v in v.items() if not k.startswith('_')} for v in values]}
    return {'sample_id':record['sample_id'],'status':'passed','growth_horizon':2,
       'full_horizon':'infinite by positive hidden-path coefficient criterion',
       'one_step_difference_minimum':str(lower_one),'hidden_path_coefficient_minimum':str(hidden_beta),
       'edge_records':edge_records,'regimes':regimes,'counts':{'matrix_intertwining_entries':intertwining_checks,
       'one_step_witnesses':one_step_checks,'two_step_initial_column_growth_checks':initial_column_checks,
       'two_and_three_step_mass_checks':mass_checks}}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'reruns/perturbations')
    ap.add_argument('--freeze-only',action='store_true')
    args=ap.parse_args()
    from output_guard import fresh_output
    out=fresh_output(args.output);out.mkdir(parents=True,exist_ok=True)
    sample_path=out/'rational_samples.json'
    (out/'status.json').write_text(json.dumps({'status':'running','phase':'sample validation'})+'\n')
    try:
        generated=make_sample_artifact();sample_bytes=(json.dumps(generated,sort_keys=True,indent=2)+'\n').encode()
        if sample_path.exists():require(sample_path.read_bytes()==sample_bytes,'Existing sample artifact differs from frozen generator')
        else:sample_path.write_bytes(sample_bytes)
        sample_sha=hashlib.sha256(sample_bytes).hexdigest()
        freeze={'schema':'population-growth.sample-freeze.v1','sample_file':'rational_samples.json','sha256':sample_sha,
          'samples':SAMPLES,'free_entries_per_sample':26,'frozen_before_evaluation':True}
        (out/'sample_freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
    except Exception as exc:
        (out/'status.json').write_text(json.dumps({'status':'failed','phase':'sample validation','error':str(exc)},indent=2)+'\n')
        raise
    if args.freeze_only:
        (out/'status.json').write_text(json.dumps({'status':'samples_frozen','sample_sha256':sample_sha})+'\n')
        print(json.dumps(freeze));return
    # Reopen the frozen artifact. Evaluation does not use an in-memory
    # generator object and cannot silently redraw a difficult sample.
    artifact=json.loads(sample_path.read_text())
    results=[]
    (out/'status.json').write_text(json.dumps({'status':'running','sample_sha256':sample_sha})+'\n')
    try:
        for rec in artifact['samples']:
            results.append(evaluate(rec))
        totals={key:sum(r['counts'][key] for r in results) for key in results[0]['counts']}
        regime_summary={}
        for regime in CYCLES:
            entries=[r['regimes'][regime] for r in results]
            minimum_low=min(F(e['minimum']['geometric_mean_interval']['lower']) for e in entries)
            minimum_high=max(F(e['minimum']['geometric_mean_interval']['upper']) for e in entries)
            maximum_low=min(F(e['maximum']['geometric_mean_interval']['lower']) for e in entries)
            maximum_high=max(F(e['maximum']['geometric_mean_interval']['upper']) for e in entries)
            ss={'samples':SAMPLES,'simple_cycle_count':len(CYCLES[regime]),'optimizer_preserved_samples':SAMPLES,
                'minimum_multiplier_enclosing_range':interval_record((minimum_low,minimum_high)),
                'maximum_multiplier_enclosing_range':interval_record((maximum_low,maximum_high))}
            if regime!='alternating':
                gap_l=min(F(e['optimizer_gap_interval']['lower']) for e in entries)
                gap_h=min(F(e['optimizer_gap_interval']['upper']) for e in entries)
                ss['smallest_sample_optimizer_gap_interval']=interval_record((gap_l,gap_h))
            regime_summary[regime]=ss
        summary={'schema':'population-growth.local-table-study.v1','status':'passed','samples':SAMPLES,
           'sample_sha256':sample_sha,'all_samples_evaluated':len(results)==SAMPLES,'exact_arithmetic':'fractions.Fraction',
           'sample_generation_checked':True,'cycle_comparison':'exact rational integer cross powers',
           'root_enclosures':'48 exact dyadic bisections of a positive enclosing interval; printed decimals are illustrative only',
           'growth_memory_two_samples':SAMPLES,'hidden_persistence_criterion_samples':SAMPLES,
           'max_sample_absolute_edge_error':str(max(F(e['absolute_error']) for r in results for e in r['edge_records'])),
           'minimum_sample_one_step_difference':str(min(F(r['one_step_difference_minimum']) for r in results)),
           'minimum_sample_hidden_coefficient':str(min(F(r['hidden_path_coefficient_minimum']) for r in results)),
           'counts':totals,'regimes':regime_summary,
           'limitations':'The finite seeded sample study checks exact matrix identities and numerical cycle rates for the recorded parameter points. Separate corner computations check the specified parameter box. No outside-box or biological calibration conclusion is drawn.'}
        (out/'sample_results.json').write_text(json.dumps({'sample_sha256':sample_sha,'samples':results},sort_keys=True,indent=2)+'\n')
        (out/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
        rows=[]
        for r in results:
            for regime,e in r['regimes'].items():
                row={'sample_id':r['sample_id'],'regime':regime,'minimum_product':e['minimum']['product'],
                  'minimum_length':e['minimum']['length'],'minimum_mean_lower':e['minimum']['geometric_mean_interval']['lower'],
                  'minimum_mean_upper':e['minimum']['geometric_mean_interval']['upper'],
                  'maximum_product':e['maximum']['product'],'maximum_length':e['maximum']['length'],
                  'maximum_mean_lower':e['maximum']['geometric_mean_interval']['lower'],
                  'maximum_mean_upper':e['maximum']['geometric_mean_interval']['upper'],
                  'optimizer_gap_lower':e['optimizer_gap_interval'].get('lower',''),
                  'optimizer_gap_upper':e['optimizer_gap_interval'].get('upper','')}
                rows.append(row)
        with (out/'cycle_extrema.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,list(rows[0]));w.writeheader();w.writerows(rows)
        (out/'status.json').write_text(json.dumps({'status':'passed','sample_sha256':sample_sha,'samples':SAMPLES},indent=2)+'\n')
        print(json.dumps(summary,sort_keys=True,indent=2))
    except Exception as exc:
        (out/'status.json').write_text(json.dumps({'status':'failed','sample_sha256':sample_sha,'completed_samples':len(results),'error':str(exc)},indent=2)+'\n')
        raise

if __name__=='__main__':main()
