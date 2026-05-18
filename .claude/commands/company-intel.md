# /company-intel — 制药公司全维度情报分析

> 适用于任何生物医药公司的深度尽调，涵盖管线、研发平台、临床进展、融资、BD交易、专利布局。
> 用法：`/company-intel Amgen`、`/company-intel 恒瑞医药`、`/company-intel Alnylam 小核酸`
> 可选参数：公司名后可跟模态关键词（聚焦特定技术平台）或"融资"（聚焦投融资分析）。

📎 **公共模块**：执行前 Read `/Users/nihil/Claude/bio-intelligence/.claude/commands/_shared.md`，加载 Pre-flight 检查、数据治理框架和 HTML 规范。

---

## 执行流程

### Step 0：解析参数

从 `$ARGUMENTS` 中提取：
- **公司名**（必填）：中英文均可，如 Amgen、恒瑞、BioNTech、药明生物
- **聚焦维度**（可选）：管线 / 融资 / BD / 平台 / 临床 / 专利
- **公司类型判断**：大型跨国药企（MNC）/ 中型Biotech / 早期Startup / CDMO/CRO / 中国本土药企

输出一行确认：
`📡 公司：[公司名] | 类型：[公司类型] | 聚焦：[维度或"全维度"] — 启动智慧芽MCP公司情报调研...`

---

### Step 1：实体标准化（必须最先执行，单独调用）

```
ls_ner_nor_normalize(user_input="$ARGUMENTS")
```

从返回结果中获取：公司标准化ID、英文/中文名称、股票代码、总部位置、相关药物列表、相关靶点列表。
后续所有 MCP 查询**使用标准化公司名**（英文全称）以确保查全率。

---

### Step 2：广度并行扫描（12个工具同时发出，不等待）

以下查询**全部并行**，一次性发出：

**公司基础**
1. `ls_organization_fetch(organization=["<标准化公司名>"])`
2. `ls_organization_pipeline_fetch(organization=["<标准化公司名>"])` — 公司全管线快照（结构化汇总）

**研发管线**
3. `ls_drug_search(company=["<标准化公司名>"], limit=50)`
4. `ls_drug_search(company=["<标准化公司名>"], highest_phase=["approved"], limit=20)`

**临床试验**
5. `ls_clinical_trial_search(company=["<标准化公司名>"], limit=40)`
6. `ls_clinical_trial_result_search(company=["<标准化公司名>"], limit=20)`

**专利布局（双轨检索）**
7. `ls_patent_search(company=["<标准化公司名>"], limit=30)`
8. `patsnap_search(search_strategy=["filter"], filters={"assignees": ["<标准化公司名>"]}, sources=["patent"], topk=30)` ← patsap_patent_search，专利全量补充

**BD 交易**
8. `ls_drug_deal_search(licensor=["<标准化公司名>"], limit=20)`
9. `ls_drug_deal_search(licensee=["<标准化公司名>"], limit=20)`

**文献与动态**
10. `ls_paper_search(company=["<标准化公司名>"], limit=10)`
11. `ls_news_vector_search(query="<公司名> pipeline drug approval deal financing partnership", lang="EN", top_k=15)`

**财务与市场**
12. `ls_financial_report_vector_search(query="<公司名> revenue earnings pipeline milestone guidance outlook", lang="EN", top_k=10)`
13. `ls_financial_report_vector_search(query="<公司名> financing funding round IPO valuation investor", lang="EN", top_k=10)`

---

### Step 3：深度向量挖掘（按公司类型分支并行）

收到 Step 2 结果后，**同时**发起：

**通用深度搜索（每个公司必做）**
```
ls_paper_vector_search(query="<公司名> platform technology innovation proprietary discovery", lang="EN", top_k=10)
ls_patent_vector_search(query="<公司名> core technology platform invention novel approach", lang="EN", top_k=15)
ls_clinical_trial_vector_search(query="<公司名> phase 2 3 efficacy safety primary endpoint result", lang="EN", top_k=12)
ls_news_vector_search(query="<公司名> FDA approval regulatory milestone NMPA NDA BLA", lang="EN", top_k=10)
```

