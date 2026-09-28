# Review and revision log

## Round 1 — Metric correctness and input robustness

An independent code review found that a subtractive variance calculation could
return a positive roundoff residual for a constant common-observation subset,
potentially displaying a false perfect correlation. It also found missing upper
bounds checks on bin codes in the native kernel.

Required revisions: use a stable pairwise calculation with an explicit constant
guard; test households that vary outside a constant shared intersection; reject
invalid bin codes, nonfinite observed values, and binary input-size mismatches.
Document score dtypes and the complete pair archive's upper-triangle ordering.

Changes implemented: first-common-value shifting and explicit variation checks
in the kernel; exact input byte counts, bin-domain checks, and observed-value
finiteness checks; archive dtypes and ordering documented in `METHODS.md`.

## Round 2 — Preprocessing, reproducibility, and UI semantics

Review found that a missing timestamp could become categorical index `-1`,
silently selecting the last timestamp. It also found that the documented Python
3.10 minimum was incompatible with `hashlib.file_digest`, and that constant-node
details needed to distinguish undefined correlation from valid zero MI.

Revisions: reject missing IDs/timestamps before indexing and test those inputs;
require Python 3.11 or newer; show metric-specific eligibility and refresh it on
toggle; consume the generated `timestampCount` metadata; validate cached pair
arrays and an implementation version with explicit exceptions rather than asserts.

Round 1 guards were rechecked. The review confirmed tied-value binning, duplicate
weighting, common-time overlap, and sparse edge selection matched the specification.

## Round 3 — Real artifacts, browser behavior, and responsive layout

The independent reviewer checked all 5,108 node records and 106,308 candidate
edges for uniqueness, score domains, valid indices, finite coordinates, and
minimum overlap. Earlier mathematical and preprocessing findings were confirmed
fixed. Nine constant households correctly had undefined correlation and eligible MI.

Visual inspection of the real HTML found that resizing from a fitted desktop
view to a phone width retained the old absolute pixel scale and cropped the graph.
The resize handler now preserves zoom relative to the newly fitted scale and
keeps the same world-space center. Browser tests now compare the resized fitted
canvas with an explicit refit, check constant/low-coverage explanations, verify
threshold and edge-limit effects, and compare exported MI/overlap values with
the embedded computed data.

The final analysis also corrects a validation-report precision issue: MI error
against the reference is now calculated in double precision before reporting,
rather than rounding the reference to float32 first.

## Final validation

- 14 numerical and artifact tests passed, including both sign extremes,
  nonlinear dependence, ties, missing observations, exact/conflicting duplicates,
  constant-on-overlap series, malformed inputs, cache versioning, full result
  domains, and every sparse candidate's agreement with the complete pair archive.
- 256 actual household pairs were independently checked using SciPy Pearson
  correlation and scikit-learn contingency-table MI. Maximum absolute errors
  were approximately `2.01e-8` for r and `1.46e-8` for MI, consistent with the
  delivered float32 score storage.
- Cache integrity was also checked under `python -O`, confirming that cache
  rejection does not depend on assertions.
- The final HTML ran in headless Microsoft Edge with networking disabled and
  zero page errors. All-household search, metric switching, selected-neighbor
  display, quoted CSV export with exact score/overlap values, constant and
  insufficient-coverage states, threshold and edge-limit changes, keyboard
  navigation, zoom, fit, and methods expansion passed.
- Desktop (1,500 px) and mobile (390 px) views were visually inspected. Mobile
  has no horizontal overflow; the fitted canvas bitmap matches an explicit refit
  after resizing. The test compares raw canvas pixels so toolbar hover styling
  does not create a false failure.

Final output: 5,108 households; 13,043,278 unordered pairs; 12,803,024 finite
correlations; 12,848,727 finite MI scores; 106,308 sparse candidate edges.
The source's 5,061 extra readings were exact duplicates; there were no conflicting
household/timestamp values. The analysis retains nine constant households and
38 households below the coverage rule.

