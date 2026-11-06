# Computational validation of structural memory horizons

This guide describes the experimental protocols, exact inputs and independent computational checks for the structural and numerical horizon studies. It provides commands and record locations for reproducing the experiments.

## Computational assessment of horizon determination

The comparison uses the exact pair recursion, explicit component-support propagation and the canonical second-compound method, all with the same preliminary structural tests. The study retains every one of its 29 declared structures.

| Structural family | Number of structures | Design |
| --- | ---: | --- |
| Separate- and joint-fitness chains | 12 | Dimensions 2, 4, 6, 8, 10 and 12 for each fitness-scope arrangement |
| Branching directed acyclic graphs | 9 | Dimensions 4, 6 and 8 crossed with intervention-count/scope-arity pairs (2,1), (3,2) and (3,3) |
| Coordinate-refresh systems | 4 | Dimensions 2, 4, 8 and 12 |
| Selection-delay systems | 2 | The selected four-coordinate example and its selection-free counterpart |
| One-state fitness-ancestral quotient | 1 | Empty ancestral set, represented by zero coordinates |
| Cycle outside fitness ancestry | 1 | Three coordinates, with a two-coordinate ancestral set |

The scalar quotient is a separate boundary example. Its composition horizon concerns that quotient, not the full composition of an unreduced nontrivial population. Nontrivial structures have dimensions from 2 to 12. The branching-graph generator uses the stored integer seed 4622026.

The main comparison contains 87 method/structure combinations. Every combination has one discarded warm-up followed by three measured executions. Each execution uses a new process with a 10-second elapsed-time limit and a 1-GiB address-space limit. The eight additional refresh comparisons disable preliminary tests and remain separate from the main comparison. Together these produce 380 raw execution records.

Decision times include input validation, preliminary structural tests, matrix construction when needed and the remaining horizon computation. Additional pair-certificate generation and independent checking are recorded separately. Process startup is excluded from the decision clock, while the elapsed-time limit covers the whole process. A median requires three completed measured executions. The original shared-host configuration, interpreter and processor information are retained in the recorded summary; the values describe these implementations under that protocol.

| Method | Structures resolved | Resource-limited structures |
| --- | ---: | --- |
| Pair recursion | 29 | 0 |
| Component-support propagation | 29 | 0 |
| Second-compound reference | 19 | Nine rejected by its dense-storage estimate and one stopped at the elapsed-time limit |

Every completed answer agrees. An uncompleted horizon calculation remains unresolved; a resource limit does not imply an infinite horizon. Preliminary structural tests can independently resolve one or both horizons before a subsequent resource stop.

Eight representative cases were specified before execution. Their complete data, all other cases and separate certificate timings are preserved in the records below. Descriptive labels correspond to the fixed identifiers as follows.

| Case label | Coordinates | Frozen identifier |
| --- | ---: | --- |
| Separate | 4 | `chain_04_separate` |
| Separate | 12 | `chain_12_separate` |
| Joint | 4 | `chain_04_joint` |
| Joint | 12 | `chain_12_joint` |
| Delay | 4 | `delay_04_selected` |
| Branching | 8 | `dag_08_u3_a3` |
| Refresh | 12 | `refresh_12` |
| Outside J | 3 | `cycle_outside_ancestry` |

The Branching case is the directed acyclic graph with action-count/scope-arity pair (3,3). It has eight coordinates, three interventions and fitness-scope arity three. The column labelled Compound uses the archived method key `exterior`. A dash in that column denotes `unknown_memory_preflight`, meaning the estimated dense-matrix storage exceeds the implementation's prescribed bound. It does not denote an absent experiment or an infinite horizon.

| Item | Source and purpose |
| --- | --- |
| Complete input design and generation | [fixtures.py](structural/src/benchmark/fixtures.py) and [protocol.json](structural/data/benchmark/protocol.json) |
| Frozen structures | [29 input files](structural/data/benchmark/inputs/) |
| Original measured executions | [raw records](structural/data/benchmark/raw/) |
| Environment and timing summaries | [summary.json](structural/data/benchmark/summary.json) |
| All outcomes and the eight predetermined displayed cases | [derived_tables.json](structural/data/benchmark/derived_tables.json) |
| Complete timing table in seconds | [benchmark.csv](structural/data/benchmark/benchmark.csv) |
| Verification coverage and fresh-execution commands | [structural README](structural/README.md) |

## Exact comparison of numerical and graphical horizons

The study uses 13 structures with at most four coordinates. Five exact rational draws per eligible structure/family give 65 free-table points and 60 tied-table points. The one-state quotient has no nontrivial sharing classes and therefore only free-table draws. Three diagnostic controls are stored separately and are excluded from the 125-point total.