**融资与估值（Biotech/Startup 重点）**
```
ls_financial_report_vector_search(query="<公司名> series A B C IPO SPAC venture capital raise fund", lang="EN", top_k=10)
ls_news_vector_search(query="<公司名> fundraising investment valuation investor lead", lang="EN", top_k=10)
```

**BD 交易深挖（全公司必做）**
```
ls_drug_deal_search(licensor=["<公司名>"], limit=30)
ls_drug_deal_search(licensee=["<公司名>"], limit=30)
ls_news_vector_search(query="<公司名> licensing acquisition partnership collaboration milestone payment", lang="EN", top_k=10)
```

**技术平台专项（若有明确平台）**
```
ls_patent_vector_search(query="<公司技术平台名> delivery mechanism formulation conjugation", lang="EN", top_k=15)
ls_paper_vector_search(query="<公司技术平台名> efficacy preclinical clinical validation", lang="EN", top_k=10)
```

**学术合作网络（每个公司必做）**
```
ls_paper_vector_search(query="<公司名> academic institution collaboration university technology transfer license research agreement", lang="EN", top_k=12)
ls_paper_fetch(paper_ids=[<Step2文献ID列表>])  — 提取共同作者机构、公司科学家/顾问网络
```

**若为中国本土药企，追加：**
```
ls_drug_search(company=["<公司名>"], country=["CN"], limit=30)
ls_clinical_trial_search(company=["<公司名>"], country=["CN"], limit=30)
ls_patent_search(company=["<公司名>"], country=["CN"], limit=20)
ls_news_vector_search(query="<公司名> NMPA CDE 国谈 医保 集采", lang="CN", top_k=10)
```

**若为 MNC，追加：**
```
ls_financial_report_vector_search(query="<公司名> annual report revenue guidance pipeline value", lang="EN", top_k=10)
ls_drug_deal_search(licensor=["<公司名>"], limit=40)
ls_news_vector_search(query="<公司名> acquisition M&A buyout strategic collaboration", lang="EN", top_k=10)
```

---

### Step 4：重点数据拉取（批量 fetch）

- 取最重要的 **5-10 件专利** → `ls_patent_fetch(patent_ids=[...])`（优先核心平台专利）
- 取 **3-5 个关键交易** → `ls_drug_deal_fetch(drug_deal_ids=[...])`（金额最大/最新）
- 取 **3-5 篇核心文献** → `ls_paper_fetch(paper_ids=[...])`（平台验证/临床数据；兼作公司科学家网络提取）
- 取关键临床试验 → `ls_clinical_trial_fetch(clinical_trial_ids=[...])`（Ph3/注册性研究）
- 取关键临床结果 → `ls_clinical_trial_result_fetch(result_ids=[...])`（已发表 Ph3 结果）
- 取各阶段代表药物 → `ls_drug_fetch(drug_ids=[...])`（每个主要管线品种各1）
- 取关键药物里程碑 → `ls_drug_milestone_fetch(drug_id=[...])`（主要管线品种 IND/NDA/获批时间线）
- 取关键新闻全文 → `ls_news_fetch(news_ids=[...])`（Step 2-3 新闻搜索中的高相关条目）
- 取合作公司信息 → `ls_organization_fetch(organization=[...])`（主要合作方/竞争对手）

---

### Step 5：综合分析框架

#### 5.1 公司概览（📡 MCP: organization_fetch + news）
- 公司全名、股票代码（交易所）、成立年份、总部城市
- 员工规模、市值（当前）/ 估值（未上市）
- 核心业务定位（疾病领域/模态/产业链环节）
- 创始人/核心管理层背景
- 历史沿革：重要里程碑时间线（成立→A轮→B轮→IPO→首个批准→重要交易）
- 与主要竞争对手的定位对比（一句话差异化）

#### 5.2 融资历史（📡 MCP: financial + news）
- **融资时间线表格**：
  | 轮次 | 时间 | 金额 | 投资方 | 估值 | 用途 |
  |------|------|------|--------|------|------|
