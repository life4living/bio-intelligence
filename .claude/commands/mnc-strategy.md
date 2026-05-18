# /mnc-strategy — MNC 战略资产需求分析

> 从 MNC 已上市产品出发，逆向推断其 BD/M&A 的资产需求逻辑。
> 核心问题：**这家公司最想买什么？为什么？愿意付多少？**
> 用法：`/mnc-strategy Amgen`、`/mnc-strategy 罗氏`、`/mnc-strategy AstraZeneca 肿瘤`
> 可选参数：公司名后可跟治疗领域（聚焦单一领域的 BD 逻辑分析）。

📎 **公共模块**：执行前 Read `/Users/nihil/Claude/bio-intelligence/.claude/commands/_shared.md`，加载 Pre-flight 检查、数据治理框架和 HTML 规范。

---

## 执行流程

### Step 0：解析参数

从 `$ARGUMENTS` 中提取：
- **MNC 名称**（必填）
- **领域聚焦**（可选）：肿瘤 / 心血管代谢 / 免疫炎症 / 神经系统 / 罕见病

输出一行确认：
`📡 MNC：[公司名] | 领域：[聚焦领域或"全领域"] — 启动战略资产需求分析...`

---

### Step 1：实体标准化（必须最先执行，单独调用）

```
ls_ner_nor_normalize(user_input="$ARGUMENTS")
```

获取标准化公司名、股票代码、总部、关联药物/靶点列表。

---

### Step 2：广度并行扫描（15个工具同时发出，不等待）

**公司与上市产品**
1. `ls_organization_fetch(organization=["<公司名>"])`
2. `ls_organization_pipeline_fetch(organization=["<公司名>"])` — 公司全管线结构化快照
3. `ls_drug_search(company=["<公司名>"], highest_phase=["approved"], limit=50)`

> ⚠ `ls_drug_fetch` 需要已批准药物的 drug_id，**已移至 Step 3**，在收到 Step 2 的 drug_id 后并行执行。

**专利（双轨检索）**
4. `ls_patent_search(company=["<公司名>"], patent_core_type=["product_compound"], limit=40)`
5. `ls_patent_search(company=["<公司名>"], patent_core_type=["new_use"], limit=20)`
6. `patsnap_search(search_strategy=["filter"], filters={"assignees": ["<公司名>"]}, sources=["patent"], topk=30)` ← patsap_patent_search，专利补充

**BD 交易（双向）**
7. `ls_drug_deal_search(licensor=["<公司名>"], limit=30)`
8. `ls_drug_deal_search(licensee=["<公司名>"], limit=40)`

**临床管线**
9. `ls_drug_search(company=["<公司名>"], limit=60)`（含在研品种）
10. `ls_clinical_trial_search(company=["<公司名>"], limit=40)`

**财务与市场**
11. `ls_financial_report_vector_search(query="<公司名> top products revenue sales blockbuster annual report", lang="EN", top_k=15)`
12. `ls_financial_report_vector_search(query="<公司名> patent expiry loss exclusivity LOE revenue impact guidance", lang="EN", top_k=10)`

**BD 动态与战略**
13. `ls_news_vector_search(query="<公司名> acquisition licensing deal strategy pipeline gap", lang="EN", top_k=15)`
14. `ls_news_vector_search(query="<公司名> patent cliff biosimilar competition revenue risk", lang="EN", top_k=10)`

**竞品与疗效基准**
15. `ls_clinical_trial_result_search(company=["<公司名>"], limit=20)`
16. `ls_drug_milestone_fetch(drug_id=["<Top产品药物ID>"])` — 上市产品专利到期/LOE 里程碑时间线

---

### Step 3：深度向量挖掘（并行发出）

**已批准药物详情（从 Step 2 移至此处）**
```
ls_drug_fetch(drug_ids=[<Step2 drug_search 返回的全部已批准药物ID>])  — 分批并行，获取销售额/适应症/靶点/PK信息
```

**Top 产品机制与耐药**
```
ls_paper_vector_search(query="<Top产品1> mechanism resistance combination synergy", lang="EN", top_k=10)
ls_paper_vector_search(query="<Top产品2> mechanism resistance combination synergy", lang="EN", top_k=10)
ls_paper_vector_search(query="<Top产品3> mechanism resistance combination synergy", lang="EN", top_k=10)
（对销售额前5产品各发一次，并行）
```

