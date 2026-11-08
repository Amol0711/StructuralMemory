"""Independent replay checker for structural-memory horizon certificates.

This module deliberately imports neither the production pair-state transition
nor the reachable-graph solver.  Structural inputs and serialized states are
decoded independently, and transitions are recomputed using ordinary sets.

A finite certificate supplies a transition-closed reachable graph, an integer
ranking that bounds every continuation ending at a bad state, and a word
attaining that bound.  An infinite certificate supplies a checked lasso with
a bad-query continuation.  Unknown or malformed data is never a certificate.

``check_certificate`` returns False for invalid data.  Resource exhaustion is
allowed to raise; it is never converted into an accepted proof.  The command
line interface emits a JSON verdict and exits 0 for valid, 1 for invalid and
2 for a file/JSON/checking error.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCHEMA = "structural-memory.pair-certificate.v1"


class CertificateError(ValueError):
    """The supplied data does not satisfy the certificate contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CertificateError(message)


def _object(value: object, keys: set[str], name: str) -> dict:
    _require(type(value) is dict, f"{name} must be an object")
    _require(all(type(k) is str for k in value), f"{name} keys must be strings")
    _require(set(value) == keys, f"{name} has missing or unexpected fields")
    return value


def _array(value: object, name: str, length: int | None = None) -> list:
    _require(type(value) is list, f"{name} must be an array")
    if length is not None:
        _require(len(value) == length, f"{name} has the wrong length")
    return value


def _integer(value: object, name: str, minimum: int = 0,
             maximum: int | None = None) -> int:
    # bool is an int subclass, but is not an action, index, mask or horizon.
    _require(type(value) is int, f"{name} must be an integer")
    _require(value >= minimum, f"{name} is below its allowed range")
    if maximum is not None:
        _require(value <= maximum, f"{name} is above its allowed range")
    return value


def _coordinates(value: object, n: int, name: str) -> frozenset[int]:
    entries = _array(value, name)
    for v in entries:
        _integer(v, name + " coordinate", maximum=n - 1)
    # Parent/scope inputs denote sets. Repeated coordinates are harmless,
    # whereas repeated scope *leaves* are retained by _structure below.
    return frozenset(entries)


def _structure(value: object) -> tuple:
    data = _object(value, {"n", "U", "pa", "fac"}, "structure")
    n = _integer(data["n"], "n")
    action_count = _integer(data["U"], "U", minimum=1)
    parent_actions = _array(data["pa"], "pa", action_count)
    factor_actions = _array(data["fac"], "fac", action_count)
    parents, factors = [], []
    for action in range(action_count):
        rows = _array(parent_actions[action], f"pa[{action}]", n)
        parents.append(tuple(_coordinates(row, n, f"pa[{action}][{i}]")
                             for i, row in enumerate(rows)))
        scopes = _array(factor_actions[action], f"fac[{action}]")
        factors.append(tuple(_coordinates(scope, n, f"fac[{action}][{k}]")
                             for k, scope in enumerate(scopes)))
    targets = tuple(frozenset().union(*scopes) for scopes in factors)
    return n, action_count, tuple(parents), tuple(factors), targets


def _initial(structure: tuple) -> tuple[frozenset[int], frozenset[tuple[int, int]]]:
    vertices = frozenset(range(structure[0]))
    return vertices, frozenset((i, j) for i in vertices for j in vertices)


def _state(value: object, n: int, name: str) -> tuple:
    data = _object(value, {"root", "pairs"}, name)
    root_mask = _integer(data["root"], name + ".root")
    _require(root_mask.bit_length() <= n, name + ".root exceeds the coordinates")
    rows = _array(data["pairs"], name + ".pairs", n)
    for row in rows:
        _integer(row, name + ".pairs row")
        _require(row.bit_length() <= n, name + ".pairs exceeds the coordinates")
    root = frozenset(i for i in range(n) if (root_mask >> i) & 1)
    relation = frozenset((i, j) for i in range(n) for j in range(n)
                         if (rows[i] >> j) & 1)
    _require(all((i, i) in relation for i in range(n)), name + " is not reflexive")
    _require(all((j, i) in relation for i, j in relation), name + " is not symmetric")
    _require(all((i, j) in relation for i in root for j in root),
             name + " does not contain the root clique")
    return root, relation


