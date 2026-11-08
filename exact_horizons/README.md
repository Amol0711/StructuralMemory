# Exact numerical horizon study

This component contains the frozen 125-point rational study: 65 free-table
points and 60 points with the coarsest allowed sharing by entry type and
`chi = all(context)`. There are five draws for each eligible structure/family.
Three diagnostic controls are stored separately and are excluded from the
125-point and 250-horizon totals. No point was resampled.

The `zero_coordinates` fixture represents the **one-state quotient for
J = empty**, encoded by zero coordinates (`n = 0`). Its zero-dimensional
exterior space gives zero full-composition and growth horizons **for that
quotient**. This does not assert a zero full-composition horizon for an
original system with nonempty state coordinates. There are no nontrivial
sharing classes in this scalar fixture, so it has only five free draws.

## Requirements and verification

Python 3.10 or later; only the standard library is used. The frozen generator
ran on Python 3.12.14; its environment is retained in `protocol.json` and
`records/*/environment.json`. The full capped rerun uses the Unix `resource`
module and is intended for Linux. The verifier is independent of the current
working directory. Replace `/path/to` below with the extracted package path.

```sh
python /path/to/exact_horizons/code/verify.py --output /tmp/exact-check.json
python -O /path/to/exact_horizons/code/verify.py --output /tmp/exact-check-optimized.json
```

The default verification checks:

- Every packaged payload against `integrity.json`.
- All 125 integer seeds by regenerating all 3,445 sampled rational entries, preserving
  entry/class enumeration order and inclusive integer draws.
- All 128 case/control matrix constructions with both exact backends.
- All 1,024 archived backend/component/mode records and their input bindings.
- All five constant-word certificates by independently constructing the
  matrices and replaying the 21 primitive orbit rows; the first 20 rows have
  rank 20 and the nonzero 21st row is their first dependent iterate.
- The retained exceptional common-column factorization and the counts of 20
  zero, 102 positive finite and 128 infinite numerical horizons.
- Fresh exact full/growth horizon computations with both backends for all
  cases with at most three coordinates, the four-coordinate exceptional
  case, and all three controls (49 cases total).

`--no-replay` skips the last, direct horizon-computation step only. Seed,
all-case matrix, archived-record, and orbit-certificate checks still run.
Verification reports must be written outside this frozen component. Checks
use explicit exceptions and remain active with Python `-O`.

## Frozen inputs and raw outcomes

`cases/` and `controls/` contain exact rational tables. Each sampled case has
its original full integer `seed`. Regeneration starts directly from that
integer with `random.Random(seed)`. Renaming a fixture must never change its
seed. The stored rational tables remain the authoritative numerical inputs.
Transition draws are from `{1,...,96}/97`, fitness draws from `{1,...,388}/97`.

`records/` retains 1,024 original execution outcomes: two backends, two
components, two Python modes, 128 cases/controls. This includes **20 raw
120-second cap outcomes**, corresponding to five distinct free four-coordinate
refresh growth queries. Each capped record remains `status: unknown`, with
its original measured duration and cause. A cap is never an infinity verdict.

`certificates/normal/` and `certificates/optimized/` contain the five independent
constant-word resolutions in each mode. They establish infinite growth
horizons without overwriting capped runs. The matrices used for these
certificates are exact rational numerical matrices; graphical horizons are
not used as numerical certificates. `results/point_results.json` stores the
final numerical decisions and graphical comparisons; `results/summary.json`
stores the aggregate counts. The sole disagreement is
`chain_04_joint__T__01`, retained with numerical pair `(1,1)` and graphical
pair `(infinity,infinity)`. Its two transition levels coincide at `94/97`;
fitness levels are `235/97` and `368/97`.

Export changes are confined to documentation and provenance metadata. Raw
scientific arrays, exact decisions, elapsed timings and memory measurements
are preserved. `case_sha256` binds a record to the exported case, while
`frozen_case_sha256` retains the pre-export case hash. Likewise,
`frozen_backend_sha256` identifies the original execution source and
`export_backend_sha256` identifies the distributed source after documentation
cleanup. Original execution hashes must not be mistaken for hashes of the
cleaned source. The algorithms and matrix arithmetic are unchanged. No new
runtime measurements replace the recorded timings.

## Fresh computations

Compute one case directly (no external time limit):

```sh
python /path/to/exact_horizons/code/primary.py /path/to/exact_horizons/cases/chain_02_separate__U__01.json
python /path/to/exact_horizons/code/independent.py /path/to/exact_horizons/cases/chain_02_separate__U__01.json
python /path/to/exact_horizons/code/constant_word_certificate.py /path/to/exact_horizons/cases/refresh_04__U__01.json
```

Run the complete study under the original 120-second per-component/backend,
2 GiB per-worker address-space, four-worker limits:

```sh
python /path/to/exact_horizons/code/run_study.py --output-dir /tmp/fresh-exact-run --mode normal
python /path/to/exact_horizons/code/run_study.py --output-dir /tmp/fresh-exact-run --mode optimized
```

The output directory must be outside this component and each selected mode's
subdirectory must not already exist. Use `--select CASE_ID ...` for a subset,
for example `--select chain_02_separate__U__01 control__constant_mass_control`.
Resource outcomes and runtimes can differ across machines. Fresh outputs are
new measurements and must not overwrite frozen records. Both finite and
infinite exact decisions are returned only when a backend establishes them;
any timeout remains unknown. The certificate command can be run separately
to check an applicable constant-word infinity certificate; a
`not_applicable` result makes no finite or infinite assertion.
