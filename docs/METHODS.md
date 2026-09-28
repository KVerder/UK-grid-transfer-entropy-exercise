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

Consumption is discretized independently for each household using up to eight
quantile bins, estimated from that household's observed readings for the entire
month. Repeated thresholds are collapsed, and equal readings stay in the same
bin. The bins are fixed before intersecting a household pair's timestamps.

On the pair's common timestamps, let `c[a,b]` be a joint bin count, `n` the
overlap count, and `c[a,*]` and `c[*,b]` the two marginal counts. We compute:

```text
MI = sum over nonempty cells of (c[a,b] / n) *
     ln(c[a,b] * n / (c[a,*] * c[*,b]))
```

Production MI is computed by the unmodified JIDT 1.6.1 library's
`MutualInformationCalculatorDiscrete(base, base, 0)`, where `base` is the maximum
number of bins. Each worker resets its calculator for every pair and supplies
only the paired observations. JIDT returns **bits**, which are multiplied by
`ln(2)` to store **nats**, matching the formula above and the existing display.
See [JIDT setup and provenance](JIDT.md).

The value is nonnegative and symmetric.
A constant discretized series has MI zero when overlap is sufficient. This is
the empirical contingency-table estimator, independently checked against
[scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mutual_info_score.html),
applied to discretized consumption, not to household identifiers.

This estimator can detect nonlinear dependence, but it discards within-bin
variation and depends on the binning choice. It is not bias-corrected or
normalized. Finite samples can yield positive MI for independent processes.
MI and Pearson r have different scales; their numerical values and opacities
should not be compared across toggle modes as equivalent effect sizes.

## Positioning and display

No coordinates are present in the supplied CSV or among the three resources
listed on the source page. The generated HTML therefore displays **similarity
coordinates, not a geographic map**. The layout groups similar standardized
consumption profiles; the generated metadata describes the exact algorithm and
seed. Any mean filling used solely to position nodes does not enter pair metrics.
Positions stay fixed when the edge metric changes so that comparisons are easier.

Node hue varies linearly from green through yellow to red across the minimum and
maximum household January means. The mean is kWh per observed half-hour after
deduplication; missing readings are excluded. This is average consumption, not a
monthly total. The legend gives the actual endpoints. A dashed outline indicates
that a household cannot support the active metric under the coverage/variance rule.

Edges have a fixed width. Opacity is `0.04 + 0.81 * strength`, where strength is
`abs(r)` for correlation and `MI / largest candidate MI` for mutual information.
Zero-score edges are omitted. The MI scale is fixed across filters. Positive
correlation is blue, negative correlation yellow, and MI purple. Selection adds
candidate edges without drawing an edge twice or changing its opacity.

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
