"""JIDT KSG-1 execution and an independent nearest-neighbour reference."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from setup_jidt import ensure_jidt, JAR_SHA256

ROOT = Path(__file__).resolve().parents[1]
VERSION = "pearson-pairshift-jidt-1.6.1-ksg1-v3"
DEFAULT_K = 2
DEFAULT_SEED = 42
DEFAULT_NOISE = 1e-8


def calculate(values, work, minimum=1000, k=DEFAULT_K, threads=8, seed=DEFAULT_SEED, noise=DEFAULT_NOISE):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    java, javac = shutil.which("java"), shutil.which("javac")
    if not java or not javac:
        raise RuntimeError("Install a Java JDK 11 or newer with java and javac on PATH")
    if not 1 <= k < minimum <= values.shape[1] or threads < 1 or not np.isfinite(noise) or noise < 0:
        raise ValueError("Require 1 <= k < minimum <= timestamps, positive threads, and nonnegative finite noise")
    jar = ensure_jidt()
    values.astype("<f8").tofile(work / "values.bin")
    settings = {"version": VERSION, "minimum": minimum, "k": k, "seed": seed,
                "noise": noise, "shape": values.shape, "jarSha256": JAR_SHA256}
    signature = hashlib.sha256(json.dumps(settings, sort_keys=True).encode())
    signature.update((work / "values.bin").read_bytes())
    for name in ("JidtKsg.java", "JidtPairMI.java"):
        signature.update((ROOT / "scripts" / name).read_bytes())
    checkpoint = work / ("ksg-checkpoints-" + signature.hexdigest())
    checkpoint.mkdir(exist_ok=True)
    (checkpoint / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    classes = work / "java-classes"
    classes.mkdir(exist_ok=True)
    subprocess.run([javac, "-encoding", "UTF-8", "-cp", str(jar), "-d", str(classes),
                    str(ROOT / "scripts/JidtKsg.java"), str(ROOT / "scripts/JidtPairMI.java")], check=True)
    subprocess.run([java, "-Xmx2g", "-cp", os.pathsep.join([str(classes), str(jar)]), "JidtPairMI",
                    str(work), str(len(values)), str(values.shape[1]), str(minimum), str(k),
                    str(threads), str(seed), str(noise), str(checkpoint)], check=True)
    return np.fromfile(work / "mutual_information.bin", dtype="<f4")


class JavaRandom:
    """Java's documented 48-bit PRNG and nextGaussian sequence for reference checks."""
    def __init__(self, seed):
        self.state = (int(seed) ^ 0x5DEECE66D) & ((1 << 48) - 1)
        self.cached = None

    def bits(self, count):
        self.state = (self.state * 0x5DEECE66D + 11) & ((1 << 48) - 1)
        return self.state >> (48 - count)

    def uniform(self):
        return ((self.bits(26) << 27) + self.bits(27)) / float(1 << 53)

    def gaussian(self):
        if self.cached is not None:
            value, self.cached = self.cached, None
            return value
        while True:
            a, b = 2 * self.uniform() - 1, 2 * self.uniform() - 1
            s = a*a + b*b
            if 0 < s < 1:
                factor = math.sqrt(-2 * math.log(s) / s)
                self.cached = b * factor
                return a * factor


def reference(x, y, k=DEFAULT_K, seed=DEFAULT_SEED, noise=DEFAULT_NOISE):
    from scipy.spatial import cKDTree
    from scipy.special import digamma
    x, y = np.asarray(x, dtype=float).copy(), np.asarray(y, dtype=float).copy()
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return 0.
    x = (x - x.mean()) / x.std(ddof=1)
    y = (y - y.mean()) / y.std(ddof=1)
    random = JavaRandom(seed)
    for t in range(len(x)):
        x[t] += noise * random.gaussian()
        y[t] += noise * random.gaussian()
    joint = np.column_stack((x, y))
    distances = cKDTree(joint).query(joint, k=k+1, p=np.inf)[0][:, -1]
    radii = np.nextafter(distances, 0)
    nx = cKDTree(x[:, None]).query_ball_point(x[:, None], radii, p=np.inf, return_length=True) - 1
    ny = cKDTree(y[:, None]).query_ball_point(y[:, None], radii, p=np.inf, return_length=True) - 1
    return float(digamma(k) + digamma(len(x)) - np.mean(digamma(nx+1) + digamma(ny+1)))
