# 可选大阿卡纳牌意 DLC

公开安装默认关闭；本地默认配置可开启。
`scripts/statistical_draw.py --meanings-pack <目录>` 启用，
`--no-meanings` 关闭。有效性在抽取前检查；失败不消耗随机抽取。
旧式 `--meanings-dir`（私有安装为 `--kicocraft-dir`）与 DLC 开关互斥，
显式旧目录优先于本地默认包。新包始终用固定 `card_id` 匹配。
公共旧式目录默认 Book T 编号；韦特编号需显式 `--meanings-numbering rws`。

## 阶段 1 的实际输入

`statistics.json.meaning_pack` 记录本次解释使用的包；大牌突出项的
`major_meaning.text` 是完整正文，已写入 `positions/major.md`。
偏多与偏少的突出牌都加载；基线牌不因包里有正文而被提升为重点。
无突出大牌时保留 enabled 状态与空的 loaded_card_ids，说明没有需要加载的牌。

主 agent 将该数据卡完整交给大牌分读者。分读者先读完每张正文，
再结合 Book T 摘要理解牌义全幅，保留条件分支。每张牌的分析附一行
`meaning_use: card_id / 单牌版本 / 正文精确短引 / 本题形态及限制`。
不能只读标签，不能用“已加载”取代正文依据，也不能把正文全部粘贴后
继续按模型惯常牌意解读。未能落实到本题的部分明确保留。

主 agent 的阶段 1 验收检查：每张已加载牌都有正文短引，且引文确实来自
该牌；牌义动作与限制实际进入形态分列。阶段 2 的元素判断与阶段 3 的
候选检验必须承接这些形态，不能在合并时丢掉正文条件。
Book T 与作者解释保留来源，不作为两次独立证据累加置信。

## 数值边界与已保存结果

包不会改变频数、正逆、z、p、显著度分段或突出牌选择。
Book T 有元素归属时沿用；没有时可使用作者标签补足，保留来源。
改变 DLC 可能改变解释性元素标与文字解释，不能宣称所有输出逐字相同。
未指定元素继续留在大牌线。

已有结果切换开关时，只运行 `scripts/enrich_meanings.py`：
读取旧 `statistics.json`，写入新报告目录。保留原抽取协议和回执，
新顶层 `meaning_pack` 是当前解释选择；原 `protocol.meaning_pack_at_draw`
仅表示抽取时的选择。旧报告、原始抽取不覆盖，不重抽。
完整接口与 token 说明见
[HANDOFF](https://github.com/Kico-Tachagemofet/kico-tarot-meanings/blob/main/HANDOFF.md)。
