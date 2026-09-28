"""Independent numerical, cleaning, and kernel contract regression checks.

Run: python -m unittest discover -s tests -p "test_analysis*.py" -v
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
import unittest
import warnings

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import mutual_info_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze import (METRIC_VERSION, compile_kernel, compute_jidt_mi, deduplicate, load_readings,
                     pair_offset, quantile_bins, select_edges, validate_pair_archive)


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep compiled test artifacts in the repository's ignored workspace.
        test_runs = Path(__file__).resolve().parents[1] / "work/test-runs"
        test_runs.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=test_runs)
        cls.work = Path(cls.temp.name)
        cls.executable = compile_kernel(cls.work)

    @classmethod
    def tearDownClass(cls):
        # Retry if Windows denies removal of a just-executed test binary.
        for attempt in range(5):
            try:
                cls.temp.cleanup()
                return
            except PermissionError:
                if attempt == 4:
                    if os.name == "nt":
                        warnings.warn(f"Windows retained test artifacts in {cls.work}; numerical checks are unaffected")
                        return
                    raise
                time.sleep(0.2 * 2**attempt)

    def kernel(self, values, minimum=80, bins=8):
        labels, _ = quantile_bins(values, bins)
        centered = values - np.nanmean(values, axis=1, keepdims=True)
        centered.astype("<f8").tofile(self.work / "centered.bin")
        labels.tofile(self.work / "bins.bin")
        subprocess.run([str(self.executable), str(self.work), str(len(values)),
                        str(values.shape[1]), str(minimum), str(bins), "2"], check=True,
                       capture_output=True)
        compute_jidt_mi(self.work, len(values), values.shape[1], minimum, bins, 2)
        return (np.fromfile(self.work / "correlation.bin", dtype="<f4"),
                np.fromfile(self.work / "mutual_information.bin", dtype="<f4"),
                np.fromfile(self.work / "overlap.bin", dtype="<u2"), labels)

    def test_upper_triangle_offsets(self):
        n = 11
        self.assertEqual([pair_offset(i, j, n) for i in range(n) for j in range(i+1, n)],
                         list(range(n*(n-1)//2)))

    def test_cache_requires_matching_schema_settings_and_version(self):
        ids = np.array(["A", "B", "C"])
        cache = {"ids": ids, "correlation": np.array([.2, .3, np.nan], dtype="f4"),
                 "mutual_information": np.array([.1, .2, np.nan], dtype="f4"),
                 "overlap": np.array([1488, 1400, 999], dtype="u2"),
                 "source_sha256": np.array("abc"), "min_overlap": np.array(1000),
                 "mi_bins": np.array(8), "metric_version": np.array(METRIC_VERSION)}
        validate_pair_archive(cache, "abc", ids, 1000, 8)
        cases = [("metric_version", np.array("old")), ("source_sha256", np.array("other")),
                 ("min_overlap", np.array(999)), ("mi_bins", np.array(4)),
                 ("ids", ids[::-1]), ("correlation", np.ones(2, dtype="f4")),
                 ("correlation", np.ones(3, dtype="f8")),
                 ("overlap", np.array([1489, 1400, 999], dtype="u2")),
                 ("mutual_information", np.array([np.nan, .2, np.nan], dtype="f4"))]
        for key, changed in cases:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_pair_archive({**cache, key: changed}, "abc", ids, 1000, 8)
        del cache["metric_version"]
        with self.assertRaises(ValueError):
            validate_pair_archive(cache, "abc", ids, 1000, 8)

    def test_duplicate_policy_averages_distinct_values(self):
        frame = pd.DataFrame({"LCLid": ["a", "a", "a", "a", "b"],
                              "DateTime": [0, 0, 0, 0, 0],
                              "stdorToU": ["Std"]*5, "value": [.2, .2, .2, .4, .8]})
        clean, stats = deduplicate(frame)
        self.assertAlmostEqual(clean.loc[clean.LCLid == "a", "value"].item(), .3)
        self.assertEqual(stats["exactDuplicateRowsRemoved"], 2)
        self.assertEqual(stats["duplicateExtraRows"], 3)
        self.assertEqual(stats["conflictingKeysAveraged"], 1)
        self.assertEqual(stats["distinctConflictRowsCollapsed"], 1)

    def test_quantile_ties_constants_and_missing(self):
        values = np.array([[0, 0, 0, 0, 1, 1, 2, np.nan], [5]*8], dtype=float)
        labels, cuts = quantile_bins(values)
        self.assertEqual(labels[0, -1], -1)
        self.assertTrue(np.all(labels[1] == 0))
        self.assertEqual(cuts[1], [])
        for value in (0, 1, 2):
            self.assertEqual(len(np.unique(labels[0, values[0] == value])), 1)
        self.assertLessEqual(len(np.unique(labels[0, labels[0] >= 0])), 8)

    def test_source_rejects_missing_household_or_timestamp(self):
        for field in ("LCLid", "DateTime"):
            frame = pd.DataFrame({"LCLid": ["MAC000001", "MAC000002"],
                                  "DateTime": ["2014-01-01 00:00:00", "2014-01-01 00:30:00"],
                                  "stdorToU": ["Std", "Std"],
                                  "KWH/hh (per half hour) ": [.1, .2]})
            frame.loc[0, field] = None
            source = self.work / "invalid-source.csv"
            frame.to_csv(source, index=False)
            with self.assertRaisesRegex(ValueError, "missing household IDs or timestamps"):
                load_readings(source)

    def test_kernel_matches_independent_references(self):
        rng = np.random.default_rng(123)
        x = np.linspace(-1, 1, 128)
        values = np.array([x, 3*x + 7, -x, x*x, np.ones(128),
                           rng.normal(size=128), rng.normal(size=128)])
        values[5, :20] = np.nan
        values[6, :70] = np.nan
        corr, mi, overlap, labels = self.kernel(values)
        n = len(values)
        for i in range(n):
            for j in range(i+1, n):
                k = pair_offset(i, j, n)
                valid = np.isfinite(values[i]) & np.isfinite(values[j])
                self.assertEqual(overlap[k], valid.sum())
                if valid.sum() < 80:
                    self.assertTrue(np.isnan(corr[k]) and np.isnan(mi[k]))
                    continue
                a, b = values[i, valid], values[j, valid]
                if np.ptp(a) == 0 or np.ptp(b) == 0:
                    self.assertTrue(np.isnan(corr[k]))
                else:
                    self.assertAlmostEqual(corr[k], pearsonr(a, b).statistic, places=6)
                self.assertAlmostEqual(mi[k], mutual_info_score(labels[i, valid], labels[j, valid]), places=6)
        self.assertAlmostEqual(corr[pair_offset(0, 1, n)], 1)
        self.assertAlmostEqual(corr[pair_offset(0, 2, n)], -1)
        self.assertAlmostEqual(corr[pair_offset(0, 3, n)], 0, places=6)
        self.assertGreater(mi[pair_offset(0, 3, n)], .5)
        self.assertAlmostEqual(mi[pair_offset(0, 4, n)], 0)

    def test_constant_only_on_pair_intersection(self):
        # Both households vary globally, but their shared 1,000 timestamps do not.
        values = np.array([[.1]*1000 + [.2, np.nan], [.3]*1000 + [np.nan, .7]])
        corr, mi, overlap, _ = self.kernel(values, minimum=1000)
        self.assertEqual(overlap[0], 1000)
        self.assertTrue(np.isnan(corr[0]))
        self.assertEqual(mi[0], 0)

    def test_jidt_bits_are_converted_to_nats(self):
        binary = np.tile([0., 1.], 64)
        _, mi, overlap, _ = self.kernel(np.array([binary, binary]), bins=2)
        self.assertEqual(overlap[0], 128)
        self.assertAlmostEqual(mi[0], np.log(2), places=6)

    def test_kernel_rejects_invalid_binary_inputs(self):
        np.arange(20, dtype="<f8").tofile(self.work / "centered.bin")
        labels = np.zeros(20, dtype="i1")
        labels[0] = 8
        labels.tofile(self.work / "bins.bin")
        command = [str(self.executable), str(self.work), "2", "10", "2", "8", "2"]
        invalid = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("Bin code", invalid.stderr)
        labels[:19].tofile(self.work / "bins.bin")
        invalid = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("byte length", invalid.stderr)
        labels[:] = 0
        labels.tofile(self.work / "bins.bin")
        bad = np.arange(20, dtype="<f8")
        bad[0] = np.nan
        bad.tofile(self.work / "centered.bin")
        invalid = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("nonfinite", invalid.stderr)

    def test_sparse_union_retains_both_metrics_and_negative_sign(self):
        corr = np.array([-.95, .5, np.nan, .2, .3, .9])
        mi = np.array([.1, .5, .6, .2, .7, .1])
        overlap = np.full(6, 128, dtype="u2")
        edges = select_edges(corr, mi, overlap, 4, top_k=1)
        by_pair = {(e["s"], e["t"]): e for e in edges}
        self.assertIn((0, 1), by_pair)
        self.assertEqual(by_pair[(0, 1)]["r"], -.95)
        self.assertEqual(by_pair[(0, 1)]["mi"], .1)
        self.assertIsNone(by_pair[(0, 3)]["r"])
        self.assertEqual(by_pair[(0, 3)]["mi"], .6)


if __name__ == "__main__":
    unittest.main()
