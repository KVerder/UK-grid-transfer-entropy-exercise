"""Extract original CSV records for the first N household IDs in sorted order."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]


def export(source, destination, count=10):
    if count < 1 or source.resolve() == destination.resolve():
        raise ValueError("Require a positive count and a separate output file")
    with source.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream)
        header = next(rows)
        id_column = header.index("LCLid")
        ids = sorted({row[id_column] for row in rows})[:count]
    selected = set(ids)
    counts = Counter()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open(newline="", encoding="utf-8-sig") as stream, destination.open("w", newline="", encoding="utf-8") as output:
        rows, writer = csv.reader(stream), csv.writer(output)
        writer.writerow(next(rows))
        for row in rows:
            if row[id_column] in selected:
                writer.writerow(row)
                counts[row[id_column]] += 1
    # Reopen the delivered file and verify its header, household set, and row counts.
    with destination.open(newline="", encoding="utf-8") as stream:
        rows = csv.reader(stream)
        assert next(rows) == header
        actual = Counter(row[id_column] for row in rows)
    assert actual == counts and set(actual) == selected
    return {"file": str(destination.resolve()), "households": ids,
            "rows": sum(counts.values()), "rowsPerHousehold": dict(sorted(counts.items())),
            "selection": "First household IDs in ascending alphabetical order",
            "records": "Original January 2014 values, columns, order, and duplicates retained"}


def export_wide(source, destination, count=10):
    """One aligned half-hour row and one value column per household."""
    raw = ROOT / "work/household-export-original.csv"
    raw.parent.mkdir(parents=True, exist_ok=True)
    metadata = export(source, raw, count)
    ids = metadata["households"]
    cells = {}
    with raw.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        value_column = next(name for name in reader.fieldnames if name.strip().startswith("KWH/hh"))
        for row in reader:
            time = datetime.fromisoformat(row["DateTime"])
            if time.year != 2014 or time.month != 1 or time.minute not in (0,30) or time.second:
                raise ValueError("Expected January 2014 half-hour readings")
            cells.setdefault((time,row["LCLid"]),set()).add(Decimal(row[value_column]))
    grid = [datetime(2014,1,1)+timedelta(minutes=30*i) for i in range(1488)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w",newline="",encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["DateTime",*ids])
        for time in grid:
            values = []
            for household in ids:
                observed = cells.get((time,household),set())
                values.append(str(sum(observed)/len(observed)) if observed else "")
            writer.writerow([time.isoformat(sep=" "),*values])
    with destination.open(newline="",encoding="utf-8") as stream:
        reader = csv.reader(stream)
        assert next(reader) == ["DateTime",*ids]
        rows = list(reader)
    assert len(rows)==1488 and all(len(row)==len(ids)+1 for row in rows)
    for row,time in zip(rows,grid):
        for household,value in zip(ids,row[1:]):
            observed = cells.get((time,household),set())
            assert (Decimal(value)==sum(observed)/len(observed)) if observed else value==""
    return {"file":str(destination.resolve()),"households":ids,"timestampRows":len(grid),
            "originalRows":metadata["rows"],"duplicateRowsCollapsed":metadata["rows"]-len(cells),
            "conflictingCellsAveraged":sum(len(values)>1 for values in cells.values()),
            "missingCellsBlank":len(ids)*len(grid)-len(cells),"unit":"kWh per half-hour"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/london-smart-meters-2014-01.csv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(export_wide(args.input, args.output, args.count), indent=2))