**BD 历史深挖**
```
ls_drug_deal_fetch — 取 Step 2 返回的全部交易详情（分批并行）
ls_financial_report_vector_search(query="<公司名> business development M&A acquisition strategy therapeutic focus", lang="EN", top_k=10)
ls_news_vector_search(query="<公司名> deal rationale synergy strategic fit therapeutic area expansion", lang="EN", top_k=10)
```

**专利悬崖详情**
```
ls_patent_fetch — 取 Step 2 返回的各 Top 产品核心专利（各品种取主要化合物专利1-2件）
ls_fda_label_vector_search(query="<Top产品名> approved indication extension label expansion", lang="EN", top_k=8)
```

**靶点协同研究**
```
ls_paper_vector_search(query="<核心靶点1> combination synergy <相邻靶点> pathway cross-talk", lang="EN", top_k=10)
ls_clinical_trial_vector_search(query="<Top产品名> combination clinical trial co-administration basket", lang="EN", top_k=10)
```

**竞争对手 BD 对比**
```
ls_drug_deal_search(licensee=["<竞争对手1>"], limit=20)
ls_drug_deal_search(licensee=["<竞争对手2>"], limit=20)
（与该 MNC 同领域的主要竞争对手，各取一次）
```

**学术早期资产来源扫描（针对已识别的缺口领域）**
```
ls_paper_vector_search(query="<缺口领域关键词> academic institution technology transfer license early stage discovery", lang="EN", top_k=15)  — 全球学术机构在缺口领域的转化研究活跃度
ls_paper_vector_search(query="<缺口领域关键词> China university research institute collaboration license-in", lang="CN", top_k=12)  — 中国学术机构早期资产（License-in from China 机会）
ls_news_vector_search(query="<缺口领域> academic spinoff startup licensing deal university", lang="EN", top_k=10)  — 学术转化动态
```

---

### Step 4：重点数据拉取

- 全部已批准药物详情 → `ls_drug_fetch(drug_ids=[...])`（分批，含销售额/适应症/靶点）
- 全部 BD 交易详情 → `ls_drug_deal_fetch(drug_deal_ids=[...])`
- Top 产品核心专利 → `ls_patent_fetch(patent_ids=[...])`（各主力产品1-2件化合物专利）
- 关键里程碑时间线 → `ls_drug_milestone_fetch(drug_id=[...])`（专利到期/LOE/PDUFA/仿制药进入预期）
- 关键新闻全文 → `ls_news_fetch(news_ids=[...])`（Step 2-3 高相关性新闻条目）
- 关键临床结果 → `ls_clinical_trial_result_fetch(result_ids=[...])`
- 主要竞争对手公司信息 → `ls_organization_fetch(organization=[...])`

---

### Step 5：综合分析框架

---

#### 5.1 Top 产品全景（📡 MCP: drug_fetch + financial + fda_label）

对每个已批准产品构建完整档案，并按年销售额排序：

**产品档案表**（排序：年销售额从高到低）

| 产品名 | 通用名 | 靶点 | 机制（MoA） | 适应症（全部） | 年销售额 | 销售峰值年 | 专利到期 | LOE 风险 |
|--------|--------|------|------------|--------------|---------|-----------|---------|---------|

对前 **Top 5 产品**，逐一展开：

```
【产品名】
━ 靶点：[靶点名] | 靶点类别：[激酶/GPCR/抗体靶点/核酸靶点/...]
━ 生物机制：[通路图谱，上游激活因子 → 靶点 → 下游效应 → 治疗效果]
━ 适应症扩展历史：
    [年份] 首批适应症 → [年份] 扩展1 → [年份] 扩展2 → ...
━ 核心专利：
    化合物专利：[专利号] 到期：[年份]（美国）/ [年份]（欧洲）/ [年份]（中国）
    用途专利：[专利号] 到期：[年份]
    工艺专利：[专利号] 到期：[年份]
    补充保护证书（SPC）延长：[是/否，延长至年份]
━ 仿制药/生物类似药现状：[已上市 X 家 / 预期进入年份]
━ 年销售额趋势：[Year-3] [Year-2] [Year-1] [当年] [峰值预测]
━ 耐药机制：[已知耐药通路，点突变/旁路激活/...]
━ 当前 combo 组合：[已批准 combo / 进行中 combo 试验]
━ 适应症扩展机会：[尚未获批但在研的适应症/患者分层]
```

