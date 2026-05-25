# /target-intel — 靶点立项情报分析

> 适用于任何治疗靶点的全维度立项情报调研，深度整合智慧芽MCP工具。
> 用法：`/target-intel KRAS`、`/target-intel ALK7 siRNA`、`/target-intel KIT 小分子`
> 可选参数：靶点名后可跟模态关键词（siRNA/小分子/抗体/ADC/PROTAC），影响深度分析方向。

📎 **公共模块**：执行前 Read `/Users/nihil/Claude/bio-intelligence/.claude/commands/_shared.md`，加载 Pre-flight 检查、数据治理框架和 HTML 规范。

---

## 执行流程

### Step 0：解析参数

从 `$ARGUMENTS` 中提取：
- **靶点名**（必填）：基因名/别名，如 KRAS、ALK7/ACVR1C、KIT/CD117
- **模态偏好**（可选）：siRNA / 小核酸 / 小分子 / 抗体 / ADC / PROTAC / 细胞治疗
- **适应症类型**：判断是否为肿瘤（oncology）靶点，决定是否启用 Step 3 肿瘤条件分支
- 若无模态参数，默认全模态分析

**【免疫靶点识别】** 判断靶点是否属于以下家族：
- TNFR 超家族（OX40/TNFRSF4、CTLA-4、CD40、RANK、DR5 等）
- CD28 超家族（PD-1、ICOS、TIGIT、TIM-3 等）
- 细胞因子受体（IL-4R、IL-13R、TSLPR 等）

若为免疫靶点，**同时识别其配体/受体伴侣**（如 OX40→OX40L/TNFSF4，PD-1→PD-L1/PD-L2），并在 Step 2 中同步搜索。配体伴侣作为"共靶点"在报告中独立呈现。

输出一行确认：
`📡 靶点：[靶点名] | 配体伴侣：[伴侣名或"无"] | 模态：[模态或"全模态"] | 类型：[肿瘤/非肿瘤] — 启动智慧芽MCP深度调研...`

---

### Step 1：实体标准化（必须最先执行，单独调用）

```
ls_ner_nor_normalize(user_input="$ARGUMENTS")
```

从返回结果中获取：靶点标准化ID、别名列表、关联疾病名、关联药物名。
后续所有 MCP 查询**使用标准化名称**以确保查全率，同时保留别名用于向量搜索。

**若识别到配体伴侣，同时标准化：**
```
ls_ner_nor_normalize(user_input="<配体伴侣名>")
```

---

### Step 2：广度并行扫描（全部并行，一次性发出）

> ⚠ `ls_drug_milestone_fetch` 和 `ls_organization_pipeline_fetch` 需要先知道药物ID/公司名，**已移至 Step 4**，不在此并行。

**靶点与疾病基础**
1. `ls_target_fetch(target=["<标准化靶点名>"])`
2. `ls_disease_fetch(disease=["<关联主要疾病>"])`

**药物管线（主靶点）— 分阶段全量检索**

> ⚠ **禁止使用单次 `limit=40` 大查询**：API 返回的 `total` 是全库计数，`limit` 只控制返回记录数；当 total >> limit 时，多余记录被截断，且 API 隐式排序不稳定，导致结果不可重复。例：OX40 total=86, limit=40 → 46条记录永久丢失。
>
> **必须按 `highest_phase` 分阶段发出，确保每阶段 total < limit，全量稳定返回。**

并行发出以下查询（主靶点 5 组 + 配体伴侣 5 组，共 10 组，若无配体伴侣则 5 组）：

**主靶点（5组）**
3a. `ls_drug_search(target=["<标准化靶点名>"], highest_phase=["approved","nda_bla"], limit=20)`
3b. `ls_drug_search(target=["<标准化靶点名>"], highest_phase=["phase_3","phase_2_3"], limit=20)`
3c. `ls_drug_search(target=["<标准化靶点名>"], highest_phase=["phase_2"], limit=20)`
3d. `ls_drug_search(target=["<标准化靶点名>"], highest_phase=["phase_1","phase_1_2","early_phase_1"], limit=30)`
3e. `ls_drug_search(target=["<标准化靶点名>"], highest_phase=["preclinical"], limit=40)` ← 临床前，用于 Step 4 多维评分筛选

**【若识别到配体伴侣】配体伴侣（5组）**
- `ls_target_fetch(target=["<配体伴侣名>"])`
- `ls_drug_search(target=["<配体伴侣名>"], highest_phase=["approved","nda_bla"], limit=20)`
- `ls_drug_search(target=["<配体伴侣名>"], highest_phase=["phase_3","phase_2_3"], limit=20)`
- `ls_drug_search(target=["<配体伴侣名>"], highest_phase=["phase_2"], limit=20)`
- `ls_drug_search(target=["<配体伴侣名>"], highest_phase=["phase_1","phase_1_2","early_phase_1"], limit=30)`
- `ls_drug_search(target=["<配体伴侣名>"], highest_phase=["preclinical"], limit=40)`

合并去重后分组：**已批准 → Ph3 → Ph2 → Ph1（全量呈现）**；**临床前 → Step 4 评分筛选 Top 20**。

**临床试验**
5. `ls_clinical_trial_search(target=["<标准化靶点名>"], limit=30)`
6. `ls_clinical_trial_result_search(target=["<标准化靶点名>"], limit=15)`

**专利（双轨交叉验证 — 必做）**
7. `ls_patent_search(target=["<标准化靶点名>"], patent_core_type=["product_compound","sequence","new_use"], limit=30)`
8. `patsnap_search(search_strategy=["keyword"], keywords=["<标准化靶点名>", "<靶点别名1>", "<靶点别名2>"], sources=["patent"], topk=30)` ← ⚠ **必做交叉验证**：Pharma Intelligence 靶点标注索引对 WO 新公开专利有 6-12 月延迟，patsnap_search 使用全文关键词匹配可捕获遗漏专利
9. `patsnap_search(search_strategy=["semantic"], semantic_query="<靶点名> mechanism inhibitor therapeutic target drug discovery", sources=["patent"], topk=20)` ← 语义专利补充

