#!/usr/bin/env python3
"""Multi-seed synthetic evaluation (see core/detection/benchmark.py for scope and caveats).

    python scripts/evaluate_detection.py --seeds 1-12
    python scripts/evaluate_detection.py --seeds 1-12 --format json --out var/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.detection.benchmark import (HELDOUT_SEEDS, ablation_to_markdown, evaluate_seeds, graph_ablation,  # noqa: E402
                                      parse_seeds, to_markdown)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1-12", help="e.g. 1-12 or 1,5,9-11")
    ap.add_argument("--accounts", type=int, default=None)
    ap.add_argument("--normal", type=int, default=None, help="normal baseline transactions")
    ap.add_argument("--include-structuring", action="store_true", help="add the opt-in STRUCTURING scenario")
    ap.add_argument("--graph-ablation", action="store_true", help="paired OFF/ON comparison of graph-analytics model features")
    ap.add_argument("--heldout", action="store_true", help="use the pre-declared held-out seeds (101-150) instead of --seeds")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    seeds = HELDOUT_SEEDS if a.heldout else parse_seeds(a.seeds)
    kw = dict(num_accounts=a.accounts, num_normal=a.normal, include_structuring=a.include_structuring)
    if a.graph_ablation:
        s = graph_ablation(seeds, **kw)
        text = ablation_to_markdown(s) if a.format == "md" else json.dumps(s, indent=2)
    else:
        s = evaluate_seeds(seeds, **kw)
        text = to_markdown(s) if a.format == "md" else json.dumps(s, indent=2)
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
