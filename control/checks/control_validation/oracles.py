"""Independent exact population and finite-graph reference calculations.

No production verification modules are imported here.
"""
from fractions import Fraction as F
from itertools import product


def base_tables():
    x={0:F(1,10),1:F(9,10)}
    c={(u,i):F(1,10) if i==0 else F(9,10) for u in range(2) for i in range(2)}
    f={(u,i):F(3,2) if u==i else F(1,4) for u in range(2) for i in range(2)}
    b={(u,a,c_,b_):(1+F(1,4)*(2*b_-1)+F(1,8)*(2*a-1)+F(1,8)*(2*c_-1))/2
       for u in range(2) for a,c_,b_ in product(range(2),repeat=3)}
    return x,c,f,b


def matrices(tables=None):
    x,c,f,b=base_tables() if tables is None else tables
    states=list(product(range(2),repeat=3));answer=[]
    for u in range(2):
        matrix=[]
        for new in states:
            row=[]
            for old in states:
                ps=(x[u],c[u,old[0]],b[(u,*old)])
                q=F(1)
                for bit,p in zip(new,ps):q*=p if bit else 1-p
                row.append(q*f[u,old[1]])
            matrix.append(row)
        answer.append(matrix)
    return answer


def matvec(matrix,vector):
    return [sum((a*b for a,b in zip(row,vector)),F(0)) for row in matrix]


def rowmat(row,matrix):
    return [sum((row[i]*matrix[i][j] for i in range(len(row))),F(0)) for j in range(len(row))]


def mass(ms,word,p):
    z=list(p)
    for a in word:z=matvec(ms[a],z)
    return sum(z,F(0))


def mass_row(ms,word):
    row=[F(1)]*len(ms[0])
    for a in reversed(word):row=rowmat(row,ms[a])
    return row


