"""Exact constant-word numerical infinity certificates.

This separate module does not alter the frozen exterior-descent backend or
overwrite any capped-run record. It uses numerical matrices only; graphical
horizons and the primary implementation are never imported.

API: certify(case, component='growth') returns a certificate or not_applicable.
The caller must retain its declared wall-time/memory caps and preserve unknown
if a certificate is not produced. A non-applicable result makes no finite claim.
"""

from itertools import combinations
import argparse
import json

from independent import (IntegerSpace, build, compound, digest, multiply_row,
                         primitive, require, sparse)


def certify(case, component="growth"):
    require(component in ("full", "growth"), "Invalid component")
    matrices, masses, construction = build(case)
    pairs = list(combinations(range(len(matrices[0])), 2))
    width = len(pairs)
    common = {"component": component, "case_id": case["case_id"],
              "arithmetic": "exact integers and fractions.Fraction",
              "construction": construction, "exterior_dimension": width}
    if width == 0:
        return {**common, "status": "not_applicable", "reason": "zero exterior dimension"}
    attempts = []
    for action, matrix in enumerate(matrices):
        exterior = compound(matrix, pairs)
        action_sparse = sparse(exterior)
        if component == "full":
            trace = sum(exterior[i][i] for i in range(width))
            attempts.append({"action": action, "trace_compound": str(trace)})
            if trace:
                return {**common, "status": "certified_infinity", "horizon": "infinity",
                        "method": "constant_action_nonzero_compound_trace",
                        "action": action, "trace_compound": str(trace),
                        "reason": "Nonzero trace implies a nonnilpotent compound; its powers never vanish.",
                        "attempts": attempts}
            continue
        for readout, mass in enumerate(masses):
            row = primitive([mass[i] - mass[j] for i, j in pairs])
            space = IntegerSpace(width)
            orbit = []
            for length in range(width + 1):
                orbit.append(row)
                if not any(row):
                    attempts.append({"action": action, "readout_action": readout,
                                     "termination": "zero_iterate", "length": length})
                    break
                if not space.add(row):
                    require(length == len(space), "Earlier Krylov iterates were not independent")
                    require(space.contains(row), "First dependent iterate fails exact span check")
                    # The prefix is a basis of a cyclic invariant space. Check
                    # invariance directly as well as through the orbit relation.
                    require(all(space.contains(multiply_row(v, action_sparse))
                                for v in orbit[:-1]), "Krylov span is not invariant")
                    require(all(any(v) for v in orbit), "Zero iterate in nonnilpotence certificate")
                    attempts.append({"action": action, "readout_action": readout,
                                     "termination": "nonzero_dependent_iterate", "length": length})
                    return {**common, "status": "certified_infinity", "horizon": "infinity",
                            "method": "constant_word_nonmonomial_cyclic_polynomial",
                            "action": action, "readout_action": readout,
                            "first_dependence_length": length,
                            "prefix_rank": len(space),
                            "prefix_pivots": sorted(space.rows),
                            "dependent_iterate_nonzero": True,
                            "invariant_span_verified": True,
                            "primitive_orbit_rows": orbit,
                            "primitive_orbit_sha256": digest(orbit),
                            "reason": "The first dependent Krylov iterate is nonzero. The cyclic minimal polynomial is not a monomial, so this numerical orbit is not eventually zero.",
                            "attempts": attempts}
                row = primitive(multiply_row(row, action_sparse))
            else:
                raise RuntimeError("Krylov independence exceeds exterior dimension")
    return {**common, "status": "not_applicable", "attempts": attempts,
            "reason": "No constant-word certificate found; no finite or infinite decision is implied."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", help="Frozen case JSON")
    parser.add_argument("--component", choices=("full", "growth"), default="growth")
    args = parser.parse_args()
    with open(args.case) as handle:
        case = json.load(handle)
    print(json.dumps(certify(case, args.component), sort_keys=True))