---

#### 5.2 专利悬崖时间表（📡 MCP: patent_fetch + drug_milestone_fetch + financial）

**核心专利识别前置**（📡 MCP: patent_search + patent_vector_search + patent_fetch）：在做到期分析之前，通过多维专利检索（申请人+技术关键词+引用量）先区分：
- "无法绕过的核心化合物专利"（真正 LOE 触发点）
- "可被挑战/绕路的外围专利"（不影响仿制药进入时间）

**里程碑时间线补充**（📡 MCP: drug_milestone_fetch）：专利到期节点 + 预期仿制药/生物类似药进入时间 + PDUFA/监管节点

**专利悬崖瀑布图数据**：各产品核心专利到期 + 对应收入敞口

| 年份 | 产品 | 专利类型到期 | 销售额敞口（$M） | 仿制/生物类似药预期 | 缓冲措施 |
|------|------|------------|----------------|-------------------|---------|

**LOE 累计影响估算**：
- [当前年+1]：预计 LOE 金额 $XB
- [当前年+2]：预计 LOE 金额 $XB（累计）
- [当前年+3~5]：高风险窗口期
- 需要多少新资产收入来覆盖缺口？（按年）

**缓冲措施评估**：
- 适应症扩展（Label Extension）对抗 LOE 的能力
- 下一代改良型化合物（如剂型改进/缓释）
- 当前管线中能否及时上市填补

---

#### 5.3 BD 历史模式解析（📡 MCP: deal_fetch + news）

**历史 BD 交易全清单**（近5年，按时间排序）

| 时间 | 类型 | 资产/公司 | 领域 | 靶点/模态 | 阶段 | 首付款 | 总金额 | 被许可方/收购标的 |
|------|------|----------|------|---------|------|--------|--------|----------------|

**BD 模式统计分析**：
- 偏好阶段：临床前 [X]% / Ph1 [X]% / Ph2 [X]% / Ph3 [X]% / 已批 [X]%
- 偏好类型：License-in [X]% / 收购 [X]% / 合作开发 [X]%
- 偏好模态：小分子 [X] / 抗体 [X] / ADC [X] / 细胞治疗 [X] / 核酸 [X]
- 偏好领域：[领域1] [X]件 / [领域2] [X]件 / ...
- 历史首付比例：平均首付占总额 [X]%（范围：[X]%-[X]%）
- 典型估值区间：临床前 $[X]-[X]M / Ph1 $[X]-[X]M / Ph2 $[X]-[X]M

**近12个月 BD 动态**：
- 最新交易分析（意图、逻辑、市场反应）
- 与历史模式的异同（是否战略转向？）

---

#### 5.4 三大 BD 需求逻辑分析（🧠 Claude 综合推断）

> 核心方法：将专利悬崖时间表 × BD 历史模式 × 当前管线空白 × Top 产品耐药机制 四维交叉，推断该 MNC 的资产需求优先级。

---

**逻辑一：管线补充（Pipeline Fill）**

*解决的问题：专利悬崖带来的收入缺口需要在何时、多大规模的新资产来填补？*

- **紧迫性时间表**：
  | 年份 | 收入缺口 | 需要多少资产 | 资产需要的最晚获批时间 | 因此需要的最晚交易时间 |
  |------|---------|------------|-------------------|-------------------|

- **领域优先级**：收入敞口最大的治疗领域需要优先补充
  | 治疗领域 | 当前收入 | LOE 时间 | 当前管线覆盖率 | 缺口评级 |
  |---------|---------|---------|--------------|---------|

- **阶段偏好推断**：
  - 若缺口在2-3年内：需要 Ph3 资产，愿意支付高溢价（$500M+ 首付）
  - 若缺口在3-5年内：Ph2 资产是最优性价比区间
  - 若缺口在5年以上：可以接受早期资产，以里程碑付款为主

- **模态偏好推断**：基于历史 BD 和当前产能/能力

---

**逻辑二：靶点协同（Target Synergy）**

*解决的问题：与现有批准药物在机制/通路/适应症上产生协同，强化已有资产价值。*

- **同通路协同机会**：
  | 现有药物 | 靶点 | 通路 | 协同靶点候选 | 协同依据 | 已有该协同靶点在研品种 |
  |---------|------|------|------------|--------|-------------------|

