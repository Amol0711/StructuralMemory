"""Union-graph prechecks and a separate bounded pair-lasso demonstration.

A labeled directed cycle produces arbitrarily long active directed paths
from an initial root. For a growth query append a labeled path to a declared
fitness coordinate. Conditioning on separate sink fitness leaves cannot
block these directed paths. Graphical reset persists at longer lengths, so
arbitrarily long connected queries exclude every finite uniform horizon.

Outputs concern all words in the unrestricted alphabet, not a constrained
language and not actual numerical horizons for arbitrary parameter values.
Only the empty-fitness and zero-coordinate shortcuts assert finite values.
Union-graph traversal is linear in the explicit graph and scope input.
This adapter also validates and serializes bit-mask structures; their
unbounded-integer operations are not assigned unit bit cost. The optional
pair-lasso probe has a different, explicitly bounded cost.
"""
from collections import deque

from compact_memory.model import Structure, initial_state, transition

SCHEMA = "structural-memory.union-certificate.v1"
RESULT_SCHEMA = "structural-memory.union-precheck.v1"
SEMANTICS = "graphical-unrestricted"


def _bits(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _validated(structure):
    return structure if isinstance(structure, Structure) else Structure.from_dict(structure)


def _union(structure):
    """Preserve first encountered action labels without sorting edge lists."""
    outgoing = [[] for _ in range(structure.n)]
    incoming = [[] for _ in range(structure.n)]
    labels = {}
    parent_entries = 0
    for action, rows in enumerate(structure.pa):
        for child, mask in enumerate(rows):
            for parent in _bits(mask):
                parent_entries += 1
                if (parent, child) not in labels:
                    labels[parent, child] = action
                    outgoing[parent].append(child)
                    incoming[child].append(parent)
    targets = {}
    scope_entries = 0
    for action, scopes in enumerate(structure.fac):
        for factor, mask in enumerate(scopes):
            for coordinate in _bits(mask):
                scope_entries += 1
                targets.setdefault(coordinate, (action, factor))
    ancestors = set(targets)
    todo = deque(targets)
    while todo:
        for parent in incoming[todo.popleft()]:
            if parent not in ancestors:
                ancestors.add(parent)
                todo.append(parent)
    return outgoing, labels, targets, ancestors, parent_entries, scope_entries


def _cycle(outgoing, labels, allowed):
    """Iterative DFS, returning vertices with a repeated closing endpoint."""
    color = [0] * len(outgoing)
    parent = {}
    for start in range(len(outgoing)):
        if start not in allowed or color[start]:
            continue
        color[start] = 1
        stack = [(start, 0)]
        while stack:
            vertex, position = stack[-1]
            if position == len(outgoing[vertex]):
                color[vertex] = 2
                stack.pop()
                continue
            stack[-1] = vertex, position + 1
            child = outgoing[vertex][position]
            if child not in allowed:
                continue
            action = labels[vertex, child]
            if color[child] == 0:
                color[child] = 1
                parent[child] = vertex, action
                stack.append((child, 0))
            elif color[child] == 1:
                vertices = [vertex]
                actions = []
                current = vertex
                while current != child:
                    previous, edge_action = parent[current]
                    vertices.append(previous)
                    actions.append(edge_action)
                    current = previous
                vertices.reverse()
                actions.reverse()
                vertices.append(child)
                actions.append(action)
                return {"vertices": vertices, "actions": actions}
    return None


def _target_path(start, outgoing, labels, targets):
    predecessor = {start: None}
    todo = deque([start])
    while todo:
        vertex = todo.popleft()
        if vertex in targets:
            vertices = [vertex]
            actions = []
            current = vertex
            while predecessor[current] is not None:
                previous, action = predecessor[current]
                actions.append(action)
                vertices.append(previous)
                current = previous
            vertices.reverse()
            actions.reverse()
            action, factor = targets[vertex]
            return ({"vertices": vertices, "actions": actions},
                    {"action": action, "factor": factor, "coordinate": vertex})
        for child in outgoing[vertex]:
            if child not in predecessor:
                predecessor[child] = vertex, labels[vertex, child]
                todo.append(child)
    raise RuntimeError("A cycle in fitness ancestry has no path to fitness")


def _certificate(structure, query, horizon, proof):
    return {"schema": SCHEMA, "semantics": SEMANTICS,
            "structure": structure.to_dict(), "query": query,
            "status": "infinite" if horizon == "infinite" else "finite",
            "horizon": None if horizon == "infinite" else horizon,
            "proof": proof}


def precheck(structure):
    """Return original graphical horizons 0/'infinite'/None and certificates.

    None means this shortcut is inconclusive, never that the horizon is
    finite. J is fitness ancestry in the whole union graph. Certificate
    verification is a distinct operation; benchmark callers must time it
    separately and bind certificates to the requested structure.
    """
    structure = _validated(structure)
    outgoing, labels, targets, ancestors, pe, se = _union(structure)
    horizons = {"full": None, "growth": None}
    certificates = {"full": None, "growth": None}
    if structure.n == 0:
        horizons["full"] = 0
        certificates["full"] = _certificate(structure, "full", 0,
                                              {"type": "zero_coordinates"})
    if not targets:
        horizons["growth"] = 0
        certificates["growth"] = _certificate(structure, "growth", 0,
                                                {"type": "empty_fitness"})
    whole_cycle = _cycle(outgoing, labels, set(range(structure.n)))
    if whole_cycle is not None:
        horizons["full"] = "infinite"
        certificates["full"] = _certificate(structure, "full", "infinite",
                                 {"type": "union_cycle", "cycle": whole_cycle})
    if targets:
        relevant_cycle = _cycle(outgoing, labels, ancestors)
        if relevant_cycle is not None:
            path, target = _target_path(relevant_cycle["vertices"][0],
                                       outgoing, labels, targets)
            horizons["growth"] = "infinite"
            certificates["growth"] = _certificate(structure, "growth", "infinite",
                {"type": "cycle_to_fitness", "cycle": relevant_cycle,
                 "path": path, "target": target})
    return {"schema": RESULT_SCHEMA, "semantics": SEMANTICS,
            "structure": structure.to_dict(),
            "J": [i for i in range(structure.n) if i in ancestors],
            "horizons": horizons, "certificates": certificates,
            "unresolved": [q for q in ("full", "growth") if horizons[q] is None],
            "stats": {"union_edges": len(labels), "input_parent_entries": pe,
                      "input_scope_entries": se}}


def early_self_loop_certificates(structure):
    """Probe prefix lengths zero/one for one-action bad pair-state loops.

    This is not part of precheck(). It is a bounded explanatory probe, not
    a complete infinity decision. Generated certificates use the existing
    pair-certificate schema and can be checked by its independent checker.
    At most (U+1)*U + U pair updates are evaluated; a null result is unknown.
    """
    structure = _validated(structure)
    start = initial_state(structure)
    prefixes = [([], start)]
    evaluated = 0
    for action in range(structure.U):
        prefixes.append(([action], transition(structure, start, action)))
        evaluated += 1
    certificates = {"full": None, "growth": None}
    unions = structure.fitness_unions
    for prefix, state in prefixes:
        for action in range(structure.U):
            successor = transition(structure, state, action)
            evaluated += 1
            if successor != state:
                continue
            for query in ("full", "growth"):
                if certificates[query] is not None:
                    continue
                next_action = None
                if query == "full":
                    bad = bool(state.root)
                else:
                    next_action = next((u for u, target in enumerate(unions)
                                        if state.root & target), None)
                    bad = next_action is not None
                if bad:
                    certificates[query] = {
                        "schema": "structural-memory.pair-certificate.v1",
                        "structure": structure.to_dict(), "query": query,
                        "status": "infinite", "horizon": None,
                        "proof": {"type": "lasso", "prefix": prefix,
                                  "cycle": [action], "suffix": [],
                                  "next_action": next_action}}
            if all(certificates.values()):
                return {"certificates": certificates,
                        "pair_transition_evaluations": evaluated,
                        "complete_decision": False}
    return {"certificates": certificates, "pair_transition_evaluations": evaluated,
            "complete_decision": False}