def _step(structure: tuple, state: tuple, action: int) -> tuple:
    """Recompute one transition with sets, independently of production code."""
    n, _, parents, factors, _ = structure
    rooted, relation = set(state[0]), set(state[1])
    for scope in factors[action]:
        neighbors = {j for i, j in relation if i in scope}
        # The marking test uses the original scope, not its neighborhood.
        touches_root = bool(rooted.intersection(scope))
        relation.update((i, j) for i in neighbors for j in neighbors)
        if touches_root:
            rooted.update(neighbors)

    action_parents = parents[action]
    new_root = frozenset(i for i, parent_set in enumerate(action_parents)
                         if rooted.intersection(parent_set))
    new_relation = {(i, i) for i in range(n)}
    for i, left_parents in enumerate(action_parents):
        shared_ancestors = {q for p, q in relation if p in left_parents}
        for j, right_parents in enumerate(action_parents):
            if shared_ancestors.intersection(right_parents):
                new_relation.add((i, j))
    return new_root, frozenset(new_relation)


def _word(value: object, action_count: int, name: str) -> list[int]:
    word = _array(value, name)
    for action in word:
        _integer(action, name + " action", maximum=action_count - 1)
    return word


def _replay(structure: tuple, state: tuple, word: list[int]) -> tuple:
    for action in word:
        state = _step(structure, state, action)
    return state


def _bad(structure: tuple, state: tuple, query: str) -> bool:
    if query == "full":
        return bool(state[0])
    return any(state[0].intersection(target) for target in structure[4])


def _check_bad_witness(structure: tuple, state: tuple, query: str,
                       next_action: object) -> None:
    if query == "full":
        _require(next_action is None, "full witness must have no next action")
        _require(bool(state[0]), "full witness ends at a separated state")
    else:
        action = _integer(next_action, "witness next action",
                          maximum=structure[1] - 1)
        _require(bool(state[0].intersection(structure[4][action])),
                 "growth witness is separated for its specified next action")


def _finite(structure: tuple, query: str, horizon: object, value: object) -> None:
    h = _integer(horizon, "finite horizon")
    proof = _object(value, {"type", "states", "transitions", "initial", "rank",
                            "witness_word", "witness_next_action"}, "finite proof")
    _require(type(proof["type"]) is str and proof["type"] == "closed_graph_rank",
             "wrong finite proof type")
    initial_id = _integer(proof["initial"], "initial state id", maximum=0)
    serialized = _array(proof["states"], "states")
    _require(bool(serialized), "finite proof has no states")
    states = [_state(v, structure[0], f"states[{i}]")
              for i, v in enumerate(serialized)]
    _require(len(set(states)) == len(states), "serialized states are not unique")
    _require(states[initial_id] == _initial(structure), "wrong initial pair state")
    count = len(states)
    transitions = _array(proof["transitions"], "transitions", count)
    ranks = _array(proof["rank"], "rank", count)
    for rank in ranks:
        _integer(rank, "rank entry", minimum=-1)
    for i, row in enumerate(transitions):
        _array(row, f"transitions[{i}]", structure[1])
        for action, successor in enumerate(row):
            _integer(successor, "successor id", maximum=count - 1)
            _require(_step(structure, states[i], action) == states[successor],
                     "transition graph is not closed under the true update")
            if ranks[successor] >= 0:
                _require(ranks[i] > ranks[successor],
                         "rank does not strictly decrease towards a bad continuation")
        if _bad(structure, states[i], query):
            _require(ranks[i] >= 0, "a bad state has rank -1")

    reachable, stack = {initial_id}, [initial_id]
    while stack:
        for successor in transitions[stack.pop()]:
            if successor not in reachable:
                reachable.add(successor)
                stack.append(successor)
    _require(len(reachable) == count, "finite certificate contains unreachable states")
    _require(ranks[initial_id] == h - 1, "horizon and initial rank disagree")
    if h == 0:
        _require(proof["witness_word"] is None, "zero horizon must have no bad-word witness")
        _require(proof["witness_next_action"] is None, "zero horizon must have no next-action witness")
    else:
        word = _word(proof["witness_word"], structure[1], "witness word")
        _require(len(word) == h - 1, "bad witness does not establish the asserted least horizon")
        endpoint = _replay(structure, _initial(structure), word)
        _check_bad_witness(structure, endpoint, query, proof["witness_next_action"])


