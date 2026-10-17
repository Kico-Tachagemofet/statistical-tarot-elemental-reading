#!/usr/bin/env python3
"""Rebuild page.html from saved statistics. This entry never draws cards."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load_renderer():
    """Load report_renderer.py by path so `python -I` (no script dir on sys.path) still works."""
    path = Path(__file__).resolve().parent / "report_renderer.py"
    spec = importlib.util.spec_from_file_location("statistical_tarot_report_renderer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load report renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_page = _load_renderer().write_page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("statistics", type=Path, help="Path to an existing statistics.json")
    parser.add_argument("--out", type=Path, help="Report directory; defaults to the input directory")
    args = parser.parse_args()
    stats = json.loads(args.statistics.read_text(encoding="utf-8-sig"))
    out = args.out if args.out is not None else args.statistics.parent
    out.mkdir(parents=True, exist_ok=True)
    write_page(out, stats)
    print(out.resolve() / "page.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
