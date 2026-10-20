"""Shared meaning-pack reader v1.0.0. MIT licensed. Standard library only.

Deterministic enrichment of existing cards; this module never draws symbols.
Vendored unchanged by both consumers. Content has its own manifest license.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

READER_VERSION = "1.0.0"
MAJOR_IDS = (
    "atu_00_fool", "atu_01_magician", "atu_02_high_priestess", "atu_03_empress",
    "atu_04_emperor", "atu_05_hierophant", "atu_06_lovers", "atu_07_chariot",
    "atu_08_justice", "atu_09_hermit", "atu_10_wheel_of_fate", "atu_11_fortitude",
    "atu_12_hanged_man", "atu_13_death", "atu_14_temperance", "atu_15_devil",
    "atu_16_blasted_tower", "atu_17_star", "atu_18_moon", "atu_19_sun",
    "atu_20_judgment", "atu_21_universe",
)


class MeaningPackError(ValueError):
    """An explicitly enabled pack cannot be loaded; do not silently disable it."""


def resolve_pack(explicit=None, *, disabled=False, config_dir=None):
    """Explicit off > explicit path > local installation config > off.

    A local meanings.local.json is installation-only, never shipped publicly.
    Relative configured paths resolve against the config file's directory.
    """
    if disabled:
        if explicit:
            raise MeaningPackError("Choose --meanings-pack OR --no-meanings.")
        return None
    if explicit:
        return Path(explicit).expanduser()
    if config_dir is None:
        return None
    config = Path(config_dir) / "meanings.local.json"
    if not config.exists():
        return None
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            raise ValueError("enabled must be a boolean")
        if not data["enabled"]:
            return None
        value = data.get("pack")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("enabled pack requires a path")
        path = Path(value).expanduser()
        return path if path.is_absolute() else config.parent / path
    except (OSError, ValueError, TypeError) as exc:
        raise MeaningPackError(f"Invalid local meaning-pack configuration: {exc}") from exc


class MeaningPack:
    """Validate all 22 assets before use; select only relevant text for prompts."""

    def __init__(self, directory):
        try:
            root = Path(directory).expanduser().resolve()
            manifest_bytes = (root / "manifest.json").read_bytes()
            manifest = json.loads(manifest_bytes)
            if manifest.get("schema_version") != 1 or manifest.get("coverage") != "major_arcana":
                raise ValueError("Expected schema_version=1 and coverage=major_arcana")
            for key in ("pack_id", "version", "author", "license", "source_url"):
                if not isinstance(manifest.get(key), str) or not manifest[key]:
                    raise ValueError(f"Missing manifest field: {key}")
            cards = manifest["cards"]
            if set(cards) != set(MAJOR_IDS):
                raise ValueError("Pack must contain exactly the 22 stable Book T major IDs")
            self.cards = {}
            for card_id, entry in cards.items():
                if entry["card_id"] != card_id:
                    raise ValueError(f"Identity mismatch: {card_id}")
                path = (root / entry["file"]).resolve()
                if not path.is_relative_to(root):
                    raise ValueError(f"Card file escapes pack root: {card_id}")
                data = path.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest != entry["sha256"]:
                    raise ValueError(f"Card checksum mismatch: {card_id}")
                text = data.decode("utf-8")
                if not text.strip() or not entry.get("version"):
                    raise ValueError(f"Empty card text or version: {card_id}")
                if entry.get("element") not in (None, "Air", "Water", "Fire", "Earth", "Aether"):
                    raise ValueError(f"Invalid author element: {card_id}")
                tokens = entry.get("tokens", {})
                if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in tokens.values()):
                    raise ValueError(f"Invalid token estimate: {card_id}")
                self.cards[card_id] = {
                    "card_id": card_id, "title": entry["title"], "version": entry["version"],
                    "sha256": digest, "element": entry.get("element"),
                    "element_zh": entry.get("element_zh"), "tokens": tokens, "text": text,
                }
            self.metadata = {key: manifest[key] for key in (
                "pack_id", "version", "author", "license", "source_url")}
            self.metadata["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise MeaningPackError(f"Enabled meaning pack could not be validated: {exc}") from exc

    def select(self, card_ids):
        ids = list(dict.fromkeys(card_ids))
        unknown = [card_id for card_id in ids if card_id not in self.cards]
        if unknown:
            raise MeaningPackError(f"Requested cards are not covered: {unknown}")
        selected = {card_id: deepcopy(self.cards[card_id]) for card_id in ids}
        encodings = set.intersection(*(set(v["tokens"]) for v in selected.values())) if selected else set()
        receipt = {
            "enabled": True, **self.metadata, "reader_version": READER_VERSION,
            "loaded_card_ids": ids,
            "card_versions": {k: v["version"] for k, v in selected.items()},
            "card_sha256": {k: v["sha256"] for k, v in selected.items()},
            "text_tokens": {n: sum(v["tokens"][n] for v in selected.values()) for n in sorted(encodings)},
            "token_scope": "Selected card Markdown only; excludes wrappers, other input and output. Not Claude counts.",
        }
        return {"receipt": receipt, "cards": selected}


def disabled_receipt():
    return {"enabled": False, "reader_version": READER_VERSION, "loaded_card_ids": [], "text_tokens": {}}


def enrich_anchor(result, pack):
    """Return a copy with deduplicated texts and per-position references."""
    output = deepcopy(result)
    for card in output["per_card"]:
        card.pop("author_meaning_ref", None)
    ids = [card["card_id"] for card in output["per_card"] if card["card_class"] == "major_arcana"]
    selected = pack.select(ids) if pack else {"receipt": disabled_receipt(), "cards": {}}
    output["meaning_pack"] = selected["receipt"]
    output["author_meanings"] = selected["cards"]
    if pack:
        for card in output["per_card"]:
            if card["card_class"] == "major_arcana":
                card["author_meaning_ref"] = card["card_id"]
    return output


def enrich_statistics(stats, pack):
    """Replace only meaning enrichment and interpretive tags, never observations.

    Call on an existing statistics.json to switch packs without random draws.
    The original protocol and receipt remain as recorded at draw time.
    """
    output = deepcopy(stats)
    highlights = [h for pl in output["piles"] if pl["key"] == "major" for h in pl["highlights"]]
    selected = pack.select([h["card_id"] for h in highlights]) if pack else {
        "receipt": disabled_receipt(), "cards": {}}
    for h in highlights:
        h.pop("kicocraft", None)
        h.pop("major_meaning", None)
        bt = h["book_t"]
        meaning = selected["cards"].get(h["card_id"])
        bt_element = bt.get("element")
        element = bt_element or (meaning or {}).get("element")
        source = "Book T" if bt_element else (
            f"{pack.metadata['pack_id']} {pack.metadata['version']}" if element and pack else None)
        h["element_tag"] = {
            "element": element, "source": source, "book_t_element": bt_element,
            "custom_element": (meaning or {}).get("element_zh"),
            "kicocraft_element": (meaning or {}).get("element_zh"),
            "attribution": bt.get("attribution"),
        }
        if meaning:
            h["major_meaning"] = meaning
    output["meaning_pack"] = selected["receipt"]
    return output
