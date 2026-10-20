"""DLC integration against deterministic synthetic observations, never live draws."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("draw_under_test", ROOT / "scripts/statistical_draw.py")
draw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draw)
PACK = os.environ.get("KICO_MEANINGS_PACK")


class SyntheticRandom:
    """Deliberately all Fool: verifies zero-count cards also receive meanings."""
    def randrange(self, stop):
        return 4 if stop == 5 else 0

    def random(self):
        return 0.75


@unittest.skipUnless(PACK, "Optional DLC not installed; set KICO_MEANINGS_PACK")
class StatisticalMeaningTests(unittest.TestCase):
    def run_fixture(self, directory, *flags):
        args = ["statistical_draw", "--question", "Synthetic test fixture", "--out", str(directory),
                "--draws", "110", "--phase3", "", *flags]
        with patch.object(sys, "argv", args), patch.object(draw, "SystemRandom", SyntheticRandom):
            self.assertEqual(draw.main(), 0)
        return json.loads((directory / "statistics.json").read_text(encoding="utf-8"))

    def test_sampling_and_statistics_identical_with_dlc(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            off = self.run_fixture(root / "off", "--no-meanings")
            on = self.run_fixture(root / "on", "--meanings-pack", PACK)
            self.assertEqual((root / "off/raw.ndjson").read_bytes(), (root / "on/raw.ndjson").read_bytes())
            for a, b in zip(off["piles"], on["piles"]):
                self.assertEqual(a["cards"], b["cards"])
                for key in ("count", "z", "expected", "sd", "size"):
                    self.assertEqual(a[key], b[key])
            self.assertEqual(len(on["meaning_pack"]["loaded_card_ids"]), 22)
            highlights = on["piles"][-1]["highlights"]
            self.assertTrue(any(h["count"] == 0 and "major_meaning" in h for h in highlights))
            for h in highlights:
                if h["book_t"].get("element"):
                    self.assertEqual(h["element_tag"]["element"], h["book_t"]["element"])
            card = (root / "on/positions/major.md").read_text(encoding="utf-8")
            self.assertIn("kico-major-arcana v1.0.0", card)
            self.assertIn("# 力量 VIII", card)
            self.assertIn("# 正义 XI", card)

    def test_saved_report_switch_never_changes_original_observations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "original"
            original = self.run_fixture(source, "--no-meanings")
            before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
            command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/enrich_meanings.py"),
                       "--statistics", str(source / "statistics.json"),
                       "--out", str(root / "enabled"), "--meanings-pack", PACK]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            enabled = json.loads((root / "enabled/statistics.json").read_text(encoding="utf-8"))
            self.assertEqual(enabled["protocol"], original["protocol"])
            self.assertEqual(enabled["receipt"], original["receipt"])
            self.assertFalse((root / "enabled/raw.ndjson").exists())
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()})
            disabled = draw._meanings.enrich_statistics(enabled, None)
            self.assertEqual(disabled["piles"], original["piles"])
            self.assertTrue(enabled["meaning_pack"]["enabled"])

    def test_missing_pack_fails_before_rng_or_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "must-not-exist"
            args = ["draw", "--question", "fixture", "--out", str(out),
                    "--meanings-pack", str(Path(PACK) / "missing")]
            with patch.object(sys, "argv", args), patch.object(draw, "SystemRandom") as rng:
                with self.assertRaises(SystemExit):
                    draw.main()
                rng.assert_not_called()
            self.assertFalse(out.exists())

    def test_selected_highlights_only_and_legacy_removed(self):
        deck = draw.build_deck(ROOT / "data/tarot")
        majors = {c["id"]: c for c in deck["major"]}
        ids = ["atu_11_fortitude", "atu_08_justice", "atu_21_universe"]
        stats = {"piles": [{"key": "major", "highlights": [
            {"card_id": k, "book_t": majors[k]["book_t"], "kicocraft": {"text": "old private text"}}
            for k in ids]}], "protocol": {"fixed": True}, "receipt": {"fixed": True}}
        before = deepcopy(stats)
        result = draw._meanings.enrich_statistics(stats, draw._meanings.MeaningPack(PACK))
        self.assertEqual(stats, before)
        self.assertEqual(result["meaning_pack"]["loaded_card_ids"], ids)
        self.assertTrue(all("kicocraft" not in h for h in result["piles"][0]["highlights"]))
        self.assertEqual(len(result["piles"][0]["highlights"]), 3)


if __name__ == "__main__":
    unittest.main()
