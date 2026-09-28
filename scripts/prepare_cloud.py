"""Package cleaned inputs and pinned JIDT for a distributed run; no cloud calls."""
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from analyze import load_readings
from setup_jidt import ensure_jidt

ROOT = Path(__file__).resolve().parents[1]

def main():
    target = ROOT / 'work/cloud-input'
    target.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'data/london-smart-meters-2014-01.csv'
    ids, _, values, _ = load_readings(source)
    values.astype('<f8').tofile(target / 'values.bin')
    shutil.copy2(ensure_jidt(), target / 'infodynamics.jar')
    for name in ('JidtKsg.java', 'JidtCloudPairs.java'):
        shutil.copy2(ROOT / 'scripts' / name, target / name)
    with np.load(ROOT / 'analysis/pairs.npz', allow_pickle=False) as archive:
        assert np.array_equal(ids, archive['ids'])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == str(archive['source_sha256'])
    manifest = {'houses': len(ids), 'timestamps': values.shape[1], 'minimum': 1000,
                'k': 2, 'seed': 42, 'noise': 1e-8, 'ids': ids.tolist(),
                'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in target.iterdir() if p.name != 'manifest.json'}}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Prepared {len(ids)} households; no cloud resources started.')

if __name__ == '__main__':
    main()
