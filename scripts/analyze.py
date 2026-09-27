"""Reproduce the January 2014 London household network, including every pair.

Run from the repository root: python scripts/analyze.py
A C++17 compiler with optional OpenMP is required for a fresh computation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PERIOD_START = "2014-01-01"
PERIOD_END = "2014-02-01"
SOURCE = "https://data.london.gov.uk/dataset/smartmeter-energy-consumption-data-in-london-households-vqm0d"
METRIC_VERSION = "pearson-pairshift-empirical-quantile-v1"


def pair_offset(i: int | np.ndarray, j: int | np.ndarray, n: int):
    """Upper triangle, row-major, i < j: (0,1),(0,2),...,(n-2,n-1)."""
    return i * (2 * n - i - 1) // 2 + j - i - 1


def quantile_bins(values: np.ndarray, max_bins: int = 8) -> tuple[np.ndarray, list]:
    """Global per-household bins; equal values never split, missing remains -1."""
    if max_bins < 2 or max_bins > 32:
        raise ValueError("max_bins must be between 2 and 32")
    result = np.full(values.shape, -1, dtype=np.int8)
    edges = []
    for i, row in enumerate(values):
        valid = np.isfinite(row)
        observed = row[valid]
        if not observed.size:
            edges.append([])
            continue
        cuts = np.unique(np.quantile(observed, np.arange(1, max_bins) / max_bins))
        cuts = cuts[(cuts > observed.min()) & (cuts < observed.max())]
        result[i, valid] = np.searchsorted(cuts, observed, side="right")
        edges.append(cuts.tolist())
    return result, edges


def deduplicate(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove repeated value records, then average distinct conflicting values.

    Tariff is metadata and does not multiply a repeated measurement's weight.
    """
    key = ["LCLid", "DateTime"]
    exact = int(frame.duplicated().sum())
    unique_values = frame.drop_duplicates(key + ["value"])
    grouped = unique_values.groupby(key, observed=True, sort=True)["value"]
    group_sizes = grouped.size()
    result = grouped.mean().reset_index()
    quality = {
        "sourceRows": int(len(frame)),
        "uniqueHouseholdTimestampKeys": int(len(result)),
        "duplicateExtraRows": int(len(frame) - len(result)),
        "exactDuplicateRowsRemoved": exact,
        "repeatedValueRowsRemoved": int(len(frame) - len(unique_values)),
        "conflictingKeysAveraged": int((group_sizes > 1).sum()),
        "distinctConflictRowsCollapsed": int((group_sizes - 1).sum()),
    }
    return result, quality


def load_readings(path: Path):
    header = pd.read_csv(path, nrows=0).columns.tolist()
    value_col = next(c for c in header if c.strip().startswith("KWH/hh"))
    frame = pd.read_csv(path, dtype={"LCLid": "category", "stdorToU": "category",
                                    "DateTime": "category", value_col: "float64"})
    frame = frame.rename(columns={value_col: "value"})
    if frame[["LCLid", "DateTime"]].isna().any().any():
        raise ValueError("CSV contains missing household IDs or timestamps")
    if not np.isfinite(frame["value"].to_numpy()).all():
        raise ValueError("CSV contains nonfinite readings; resolve source values explicitly")
    timestamp_categories = pd.to_datetime(frame["DateTime"].cat.categories)
    grid = pd.date_range(PERIOD_START, PERIOD_END, freq="30min", inclusive="left")
    category_slots = grid.get_indexer(timestamp_categories)
    if np.any(category_slots < 0):
        raise ValueError("CSV contains readings outside January 2014 or off the half-hour grid")
    timestamp_codes = frame["DateTime"].cat.codes.to_numpy()
    if np.any(timestamp_codes < 0):
        raise ValueError("CSV contains missing timestamps")
    frame["DateTime"] = category_slots[timestamp_codes]
    ids = np.array(sorted(frame["LCLid"].unique().tolist()))
    tariff_counts = frame.groupby("LCLid", observed=True)["stdorToU"].nunique()
    tariffs = frame.groupby("LCLid", observed=True)["stdorToU"].first().reindex(ids).astype(str).tolist()
    clean, quality = deduplicate(frame)
    quality["householdsWithConflictingTariffMetadata"] = int((tariff_counts > 1).sum())
    values = np.full((len(ids), len(grid)), np.nan, dtype=np.float64)
    indices = pd.Index(ids).get_indexer(clean["LCLid"])
    if np.any(indices < 0):
        raise ValueError("Cannot map a source household to its output index")
    values[indices, clean["DateTime"].to_numpy(dtype=int)] = clean["value"].to_numpy()
    quality["missingHouseholdHalfHours"] = int(np.isnan(values).sum())
    return ids, tariffs, values, quality


