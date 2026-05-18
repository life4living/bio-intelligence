# /disease-intel — 适应症全景情报分析

> 适用于任意疾病/适应症的全维度调研，以"这个适应症有哪些机会"为核心问题。
> 用法：`/disease-intel NSCLC`、`/disease-intel 特应性皮炎`、`/disease-intel 2型糖尿病 中国`
> 可选参数：疾病名后可跟"中国"（聚焦中国市场）或"早期"/"后线"（聚焦特定治疗线）。

---

## Pre-flight：MCP 连接检查（每次执行前必做）

**在 Step 0 之前**，用探针验证 `pharma_intelligence` MCP 工具是否可用：

```
ls_ner_nor_normalize(user_input="test")
```

根据结果判断：

| 结果 | 状态 | 处理 |
|------|------|------|
| 返回任意 JSON | ✅ 正常 | 继续 Step 0 |
| Connection refused / tool not found / MCP disconnected | ❌ 代理未运行 | 输出诊断（见下），**暂停执行**，等用户修复后重发指令 |
| HTTP 400 / schema validation error | ❌ 代理异常（未过滤 anyOf） | 输出诊断（见下），**暂停执行** |
| 超时（>60s 无响应） | ⚠️ 网络或服务器繁忙 | 提示用户，等 10s 后重试一次；二次仍超时则暂停 |

**连接失败时输出以下内容，不再继续执行任何 MCP 工具：**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌  MCP 连接失败 — 智慧芽工具不可用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
在终端（! 前缀可在 Claude Code 中直接运行）执行以下步骤：

  步骤 1 — 检查代理是否在运行：
  ! lsof -i :3099

  步骤 2 — 若无输出，启动代理：
  ! python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &

  步骤 3 — 在 Claude Code 中验证连接：
  /mcp   ← 确认 pharma_intelligence 显示 Connected

  步骤 4 — 验证通过后，重新发送本次调研指令。

常见原因速查：
  • 终端关闭 / 系统休眠       → 代理进程退出，执行步骤 2 重启
  • 端口 3099 已被占用        → ! lsof -ti :3099 | xargs kill，再重启
  • python3.10 路径不对       → ! which python3.10 确认，或用完整路径
  • 400 schema 错误（无代理） → 代理未正确配置，检查 /mcp 端点是否指向 127.0.0.1:3099

详细说明：bio-intelligence/KNOWN_ISSUES.md > MCP Error A / MCP Error D
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**执行中途 MCP 工具报错（单个工具失败）的处理：**
- 单次工具调用返回错误（非连接断开）→ 记录为"⚠ MCP数据暂缺"，改用 `ls_web_search` 补充，**不中断整体流程**
- 同一轮中 3 个以上工具连续失败 → 重新做一次 Pre-flight 探针，判断是否代理已断开
- 超时但其他工具正常 → 调整该工具 query，缩短结果数量后重试一次（`limit` 从 30→15）

---

## 数据可信度框架（Data Governance）

> 所有 skills 共用。确保报告中每条关键数据来源可溯、可信度透明、不确定信息显式声明。

### 来源分级（Source Tier）

| 等级 | 标记 | 来源类型 | 解释 |
|------|------|---------|------|
| **S** | 🟢 S | MCP `*_fetch`（带唯一 ID） | 数据库原始记录，ID 可复现验证 |
| **A** | 🟢 A | MCP `*_search`（结构化检索） | 经索引的结构化数据，ID 列表可追溯 |
| **B** | 🟡 B | MCP `*_vector_search`（语义检索） | 语义匹配，可能有上下文漂移；重要数值应用 fetch 交叉验证 |
| **W** | 🟡 W | `ls_web_search` 补充 | MCP 无数据时的公开网络信息 |
| **C** | 🔴 C | Claude 模型推断 / 综合分析 | 基于多源数据的判断，非实测数据；必须列出所依赖的具体数据点 |

### 核实验证规则（5条，强制执行）