> ⚠ **专利覆盖率交叉验证**：将 7（ls_patent_search）与 8-9（patsnap_search）结果按专利号去重对比。若 patsnap_search 出现 ls_patent_search 未收录的专利号（尤其当年和前一年公开的 WO），在报告中标注"⚠ ls_patent_search 未收录，原因为靶点索引延迟"。对管线公司追加 `patsnap_search(keywords=["<公司名>", "<靶点名> antibody patent"])` 确保覆盖公司最新申请。

**交易与文献**
10. `ls_drug_deal_search(target=["<标准化靶点名>"], limit=20)`
11. `ls_paper_search(target=["<标准化靶点名>"], limit=15)``

**转化医学与流行病学**
12. `ls_translational_medicine_search(target=["<标准化靶点名>"], limit=10)`
13. `ls_epidemiology_vector_search(query="<靶点名> <主要疾病> incidence prevalence patient population", lang="EN", top_k=10)`

**近期动态**
14. `ls_news_vector_search(query="<靶点名> drug clinical trial approval deal", lang="EN", top_k=10)`

**管线覆盖率补充验证（必做）**

药物管线搜索天然存在收录延迟，`ls_drug_search` 可能遗漏近6-12个月入组的关键品种。用新闻搜索交叉验证：
```
ls_news_vector_search(query="<靶点名> <配体伴侣名> new drug Phase 3 Phase 2 clinical trial 2024 2025 approval", lang="EN", top_k=15)
```
将新闻中提及的药物名与 drug_search 结果对比，若出现未收录品种，在 Step 4 中用 `ls_drug_search(drug_name=["<药物名>"])` 补充查询。

---

### Step 3：深度向量挖掘（按模态 + 适应症类型分支并行）

收到 Step 2 结果后，**同时**发起以下向量搜索：

**通用深度搜索（每个靶点必做）**
```
ls_patent_vector_search(query="<靶点名> mechanism binding site inhibitor resistance mutation", lang="EN", top_k=15)
ls_paper_vector_search(query="<靶点名> signaling pathway biomarker clinical efficacy", lang="EN", top_k=10)
ls_clinical_trial_vector_search(query="<靶点名> phase 2 3 response rate efficacy safety", lang="EN", top_k=10)
ls_clinical_guideline_vector_search(query="<主要疾病> treatment guideline first-line standard of care", lang="EN", top_k=8)
ls_fda_label_vector_search(query="<已上市最重要药物名> indication dosage efficacy safety adverse events", lang="EN", top_k=8)
ls_financial_report_vector_search(query="<靶点名> market size revenue forecast commercial", lang="EN", top_k=8)
```

**生物标志物专项搜索（每个靶点必做）**
```
ls_translational_medicine_search(query="<靶点名> biomarker companion diagnostic patient selection", limit=10)
ls_paper_vector_search(query="<靶点名> diagnostic prognostic predictive biomarker companion diagnostic IHC score", lang="EN", top_k=10)
ls_clinical_trial_vector_search(query="<靶点名> biomarker stratification enrollment criteria IHC threshold", lang="EN", top_k=8)
```

**药物警戒专项搜索（已有上市药物时执行）**
```
ls_fda_label_vector_search(query="<药物名> adverse events warnings black box REMS dose modification", lang="EN", top_k=10)
ls_paper_vector_search(query="<靶点名> safety tolerability adverse events toxicity real world", lang="EN", top_k=8)
ls_clinical_trial_vector_search(query="<靶点名> dose limiting toxicity DLT discontinuation rate safety profile", lang="EN", top_k=8)
```

**KOL 与学术生态（每个靶点必做）**
```
ls_paper_vector_search(query="<靶点名> KOL academic institution collaboration clinical investigator principal investigator leading researcher", lang="EN", top_k=12)
ls_paper_fetch(paper_ids=[<Step2高引文献ID列表>])  — 获取关键文献全文，提取通讯作者/机构/合作关系
ls_news_vector_search(query="<靶点名> conference ASCO AACR ESMO keynote presentation academic publication", lang="EN", top_k=8)
```

**【若为免疫靶点】MOA 专项搜索**

免疫靶点存在激动剂/拮抗剂两种截然不同的 MOA，必须分别搜索：
```
ls_paper_vector_search(query="<靶点名> agonist stimulatory costimulatory T cell activation cancer immunotherapy", lang="EN", top_k=8)
ls_paper_vector_search(query="<靶点名> antagonist blocking inhibitory antibody autoimmune inflammatory", lang="EN", top_k=8)
ls_paper_vector_search(query="<靶点名> ADCC antibody dependent cell cytotoxicity depleting non-depleting Treg NK cell pyrexia fever", lang="EN", top_k=8)
```
对于抗体类药物，还需搜索 Fc 效应功能差异（depleting IgG1 vs non-depleting IgG4/aglycosyl）：
```
ls_patent_vector_search(query="<靶点名> antibody IgG1 IgG4 afucosylated ADCC effector function depleting non-depleting half-life extension YTE XTEND", lang="EN", top_k=10)
ls_news_vector_search(query="<靶点名> <配体伴侣名> mechanism depleting non-depleting safety profile TEAE pyrexia", lang="EN", top_k=8)
```

**若为肿瘤适应症，追加：**
```
ls_paper_vector_search(query="<靶点名> <癌种> molecular subtype ASCL1 TP53 RB1 genomic classification", lang="EN", top_k=10)
ls_clinical_trial_vector_search(query="<癌种> unmet medical need treatment gap progression overall survival benchmark", lang="EN", top_k=8)
ls_paper_vector_search(query="<靶点名> tumor microenvironment immune evasion resistance mechanism", lang="EN", top_k=8)
```

**若模态含"siRNA/小核酸/RNAi/ASO/寡核苷酸"，追加：**
```
ls_patent_vector_search(query="<靶点名> siRNA dsRNA antisense strand sequence chemical modification 2'-OMe 2'-F GalNAc delivery", lang="EN", top_k=15)
ls_patent_vector_search(query="<靶点名> oligonucleotide adipose liver tissue delivery conjugate lipid nanoparticle", lang="EN", top_k=10)
ls_sequence_search_submit(sequence="<靶点mRNA关键序列>", search_type="siRNA", top_k=20)  ← biology_modality，竞品序列相似性搜索（异步，需 check_status + get_results）
ls_modification_search_submit(query="<靶点名> siRNA chemical modification 2OMe 2F GalNAc LNA PS backbone", limit=20)  ← biology_modality，化学修饰专利搜索
ls_patent_sequence_fetch(patent_ids=[<含序列的重要专利ID>])  ← biology_modality，获取专利中的序列数据
```
> 注：ls_sequence_search_submit 返回 task_id，需调用 ls_sequence_search_check_status(task_id=<id>) 确认完成，再 ls_sequence_search_get_results(task_id=<id>) 取结果。

**若模态含"小分子"，追加：**
```
ls_patent_vector_search(query="<靶点名> small molecule inhibitor selectivity kinase binding crystal structure", lang="EN", top_k=15)
ls_patent_vector_search(query="<靶点名> mutation resistance acquired secondary bypass mechanism", lang="EN", top_k=10)
ls_structure_search(smiles="<候选化合物SMILES>", type="SIM", threshold=0.8, limit=20)  ← chemical_molecular，竞品结构相似性（必须提供 SMILES，type="SIM" 表示相似性搜索）
ls_structure_fetch(structure_id=<来自structure_search的代表性结构ID>)  ← chemical_molecular，获取结构详情
ls_chemical_mcs_analyze(smiles_list=["<化合物1 SMILES>", "<化合物2 SMILES>", "<化合物3 SMILES>"])  ← chemical_molecular，最大公共子结构分析（骨架共性识别）
ls_sar_submit(target="<靶点名>", smiles=["<候选化合物列表>"])  ← chemical_molecular，构效关系分析（异步，需 ls_sar_fetch）
ls_patent_structure_fetch(patent_ids=[<含化合物结构的重要专利ID>])  ← chemical_molecular，专利结构数据
ls_admet_predict(smiles="<代表性先导化合物SMILES>")  ← chemical_molecular，成药性快速评估
```
> 注：ls_sar_submit 返回 task_id，需调用 ls_sar_fetch(task_id=<id>) 获取构效关系分析结果。

**若模态含"抗体/mAb/ADC/双抗"，追加：**
```
ls_patent_vector_search(query="<靶点名> antibody epitope binding affinity CDR humanization bispecific", lang="EN", top_k=15)
ls_paper_vector_search(query="<靶点名> antibody drug conjugate payload linker ADC PK ADCP internalization", lang="EN", top_k=10)
ls_antibody_antigen_search(target_name="<标准化靶点名>", limit=20)  ← biology_modality（参数必须用 target_name=，不能用 query=）
ls_sequence_search_submit(sequence="<靶点抗原表位关键序列>", search_type="antibody", top_k=20)  ← biology_modality，抗体序列相似性（异步）
ls_sequence_alignment(sequences=["<候选抗体VH序列>", "<参考抗体VH序列>"])  ← biology_modality，CDR/框架区序列比对
```

---

### Step 4：重点数据拉取与数据质量验证

从 Step 2 和 Step 3 结果中执行批量 fetch，**同时进行数据质量交叉验证**：

**批量拉取（优先级排序）**
- 取最重要的 **5-8 件专利** → 优先用 `patsnap_fetch(keys=[<专利号列表>], key_type="pn", module=["basic"])` 获取完整 Markdown；备用 `ls_patent_fetch(patent_ids=[...])`
- 取最重要的 **3-5 篇文献** ID → `ls_paper_fetch(paper_ids=[...])`
- 取最重要的 **3-5 个交易** ID → `ls_drug_deal_fetch(drug_deal_ids=[...])`
- 取最重要的 **2-4 条转化医学** ID → `ls_translational_medicine_fetch(translational_medicine_ids=[...])`
- 若有关键公司出现多次 → `ls_organization_fetch(organization=["<公司名>"])` 获取公司详情
- 关键新闻条目 → `ls_news_fetch(news_ids=[...])` 获取 Step 2 高相关性新闻的全文详情
- 若小分子模态已提交 SAR → `ls_sar_fetch(task_id=<id>)` 获取构效关系报告
- 若核酸模态已提交序列搜索 → `ls_sequence_search_get_results(task_id=<id>)` 获取结果

**专利 Analytics UUID 解析（！必做）**

报告中的专利条目需要 Analytics 链接（`https://analytics.zhihuiya.com/patent-view/abst?patentId={UUID}`），但 `ls_patent_search`/`ls_patent_fetch` 返回的 `patent_id` 为 32 位 hex 格式，不含 UUID 连字符。**必须经 `patsnap_search` 获取 UUID**：
```
patsnap_search(search_strategy=["keyword"], keywords=["<专利号>"], sources=["patent"], topk=1)
```
从返回结果的 `id` 字段提取 UUID（如 `84e2b026-6a0c-4f71-b8b8-e9f9f2325678`），组装 Analytics 链接。