def _infinite(structure: tuple, query: str, horizon: object, value: object) -> None:
    _require(horizon is None, "infinite horizon must be null")
    proof = _object(value, {"type", "prefix", "cycle", "suffix", "next_action"},
                    "infinite proof")
    _require(type(proof["type"]) is str and proof["type"] == "lasso",
             "wrong infinite proof type")
    prefix = _word(proof["prefix"], structure[1], "prefix")
    cycle = _word(proof["cycle"], structure[1], "cycle")
    suffix = _word(proof["suffix"], structure[1], "suffix")
    _require(bool(cycle), "lasso cycle must be nonempty")
    entry = _replay(structure, _initial(structure), prefix)
    _require(_replay(structure, entry, cycle) == entry, "lasso cycle does not close")
    endpoint = _replay(structure, entry, suffix)
    _check_bad_witness(structure, endpoint, query, proof["next_action"])


def _verify(certificate: object) -> None:
    cert = _object(certificate, {"schema", "structure", "query", "status", "horizon", "proof"},
                   "certificate")
    _require(type(cert["schema"]) is str and cert["schema"] == SCHEMA,
             "unsupported certificate schema")
    _require(type(cert["query"]) is str and cert["query"] in {"full", "growth"},
             "unknown certificate query")
    _require(type(cert["status"]) is str and cert["status"] in {"finite", "infinite"},
             "only finite or infinite claims can carry a certificate")
    structure = _structure(cert["structure"])
    if cert["status"] == "finite":
        _finite(structure, cert["query"], cert["horizon"], cert["proof"])
    else:
        _infinite(structure, cert["query"], cert["horizon"], cert["proof"])


def check_certificate(certificate: object) -> bool:
    """Return whether a certificate independently proves its stated horizon.

    No solver output is trusted.  Invalid schema, structure, state, transition,
    rank or witness data returns False.  Memory exhaustion and interruptions
    propagate instead of producing any affirmative result.
    """
    try:
        _verify(certificate)
    except CertificateError:
        return False
    return True


def explain_certificate(certificate: object) -> dict:
    """Return a small JSON-compatible verdict with the first failure reason."""
    try:
        _verify(certificate)
    except CertificateError as exc:
        return {"valid": False, "error": str(exc)}
    return {"valid": True}


def _json_object(pairs: list) -> dict:
    """Reject ambiguous duplicate keys at every JSON object depth."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", help="certificate JSON path, or - for standard input")
    arguments = parser.parse_args(argv)
    try:
        source = sys.stdin.read() if arguments.certificate == "-" else Path(arguments.certificate).read_text()
        certificate = json.loads(source, object_pairs_hook=_json_object,
                                 parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("nonfinite JSON number: " + value)))
        verdict = explain_certificate(certificate)
    except (OSError, ValueError, MemoryError) as exc:
        print(json.dumps({"valid": False, "checking_error": type(exc).__name__ + ": " + str(exc)},
                         allow_nan=False))
        return 2
    print(json.dumps(verdict, allow_nan=False))
    return 0 if verdict["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
