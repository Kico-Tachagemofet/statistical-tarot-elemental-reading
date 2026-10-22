# 玄学能力与体系压力测试

`mystic-talent-report` v0.1.0 是统计塔罗的专题报告扩展：先从完整牌义、四元素与占星语言读出能力和长处，再将同一份画像放进具体体系的任务中，说明哪一环接得住、哪一环吃紧、什么条件帮助发挥。

它沿用原统计塔罗的抽样和分析，不另抽一盘，也不增加天赋总分。分析结构为七模块、接收矩阵、独立商业轴和六类任务链；成品是散文报告，不是评分表。

## 安装与调用

先安装本仓库的 `statistical-tarot-elemental-reading`。然后任选一种方式：

1. **保留在仓库内使用**：让 Agent 读取 `addons/mystic-talent-report/SKILL.md`。扩展会核对上两级目录中的原统计 skill。
2. **作为可发现的独立 skill**：将本目录完整复制到客户端实际使用的 skills 目录，与 `statistical-tarot-elemental-reading` 并列。它会先查找该兄弟目录；也接受用户明确提供原 skill 的路径。

安装后的目录形状可以是：

```text
skills/
├── statistical-tarot-elemental-reading/
│   ├── SKILL.md
│   ├── scripts/
│   └── data/tarot/
└── mystic-talent-report/
    ├── SKILL.md
    ├── references/
    └── agents/
```

例如对 Agent 说：

> 用 $mystic-talent-report 读取这个已有统计塔罗案例，先写能力与长处，再自动选择四个体系做压力测试。把 REPORT.md 和 AUDIT.md 保存到新目录。

也可以先形成画像，再选 3–5 个关心的体系。没有选择时，默认取画像最有具体依据的 3–5 个；选择不会反过来改变能力判断。

## 输入与输出

输入为原统计 skill 的 `protocol.json`、`statistics.json`、五堆数据卡及已有分析；已有分读可以复用并校准。尚无抽样且用户明确要求新测时，由原 skill 完成一次抽取。

- `REPORT.md`：一句定调，通常 4–6 节散文；先能力，后领域；技术依据置于节末。
- `AUDIT.md`：统计与牌证、占星解释、固定画像、接收与商业细项、领域压力测试和未决分叉。

判断顺序是 **牌义 → 冷热干湿 → 行星／星座 → 全场关系 → 能力模块**。喜乐宫只在领域层解释工作场景与官能的亲和，不回填实际本命落宫。

## 随附内容

- [牌义与占星校准](references/card-astrology.md)：七组关键牌义对照、七曜、十二星座及宫廷牌。
- [任务压力测试](references/domain-pressure.md)：六类任务链与十四体系索引。
- [十四张领域卡](references/domains/)：可独立读取的传统与支线资料。
- [宫位与喜乐亲和](references/field-affinity.md)：十四体系的主次场景映射。
- [报告写法](references/report-writing.md)：能力判断如何形成有主线的散文。
- [合成换牌样例](examples/swap-cases.md)：相同背景下，替换关键牌怎样改变结论。这里没有真实个人案例。

## 可选大牌正文

支持 [Kico 大阿卡纳牌意包](https://github.com/Kico-Tachagemofet/kico-tarot-meanings)，按原统计 skill 的牌义包开关和本次数据记录使用。未启用时继续使用本次 Book T 材料；不自动套用参考卡中标明来源于作者正文的分支。

## 许可证

本扩展的维护者原创文字与结构采用 [CC BY-NC-SA 4.0](LICENSE-CONTENT)，署名 Kico-Tachagemofet。第三方原典及译本保留各自权利；本包提供来源与简要转述，不包含书籍 PDF、私人案例或其他个人材料。