**管线公司来源文献（！新增必做步骤）**

对每个有管线药物（Phase 1-3/已批准）的公司，**必须检索其来源文献**，因为公司发表论文是管线药物最直接的机理/疗效证据，远比通用靶点生物学论文更有价值：
```
ls_paper_search(organization=["<公司名>"], target=["<标准化靶点名>"], limit=10)  ← 公司+靶点交叉
ls_paper_search(organization=["<公司名>"], limit=10)  ← 公司全部文献（可能含靶点未标注的论文）
```
在报告文献节中以"管线公司来源文献"子节独立呈现，标注公司名和管线品种关联。

**药物管线逐条验证（！新增质控步骤）**

对 drug_search 中 Phase 1-3 的每个关键品种，**单独执行 `ls_drug_fetch`** 以验证：
```
ls_drug_fetch(drug_ids=["<drug_id_1>", "<drug_id_2>", ...])
```
验证以下字段的一致性：
| 字段 | 验证逻辑 |
|------|---------|
| 开发公司 | drug_fetch 返回的 `organization` 为准；search 结果"未披露"时 fetch 往往有完整信息 |
| 开发阶段 | drug_fetch 的 `highest_phase` 与 search 结果对齐；不一致时以 fetch 为准 |
| MOA/作用机制 | 校验是否与靶点一致；如返回完全不同靶点的药物，说明 drug_id 对应错误（见容错规则10） |
| 适应症 | 是否与本次分析领域相关 |