Transition entries lie in `{1,...,96}/97`; fitness entries lie in `{1,...,388}/97`. Tied parameters use the coarsest permitted equality classes separately for each entry type and each value of `chi = all(context)`, including the empty context. The exact integer seed stored in each case, together with the prescribed entry/class enumeration order, regenerates the sampled rational entries. All draws are retained without resampling.

Two independent exact implementations evaluate each composition and growth horizon in both normal and optimized Python modes. Including the three controls, this produces 1,024 execution records. The original per-component, per-implementation limit is 120 seconds, with a 2-GiB address-space limit per worker and at most four workers.

Twenty raw time-limit records concern five distinct free four-coordinate refresh growth calculations across the two implementations and two execution modes. Separate constant-intervention certificates establish infinite growth horizons for these five cases. The raw execution outcomes remain unresolved in the archive; the resolved mathematical decisions are recorded separately.

For each constant-intervention certificate, an independent exact reconstruction checks the row orbit and its cyclic minimal polynomial. The first 20 primitive rows are independent, and the nonzero 21st row is the first dependent iterate. The resulting polynomial is nonmonomial.

| Numerical outcome | Count |
| --- | ---: |
| Parameter points | 125 |
| Composition/growth horizon decisions | 250 |
| Zero horizons | 20 |
| Positive finite horizons | 102 |
| Infinite horizons | 128 |
| Points agreeing with both graphical horizons | 124 |
| Retained exceptional points | 1 |

The exceptional point is `chain_04_joint__T__01`. Its two transition levels both equal 94/97, while its fitness levels are 235/97 and 368/97. The transition columns therefore coincide, and the mass rows are nonconstant. Its numerical horizon pair is (1,1), whereas its graphical pair is (infinity,infinity). The retained coincidence illustrates exceptional shortening under finite-grid sampling. Equal fitness levels would make the mass rows constant and give zero growth memory.

| Item | Source and purpose |
| --- | --- |
| Sampling grids, ties, seeds, ordering and limits | [protocol.json](exact_horizons/protocol.json) |
| All exact sampled tables | [cases](exact_horizons/cases/) |
| Separate diagnostic controls | [controls](exact_horizons/controls/) |
| Original exact-calculation outcomes | [records](exact_horizons/records/) |
| Independent constant-intervention resolutions | [certificates](exact_horizons/certificates/) |
| Final horizon pairs and graphical comparisons | [point_results.json](exact_horizons/results/point_results.json) |
| Counts and retained exceptional case | [summary.json](exact_horizons/results/summary.json) |
| Verification coverage and fresh-execution commands | [exact-horizon README](exact_horizons/README.md) |

## Independent checks

Run the following commands from the package root with Python 3.10 or newer. The programs use the standard library and leave the frozen records unchanged.

```sh
python structural/verify.py
python exact_horizons/code/verify.py
```

The structural verifier independently recomputes all 58 horizon answers for the 29 structures, checks the recorded timing summaries and resource outcomes, and validates all 360 certificates in the timing records. It also checks the 12 chain examples and their 24 certificates.

The exact-horizon verifier regenerates all 3,445 sampled rational entries, reconstructs all 128 case/control matrix families with both implementations, checks all 1,024 archived outcomes and the five independent orbit certificates, and recomputes both horizons with both implementations on the documented 49-case subset. The command below omits only that last subset of fresh horizon calculations; all input regeneration, matrix construction, archived-record and orbit-certificate checks still run.

```sh
python exact_horizons/code/verify.py --no-replay
```

For the complete package inventory and all three component checks, run `python verify.py`. The same commands with `python -O` retain their checks. Fresh capped experiments and new timing measurements use separate output directories, as specified in the component READMEs. They do not overwrite the archived values.

## Terminology in archived files

File names and machine-readable keys remain stable so that the checks, citations to records and recorded source hashes remain reproducible.

| Scientific description | Archived identifier |
| --- | --- |
| Component-support propagation | Method key `antichain` |
| Canonical second-compound method | Method key `exterior` |
| Constant-intervention infinity certificate | Files and commands containing `constant_word` |
| Finite intervention sequence | Record field or file name containing `word` |
| Unresolved dense-storage estimate | Status `unknown_memory_preflight` |
| Unresolved elapsed-time limit | Status `unknown_timeout` |

These identifiers denote the recorded procedures and numerical outcomes. The [experimental methods](EXPERIMENTAL_METHODS.md) also document the growth-control, finite-horizon and perturbation studies.