def compile_kernel(work: Path) -> Path:
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        raise RuntimeError("Install g++ or clang++ with C++17 support")
    executable = work / ("compute_pairs.exe" if os.name == "nt" else "compute_pairs")
    base = [compiler, "-O3", "-std=c++17", str(ROOT / "scripts" / "compute_pairs.cpp"), "-o", str(executable)]
    result = subprocess.run(base + ["-fopenmp"], capture_output=True, text=True)
    if result.returncode:
        print("OpenMP unavailable; compiling a single-thread kernel", flush=True)
        subprocess.run(base, check=True)
    return executable


def reference_pair(x, y, bx, by, minimum=1000, max_bins=8):
    """Small independent NumPy reference, used by unit and integration tests."""
    valid = np.isfinite(x) & np.isfinite(y)
    n = int(valid.sum())
    if n < minimum:
        return np.nan, np.nan, n
    a, b = x[valid], y[valid]
    da, db = a - a.mean(), b - b.mean()
    denominator = np.sqrt(np.dot(da, da) * np.dot(db, db))
    r = float(np.dot(da, db) / denominator) if denominator > 0 else np.nan
    counts = np.bincount(bx[valid].astype(int) * max_bins + by[valid],
                         minlength=max_bins * max_bins).reshape(max_bins, max_bins)
    p = counts / n
    independent = p.sum(axis=1, keepdims=True) * p.sum(axis=0, keepdims=True)
    nonzero = p > 0
    mi = float(np.sum(p[nonzero] * np.log(p[nonzero] / independent[nonzero])))
    return r, max(0., mi), n


def compute_pairs(values, bins, work: Path, minimum: int, max_bins: int, threads: int):
    centered = values - np.nanmean(values, axis=1, keepdims=True)
    # Center once for numerical stability; kernel still recenters each intersection.
    centered.astype("<f8").tofile(work / "centered.bin")
    bins.tofile(work / "bins.bin")
    executable = compile_kernel(work)
    subprocess.run([str(executable), str(work), str(len(values)), str(values.shape[1]),
                    str(minimum), str(max_bins), str(threads)], check=True)
    return (np.fromfile(work / "correlation.bin", dtype="<f4"),
            np.fromfile(work / "mutual_information.bin", dtype="<f4"),
            np.fromfile(work / "overlap.bin", dtype="<u2"))


def validate_pair_archive(saved, source_hash, ids, minimum, max_bins, timestamp_count=1488):
    """Reject incompatible, stale, or damaged cached pair arrays, even under python -O."""
    required = {"ids", "correlation", "mutual_information", "overlap", "source_sha256",
                "min_overlap", "mi_bins", "metric_version"}
    if not required.issubset(saved.keys()):
        raise ValueError("Pair archive lacks required schema/version metadata; recompute pairs")
    # NpzFile decompresses on every indexing operation; load each member once.
    saved = {key: saved[key] for key in required}
    if np.ndim(saved["metric_version"]) != 0 or str(saved["metric_version"]) != METRIC_VERSION:
        raise ValueError("Metric version changed; recompute pairs")
    if np.ndim(saved["source_sha256"]) != 0 or str(saved["source_sha256"]) != source_hash:
        raise ValueError("Input checksum changed; cannot reuse pairs")
    if (np.ndim(saved["min_overlap"]) != 0 or np.ndim(saved["mi_bins"]) != 0 or
            int(saved["min_overlap"]) != minimum or int(saved["mi_bins"]) != max_bins):
        raise ValueError("Analysis settings changed; cannot reuse pairs")
    if saved["ids"].dtype.kind != "U" or not np.array_equal(saved["ids"], ids):
        raise ValueError("Household ordering changed; cannot reuse pairs")
    count = len(ids) * (len(ids)-1) // 2
    for name, dtype in (("correlation", np.float32), ("mutual_information", np.float32),
                        ("overlap", np.uint16)):
        if saved[name].shape != (count,) or saved[name].dtype != dtype:
            raise ValueError(f"Invalid pair array shape or dtype: {name}")
    corr, mi, overlap = saved["correlation"], saved["mutual_information"], saved["overlap"]
    if np.any(overlap > timestamp_count):
        raise ValueError("Pair overlap exceeds the timestamp grid")
    valid_r, valid_mi = np.isfinite(corr), np.isfinite(mi)
    if np.isinf(corr).any() or np.isinf(mi).any():
        raise ValueError("Infinite metric in pair archive")
    if np.any(np.abs(corr[valid_r]) > 1) or np.any(mi[valid_mi] < 0) or np.any(mi[valid_mi] > np.log(max_bins) + 1e-6):
        raise ValueError("Pair metric outside mathematical bounds")
    if not np.array_equal(valid_mi, overlap >= minimum) or np.any(valid_r & ~valid_mi):
        raise ValueError("Pair eligibility disagrees with overlap")
    return corr, mi, overlap


