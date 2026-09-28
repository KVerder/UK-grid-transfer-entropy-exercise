# JIDT mutual information

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