**R1 — 数值型临床数据**（mPFS / OS / ORR / 批准日期）
- 来源必须为 S 或 A 级：`clinical_trial_result_fetch`、`drug_fetch.first_approved_date`、`drug_milestone_fetch`
- 行内标注格式：`数值 [S, ct_result_id: xxx]` 或 `数值 [A, drug_id: xxx]`
- 仅来自 vector_search 的临床数据：标注 `⚠ 待 fetch 验证` 并尽量补做 fetch

**R2 — 市场 / 流行病学数据**（市场规模、患者人数、发病率）
- 必须注明：数据机构（GlobalData / EvaluatePharma / 政府报告等）+ 预测年份 + 基准年
- 中国患者数如需推算，明确写出公式，例如：`全球 × 中国占比系数(~22%)` → 给出区间而非点估计
- 来自 Claude 训练知识的流行病学数据：标注 `[C, 知识截止 2025-08]`，并用 MCP 结果交叉核查

**R3 — BD 交易金额**
- 来源：`drug_deal_fetch.deal_value`；若 `disclosed=false` → 在报告中明确标注 `[金额未披露]`
- 禁止推测未披露交易金额

**R4 — 定性判断**（需求缺口评级、立项机会评分、KOL 认定、竞争强度）
- 必须标注 `[C]` + 列出所依赖的具体数据点（至少 2 个 S/A/B 级来源）
- KOL 认定：必须有 MCP paper/news 来源；若仅来自模型知识 → 标注 `[C, 未经 MCP 验证]`

**R5 — MCP 无数据时的处理链**
1. MCP 返回空 / 错误 → 记录为 `⚠ MCP无数据`
2. 调用 `ls_web_search`（1次）→ 有结果则标注 `[W, URL/来源]`
3. 仍无数据 → 在报告中**显式写明**：「此项数据 MCP 及公开网络均未覆盖，以下为模型推断 [C]」
4. 涉及重要决策的关键数据缺失时，在结论中明确说明该缺失对立项判断的影响

### 行内标注格式（分析 & 报告统一使用）

```
数值/结论 [等级, 来源ID或工具名]
```

示例：
- `mPFS 27.5mo [S, ct_result: 028e294...]` — fetch 获取的试验结果
- `全球新发 ~220万/年 [B, epidemiology_vector_search]` — 语义检索，有不确定性
- `市场规模 $783亿(2023) [W, GlobalData via ls_web_search]` — 网络补充
- `未满足需求：极高 [C, 依据: mPFS<3mo(S) + 无批准SOC(A)]` — 模型判断，依据显式列出

### HTML 报告中的数据透明度要求

1. **每个数据表格**：新增「可信度」列，用 🟢高 🟡中 🔴推断 标注
2. **页脚参考列表**：`[1] ls_clinical_trial_result_fetch, ID: xxx` 格式，按编号索引
3. **数据说明节（第 11 节，必含）**：
   - 数据来源统计（各等级条目数）
   - 关键数据点引用列表
   - 数据缺失清单（缺失原因 + 对结论的影响评估）
   - 推断方法说明
   - 数据截止日期：`currentDate`

---

## 执行流程

### Step 0：解析参数

从 `$ARGUMENTS` 中提取：
- **疾病名**（必填）：中英文均可，如 NSCLC、小细胞肺癌、atopic dermatitis
- **市场聚焦**（可选）：中国 / 全球 / US / EU
- **治疗线聚焦**（可选）：1L / 2L / 后线 / 全治疗线
- **疾病类型判断**：肿瘤 / 免疫炎症 / 代谢内分泌 / 神经系统 / 心血管 / 感染 / 罕见病

输出一行确认：
`📡 疾病：[疾病名] | 类型：[疾病类型] | 聚焦：[市场/治疗线] — 启动智慧芽MCP疾病调研...`

---

### Step 1：实体标准化（必须最先执行，单独调用）

