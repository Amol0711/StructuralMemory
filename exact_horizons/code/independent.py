"""Independent fraction-free exterior-descent implementation.

The backend reconstructs matrices from the frozen local entries and checks
finite horizon boundaries by direct word products. Infinity requires a verified
nonzero invariant image space; a resource cap never implies infinity.
Only the Python standard library is required.
"""

from fractions import Fraction
from hashlib import sha256
from itertools import combinations, product
from math import gcd, lcm
import argparse
import json


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(value):
    return sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def primitive(row):
    row = list(row)
    divisor = gcd(*row)
    if divisor:
        if next(v for v in row if v) < 0:
            divisor = -divisor
        if divisor != 1:
            row = [v // divisor for v in row]
    return row


class IntegerSpace:
    """Fraction-free primitive echelon basis over Q, independently implemented."""

    def __init__(self, width):
        self.width = width
        self.rows = {}

    def reduce(self, row):
        require(len(row) == self.width, "Wrong exterior row width")
        row = primitive(row)
        for pivot in sorted(self.rows):
            value = row[pivot]
            if value:
                basis = self.rows[pivot]
                scale = basis[pivot]
                row = primitive([scale * x - value * y for x, y in zip(row, basis)])
        return row

    def add(self, row):
        row = self.reduce(row)
        pivot = next((i for i, x in enumerate(row) if x), None)
        if pivot is None:
            return False
        self.rows[pivot] = row
        return True

    def contains(self, row):
        return not any(self.reduce(row))

    def basis(self):
        return [self.rows[k] for k in sorted(self.rows)]

    def __len__(self):
        return len(self.rows)


def build(case):
    """Construct rational selected matrices and clear denominators per action."""
    structure = case["structure"]
    n, actions = structure["n"], structure["U"]
    require(isinstance(n, int) and n >= 0 and actions > 0, "Invalid structure size")
    require(len(structure["pa"]) == len(structure["fac"]) == actions,
            "Action count mismatch")
    entries = {}
    for entry in case["entries"]:
        key = (entry["type"], entry["action"], entry["index"], tuple(entry["context"]))
        require(key not in entries, "Duplicate local table entry")
        value = Fraction(entry["value"])
        require(0 < value < 1 if entry["type"] == "theta" else value > 0,
                "Nonpositive or invalid local entry")
        require(entry["type"] in ("theta", "psi"), "Unknown entry type")
        entries[key] = value
    expected = set()
    for action in range(actions):
        require(len(structure["pa"][action]) == n, "Missing transition coordinate")
        for kind, scopes in (("theta", structure["pa"][action]),
                             ("psi", structure["fac"][action])):
            for index, scope in enumerate(scopes):
                require(len(set(scope)) == len(scope) and all(0 <= j < n for j in scope),
                        "Invalid local scope")
                for context in product((0, 1), repeat=len(scope)):
                    expected.add((kind, action, index, context))
    require(set(entries) == expected, "Missing or extraneous local table entries")
    states = list(product((0, 1), repeat=n))
    matrices, masses, rational_payload, scales = [], [], [], []
    for action in range(actions):
        mass = []
        for state in states:
            weight = Fraction(1)
            for k, scope in enumerate(structure["fac"][action]):
                weight *= entries[("psi", action, k, tuple(state[j] for j in scope))]
            mass.append(weight)
        matrix = []
        for target in states:
            row = []
            for col, source in enumerate(states):
                value = mass[col]
                for i, scope in enumerate(structure["pa"][action]):
                    probability = entries[("theta", action, i, tuple(source[j] for j in scope))]
                    value *= probability if target[i] else 1 - probability
                row.append(value)
            matrix.append(row)
        require(all(v > 0 for row in matrix for v in row), "Matrix is not strictly positive")
        require([sum(col) for col in zip(*matrix)] == mass, "Exact column sums differ from fitness")
        rational_payload.append({"matrix": [[str(v) for v in row] for row in matrix],
                                 "mass": [str(v) for v in mass]})
        denominator = lcm(*(v.denominator for row in matrix for v in row))
        integer_matrix = [[int(v * denominator) for v in row] for row in matrix]
        divisor = gcd(*(v for row in integer_matrix for v in row))
        integer_matrix = [[v // divisor for v in row] for row in integer_matrix]
        factor = Fraction(denominator, divisor)
        integer_mass = [sum(col) for col in zip(*integer_matrix)]
        require(all(integer_mass[i] == factor * mass[i] for i in range(len(states))),
                "Action scaling does not preserve column sums")
        matrices.append(integer_matrix)
        masses.append(integer_mass)
        scales.append(str(factor))
    return matrices, masses, {"rational_matrix_mass_sha256": digest(rational_payload),
                              "integer_matrix_mass_sha256": digest({"matrices": matrices, "masses": masses}),
                              "positive_action_scaling": scales,
                              "strict_positivity_and_exact_column_sums": True}


def compound(matrix, pairs):
    return [[matrix[i][k] * matrix[j][l] - matrix[i][l] * matrix[j][k]
             for k, l in pairs] for i, j in pairs]


def sparse(matrix):
    return [[(j, x) for j, x in enumerate(row) if x] for row in matrix]


def multiply_row(row, matrix_sparse):
    out = [0] * len(row)
    for i, value in enumerate(row):
        if value:
            for j, coefficient in matrix_sparse[i]:
                out[j] += value * coefficient
    return out


def space_image(space, actions, width):
    image = IntegerSpace(width)
    for row in space.basis():
        for action in actions:
            image.add(multiply_row(row, action))
    return image


def descend(space, actions, width, initial_length=0, prefix=None):
    length = initial_length
    dimensions = list(prefix or [len(space)])
    while len(space):
        image = space_image(space, actions, width)
        require(len(image) <= len(space), "Exterior descent dimension increases")
        require(all(space.contains(row) for row in image.basis()),
                "Exterior image is not contained in preceding row space")
        dimensions.append(len(image))
        if len(image) == len(space):
            return "infinity", {"dimensions": dimensions,
                                "termination": "nonzero_fixed_space",
                                "inclusion_verified": True,
                                "fixed_dimension": len(space),
                                "fixed_basis_sha256": digest(space.basis())}
        space = image
        length += 1
        require(length <= width, "Finite descent exceeds exterior dimension")
    return length, {"dimensions": dimensions, "termination": "zero_space",
                    "inclusion_verified": True}


def exterior_horizons(matrices, masses, components):
    states = len(matrices[0])
    pairs = list(combinations(range(states), 2))
    width = len(pairs)
    if width == 0:
        return 0, 0, {"exterior_dimension": 0, "full": {"dimensions": [0], "termination": "zero_space"},
                      "growth": {"dimensions": [0], "termination": "zero_space"},
                      "growth_closure_dimensions": [0]}
    raw_actions = [compound(matrix, pairs) for matrix in matrices]
    actions = [sparse(action) for action in raw_actions]
    full = growth = None
    full_detail = growth_detail = None
    closure_dimensions = None
    if "full" in components:
        full_space = IntegerSpace(width)
        for action in raw_actions:
            for row in action:
                full_space.add(row)
        full, full_detail = descend(full_space, actions, width, 1, [width, len(full_space)])
    if "growth" in components:
        closure = IntegerSpace(width)
        for mass in masses:
            closure.add([mass[i] - mass[j] for i, j in pairs])
        closure_dimensions = [len(closure)]
        while True:
            old_dim = len(closure)
            # Freeze the old basis before updating the same growing space.
            new = [multiply_row(row, action) for row in closure.basis() for action in actions]
            for row in new:
                closure.add(row)
            closure_dimensions.append(len(closure))
            require(old_dim <= len(closure) <= width, "Invalid invariant-closure growth")
            if len(closure) == old_dim:
                require(all(closure.contains(row) for row in new), "Growth closure is not invariant")
                break
        growth, growth_detail = descend(closure, actions, width)
    return full, growth, {"exterior_dimension": width, "full": full_detail,
                          "growth": growth_detail, "growth_closure_dimensions": closure_dimensions}


def matmul(left, right):
    columns = list(zip(*right))
    return [[sum(x * y for x, y in zip(row, col)) for col in columns] for row in left]


def reset_full(matrix):
    # Strict positivity means the first entry is a valid anchor.
    anchor = matrix[0][0]
    return all(row[j] * anchor == row[0] * matrix[0][j]
               for row in matrix for j in range(len(matrix)))


def reset_growth(matrix, mass):
    columns = list(zip(*matrix))
    bottom = [sum(col) for col in columns]
    top = [sum(x * y for x, y in zip(mass, col)) for col in columns]
    return all(top[j] * bottom[0] == top[0] * bottom[j] for j in range(len(matrix)))


def boundary_checks(matrices, masses, full, growth):
    """All words at each finite horizon and a last-bad word just before it."""
    finite = {"full": full, "growth": growth}
    finite = {kind: value for kind, value in finite.items() if isinstance(value, int)}
    if not finite:
        return {"status": "not_applicable_both_infinite", "word_products": 0}
    maximum = max(finite.values())
    # This study's declared structures have small finite horizons. A checker
    # limit is an explicit error, not an altered numerical horizon decision.
    require(maximum <= 12, "Finite-word replay horizon exceeds declared checker limit")
    size = len(matrices[0])
    level = [((), [[int(i == j) for j in range(size)] for i in range(size)])]
    results = {kind: {"horizon": h, "all_words_at_horizon": False, "last_bad_word": None}
               for kind, h in finite.items()}
    products = 0
    for length in range(maximum + 1):
        products += len(level)
        require(products <= 100000, "Finite-word replay exceeds explicit product limit")
        for kind, horizon in finite.items():
            if length not in (horizon, horizon - 1):
                continue
            bad = []
            for word, matrix in level:
                if kind == "full":
                    if not reset_full(matrix):
                        bad.append({"word": list(word)})
                else:
                    for action, mass in enumerate(masses):
                        if not reset_growth(matrix, mass):
                            bad.append({"word": list(word), "readout_action": action})
                            break
            if length == horizon:
                require(not bad, "Numerical finite horizon fails exact word replay")
                results[kind]["all_words_at_horizon"] = True
                results[kind]["words_at_horizon"] = len(level)
            elif horizon > 0:
                require(bool(bad), "Finite horizon is not minimal in exact word replay")
                results[kind]["last_bad_word"] = bad[0]
        if length < maximum:
            level = [(word + (action,), matmul(matrix, old))
                     for word, old in level for action, matrix in enumerate(matrices)]
    return {"status": "passed", "word_products": products, "checks": results}


def solve(case, components=("full", "growth")):
    require(bool(components) and set(components) <= {"full", "growth"}, "Invalid requested component")
    matrices, masses, construction = build(case)
    full, growth, detail = exterior_horizons(matrices, masses, components)
    replay = boundary_checks(matrices, masses, full, growth)
    result = {"details": {"method": "independent_fraction_free_exterior_descent",
                        "arithmetic": "exact integers and fractions.Fraction",
                        "construction": construction, "exterior": detail,
                        "finite_boundary_replay": replay}}
    if "full" in components:
        result["full"] = full
    if "growth" in components:
        result["growth"] = growth
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", help="Frozen case JSON")
    parser.add_argument("--component", choices=("full", "growth"))
    args = parser.parse_args()
    with open(args.case) as handle:
        case = json.load(handle)
    print(json.dumps(solve(case, (args.component,) if args.component else ("full", "growth")), sort_keys=True))
