"""Check exact exported pair records against the original JIDT archive."""
import json
from pathlib import Path
import struct
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

class PairLookupTests(unittest.TestCase):
    def test_export_matches_archive(self):
        with (ROOT/'analysis/household-pairs.gspairs').open('rb') as f, np.load(ROOT/'analysis/pairs.npz',allow_pickle=False) as source:
            self.assertEqual(f.read(8),b'GSPAIR01')
            length=struct.unpack('<I',f.read(4))[0]
            header=json.loads(f.read(length)); offset=f.tell()
            self.assertEqual(header['ids'],source['ids'].tolist())
            self.assertEqual(header['sourceSha256'],str(source['source_sha256']))
            r,mi,n=source['correlation'],source['mutual_information'],source['overlap']
            indices=np.unique(np.r_[0,len(r)-1,np.random.default_rng(712).integers(0,len(r),1024)])
            for i in indices:
                f.seek(offset+int(i)*10)
                record=struct.unpack('<ffH',f.read(10))
                np.testing.assert_array_equal(record,(r[i],mi[i],n[i]))

if __name__=='__main__': unittest.main()