```
ls_ner_nor_normalize(user_input="$ARGUMENTS")
```

从返回结果中获取：疾病标准化ID（ICD编码/MeSH ID）、别名列表、关联靶点列表、关联药物列表。
后续查询使用**标准化疾病名 + 主要靶点别名**双轨检索以确保查全率。

---

### Step 2：广度并行扫描（14个工具同时发出，不等待）

以下查询**全部并行**，一次性发出：

**疾病基础**
1. `ls_disease_fetch(disease=["<标准化疾病名>"])`
2. `ls_epidemiology_vector_search(query="<疾病名> incidence prevalence mortality patient population global China", lang="EN", top_k=15)`

**治疗靶点全景**
3. `ls_target_fetch(target=["<关联主要靶点1>"])`（取 Step 1 返回的前3个靶点并行各发一次）

**药物管线**
4. `ls_drug_search(disease=["<标准化疾病名>"], limit=50)`
5. `ls_drug_search(disease=["<标准化疾病名>"], highest_phase=["approved"], limit=30)`

**临床试验**
6. `ls_clinical_trial_search(disease=["<标准化疾病名>"], limit=40)`
7. `ls_clinical_trial_result_search(disease=["<标准化疾病名>"], limit=20)`

**专利**
8. `ls_patent_search(disease=["<标准化疾病名>"], patent_core_type=["product_compound","new_use"], limit=30)`

**交易与文献**
9. `ls_drug_deal_search(disease=["<标准化疾病名>"], limit=25)`
10. `ls_paper_search(disease=["<标准化疾病名>"], limit=15)`

**转化医学**
11. `ls_translational_medicine_search(disease=["<标准化疾病名>"], limit=10)`

**指南与市场**
12. `ls_clinical_guideline_vector_search(query="<疾病名> treatment guideline first-line standard of care NCCN ESMO", lang="EN", top_k=10)`
13. `ls_financial_report_vector_search(query="<疾病名> market size revenue forecast patient population commercial", lang="EN", top_k=8)`

**近期动态与里程碑**
14. `ls_news_vector_search(query="<疾病名> drug approval clinical trial deal breakthrough", lang="EN", top_k=10)`
15. `ls_drug_milestone_fetch(drug_id=["<Step 4-5中识别的主要在研药物ID>"])` — 关键药物里程碑时间线
16. `ls_organization_pipeline_fetch(organization=["<关联主要公司名>"])` — 公司全管线快照（补充 drug_search 覆盖）

---

### Step 3：深度向量挖掘（按疾病类型分支并行）

收到 Step 2 结果后，**同时**发起：

**通用深度搜索（每个疾病必做）**
```
ls_paper_vector_search(query="<疾病名> pathophysiology mechanism molecular biology driver mutation", lang="EN", top_k=12)
ls_paper_vector_search(query="<疾病名> unmet medical need treatment gap clinical outcome benchmark", lang="EN", top_k=10)
ls_clinical_trial_vector_search(query="<疾病名> phase 3 overall survival progression free response rate standard", lang="EN", top_k=12)
ls_fda_label_vector_search(query="<已上市标准治疗药物> indication efficacy safety dosage", lang="EN", top_k=8)
```

**生物标志物与患者分层**
```
ls_paper_vector_search(query="<疾病名> biomarker patient selection stratification companion diagnostic", lang="EN", top_k=10)
ls_translational_medicine_search(query="<疾病名> biomarker predictive prognostic diagnostic", limit=10)
```

**KOL 识别（每个疾病必做）**
```
ls_paper_vector_search(query="<疾病名> KOL academic institution leading researcher clinical investigator principal investigator", lang="EN", top_k=12)
ls_paper_fetch(paper_ids=[<Step2高引文献ID列表>])  — 获取关键文献全文，提取通讯作者/机构信息
ls_news_vector_search(query="<疾病名> conference ASCO AACR ESMO keynote speaker expert opinion", lang="EN", top_k=8)
```