def select_edges(correlation, information, overlap, n, top_k=12):
    """Union of endpoint top-k |r| and top-k MI. Every edge retains both scores."""
    selected = {}
    all_indices = np.arange(n, dtype=np.int64)
    for i in range(n):
        others = all_indices[all_indices != i]
        positions = pair_offset(np.minimum(i, others), np.maximum(i, others), n)
        for metric, rank_name in [(np.abs(correlation[positions]), "rankR"),
                                   (information[positions], "rankMi")]:
            valid = np.flatnonzero(np.isfinite(metric))
            # Stable household-index tie breaking makes graph selection reproducible.
            ranked = valid[np.lexsort((others[valid], -metric[valid]))[:top_k]]
            for rank, local in enumerate(ranked, 1):
                k = int(positions[local])
                edge = selected.setdefault(k, {"s": int(min(i, others[local])),
                                                "t": int(max(i, others[local]))})
                edge[rank_name] = min(rank, edge.get(rank_name, rank))
    edges = []
    for k, edge in sorted(selected.items()):
        edge.update(r=float(correlation[k]) if np.isfinite(correlation[k]) else None,
                    mi=float(information[k]) if np.isfinite(information[k]) else None,
                    n=int(overlap[k]))
        edges.append(edge)
    return edges


def similarity_layout(values, threads=8):
    """Seeded t-SNE of 32 SVD components of standardized household series.

    Missing slots are household-mean filled ONLY here. Unit-length, centered
    complete series have squared Euclidean distance 2(1-r), so the embedding
    groups positive correlation rather than large absolute correlation.
    """
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.manifold import TSNE
    from threadpoolctl import threadpool_limits

    centered = values - np.nanmean(values, axis=1, keepdims=True)
    centered = np.nan_to_num(centered, nan=0)
    norm = np.linalg.norm(centered, axis=1)
    active = np.nanmax(values, axis=1) > np.nanmin(values, axis=1)
    unit = centered[active] / norm[active, None]
    components = min(32, unit.shape[0] - 1, unit.shape[1] - 1)
    if components < 2:
        return np.zeros((len(values), 2)), np.full(len(values), -1, dtype=int), {"layoutSeed": 42}
    with threadpool_limits(limits=threads):
        reduced = TruncatedSVD(n_components=components, n_iter=7, random_state=42).fit_transform(unit)
        cluster_count = min(32, max(2, int(np.sqrt(len(unit) / 5))))
        labels = KMeans(n_clusters=cluster_count, random_state=42, n_init=10).fit_predict(reduced)
        xy_active = TSNE(n_components=2, perplexity=min(40, (len(unit)-1)/3),
                         learning_rate="auto", init="pca", random_state=42,
                         max_iter=1000, metric="euclidean", n_jobs=threads).fit_transform(reduced)
    xy = np.zeros((len(values), 2))
    xy[active] = xy_active
    scale = max(float(np.max(np.abs(xy_active))), 1.)
    xy /= scale
    # Constant series have undefined correlation and are explicitly placed aside.
    missing = np.flatnonzero(~active)
    if len(missing):
        angles = np.arange(len(missing)) * 2 * np.pi / len(missing)
        xy[missing] = np.column_stack((1.15 + .05 * np.cos(angles), .05 * np.sin(angles)))
    clusters = np.full(len(values), -1, dtype=int)
    clusters[active] = labels
    return xy, clusters, {"layoutSeed": 42, "layoutComponents": components,
                           "layoutClusters": cluster_count, "layoutPerplexity": 40,
                           "layoutMeanImputationOnly": True}


