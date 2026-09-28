# Executed specification

Using all January 2014 household readings in GSclone, calculate zero-lag Pearson
correlation and empirical mutual information for every household pair on aligned
half-hour timestamps. Document duplicate handling, missing data, minimum overlap,
constant series, and the MI estimator.

Build a standalone HTML network with all households searchable, a correlation/MI
toggle, weighted edges, zoom, filters, and household details. Use verified
coordinates if available; otherwise use a clearly labelled layout that groups
positively correlated households. Keep the display sparse for readability and
save the complete pairwise results separately.

Include reproducible code, source attribution, and tests. Perform three
review-and-fix rounds, then push the HTML, code, and analysis artifacts to GitHub.

## Method choices

- Use the original half-hour series, with no daily aggregation for pair metrics.
- Remove exact repeated values within each household/timestamp key before
  averaging any distinct conflicting readings at that key.
- Use only timestamps observed by both households; do not impute metric inputs.
- Require at least 1,000 common observations out of 1,488 possible January slots.
- Compute signed Pearson r; edge opacity represents its absolute magnitude and
  edge color communicates its sign.
- Calculate continuous MI using JIDT KSG algorithm 1 with k=2, paired-variable
  normalization, and seeded tiny noise for ties. Preserve its nats output and
  negative finite-sample estimates.
- Color nodes with a quadratic scale on each side of the mean household use,
  from green at the minimum through yellow at the mean to red at the maximum.
  Increase both edge width and opacity linearly with strength;
  use blue for positive correlation, yellow for negative, and purple for MI.
- Keep unavailable scores missing. A constant series has undefined Pearson r;
  its empirical discrete MI is zero when there is sufficient overlap.
- Display a sparse selection of links, but compute and retain every unordered pair.
- Treat the results as exploratory synchronous associations, not causal links,
  lagged relationships, or tests of statistical significance.