**若为肿瘤，追加：**
```
ls_paper_vector_search(query="<癌种> molecular subtype genomic classification driver mutation frequency", lang="EN", top_k=10)
ls_paper_vector_search(query="<癌种> tumor microenvironment immune infiltration PD-L1 MSI TMB", lang="EN", top_k=8)
ls_clinical_trial_vector_search(query="<癌种> second line third line salvage therapy ORR OS benchmark", lang="EN", top_k=10)
```

**若为免疫炎症，追加：**
```
ls_paper_vector_search(query="<疾病名> cytokine pathway IL Jak STAT autoimmune mechanism", lang="EN", top_k=10)
ls_paper_vector_search(query="<疾病名> disease severity scoring EASI PASI DLQI patient reported outcome", lang="EN", top_k=8)
```

**若为神经系统，追加：**
```
ls_paper_vector_search(query="<疾病名> CNS blood brain barrier neurodegeneration mechanism biomarker", lang="EN", top_k=10)
ls_paper_vector_search(query="<疾病名> cognitive function ADAS-COG MMSE endpoint clinical trial design", lang="EN", top_k=8)
```

**若为代谢/内分泌，追加：**
```
ls_paper_vector_search(query="<疾病名> metabolic pathway insulin resistance HbA1c endpoint glucose", lang="EN", top_k=10)
ls_epidemiology_vector_search(query="<疾病名> obesity comorbidity cardiovascular renal outcome risk factor", lang="EN", top_k=8)
```

---

### Step 4：重点数据拉取（批量 fetch）

从 Step 2 和 Step 3 结果中：
- 取最重要的 **3-5 个靶点** → `ls_target_fetch(target=[...])`（验证每个靶点详情）
- 取最重要的 **5-8 件专利** → `ls_patent_fetch(patent_ids=[...])`
- 取最重要的 **3-5 篇文献** → `ls_paper_fetch(paper_ids=[...])`（兼作 KOL 通讯作者提取）
- 取最重要的 **3-5 个交易** → `ls_drug_deal_fetch(drug_deal_ids=[...])`
- 取关键临床试验 → `ls_clinical_trial_fetch(clinical_trial_ids=[...])`（Phase 3 优先）
- 取关键临床结果 → `ls_clinical_trial_result_fetch(result_ids=[...])`
- 取代表性药物 → `ls_drug_fetch(drug_ids=[...])`（各治疗线代表药物各1）
- 取关键药物里程碑 → `ls_drug_milestone_fetch(drug_id=[...])`（主要在研/近期获批品种）
- 取关键新闻全文 → `ls_news_fetch(news_ids=[...])`（Step 2 新闻搜索中的高相关条目）
- 若有关键机构 → `ls_organization_fetch(organization=[...])`

---

### Step 5：综合分析框架

#### 5.1 疾病生物学（📡 MCP: disease_fetch + paper + target_fetch）
- 定义与诊断标准（ICD编码/诊断 criteria）
- 发病机制（分子通路图谱）
- 疾病亚型分类（分子/病理/临床分型）
- 关键驱动靶点列表（已验证 + 新兴 + 假说中）：
  | 靶点 | 验证级别 | 已有药物 | 通路 | 可成药性 | **来源** |
  |------|---------|---------|------|---------|---------|
- 遗传学证据（GWAS / 孟德尔随机化 / 家族性突变）
- **数据标注要求**：每个靶点的验证级别需注明来源（`target_fetch` ID 或文献 paper_id）

#### 5.2 流行病学（📡 MCP: epidemiology + paper）
- 全球发病率 / 患病率 / 死亡率（年度数据，趋势）
- 中国流行病学数据（与全球对比）
- 人口特征（年龄/性别/地域分布）
- 疾病负担（DALY / 经济负担）
- 诊断率 / 治疗率 / 漏诊原因
- **数据标注要求**：
  - 每条流行病学数据必须标注来源 [B, epidemiology_vector_search] 或 [W, 机构名]
  - 中国数据若为推算，写明公式和来源；点估计必须附区间（如 `~85万（范围：80-95万）`）
  - MCP 无数据的项目显式标注 `⚠ MCP未覆盖，数据来源：[来源]`

