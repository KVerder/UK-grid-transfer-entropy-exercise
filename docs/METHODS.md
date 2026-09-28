# Household associations, January 2014

## Population and alignment

The input is the January 2014 subset of the UK Power Networks Low Carbon London
data published on the [London Datastore](https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d).
Every household in the extract is retained as a node. The time grid has 1,488
half-hour slots from January 1 at 00:00 through January 31 at 23:30. Timestamp
labels are used as supplied; there is no timezone conversion or lag search.

Exact repeats of a household/timestamp/consumption value are removed first.
If a timestamp has distinct conflicting consumption values, their arithmetic
mean is used once. The original downloaded CSV remains unchanged. The generated
analysis metadata records the actual duplicate and conflict counts.

Missing readings remain missing. Each unordered pair uses only its common
observed timestamps for both metrics. A score requires at least 1,000 common
half-hours (approximately 67% of the month); this is a chosen coverage rule,
not a significance threshold. The complete results include overlap counts and
missing scores, including for pairs which do not pass that rule.

## Pearson correlation

For a pair's common observations, Pearson r is the centered cross-product divided
by the product of the centered Euclidean norms. It measures synchronous linear
association and lies between -1 and +1. A series that is constant on the common
observations has undefined correlation, stored as NaN rather than zero.
See the [SciPy Pearson reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html).

In the network, edge opacity represents absolute r. Blue denotes positive
correlation and yellow denotes negative correlation. The signed number remains
visible in details and exports. Negative correlation does not attract nodes
together in the similarity layout.

## Mutual information

The default pipeline calls JIDT 1.6.1's
`MutualInfoCalculatorMultiVariateKraskov1` with `k=2` on continuous half-hour
consumption. There is no binning. Each pair uses its common observed timestamps,
standardizes each variable with its sample mean and sample standard deviation,
and adds Gaussian tie-breaking noise of standard deviation `1e-8`. The random
seed is `42 + pair_index`, making results reproducible across worker counts.

The JIDT calculator uses maximum norm and no temporal exclusion window. Its
internal normalization and unseeded noise are disabled because preparation is
performed explicitly by the wrapper. JIDT KSG returns **nats directly**.
See [exact settings and provenance](JIDT.md), and [current run status](KSG_RUN.md).

Negative finite-sample estimates are retained in the complete archive rather
than clipped to zero. They are not negative associations; only positive MI
estimates are displayed as MI edges. A constant variable on the common timestamps
has MI set to zero analytically; insufficient overlap remains NaN.

KSG's continuous-data assumptions and tiny tie-breaking noise matter for these
rounded meter readings. No significance test, surrogate correction, or temporal
exclusion is performed. MI and Pearson r use different scales; visual weights
must not be compared between modes as equivalent effect sizes.

## Positioning and display

No coordinates are present in the supplied CSV or among the three resources
listed on the source page. The generated HTML therefore displays **similarity
coordinates, not a geographic map**. The layout groups similar standardized
consumption profiles; the generated metadata describes the exact algorithm and
seed. Any mean filling used solely to position nodes does not enter pair metrics.
Positions stay fixed when the edge metric changes so that comparisons are easier.

Node colors use each household's January mean kWh per observed half-hour after
deduplication. Missing readings are excluded. Let `a` and `b` be the minimum
and maximum household means, and `m` their unweighted arithmetic mean. Green is
at `a`, yellow at `m`, and red at `b`. The normalized color coordinate is:

```text
x < m: u = 0.5 * ((x-a)/(m-a))^2
x = m: u = 0.5
x > m: u = 0.5 + 0.5 * ((x-m)/(b-m))^2
hue = 120 * (1-u) degrees
```

The legend reports all three anchors. A dashed outline indicates that the
household cannot support the active metric under the coverage/variance rule.

