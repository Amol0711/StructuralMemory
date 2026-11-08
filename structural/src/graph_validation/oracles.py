"""Independent finite-set component and unrolled-DAG comparison oracles.

No imports from compact_memory or the earlier verification implementations.
These bounded diagnostics corroborate, rather than prove, the mathematics.
"""
import itertools


def raw_initial(n):
    return [(True, frozenset([i])) for i in range(n)]


def raw_step(raw, parents, factors, n):
    # Track real components separately; roots are NOT collapsed here.
    groups = [(marked, set(support)) for marked, support in raw]
    for scope in factors:
        scope = set(scope)
        hit = [k for k, (_, support) in enumerate(groups) if support & scope]
        if not hit:
            continue
        marked = any(groups[k][0] for k in hit)
        support = set().union(*(groups[k][1] for k in hit))
        indices = set(hit)
        groups = [g for k, g in enumerate(groups) if k not in indices]
        groups.append((marked, support))
    result = []
    for marked, support in groups:
        new = frozenset(i for i, pa in enumerate(parents) if set(pa) & support)
        if new:
            result.append((marked, new))
    result.extend((False, frozenset([i])) for i in range(n))
    return result


def collapsed_pair(raw, n):
    root = set().union(*(set(s) for marked, s in raw if marked))
    supports = [set(s) for marked, s in raw if not marked] + [root]
    pairs = {(i, j) for support in supports for i in support for j in support}
    return sum(1 << i for i in root), tuple(
        sum(1 << j for j in range(n) if (i, j) in pairs) for i in range(n))


def unrolled(structure, word):
    n = structure['n']
    parents = {(t, i): set() for t in range(len(word)+1) for i in range(n)}
    evidence = set()
    for t, action in enumerate(word):
        for i, pa in enumerate(structure['pa'][action]):
            parents[t+1, i] = {(t, j) for j in pa}
        for k, scope in enumerate(structure['fac'][action]):
            leaf = ('leaf', t, k)
            parents[leaf] = {(t, j) for j in scope}
            evidence.add(leaf)
    return parents, evidence


def ancestor_closure(parents, nodes):
    seen, stack = set(), list(nodes)
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(parents[node])
    return seen


def connected_by_moralization(structure, word, targets):
    """Set-to-set d-connection, via ancestral moralization from first principles."""
    n = structure['n']
    sources = {(0, i) for i in range(n)}
    targets = {(len(word), i) for i in targets}
    if not sources or not targets:
        return False
    if sources & targets:
        return True
    parents, evidence = unrolled(structure, word)
    retained = ancestor_closure(parents, sources | targets | evidence)
    adjacency = {v: set() for v in retained}
    for child in retained:
        pa = parents[child]
        for p in pa:
            adjacency[child].add(p)
            adjacency[p].add(child)
        for p, q in itertools.combinations(pa, 2):
            adjacency[p].add(q)
            adjacency[q].add(p)
    seen, stack = set(), list(sources)
    while stack:
        node = stack.pop()
        if node in evidence or node in seen:
            continue
        if node in targets:
            return True
        seen.add(node)
        stack.extend(adjacency[node]-evidence-seen)
    return False


def scopes_union(structure, action):
    return set().union(*(set(f) for f in structure['fac'][action]))


def subsets(n, include_empty=True):
    return [frozenset(i for i in range(n) if mask & (1 << i))
            for mask in range(0 if include_empty else 1, 1 << n)]


def chain(n, *, factors='unary', actions=2):
    pa = [[[] if i == 0 else [i-1] for i in range(n)] for _ in range(actions)]
    if factors == 'none':
        fac = [[] for _ in range(actions)]
    elif factors == 'joint':
        fac = [[[0, 1]]] * actions if n >= 2 else [[[0]]] * actions
    else:
        fac = [[[n-1]]] * actions if n else [[] for _ in range(actions)]
    return {'n': n, 'U': actions, 'pa': pa, 'fac': fac}


def persistent(n, actions=2):
    return {'n': n, 'U': actions,
            'pa': [[[i] for i in range(n)] for _ in range(actions)],
            'fac': [[[0]] for _ in range(actions)] if n else [[] for _ in range(actions)]}