- 融资总额 / 烧钱率估算 / 现金跑道（如可获得）
- 主要机构投资方背景分析（VC/战略投资/主权基金）
- IPO 信息（时间/募资额/发行价/当前股价涨跌幅）
- 近12个月资本动态

#### 5.3 研发管线（📡 MCP: drug_search + organization_pipeline_fetch + clinical_trial + drug_milestone_fetch）
- **全管线一览表**（可筛选/排序）：
  | 药物名称 | 靶点 | 模态 | 适应症 | 阶段 | 预期里程碑 | 合作方 |
  |---------|------|------|--------|------|-----------|--------|
- 管线阶段分布统计（已批/Ph3/Ph2/Ph1/临床前）
- 模态分布统计（各模态品种数）
- **关键里程碑时间线**（来自 drug_milestone_fetch）：各主要品种 IND→NDA→获批 时间节点
- **战略重点适应症**：投入资源最多的3-5个适应症分析
- **管线风险评估**：依赖度分析（核心品种占预期收入/价值比例）

#### 5.4 技术平台（📡 MCP: patent + paper + 🧠 Claude）
- **核心专有技术平台清单**：
  | 平台名称 | 技术类型 | 临床验证状态 | 专利保护情况 | 竞争对手类似技术 |
  |---------|---------|------------|------------|----------------|
- 各平台的科学基础与差异化优势
- 专利护城河深度评估（广度/深度/到期时间）
  - 通过 `ls_patent_search` + `ls_patent_vector_search` + `ls_patent_fetch` 多维检索识别核心 IP（重点：申请人+技术关键词+引用量组合，区分真正核心专利 vs 外围专利堆砌）
- 技术来源：内部发现 / 学术许可 / 收购获得
- **学术合作网络**（📡 MCP: paper_vector_search + paper_fetch）：主要合作高校/科研机构 + 合作方向 + 已转化技术数量（来自 paper 通讯作者机构提取）
- 平台局限性与技术风险

#### 5.5 临床进展（📡 MCP: clinical_trial + result）
- **关键临床试验清单**（Ph2+）：
  | 药物 | 研究名 | 阶段 | 适应症 | 入组数 | 主要终点 | 状态 | 预期数据 |
  |------|--------|------|--------|--------|---------|------|---------|
- **已发布关键数据**：ORR/PFS/OS等核心疗效指标
- **安全性信号**：各品种 Grade 3+ AE，黑框警告，停药率
- 与竞争品种的头对头（或间接）疗效比较
- 近12个月临床数据读出 + 未来12-24个月预期催化剂

#### 5.6 BD 交易（📡 MCP: deal_search + deal_fetch）
- **许可/授权出（License-out）清单**：
  | 资产 | 受让方 | 时间 | 首付款 | 总金额 | 权益范围 | 信号解读 |
  |------|--------|------|--------|--------|---------|---------|
- **引进/授权入（License-in/Acquisition）清单**：
  | 资产/公司 | 来源方 | 时间 | 金额 | 战略意图 |
  |----------|--------|------|------|---------|
- BD 策略分析：对外授权模式 / 引进偏好 / 地域策略（全球/亚太/中国）
- 交易估值水平：与行业基准对比（首付比例/总金额/里程碑设置）
- 潜在合作机会分析（当前管线中适合BD的资产）

#### 5.7 专利布局（📡 MCP: patent_search + patent_vector_search + patent_fetch）
- **核心专利识别**：通过 `ls_patent_search`（申请人精确检索）+ `ls_patent_vector_search`（技术关键词语义搜索）+ `ls_patent_fetch`（全文验证）三层检索，识别技术影响力最高的核心 IP，区分"真正无法绕过的核心专利"与"数量补充型外围专利"
- **专利组合概览**：按技术方向分类，数量/时间分布
- **核心专利族**（5-10件）：专利号/保护范围/到期时间
- **产学研联合专利**（来自 paper_vector_search 学术合作检索）：判断技术来源的学术依赖度
- 专利布局策略：化合物专利 / 工艺专利 / 用途专利 / 组合专利
- 知识产权风险：专利悬崖时间表 / 仿制药/生物类似药进入威胁
- 专利空白与补强建议

