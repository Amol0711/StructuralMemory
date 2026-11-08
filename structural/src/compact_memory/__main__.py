"""CLI: solve a structural model or independently check one certificate.

Exit codes: 0 resolved/valid; 2 resource-limited unknown; 1 invalid input,
invalid certificate, or an execution error. Output JSON contains no Infinity
or NaN tokens. The solve command enumerates reachable states explicitly.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile

from .solver import solve


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _object(pairs):
    answer = {}
    for key, value in pairs:
        if key in answer:
            raise ValueError("Duplicate JSON object key: " + key)
        answer[key] = value
    return answer


def _read(path):
    text = sys.stdin.read() if path == "-" else Path(path).read_text()
    def invalid_constant(value):
        raise ValueError("Nonfinite JSON token: " + value)
    return json.loads(text, object_pairs_hook=_object, parse_constant=invalid_constant)


def _write(data, output):
    text = json.dumps(data, indent=2, allow_nan=False) + "\n"
    if output is not None:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    sys.stdout.write(text)


def main(argv=None):
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    solving = commands.add_parser("solve", help="Compute structural horizons")
    solving.add_argument("input", help="Structure JSON path or - for stdin")
    solving.add_argument("--output", help="Also atomically write result JSON here")
    solving.add_argument("--max-states", type=int, default=100000)
    solving.add_argument("--max-transitions", type=int, default=1000000)
    checking = commands.add_parser("check", help="Check one certificate independently")
    checking.add_argument("input", help="Certificate JSON path or - for stdin")
    checking.add_argument("--output", help="Also atomically write the verdict here")
    try:
        args = parser.parse_args(argv)
        data = _read(args.input)
        if args.command == "solve":
            result = solve(data, max_states=args.max_states,
                           max_transitions=args.max_transitions)
            _write(result, args.output)
            return 2 if any(result[q]["status"] == "unknown" for q in ("full", "growth")) else 0
        from .certificate_checker import check_certificate
        valid = check_certificate(data)
        _write({"valid": valid}, args.output)
        return 0 if valid else 1
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        print(f"compact_memory: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