**里程碑与竞争对手快照（从 Step 2 移至此处）**
- 关键药物里程碑 → `ls_drug_milestone_fetch(drug_id=[<从drug_search获取的关键药物ID>])` — IND/NDA/获批/停项时间线
- 竞争对手全管线 → `ls_organization_pipeline_fetch(organization=["<Step 2中识别的主要竞争公司>"])` — 竞争对手全管线快照

**已批准药物完整信息**
- 已批准药物各取 1 条 → `ls_drug_fetch(drug_ids=[...])` 获取 PK/PD 完整信息

**BD 交易状态交叉验证（！新增质控步骤）**

BD 交易的终止状态可能不同步反映在 `ls_drug_fetch` 的开发商列表中。对每个重要交易：
1. 从 `ls_drug_deal_fetch` 结果中检查 `status` 字段（Active / Terminated / Completed）
2. 检查交易标题和描述中是否含有"exit"、"terminate"、"jilt"、"walk away"等终止关键词
3. 若发现终止交易，在报告中以醒目方式（红色警示框）标注，并说明权益归属预期
4. 不要仅依赖 `drug_fetch` 的开发商列表判断合作状态

选取标准：专利优先选引用量高/申请人为头部公司/含技术创新的；交易优先选金额最大/最近的。

**临床前管线多维评分与筛选（Top 20）**

对 Step 2（3e 组）返回的全部临床前候选品种，在 Step 4 执行以下评分流程，选出 Top 20 进行 `drug_fetch` 详细记录。

> **设计原则**：临床前品种数量多、数据稀疏，不能全量 fetch；但纯粹按 API 返回顺序取前 N 条会遗漏真正有价值的早期资产。五维评分提供客观排序依据。

**评分维度（每条品种 0–4 分，总分 0–20）**

| 维度 | 满分 | 数据来源 | 评分标准 |
|------|------|---------|---------|
| **BD 线索** | 4 | `ls_drug_deal_search`（品种名/公司名）+ `ls_news_vector_search` | 有正式 BD 交易（已签）=4；新闻提及洽谈/LOI=2；无信号=0 |
| **专利申请时间** | 4 | Step 2 `ls_patent_search` 结果中的申请日字段 | 2024年后申请=4；2022–2023=3；2020–2021=2；2019年前=1；无专利=0 |
| **MOA 新颖性** | 4 | Claude 判断：与已进入临床的品种 MOA 对比 | 全新作用靶点/机制=4；已知机制但模态创新（如 ADC/PROTAC）=3；同类优化=2；完全同质化=0 |
| **研究机构影响力** | 4 | `ls_paper_vector_search` 通讯作者/机构 + `ls_organization_fetch` | 顶级学术医学中心（MD Anderson/Mayo/MSKCC/北京协和等）=4；头部企业研发中心=3；区域知名机构=2；无知名机构信号=0 |
| **文献影响力** | 4 | `ls_paper_search` 返回的引用数/期刊 | IF>10 期刊或引用>100=4；IF 5–10 或引用 30–100=3；IF 2–5=2；仅会议摘要=1；无文献=0 |

**执行步骤**

1. 从 Step 2（3e 组）获取完整临床前品种列表（drug_id + 名称 + 公司）
2. 对每条品种，**并行**检索以下补充数据（批量发出，1轮内完成）：
   ```
   ls_drug_deal_search(drug_name=["<品种名>"], limit=5)        ← BD线索
   ls_patent_search(target=["<靶点名>"], drug_name=["<品种名>"], limit=5)  ← 专利时间
   ls_news_vector_search(query="<品种名> deal partnership license", lang="EN", top_k=5)  ← BD新闻
   ls_paper_vector_search(query="<品种名> preclinical efficacy mechanism", lang="EN", top_k=5)  ← 文献
   ```
   > 若临床前品种过多（>30条），先按 API 返回顺序取前 30 条参与评分，避免 context 过载。

3. 依据五维评分表打分，**形成排序表**：

   | 排名 | 品种名 | 公司 | BD线索 | 专利时间 | MOA新颖性 | 机构影响力 | 文献 | 总分 |
   |------|--------|------|--------|---------|---------|---------|------|------|
   | 1 | ... | ... | 4 | 3 | 4 | 2 | 3 | 16 |
   | ... |

4. 取 **总分最高的 Top 20** 品种，执行：
   ```
   ls_drug_fetch(drug_ids=["<top20_drug_id列表>"])
   ```
   若总分前 20 名中存在明显并列（分差 ≤1），优先选择 BD线索 得分更高的品种。

5. 将 Top 20 临床前品种写入报告管线表，附评分总分列；其余品种以"临床前候选池（共 N 个，已按五维评分筛选）"在备注中说明。

---

### Step 5：综合分析框架

整合所有 MCP 数据 + Claude 自身知识，按以下框架分析（各节标注数据来源）：

#### 5.1 靶点基础（📡 MCP: target_fetch + paper）
- 基因位置、蛋白结构、关键功能域
- 信号通路图谱（上游激活 → 靶点 → 下游效应）
- 致病机制（功能获得型 / 功能缺失型 / 过表达）
- 突变谱（按适应症列举关键突变，注明频率）
- 组织表达特异性（来源：文献 + target_fetch）
- 人类遗传学验证证据（GWAS/Mendelian randomization）

