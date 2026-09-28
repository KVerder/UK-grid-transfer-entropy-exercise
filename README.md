# GSclone

## Interactive household network

Download and open [household-network.html](household-network.html) in a browser.
It contains its own code and display data and works offline. GitHub's file page
shows the HTML source; use **Download raw file** and open the downloaded file.

- Toggle Pearson correlation and mutual information to change edge weights.
- Node color shows January mean kWh per observed half-hour, from green (lowest)
  to red (highest). Stronger edges are more opaque: blue for positive correlation,
  yellow for negative correlation, and purple for mutual information.
- Search any household ID, inspect its retained strongest connections, and
  compare its daily consumption profile.
- Pan, zoom, change the edge threshold or edge limit, and export visible edges.
- Positions group similar consumption profiles. **They are not household locations.**
- The display is sparse. Every unordered pair is evaluated separately in
  [analysis/pairs.npz](analysis/pairs.npz); omitted links are not necessarily zero.

See [methods](docs/METHODS.md), [the executed specification](docs/task-prompt.md),
and [three review rounds](docs/REVIEWS.md). The original source CSV is preserved.

### Reproduce

Prerequisites: Python 3.11 or newer, a C++17 compiler (`g++` or `clang++` on PATH),
a Java JDK 11 or newer (`java` and `javac` on PATH), and Git LFS.
An OpenMP-capable compiler speeds up Pearson computation. MI is calculated by
JIDT 1.6.1's `MutualInformationCalculatorDiscrete`, using up to eight quantile
bins. The first run downloads the official JIDT release and verifies pinned
SHA-256 checksums; subsequent runs use the verified local jar. See
[JIDT provenance and setup](docs/JIDT.md).

```sh
git lfs install
git clone https://github.com/KVerder/GSclone.git
cd GSclone
git lfs pull
python -m pip install -r requirements.txt
python scripts/analyze.py --threads 8
python scripts/build_html.py
python -m unittest discover -s tests -p "test_*.py"
```

To rebuild the layout/display dataset from existing pair results after changing
display settings, run `python scripts/analyze.py --reuse-pairs`, then rebuild the
HTML. Reuse verifies the input checksum, household IDs, and metric settings.

Retrieve any two distinct household IDs, including a pair hidden in the graph:

```sh
python scripts/lookup_pair.py MAC000002 MAC000003
```

Browser integration checks use Node.js and Playwright:

```sh
npm install
npx playwright install chromium
npm run test:browser
```

Alternatively set `BROWSER_EXECUTABLE` to an installed Chromium/Edge executable.
Browser checks run offline, exercise controls, and save screenshots in the ignored
`test-results/` directory. The static HTML itself requires none of these tools.

## London smart-meter readings: January 2014

[data/london-smart-meters-2014-01.csv](data/london-smart-meters-2014-01.csv) contains **7,525,113 records from 5,108 households**. The file is 382,838,595 bytes and is stored with Git LFS.

Source: **UK Power Networks**, *SmartMeter Energy Consumption Data in London Households*, published through the [London Datastore](https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d). The source is licensed under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).

Downloaded on 2026-09-27 from the official [LCL-FullData.zip archive](https://data.london.gov.uk/download/vqm0d/3527bf39-d93e-4071-8451-df2ade1ea4f2/LCL-FullData.zip), containing `CC_LCL-FullData.csv`.

### Extraction

All 167,932,474 source data rows were scanned. Records were retained when `DateTime >= 2014-01-01 00:00:00` and `DateTime < 2014-02-01 00:00:00`, using the source timestamps without timezone conversion. Both `Std` and `ToU` groups are included. Original column names, field text, record order, and duplicate records are preserved. There is no aggregation, deduplication, or missing-value imputation.

| Column | Meaning |
| --- | --- |
| `LCLid` | Household identifier |
| `stdorToU` | Source tariff group: `Std` or `ToU` |
| `DateTime` | Source reading timestamp |
| `KWH/hh (per half hour) ` | Electricity consumption in kWh per half hour; original header includes a trailing space |

### Validation and source limitations

- Every output record falls within January 2014, with all 31 dates present.
- First timestamp: `2014-01-01 00:00:00.0000000`; last timestamp: `2014-01-31 23:30:00.0000000`.
- All records have four columns and valid half-hour timestamps and finite numeric consumption values. No `Null` consumption values or negative readings were found.
- **5,061 records repeat a household/timestamp key already present in the extract.** These source records are retained. Do not assume household/timestamp keys are unique.
- Household coverage is not necessarily complete. Daily record counts are included in the metadata.
- The downloaded archive passed its ZIP integrity check. [Metadata](data/london-smart-meters-2014-01.metadata.json) includes daily counts, tariff counts, and SHA-256 checksums of the archive and extracted CSV.

### Download with Git LFS

```sh
git lfs install
git clone https://github.com/KVerder/GSclone.git
```

For an existing clone, run `git lfs pull` inside the repository to retrieve the CSV contents.
