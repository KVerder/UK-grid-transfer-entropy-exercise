"""Checks on the delivered all-pair archive and sparse display data."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lookup_pair import pair_index


class PairIndexTests(unittest.TestCase):
    def test_every_pair_and_reverse(self):
        expected = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        for position, (first, second) in enumerate(expected):
            self.assertEqual(pair_index(first, second, 4), position)
            self.assertEqual(pair_index(second, first, 4), position)

    def test_diagonal_and_unknown_index_rejected(self):
        for pair in [(0, 0), (-1, 2), (0, 4)]:
            with self.assertRaises(ValueError):
                pair_index(*pair, 4)


@unittest.skipUnless((ROOT / "analysis/network.json").exists(), "Generate analysis artifacts first")
class DeliveredOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = json.loads((ROOT / "analysis/network.json").read_text())
        with np.load(ROOT / "analysis/pairs.npz", allow_pickle=False) as data:
            cls.ids = data["ids"].tolist()
            cls.r = data["correlation"]
            cls.mi = data["mutual_information"]
            cls.overlap = data["overlap"]

    def test_full_population_and_score_domains(self):
        self.assertEqual(self.network["meta"]["miLibrary"], "JIDT")
        self.assertEqual(self.network["meta"]["miLibraryVersion"], "1.6.1")
        self.assertEqual(self.network["meta"]["miNativeUnit"], "bits")
        self.assertEqual(self.network["meta"]["miUnit"], "nats")
        n = len(self.ids)
        self.assertEqual(len(self.r), n * (n - 1) // 2)
        self.assertEqual(len(self.r), len(self.mi))
        self.assertEqual(len(self.r), len(self.overlap))
        self.assertEqual(self.ids, [x["id"] for x in self.network["nodes"]])
        self.assertTrue(np.all(np.abs(self.r[np.isfinite(self.r)]) <= 1))
        self.assertTrue(np.all(self.mi[np.isfinite(self.mi)] >= 0))
        self.assertTrue(np.all(self.mi[np.isfinite(self.mi)] <= np.log(8) + 1e-6))
        enough = self.overlap >= self.network["meta"]["minOverlap"]
        self.assertTrue(np.array_equal(np.isfinite(self.mi), enough))
        self.assertTrue(np.all(~np.isfinite(self.r[~enough])))

    def test_every_candidate_edge_matches_complete_results(self):
        seen = set()
        for edge in self.network["edges"]:
            s, t = edge["s"], edge["t"]
            self.assertLess(s, t)
            self.assertNotIn((s, t), seen)
            seen.add((s, t))
            k = pair_index(s, t, len(self.ids))
            self.assertEqual(edge["n"], int(self.overlap[k]))
            for key, values in [("r", self.r), ("mi", self.mi)]:
                if edge[key] is None:
                    self.assertFalse(np.isfinite(values[k]))
                else:
                    self.assertAlmostEqual(edge[key], float(values[k]), delta=1e-6)

    def test_nodes_have_usable_geometry_and_coverage(self):
        for node in self.network["nodes"]:
            self.assertTrue(np.isfinite([node["x"], node["y"]]).all())
            self.assertGreaterEqual(node["coverage"], 0)
            self.assertLessEqual(node["coverage"], 1)
            self.assertEqual(len(node["daily"]), 31)


if __name__ == "__main__":
    unittest.main()