def cycle_eigenrow(ms,word,period_product,memory=2):
    repeats=max(1,(memory+len(word)-1)//len(word))
    row=mass_row(ms,tuple(word)*repeats)
    rhs=list(row)
    for a in reversed(word):rhs=rowmat(rhs,ms[a])
    return all(v>0 for v in row) and rhs==[period_product*v for v in row]


def constraints():
    return {
      'unrestricted':{'states':1,'initial':[0],'next':[[0,0]]},
      'no11':{'states':2,'initial':[0],'next':[[0,1],[0,None]]},
      'alternating':{'states':2,'initial':[0,1],'next':[[None,1],[0,None]]},
      'transient_prefix':{'states':5,'initial':[0],'next':[[1,None],[2,None],[3,None],[4,None],[4,4]]},
      'unreachable_better':{'states':2,'initial':[0],'next':[[None,0],[1,None]]},
      'dead':{'states':3,'initial':[0],'next':[[1,None],[2,None],[None,None]]},
    }


def model_data(constraint=None,memory=2,weights=None):
    if constraint is None:constraint=constraints()['unrestricted']
    records=[]
    for hist in product(range(2),repeat=memory):
        for a in range(2):
            value=(F(51,40) if hist and a==hist[0] else F(19,40)) if weights is None else weights[hist,a]
            records.append({'history':list(hist),'action':a,'value':str(value)})
    return {'actions':2,'memory':memory,'weights':records,'constraint':constraint}


def weight_map(data):
    return {(tuple(x['history']),x['action']):F(x['value']) for x in data['weights']}


def constraint_viable(con):
    # Iteratively delete states with no remaining successor. This avoids
    # sharing production SCC/cycle detection or its product-state traversal.
    keep=set(range(con['states']))
    while True:
        smaller={q for q in keep if any(r in keep for r in con['next'][q] if r is not None)}
        if smaller==keep:return keep
        keep=smaller


def legal_words(con,actions,length,extendable=False):
    states={():set(con['initial'])}
    for _ in range(length):
        new={}
        for w,qs in states.items():
            for a in range(actions):
                nxt={con['next'][q][a] for q in qs if con['next'][q][a] is not None}
                if nxt:new[w+(a,)]=nxt
        states=new
    keep=constraint_viable(con)
    return {w:qs for w,qs in states.items() if not extendable or qs&keep}


def brute_finite(ms,data,p,T,extendable=False):
    values=[(mass(ms,w,p),w) for w in legal_words(data['constraint'],data['actions'],T,extendable)]
    if not values:return None
    return min(values),max(values)



def mass_tree(ms,data,p,max_length):
    """Propagate every legal word once in the original eight-state matrices."""
    con=data['constraint'];current={(): (set(con['initial']),list(p))}
    output={(): (set(con['initial']),sum(p,F(0)))}
    for _ in range(max_length):
        new={}
        for word,(qs,z) in current.items():
            for a in range(data['actions']):
                nxt={con['next'][q][a] for q in qs if con['next'][q][a] is not None}
                if nxt:
                    child=word+(a,);zz=matvec(ms[a],z)
                    new[child]=(nxt,zz);output[child]=(nxt,sum(zz,F(0)))
        current=new
    return output


def reference_graph(data):
    L,U=data['memory'],data['actions'];con=data['constraint'];weights=weight_map(data)
    warm=legal_words(con,U,L)
    initial={(w,q) for w,qs in warm.items() for q in qs}
    reached=set(initial);pending=list(initial);edges={}
    while pending:
        w,q=pending.pop();row=[]
        for a,r in enumerate(con['next'][q]):
            if r is None:continue
            target=((w+(a,))[-L:] if L else (),r)
            row.append((a,target,weights[w,a]))
            if target not in reached:reached.add(target);pending.append(target)
        edges[w,q]=row
    # No reachable infinite path iff the iterative outdegree core vanishes.
    viable=set(reached)
    while True:
        nxt={s for s in viable if any(t in viable for _,t,_ in edges[s])}
        if nxt==viable:break
        viable=nxt
    return initial,edges,viable


def compare_roots(left,right):
    """Compare positive roots (product,length) using rational integer powers."""
    a,n=left;b,m=right
    return (a**m>b**n)-(a**m<b**n)


def closed_walk_extrema(data):
    """Independent min/max closed-walk DP, not simple-cycle enumeration.

    A simple cycle has at most |V| edges. For each possible starting state,
    exact shortest/longest multiplicative closed walks of lengths 1..|V|
    therefore suffice to determine the two cycle means.
    """
    initial,edges,viable=reference_graph(data)
    if not viable:return None
    low=high=None
    for start in viable:
        lower={start:F(1)};upper={start:F(1)}
        for k in range(1,len(viable)+1):
            lo={};hi={}
            for source,pv in lower.items():
                for _,target,g in edges[source]:
                    if target in viable:lo[target]=min(lo.get(target,pv*g),pv*g)
            for source,pv in upper.items():
                for _,target,g in edges[source]:
                    if target in viable:hi[target]=max(hi.get(target,pv*g),pv*g)
            lower,upper=lo,hi
            if start in lower:
                value=(lower[start],k)
                if low is None or compare_roots(value,low)<0:low=value
            if start in upper:
                value=(upper[start],k)
                if high is None or compare_roots(value,high)>0:high=value
    return low,high


def replay_witness(data,answer):
    q=answer['initial_constraint_state'];con=data['constraint'];L=data['memory']
    if q not in con['initial']:return False
    prefix=tuple(answer['prefix']);cycle=tuple(answer['cycle'])
    if not cycle or len(prefix)<L:return False
    history=()
    for a in prefix:
        q=con['next'][q][a]
        if q is None:return False
        history=(history+(a,))[-L:] if L else ()
    start=(history,q);p=F(1);weights=weight_map(data)
    for a in cycle:
        p*=weights[history,a];q=con['next'][q][a]
        if q is None:return False
        history=(history+(a,))[-L:] if L else ()
    return (history,q)==start and p==F(answer['product']) and len(cycle)==answer['length']
