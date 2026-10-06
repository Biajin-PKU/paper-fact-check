# Paper Fact Check

**投稿前，让论文和它自己的证据对一遍。**

[English](README.md) · [简体中文](README.zh-CN.md)

![license: MIT](https://img.shields.io/badge/license-MIT-blue) ![python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue) ![works with 80+ agents](https://img.shields.io/badge/agents-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Cursor%20%C2%B7%2080%2B-black)

Paper Fact Check 读你的论文（有代码和数据也一起读），找出论文自己和自己对不上的地方：摘要和表格里同一个数不一样、p 值和统计量算不回来、引用的文献不存在、结论比结果说得更满。每一条都引用原文、给出算式，并给一句可以直接替换的改法。

各个学科都能用，中英文论文都支持。PDF、Word、LaTeX/Overleaf 项目都可以直接丢进来。

---

## 一个真实例子

一篇 2026 年 arXiv 论文（ICRA 2026）的第 1 版，图 2 图注写道：

> "achieving 41.4% bandwidth reduction (800 vs 2800 bits)"

```
[重要 · 影响结论]  相对变化和它自己给的两个数对不上
位置    摘要；第 I 节；图 2 图注；第 VI、VII 节
证据    每轮 800 vs 2800 bits（图 2 图注；表 I）
算式    1 − 800 / 2800 = 71.4%，不是 41.4%
改法    "achieving 71.4% bandwidth reduction (800 vs 2800 bits)"
```

作者在第 2 版把所有出现的地方都改成了 71.4%。Paper Fact Check 在第 1 版上指出这个问题，在第 2 版上不再报告。

---

## 快速开始

**在编程智能体里用（Claude Code、Codex、Cursor、OpenCode、Gemini CLI 等 80 多种）**

```bash
npx skills add Biajin-PKU/paperfactcheck
```

然后在智能体里输入：

```
/paperfactcheck 论文.pdf
/paperfactcheck overleaf项目.zip --code ./代码目录
```

| 你在哪用 | 怎么装 |
|---|---|
| Claude Code 插件 | `/plugin marketplace add Biajin-PKU/paperfactcheck`，再 `/plugin install paperfactcheck@paperfactcheck` |
| Claude 网页版 | 从 Releases 下载 `paperfactcheck-skill.zip`，在 *设置 → Skills* 上传 |
| 下载后直接运行 | `git clone https://github.com/Biajin-PKU/paperfactcheck && python3 paperfactcheck/skills/paperfactcheck/run.py 论文.pdf`（无需安装任何依赖） |
| 命令行 | `uvx --from git+https://github.com/Biajin-PKU/paperfactcheck paperfactcheck 论文.pdf` |
| Claude 桌面版、Cursor 等支持 MCP 的应用 | `paperfactcheck mcp`（[配置方法](docs/mcp.md)） |
| GitHub / Overleaf 的 git 同步 | [GitHub Action](docs/action.md)：每次推送自动检查 |
| ChatGPT、Kimi、豆包等任意对话 | 复制 [`prompt.zh-CN.md`](prompt.zh-CN.md)，上传 PDF。无需安装；算术由模型自己做，查出的问题会少一些 |

---

## 查什么

**数字**
- 同一个量在摘要、正文、表格、图注里写得不一样
- "提高了 X%" 和它比较的两个数对不上
- 百分比和分子分母对不上；各部分加起来不等于总数

**统计**
- 用 t、F、χ²、r、z 和自由度重算 p 值，并指出结论会不会因此翻转
- 置信区间和 p 值互相矛盾；点估计落在自己的区间外
- 用文中统计量重算效应量
- 整数数据不可能得出的平均值和标准差（GRIM、GRIMMER）
- 写"更好""显著"，但它自己的区间包含"无效应"
- 结果规整得不像测量出来的

**参考文献**
- 每条文献是否存在，作者、年份、期刊、DOI 是否正确
- 是否已被撤稿或发布了关注声明
- 被引论文是否真的说了正文说它说的话
- 正文引了但文献表没有，或文献表有但正文没引

**图和表**
- 提到了但不存在的子图；从未被正文提到的表和图
- 图注描述的内容和图上画的不一致

**代码和数据**（提供了才查）
- 运行附带代码，把输出和论文里的数逐个比对
- 代码算的东西和方法部分写的不一样
- 训练集和测试集泄漏；只可能得出"一致"的评估方式
- 没有任何测试读过的结果文件

**报告规范**
- 识别研究类型，对照相应规范：CONSORT、STROBE、PRISMA、ARRIVE、STARD、TRIPOD+AI、COREQ
- 伦理审批、知情同意、利益冲突、基金、数据与代码可得性、试验注册
- 样本量依据、随机化、盲法

**结论**
- 观察性数据用了因果措辞；有保留的发现写成了确定的
- 摘要说得比结果更满
- 计划中的工作写成了已完成；事后挑选的亚组或阈值

**AI 写作痕迹**
- 没删掉的助手回复、占位符、`[citation needed]`
- 扭曲短语：固定术语被同义词替换坏了
- 同一个概念用了几个名字；缩写未定义就使用

---

## 你会拿到什么

一份浏览器直接打开的 HTML 报告，同时附 Markdown 和 JSON。

- **总览**：几条会改变结论、几条值得改、哪些没法核实
- **每一条发现**：原文引用和位置、矛盾的证据、算式、替换句、严重程度
- **无法核实**：哪些没查、为什么没查（没提供代码、文献查询失败），不会悄悄跳过
- 报告语言跟随你的提问语言

![一份中文核查报告](docs/images/report-zh.png)

完整示例：[示例报告（Markdown）](examples/demo-zh/report/report.md)，HTML 版在 `examples/demo-zh/report/report.html`，原稿在 [`examples/demo-zh/manuscript.md`](examples/demo-zh/manuscript.md)。

---

## 为什么可以相信它的发现

- **算出来，不是猜出来。** 凡是算术能判定的，都由脚本计算，这部分结果每次运行、换任何模型都一样。
- **引原文，不转述。** 一条发现必须能指出原文，以及和它矛盾的证据，否则不报。
- **只说不一致，不做指控。** 它只报告论文怎么写、哪里和它矛盾，从不推断动机。
- **每条候选都要复核。** 模型会回到原文逐条确认脚本的发现，误读的在成稿前剔除。

## 基准测试

全部基于公开的 arXiv 论文源码，可以复现，详见 [`benchmark/`](benchmark/README.md)。下表只测脚本层（不含模型复核）。

| 测试 | 结果 |
|---|---|
| 作者后来自己更正过数字的 14 篇论文 | 在更正前的版本上查出 1 篇（上文的 41.4% 案例）。多数更正是重跑实验后正文和表格一起改，更正前的版本内部并不矛盾 |
| 开发中从未用过的 182 篇近期论文（3 批，不同学科） | 严重级发现共 25 条，人工逐条核对：5 条属实（引用键在文献库里不存在、正文引用的子图图注里没有），其余为误报；每批暴露的误报类型都已修复后再测下一批，最后一批 50 篇仅 1 条，为误报 |

结论：脚本的发现是候选，必须经过上面的复核步骤，这也是它作为 skill 运行的原因。

---

## 它不做什么

- 查重和 AI 生成率评分。请使用学校或期刊指定的平台。
- 图片篡改鉴定。
- 评价创新性或重要性。
- 判定是否存在学术不端。

## 隐私

稿件只留在你的电脑和你本来就在用的模型里。文献核查只把文献条目信息发给 Crossref、OpenAlex、arXiv、PubMed；加 `--offline` 可关闭。

## 常见问题

**和直接让 ChatGPT 审一遍有什么不同？**
对话模型是读完给意见，每次给的都不一样。Paper Fact Check 会重算论文里的数、逐条查文献，只报告能引原文的问题。

**会不会把没问题的地方报出来？**
偶尔会，比如两个数不同其实是因为来自不同条件。每条发现都附证据，几秒钟就能判断要不要理会。

**哪些学科能用？**
凡是报告数字、统计结果或参考文献的论文都能用。报告规范部分覆盖临床、生物医学、社会科学和机器学习的常见研究类型。

**支持哪些文件？**
PDF、Word（.docx）、LaTeX 文件夹或 zip（含 Overleaf 导出）、Markdown。代码和数据文件夹可选。

## 许可证

MIT