- **耐药克服组合**：
  | 现有药物 | 已知耐药机制 | 克服耐药的协同靶点 | 已有临床证据 | 机会空间 |
  |---------|-----------|-----------------|------------|---------|

- **适应症扩展组合**：
  | 现有药物 | 当前适应症 | Combo 可扩展适应症 | 所需联合靶点 | 临床逻辑 |
  |---------|---------|-----------------|------------|---------|

- **平台技术协同**：
  - 该 MNC 是否有特定递送/制造平台？
  - 哪些外部资产能最大化利用该平台？

---

**逻辑三：药物组合（Combination Strategy）**

*解决的问题：通过 Combo 策略将现有药物销售寿命延长、ORR 提高、适应症扩展。*

- **Top 产品 Combo 机会矩阵**：

  | 产品 | 当前局限性 | Combo 所需特征 | 理想搭档靶点 | 是否需要 BD 引进 | 潜在 ORR 提升 |
  |------|---------|--------------|------------|--------------|-------------|

- **已在进行的 Combo 试验**（来自 clinical_trial_search）：
  与哪些外部药物/靶点在做 Combo？这些合作是否可能转化为资产收购？

- **Combo 驱动的 BD 逻辑**：
  - "买来用于 Combo 而非单独开发" 的资产特征
  - 预期协同增效程度 vs 愿意支付的溢价

---

#### 5.5 资产需求画像（🧠 Claude 综合输出）

> **核心输出：这家 MNC 最可能想要什么资产？**

**最高优先级资产画像**（按 BD 紧迫性排序，最多3个画像）：

```
【画像1：最紧迫需求】
━ 触发逻辑：[逻辑一/二/三，具体说明]
━ 目标领域：[治疗领域]
━ 靶点偏好：[具体靶点 or 靶点类型]
━ 模态偏好：[小分子/抗体/ADC/...]
━ 理想阶段：[Ph1/Ph2/Ph3]，原因：[...]
━ 患者分层：[优选有明确 biomarker 的 / 广谱患者群]
━ 价格预期：首付 $[X]-[X]M，总额 $[X]-[X]B，参考交易：[历史可比交易]
━ 交易紧迫性：[高/中/低]，原因：[专利悬崖时间/竞争对手动作]
━ 典型配套方案：[独家 License-in / 共同开发 / 直接收购]

【画像2：战略布局需求】
...

【画像3：机会性需求】
...
```

**学术早期资产来源地图**（📡 MCP: paper_vector_search + news_vector_search）
> 针对3个画像的缺口领域，识别学术界正在研究的早期资产——这是 MNC 未来 BD 的上游来源。

| 缺口领域 | 活跃学术机构 | 代表性合作药企 | 转化成熟度 | BD 机会评级 |
|---------|------------|--------------|---------|----------|

- 中国学术机构在各缺口领域的早期成果（License-in from China 机会评估）
- 哪些院校已与竞争对手建立合作 → 需要抢占的学术资源

**竞争对手对比**：同类 MNC 在相同领域的 BD 活跃程度，对价格的压力影响。

**最应该避开的资产类型**：该 MNC 历史上拒绝的或能力不足的方向。

---

#### 5.6 对外合作/授权策略建议（🧠 Claude）

> 若持有资产并希望向该 MNC 推介，应该如何定位和呈现？

- **最佳对接时机**：基于专利悬崖时间表和 BD 历史，何时是最佳接触窗口
- **定位建议**：应强调"管线补充"还是"协同增效"还是"Combo 机会"
- **数据包优先级**：该 MNC 最看重什么数据（ORR？OS？Safety？CDx？）
- **价格锚定参考**：基于历史可比交易设定预期
- **谈判要点**：里程碑设置、适应症范围、地域范围（全球vs分区）

---

### Step 6：生成交互式 HTML 报告

保存至：`/Users/nihil/Claude/{公司名小写}_mnc_strategy_report.html`

**⚠ 日期要求：使用系统注入的 `currentDate`，文件内所有年份统一核查。**

**⚠ 数据透明度要求（新增，强制）：**
- 专利悬崖瀑布图每个数据点标注来源等级（🟢 S=patent_fetch / 🟡 B=financial_vector / 🔴 C=推算）
- 「资产需求画像」节在每个画像卡片显示 `🔴 战略推断` badge + 依据数据列表
- BD 交易金额：来自 drug_deal_fetch 的 disclosed=false 一律显示 `[金额未披露]`
- 报告末尾必含**数据说明节**（来源统计 / 关键引用列表 / 数据缺失清单 / 推断方法 / 截止日期）

