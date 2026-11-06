# Boolean population simulations

Python simulations and numerical experiments for Boolean population models. The package contains executable programs, fixed inputs, recorded numerical outcomes and independent computational checks.

## Start here

Use **Python 3.10 or newer**. All programs use the Python standard library; no package installation is required. Run from this directory:

```sh
python verify.py
python -O verify.py
```

Both commands verify the delivered file inventory and run all three component checks. They print their results without changing the frozen records. Absolute script paths also work from another working directory. Python optimization is propagated to the component checks.

| Component | Frozen material | What the default check repeats |
| --- | --- | --- |
| `structural/` | 12 chain examples; 29 benchmark inputs; 380 raw timing trials | Regenerates inputs, solves all structural queries, checks 24 chain and 360 benchmark certificates, and validates recorded summaries and cap outcomes |
| `exact_horizons/` | 125 parameter points and 3 separate controls; 1,024 raw execution records; five constant-word certificates | Regenerates rational tables from all stored integer seeds, constructs matrices independently, checks numerical records and the five certificates, and replays a documented subset using both exact backends |
| `control/` | Exact transients, 256 perturbation samples and seven cascade models | Regenerates samples and their results, checks box-corner bounds, all-column growth weights, and recorded scheduling certificates |

The scalar case is a **one-state fitness-ancestral quotient with empty ancestry**, encoded with zero coordinates. It does not assert that the original population's full-composition horizon is zero.

The [horizon-validation guide](COMPUTATIONAL_VALIDATION.md) describes the structural comparison and exact numerical study, including the experimental design, timing conventions, resource limits, retained exceptional point and independent checks. The [experimental methods and numerical records](EXPERIMENTAL_METHODS.md) also cover the transient checks and sampled cycle-minimum ranges, with direct links to their source records.

## Verification and fresh experiments

Read each component's README for its commands and exact coverage. In particular:

```sh
python structural/verify.py
python exact_horizons/code/verify.py
python control/verify.py
python control/reproduce.py --output /absolute/path/to/new-control-run
```

The last command freshly recomputes the complete control study and compares its scientific results with the frozen records. Output directories for fresh experiments must be outside the delivered package. Full timing benchmarks and capped exact calculations are optional and more expensive; they need a POSIX/Linux environment for resource controls. The read-only verification commands do not rerun all historical timing trials.

## Interpreting the records

- The structural timing study retains its 10-second wall-time and 1-GiB address-space protocol, discarded warm-up runs, and implementation-specific memory preflights. Timings describe the recorded machine and workload; new timings may differ.
- All 125 exact parameter points are retained: 65 free and 60 tied. Numerical and graphical horizon pairs agree at 124 points; the one exceptional tied point remains included. The three diagnostic controls are separate from those 125 points.
- Twenty raw timeout records concern five distinct growth queries, observed across two backends and two execution modes. Their raw outcomes remain capped; the separate exact constant-word certificates resolve the five mathematical horizons as infinite. Capped execution is not itself an infinity certificate.
- Stored integer seeds are authoritative. Regeneration uses these exact integers and the documented sampling order; it does not derive replacement seeds from renamed files or prose labels.
- The checks distinguish scientific values from wall-clock measurements and execution metadata. Exported source has been reorganized for portability; historical execution-source hashes identify the recorded runs and are not represented as hashes of the reorganized code.

## Repository setup

Place the contents of this directory at the repository root, including `.gitignore` and `.gitattributes`. Run `python -B verify.py` after extraction or checkout. The verifier checks every distributed file against `SHA256SUMS`; Git metadata and Python bytecode caches are excluded. Keep fresh experiment outputs and virtual environments outside this directory. `.gitattributes` preserves the exact recorded file bytes during Git checkout.
