#!/usr/bin/env python3
"""Attach/remove DLC on saved statistics. No random calls; source stays untouched."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--statistics", required=True, help="Existing statistics.json")
    parser.add_argument("--out", required=True, help="New output directory; must not already exist")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--meanings-pack", help="Enable a validated major-arcana DLC directory")
    choice.add_argument("--no-meanings", action="store_true", help="Remove authored meanings and their element tags")
    args = parser.parse_args()
    reader = load_module("saved_meaning_reader", HERE / "card_meanings.py")
    try:
        source = Path(args.statistics).read_bytes()
        stats = json.loads(source)
        path = reader.resolve_pack(args.meanings_pack, disabled=args.no_meanings, config_dir=HERE.parent)
        pack = reader.MeaningPack(path) if path else None
        result = reader.enrich_statistics(stats, pack)
        result["enrichment_source"] = {"statistics_sha256": hashlib.sha256(source).hexdigest(),
                                       "operation": "meaning-only; original protocol and draw receipt preserved"}
        out = Path(args.out)
        if out.exists():
            raise ValueError("Output directory exists; choose a new report directory, not a new draw")
        # Import rendering functions only; main() and SystemRandom are never called.
        draw = load_module("statistics_report_writer", HERE / "statistical_draw.py")
        out.mkdir(parents=True)
        (out / "statistics.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        draw.write_position_cards(out, result)
        draw.write_page(out, result)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot enrich saved report: {exc}", file=sys.stderr)
        return 2
    print(f"Saved meaning-only report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