#### 5.8 竞争定位（📡 MCP + 🧠 Claude）
- **竞争格局图**：主要竞争对手对比表（管线/平台/资本/商业化能力）
- 核心竞争优势（技术壁垒/先发优势/商业网络/资本实力）
- 主要竞争劣势/短板
- 差异化定位分析

#### 5.9 投资/合作评估（🧠 Claude 综合判断）
- **综合评分**（0-10分）：管线质量/平台价值/商业化能力/财务健康度/管理团队 5维雷达
- 投资亮点（最多5条）
- 主要风险（最多5条）
- **潜在合作场景**（若为寻找合作/授权）：最适合合作的资产/领域/合作结构建议
- 估值参考区间（基于可比公司/交易/DCF分析）
- 12-24个月关键观察指标

---

### Step 6：生成交互式 HTML 报告

保存至：`/Users/nihil/Claude/{公司名小写英文}_company_intel_report.html`

**⚠ 日期要求：使用系统注入的 `currentDate`，文件内所有年份统一核查。**

#### HTML 设计规范

**主色调按公司类型**
- MNC（大型跨国药企）：`#58a6ff`（蓝）
- 中型Biotech：`#bc8cff`（紫）
- 早期Startup：`#3fb950`（绿）
- CDMO/CRO：`#f0883e`（橙）
- 中国本土：`#d29922`（金）

**导航节点**（必含）
1. 公司概览
2. 融资历史
3. 研发管线
4. 技术平台
5. 临床进展
6. BD 交易
7. 专利布局
8. 竞争定位
9. 投资评估

**交互功能**
- 管线表格：按阶段/靶点/模态/适应症多维筛选 + 排序
- BD 交易：许可出 / 引进入 Tab 切换，金额气泡大小编码
- 融资时间线：可缩放的交互时间轴（含各轮估值）
- 竞争对手对比：可勾选对手进行多公司雷达图叠加

**图表（Chart.js CDN）**
- 管线阶段分布：甜甜圈图（按适应症分色）
- 模态分布：横向条形图
- 融资历史：堆叠条形图（各轮金额，时间轴）
- BD 交易金额趋势：折线图（近5年，许可出 vs 引进入分开）
- 5维综合评估雷达图
- 竞争对手管线数量对比：分组条形图
- 专利申请趋势：折线图（近10年）
- 临床催化剂时间轴：Gantt 图风格（各品种预期数据读出）

**专项可视化**
- 管线热力图：适应症 × 阶段矩阵，填充颜色=模态
- 融资轮次估值曲线：面积图（含行业均值参照线）
- BD 交易地图：许可出（向右箭头）/ 引进入（向左箭头）可视化
- 竞争定位四象限图：平台广度 × 管线深度（各竞争对手标注）

---

### Step 7：输出摘要

```
✅ 公司情报报告生成完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
公司：[全称] | 类型：[MNC/Biotech/Startup] | 股票：[代码/交易所]
总部：[城市] | 成立：[年份] | 市值/估值：[$XB]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCP 数据覆盖：
  研发管线    n=[X]（已批 [X] | Ph3 [X] | Ph2 [X] | Ph1 [X]）
  临床试验    n=[X]（结果数 [X]）
  BD 交易     n=[X]（许可出 [X] | 引进入/收购 [X]，最大金额 $[X]M）
  专利        n=[X]（核心平台专利 [X]）
  融资轮次    n=[X]（融资总额 $[X]M）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据可信度统计：
  🟢 S/A（数据库直接记录）  n=[X] 条
  🟡 B/W（搜索/网络补充）   n=[X] 条
  🔴 C（模型推断/综合）     n=[X] 条
  ⚠ 数据缺失项             n=[X] 条（详见报告数据说明节）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
核心发现：
• [管线/平台核心价值判断] — 来源：[S/A/B/C]
• [最重要的BD交易或融资信号] — 来源：[S/A/B/C]
• [主要风险或催化剂] — 来源：[S/A/B/C]

综合评分：[X]/10 🔴 C（综合推断）
合作/投资建议：[强烈推荐 / 推荐 / 谨慎 / 不推荐]
理由：[一句话核心判断，标注关键依据数据来源]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12-24个月关键催化剂：
• [时间] [事件]（[影响评估]）— 来源：[S/A/B/C]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
报告路径：/Users/nihil/Claude/[filename].html
数据说明：报告末尾数据说明节（含缺失清单 + 引用列表 + 推断方法）
```

