"""Run, validate, and deliver the full KSG-1 k=2 analysis with resumable checkpoints.

Git publication is a separate step after this runner reports complete.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--deliver-html", type=Path, required=True)
    args = parser.parse_args()
    if not args.node:
        parser.error("Node.js is required for the final browser checks")
    work = ROOT / "work"
    status_file = work / "full-ksg-status.json"
    staging = work / "ksg-full-analysis"
    html = work / "ksg-full-output.html"
    state = {"pid": os.getpid(), "algorithm": "JIDT KSG-1", "k": 2,
             "startedUtc": datetime.now(timezone.utc).isoformat(), "status": "running"}

    def status(stage, **extra):
        state.update(stage=stage, updatedUtc=datetime.now(timezone.utc).isoformat(), **extra)
        temporary = status_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(status_file)
        print(json.dumps(state), flush=True)

    def run(command, env=None):
        subprocess.run(command, cwd=ROOT, env=env, check=True)

    try:
        status("analysis")
        run([sys.executable, "-u", "scripts/analyze.py", "--mi-k", "2", "--threads", str(args.threads),
             "--work", str(work / "ksg-full"), "--output", str(staging)])
        status("artifact_validation")
        env = {**os.environ, "ANALYSIS_DIR": str(staging), "HTML_PATH": str(html)}
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_outputs.py", "-v"], env)
        manifest = json.loads((staging / "manifest.json").read_text())
        if manifest.get("miAlgorithm") != 1 or manifest.get("miK") != 2 or manifest.get("householdCount") != 5108:
            raise ValueError("Full-run estimator or household count does not match the requested run")
        status("html_and_browser_validation")
        run([sys.executable, "scripts/build_html.py", "--data", str(staging / "network.json"), "--output", str(html)])
        run([args.node, "tests/browser.cjs"], env)
        status("delivery")
        for name in ("pairs.npz", "network.json", "manifest.json"):
            shutil.copy2(staging / name, ROOT / "analysis" / name)
        shutil.copy2(html, ROOT / "household-network.html")
        args.deliver_html.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html, args.deliver_html)
        status("ready_to_publish", status="complete", completedUtc=datetime.now(timezone.utc).isoformat(),
               pairCount=manifest["pairCount"], validMiPairs=manifest["validMiPairs"],
               html=str(args.deliver_html), publication="Pending Git commit and push")
    except BaseException as failure:
        status("failed", status="failed", error=str(failure))
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
