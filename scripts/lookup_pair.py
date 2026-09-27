"""Retrieve a pair from the complete results, including pairs hidden in the HTML."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def pair_index(i: int, j: int, size: int) -> int:
    if not 0 <= i < size or not 0 <= j < size or i == j:
        raise ValueError("Choose two distinct household indices within the dataset")
    i, j = min(i, j), max(i, j)
    return i * (2 * size - i - 1) // 2 + j - i - 1


def lookup(path: Path, first: str, second: str) -> dict:
    with np.load(path, allow_pickle=False) as data:
        ids = data["ids"].tolist()
        try:
            i, j = ids.index(first), ids.index(second)
        except ValueError as exc:
            raise ValueError("Both household IDs must be present in the results") from exc
        k = pair_index(i, j, len(ids))
        def score(key: str):
            value = float(data[key][k])
            return value if np.isfinite(value) else None
        return {
            "household_a": first,
            "household_b": second,
            "pearson_r": score("correlation"),
            "mutual_information_nats": score("mutual_information"),
            "common_half_hours": int(data["overlap"][k]),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("household_a")
    parser.add_argument("household_b")
    parser.add_argument("--pairs", type=Path, default=Path(__file__).resolve().parents[1] / "analysis/pairs.npz")
    args = parser.parse_args()
    try:
        print(json.dumps(lookup(args.pairs, args.household_a, args.household_b), indent=2, allow_nan=False))
    except ValueError as exc:
        parser.error(str(exc))