---

## 工具使用速查

| 阶段 | 工具 | 用途 |
|------|------|------|
| Step 1 | `ls_ner_nor_normalize` | 公司实体标准化，获取正式英文名/ID |
| Step 2 | `ls_organization_fetch` | 公司基础信息、规模、融资 |
| Step 2 | `ls_organization_pipeline_fetch` | 公司全管线结构化快照 |
| Step 2 | `ls_drug_search` × 2 | 全管线 + 仅已批准 |
| Step 2 | `ls_clinical_trial_search` | 注册试验列表 |
| Step 2 | `ls_clinical_trial_result_search` | 已发表试验结果 |
| Step 2 | `ls_patent_search` | 专利布局 |
| Step 2 | `ls_drug_deal_search` × 2 | 许可出 + 引进入双向检索 |
| Step 2 | `ls_paper_search` | 技术平台文献 |
| Step 2 | `ls_news_vector_search` × 多次 | 融资/审批/BD动态 |
| Step 2 | `ls_financial_report_vector_search` × 2 | 财务/管线价值 + 融资轮次 |
| Step 3 | `ls_patent_vector_search` | 平台技术专利深挖 |
| Step 3 | `ls_paper_vector_search` | 平台验证文献 + 学术合作网络 |
| Step 3 | `ls_clinical_trial_vector_search` | 关键临床结果语义检索 |
| Step 3 | `ls_drug_deal_search` × 扩展 | 更完整的 BD 记录 |
| Step 4 | `ls_patent_fetch` | 核心专利全文 |
| Step 4 | `ls_drug_deal_fetch` | 关键交易详情 |
| Step 4 | `ls_paper_fetch` | 技术平台文献全文（兼作学术合作机构提取） |
| Step 4 | `ls_clinical_trial_fetch` | 关键试验详情 |
| Step 4 | `ls_clinical_trial_result_fetch` | Ph3 结果详情 |
| Step 4 | `ls_drug_fetch` | 各管线品种详情 |
| Step 4 | `ls_drug_milestone_fetch` | 主要管线品种里程碑时间线 |
| Step 4 | `ls_news_fetch` | 关键新闻全文详情 |
| Step 4 | `ls_organization_fetch` | 主要合作方/竞争对手信息 |
| 补充 | `ls_web_search` | MCP 无结果时补充 |

---

## 容错规则

1. **公司未标准化**：用原始名称 + 英文/中文双语并行检索，报告标注 `⚠ 实体名称未标准化`
2. **早期公司信息匮乏**：Startup MCP 数据稀少时大幅使用 `ls_web_search` + Claude 知识，报告节首显示 `🟡 W / 🔴 C 来源为主，可信度有限`
3. **管线过多（>30个）**：按适应症分组，每组展示已批 + Ph3，其余汇总统计
4. **专利过多（>50件）**：按技术方向聚合，每方向取最核心1-2件 fetch
5. **融资信息缺失**：从新闻推断，标注 `[W/C, 基于公开信息估算]`；禁止写未披露金额的精确数字
6. **BD 交易金额未披露**：标注 `[金额未披露]`，绝不推测金额；可说明「参照同类交易区间 $X-Y M」并标注 `[C, 类比推断]`
7. **学术合作网络不全**：优先 paper_fetch 通讯作者 [S]；缺失时 news_vector_search [B]；均无则声明 `⚠ 学术合作数据不足 [C]`
8. **关键数据仅 B/W 级来源**：在报告表格加 `⚠ 待验证` badge，在数据说明节列出未做 fetch 验证的原因
