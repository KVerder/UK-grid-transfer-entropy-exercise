# Full KSG-1 run

Status: **running locally; full KSG results are not yet published**.

The full JIDT KSG algorithm 1 run uses `k=2` and all 5,108 households
(13,043,278 unordered pair slots), with at least 1,000 common readings per pair.
The current published HTML retains the previous discrete MI results and labels
them accordingly. Its latest styling is already available: linear width and
opacity for edge strength, and quadratic node colors centered on mean use.

The background runner is `scripts/run_full_ksg.py`. It writes progress to
`work/full-ksg-status.json`, `work/full-ksg.log`, and `work/full-ksg-error.log`.
KSG chunks are saved under `work/ksg-full/ksg-checkpoints-*` and are reused only
when input values, estimator settings, JIDT jar, and Java sources match.

The runner stages results in `work/ksg-full-analysis`. It performs independent
sample checks, artifact tests, and offline browser tests before updating the
delivered files. Git publication is a separate final step; no automatic recurring
monitor has been authorized or installed.

## Measured runtime

On this device with eight pair workers, a benchmark on 10,000 sampled household
pairs took 11.91 seconds at `k=2`. Linear extrapolation to the full pair count is
about 4.3 hours for MI alone. Allow roughly 4–5 hours including preparation,
saving, and validation; this is an estimate, not a deadline. The device must
remain running for computation to progress.

## Validation before launch

- Eleven numerical tests passed, including independent KSG references, Gaussian
  MI in nats, negative estimates, constants, missing observations, and checkpoint
  reuse across thread counts.
- An end-to-end run on the first ten households evaluated all 45 pairs. Maximum
  error against the independent KSG reference was `1.401171090265052e-8` nats.
- The updated full-population HTML passed the offline browser suite with no
  runtime errors or mobile overflow.

## CSV export

`scripts/export_households.py --output <path.csv>` extracts the first ten IDs in
ascending order into a wide CSV. The first row contains `DateTime` followed by
the household IDs; the next 1,488 rows contain half-hour consumption in kWh.
Duplicate values at a household/timestamp are collapsed, distinct conflicting
values would be averaged, and missing readings remain blank. This export has
ten duplicate source rows collapsed, no conflicts, and four blank readings.