Correlation edge width and opacity increase linearly with strength:
`width = 0.25 + 3.75 * strength` pixels and
`opacity = 0.04 + 0.81 * strength`. Strength is `abs(r)`.
MI uses the mean-centered quadratic mapping specified below. Scales stay fixed across
filters. Positive correlation is blue, negative correlation yellow, and MI
purple. Selection draws each edge once, preserving its opacity.

All unordered pairs are calculated and saved separately. The HTML embeds a
sparse union of the strongest 12 neighbors per household by absolute correlation
and by MI. Controls then filter and cap the visible links. The absence of an edge
on screen does not establish that a pair is unrelated or that its score is
missing. Search can select every household, including low-coverage or constant
households. Selected-household details expose retained candidate relationships.

## Interpretation

The default layout centers each household's series, substitutes centered zero
for missing slots solely for positioning, and normalizes each nonconstant series
to unit length. It uses 32 randomized truncated-SVD components followed by t-SNE
with perplexity 40, 1,000 iterations, and seed 42. For complete centered unit
series, squared Euclidean distance is `2 * (1 - r)`, so the input representation
reflects positive correlation. Dimensionality reduction and missingness make the
display an approximation. Constant households are placed separately.

These are exploratory associations in observed January consumption. Shared
daily schedules, weather, calendar effects, and other common influences can
produce edges. Temporal autocorrelation is present, and no permutation tests,
p-values, multiple-testing correction, or causal inference are performed.
An edge does not establish a physical electricity-network connection or a social
relationship. The similarity layout is a visual projection, not a measurement
of physical distance or proof of a discrete household type.

## Reproducibility and validation

The analysis source, dependency requirements, all-pair results, display dataset,
offline HTML builder, and tests are included in this repository. The raw input
is tracked in Git LFS. The three review-and-fix rounds and actual validation
results are recorded in `docs/REVIEWS.md`.

### Complete pair archive

`analysis/pairs.npz` is a NumPy archive with household names in `ids`, Pearson
values in `correlation`, MI values in `mutual_information`, and common timestamp
counts in `overlap`. Score arrays store float32, and overlap counts store uint16.
Metric accumulation uses double precision. “All-pair” means every unordered
pair is evaluated; it does not mean exact real-number arithmetic.

Pairs use the upper triangle without a diagonal, in order `(0,1), (0,2), ...,
(0,N-1), (1,2), ...`. For indices `i < j`, the flat array position is
`i * (2*N - i - 1) // 2 + j - i - 1`. Scores unavailable under the documented
rules are NaN. `scripts/lookup_pair.py` retrieves any two household IDs from
these complete results, including pairs omitted from the displayed network.


## Current display revision

The published full-population data remains JIDT discrete MI (up to eight quantile
bins, bits converted to nats). The local continuous KSG run was stopped; KSG
methods above describe the optional recomputation, not the current displayed MI.
MI styling now uses the fixed mean of nonnegative candidate-edge scores, including
zeros. Below the mean, width is 1.5*(MI/mean)^2 px and alpha is 0.7*(MI/mean)^2.
Above it, q=((MI-mean)/(max-mean))^2, width=1.5+1.5*q and alpha=0.7+0.3*q.
Zero MI is not drawn. Correlation styling and quadratic node colors are unchanged.
Pinch gestures zoom about the moving midpoint and support simultaneous pan.


## Optional metric grouping

The HTML bundles two deterministic precomputed layouts. Weighted Louvain
communities use the union of each household’s five strongest retained candidate
links, with squared positive MI or squared
absolute Pearson r as weights, resolution 1.4 and seed 42 (NetworkX 3.5).
Thus strong negative correlations also group together. Each community uses
a weighted spring layout (35 iterations, seed 42); separate disks are packed
without overlap. Unlinked households occupy a separate region and remain
searchable. Communities are exploratory and do not imply every pair within
a group has high association. These are sparse-network communities, not a
clustering of the complete pair matrix. The browser switches positions instantly
and independently of edge metric or filter. Reset restores original positions
and fitted zoom without clearing filters or selected households.
