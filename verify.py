#!/usr/bin/env python3
"""Verify the complete distribution and replay all component checks."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def inventory():
    expected = {}
    for line in (ROOT / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe manifest path')
        require(name != 'SHA256SUMS' and name not in expected, 'Duplicate or self-referential path')
        require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None, 'Malformed checksum')
        expected[name] = digest
    actual = {
        p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
        if p.is_file() and not {'__pycache__', '.git'}.intersection(p.relative_to(ROOT).parts)
        and p.relative_to(ROOT).as_posix() != 'SHA256SUMS'
    }
    require(actual == set(expected), 'Delivered inventory differs from SHA256SUMS')
    for name, digest in expected.items():
        p = ROOT / name
        require(not p.is_symlink() and p.resolve().is_relative_to(ROOT), 'Unsafe payload path')
        require(hashlib.sha256(p.read_bytes()).hexdigest() == digest, 'Payload changed: ' + name)
    return len(expected)


def main():
    count = inventory()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    results = {}
    for name, script in (
        ('structural', 'structural/verify.py'),
        ('exact_horizons', 'exact_horizons/code/verify.py'),
        ('control', 'control/verify.py'),
    ):
        command = [sys.executable]
        if sys.flags.optimize:
            command.append('-' + 'O' * sys.flags.optimize)
        command.append(str(ROOT / script))
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        require(result.returncode == 0, name + ' failed:\n' + result.stdout + result.stderr)
        results[name] = json.loads(result.stdout)
        require(results[name].get('status') == 'passed', name + ' did not report success')
    print(json.dumps({'status': 'passed', 'verified_payloads': count, 'components': results}, indent=2))


if __name__ == '__main__':
    main()
