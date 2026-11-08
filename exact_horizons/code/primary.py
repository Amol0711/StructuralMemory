"""Exact exterior-descent backend using primitive integer echelon arithmetic.

Positive action-wise scaling clears denominators without altering uniform
horizons. Matrix construction, invariant closure and strict descent use exact
arithmetic. Graphical horizon decisions are never consulted.
"""
from fractions import Fraction
from itertools import combinations, product
from math import gcd, lcm
import hashlib
import json

ALGORITHM = "invariant closure and exterior descent; exact primitive integer echelon"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _primitive(v):
    v = list(v)
    g = 0
    for x in v:
        g = gcd(g, x)
    if g > 1:
        v = [x // g for x in v]
    first = next((x for x in v if x), 0)
    if first < 0:
        v = [-x for x in v]
    return tuple(v)


class RowSpace:
    """Exact rational row space represented by primitive integer echelon rows."""
    def __init__(self, width, rows=()):
        self.width = width
        self.rows = {}
        for row in rows:
            self.add(row)

    def reduce(self, original):
        require(len(original) == self.width, "Row width mismatch")
        v = list(original)
        require(all(isinstance(x, int) for x in v), "Noninteger row in exact backend")
        for p in sorted(self.rows):
            if v[p]:
                row = self.rows[p]
                common = gcd(row[p], v[p])
                a, b = row[p] // common, v[p] // common
                v = list(_primitive([a*x-b*y for x, y in zip(v, row)]))
        return tuple(v)

    def add(self, original):
        v = self.reduce(original)
        p = next((i for i, x in enumerate(v) if x), None)
        if p is None:
            return False
        self.rows[p] = _primitive(v)
        return True

    def basis(self):
        return tuple(self.rows[p] for p in sorted(self.rows))

    def dim(self):
        return len(self.rows)

    def contains(self, row):
        return not any(self.reduce(row))


def _digest_rows(rows):
    text = json.dumps(rows, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def build_matrices(case):
    """Independently construct matrices, validate all entries and column masses."""
    structure = case["structure"]
    n, actions = structure["n"], structure["U"]
    pa, fac = structure["pa"], structure["fac"]
    require(isinstance(n, int) and n >= 0 and isinstance(actions, int) and actions > 0,
            "Invalid dimensions")
    require(len(pa) == len(fac) == actions, "Action dimension mismatch")
    expected = set()
    for typ, scopes_by_action in (("theta", pa), ("psi", fac)):
        for u, scopes in enumerate(scopes_by_action):
            if typ == "theta":
                require(len(scopes) == n, "Transition coordinate count mismatch")
            for index, scope in enumerate(scopes):
                require(len(set(scope)) == len(scope) and all(isinstance(j, int) and 0 <= j < n for j in scope),
                        "Invalid parent/factor scope")
                for context in product((0, 1), repeat=len(scope)):
                    expected.add((typ, u, index, context))
    entries = {}
    for e in case["entries"]:
        key = (e["type"], e["action"], e["index"], tuple(e["context"]))
        require(key not in entries and key in expected, "Unexpected or duplicate local entry")
        q = Fraction(e["value"])
        require((0 < q < 1) if e["type"] == "theta" else q > 0,
                "Local entry outside positive table domain")
        if "chi" in e:
            require(e["chi"] == int(all(e["context"])), "Incorrect chi label")
        entries[key] = q
    require(set(entries) == expected, "Missing local entries")
    states = tuple(product((0, 1), repeat=n))
    matrices = []
    masses = []
    scales = []
    for u in range(actions):
        mass = []
        for x in states:
            m = Fraction(1)
            for k, scope in enumerate(fac[u]):
                m *= entries[("psi", u, k, tuple(x[j] for j in scope))]
            mass.append(m)
        mat = []
        for y in states:
            row = []
            for col, x in enumerate(states):
                probability = Fraction(1)
                for i, scope in enumerate(pa[u]):
                    q = entries[("theta", u, i, tuple(x[j] for j in scope))]
                    probability *= q if y[i] else 1-q
                row.append(probability*mass[col])
            mat.append(row)
        require(all(value > 0 for row in mat for value in row), "Nonpositive dense matrix entry")
        require(all(sum(mat[i][j] for i in range(len(states))) == mass[j]
                    for j in range(len(states))), "Column-sum identity failed")
        denominator = 1
        for row in mat:
            for q in row:
                denominator = lcm(denominator, q.denominator)
        integer = [[q.numerator*(denominator//q.denominator) for q in row] for row in mat]
        common = 0
        for row in integer:
            for value in row:
                common = gcd(common, value)
        require(common > 0, "Zero action matrix")
        integer = tuple(tuple(value//common for value in row) for row in integer)
        integer_mass = tuple(sum(row[j] for row in integer) for j in range(len(states)))
        scale = Fraction(denominator, common)
        require(all(Fraction(integer_mass[j]) == mass[j]*scale for j in range(len(states))),
                "Scaled column sums differ")
        matrices.append(integer)
        masses.append(integer_mass)
        scales.append(str(scale))
    return tuple(matrices), tuple(masses), {
        "state_order": "lexicographic tuples in product((0,1), repeat=n)",
        "state_count": len(states), "actions": actions,
        "entry_count": len(entries), "positive_local_entries": True,
        "column_sum_identities": True, "positive_action_scalings": scales,
        "integer_matrix_sha256": [_digest_rows(m) for m in matrices],
    }


def _compound(matrix, pairs):
    return tuple(tuple(matrix[i][k]*matrix[j][ell]-matrix[i][ell]*matrix[j][k]
                       for k, ell in pairs) for i, j in pairs)


def _images(space, compounds):
    for row in space.basis():
        active = [(i, value) for i, value in enumerate(row) if value]
        for b in compounds:
            out = [0]*space.width
            for i, value in active:
                bi = b[i]
                for j, entry in enumerate(bi):
                    if entry:
                        out[j] += value*entry
            yield _primitive(out)


def _record(space):
    return {"dimension": space.dim(), "basis_sha256": _digest_rows(space.basis())}


def _descend(space, compounds):
    records = [_record(space)]
    k = 0
    last_nonzero = None
    while space.dim():
        last_nonzero = space
        nxt = RowSpace(space.width)
        for row in _images(space, compounds):
            nxt.add(row)
        require(all(space.contains(row) for row in nxt.basis()), "Descending-space inclusion failed")
        require(nxt.dim() <= space.dim(), "Descending-space dimension increased")
        records.append(_record(nxt))
        if nxt.dim() == space.dim():
            # Inclusion plus equal dimensions is exact nonzero space equality.
            return "infinity", {"descent": records,
                "reason": "exact nonzero image-space equality",
                "terminal_basis": [list(r) for r in space.basis()]}
        space = nxt
        k += 1
        require(k <= space.width, "Finite horizon exceeds exterior dimension")
    return k, {"descent": records,
               "reason": "first zero image space",
               "last_nonzero_basis": [] if last_nonzero is None else [list(r) for r in last_nonzero.basis()]}


def solve(case, components=("full", "growth")):
    components = tuple(components)
    require(bool(components) and len(set(components)) == len(components)
            and all(x in ("full", "growth") for x in components), "Invalid components")
    matrices, masses, construction = build_matrices(case)
    size = len(matrices[0])
    pairs = tuple(combinations(range(size), 2))
    width = len(pairs)
    details = {"algorithm": ALGORITHM, "matrix_construction": construction,
               "exterior_dimension": width}
    answer = {"details": details}
    if not width:
        trivial = {"descent": [{"dimension": 0, "basis_sha256": _digest_rows(())}],
                   "reason": "zero-dimensional exterior space", "last_nonzero_basis": []}
        for component in components:
            answer[component] = 0
            details[component] = dict(trivial)
            if component == "growth":
                details[component]["closure"] = [{"dimension": 0, "basis_sha256": _digest_rows(())}]
        return answer
    compounds = tuple(_compound(m, pairs) for m in matrices)
    if "full" in components:
        full_space = RowSpace(width, (tuple(int(i == j) for j in range(width)) for i in range(width)))
        answer["full"], details["full"] = _descend(full_space, compounds)
    if "growth" in components:
        seeds = [tuple(m[i]-m[j] for i, j in pairs) for m in masses]
        growth_space = RowSpace(width, seeds)
        closure = [_record(growth_space)]
        while True:
            nxt = RowSpace(width, growth_space.basis())
            for row in _images(growth_space, compounds):
                nxt.add(row)
            require(nxt.dim() >= growth_space.dim(), "Growth closure dimension decreased")
            closure.append(_record(nxt))
            if nxt.dim() == growth_space.dim():
                break
            growth_space = nxt
            require(len(closure) <= width+1, "Growth closure exceeded dimension bound")
        answer["growth"], details["growth"] = _descend(growth_space, compounds)
        details["growth"]["closure"] = closure
    if all(x in answer for x in ("full", "growth")):
        require(answer["full"] == "infinity" or (answer["growth"] != "infinity" and answer["growth"] <= answer["full"]),
                "Growth horizon exceeds finite full horizon")
    return answer


if __name__ == "__main__":
    import sys
    require(len(sys.argv) == 2, "Usage: python primary.py CASE.json")
    with open(sys.argv[1]) as stream:
        case = json.load(stream)
    print(json.dumps(solve(case), sort_keys=True, indent=2))