#### 5.3 标准治疗（📡 MCP: guideline + fda_label + clinical_trial）
- 当前 SOC（按治疗线列表）：
  | 治疗线 | 方案 | 批准日期 | 关键数据 | 局限性 | **来源** |
  |--------|------|---------|---------|--------|---------|
- 主要指南推荐（NCCN / ESMO / 中国指南）
- 疗效基准线（各治疗线 ORR / PFS / OS 参考值）
- 获批生物标志物与检测要求
- **数据标注要求**：
  - 批准日期必须来自 `drug_fetch.first_approved_date` 或 `drug_milestone_fetch` [S]
  - 疗效数值必须来自 `clinical_trial_result_fetch` 或 `paper_fetch` [S]，并附 trial_id / paper_id
  - 若仅来自 vector_search，标注 `[B, ⚠ 建议 fetch 验证]`

#### 5.4 未满足临床需求（📡 MCP + 🧠 Claude）
- **治疗缺口分析矩阵**：
  | 患者亚群 | 当前最佳方案 | 主要局限 | 缺口评级 | **评级依据** |
  |---------|------------|---------|---------|------------|
- 缺口维度评估：
  - 疗效维度（ORR低/OS短/耐药快）
  - 安全性维度（毒性不可耐受/患者依从性差）
  - 便利性维度（给药方式/频次/监测需求）
  - 可及性维度（价格/供应链/诊断门槛）
- 对应靶点/机制机会
- **数据标注要求**：
  - 缺口评级属于 [C] 级判断，必须列出至少 2 个支撑数据点（需有 S/A/B 级来源）
  - 若关键缺口缺乏 MCP 数据支撑，说明其对结论可靠性的影响

#### 5.5 靶点机会图谱（📡 MCP: target_fetch + paper + drug_search）
- 已验证靶点（有批准药物）：管线拥挤度评估
- 临床期靶点（有临床数据但未批）：进入机会评估
- 新兴靶点（临床前/早期概念）：科学可信度评分
- 空白靶点（遗传学验证但无药物）：立项机会高亮
- **数据标注要求**：靶点详情来自 `target_fetch` [S]；药物数量来自 `drug_search` [A]；评估判断标注 [C]

#### 5.6 药物管线（📡 MCP: drug_search + clinical_trial + drug_milestone_fetch）
- 全管线按阶段 + 靶点 + 模态列表
- 模态分布统计（小分子/抗体/ADC/细胞治疗/基因治疗 各几个）
- **关键里程碑时间线**（来自 `drug_milestone_fetch` [S]）：主要在研品种 NDA/PDUFA/获批预期节点
- 中国管线专项：国产 vs 进口竞争格局
- 近12个月重要里程碑（批准/数据/停项）
- **数据标注要求**：每条里程碑需注明 drug_id；预期（未来）节点标注 `[C, 预测]` 并说明依据

#### 5.7 市场与商业（📡 MCP: financial + epidemiology + deal）
- 市场规模（当前 + 2030 预测，全球/中国）
- 主要上市药物销售峰值 / 当前年销售额
- 重要 BD 交易清单（按金额排序，近5年）
- 支付环境（医保准入/集采风险/商业保险渗透率）
- 中国 NMPA 审批时间线
- **数据标注要求**：
  - 市场规模必须标注数据机构 + 预测年 + CAGR；MCP 来自 `financial_report_vector_search` [B]；若无 MCP 数据则 [W]
  - BD 金额来自 `drug_deal_fetch.deal_value` [S]；未披露金额不得推测，写 `[金额未披露]`
  - 药物销售额如非来自 MCP，标注来源（公司财报 / EvaluatePharma）[W]

