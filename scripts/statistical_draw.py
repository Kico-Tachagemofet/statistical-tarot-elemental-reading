#!/usr/bin/env python3
"""
statistical_draw.py — 统计塔罗五位置抽取与统计（阶段 0）

牌阵：火位 / 水位 / 风位 / 土位（各花色 10 数字牌 + 4 宫廷牌 = 14 张）+ 大阿卡那位（22 张）。
每次先在五堆里等概率选一堆，再从该堆等概率抽一张，正逆各 50%。固定次数，不补抽不重抽。
位置只表示元素归属，无抽取顺序含义。

输出（写入 --out 目录）：
  protocol.json      抽取前写入的口径
  raw.ndjson         逐次原始记录（逐行落盘）
  receipt.json       完成回执（含 raw.ndjson sha256）
  statistics.json    统计 + 突出牌的 Book T / 属性展开 / 自定牌意 / 元素标
  positions/*.md     五张数据卡（给阶段 1 的子 agent）
  page.html          给人看的页面

数据来源：skill 自带的 data/tarot/{atu,pips,courts}.json（Book T 属性与牌义摘要；可用 --data-dir 另指）；
          本目录 card_names_zh.json（中文牌名）；
          symbol-anchor-check/phase3_unfold.py（属性展开；与本 skill 装在同一 skills 目录时自动使用，
          可用 --phase3 另指；没有或加载失败时跳过，不影响抽取与统计）；
          --meanings-dir（自定大牌牌意 md，可选）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from random import SystemRandom

HERE = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = HERE.parent / "data" / "tarot"
DEFAULT_PHASE3 = HERE.parent.parent / "symbol-anchor-check" / "phase3_unfold.py"

PILES = [
    ("fire", "火位", "Fire", "wands"),
    ("water", "水位", "Water", "cups"),
    ("air", "风位", "Air", "swords"),
    ("earth", "土位", "Earth", "disks"),
    ("major", "大阿卡那位", None, None),
]
ZH_ELEMENT = {"风": "Air", "水": "Water", "火": "Fire", "土": "Earth"}
DATA_FILES = ("atu.json", "pips.json", "courts.json")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


# ── data ────────────────────────────────────────────────────
def load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_deck(data_dir: Path) -> dict[str, list[dict]]:
    zh = load_json(HERE / "card_names_zh.json")
    atu, pips, courts = (load_json(data_dir / name) for name in DATA_FILES)
    piles: dict[str, list[dict]] = {k: [] for k, *_ in PILES}
    for e in pips + courts:
        key = {"wands": "fire", "cups": "water", "swords": "air", "disks": "earth"}[e["suit"]]
        piles[key].append({"id": e["id"], "zh": zh.get(e["id"], e["id"]), "class": e["card_class"], "book_t": e["book_t"]})
    for e in atu:
        piles["major"].append({"id": e["id"], "zh": zh.get(e["id"], e["id"]), "class": e["card_class"],
                               "name": e["name_traditional"], "number": e["number_arabic"], "book_t": e["book_t"]})
    for k, *_ in PILES:
        piles[k].sort(key=lambda c: c["id"])
    sizes = {k: len(v) for k, v in piles.items()}
    assert sizes == {"fire": 14, "water": 14, "air": 14, "earth": 14, "major": 22}, sizes
    return piles


def load_meanings(kdir: Path | None) -> dict[int, dict]:
    """按大牌编号取最高版本的自定牌意：返回 {number: {version, element_zh, element, text}}。

    文件名形如 `NN-名称-vX.Y.md`（NN 为大牌编号），正文含一行 `| 元素 | 水（…） |` 时取其元素。
    """
    out: dict[int, dict] = {}
    if not kdir or not kdir.is_dir():
        return out
    pat = re.compile(r"^(\d{2})-.*-v(\d+)\.(\d+)\.md$")
    for p in sorted(kdir.glob("*.md")):
        m = pat.match(p.name)
        if not m:
            continue
        num, ver = int(m.group(1)), (int(m.group(2)), int(m.group(3)))
        if num in out and out[num]["_ver"] >= ver:
            continue
        text = p.read_text(encoding="utf-8")
        em = re.search(r"^\|\s*元素\s*\|\s*([^|]+?)\s*\|", text, re.M)
        ezh = em.group(1).strip() if em else None
        element = None
        if ezh:
            for zh_ch, en in ZH_ELEMENT.items():
                if ezh.startswith(zh_ch):
                    element = en
                    break
        out[num] = {"_ver": ver, "version": f"v{ver[0]}.{ver[1]}", "element_zh": ezh, "element": element, "text": text}
    return out


def load_phase3(path: Path | None):
    """加载属性展开模块。返回 (模块或 None, 说明或 None)；任何失败都只跳过属性展开。"""
    if not path or not path.exists():
        return None, None
    try:
        spec = importlib.util.spec_from_file_location("phase3_unfold", path)
        if spec is None or spec.loader is None:
            return None, f"无法加载 {path.name}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for fn in ("unfold_pip", "unfold_major", "unfold_court"):
            if not hasattr(mod, fn):
                return None, f"{path.name} 缺少 {fn}"
        return mod, None
    except Exception as exc:  # 属性展开是可选层，加载失败不阻断抽取
        return None, f"{path.name} 加载失败：{exc!r}"


# ── statistics ─────────────────────────────────────────────
def binom_pmf(n: int, k: int, p: float) -> float:
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(p) + (n - k) * math.log(1 - p))


def binom_two_sided(n: int, k: int, p: float) -> tuple[float, float, float]:
    lower = sum(binom_pmf(n, i, p) for i in range(0, k + 1))
    upper = sum(binom_pmf(n, i, p) for i in range(k, n + 1))
    return lower, upper, min(1.0, 2 * min(lower, upper))


def band(z: float) -> str:
    a = abs(z)
    if a < 1:
        return "接近基线"
    if a < 2:
        return "普通偏离"
    return "极端候选"


def holm(pvals: list[float], alpha: float = 0.05) -> list[tuple[float, bool]]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [1.0] * m
    flags = [False] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = min(1.0, (m - rank) * pvals[i])
        running = max(running, val)
        adj[i] = running
    for i in range(m):
        flags[i] = adj[i] <= alpha
    return list(zip(adj, flags))


# ── main ────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--question", required=True, help="原问，原句保留")
    ap.add_argument("--out", required=True, help="输出目录（已有 raw.ndjson 则拒绝执行）")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Book T 数据目录（含 atu/pips/courts.json），默认用 skill 自带的")
    ap.add_argument("--phase3", default=str(DEFAULT_PHASE3), help="symbol-anchor-check 的 phase3_unfold.py；默认找同一 skills 目录下的")
    ap.add_argument("--meanings-dir", default=None, help="自定大牌牌意目录（可选）")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    data_dir = Path(args.data_dir)
    missing = [name for name in DATA_FILES if not (data_dir / name).is_file()]
    if missing:
        print(f"拒绝：数据目录缺少 {', '.join(missing)}。用 --data-dir 指向含 atu/pips/courts.json 的目录。", file=sys.stderr)
        return 2

    out = Path(args.out)
    raw_path = out / "raw.ndjson"
    if raw_path.exists():
        print(f"拒绝：{raw_path} 已存在。抽取不可重放，不重抽；换目录。", file=sys.stderr)
        return 2

    # 抽取之前把所有材料备齐：任何一项出错都不会消耗随机抽取
    piles = build_deck(data_dir)
    meanings = load_meanings(Path(args.meanings_dir)) if args.meanings_dir else {}
    p3, p3_note = load_phase3(Path(args.phase3) if args.phase3 else None)
    if p3_note:
        print(f"提示：{p3_note}；本次不做属性展开。", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)
    n = args.draws
    n_piles = len(PILES)

    protocol = {
        "version": 3,
        "question": args.question,
        "prepared_at": now_iso(),
        "draws": n,
        "spread": "五位置：火位／水位／风位／土位各 14 张（10 数字牌 + 4 宫廷牌），大阿卡那位 22 张",
        "position_semantics": "位置只表示元素归属；没有抽取顺序、时间、主体或因果含义",
        "sampling": "每次先在五堆中等概率选一堆，再从该堆中等概率抽一张；每次独立，恢复整副",
        "random_source": "Python random.SystemRandom, operating-system entropy, no replay seed",
        "orientation": "每张正逆独立各 50%；主统计按牌名合并，正逆完整保留",
        "stopping": f"固定 {n} 次；不因任何结果补抽、重抽或删改；开始后禁止再次执行抽取",
        "pile_family": f"5 堆各 Binomial({n}, 1/5)，预期 {n/5:.2f}，sd {math.sqrt(n*0.2*0.8):.3f}",
        "card_family": f"小牌堆每张 Binomial({n}, 1/70) 预期 {n/70:.3f}；大牌堆每张 Binomial({n}, 1/110) 预期 {n/110:.3f}",
        "display_bands": {"接近基线": "|z|<1", "普通偏离": "1<=|z|<2", "极端候选": "|z|>=2"},
        "tail_definition": "包含观察值的精确上下尾；双尾=min(1,2*min(P(X<=k),P(X>=k)))",
        "multiplicity": "Holm 校正按堆各做，alpha=0.05；只标注，不删除或压低任何频数",
        "major_element_tagging": "Book T 元素归属直接标；行星牌按自定牌意标（若提供）；都没有则标未指定，留在大牌线",
        "sources": {
            "book_t": "skill 自带 data/tarot" if data_dir.resolve() == DEFAULT_DATA_DIR.resolve() else "--data-dir 指定的目录",
            "phase3_unfold": "symbol-anchor-check/phase3_unfold.py" if p3 else None,
            "major_meanings": f"--meanings-dir 指定的目录（{len(meanings)} 张）" if meanings else None,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    (out / "protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")

    rng = SystemRandom()
    pile_keys = [k for k, *_ in PILES]
    counts = {k: [0] * len(piles[k]) for k in pile_keys}
    ups = {k: [0] * len(piles[k]) for k in pile_keys}
    with raw_path.open("w", encoding="utf-8") as f:
        for i in range(1, n + 1):
            pk = pile_keys[rng.randrange(n_piles)]
            ci = rng.randrange(len(piles[pk]))
            rev = rng.random() < 0.5
            counts[pk][ci] += 1
            if not rev:
                ups[pk][ci] += 1
            card = piles[pk][ci]
            f.write(json.dumps({"draw": i, "pile": pk, "card_id": card["id"], "zh": card["zh"],
                                "reversed": rev}, ensure_ascii=False) + "\n")
            f.flush()
    raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    receipt = {"completed_at": now_iso(), "draws": n, "raw_sha256": raw_sha}
    (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    stats: dict = {"question": args.question, "protocol": protocol, "receipt": receipt, "piles": []}
    pile_sd = math.sqrt(n * 0.2 * 0.8)
    for pk, label, elem, suit in PILES:
        cards = piles[pk]
        size = len(cards)
        total = sum(counts[pk])
        p_card = 1 / (n_piles * size)
        exp_card = n * p_card
        sd_card = math.sqrt(n * p_card * (1 - p_card))
        rows = []
        for ci, card in enumerate(cards):
            k = counts[pk][ci]
            lo, hi, two = binom_two_sided(n, k, p_card)
            z = (k - exp_card) / sd_card
            rows.append({"card_id": card["id"], "zh": card["zh"], "class": card["class"], "count": k,
                         "upright": ups[pk][ci], "reversed": k - ups[pk][ci], "expected": exp_card,
                         "z": z, "band": band(z), "p_lower": lo, "p_upper": hi, "p_two": two})
        for row, (adj, flag) in zip(rows, holm([r["p_two"] for r in rows])):
            row["p_holm"] = adj
            row["holm_flag"] = flag
        rows.sort(key=lambda r: -r["z"])
        highlights = []
        for row in rows:
            if row["band"] == "接近基线":
                continue
            card = next(c for c in cards if c["id"] == row["card_id"])
            bt = card["book_t"]
            h = {**row, "book_t": bt}
            if p3:
                try:
                    fn = {"minor_pip": p3.unfold_pip, "major_arcana": p3.unfold_major, "court": p3.unfold_court}[card["class"]]
                    h["property_unfolding"] = fn(bt, label, False)
                except Exception as exc:  # 属性展开失败不阻断统计
                    h["property_unfolding_error"] = repr(exc)
            if pk == "major":
                bt_elem = bt.get("element")
                mc = meanings.get(card["number"])
                tag, src = None, None
                if bt_elem:
                    tag, src = bt_elem, "Book T"
                elif mc and mc.get("element"):
                    tag, src = mc["element"], f"自定牌意 {mc['version']}"
                h["element_tag"] = {"element": tag, "source": src, "book_t_element": bt_elem,
                                    "custom_element": (mc or {}).get("element_zh"),
                                    "attribution": bt.get("attribution")}
                if mc:
                    h["major_meaning"] = {"version": mc["version"], "text": mc["text"]}
            highlights.append(h)
        stats["piles"].append({
            "key": pk, "label": label, "element": elem, "suit": suit, "size": size,
            "count": total, "expected": n / n_piles, "sd": pile_sd, "z": (total - n / n_piles) / pile_sd,
            "card_expected": exp_card, "card_sd": sd_card, "cards": rows, "highlights": highlights,
        })
    (out / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")

    write_position_cards(out, stats)
    write_page(out, stats)
    print(f"完成：{n} 次。输出目录 {out}")
    for pl in stats["piles"]:
        hl = ", ".join(f"{h['zh']}{h['count']}({'+' if h['z']>0 else '-'})" for h in pl["highlights"])
        print(f"  {pl['label']}: {pl['count']} 次 (z={pl['z']:+.2f})  突出: {hl or '无'}")
    return 0


# ── position data cards (for sub-agents) ───────────────────
def fmt_attrs(bt: dict, cls: str) -> str:
    bits = []
    if cls == "minor_pip":
        bits.append(f"{bt.get('sephira')} in {bt.get('world')}（{', '.join(bt.get('sephira_qualities') or [])}）")
        d = bt.get("decan")
        if d:
            bits.append(f"旬星 {d['planet']} in {d['sign']} {d.get('span_degrees','')}；{bt.get('decan_dignity')}")
    elif cls == "court":
        bits.append(bt.get("element_compound", ""))
        zs = bt.get("zodiacal_span")
        if zs:
            bits.append(f"黄道跨度 {zs['start']}–{zs['end']}")
    else:
        a = bt.get("attribution") or {}
        bits.append(f"归属 {a.get('type')}: {a.get('value')}；路径 {bt.get('path_on_tree')} {'–'.join(bt.get('path_between') or [])}")
        if bt.get("ruling_planet_of_sign"):
            bits.append(f"星座主星 {bt['ruling_planet_of_sign']}，耀升 {bt.get('exaltation_in_sign')}")
    bits.append("性质 " + "+".join(bt.get("primary_qualities") or []))
    return "；".join(b for b in bits if b)


def write_position_cards(out: Path, stats: dict) -> None:
    pdir = out / "positions"
    pdir.mkdir(exist_ok=True)
    q = stats["question"]
    for pl in stats["piles"]:
        L = [f"# {pl['label']} 数据卡", "", f"原问：{q}", "",
             f"堆：{pl['label']}（{pl['element'] or '大阿卡那'}，{pl['size']} 张）。本堆被抽到 {pl['count']} 次，预期 {pl['expected']:.1f}，z={pl['z']:+.2f}。",
             f"本堆每张牌预期 {pl['card_expected']:.2f} 次，sd {pl['card_sd']:.2f}。分段：|z|<1 接近基线；1–2 普通偏离；≥2 极端候选。", "",
             "## 全部牌（按 z 降序）", "", "| 牌 | 次数 | 正／逆 | z | 分段 | 校正 p |", "|---|---:|---|---:|---|---:|"]
        for r in pl["cards"]:
            L.append(f"| {r['zh']} | {r['count']} | {r['upright']}／{r['reversed']} | {r['z']:+.2f} | {r['band']} | {r['p_holm']:.3f} |")
        L += ["", "## 突出牌（普通偏离与极端候选）", ""]
        if not pl["highlights"]:
            L.append("无。本堆所有牌都接近基线；分读报告写明「无突出」，只做位置概况。")
        for h in pl["highlights"]:
            bt = h["book_t"]
            direction = "偏多" if h["z"] > 0 else "偏少"
            L += [f"### {h['zh']}（{h['count']} 次，{direction}，{h['band']}，正／逆 {h['upright']}／{h['reversed']}）", "",
                  f"- Book T 牌名：{bt.get('book_t_title')}",
                  f"- Book T 牌义：{bt.get('book_t_summary')}",
                  f"- 属性：{fmt_attrs(bt, h['class'])}"]
            if h.get("property_unfolding"):
                pu = h["property_unfolding"]
                L.append("- 属性展开：" + " ".join(v for k, v in pu.items() if k != "position_layer" and isinstance(v, str)))
            if "element_tag" in h:
                t = h["element_tag"]
                L.append(f"- 元素标：{t['element'] or '未指定'}（来源 {t['source'] or '无'}；Book T 元素 {t['book_t_element']}；自定牌意元素 {t['custom_element'] or '无'}）")
            if h.get("major_meaning"):
                L += ["", f"自定牌意（{h['major_meaning']['version']}）：", "", h["major_meaning"]["text"].strip()]
            L.append("")
        (pdir / f"{pl['key']}.md").write_text("\n".join(L), encoding="utf-8")


# ── page ────────────────────────────────────────────────────
def write_page(out: Path, stats: dict) -> None:
    """Render the saved report without loading enrichment or drawing cards."""
    renderer_path = HERE / "report_renderer.py"
    spec = importlib.util.spec_from_file_location("statistical_tarot_report_renderer", renderer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load report renderer: {renderer_path}")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.write_page(out, stats)


if __name__ == "__main__":
    sys.exit(main())
