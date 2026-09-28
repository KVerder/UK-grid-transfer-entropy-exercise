# JIDT mutual information
# JIDT KSG algorithm 1

The default analysis uses the unmodified [JIDT 1.6.1 library](https://github.com/jlizier/jidt/releases/tag/v1.6.1)
and `MutualInfoCalculatorMultiVariateKraskov1` with **k=2**. It operates on
continuous half-hour readings, without quantile bins. The current full-run and
publication status is recorded in [KSG_RUN.md](KSG_RUN.md).

## Exact settings

- Zero-lag pairs of common observed timestamps; minimum 1,000 readings.
- Standardize each paired variable with its sample mean and sample standard
  deviation, using JIDT's MatrixUtils normalization.
- Add Gaussian noise with standard deviation `1e-8` in standardized units to
  break ties in rounded meter readings. The wrapper uses Java Random with seed
  `42 + pair_index`; draws alternate between the two variables. JIDT's internal
  noise is disabled because version 1.6.1 does not expose a seeded-noise property.
- JIDT normalization is disabled after the explicit normalization above.
- Maximum norm, KSG algorithm 1, `k=2`, no Theiler exclusion window.
- One JIDT observation worker per calculator; parallelism is across household
  pairs. Each worker owns its calculator and initializes it for every pair.
- KSG returns **nats directly**. There is no bits-to-nats conversion.
- Preserve negative finite-sample estimates in the archive. Only positive MI
  estimates are shown as edges; negative estimates do not mean anticorrelation.
- A variable constant on the pair's shared timestamps has MI set to zero
  analytically, avoiding normalization of zero variance. Insufficient overlap is NaN.

The [upstream KSG implementation](https://raw.githubusercontent.com/jlizier/jidt/v1.6.1/java/source/infodynamics/measures/continuous/kraskov/MutualInfoCalculatorMultiVariateKraskov.java)
documents the estimator, units, neighbour count, norm, and exclusion settings.
The C++ kernel computes only Pearson correlation and overlap counts.

## Reproduction and resuming

Install a Java JDK 11 or newer with `java` and `javac` on PATH, plus the Python
and C++ prerequisites in the README:

```sh
python scripts/setup_jidt.py
python scripts/analyze.py --threads 8 --mi-k 2
python scripts/build_html.py
```

The same analysis command resumes completed KSG chunks automatically. Checkpoint
identity includes input values, settings, Java source, and the JIDT jar checksum.
A settings or source change creates a different checkpoint directory.
The pair archive also records estimator version, k, noise magnitude, and seed.

For an end-to-end staged run that checks outputs before replacing delivered
artifacts, use `scripts/run_full_ksg.py --deliver-html <output.html>`. Node.js,
Playwright, and a browser are required for that runner's final browser checks.
Git publication remains a separate step.

## Library provenance

Setup downloads the official release ZIP into ignored `work/jidt` and checks
both archive and extracted jar. Mismatches fail rather than silently using a
different library. JIDT is GPL v3 or later; the release includes its source and
license. The library is unmodified and is not vendored in this repository.

| File | SHA-256 |
| --- | --- |
| Release ZIP | `460914b46c29ec05cbb4424e5b46d5bfd08bdcbbe6c22c40c92b06966fb81d71` |
| Jar | `2d367c244b729877fdaf0608884cf97ae964a8035c3020215b799812143a5b11` |

## Validation

Independent Python checks reconstruct KSG-1 with SciPy cKDTree and digamma,
using the matching seeded jitter. Tests cover Gaussian theoretical MI in nats,
nonlinear dependence, negative estimates, constants, missing observations,
pair-index ordering, and checkpoint reuse. The production pipeline independently
checks 256 actual pairs before building its display data.
GSclone uses the official [Java Information Dynamics Toolkit (JIDT)](https://github.com/jlizier/jidt)
version [1.6.1](https://github.com/jlizier/jidt/releases/tag/v1.6.1).
JIDT is distributed under GNU GPL v3 or later; its upstream release includes the
license and sources. The downloaded library is unmodified and kept in the ignored
`work/jidt` directory. It is not vendored in this repository.

## Estimator

`scripts/JidtPairMI.java` imports and calls
`infodynamics.measures.discrete.MutualInformationCalculatorDiscrete` for every
eligible household pair. This retains the existing tied-value-preserving,
eight-bin quantile discretization and minimum of 1,000 common observations.
It is the discrete estimator, not JIDT's continuous KSG estimator.

Each worker owns a separate calculator. Every pair starts with `initialise()`,
followed by `addObservations()` on exact-length arrays containing only common
observed timestamps. `computeAverageLocalOfObservations()` returns bits; the
wrapper multiplies by `ln(2)` to preserve the project's nats output convention.
The [upstream implementation](https://raw.githubusercontent.com/jlizier/jidt/v1.6.1/java/source/infodynamics/measures/discrete/MutualInformationCalculatorDiscrete.java)
documents the unit and computes the empirical discrete estimator.

The C++ kernel now computes only Pearson correlation and observation overlap.
It contains no production MI calculation. Independent Python reference formulas
and scikit-learn are used only for validation, not to populate production MI.
The pair-cache version changed, so results from the former implementation cannot
silently be reused. Generated metadata records the JIDT version, jar checksum,
estimator, native unit, and conversion.

## Reproduction

Install a Java JDK 11 or newer and put both `java` and `javac` on PATH, alongside
the Python and C++ prerequisites listed in the README. Run:

```sh
python scripts/setup_jidt.py
python scripts/analyze.py --threads 8
python scripts/build_html.py
```

The setup step is also invoked automatically by fresh analysis. It downloads
`infodynamics-dist-1.6.1.zip` from the official GitHub release, verifies the archive,
and extracts and verifies `infodynamics.jar`. Mismatched files cause an error.

| File | SHA-256 |
| --- | --- |
| Release ZIP | `460914b46c29ec05cbb4424e5b46d5bfd08bdcbbe6c22c40c92b06966fb81d71` |
| Unmodified jar | `2d367c244b729877fdaf0608884cf97ae964a8035c3020215b799812143a5b11` |

Run the Python tests to check JIDT against independent MI references, including
nonlinear relationships, constants, missing observations, and the bits-to-nats
conversion. A fresh production run also checks 256 sampled pairs against SciPy
and scikit-learn and records the maximum errors in `analysis/manifest.json`.