#### 5.8 专利格局（📡 MCP: patent_search + vector）
- 主要专利族群按靶点/机制分类
- 各靶点专利到期时间表
- 可进入专利空白区（技术/适应症/组合维度）
- **数据标注要求**：专利到期日来自 `patent_fetch` [S]；专利空白区分析属于 [C]，需列出参考专利族

#### 5.9 立项机会评估（🧠 Claude 综合判断）
- **机会矩阵**：各靶点/模态组合的机会评分（市场 × 竞争 × 技术难度）
- **Top 3 推荐立项方向**（每条含：靶点/模态/适应症/患者分层/差异化策略/资源需求）
- 主要风险（科学/临床/监管/商业）
- 近期关注窗口（12-24个月内重要数据读出）
- **数据标注要求**：
  - 整节属于 [C] 级综合判断，在节首声明
  - 每条推荐列出 3 个以上支撑数据点（含来源等级）
  - 若存在无法验证的假设，在「主要风险」中显式列出

#### 5.10 KOL 与学术生态（📡 MCP: paper_vector_search + paper_fetch + news_vector_search）
- **领域 Top KOL 表**（来自 paper_vector_search KOL 查询 + paper_fetch 通讯作者提取）：
  | 姓名 | 机构 | 研究方向 | 代表文献 | 产业合作记录 | **来源** |
  |------|------|---------|---------|------------|---------|
- **奠基性文献 Top 5**（来自 paper_fetch 全文，高引用量核心文献）
- **学术-产业合作格局**（来自 paper_vector_search 语义检索）：
  - 哪些学术机构与药企有活跃合作 → 潜在 License-in 来源
  - 中国高校/研究所的早期技术转化动态
- **数据标注要求**：
  - KOL 姓名必须来自 `paper_fetch` 通讯作者字段 [S] 或 `news_fetch` [A]；纯模型知识来源标注 `[C, 未经MCP验证]`
  - 文献引用必须附 paper_id 或 DOI

---

### Step 6：生成交互式 HTML 报告

保存至：`/Users/nihil/Claude/{疾病名拼音或英文}_disease_intel_report.html`

**⚠ 日期要求：使用系统注入的 `currentDate`，文件内所有年份统一核查。**

**⚠ 数据透明度要求（新增，强制）：**
- 数据表格必须增加「可信度」列，用 🟢 S/A、🟡 B/W、🔴 C 标注每行数据的来源等级
- 关键数值旁附上标引用编号 `[n]`，报告末尾对应参考列表
- 不确定 / 推断数据用斜体 + `（推断）` 或 `（估算，±X%）` 标注
- 若某数据无 MCP 来源，在数值后标注 `⚠`，悬停提示说明

#### HTML 设计规范

**主色调按疾病类型**
- 肿瘤：`#f85149`（红）
- 免疫/炎症：`#3fb950`（绿）
- 神经系统：`#bc8cff`（紫）
- 代谢/内分泌：`#f0883e`（橙）
- 心血管：`#58a6ff`（蓝）
- 罕见病：`#d29922`（金）

**导航节点**（必含）
1. 疾病概览
2. 流行病学
3. 标准治疗
4. 未满足需求
5. 靶点图谱
6. 药物管线
7. 市场商业
8. 专利格局
9. 立项机会
10. KOL 生态
11. **数据说明**（新增必含节）

**交互功能**
- 靶点机会表格：可按验证级别/可成药性/管线拥挤度筛选排序
- 药物管线：按靶点/模态/阶段/公司多维筛选
- 未满足需求：患者亚群 Tab 切换，每个亚群独立缺口分析
- 治疗地图：可折叠的治疗线树状图

**图表（Chart.js CDN）**
- 流行病学趋势：折线图（历史 + 预测）
- 全球 vs 中国患病人数：双轴条形图
- 靶点机会矩阵：气泡图（x=可成药性，y=市场机会，size=管线拥挤度）
- 管线阶段分布：甜甜圈图（按靶点分色）
- BD 交易时间轴：瀑布图
- 市场规模预测：面积图
- 立项机会雷达图（每个推荐方向一个独立雷达）

