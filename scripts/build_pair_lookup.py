"""Export exact float32 pair results for browser File.slice lookups (10 bytes/pair)."""
import argparse
import json
from pathlib import Path
import struct
import numpy as np
ROOT = Path(__file__).resolve().parents[1]

def build(analysis, output):
    meta = json.loads((analysis / 'network.json').read_text(encoding='utf-8'))['meta']
    with np.load(analysis / 'pairs.npz', allow_pickle=False) as data:
        count = len(data['ids']) * (len(data['ids']) - 1) // 2
        header = {'format':'GSclone-pairs-v1', 'ids':data['ids'].tolist(), 'count':count,
                  'sourceSha256':str(data['source_sha256']), 'miEstimator':meta['miEstimator'],
                  'miAlgorithm':meta.get('miAlgorithm'), 'miK':meta.get('miK'),
                  'miBins':meta.get('miBins'), 'minOverlap':int(data['min_overlap'])}
        raw = json.dumps(header, separators=(',',':')).encode('utf-8')
        correlation, mi, overlap = data['correlation'], data['mutual_information'], data['overlap']
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('wb') as f:
            f.write(b'GSPAIR01'); f.write(struct.pack('<I', len(raw))); f.write(raw)
            for start in range(0, count, 100000):
                end = min(count, start+100000)
                chunk = np.empty(end-start, dtype=[('r','<f4'),('mi','<f4'),('n','<u2')])
                chunk['r'] = correlation[start:end]
                chunk['mi'] = mi[start:end]
                chunk['n'] = overlap[start:end]
                f.write(chunk.tobytes())
        assert output.stat().st_size == 12+len(raw)+10*count
        print(f'Exported {count:,} exact pairs: {output} ({output.stat().st_size:,} bytes)')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis',type=Path,default=ROOT/'analysis')
    parser.add_argument('--output',type=Path,default=ROOT/'analysis/household-pairs.gspairs')
    args=parser.parse_args();build(args.analysis,args.output)
