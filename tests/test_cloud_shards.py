"""Check cloud shard union and exact agreement with the existing JIDT runner."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ksg import calculate
from setup_jidt import ensure_jidt

class CloudShardTests(unittest.TestCase):
    def test_shards_match_local_pairs_and_pilot_spans_population(self):
        folder = ROOT / 'work/test-runs'
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder, ignore_cleanup_errors=True) as tmp:
            work = Path(tmp)
            data = np.round(np.random.default_rng(71).normal(size=(12, 1100)), 2)
            data[0] = 1
            data[1, :150] = np.nan
            expected = calculate(data, work, threads=2)
            classes = work / 'java-classes'
            jar = ensure_jidt()
            subprocess.run(['javac', '-cp', os.pathsep.join((str(classes), str(jar))),
                            '-d', str(classes), str(ROOT / 'scripts/JidtCloudPairs.java')], check=True)
            combined = np.full(len(expected), np.nan)
            seen = np.zeros(len(expected), dtype=int)
            for limit in (0, 5):
                for shard in range(3):
                    output = work / f'{limit}-{shard}.bin'
                    subprocess.run(['java', '-cp', os.pathsep.join((str(classes), str(jar))), 'JidtCloudPairs',
                                    str(work / 'values.bin'), str(output), '12', '1100', str(shard), '3', str(limit), '2', '1000'], check=True)
                    records = np.fromfile(output, dtype=[('index','<i4'), ('mi','<f4')])
                    indices = records['index']
                    np.testing.assert_array_equal(records['mi'], expected[indices])
                    if not limit:
                        np.testing.assert_array_equal(indices, np.arange(shard, len(expected), 3))
                        combined[indices] = records['mi']; seen[indices] += 1
                    else:
                        self.assertEqual(len(indices), 5)
                        self.assertEqual(indices[0], shard)
                        self.assertEqual(indices[-1], np.arange(shard, len(expected), 3)[-1])
            np.testing.assert_array_equal(seen, 1)
            np.testing.assert_array_equal(combined, expected)

if __name__ == '__main__':
    unittest.main()
