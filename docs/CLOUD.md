# Fast KSG execution: prepared, not yet run in the cloud

JIDT KSG-1, k=2, remains the estimator. The 13,043,278 pair slots are independent,
so the prepared Modal runner uses 64 containers, each with eight physical CPU
cores and 4 GiB memory. Shards interleave pair indices to balance households
with different costs. Missing-data intersection, normalization, tie noise,
seed=42+global_pair_index, minimum overlap=1000, and constant handling match
the existing local runner. The pinned JIDT jar is unchanged.

The pilot samples 8,192 pairs spread throughout each shard (524,288 overall).
The slowest shard determines the conservative extrapolation. Full computation
is rejected if projected compute exceeds eight minutes, leaving two minutes
for dispatch, transfer, and merge. This is an estimate, not a ten-minute SLA;
signup, image building, quotas, capacity, and final validation add elapsed time.
Each full Java subprocess stops after nine minutes; functions time out after
ten. There are no automatic retries. Partial results never replace binned MI.

## Account and cost

The user authorized included credit only, with no paid overage. Before any cloud
call, verify the account's available credit and billing settings. Signup/login
requires the user's own identity. No account has been created by this code.

Modal's published Starter plan lists $30/month included compute and 100
containers. Function prices checked on 2026-09-28 are $0.0000131 per physical
core-second and $0.00000222 per GiB-second. Thus 64 × 8 cores plus 64 × 4 GiB
for 600 seconds is $4.365312. A $5 full-run allowance and $2 pilot allowance
include some overhead; the CLI budget is a preflight estimate, not a provider
billing cap. Verify credit-only account enforcement before launch.

Sources actually consulted:
- https://modal.com/pricing
- https://modal.com/docs/guide/resources
- https://modal.com/docs/guide/scale
- https://github.com/jlizier/jidt/wiki/GPU
- https://aws.amazon.com/ec2/instance-types/hpc7a/

JIDT's GPU path primarily parallelizes surrogate significance calculations;
its documentation cautions that individual MI calls may not benefit. CPU pair
sharding is therefore the first benchmark. AWS also offers 192 physical-core
Hpc7a machines, but a new account's quotas and provisioning are unverified.

## Commands after signup and credit verification

```sh
python -m pip install modal==1.5.5
python scripts/prepare_cloud.py
modal token new
modal run scripts/cloud_ksg.py --budget-usd 2
# Only if pilot passes and included credit remains sufficient:
modal run scripts/cloud_ksg.py --full --budget-usd 5
```

The input bundle contains only the cleaned anonymous household matrix, IDs,
provenance, and estimator code/library. Checksums guard the bundle. Complete
shards are checked for exact pair coverage and expected missingness before
writing `work/cloud-analysis/pairs.npz`. Local shard tests compare against the
existing full JIDT runner, including missing observations and tied values.

After cloud completion, use `python scripts/analyze.py --reuse-pairs --output
work/cloud-analysis` for independent sample validation and network rebuilding,
then run artifact and browser checks against those staged outputs. Publishing
the validated results remains a separate step. This script never pushes Git.
