"""Reachable pair-graph horizon solver with independently checkable proofs.

This implementation explicitly enumerates reachable states and returns
independently checkable certificates.
"""
from collections import deque

from .model import Structure, initial_state, transition


CERTIFICATE_SCHEMA = "structural-memory.pair-certificate.v1"
RESULT_SCHEMA = "structural-memory.compact-solver.v1"


def _budget(value, name, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")
    return value


def _prefix(predecessors, vertex):
    actions = []
    while vertex:
        parent, action = predecessors[vertex]
        actions.append(action)
        vertex = parent
    actions.reverse()
    return actions


def _cycle(transitions, allowed):
    """Find a directed cycle by an iterative depth-first traversal."""
    color = [0] * len(transitions)
    parent = {}
    for start in sorted(allowed):
        if color[start]:
            continue
        color[start] = 1
        stack = [(start, 0)]
        while stack:
            vertex, action = stack[-1]
            if action == len(transitions[vertex]):
                color[vertex] = 2
                stack.pop()
                continue
            stack[-1] = (vertex, action + 1)
            child = transitions[vertex][action]
            if child not in allowed:
                continue
            if color[child] == 0:
                parent[child] = (vertex, action)
                color[child] = 1
                stack.append((child, 0))
            elif color[child] == 1:
                actions = []
                current = vertex
                while current != child:
                    previous, edge_action = parent[current]
                    actions.append(edge_action)
                    current = previous
                actions.reverse()
                actions.append(action)
                return child, actions
    raise RuntimeError("Cycle detection disagrees with the topological test")


def _next_action(structure, state, query):
    if query == "full":
        return None
    for action, scope in enumerate(structure.fitness_unions):
        if scope & state.root:
            return action
    raise RuntimeError("A growth witness has no connected next-action query")


def _certificate(structure, query, status, horizon, proof):
    return {"schema": CERTIFICATE_SCHEMA, "structure": structure.to_dict(),
            "query": query, "status": status, "horizon": horizon,
            "proof": proof}


def _classify(structure, states, transitions, predecessors, reverse, query):
    target = 0
    for scope in structure.fitness_unions:
        target |= scope
    bad = [bool(s.root) if query == "full" else bool(s.root & target)
           for s in states]
    relevant = {v for v, value in enumerate(bad) if value}
    queue = deque(sorted(relevant))
    # The stored continuation follows discovery distance strictly downward.
    to_bad = {}
    while queue:
        child = queue.popleft()
        for vertex, action in reverse[child]:
            if vertex not in relevant:
                relevant.add(vertex)
                to_bad[vertex] = (action, child)
                queue.append(vertex)

    indegree = [0] * len(states)
    for vertex in relevant:
        for child in transitions[vertex]:
            if child in relevant:
                indegree[child] += 1
    queue = deque(sorted(v for v in relevant if indegree[v] == 0))
    topological = []
    while queue:
        vertex = queue.popleft()
        topological.append(vertex)
        for child in transitions[vertex]:
            if child in relevant:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

    if len(topological) != len(relevant):
        start, cycle = _cycle(transitions, relevant)
        suffix = []
        terminal = start
        while not bad[terminal]:
            action, terminal = to_bad[terminal]
            suffix.append(action)
        proof = {"type": "lasso", "prefix": _prefix(predecessors, start),
                 "cycle": cycle, "suffix": suffix,
                 "next_action": _next_action(structure, states[terminal], query)}
        return {"status": "infinite", "horizon": None,
                "certificate": _certificate(structure, query, "infinite", None, proof)}

    rank = [-1] * len(states)
    for vertex in reversed(topological):
        value = 0 if bad[vertex] else -1
        for child in transitions[vertex]:
            if rank[child] >= 0:
                value = max(value, 1 + rank[child])
        rank[vertex] = value
    horizon = rank[0] + 1
    witness = None
    terminal = None
    if horizon:
        witness = []
        terminal = 0
        while rank[terminal] > 0:
            choices = [(action, child) for action, child in enumerate(transitions[terminal])
                       if rank[child] == rank[terminal] - 1]
            if not choices:
                raise RuntimeError("Longest bad path could not be reconstructed")
            action, terminal = choices[0]
            witness.append(action)
        if not bad[terminal] or len(witness) != horizon - 1:
            raise RuntimeError("The reconstructed least-horizon witness is invalid")
    proof = {"type": "closed_graph_rank",
             "states": [state.to_dict() for state in states],
             "transitions": [list(row) for row in transitions], "initial": 0,
             "rank": rank, "witness_word": witness,
             "witness_next_action": None if terminal is None else
                 _next_action(structure, states[terminal], query)}
    return {"status": "finite", "horizon": horizon,
            "certificate": _certificate(structure, query, "finite", horizon, proof)}


def solve(structure, *, max_states=100000, max_transitions=1000000):
    """Return structural full/growth horizons and certificates or UNKNOWN.

    max_states must be >=1 and counts the initial state. max_transitions may
    be zero and limits transition evaluations. A state-budget stop can occur
    after evaluating one transition that cannot be stored; statistics retain
    that distinction. Both queries are conservatively unknown on any
    incomplete exploration. No resource stop is an infinity certificate.
    """
    if not isinstance(structure, Structure):
        structure = Structure.from_dict(structure)
    _budget(max_states, "max_states", 1)
    _budget(max_transitions, "max_transitions", 0)
    start = initial_state(structure)
    states = [start]
    identifiers = {start: 0}
    transitions = [[]]
    predecessors = [None]
    evaluated = 0
    stored = 0
    cursor = 0
    reason = None
    while cursor < len(states) and reason is None:
        for action in range(structure.U):
            if evaluated >= max_transitions:
                reason = "max_transitions"
                break
            successor = transition(structure, states[cursor], action)
            evaluated += 1
            child = identifiers.get(successor)
            if child is None:
                if len(states) >= max_states:
                    reason = "max_states"
                    break
                child = len(states)
                identifiers[successor] = child
                states.append(successor)
                transitions.append([])
                predecessors.append((cursor, action))
            transitions[cursor].append(child)
            stored += 1
        if reason is None:
            cursor += 1
    complete = reason is None
    exploration = {"complete": complete, "states_discovered": len(states),
                   "transitions_evaluated": evaluated, "transitions_stored": stored,
                   "fully_expanded_states": cursor,
                   "max_states": max_states, "max_transitions": max_transitions,
                   "stop_reason": reason,
                   "state_description_bits": structure.n * (structure.n + 1) // 2,
                   "implementation": "explicit reachable pair-state graph"}
    result = {"schema": RESULT_SCHEMA, "structure": structure.to_dict(),
              "exploration": exploration}
    if not complete:
        for query in ("full", "growth"):
            result[query] = {"status": "unknown", "horizon": None,
                             "certificate": None, "reason": reason}
        return result
    reverse = [[] for _ in states]
    for vertex, row in enumerate(transitions):
        for action, child in enumerate(row):
            reverse[child].append((vertex, action))
    for query in ("full", "growth"):
        result[query] = _classify(structure, states, transitions, predecessors, reverse, query)
    return result