## JIDT and visual encoding update — September 28, 2026

Replaced production MI with the checksum-pinned, unmodified JIDT 1.6.1 discrete
calculator. The C++ kernel now computes only Pearson correlation and overlap.
The previous quantile bins and paired-observation rule remain unchanged. JIDT's
bits are converted to nats, and the cache version prevents reuse of results from
the old implementation. See `docs/JIDT.md` for setup and provenance.

Every one of the 12,848,727 finite recomputed MI scores matched the previous
float32 values exactly; unavailable-score masks, Pearson values, overlap counts,
and household ordering were also unchanged. The known one-bit example returned
`ln(2)` nats, and independent nonlinear, constant, and missing-data checks passed.

Nodes now use a linear green-to-red scale of January mean kWh per observed
half-hour. Edges have fixed width and strength-dependent opacity; correlation
uses blue for positive and yellow for negative values, while MI remains purple.
Selection no longer draws an edge twice, preserving its encoded opacity.
Desktop and mobile previews were inspected, including the numeric consumption
legend and absence of mobile horizontal overflow.

Windows denied removal of generated test executables after numerical assertions
passed. Test artifacts now stay in the ignored `work/test-runs` directory;
cleanup retries before emitting an explicit Windows-only warning if removal
still fails. Numerical or artifact assertion failures remain fatal.

Final validation of the update: all 15 Python numerical/artifact tests passed.
The final regenerated HTML passed the offline browser integration suite with
zero runtime errors, no remote requests, and no mobile overflow. Tests verified
metric switching, household selection, exact exported MI/overlap values,
coverage states, filters, keyboard navigation, and mobile fit preservation.
The production run independently checked 256 sampled pairs; maximum MI error
against scikit-learn was `1.4645914314659336e-8` nats.

## KSG-1 k=2 and scale revision — September 28, 2026

The next default pipeline uses continuous JIDT KSG algorithm 1 with k=2,
sample-standardized paired observations, and reproducible Gaussian tie-breaking
noise. It keeps negative estimates and uses nats directly. Settings, source,
library checksum, and input values determine resumable checkpoint identity.
Eleven numerical tests passed, including independent cKDTree/digamma references,
Gaussian theoretical MI, negative estimates, constants, and checkpoint recovery.
All 45 first-ten-household pairs passed an end-to-end run; the maximum independent
MI error was `1.401171090265052e-8` nats. Full-run results remain pending and are
tracked in `docs/KSG_RUN.md`; no claim of completed full KSG validation is made.

Both edge width and opacity now increase linearly with normalized strength.
The node gradient is quadratic separately below and above the unweighted mean
of household mean consumption, with yellow anchored at that mean. The final
desktop and mobile views were inspected and the offline browser suite passed.

The local ten-household CSV now has 1,488 timestamps and household IDs as column
headers. Every exported value was checked against the source cells after
collapsing ten exact duplicates; four missing readings remain blank.


## 2026-09-28: three reviews of tablet, pair lookup, and cloud preparation

1. Numerical review: cloud shard union matches the existing JIDT KSG-1 runner
   exactly on 66 test pairs with ties, missing observations, and a constant
   series. Pilot indexing spans the population. Full lookup export sampled
   records match the source archive exactly; all five artifact checks pass.
2. Interaction review: browser tests cover MI maximum width/alpha, differentiated
   strokes, inverse pinch anchoring to 0.01 CSS pixels, two-finger pan, continued
   one-finger pan, cancelled touches, and no unintended node selection. Pinch
   transforms now use the gesture's initial view to prevent cumulative drift.
3. Delivery review: offline browser tests cover graph candidates and arbitrary
   file-backed pairs, reversed IDs, invalid/same IDs, rejected files, exact values,
   desktop/mobile layout, and existing controls. The desktop screenshot was
   visually inspected. Binned results remain active; no incomplete KSG result is
   published. Cloud execution still requires device login and credit-only billing
   verification. The temporary check is read-only and runs every 30 minutes.
