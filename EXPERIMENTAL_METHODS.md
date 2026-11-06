# Experimental methods and numerical records

This document describes the frozen structural, exact-horizon and growth-control experiments. It links the input designs and reported summaries to executable generators, exact data and independent checks. All paths are relative to the package root.

## Structural comparison

The 29 benchmark inputs comprise 12 chains, nine branching directed acyclic graphs, four refresh cases, two selection-delay cases, one one-state quotient and one example with a cycle outside fitness ancestry. The chains use dimensions 2, 4, 6, 8, 10 and 12 with either separate or joint fitness scopes. The branching graphs cross dimensions 4, 6 and 8 with action-count/scope-arity pairs (2,1), (3,2) and (3,3). Their frozen generator seed is 4622026. Every generated input is retained.

The three methods are the marked-support pair recursion, explicit component-support propagation and the canonical second-compound decision. They share structural prechecks for both original graphical horizons. These prechecks settle both queries on five inputs, one query on two inputs, and neither query on 22 inputs. The one-state fixture encodes the quotient with empty fitness ancestry using zero coordinates; its full-composition query concerns that scalar quotient.

Using one-based coordinate indices, the two actions of the four-coordinate delay example have parent tuples

- Action 0 has ({3}, {4}, {2,4}, empty).
- Action 1 has ({3}, {4}, {2}, empty).

Its fitness scopes are (empty, empty) for action 0 and ({1}, empty) for action 1. The graphical horizons are (6,6). Removing selection gives (4,0). Stored JSON and generator code use zero-based indices.

For the refresh cases with dimensions 2, 4, 8 and 12, action a refreshes coordinate a while the other coordinates have self-parents. Fitness factors have separate unary scopes. The common cycle precheck certifies both horizons as infinite. Unpruned enumeration reaches 2^n pair states; a one-action prefix and loop already provide an infinity certificate. The eight additional unpruned stress runs are separate from the main common-precheck comparison.

Each main method/input pair uses one discarded warm-up and three fresh measured subprocesses under a 10-second wall-time cap and a 1-GiB address-space cap. Decision time includes input processing, prechecks, matrix construction and decision computation. Additional pair-certificate generation and independent checking are recorded separately. Process startup is excluded from the decision clock; the parent wall-time cap covers the subprocess. Medians require three completed trials.

The exterior reference uses dense second-compound matrices and sparse exact integer elimination. Its dense-storage preflight is implementation-specific. Pair and support methods resolve all 29 inputs. The exterior implementation resolves 19 inputs, with nine memory preflights and one timeout. Every resolved answer agrees. A capped computation remains unknown unless a separate checked certificate resolves it. The recorded timings describe the specified implementations, workload and shared host.

| Record | Contents |
| --- | --- |
| [fixtures.py](structural/src/benchmark/fixtures.py) | Complete input generators and regeneration checks |
| [protocol.json](structural/data/benchmark/protocol.json) | Frozen inputs, seed, resource caps and timing rules |
| [inputs/](structural/data/benchmark/inputs/) | All 29 declared structures |
| [raw/](structural/data/benchmark/raw/) | All 380 execution records, including warm-ups and stress runs |
| [summary.json](structural/data/benchmark/summary.json) | Machine information and summaries derived from raw records |
| [derived_tables.json](structural/data/benchmark/derived_tables.json) | All horizon outcomes, precheck counts and eight predetermined landmarks |
| [benchmark.csv](structural/data/benchmark/benchmark.csv) | Complete timing table in seconds |

## Exact numerical horizons

The 13 structures with at most four coordinates comprise four chains, three branching graphs, two refresh cases, two delay cases, one cycle outside fitness ancestry and the one-state quotient. Five draws per eligible family give 65 free-table points and 60 tied-table points. The scalar quotient has no nontrivial ties.

Transition entries are drawn from {1,...,96}/97 and fitness entries from {1,...,388}/97. Tied draws use the coarsest equality classes permitted separately within each entry type and each value of the indicator chi = all(context), including the empty context. Regeneration must use the exact integer seed stored in each case and the specified entry enumeration order. It must not derive a new seed from a renamed case identifier.

All 125 parameter points are retained without resampling. Numerical and graphical horizon pairs agree at 124 points. In `chain_04_joint__T__01`, both transition levels equal 94/97, producing a common transition column and nonconstant mass rows. The numerical pair is (1,1), whereas the graphical pair is (infinity,infinity). Equal fitness levels would instead make all mass rows constant and give zero growth memory. Finite-grid sampling therefore retains possible exceptional coincidences.

Twenty raw 120-second cap records concern five distinct free four-coordinate refresh growth queries, each tested with two exact backends in normal and optimized Python modes. Separate constant-word certificates resolve these five growth horizons as infinite, completing all 250 numerical decisions. The check reconstructs exact matrices and replays the primitive row orbit. For each certificate, its first 20 rows are independent and its nonzero 21st row is the first dependent iterate. The recorded cyclic minimal polynomial is nonmonomial. Raw cap outcomes remain unchanged and are not relabeled as successful runs.