def validate_sample(values, bins, corr, mi, overlap, minimum, max_bins, sample_size=256):
    from scipy.stats import pearsonr
    from sklearn.metrics import mutual_info_score
    rng = np.random.default_rng(42)
    n = len(values)
    pairs = {(0, n-1)}
    while len(pairs) < min(sample_size, n*(n-1)//2):
        i, j = sorted(rng.choice(n, size=2, replace=False).tolist())
        pairs.add((i, j))
    max_corr_error, max_mi_error = 0., 0.
    for i, j in sorted(pairs):
        k = int(pair_offset(i, j, n))
        valid = np.isfinite(values[i]) & np.isfinite(values[j])
        count = int(valid.sum())
        assert count == int(overlap[k]), (i, j, "overlap")
        if count < minimum:
            assert np.isnan(corr[k]) and np.isnan(mi[k])
            continue
        x, y = values[i, valid], values[j, valid]
        expected_r = pearsonr(x, y).statistic if np.ptp(x) > 0 and np.ptp(y) > 0 else np.nan
        expected_mi = mutual_info_score(bins[i, valid], bins[j, valid])
        assert np.isclose(corr[k], expected_r, atol=1e-6, equal_nan=True), (i, j, "correlation")
        assert np.isclose(mi[k], expected_mi, atol=1e-6), (i, j, "MI")
        if np.isfinite(expected_r):
            max_corr_error = max(max_corr_error, float(abs(corr[k] - expected_r)))
        max_mi_error = max(max_mi_error, abs(float(mi[k]) - float(expected_mi)))
    return {"sampledPairs": len(pairs), "seed": 42,
            "pearsonReference": "scipy.stats.pearsonr", "miReference": "sklearn.metrics.mutual_info_score",
            "maximumAbsoluteCorrelationError": max_corr_error, "maximumAbsoluteMiError": max_mi_error}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/london-smart-meters-2014-01.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis")
    parser.add_argument("--work", type=Path, default=ROOT / "work/analysis")
    parser.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--min-overlap", type=int, default=1000)
    parser.add_argument("--mi-bins", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--reuse-pairs", action="store_true", help="Reuse existing pairs.npz; verify input checksum and settings")
    args = parser.parse_args()
    if not 2 <= args.min_overlap <= 1488 or args.threads < 1 or args.top_k < 1:
        parser.error("Require 2 <= min-overlap <= 1488, threads >= 1, top-k >= 1")
    started = time.perf_counter()
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    with args.input.open("rb") as input_file:
        source_hash = hashlib.file_digest(input_file, "sha256").hexdigest()
    print("Loading and resolving duplicate records", flush=True)
    ids, tariffs, values, quality = load_readings(args.input)
    print(f"Loaded {len(ids):,} households; quality={quality}", flush=True)
    bins, bin_edges = quantile_bins(values, args.mi_bins)
    print("Computing all unordered household pairs", flush=True)
    if args.reuse_pairs:
        with np.load(args.output / "pairs.npz", allow_pickle=False) as saved:
            corr, mi, overlap = validate_pair_archive(saved, source_hash, ids, args.min_overlap,
                                                     args.mi_bins, values.shape[1])
    else:
        corr, mi, overlap = compute_pairs(values, bins, args.work, args.min_overlap, args.mi_bins, args.threads)
        np.savez_compressed(args.output / "pairs.npz", ids=ids, correlation=corr,
                            mutual_information=mi, overlap=overlap, source_sha256=source_hash,
                            min_overlap=args.min_overlap, mi_bins=args.mi_bins, metric_version=METRIC_VERSION)
    pair_seconds = time.perf_counter() - started
    print(f"Pair matrix ready after {pair_seconds:.1f}s; independently checking sampled pairs", flush=True)
    validation = validate_sample(values, bins, corr, mi, overlap, args.min_overlap, args.mi_bins)
    print("Selecting sparse display edges and embedding household similarity", flush=True)
    edges = select_edges(corr, mi, overlap, len(ids), args.top_k)
    xy, clusters, layout_meta = similarity_layout(values, args.threads)
    counts = np.isfinite(values).sum(axis=1)
    means = np.nanmean(values, axis=1)
    variances = np.nanvar(values, axis=1)
    variances[np.nanmax(values, axis=1) == np.nanmin(values, axis=1)] = 0
    daily_sum = np.nansum(values.reshape(len(ids), 31, 48), axis=2)
    daily_count = np.isfinite(values.reshape(len(ids), 31, 48)).sum(axis=2)
    daily = np.divide(daily_sum, daily_count, out=np.full_like(daily_sum, np.nan), where=daily_count > 0)
    nodes = [{"id": str(hid), "tariff": tariffs[i], "x": round(float(xy[i, 0]), 6),
              "y": round(float(xy[i, 1]), 6), "cluster": int(clusters[i]),
              "coverage": float(counts[i] / values.shape[1]), "observations": int(counts[i]),
              "mean": float(means[i]), "standardDeviation": float(np.sqrt(variances[i])),
              "eligible": bool(counts[i] >= args.min_overlap),
              "correlationEligible": bool(counts[i] >= args.min_overlap and variances[i] > 0),
              "miEligible": bool(counts[i] >= args.min_overlap),
              "effectiveBins": int(len(np.unique(bins[i, bins[i] >= 0]))),
              "daily": [float(v) if np.isfinite(v) else None for v in daily[i]]}
             for i, hid in enumerate(ids)]
    meta = {"title": "London households · January 2014", "source": SOURCE,
            "period": "2014-01", "timestampCount": int(values.shape[1]),
            "householdCount": int(len(ids)), "pairCount": int(len(corr)),
            "validCorrelationPairs": int(np.isfinite(corr).sum()),
            "validMiPairs": int(np.isfinite(mi).sum()),
            "insufficientOverlapPairs": int((overlap < args.min_overlap).sum()),
            "constantHouseholds": int((variances == 0).sum()),
            "householdsBelowMinOverlap": int((counts < args.min_overlap).sum()),
            "minOverlap": args.min_overlap, "miBins": args.mi_bins, "miUnit": "nats",
            "miEstimator": "Empirical plug-in MI of tied-value-preserving per-household quantile bins",
            "metricVersion": METRIC_VERSION,
            "layout": "similarity", "layoutMethod": "Seeded t-SNE on 32 SVD components of centered unit-length series",
            "locationAvailable": False,
            "locationNote": "No household coordinates are provided in the published consumption CSV; positions show consumption similarity, not geography.",
            "topK": args.top_k, "displayEdgeCount": len(edges),
            "edgeSelection": "Union of each household's top-k absolute Pearson correlations and top-k mutual information scores",
            "dailyUnit": "Mean kWh per observed half-hour, by date", "sourceSha256": source_hash,
            "duplicatePolicy": "Remove repeated household/timestamp/value records, then average distinct conflicting values",
            "missingPolicy": "No metric imputation; use observed timestamp intersection for both metrics",
            "miCaveat": "Finite-sample empirical MI is upward-biased and does not establish statistical significance or causality. Serial dependence and shared daily/weekly patterns are not removed.",
            "quality": quality, "validation": validation, **layout_meta}
    network = {"meta": meta, "nodes": nodes, "edges": edges}
    (args.output / "network.json").write_text(json.dumps(network, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    manifest = {**meta, "totalRuntimeSeconds": round(time.perf_counter() - started, 2),
                "pairStageSeconds": round(pair_seconds, 2),
                "pairFile": "pairs.npz", "pairOrdering": "Row-major upper triangle i<j; k=i*(2*N-i-1)//2+(j-i-1)",
                "arrays": {"ids": "Sorted household IDs", "correlation": "float32; NaN for insufficient overlap or zero variance on overlap",
                           "mutual_information": "float32 nats; NaN for insufficient overlap, zero for a constant overlapping binned series",
                           "overlap": "uint16 shared observed half-hours"},
                "binThresholds": {str(hid): cuts for hid, cuts in zip(ids, bin_edges)}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"households": len(ids), "pairs": len(corr), "edges": len(edges),
                      "validCorrelationPairs": meta["validCorrelationPairs"], "validMiPairs": meta["validMiPairs"],
                      "runtimeSeconds": manifest["totalRuntimeSeconds"], "validation": validation}), flush=True)


if __name__ == "__main__":
    main()