**【若为免疫靶点】配体伴侣并列分析**
- 受体（主靶点）与配体（伴侣靶点）的生物学功能对比
- 两种调控策略的差异：靶向受体 vs 靶向配体的 MOA 区别
- 已上市/在研品种按靶向受体/配体分类统计

**【新增】生物标志物四分类分析**（📡 MCP: translational_medicine + paper + clinical_trial）
| 标志物类型 | 定义 | 本靶点对应标志物 | 检测方法 | 临床应用状态 |
|-----------|------|-----------------|---------|------------|
| 诊断型（Diagnostic） | 识别目标患者人群 | [如 DLL3 IHC H-score] | [IHC/NGS/PCR] | [已批/探索中] |
| 预后型（Prognostic） | 预测自然病程好坏 | [如 ASCL1高表达] | [...] | [...] |
| 预测型（Predictive） | 预测对特定药物的响应 | [如 DLL3≥75% cut-off] | [...] | [...] |
| 药效动力学（PD Biomarker） | 确认靶点接合/通路抑制 | [如 ctDNA清零率] | [...] | [...] |

伴随诊断（CDx）开发现状：现有/在研/空白 + 监管状态

**KOL 与学术生态**（📡 MCP: paper_vector_search + paper_fetch + news_vector_search）
- **领域 Top KOL 表**（来自 paper_vector_search KOL 查询 + paper_fetch 通讯作者提取）：
  | 姓名 | 机构 | 研究方向 | 代表文献 | 产业合作 |
  |------|------|---------|---------|---------|
- 高影响力文献 Top 5（来自 paper_fetch 全文，提取核心引用关系）
- 学术机构分布：哪些高校/研究所在此靶点有活跃转化研究

#### 5.2 药物管线（📡 MCP: drug_search + drug_fetch + clinical_trial + drug_milestone_fetch）
- **已批准药物**全清单（含首批日期、公司、适应症、机制）
- **临床阶段**品种按 Phase 3 → 2 → 1 排列，标注公司/模态/适应症
- **关键里程碑时间线**（来自 drug_milestone_fetch）：各主要品种 IND→Ph1→Ph2→Ph3→NDA 时间点
- **临床前**代表性品种（若有显著创新）
- 模态分布统计（小分子/抗体/ADC/siRNA/细胞治疗/PROTAC 各几个）
- **中国管线**专项：已批/在研/空白分析
- **PK/PD 关键参数**（已上市药物）：半衰期/暴露量/Cmax/分布容积/口服生物利用度/主要代谢途径

> ⚠ **公司名称质控**：管线表中每个品种的公司名必须来自 `ls_drug_fetch` 验证后的结果，不得直接使用 drug_search 中"未披露"的原始字段。若 fetch 后仍无公司信息，标注"⚠ 开发商待核实"，同时用 `ls_news_vector_search(query="<药物名> company developer")` 补充。

**【若为免疫靶点】按 MOA 分类展示管线**

免疫靶点管线必须在三个维度呈现（**缺任何一个维度均为不完整报告**）：

| MOA 类别 | 作用靶点 | Fc效应 | 代表品种 | 临床状态 | 关键AE |
|---------|---------|-------|---------|---------|-------|
| 激动剂（Agonist） | 受体 | 依IgG亚型 | ... | ... | ... |
| 受体拮抗剂（Antagonist） | 受体 | 耗竭/非耗竭 | ... | ... | 发热/寒战（耗竭型）|
| 配体拮抗剂（Ligand Ant.） | 配体 | 通常非耗竭 | ... | ... | 安全性更优 |

#### 5.3 安全性与药物警戒（📡 MCP: fda_label + paper + clinical_trial）
- **上市药物 AE 谱系对比表**：各药物 Grade 3+ AE 发生率对比（表格形式）
- **黑框警告/REMS 要求**：如有，逐药列出
- **靶点相关毒性**：由靶点生物学决定的 on-target 毒性（如 VEGFR→高血压，TCE→CRS）
- **剂量限制毒性（DLT）**：各品种 MTD 和 RP2D 信息
- **真实世界安全性**：上市后 AE 信号（来源：文献/FDA FAERS/MCP新闻）
- **毒性管理策略**：剂量调整方案、预防用药、监测方案

**【若为免疫靶点】Fc效应功能与安全性关联分析**
- 按耗竭型（afucosylated IgG1/ADCC增强）vs 非耗竭型（IgG4/aglycosyl/IgG1-LALA）分组对比 AE 谱
- 列出每个品种的 IgG 亚型 + Fc 工程化修饰 + 对应主要 AE

#### 5.4 竞争格局（📡 MCP + 🧠 Claude）
- 突变覆盖矩阵（主要药物 × 突变类型/适应症，颜色编码）
- 各适应症治疗线竞争梯队（1线/2线/后线）
- **耐药机制全图**（靶点突变/旁路激活/表型转化）
- 下一代产品差异化策略（耐药克服/适应症扩展/新模态）
- 主要竞争对手技术壁垒评估
- **竞争对手核心专利识别**（📡 MCP: patent_search + patent_vector_search + patent_fetch）：通过多维检索（申请人 + 技术关键词 + 引用量）识别 Top 3 竞争公司真正无法绕过的核心 IP

**【若为肿瘤适应症】分子亚型分析**
- 肿瘤分子亚型图谱（如 SCLC-A/N/P/I）及各亚型靶点表达
- 未满足临床需求（UMN）评估：各亚型/治疗线的 ORR/PFS/OS 基准 vs 现有 SOC 差距
- 肿瘤微环境（TME）对靶向治疗的影响（免疫细胞浸润/免疫抑制机制）

#### 5.5 市场分析（📡 MCP: epidemiology + financial + guideline）
- 核心适应症流行病学数据（患者数/发病率/诊断率）
- 市场规模（现有 + 2030 预测，全球/中国拆分）
- 现有药物定价参照（孤儿病 vs 广谱）
- 支付政策与准入壁垒（医保/集采影响）
- 标准治疗流程与靶向药切入时机（来源：临床指南）

