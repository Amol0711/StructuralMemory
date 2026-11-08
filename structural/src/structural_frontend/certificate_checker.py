"""Independent checker for union-cycle structural-memory certificates.

Imports neither the producer nor pair transitions/solver. Parent and scope
lists are decoded with ordinary sets. The optional expected_structure binds
the embedded claim to a requested input. Invalid data returns False; resource
exhaustion and interruptions propagate rather than accepting any claim.
"""
import argparse
import json
from pathlib import Path
import sys

SCHEMA = "structural-memory.union-certificate.v1"
SEMANTICS = "graphical-unrestricted"


class CertificateError(ValueError):
    """Certificate violates its explicit structural proof contract."""


def _require(condition, message):
    if not condition:
        raise CertificateError(message)


def _object(value, keys, name):
    _require(type(value) is dict, name + " must be an object")
    _require(all(type(k) is str for k in value), name + " keys must be strings")
    _require(set(value) == keys, name + " has missing or unexpected fields")
    return value


def _array(value, name, length=None):
    _require(type(value) is list, name + " must be an array")
    if length is not None:
        _require(len(value) == length, name + " has the wrong length")
    return value


def _integer(value, name, lower=0, upper=None):
    _require(type(value) is int, name + " must be an integer")
    _require(value >= lower, name + " is below its allowed range")
    if upper is not None:
        _require(value <= upper, name + " is above its allowed range")
    return value


def _coordinates(value, n, name):
    values = _array(value, name)
    for entry in values:
        _integer(entry, name + " coordinate", upper=n-1)
    return frozenset(values)


def _structure(value):
    data = _object(value, {"n", "U", "pa", "fac"}, "structure")
    n = _integer(data["n"], "n")
    count = _integer(data["U"], "U", lower=1)
    pa = _array(data["pa"], "pa", count)
    fac = _array(data["fac"], "fac", count)
    parents, factors = [], []
    for action in range(count):
        rows = _array(pa[action], "parent rows", n)
        parents.append(tuple(_coordinates(row, n, "parents") for row in rows))
        scopes = _array(fac[action], "fitness scopes")
        factors.append(tuple(_coordinates(scope, n, "scope") for scope in scopes))
    return n, count, tuple(parents), tuple(factors)


def _walk(value, structure, name, *, cycle):
    n, count, parents, _ = structure
    walk = _object(value, {"vertices", "actions"}, name)
    vertices = _array(walk["vertices"], name + " vertices")
    actions = _array(walk["actions"], name + " actions")
    _require(len(vertices) == len(actions)+1, name + " lengths disagree")
    _require(bool(vertices), name + " has no vertex")
    for vertex in vertices:
        _integer(vertex, name + " vertex", upper=n-1)
    for action in actions:
        _integer(action, name + " action", upper=count-1)
    if cycle:
        _require(bool(actions), "cycle must be nonempty")
        _require(vertices[0] == vertices[-1], "cycle does not close")
    for parent, child, action in zip(vertices, vertices[1:], actions):
        _require(parent in parents[action][child], name + " uses a missing labeled edge")
    return vertices


def _verify(certificate, expected_structure=None):
    cert = _object(certificate, {"schema", "semantics", "structure", "query",
                                "status", "horizon", "proof"}, "certificate")
    _require(type(cert["schema"]) is str and cert["schema"] == SCHEMA,
             "unsupported certificate schema")
    _require(type(cert["semantics"]) is str and cert["semantics"] == SEMANTICS,
             "certificate must concern unrestricted graphical horizons")
    _require(type(cert["query"]) is str and cert["query"] in {"full", "growth"},
             "unknown query")
    _require(type(cert["status"]) is str and cert["status"] in {"finite", "infinite"},
             "unknown claims cannot be certificates")
    structure = _structure(cert["structure"])
    if expected_structure is not None:
        _require(structure == _structure(expected_structure),
                 "embedded structure differs from requested structure")
    n, count, _, factors = structure
    if cert["status"] == "finite":
        _integer(cert["horizon"], "finite horizon", upper=0)
        proof = _object(cert["proof"], {"type"}, "zero-horizon proof")
        if cert["query"] == "full":
            _require(proof["type"] == "zero_coordinates", "wrong full zero proof")
            _require(n == 0, "nonzero coordinates cannot have zero full horizon")
        else:
            _require(proof["type"] == "empty_fitness", "wrong growth zero proof")
            _require(not any(scope for scopes in factors for scope in scopes),
                     "nonempty declared fitness support excludes graphical zero horizon")
        return
    _require(cert["horizon"] is None, "infinite horizon must be null")
    if cert["query"] == "full":
        proof = _object(cert["proof"], {"type", "cycle"}, "full cycle proof")
        _require(proof["type"] == "union_cycle", "wrong full cycle proof type")
        _walk(proof["cycle"], structure, "cycle", cycle=True)
        return
    proof = _object(cert["proof"], {"type", "cycle", "path", "target"},
                    "growth cycle proof")
    _require(proof["type"] == "cycle_to_fitness", "wrong growth cycle proof type")
    cycle = _walk(proof["cycle"], structure, "cycle", cycle=True)
    path = _walk(proof["path"], structure, "path", cycle=False)
    _require(path[0] == cycle[0], "fitness path does not start at the cycle base")
    target = _object(proof["target"], {"action", "factor", "coordinate"}, "target")
    action = _integer(target["action"], "target action", upper=count-1)
    factor = _integer(target["factor"], "target factor", upper=len(factors[action])-1)
    coordinate = _integer(target["coordinate"], "target coordinate", upper=n-1)
    _require(path[-1] == coordinate, "path does not end at target coordinate")
    _require(coordinate in factors[action][factor], "target is not in declared fitness scope")


def check_certificate(certificate, expected_structure=None):
    """True only for a valid union certificate bound to the supplied input."""
    try:
        _verify(certificate, expected_structure)
    except CertificateError:
        return False
    return True


def explain_certificate(certificate, expected_structure=None):
    try:
        _verify(certificate, expected_structure)
    except CertificateError as error:
        return {"valid": False, "error": str(error)}
    return {"valid": True}


def _json_object(pairs):
    answer = {}
    for key, value in pairs:
        if key in answer:
            raise ValueError("duplicate JSON object key: " + key)
        answer[key] = value
    return answer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", help="JSON certificate file, or - for stdin")
    parser.add_argument("--structure", type=Path,
                        help="requested structural input to bind the certificate")
    args = parser.parse_args(argv)
    try:
        def decode(text):
            return json.loads(text, object_pairs_hook=_json_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(
                                  ValueError("nonfinite JSON number: " + value)))
        cert = decode(sys.stdin.read() if args.certificate == "-" else
                      Path(args.certificate).read_text())
        expected = None if args.structure is None else decode(args.structure.read_text())
        verdict = explain_certificate(cert, expected)
    except (OSError, ValueError, MemoryError) as error:
        print(json.dumps({"valid": False, "checking_error": type(error).__name__+": "+str(error)}))
        return 2
    print(json.dumps(verdict))
    return 0 if verdict["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