| Record | Contents |
| --- | --- |
| [protocol.json](exact_horizons/protocol.json) | Rational grids, tie rules, enumeration order and resource limits |
| [cases/](exact_horizons/cases/) | All 125 exact parameter tables and their stored seeds |
| [controls/](exact_horizons/controls/) | Three diagnostic controls, outside the 125-point total |
| [records/](exact_horizons/records/) | All 1,024 backend/component/mode outcomes |
| [certificates/](exact_horizons/certificates/) | Separate constant-word certificates in both Python modes |
| [point_results.json](exact_horizons/results/point_results.json) | Resolved numerical horizons and graphical comparisons |
| [summary.json](exact_horizons/results/summary.json) | Aggregate counts and retained exceptional case |

## Exact finite-horizon growth control

The transient study uses three visible initial laws on two binary coordinates. The uniform law gives each configuration probability 1/4. The correlated law gives 00 and 11 probability 1/2 each; the anticorrelated law gives 01 and 10 probability 1/2 each. Every law has an independent fair hidden bit.

For each of the unrestricted, no-consecutive-1 and forced-alternation regimes, all legal words are enumerated through T=12, including T=0. Every tested word admits an infinite legal continuation. Ties are resolved by selecting the lexicographically first minimizing or maximizing word. Direct eight-state population propagation and an independently constructed four-state quotient agree on all 27,603 masses and visible marginals. Independent history calculations verify both extrema for all 117 regime/law/horizon combinations.

Periodic-phase comparisons use all legal rotations of 0011, 001 and 01 in the three respective regimes. Each rotation is checked as an infinite periodic schedule, including the period boundary. The best phase reaches the finite-horizon minimum in all 117 tested cases. Under the no-consecutive-1 constraint, the fixed phase 001 costs up to 3519/551 times the optimum for the correlated law. These findings concern the tested finite horizons and do not establish all-horizon phase optimality.

| Record | Contents |
| --- | --- |
| [input.json](control/frozen/transients/input.json) | Exact baseline parameters, initial laws, constraints and tie rule |
| [all_legal_word_masses.csv](control/frozen/transients/all_legal_word_masses.csv) | Complete exact word/law masses |
| [finite_horizons.json](control/frozen/transients/finite_horizons.json) | Extrema, attaining words and legal periodic-phase comparisons |
| [two_step_prefixes.json](control/frozen/transients/two_step_prefixes.json) | Initial-law-dependent prefix masses |
| [summary.json](control/frozen/transients/summary.json) | Independent-agreement counts and phase-penalty summaries |
| [control_transients.dat](control/frozen/transients/control_transients.dat) | Presentation values derived from the exact records |

## Perturbation samples and sampled cycle minima

The local-table study uses 256 rational samples with 26 independently perturbed entries per sample and frozen seed 4612026. The parameter box and generation order are stored with the exact draws. All 16,384 two-step initial-column growth identities agree between the full model and the quotient. Exact integer-power comparisons of rational cycle products preserve the minimizing cycles in every sample. Root enclosures use 48 exact dyadic bisections.

At the baseline, ell=19/40 and h=51/40. The following intervals are outward-rounded enclosures of the range of minimum asymptotic multipliers across the 256 sampled parameter points.

| Constraint | Minimizing cycle word | Baseline minimum | Enclosure of sampled minima |
| --- | --- | --- | --- |
| Unrestricted | 0011 | ell | [0.4284, 0.5109] |
| No consecutive 1 | 001 | (ell^2 h)^(1/3) | [0.6153, 0.6974] |
| Forced alternation | 01 | h | [1.2209, 1.3233] |

The baseline maximum is h in every regime. The intervals above describe sampled minima, not perturbed maxima, whole-box enclosures or attained endpoints of an analytic bound. The exact rational root bounds in the records determine the outward rounding. Separate analytic corner checks verify the uniform edge bounds and cycle comparisons throughout the parameter box.

| Record | Contents |
| --- | --- |
| [sample_freeze.json](control/frozen/perturbations/sample_freeze.json) | Frozen protocol and sample binding |
| [rational_samples.json](control/frozen/perturbations/rational_samples.json) | All exact draws, local tables and seed |
| [sample_results.json](control/frozen/perturbations/sample_results.json) | Per-sample identity and cycle checks |
| [cycle_extrema.csv](control/frozen/perturbations/cycle_extrema.csv) | Sampled extrema and their root bounds |
| [summary.json](control/frozen/perturbations/summary.json) | Exact enclosing ranges and aggregate counts |
| [analytic_control_check.py](control/checks/analytic_control_check.py) | Independent edge-corner and cycle checks |

## Reproduce and verify

The [package README](README.md) and component READMEs give all commands. `python verify.py` and `python -O verify.py` check the complete file inventory and execute the structural, exact-horizon and control verifiers. The [control reproducer](control/reproduce.py) regenerates the complete control study in a fresh output directory. Fresh timings and resource outcomes must remain separate from frozen measurements.
