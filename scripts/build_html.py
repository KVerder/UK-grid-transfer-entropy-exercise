"""Bundle the real network data and UI into a standalone, offline HTML file."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from group_layouts import grouping_layouts

ROOT = Path(__file__).resolve().parents[1]


def build(data_path: Path, destination: Path, rebuild_layouts: bool = False) -> None:
    data = json.loads(data_path.read_text(encoding="utf-8-sig"))
    if not data.get("nodes") or not isinstance(data.get("edges"), list):
        raise ValueError("A populated, computed network dataset is required")
    # Styling changes can reuse identical precomputed layouts from this output.
    previous = None
    if destination.exists() and not rebuild_layouts:
        match = re.search(r'<script id="network-data" type="application/json">(.*?)</script>', destination.read_text(encoding='utf-8-sig'), re.S)
        if match:
            previous = json.loads(match.group(1))
    if previous and previous.get('nodes') == data['nodes'] and previous.get('edges') == data['edges'] and previous.get('layouts'):
        data['layouts'] = previous['layouts']
    else:
        data['layouts'] = grouping_layouts(data)
    encoded = json.dumps(data, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    # A literal closing script tag must not terminate the embedded JSON element.
    encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (ROOT / "web/template.html").read_text(encoding="utf-8-sig")
    replacements = {
        "__CSS__": (ROOT / "web/styles.css").read_text(encoding="utf-8-sig"),
        "__APP_JS__": (ROOT / "web/app.js").read_text(encoding="utf-8-sig"),
        "__DATA_JSON__": encoded,
    }
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"Template must contain exactly one {marker}")
        template = template.replace(marker, value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(template, encoding="utf-8", newline="\n")
    print(f"Built {destination}: {destination.stat().st_size:,} bytes; "
          f"{len(data['nodes']):,} nodes, {len(data['edges']):,} candidate edges")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "analysis/network.json")
    parser.add_argument("--output", type=Path, default=ROOT / "household-network.html")
    parser.add_argument("--rebuild-layouts", action="store_true", help="Recompute community layouts even if the embedded dataset is unchanged")
    args = parser.parse_args()
    build(args.data, args.output, args.rebuild_layouts)