#### HTML 设计规范

**主色调**：`#f0883e`（橙色，战略/商业分析）

**导航节点**（必含）
1. Top 产品全景
2. 专利悬崖
3. BD 历史
4. 管线补充逻辑
5. 靶点协同逻辑
6. 组合策略逻辑
7. 资产需求画像
8. 推介策略
9. **数据说明**（新增必含节）

**交互功能**
- Top 产品表格：按销售额/治疗领域/LOE时间排序
- BD 历史：按类型（License-in/收购）、按领域、按年份筛选
- Combo 机会矩阵：可切换不同产品查看各自 Combo 机会
- 资产画像：按三大逻辑 Tab 切换

**图表（Chart.js CDN）**

- **专利悬崖瀑布图**（核心图表）：x轴=年份，y轴=受威胁收入（$B），颜色=产品，叠加当前管线填补预测线
- **Top 产品销售趋势**：多线折线图（各产品历史+预测）
- **BD 历史阶段分布**：堆叠条形图（按年，各阶段颜色区分）
- **BD 历史模态分布**：甜甜圈图（小分子/生物药/ADC/细胞治疗/核酸）
- **三大 BD 逻辑强度雷达图**：管线补充 / 靶点协同 / Combo策略（各领域各画一个，3个雷达叠加）
- **治疗领域资产缺口热力图**：x轴=治疗领域，y轴=阶段，颜色=缺口程度（红=严重缺口，绿=覆盖充分）
- **资产需求优先级四象限**：x轴=紧迫性，y轴=战略价值，气泡大小=预期交易规模

**专项可视化**

- **产品靶点通路图**：svg 通路网络图，节点=靶点（已有药物节点高亮），边=通路关系，未占据节点=BD 机会标注
- **专利到期时间轴**：交互式时间轴，各产品专利族标注颜色，悬停显示详情（专利号/到期时间/仿制药预期）
- **BD 交易气泡图**：x轴=交易时间，y轴=总金额，气泡大小=首付金额，颜色=领域，悬停显示交易详情
- **管线热力图**：治疗领域 × 阶段，格子数字=品种数，颜色=空缺程度

---

### Step 7：输出摘要

```
✅ MNC 战略资产需求分析完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MNC：[公司名] | 市值：$[X]B | 年收入：$[X]B
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
产品组合：
  已批准品种    n=[X]（Top产品：[产品1] $[X]B / [产品2] $[X]B / [产品3] $[X]B）
  当前管线      n=[X]（Ph3 [X] | Ph2 [X] | Ph1 [X]）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
专利悬崖预警：
  [当前年+1]  收入敞口 $[X]B（产品：[名称]）
  [当前年+2]  累计敞口 $[X]B
  [当前年+3]  最高风险年，累计 $[X]B
  当前管线覆盖率：[X]%（仍有 $[X]B 缺口待补）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BD 历史（近5年）：
  交易总数 n=[X]（License-in [X] | 收购 [X]）
  偏好阶段：[阶段] | 偏好领域：[领域] | 偏好模态：[模态]
  平均首付：$[X]M | 平均总额：$[X]M
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
数据可信度统计：
  🟢 S/A（数据库直接记录）  n=[X] 条
  🟡 B/W（搜索/网络补充）   n=[X] 条
  🔴 C（模型推断/综合）     n=[X] 条
  ⚠ 数据缺失项             n=[X] 条（详见报告数据说明节）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三大 BD 逻辑评级（均为 🔴 C 综合推断）：
  管线补充逻辑：[强烈/中等/较弱]（缺口年份：[年份]，依据：专利到期日[S]+管线数据[A]）
  靶点协同逻辑：[强烈/中等/较弱]（核心靶点：[靶点名]，依据：Combo试验[A]+产品适应症[S]）
  Combo 策略逻辑：[强烈/中等/较弱]（主力产品：[产品名]，依据：临床结果[S]+BD历史[S]）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
最高优先级资产画像（🔴 C 战略推断，依据数据见报告第7节）：
1. [领域]+[靶点/模态]+[阶段] — [核心逻辑一句话] — 预期首付 $[X]-[X]M [C]
2. [领域]+[靶点/模态]+[阶段] — [核心逻辑一句话] — 预期首付 $[X]-[X]M [C]
3. [领域]+[靶点/模态]+[阶段] — [核心逻辑一句话] — 预期首付 $[X]-[X]M [C]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
报告路径：/Users/nihil/Claude/[filename].html
数据说明：报告末尾数据说明节（含缺失清单 + 引用列表 + 推断方法）
```