#### 5.6 专利格局（📡 MCP: patent_search + vector）
- **核心专利族群**（化合物/序列/递送/新用途）按申请人列表
- 各主要专利到期时间估算
- **专利空白区分析**（技术/机制/适应症/模态 4维度）
- 进入可行性：绕路方案/FTO初步判断
- **模态专利深析**（小核酸：序列+修饰+递送；小分子：骨架+选择性；抗体：表位+CDR）

#### 5.7 BD 交易（📡 MCP: deal_search + fetch）
- 近5年重要交易清单（金额/类型/时间/交易方）
- 交易价值趋势（早期 vs 临床期估值对比）
- 关键信号解读（头部公司布局意图/溢价逻辑）
- 近12个月最新动态
- **已终止交易**：单独列出已终止合作，并分析终止原因（技术失败/战略调整/项目裁撤），避免误将终止合作作为活跃合作引用

#### 5.8 立项评估（🧠 Claude 综合判断）
- **综合评分**（0-10分）：成药性/竞争空间/市场价值/技术可行性 4维雷达
- 核心投资亮点（最多5条，按重要性排序）
- 主要风险（最多5条，按严重性排序）
- **推荐差异化方向**（按优先级排序，每条含：技术路线/目标适应症/壁垒建立方式/所需资源量级）
- 发现到 IND 时间/资金估算

---

### Step 6：生成交互式 HTML 报告

将完整分析写入单一 HTML 文件，保存至：
`/Users/nihil/Claude/{靶点名小写}_intel_report.html`

**⚠ 日期要求：报告生成日期必须使用系统注入的 `currentDate`（格式 YYYY-MM-DD），禁止使用训练截止年份推断。文件内所有年份字段在写入前统一核查。**

#### HTML 设计规范

**整体布局**
- 深色主题：背景 `#0d1117`，表面 `#161b22`，次表面 `#21262d`
- 主色调按靶点类别：激酶/受体=`#58a6ff`(蓝)，核酸靶点=`#3fb950`(绿)，免疫/GPCR=`#bc8cff`(紫)，代谢=`#f0883e`(橙)
- 固定顶部导航（sticky nav），各节自动高亮
- Hero 区显示 `📡 MCP实时数据` + `🧠 Claude知识融合` 双徽章 + MCP 检索量统计

**导航节点**（必含）
1. 靶点概览（`#overview`）
2. **MOA 机制概览**（`#moa`）**— 【免疫靶点必含，其他靶点可选】**
3. 信号通路（`#pathway`）
4. 生物标志物（`#biomarker`）
5. KOL 生态（`#kol`）
6. 药物管线（`#pipeline`）
7. 安全性谱系（`#safety`）
8. 竞争格局（`#competition`）
9. 市场分析（`#market`）
10. 专利格局（`#patent`）
11. BD 交易（`#deal`）
12. 立项评估（`#evaluation`）

**交互功能**
- 药物管线表格：可按模态/阶段/公司/靶点（主靶点 or 配体）筛选 + 点击列头排序
- 竞争格局：适应症/MOA × 药物覆盖矩阵（🟢有效/🟡部分/🔴失败/⚫未测试）
- 专利分类 Tab（化合物/序列/递送/新用途/组合）
- 适应症 Tab 切换（各适应症独立竞争分析）
- 可折叠面板：耐药机制详情、专利技术细节、AE 管理方案

**【若为免疫靶点】MOA 机制概览模块（#moa 节必含）**

使用三栏网格展示（CSS grid，每列独立背景色）：
```css
.moa-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
/* 激动剂列：红色调 rgba(248,81,73,.06) */
/* 受体拮抗剂列：主色调 rgba(188,140,255,.06) */
/* 配体拮抗剂列：青色调 rgba(57,208,216,.06) */
```
每列内容：MOA名称 + 主要药物列表 + 作用机制 + 关键安全性信号 + 临床发展现状

**图表（使用 Chart.js CDN，不引入其他 JS 库）**
- 药物管线阶段分布：甜甜圈图（主靶点 vs 配体伴侣双层）
- 模态分布：横向条形图
- 上市药物年度时间线：散点/条形图
- 市场规模预测：折线图（当前年 - 2032E）
- BD 交易价值：气泡图或条形图（已终止交易用虚线/灰色区分）
- 立项四维雷达图（成药性/竞争空间/市场价值/技术可行性）
- **生物标志物类型分布**：四象限气泡图（诊断/预后/预测/PD）
- **AE 谱系对比**：横向分组条形图（各药物 Grade 3+ AE 发生率，按耗竭/非耗竭分组）

**专项可视化（按模态启用）**
- 小核酸模态：序列双链体可视化（碱基颜色编码：2'-OMe蓝/2'-F红/GNA紫/VP绿/PS黄边）
- 小分子模态：突变位点结构域示意图 + 选择性谱系横向对比 + MCS骨架可视化
- 抗体/ADC 模态：靶点表位图 + 有效载荷/接头技术对比表（载荷类型/DAR/旁效应/CNS穿透/主要AE）
- **【肿瘤靶点】分子亚型热力图**：亚型 × 靶点表达 + UMN 缺口可视化

**数据溯源标记（增强版）**
- 每个数据表格增加「可信度」列：🟢 S/A（数据库直接记录）🟡 B/W（搜索/网络）🔴 C（模型推断）
- 关键数值附上标引用编号 `[n]`，对应报告末尾参考列表（tool name + record ID）
- BD 交易卡片含：金额/日期/类型/来源标注；未披露金额显示 `[金额未披露]`；**已终止交易卡片背景灰色 + 红色"已终止"角标**
- 专利条目含：专利号/申请人/状态/到期日（来自 patent_fetch [S] 或标注 `⚠ 估算`）
- 推断/估算数据用斜体 + `（推断）` 或 `（估算，±X%）` 标注
- 报告末尾必含**第 13 节：数据说明**（来源统计 / 关键引用列表 / 数据缺失清单 / 推断方法 / 截止日期 `currentDate`）

