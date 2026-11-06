"""Exact but potentially exponential reachable-history/cycle enumeration."""
from collections import deque
from fractions import Fraction
from .model import as_model, integer, encode


SCHEMA = 'structural-memory.constrained-scheduling.v1'


def _prefix(vertex, predecessors, seed_origins):
    labels = []
    while predecessors[vertex] is not None:
        vertex, action = predecessors[vertex]
        labels.append(action)
    origin, warmup = seed_origins[vertex]
    return origin, list(warmup) + list(reversed(labels))


def compare_means(product1, length1, product2, length2):
    """Compare positive rational geometric means without computing roots/logs."""
    a, b = product1 ** length2, product2 ** length1
    return (a > b) - (a < b)


def solve(model, *, max_states=10000, max_edges=100000, max_cycles=100000,
          max_warmup_steps=100000, max_cycle_steps=1000000):
    model = as_model(model)
    for name, value, lower in [('max_states',max_states,1),('max_edges',max_edges,0),
                              ('max_cycles',max_cycles,0),('max_warmup_steps',max_warmup_steps,0),
                              ('max_cycle_steps',max_cycle_steps,0)]:
        integer(value, name, lower)
    limits = dict(max_states=max_states,max_edges=max_edges,max_cycles=max_cycles,
                  max_warmup_steps=max_warmup_steps,max_cycle_steps=max_cycle_steps)
    stats = dict(warmup_steps=0, states=0, edges=0, cycle_steps=0, cycles=0,
                 graph_complete=False, cycle_search_complete=False, limits=limits)
    result = {'schema':SCHEMA,'model':model.to_dict(),'status':None,'reason':None,
              'minimum':None,'maximum':None,'exploration':stats,'graph':None}

    def stop(reason):
        result.update(status='unknown',reason=reason)
        return result

    # A seed carries an actual legal length-L word and its initial automaton state.
    frontier = {((),q):q for q in model.constraint.initial}
    if len(frontier) > max_states:
        return stop('max_states_warmup')
    for _ in range(model.memory):
        following = {}
        for (word,q), origin in frontier.items():
            for a in range(model.actions):
                if stats['warmup_steps'] >= max_warmup_steps:
                    return stop('max_warmup_steps')
                stats['warmup_steps'] += 1
                r = model.constraint.next[q][a]
                if r is not None:
                    key = (word+(a,),r)
                    if key not in following:
                        if len(following) >= max_states:
                            return stop('max_states_warmup')
                        following[key] = origin
        frontier = following
        if not frontier:
            result.update(status='infeasible',reason='no_legal_length_memory_prefix')
            stats.update(graph_complete=True,cycle_search_complete=True)
            result['graph']={'states':[],'edges':[],'initial':[],'viable':[]}
            return result
    states = list(frontier)
    ids = {state:i for i,state in enumerate(states)}
    predecessors = [None] * len(states)
    seed_origins = {i:(frontier[state],state[0]) for i,state in enumerate(states)}
    initial = list(range(len(states)))
    edges, adjacency = [], [[] for _ in states]
    stats['states'] = len(states)
    cursor = 0

    def graph_snapshot(viable=None):
        return {'states':[{'history':list(w),'constraint':q} for w,q in states],
                'edges':[{'source':v,'action':a,'target':r,'weight':encode(g)} for v,a,r,g in edges],
                'initial':initial,'viable':viable}

    while cursor < len(states):
        word,q = states[cursor]
        for a,r in enumerate(model.constraint.next[q]):
            if r is None:
                continue
            if stats['edges'] >= max_edges:
                result['graph']=graph_snapshot()
                return stop('max_edges')
            successor = (model.successor_history(word,a),r)
            if successor not in ids:
                if len(states) >= max_states:
                    result['graph']=graph_snapshot()
                    return stop('max_states')
                ids[successor] = len(states)
                states.append(successor)
                predecessors.append((cursor,a))
                adjacency.append([])
                stats['states'] += 1
            target=ids[successor]
            adjacency[cursor].append(len(edges))
            edges.append((cursor,a,target,model.weight(word,a)))
            stats['edges'] += 1
        cursor += 1
    stats['graph_complete']=True
    reverse=[[] for _ in states]
    degree=[len(row) for row in adjacency]
    for v,a,r,g in edges:
        reverse[r].append(v)
    removed={i for i,d in enumerate(degree) if d==0}
    queue=deque(sorted(removed))
    while queue:
        r=queue.popleft()
        for v in reverse[r]:
            degree[v]-=1
            if degree[v]==0:
                removed.add(v);queue.append(v)
    viable=set(range(len(states)))-removed
    result['graph']=graph_snapshot(sorted(viable))
    if not viable:
        result.update(status='infeasible',reason='no_reachable_infinite_continuation')
        stats['cycle_search_complete']=True
        return result

    extrema={'minimum':None,'maximum':None}
    ties={'minimum':0,'maximum':0}
    # Every simple directed cycle is emitted once, at its least vertex id.
    # Different action edges are distinct even if endpoints coincide.
    for start in sorted(viable):
        stack=[(start,0)];visited={start};path=[]
        while stack:
            v,index=stack[-1]
            if index==len(adjacency[v]):
                stack.pop()
                if stack:
                    visited.remove(v);path.pop()
                continue
            if stats['cycle_steps'] >= max_cycle_steps:
                return stop('max_cycle_steps')
            stats['cycle_steps'] += 1
            stack[-1]=(v,index+1)
            edge_id=adjacency[v][index]
            _,action,r,g=edges[edge_id]
            if r not in viable:
                continue
            if r==start:
                if stats['cycles'] >= max_cycles:
                    return stop('max_cycles')
                stats['cycles'] += 1
                cycle_edges=path+[edge_id]
                product=Fraction(1)
                for e in cycle_edges:product*=edges[e][3]
                candidate=(product,len(cycle_edges),start,tuple(cycle_edges))
                for kind in extrema:
                    old=extrema[kind]
                    cmp=0 if old is None else compare_means(product,len(cycle_edges),old[0],old[1])
                    better=old is None or (cmp<0 if kind=='minimum' else cmp>0)
                    if better:extrema[kind]=candidate;ties[kind]=1
                    elif cmp==0:ties[kind]+=1
            elif r>start and r not in visited:
                visited.add(r);path.append(edge_id);stack.append((r,0))
    stats['cycle_search_complete']=True
    if extrema['minimum'] is None:
        raise RuntimeError('Viable finite graph had no enumerated cycle')
    for kind,candidate in extrema.items():
        product,length,start,cycle_edges=candidate
        origin,prefix=_prefix(start,predecessors,seed_origins)
        result[kind]={'product':encode(product),'length':length,
                      'prefix':prefix,'cycle':[edges[e][1] for e in cycle_edges],
                      'initial_constraint_state':origin,'entry_state':start,
                      'cycle_edges':list(cycle_edges),'optimal_simple_cycles':ties[kind],
                      'unique_simple_cycle':ties[kind]==1}
    result['status']='optimal'
    return result
