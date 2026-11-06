"""Exact arithmetic audit of the retained three-coordinate example.

The edge functions are multi-affine in five independent visible/fitness
entries, so their extrema on the rectangular box occur at its corners.
This checks a finite analytic reduction, not sampled robustness or a new
numerical study. No production solver or existing oracle is imported.
"""
from fractions import Fraction as F
from itertools import product, permutations
import json


def require(condition,message):
    if not condition:
        raise RuntimeError(message)


def canonical_cycle(cycle):
    return min(cycle[i:]+cycle[:i] for i in range(len(cycle)))


def cycles(regime):
    vertices=tuple(product(range(2),repeat=2))
    if regime=='no11':
        vertices=tuple(v for v in vertices if v!=(1,1))
    elif regime=='alternating':
        vertices=((0,1),(1,0))
    found=set()
    for length in range(1,len(vertices)+1):
        for path in permutations(vertices,length):
            closed=path+(path[0],)
            valid=True
            for source,target in zip(closed,closed[1:]):
                if source[1]!=target[0]:valid=False
                if regime=='no11' and source[1]==target[1]==1:valid=False
                if regime=='alternating' and source[1]==target[1]:valid=False
            if valid:found.add(canonical_cycle(path))
    return sorted(found,key=lambda x:(len(x),x))


def main():
    ell,h,e=F(19,40),F(51,40),F(13,160)
    dv,dh=F(1,40),F(1,16)
    x={0:F(1,10),1:F(9,10)}
    c={0:F(1,10),1:F(9,10)}
    f={(a,i):(F(3,2) if a==i else F(1,4)) for a,i in product(range(2),repeat=2)}
    require(F(1,10)+F(1,10)-2*F(1,10)**2==F(9,50),'baseline effective error')
    require((1-F(9,50))*F(3,2)+F(9,50)*F(1,4)==h,'baseline high edge')
    require((1-F(9,50))*F(1,4)+F(9,50)*F(3,2)==ell,'baseline low edge')
    edge_records=[];r_corners=g_corners=0
    for s,t in product(range(2),repeat=2):
        r0=(1-x[s])*c[0]+x[s]*c[1]
        rvalues=[]
        for signs in product((-1,1),repeat=3):
            xx,cc0,cc1=(base+sign*dv for base,sign in zip((x[s],c[0],c[1]),signs))
            rr=(1-xx)*cc0+xx*cc1;rvalues.append(rr);r_corners+=1
            require(abs(rr-r0)<=F(9,200),'entire-box r bound at a multi-affine corner')
        for a in range(2):
            baseline=(1-r0)*f[a,0]+r0*f[a,1]
            require(baseline==(h if a==s else ell),'eight baseline weights')
            values=[]
            for signs in product((-1,1),repeat=5):
                xx,cc0,cc1,ff0,ff1=(base+sign*dv for base,sign in zip((x[s],c[0],c[1],f[a,0],f[a,1]),signs))
                rr=(1-xx)*cc0+xx*cc1;gg=(1-rr)*ff0+rr*ff1
                require(abs(gg-baseline)<=e,'entire-box g bound at a multi-affine corner')
                values.append(gg);g_corners+=1
            edge_records.append({'history':[s,t],'action':a,'baseline':str(baseline),'corner_min':str(min(values)),
                                 'corner_max':str(max(values)),'maximum_absolute_error':str(max(abs(g-baseline) for g in values))})
    # All independent local transition/fitness entries remain strictly positive.
    visible_probability_interval=(F(1,10)-dv,F(9,10)+dv)
    fitness_interval=(F(1,4)-dv,F(3,2)+dv)
    hidden_baseline=[(1+F(1,4)*(2*b-1)+F(1,8)*(2*a-1)+F(1,8)*(2*c_-1))/2
                     for a,c_,b in product(range(2),repeat=3)]
    hidden_interval=(min(hidden_baseline)-dh,max(hidden_baseline)+dh)
    require(0<visible_probability_interval[0]<visible_probability_interval[1]<1,'visible probabilities')
    require(fitness_interval[0]>0,'positive fitness')
    require(hidden_interval==(F(3,16),F(13,16)),'hidden probability box')
    one_step=(F(4,5)-2*dv)*(F(5,4)-2*dv)
    hidden_slope=F(1,4)-2*dh
    require(one_step==F(9,10),'one-step nonreset separation')
    require(hidden_slope==F(1,8),'hidden path slope')
    cycle_records={}
    for regime,expected_count in [('unrestricted',6),('no11',3),('alternating',1)]:
        cc=cycles(regime);require(len(cc)==expected_count,'complete simple-cycle count: '+regime)
        records=[]
        for path in cc:
            closed=path+(path[0],);high=sum(source[0]==target[1] for source,target in zip(closed,closed[1:]))
            low=len(path)-high
            records.append({'histories':[''.join(map(str,v)) for v in path],
                            'labels':[target[1] for target in closed[1:]],'length':len(path),
                            'high_edges':high,'low_edges':low,'baseline_product':str(h**high*ell**low),
                            'interval_lower_product':str((h-e)**high*(ell-e)**low),
                            'interval_upper_product':str((h+e)**high*(ell+e)**low)})
        cycle_records[regime]=records
    unrestricted=cycle_records['unrestricted']
    candidates=[r for r in unrestricted if r['high_edges']==0]
    require(len(candidates)==1 and candidates[0]['length']==4,'unique all-low four-cycle')
    require(all(F(r['high_edges'],r['length'])>=F(1,3) for r in unrestricted if r['high_edges']),'competitor high-edge fraction')
    strict_gap=(ell-e)**2*(h-e)-(ell+e)**3
    require(strict_gap==F(5311,409600) and strict_gap>0,'unrestricted strict interval comparison')
    no11=cycle_records['no11'];three=[r for r in no11 if r['length']==3]
    require(len(three)==1 and three[0]['high_edges']==1 and three[0]['low_edges']==2,'no11 three-cycle edge types')
    require(all(r['low_edges']==0 for r in no11 if r['length']!=3),'no11 other cycles all high')
    no11_upper=(ell+e)**2*(h+e)
    require(ell**2*h==F(18411,64000)<1,'baseline no11 decay')
    require(no11_upper==F(1718857,4096000)<1,'no11 uniform box decay')
    require(ell+e==F(89,160)<1 and h-e==F(191,160)>1,'box decay/growth margins')
    require(cycle_records['alternating'][0]['high_edges']==2,'alternation high edges')
    answer={'status':'passed','purpose':'Exact corner arithmetic and complete finite-cycle checks for the specified parameter box.',
            'arithmetic':'fractions.Fraction; no floating point','oracle_imports':False,
            'r_corner_evaluations':r_corners,'edge_corner_evaluations':g_corners,
            'corner_reduction':'Each edge is separately affine in x_s, c_t0, c_t1, f_a0, f_a1. Interval extrema therefore occur at the 32 corners; absolute error is bounded by checking both extrema.',
            'edge_records':edge_records,'simple_cycles':cycle_records,
            'one_step_growth_difference_lower_bound':str(one_step),'hidden_path_slope_lower_bound':str(hidden_slope),
            'visible_probability_interval':list(map(str,visible_probability_interval)),
            'fitness_interval':list(map(str,fitness_interval)),'hidden_probability_interval':list(map(str,hidden_interval)),
            'unrestricted_strict_comparison':str(strict_gap),'no11_upper_period_product':str(no11_upper),
            'limitations':'The code checks the stated finite corner and cycle enumerations. Its outputs apply to the specified example and parameter box.'}
    print(json.dumps(answer,sort_keys=True))

if __name__=='__main__':main()
