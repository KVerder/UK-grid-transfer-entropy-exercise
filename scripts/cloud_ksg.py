"""Modal CPU shards. Default is a pilot; full execution is explicit and benchmark-gated.

pip install modal==1.5.5
python scripts/prepare_cloud.py
modal token new
modal run scripts/cloud_ksg.py --budget-usd 2
modal run scripts/cloud_ksg.py --full --budget-usd 5
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import modal

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'work/cloud-input'
SHARDS = 64
CORES = 8
# Published Modal Function rates checked 2026-09-28; verify again before launching.
RATE = CORES * 0.0000131 + 4 * 0.00000222
app = modal.App('gsclone-ksg2')
image = (modal.Image.debian_slim(python_version='3.12')
         .apt_install('openjdk-17-jdk-headless')
         .add_local_dir(INPUT, '/inputs', copy=True)
         .run_commands('mkdir -p /classes && javac -cp /inputs/infodynamics.jar -d /classes /inputs/JidtKsg.java /inputs/JidtCloudPairs.java'))

@app.function(image=image, cpu=(CORES, CORES), memory=(4096, 4096),
              max_containers=SHARDS, timeout=600, retries=0, scaledown_window=2)
def run_shard(shard: int, limit: int):
    manifest = json.loads(Path('/inputs/manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((Path('/inputs') / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Input checksum mismatch: {name}')
    output = Path('/tmp/result.bin')
    started = time.monotonic()
    command = ['java', '-Xmx2g', '-XX:ActiveProcessorCount=8', '-cp',
               '/classes:/inputs/infodynamics.jar', 'JidtCloudPairs',
               '/inputs/values.bin', str(output), str(manifest['houses']),
               str(manifest['timestamps']), str(shard), str(SHARDS),
               str(limit), str(CORES), str(manifest['minimum'])]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=90 if limit else 540)
    timing = json.loads(result.stdout.strip().splitlines()[-1])
    timing['wallSeconds'] = time.monotonic() - started
    return timing, output.read_bytes()

@app.local_entrypoint()
def main(full: bool = False, budget_usd: float = 0):
    import numpy as np
    from datetime import datetime, timezone
    manifest_text = (INPUT / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_text)
    identity = hashlib.sha256(manifest_text).hexdigest()
    destination = ROOT / 'work/cloud-results' / identity
    destination.mkdir(parents=True, exist_ok=True)
    pilot_path = destination / 'pilot.json'
    status_path = ROOT / 'work/cloud-ksg-status.json'
    def status(state, **fields):
        status_path.write_text(json.dumps({'status': state, 'updatedUtc': datetime.now(timezone.utc).isoformat(), **fields}, indent=2))
    if budget_usd <= 0:
        raise ValueError('An explicit approved budget is required, including when using free credits.')
    if full:
        if not pilot_path.exists():
            raise ValueError('Run the cloud pilot first.')
        pilot = json.loads(pilot_path.read_text())
        if time.time() - pilot['time'] > 86400:
            raise ValueError('Pilot is older than 24 hours; benchmark again.')
        if pilot['projectedComputeSeconds'] > 480:
            raise ValueError('Pilot does not support a 10-minute run with overhead allowance.')
        if budget_usd < SHARDS * RATE * 600 + 0.5:
            raise ValueError('Budget is below the conservative compute ceiling plus setup allowance.')
    # No automatic full-run launch, retries, or publication after the pilot.
    limit = 0 if full else 8192
    if not full and budget_usd < 2:
        raise ValueError('Allow at least $2 of credit/budget for the distributed pilot.')
    status('running', stage='full' if full else 'pilot', shards=SHARDS, manifest=identity)
    started = time.monotonic()
    timings = []
    try:
        for timing, binary in run_shard.map(range(SHARDS), [limit] * SHARDS, order_outputs=False):
            timings.append(timing)
            (destination / f"{'full' if full else 'pilot'}-{timing['shard']:02d}.bin").write_bytes(binary)
            status('running', stage='full' if full else 'pilot', completedShards=len(timings), shards=SHARDS)
        elapsed = time.monotonic() - started
        if not full:
            # Slowest shard, including JVM startup; reserve time for scale-up/merge.
            projected = max(t['wallSeconds'] * t['available'] / t['pairs'] for t in timings)
            report = {'time': time.time(), 'manifest': identity, 'elapsedSeconds': elapsed,
                      'projectedComputeSeconds': projected, 'timings': timings,
                      'tenMinuteCandidate': projected <= 480}
            pilot_path.write_text(json.dumps(report, indent=2))
            status('pilot_complete', **{k:v for k,v in report.items() if k != 'timings'})
            print(json.dumps({k:v for k,v in report.items() if k != 'timings'}, indent=2))
            return
        total = manifest['houses'] * (manifest['houses'] - 1) // 2
        mi, seen = np.full(total, np.nan, dtype='<f4'), np.zeros(total, dtype=bool)
        for shard in range(SHARDS):
            records = np.fromfile(destination / f'full-{shard:02d}.bin', dtype=[('index','<i4'), ('mi','<f4')])
            expected = np.arange(shard, total, SHARDS)
            if not np.array_equal(records['index'], expected):
                raise ValueError(f'Missing, duplicated, or reordered pairs in shard {shard}')
            mi[expected], seen[expected] = records['mi'], True
        if not seen.all() or np.isinf(mi).any():
            raise ValueError('Incomplete or invalid MI matrix')
        with np.load(ROOT / 'analysis/pairs.npz', allow_pickle=False) as prior:
            if str(prior['source_sha256']) != manifest['sourceSha256'] or prior['ids'].tolist() != manifest['ids']:
                raise ValueError('Source identity changed')
            if not np.array_equal(np.isfinite(mi), prior['overlap'] >= manifest['minimum']):
                raise ValueError('MI eligibility differs from observed overlap')
            output = ROOT / 'work/cloud-analysis'
            output.mkdir(exist_ok=True)
            np.savez_compressed(output / 'pairs.npz', ids=prior['ids'], correlation=prior['correlation'],
                                overlap=prior['overlap'], source_sha256=prior['source_sha256'],
                                mutual_information=mi, min_overlap=manifest['minimum'], mi_k=2,
                                mi_noise=1e-8, mi_seed=42,
                                metric_version='pearson-pairshift-jidt-1.6.1-ksg1-v3')
        status('computed_awaiting_validation', elapsedSeconds=elapsed, pairs=total)
        print('Staged full MI matrix. Run analyze.py --reuse-pairs --output work/cloud-analysis to validate and build; nothing published.')
    except BaseException as error:
        status('failed', reason=str(error))
        raise
