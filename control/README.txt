CONTROL COMPUTATIONS

This component is self-contained and uses Python 3.10+ and the standard
library only. It contains exact rational simulation data, independently
checked certificates, and scripts for three control studies. It does not
contain a biological calibration model.

All paths below are relative to this directory. Commands also work from
another working directory when the script and output paths are absolute.

  python3 verify.py
  python3 -O verify.py
  python3 reproduce.py --output /absolute/path/to/a/new/control-run

verify.py checks the sealed recorded payloads, regenerates all 256 parameter
samples from seed 4612026, re-evaluates their exact identities and cycle rates,
recomputes all 435 cascade weights and 13,776 column ratios, rechecks the 14
structural certificates, and independently checks every recorded scheduling
graph and available optimum. It also checks all analytic edge-box corners.
It validates recorded transient tables; reproduce.py additionally regenerates
all 27,603 transient masses from the full and quotient population models.

reproduce.py runs every study to a fresh directory and compares every saved
scientific field against frozen/. Exact rational entries, witnesses, graph
edges, cap outcomes and decimal plot files must match. Timing values, machine
information, and source/payload hash bookkeeping are excluded from that
comparison. Original timings remain in frozen/ and are never replaced by a
new run. The regenerated data and detailed comparison are written only to the
chosen new directory. A run can take several minutes on a shared computer.

The per-study commands, for separately chosen fresh output directories, are:

  python3 studies/control_transients.py --output /new/path/transients
  python3 studies/control_perturbations.py --output /new/path/perturbations
  python3 studies/feasibility/run_feasibility.py --output /new/path/feasibility
  python3 checks/analytic_control_check.py

The scripts refuse to write under frozen/ or overwrite a completed output
directory. The feasibility script's --verify-recorded option verifies a NEW
run created by these scripts; use verify.py for the bundled recorded
study. --freeze-only creates a protocol/sample freeze that the same script
can evaluate on a subsequent call. It never selects or redraws a sample based
on an outcome.

TRANSIENTS

frozen/transients/input.json states the model, matrix convention, three
initial laws, all three action constraints, and the tie rule. Legal words are
exhaustively enumerated through T=12. The full eight-state matrices and an
independently constructed four-state quotient agree on 27,603 unnormalized
masses and visible marginals. An independent history recursion verifies all
117 finite-horizon extrema. Exact masses are in all_legal_word_masses.csv;
finite_horizons.json contains minimizers, maximizers, and periodic-phase
comparisons. control_transients.dat contains only presentation conversions of
those exact results. Under the no-consecutive-1 constraint, fixed phase 001
has maximum mass/optimum ratio 3519/551 for the correlated initial law.
The best legal rotation is optimal in the 117 tested cases; this finite check
does not establish an all-horizon assertion.

PERTURBATIONS AND ANALYTIC BOX CHECK

frozen/perturbations/rational_samples.json preserves all 256 samples, the
integer draws, exact tables, seed, order and formula. Each sample has 26 free
entries. All 16,384 two-step growth identities are verified directly against
the full population model and the quotient. Cycle products are compared by
exact integer powers; root bounds use 48 exact dyadic bisections. Saved
intervals enclose the sample minima and maxima. Finite sampling is not a
whole-box proof. checks/analytic_control_check.py separately enumerates the
32 corners of each of the eight multi-affine edge functions and all simple
cycles, verifying the exact analytic constants and interval comparisons.

CASCADE FEASIBILITY

frozen/feasibility/protocol.json contains all seven model specifications,
positive rational parameters, three automata and fixed caps. Every coordinate
belongs to fitness ancestry. Six terminal-fitness cascade models admit exact
history weights. One joint-adjacent-fitness case is graphically infinite and
stops before numerical weight construction: its chosen numerical point is
not thereby classified as infinite.

The exact product-law shortcut is valid only after explicit checks of terminal
selection, one parent per nonroot child, no fan-out, action-independent parent
graph, and independent coordinate innovations. This is not a general
mean-field approximation. All pure columns and histories are checked for
uniform growth ratios; a shorter-history unequal-ratio witness establishes
sharpness of each chosen finite numerical horizon.

There are 435 exact weights and 13,776 all-column ratio evaluations. Independent
dense propagation checks 92 full vectors, 200 pure-column growth ratios and
50 correlated-population growth ratios on explicitly recorded subsets. Of
18 scheduling cases, 14 optima have independently replayed legal periodic-tail
witnesses and matching closed-walk dynamic-programming optima. Four cases
remain unknown after the cycle-step cap. They are serial n=6, two actions,
unrestricted; and serial n=4, three actions, under each automaton. These caps
characterize this bounded cycle enumerator, not intrinsic scheduling hardness.

The caps are 5,000 states, 20,000 edges, 5,000 cycles, 20,000 warm-up steps and
50,000 cycle steps. Recorded stage timings are one-run descriptive measurements,
not repeated benchmark medians. The timing-only solver copy is checked by
undoing its recorded edits and recovering the uninstrumented solver exactly.

DATA INTEGRITY

payload_manifest.json binds the distributed scripts and recorded tables.
Exact inputs, numerical outcomes and recorded timing values are retained.
Fresh runs write their own output files to a separate directory and do not
replace the recorded measurements.
