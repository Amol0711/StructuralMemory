# Structural examples and capped benchmark

This component contains the pair-state solver, a separate certificate checker,
shared structural prechecks, a support-state comparator, and an exact dense
exterior-algebra reference. The executable pair solver enumerates reachable states.

All code uses the Python standard library. Use CPython 3.10 or newer. The
read-only checker is portable; timed workers require Linux (`RLIMIT_AS` and
Linux resident-memory reporting). The archived benchmark was run with the
Python/platform/CPU information retained in `data/benchmark/summary.json`.

## Verify frozen results

From the computational package root:

```sh
python structural/verify.py
python -O structural/verify.py
```

Absolute script paths also work from any working directory. The commands check
artifact hashes and input generation, reconstruct every timing summary and CSV,
check all 360 certificates in 380 raw trials, independently recompute all 58
benchmark horizon answers with the pair solver, and check the 24 certificates
and 24 horizon answers in the twelve chain examples. No archived file changes.

The benchmark uses 29 inputs: twelve chains, nine fixed-seed branching DAGs,
four refresh cases, two selection-delay cases, one scalar quotient boundary
case, and a case with a cycle outside the fitness ancestry. Every generated
case is retained. The seed is the exact integer `4622026`; `src/benchmark/fixtures.py`
regenerates and checks all original structures.

`zero_coordinates` encodes the **one-state quotient with empty ancestral set
J**, using zero Boolean coordinates. Its full-composition query is on that
one-state quotient. It does not assert that the original nontrivial population
has zero full-composition horizon, nor does it extend the original model's
positive coordinate count to zero.

## Frozen records

| Directory/file | Contents |
| --- | --- |
| `data/chains/inputs/` | Twelve declared chain structures, dimensions 2, 4, 6, 8, 10, 12 |
| `data/chains/certificates/` | Twenty-four independently checkable horizon certificates |
| `data/chains/instances/` | Pair/support outcomes, marked-state trajectories and small-case algebra |
| `data/chains/horizons.csv` and `.dat` | Chain plot/table data |
| `data/benchmark/inputs/` | Twenty-nine complete frozen input structures |
| `data/benchmark/raw/` | 380 fresh-process trials, including warmups and unresolved trials |
| `data/benchmark/summary.json` | Raw-derived summaries and original execution environment |
| `data/benchmark/benchmark.csv` | Raw-derived table in seconds |
| `data/benchmark/derived_tables.json` | All outcomes, preselected eight landmarks, and method counts |
| `data/benchmark/protocol.json` | Original input seed, caps, selection and timing rules |

Each main method uses identical structural preprocessing for both original
queries. The eight additional refresh stress runs disable preprocessing and
are not end-to-end timing comparisons. Each method-instance run has one
discarded warmup and three measured trials. The main exterior reference
completed 19 of 29 cases; nine stopped at its dense-memory preflight and one
at the wall-time limit. A resource stop is unresolved, never evidence of
infinite memory. Already certified preprocessing answers remain visible.

`recorded_execution_sources.json` preserves hashes of the original execution
sources under neutral release paths. These are historical provenance records,
not hashes of the relocated release code. The release changed paths, schema
labels, documentation, and output/checker guards; it retained the algorithms,
inputs, certificates, rational data, all numeric timing values and censored
outcomes. Current release bytes are covered by the package's `SHA256SUMS`.
Recorded timing values have not been replaced with verification runtimes.

## Fresh structural reproduction

Use an output directory that does not already exist:

```sh
python structural/src/structural_study.py --output /absolute/new-chain-results
```

This regenerates all twelve chain cases and checks 24 certificates, twelve
support-state comparisons, 204 component-state comparisons, 1,016 direct
moralized endpoint queries, and four exact canonical-algebra comparisons.
The chain CSV and plot data are regenerated. These are bounded independent
implementation checks; horizon certificates supply the all-word answers for
the twelve declared structures.

The canonical boundary matrices used in the exact comparison can have zero
transition entries. They are distinct from strictly positive parameter draws.

## Optional fresh timed benchmark

Use Linux and a separate, new output directory. The directory is frozen before
any timings are taken. Never point these commands at `structural/data`.

```sh
python structural/src/benchmark/run_benchmark.py --freeze --output /absolute/new-benchmark
python structural/src/benchmark/run_benchmark.py --run --output /absolute/new-benchmark
python structural/src/benchmark/run_benchmark.py --verify-recorded --output /absolute/new-benchmark
```

This starts 380 sequential subprocesses under 10-second/1-GiB caps. The original
run used a shared, non-isolated host. Timing, resident memory, and cap outcomes
can change with the machine, interpreter, load, and operating system. The
results belong to the new output directory, not the archived timing table.
Preselected cases and seed remain fixed regardless of the new outcomes.

For bounded exact reference and timeout/censoring checks:

```sh
python structural/src/benchmark/test_protocol.py
python -O structural/src/benchmark/test_protocol.py
python structural/check_guards.py
```

The protocol checker prints its verdict and writes no frozen records. The guard
checker uses temporary copies and requires tampered inputs/results to fail.

## Pair solver and certificate CLI

From this component directory, with `src` on Python's import path:

```sh
PYTHONPATH=src python -m compact_memory solve data/benchmark/inputs/chain_04_separate.json
PYTHONPATH=src python -m compact_memory check data/chains/certificates/chain_04_separate_full.json
```

The solver returns exit code 0 for resolved answers, 2 for a resource-limited
unknown, and 1 for invalid input or execution failure. A certificate checker
verdict of false returns exit code 1. The structural frontend is similarly
available as `python -m structural_frontend`; pass `--help` for its interface.
