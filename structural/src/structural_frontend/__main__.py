"""Decide unrestricted graphical memory using certified shortcuts then pairs.

Run from the source-package root:
  python3 src/structural_frontend/__main__.py INPUT.json --output RESULT.json
  python3 src/structural_frontend/__main__.py INPUT.json --max-states 1

The first call uses the union-graph precheck, independently checks every
shortcut certificate, and runs the existing pair solver only if a query
remains unresolved. Its fallback still explores the original pair graph,
not a quotient graph. Known zero/infinite shortcut answers are retained
if a fallback budget stops. Acyclicity never becomes a finite answer.

Empty fitness support gives graphical growth horizon zero. Zero coordinates
give both horizons zero. A cycle outside fitness ancestry can resolve full
memory while growth remains unknown under a cap. These are unrestricted
graphical answers, not numerical answers for every parameter choice and
not language-specific horizons under imposed action constraints.

Exit status: 0 both queries resolved; 3 one or both still unknown because of
a pair-graph budget; 2 input/checking/output error. Resource exceptions are
errors, never certificates. The same wrapper is callable as decide(data).
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from structural_frontend import precheck, check_certificate
from compact_memory.solver import solve
from compact_memory.certificate_checker import check_certificate as check_pair


def _budget(value, name, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")


def decide(structure, *, max_states=100000, max_transitions=1000000):
    """Return checked original full/growth answers with honest partial status."""
    _budget(max_states, "max_states", 1)
    _budget(max_transitions, "max_transitions", 0)
    front = precheck(structure)
    data = front["structure"]
    result = {
        "schema": "structural-memory.frontend-solver.v1",
        "semantics": "graphical-unrestricted", "structure": data,
        "J": front["J"], "precheck_horizons": front["horizons"],
        "precheck_stats": front["stats"], "pair_exploration": None,
    }
    for query in ("full", "growth"):
        horizon = front["horizons"][query]
        if horizon is None:
            result[query] = {"status": "unknown", "horizon": None,
                             "certificate": None, "source": "unresolved"}
        else:
            cert = front["certificates"][query]
            if not check_certificate(cert, expected_structure=data):
                raise RuntimeError("Union certificate rejected: " + query)
            result[query] = {
                "status": "infinite" if horizon == "infinite" else "finite",
                "horizon": None if horizon == "infinite" else horizon,
                "certificate": cert, "source": "union_precheck"}
    if front["unresolved"]:
        fallback = solve(data, max_states=max_states, max_transitions=max_transitions)
        result["pair_exploration"] = fallback["exploration"]
        for query in ("full", "growth"):
            value = fallback[query]
            if value["status"] != "unknown":
                cert = value["certificate"]
                if cert["structure"] != data or not check_pair(cert):
                    raise RuntimeError("Pair certificate rejected: " + query)
                if result[query]["status"] != "unknown":
                    if (value["status"], value["horizon"]) != (
                            result[query]["status"], result[query]["horizon"]):
                        raise RuntimeError("Precheck and pair result disagree: " + query)
            if query in front["unresolved"]:
                result[query] = dict(value)
                result[query]["source"] = ("unresolved" if value["status"] == "unknown"
                                             else "pair_solver")
    result["status"] = ("incomplete" if any(result[q]["status"] == "unknown"
                                            for q in ("full", "growth")) else "complete")
    return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def _emit(result, destination):
    output = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n"
    if destination is None:
        sys.stdout.write(output)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         prefix=destination.name+".", suffix=".tmp",
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(output)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="structure JSON file, or - for stdin")
    parser.add_argument("--output", type=Path)
    # Convert after invalidating any old output, so malformed numeric budget
    # strings cannot leave a prior successful result masquerading as this run.
    parser.add_argument("--max-states", default="100000")
    parser.add_argument("--max-transitions", default="1000000")
    args = parser.parse_args(argv)
    destination = args.output
    try:
        if (destination is not None and args.input != "-" and
                destination.resolve() == Path(args.input).resolve()):
            destination = None
            raise ValueError("input and output must be different files")
        if destination is not None:
            _emit({"status": "running", "semantics": "graphical-unrestricted"},
                  destination)
        max_states = int(args.max_states)
        max_transitions = int(args.max_transitions)
        text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
        data = json.loads(text, object_pairs_hook=_json_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              ValueError("nonfinite JSON number: " + value)))
        result = decide(data, max_states=max_states,
                        max_transitions=max_transitions)
        _emit(result, destination)
        return 3 if result["status"] == "incomplete" else 0
    except (OSError, ValueError, RuntimeError, MemoryError) as error:
        record = {"status": "error", "semantics": "graphical-unrestricted",
                  "error": type(error).__name__+": "+str(error)}
        try:
            _emit(record, destination)
        except (OSError, ValueError, MemoryError):
            _emit(record, None)
        return 2


if __name__ == "__main__":
    sys.exit(main())
