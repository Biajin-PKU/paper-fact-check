"""What each kind of finding is called, which group it belongs to, and whether it changes a conclusion."""
from __future__ import annotations

GROUPS = {
    "numbers": ("Numbers", "数字"),
    "statistics": ("Statistics", "统计"),
    "references": ("References", "参考文献"),
    "figures": ("Figures and tables", "图和表"),
    "code": ("Code and data", "代码和数据"),
    "reporting": ("Reporting standards", "报告规范"),
    "claims": ("Claims", "结论"),
    "writing": ("Traces of AI writing", "AI 写作痕迹"),
    "other": ("Other", "其他"),
}

# category: (group, English title, Chinese title, first-order when major)
CATEGORIES = {
    "prose_table_number_disagreement": ("numbers", "Text and table give different values", "正文和表格的数对不上", True),
    "cross_section_number_disagreement": ("numbers", "One quantity, different values in different sections", "同一个量在不同章节写法不一", True),
    "relative_change_mismatch": ("numbers", "Relative change does not match its own numbers", "相对变化和它自己给的两个数对不上", True),
    "same_change_different_values": ("numbers", "The same change quoted at two values", "同一个变化写成了两个数", True),
    "percent_count_mismatch": ("numbers", "Percentage does not match its count", "百分比和计数对不上", True),
    "percent_denominator_outlier": ("numbers", "One percentage uses a different denominator", "一个百分比的分母和其他不一致", False),
    "product_total_mismatch": ("numbers", "Parts do not multiply to the stated total", "各部分相乘不等于所说的总数", True),
    "compute_budget_inconsistency": ("numbers", "Stated totals contradict each other", "前后给出的总量互相矛盾", True),
    "terminal_digit_nonuniform": ("numbers", "Unusual digit distribution in tables", "表格数字的末位分布异常", False),
    "pvalue_recompute_mismatch": ("statistics", "p-value does not follow from its test statistic", "p 值和检验统计量算不回来", True),
    "pvalue_z_mismatch": ("statistics", "p-value does not follow from its z statistic", "p 值和 z 值算不回来", True),
    "pvalue_t_impossible": ("statistics", "p-value impossible for its t statistic", "这个 t 值不可能得出这么小的 p 值", True),
    "pvalue_clustering_below_0_05": ("statistics", "Many p-values just below 0.05", "多个 p 值恰好落在 0.05 之下", False),
    "interval_p_contradiction": ("statistics", "Confidence interval and p-value disagree", "置信区间和 p 值互相矛盾", True),
    "estimate_outside_interval": ("statistics", "Estimate outside its own interval", "点估计落在自己的置信区间外", True),
    "effect_size_mismatch": ("statistics", "Effect size does not follow from the test", "效应量和检验结果算不回来", False),
    "grim_infeasible_mean": ("statistics", "Mean impossible for its sample size (GRIM)", "这个平均值在该样本量下不可能出现（GRIM）", True),
    "grimmer_infeasible_sd": ("statistics", "Standard deviation impossible for its mean and sample size (GRIMMER)", "这个标准差在该均值和样本量下不可能出现（GRIMMER）", True),
    "directional_claim_against_interval": ("claims", "Claim stronger than its own interval", "结论比它自己的区间说得更满", True),
    "panel_reference_beyond_caption": ("figures", "Text refers to a panel the figure does not have", "正文引用了图中不存在的子图", False),
    "uncited_float": ("figures", "Table or figure never referred to", "正文从未提到的表或图", False),
    "citation_undefined": ("references", "Citation with no entry in the list", "引用了文献表里没有的条目", False),
    "citation_beyond_list": ("references", "Citation number beyond the list", "引用编号超出了文献表", False),
    "reference_never_cited": ("references", "Reference never cited", "文献表里有但正文没引", False),
    "reference_duplicate": ("references", "Same work listed twice", "同一篇文献列了两次", False),
    "reference_not_found": ("references", "Reference cannot be found", "查不到这篇文献", True),
    "reference_doi_unresolved": ("references", "DOI does not resolve", "DOI 打不开", False),
    "reference_doi_mismatch": ("references", "DOI points to a different work", "DOI 指向的是另一篇论文", False),
    "reference_arxiv_unresolved": ("references", "arXiv identifier does not exist", "arXiv 编号不存在", False),
    "reference_arxiv_mismatch": ("references", "arXiv identifier points to a different work", "arXiv 编号指向另一篇论文", False),
    "reference_retracted": ("references", "Cited work has been retracted", "引用的论文已被撤稿", True),
    "reference_concern": ("references", "Cited work has an expression of concern", "引用的论文有关注声明", False),
    "reference_year_mismatch": ("references", "Reference year differs from the record", "文献年份和记录不一致", False),
    "constructed_series_json": ("code", "Released results step by an exact constant", "公开的结果文件数值等差排列", True),
    "back_solved_mean": ("code", "Per-run values average exactly onto the printed result", "各次运行的值恰好平均到论文报的数", True),
    "label_derived_score": ("code", "Code derives a score from the answer it should predict", "代码用答案反推出分数", True),
    "unbound_released_record": ("code", "Released result file that no test reads", "公开的结果文件没有任何测试读取", False),
    "assistant_residue": ("writing", "Chatbot text or placeholder left in the paper", "论文里残留的 AI 回复或占位符", False),
    "tortured_phrase": ("writing", "Tortured phrase (synonym-swapped term)", "被同义词替换坏的专业术语", False),
    "abbreviation_before_definition": ("writing", "Abbreviation used before it is defined", "缩写在定义之前就用了", False),
    "abbreviation_two_expansions": ("writing", "Abbreviation expanded two ways", "同一个缩写有两种全称", False),
}


def describe(category: str, lang: str) -> tuple[str, str, bool]:
    group, en, zh, first = CATEGORIES.get(category, ("other", category.replace("_", " ").capitalize(),
                                                      category.replace("_", " "), False))
    return group, (zh if lang == "zh" else en), first