**立项评估模块**
- 综合评分仪表盘（0-10 刻度可视化）
- 亮点/风险对比进度条
- 推荐方向优先级矩阵（影响力 × 可行性 二维坐标）
- 下一步行动清单（可勾选 checkbox）

---

### Step 7：输出摘要

```
✅ 靶点情报报告生成完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
靶点：[名称] | [基因] | [UniProt/NCBI]
配体伴侣：[名称/UniProt] 或 "无"
模态聚焦：[模态或"全模态"] | 适应症类型：[肿瘤/非肿瘤]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP 数据覆盖：
  药物管线  n=[X]（主靶点 [X] | 配体伴侣 [X] | 已批 [X] | Ph3 [X] | Ph2 [X] | Ph1 [X]）
  临床试验  n=[X]（结果数 [X]）
  专利      n=[X]（核心化合物 [X] | 序列 [X] | 新用途 [X]）
  BD 交易   n=[X]（活跃 [X] | 终止 [X] | 最大金额 [X]M）
  文献      n=[X]
  生物标志物 n=[X]（诊断 [X] | 预测 [X] | 预后 [X] | PD [X]）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据可信度统计：
  🟢 S/A（数据库直接记录）  n=[X] 条
  🟡 B/W（搜索/网络补充）   n=[X] 条
  🔴 C（模型推断/综合）     n=[X] 条
  ⚠ 数据缺失项             n=[X] 条（详见报告第13节）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
核心发现：
• [最重要的竞争格局/空白机会] — 来源：[S/A/B/C]
• [最重要的市场/交易信号] — 来源：[S/A/B/C]
• [最重要的技术/专利差异化方向] — 来源：[S/A/B/C]
• [关键安全性信号或生物标志物机会] — 来源：[S/A/B/C]
• [若有已终止交易：终止信号解读] — 来源：[S/A/B/C]

综合评分：[X]/10 🔴 C（综合推断，依据：[X]条 S/A/B 级数据）
立项建议：[强烈推荐 / 推荐 / 谨慎推荐 / 不推荐]
理由：[一句话核心判断]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
报告路径：/Users/nihil/Claude/[filename].html
数据说明：报告第13节（含缺失清单 + 引用列表 + 推断方法）
```

---

## 工具使用速查

| 阶段 | 工具 | 用途 |
|------|------|------|
| Step 1 | `ls_ner_nor_normalize` | 实体标准化（靶点 + 配体伴侣各一次） |
| Step 2 | `ls_target_fetch` | 靶点基础信息（主靶点 + 配体伴侣） |
| Step 2 | `ls_disease_fetch` | 疾病详情 |
| Step 2 | `ls_drug_search` × 2-4 | 全管线（主靶点 + 配体伴侣各两次） |
| Step 2 | `ls_clinical_trial_search` | 注册试验列表 |
| Step 2 | `ls_clinical_trial_result_search` | 已发表试验结果 |
| Step 2 | `ls_patent_search` | 专利结构化检索 |
| Step 2 | `patsnap_search`（patsap_patent_search） | 语义专利补充检索（与 ls_patent_search 并行） |
| Step 2 | `ls_drug_deal_search` | BD 交易列表 |
| Step 2 | `ls_paper_search` | 学术文献 |
| Step 2 | `ls_translational_medicine_search` | 生物标志物/转化研究 |
| Step 2 | `ls_epidemiology_vector_search` | 流行病学数据 |
| Step 2 | `ls_news_vector_search` × 2 | 近期行业动态 + 管线覆盖率补充验证 |
| Step 3 | `ls_patent_vector_search` | 专利技术细节 |
| Step 3 | `ls_paper_vector_search` | 文献语义检索（含生物标志物/安全性/KOL/MOA） |
| Step 3 | `ls_clinical_trial_vector_search` | 试验设计语义检索（含AE/UMN） |
| Step 3 | `ls_clinical_guideline_vector_search` | 治疗指南 |
| Step 3 | `ls_fda_label_vector_search` | 说明书（含警告/REMS） |
| Step 3 | `ls_financial_report_vector_search` | 财报/市场规模 |
| Step 3 | `ls_antibody_antigen_search` | 抗体-抗原相互作用数据（抗体/ADC 模态，参数：`target_name=`） |
| Step 3 | `ls_sequence_search_submit` | 序列相似性搜索提交（核酸/抗体模态，异步） |
| Step 3 | `ls_sequence_search_check_status` | 序列搜索状态查询 |
| Step 3 | `ls_sequence_search_get_results` | 序列搜索结果获取 |
| Step 3 | `ls_sequence_alignment` | 序列比对（CDR/框架区，抗体模态） |
| Step 3 | `ls_modification_search_submit` | 化学修饰专利搜索（核酸模态） |
| Step 3 | `ls_patent_sequence_fetch` | 专利序列数据提取（核酸模态） |
| Step 3 | `ls_structure_search` | 竞品结构相似性检索（小分子模态） |
| Step 3 | `ls_structure_fetch` | 化合物结构详情获取（小分子模态） |
| Step 3 | `ls_chemical_mcs_analyze` | 最大公共子结构分析，识别骨架共性（小分子模态） |
| Step 3 | `ls_sar_submit` | 构效关系分析提交（小分子模态，异步） |
| Step 3 | `ls_patent_structure_fetch` | 专利结构数据提取（小分子模态） |
| Step 3 | `ls_admet_predict` | 成药性快速评估（小分子模态） |
| Step 4 | `ls_drug_fetch` | 药物管线逐条验证（公司/阶段/MOA质控）+ PK/PD完整信息 |
| Step 4 | `ls_drug_milestone_fetch` | 关键药物里程碑时间线（从Step2移至此） |
| Step 4 | `ls_organization_pipeline_fetch` | 竞争对手全管线快照（从Step2移至此） |
| Step 4 | `patsnap_fetch`（patent_paper_fetch） | 专利/论文完整 Markdown 全文（优先于 ls_patent_fetch） |
| Step 4 | `ls_patent_fetch` | 专利全文（备用） |
| Step 4 | `ls_paper_fetch` | 文献全文（兼作 KOL 通讯作者提取） |
| Step 4 | `ls_drug_deal_fetch` | 交易详情（含终止状态验证） |
| Step 4 | `ls_translational_medicine_fetch` | 转化医学详情 |
| Step 4 | `ls_organization_fetch` | 关键公司详情 |
| Step 4 | `ls_clinical_trial_fetch` | 关键试验详情 |
| Step 4 | `ls_news_fetch` | 关键新闻全文详情 |
| Step 4 | `ls_sar_fetch` | 构效关系分析结果（小分子模态） |
| Step 4 | `ls_sequence_search_get_results` | 序列搜索最终结果（核酸/抗体模态） |
| 补充 | `ls_web_search` | MCP 无结果时补充 |