**专项可视化**
- 治疗地图（Treatment Landscape）：svg 流程图，各治疗线 → 药物 → 疗效数据节点
- 未满足需求热力图：患者亚群 × 缺口维度矩阵（颜色编码缺口严重程度）
- 靶点-通路关系图：关键信号通路节点，标注已有药物 vs 空白位置

**第 11 节：数据说明（Data Notes）— 强制包含**

此节放在报告最后，包含：

1. **数据来源统计**
   | 来源等级 | 条目数 | 说明 |
   |---------|--------|------|
   | 🟢 S（fetch直接记录） | n | drug_id / trial_id / patent_id 等 |
   | 🟢 A（结构化搜索） | n | drug_search / patent_search 等 |
   | 🟡 B（语义搜索） | n | *_vector_search |
   | 🟡 W（网络补充） | n | ls_web_search |
   | 🔴 C（模型推断） | n | 综合判断、评分、预测 |

2. **关键数据引用列表**（带编号）
   ```
   [1] ls_clinical_trial_result_fetch, ID: xxx — mPFS 27.5mo (ALK+, Dirozalkib vs CRZ)
   [2] ls_drug_fetch, drug_id: xxx — 批准日期 2025-05-14 (Telisotuzumab vedotin)
   [3] ls_financial_report_vector_search — 市场规模 $783亿(2023), 来源: GlobalData
   ...
   ```

3. **数据缺失声明**
   - 列出未能从 MCP 获取的关键数据项
   - 说明缺失原因（MCP未收录 / 工具超时 / 数据未披露）
   - 评估该缺失对报告核心结论的影响（高/中/低影响）

4. **推断方法说明**
   - 患者数量推算公式
   - 市场规模外推方法
   - 立项机会评分权重

5. **数据时效性**
   - 报告数据截止日期：`currentDate`
   - 注明哪些领域数据更新较快（如 BD 交易、里程碑），建议定期复核

---

### Step 7：输出摘要

```
✅ 疾病情报报告生成完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
疾病：[名称] | 类型：[肿瘤/免疫/代谢/神经/心血管] | 聚焦：[全球/中国/治疗线]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP 数据覆盖：
  患者规模    [X]万/年（全球）| [X]万/年（中国）
  关联靶点    n=[X]（已验证 [X] | 临床期 [X] | 新兴 [X]）
  药物管线    n=[X]（已批 [X] | Ph3 [X] | Ph2 [X] | Ph1 [X]）
  临床试验    n=[X]（结果数 [X]）
  BD 交易     n=[X]（最大金额 [X]M）
  专利        n=[X]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据可信度统计：
  🟢 S/A（数据库直接记录）  n=[X] 条
  🟡 B/W（搜索/网络补充）   n=[X] 条
  🔴 C（模型推断/综合）     n=[X] 条
  ⚠ 数据缺失项             n=[X] 条（详见报告第11节）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
核心发现：
• [最大未满足临床需求] — 来源：[S/A/B/C]
• [最具潜力的靶点/机制空白] — 来源：[S/A/B/C]
• [最值得关注的近期数据读出] — 来源：[S/A/B/C]

Top 立项机会（均为 🔴 C 级综合判断，依据数据已在报告第9节列出）：
1. [靶点/模态] → [患者分层] — [核心差异化]
2. [靶点/模态] → [患者分层] — [核心差异化]
3. [靶点/模态] → [患者分层] — [核心差异化]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
报告路径：/Users/nihil/Claude/[filename].html
数据说明：报告第11节（含缺失清单 + 引用列表 + 推断方法）
```

---

## 工具使用速查