---

## 工具使用速查

| 阶段 | 工具 | 用途 |
|------|------|------|
| Step 1 | `ls_ner_nor_normalize` | 公司实体标准化 |
| Step 2 | `ls_organization_fetch` | 公司基本信息 |
| Step 2 | `ls_organization_pipeline_fetch` | 公司全管线结构化快照 |
| Step 2 | `ls_drug_search` × 2 | 全管线 + 仅已批准 |
| Step 2 | `ls_drug_fetch` | 全部已批准药物详情（含销售额/靶点/适应症） |
| Step 2 | `ls_patent_search` × 2 | 化合物专利 + 用途专利 |
| Step 2 | `ls_drug_deal_search` × 2 | 许可出 + 引进入双向 |
| Step 2 | `ls_clinical_trial_search` | 在研管线临床状态 |
| Step 2 | `ls_clinical_trial_result_search` | 已发布临床结果 |
| Step 2 | `ls_financial_report_vector_search` × 2 | 销售额/专利悬崖财务影响 |
| Step 2 | `ls_news_vector_search` × 2 | BD 策略/专利悬崖动态 |
| Step 2 | `ls_drug_milestone_fetch` | 上市产品专利到期/LOE/监管里程碑 |
| Step 3 | `ls_paper_vector_search` × Top5产品 | 各主力产品耐药/Combo 机制 |
| Step 3 | `ls_paper_vector_search` × 缺口领域 | 学术早期资产来源扫描 |
| Step 3 | `ls_drug_deal_fetch` | 全部交易详情（含里程碑结构） |
| Step 3 | `ls_clinical_trial_vector_search` | Combo 试验语义检索 |
| Step 3 | `ls_financial_report_vector_search` | 战略意图/BD 重点领域 |
| Step 3 | `ls_drug_deal_search` × 竞争对手 | 竞争对手 BD 对比 |
| Step 3 | `ls_news_vector_search` | 学术转化动态/竞对动向 |
| Step 4 | `ls_patent_fetch` | 各 Top 产品核心化合物专利全文 |
| Step 4 | `ls_drug_deal_fetch` | 关键交易详情 |
| Step 4 | `ls_drug_milestone_fetch` | 专利到期/LOE 里程碑确认 |
| Step 4 | `ls_news_fetch` | 关键新闻全文详情 |
| Step 4 | `ls_clinical_trial_result_fetch` | Combo 试验结果 |
| Step 4 | `ls_drug_fetch` | 各管线品种 PK/PD 详情 |
| Step 4 | `ls_organization_fetch` | 主要合作方信息 |
| 补充 | `ls_web_search` | MCP 无结果时补充（尤其是销售数据） |

---

## 容错规则

1. **销售额数据缺失**：MCP 财报工具优先，缺失时 `ls_web_search` 检索年报，再用 Claude 知识填充，标注"估算"
2. **专利到期数据不精确**：给出"预计到期"而非确定值，注明"需专业 FTO 验证"；drug_milestone_fetch 提供辅助交叉验证
3. **BD 交易数据不完整**：标注"金额未公开"，通过新闻/文献推断规模量级
4. **Combo 机制分析无 MCP 数据**：大量依赖 Claude 知识 + 文献，明确标注
5. **早期（<5年）的 MNC 有限 BD 历史**：扩展时间窗口至10年，或与同类公司对比补充
6. **竞争对手未标准化**：使用英文全称重试，仍失败则跳过该竞品分析
7. **学术来源数据不足**：从 news_vector_search 会议/专利转让/spinoff 新闻补充，标注"基于公开信息"

---

## 与其他 Skill 的关系

| 场景 | 推荐 Skill |
|------|-----------|
| 分析某具体靶点值不值得立项 | `/target-intel` |
| 分析某适应症有哪些机会 | `/disease-intel` |
| 全面了解一家公司的资产 | `/company-intel` |
| **推断 MNC 想要什么资产、为什么** | `/mnc-strategy` ← 本 Skill |
| 组合使用：先了解公司，再推断需求 | `/company-intel` + `/mnc-strategy` |
