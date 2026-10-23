# 统计塔罗四元素理气 · statistical-tarot-elemental-reading

当前方法版本：**v3.2**。更新内容见 [版本记录](CHANGELOG.md)，可下载的版本快照见 [GitHub Releases](https://github.com/Kico-Tachagemofet/statistical-tarot-elemental-reading/releases)。

面向 AI Agent 的统计塔罗解读 Skill。一副塔罗分成火、水、风、土四个花色堆和一个大阿卡那堆，用操作系统随机源抽一千次；再按固定流程，从频数的偏离读到四元素各自的状态与相互作用，最后回到原问。脚本只负责抽取、统计和数据卡，解读由 Agent 按 `SKILL.md` 完成。

- 只要抽取与统计页面、不需要解读：用已公开的 [statistical-tarot](https://github.com/Kico-Tachagemofet/statistical-tarot)，抽样口径相同。
- 数据卡里的属性展开（源质、旬星、路径的说明文字）来自 [symbol-anchor-check](https://github.com/Kico-Tachagemofet/symbol-anchor-check) 的 `phase3_unfold.py`。两个 Skill 装在同一个 skills 目录时自动使用；没有它也能完整运行，只是少了这一层说明。
- 需要玄学能力与体系报告：使用随附的 [mystic-talent-report v0.3.1 扩展](addons/mystic-talent-report/README.md)。先读能力与长处，再把画像放进所选的 3–5 个体系做任务压力测试；沿用原抽样。

## 需要什么

- Python 3.10 或更新版本，只用标准库。
- 一个能读写文件、能派子 agent 的 AI Agent。流程按 Claude Code 写：阶段 1 一次派五个子 agent 并行分读五个位置。
- 成本偏高：完整跑一盘，五个子 agent 合计约 70 万 token，每个 8 到 14 分钟（2026 年 10 月实测一盘），主 agent 另计。

## 安装

把整个仓库放进 Agent 的 skills 目录，目录名保持 `statistical-tarot-elemental-reading`，例如：

```sh
git clone https://github.com/Kico-Tachagemofet/statistical-tarot-elemental-reading ~/.claude/skills/statistical-tarot-elemental-reading
```

可选：把 symbol-anchor-check 也装进同一个 skills 目录，数据卡里就会多出属性展开。

## 使用

对 Agent 说要做一盘统计塔罗，并给出问题原句。Agent 按 `SKILL.md` 依次完成：

1. 定问：题型、留白、语境前提（冷读）、当事人视角，写在抽取之前；
2. 脚本抽取一千次并统计；
3. 框架假设；
4. 五个子 agent 分读五个位置的牌意；
5. 主 agent 判断四元素的状态与相互作用；
6. 语境核对；
7. 第二次 Via Negativa；
8. 回原问：牌意、四元素、answer 三部分。

脚本也可以单独运行：

```sh
python -I scripts/statistical_draw.py --question "本次的问题原句" --out runs/2026-10-17-示例/data
```

| 文件 | 用途 |
|---|---|
| `protocol.json` | 抽取前写下的问题与口径 |
| `raw.ndjson` | 每行一笔的原始抽取记录 |
| `receipt.json` | 完成时间、次数与原始记录的 SHA-256 |
| `statistics.json` | 五堆与每张牌的统计，突出牌附 Book T 牌义、属性与元素标 |
| `positions/*.md` | 五张数据卡，交给五个子 agent |
| `page.html` | 可离线打开的统计页面 |

`--out` 目录里已有 `raw.ndjson` 时脚本拒绝执行：抽取不可重放，不重抽、不补抽。只重建页面用 `python -I scripts/render_page.py <统计文件路径>`，这条命令不抽牌。

其他参数：`--data-dir` 另指 Book T 数据目录；`--phase3` 另指 `phase3_unfold.py`；`--meanings-dir` 指向自定大牌牌意。

## 自定大牌牌意（可选）

`--meanings-dir` 指向一个目录，里面的文件名形如 `NN-名称-vX.Y.md`（`NN` 为大牌编号，同一编号取版本最高的一份）。正文里有一行 `| 元素 | 水（…） |` 时，行星大牌（魔术师、女祭司、皇后、命运之轮、塔、太阳）按它标元素；全文进入数据卡，当作牌义交给子 agent。

没有自定牌意时，这六张大牌的元素标是"未指定"，SOP 在"元素结论增强"一步单独处理它们。

## 方法卡与来源

`references/` 里有七张方法卡（性质、关系、火、水、风、土、组合）和子 agent 的分读任务书。方法卡的每条规则在卡末来源表里标明出处：

- `【验证✓】`：可回溯到原典，包括 Aristotle、Agrippa、斯多葛文献、《法学阶梯》、Fludd、Bruno、Böhme、Paracelsus、Arroyo 与 Book T 等；
- `【Kico 校】`：维护者校准过的工作原则。

`data/tarot/` 是 78 张牌的 Book T 属性与牌义摘要，由本项目整理和转述，不是 Book T 原文；与 symbol-anchor-check 随附的是同一份。方法卡里的示例牌只用来说明规则要点，不来自任何真实占卜。

## 局限与立场

- 统计数字只描述结果与抽样基线的距离，不能证明占卜结论正确。
- 单牌的预期按全部抽取次数与无条件概率计算（与 statistical-tarot 相同），堆的总量偏离会带进同堆每张牌的 z：某堆总量偏少时，堆里的牌整体偏低。读"堆内哪几种形态被强调"时要留意这一点。
- 下面几处 SOP 还没有写定，执行时由主 agent 判断，并在案例里写明理由：
  - 五堆分成几组并列时，相对读怎么写（SOP 只写了最高与最低的堆）；
  - 风卡"风偏多可在总量层直接断想法多且相互矛盾"，在风与别的堆并列偏多时要不要启用；
  - Book T 牌义里"按尊贵"出现的那一面，在没有相邻牌的统计盘里怎么判；
  - 大阿卡那堆的总量偏多或偏少怎么读。
- 本 Skill 是一套解读方法与工作流程，不是 Book T 或任何传统的权威版本。

## 许可证

- `scripts/` 与 `data/tarot/`：MIT，见 `LICENSE`。
- `SKILL.md` 与 `references/`：CC BY-NC-SA 4.0，见 `LICENSE-CONTENT`。
- `addons/mystic-talent-report/` 的原创文字与结构：CC BY-NC-SA 4.0，见扩展内的 `LICENSE-CONTENT`。
- 方法卡引用的原典与译本不适用本仓库的许可证。

Copyright (c) 2026 Kico-Tachagemofet


## 可选 Kico 大阿卡纳牌意 DLC

支持 [Kico 大阿卡纳牌意 v1.0.0](https://github.com/Kico-Tachagemofet/kico-tarot-meanings)。
安装本 skill 不自动启用或下载正文。使用 `--meanings-pack <包目录>` 开启，
`--no-meanings` 显式关闭；错误会明确报告。
正文按本次需要加载，并记录包版本、单牌版本、校验值和文本 token 增量。

解读须执行 [牌意接入说明](references/meaning-pack.md)。
网站接入与已有结果切换见
[HANDOFF](https://github.com/Kico-Tachagemofet/kico-tarot-meanings/blob/main/HANDOFF.md)。
正文独立采用 CC BY-NC-SA 4.0；内置 `card_meanings.py` 读取器采用 MIT，
版权声明见 `LICENSE-MEANING-READER`，不会改变本仓库其他内容的许可。