| 阶段 | 工具 | 用途 |
|------|------|------|
| Step 1 | `ls_ner_nor_normalize` | 疾病实体标准化，获取 ICD/MeSH ID + 关联靶点 |
| Step 2 | `ls_disease_fetch` | 疾病详情、诊断标准、分型 |
| Step 2 | `ls_epidemiology_vector_search` | 全球/中国流行病学数据 |
| Step 2 | `ls_target_fetch` × 多个 | 关联靶点详情 |
| Step 2 | `ls_drug_search` × 2 | 全管线 + 仅已批准 |
| Step 2 | `ls_clinical_trial_search` | 注册试验列表 |
| Step 2 | `ls_clinical_trial_result_search` | 已发表试验结果 |
| Step 2 | `ls_patent_search` | 专利结构化检索 |
| Step 2 | `ls_drug_deal_search` | BD 交易列表 |
| Step 2 | `ls_paper_search` | 学术文献 |
| Step 2 | `ls_translational_medicine_search` | 生物标志物/转化研究 |
| Step 2 | `ls_clinical_guideline_vector_search` | 治疗指南/SOC |
| Step 2 | `ls_financial_report_vector_search` | 市场规模/财报 |
| Step 2 | `ls_news_vector_search` | 近期动态 |
| Step 2 | `ls_drug_milestone_fetch` | 关键药物里程碑时间线 |
| Step 2 | `ls_organization_pipeline_fetch` | 公司全管线快照 |
| Step 3 | `ls_paper_vector_search` | 机制/UMN/亚型/生物标志物/KOL深挖 |
| Step 3 | `ls_clinical_trial_vector_search` | 疗效基准/临床终点语义检索 |
| Step 3 | `ls_fda_label_vector_search` | SOC 药物说明书 |
| Step 3 | `ls_translational_medicine_search` | 生物标志物深挖 |
| Step 4 | `ls_target_fetch` | 靶点详情验证 |
| Step 4 | `ls_drug_fetch` | 各线代表药物详情 |
| Step 4 | `ls_clinical_trial_fetch` | 关键试验详情 |
| Step 4 | `ls_clinical_trial_result_fetch` | Ph3 结果详情 |
| Step 4 | `ls_drug_deal_fetch` | 交易详情 |
| Step 4 | `ls_patent_fetch` | 专利全文 |
| Step 4 | `ls_paper_fetch` | 文献全文（兼作 KOL 通讯作者提取） |
| Step 4 | `ls_drug_milestone_fetch` | 主要在研品种里程碑 |
| Step 4 | `ls_news_fetch` | 关键新闻全文详情 |
| 补充 | `ls_web_search` | MCP 无结果时补充 |

---

## 容错规则

1. **疾病未标准化**：用原始疾病名继续，加别名（英文/中文/ICD编码）并行检索
2. **关联靶点过多（>10个）**：优先取 Step 2 `ls_disease_fetch` 返回的核心靶点列表，其余聚合统计
3. **管线过多（>100个）**：按靶点分组，每组展示已批 + Ph3 + 模态最新品种
4. **指南信息缺失**：改用 `ls_paper_vector_search` 检索 review 文章重建 SOC，标注 `[B, 基于文献重建，非官方指南]`
5. **中国数据匮乏**：标注 `⚠ MCP中国数据有限`，从全球数据 + 中国系数推算，注明方法和区间，来源标注 `[C, 推算]`
6. **KOL 信息不全**：优先从 paper_fetch 通讯作者字段提取 [S]；缺失时从 news_vector_search 补充 [B]；若均无则在报告中声明 `⚠ KOL数据不足，以下为模型知识 [C, 未经MCP验证]`
7. **关键数据仅有 B/W 级来源**：在报告表格该行加 `⚠ 待验证` badge，并在第11节数据说明中列出，说明为何未做 fetch 验证
8. **市场预测数据无 MCP 来源**：使用 `ls_web_search` 查询知名机构报告（GlobalData/EvaluatePharma/Frost&Sullivan），标注 `[W, 机构名, 年份]`；若仍无数据则在报告中明确声明市场数据不可用