---

## 容错规则

1. **实体未识别**：若 `ls_ner_nor_normalize` 返回空，用原始靶点名继续，在报告中标注"未标准化"
2. **MCP 超时/空结果**：对应节标注 `⚠ MCP数据暂缺`，改用 `ls_web_search` 补充，再用 Claude 知识填充
3. **向量搜索不相关**：换更具体术语重试一次（靶点别名、适应症名、代表性药物名加入 query）
4. **管线过多（>50个）**：全部已批准 + Phase 3 全部 + Phase 2 前10个 + 模态创新品种，其余汇总统计
5. **专利过多（>50件）**：按申请人聚合，每个头部申请人取最新/最重要1-2件 fetch
6. **无上市药物**：安全性节改为"临床期AE预测"，基于靶点生物学 + 同类药物数据推断
7. **非肿瘤靶点**：跳过 Step 3 肿瘤条件分支 + 跳过 HTML 分子亚型热力图模块
8. **序列搜索超时**：ls_sequence_search_submit 异步任务若 check_status 超时，在报告中标注"序列相似性数据待补充"
9. **SAR 任务超时**：ls_sar_submit 异步任务若未完成，改用 Claude 知识 + 文献推断构效关系

**【基于 OX40 案例新增】**

10. **`ls_drug_fetch` ID不匹配**：若 drug_fetch 返回的药物名/靶点与预期完全不符（如查 GS-2272 却返回 IL-33R 药物），说明该 ID 在数据库中对应另一药物。应立即丢弃该 fetch 结果，改用 `ls_drug_search(drug_name=["<药物名>"])` 或 `ls_news_vector_search(query="<药物名> company developer phase")` 重新查询，而不是将错误数据写入报告。

11. **免疫受体靶点缺少配体搜索**：对 TNFR 超家族、CD28 超家族、细胞因子受体等免疫靶点，若仅搜索受体而未搜索配体，报告必然不完整。Step 0 识别配体后，Step 2 必须并行执行配体的 `ls_target_fetch` 和 `ls_drug_search`；若 Step 2 遗漏，在发现时立即补充，不能推迟到报告生成阶段。

12. **BD 交易终止状态未同步**：`ls_drug_fetch` 的开发商列表可能在合作终止后数月仍保留原合作方，不能以此判断合作仍有效。必须通过 `ls_drug_deal_fetch` 或 `ls_news_vector_search` 独立验证交易状态。**已终止合作不得被描述为"活跃合作"或"战略伙伴"**，必须在报告中单独标注终止时间和权益归属预期。

13. **管线关键品种遗漏**：`ls_drug_search` 存在约6-12个月的收录延迟，近期入组的 Phase 3 品种可能缺失。Step 2 的"管线覆盖率补充验证"（`ls_news_vector_search` 交叉核查）是强制步骤。若用户或已知知识指出某品种未见于搜索结果，必须单独执行 `ls_drug_search(drug_name=["<药物名>"])` 补充，而不是以"数据库无记录"为由忽略。

---

## 可扩展方向

### 扩展 A：多靶点比较模式
用法：`/target-intel KRAS vs NRAS vs HRAS 小分子`
- 并行执行 Step 1-4 × N 个靶点
- 增加"靶点对比矩阵"节（成药性/市场/竞争/专利4维对比）

### 扩展 B：公司专项竞争情报
用法：`/target-intel KRAS Amgen`（锁定特定公司）
- 追加 `ls_organization_fetch` + `ls_organization_pipeline_fetch` + `ls_drug_deal_search(licensor/licensee=["Amgen"])` + `ls_financial_report_vector_search`
- 生成该公司在此靶点的完整资产地图

### 扩展 C：专利FTO深度模式
用法：`/target-intel ALK7 siRNA FTO`
- 增加按国家的专利法律状态分析（CN/US/EP/JP）
- 启用 `ls_patent_search(country=["CN"], legal_status=["active"])` + 到期日筛选
- 核酸模态追加 `ls_sequence_search_submit` + `ls_patent_sequence_fetch` 进行序列相似性 FTO
- 生成"可进入专利窗口"时间表

### 扩展 D：临床结果深度模式
用法：`/target-intel PD-1 临床数据`
- 针对每个 Phase 3 品种拉 `ls_clinical_trial_result_fetch`
- 追加 `ls_clinical_guideline_vector_search` × 各适应症
- 生成 ORR/PFS/OS 疗效对比表（类 meta-analysis 格式）

### 扩展 E：中国市场专项
用法：`/target-intel EGFR 中国`
- `ls_drug_search(country=["CN"])` + `ls_clinical_trial_search(country=["CN"])`
- `ls_patent_search(country=["CN"])` 中国专利状态
- 生成国产 vs 进口竞争格局、NMPA 审批时间线

### 扩展 F：交易估值模型
用法：`/target-intel PCSK9 BD`
- 拉取所有 deal + 按阶段/金额/类型分类
- 建立靶点历史交易价值曲线
- 基于同类靶点交易给出"当前立项的合理估值区间"
