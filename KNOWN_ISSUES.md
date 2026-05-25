# 已知问题与解决方案汇总

基于实际调研案例（OX40 全模态 2026-05-15、SDC2 治疗型 2026-05-23）积累的 MCP 工具使用经验。

---

## Issue 1：`ls_drug_fetch` 返回完全不同的药物（ID不匹配）

**现象**
查询 GS-2272（预期为 OX40 相关抗体），`ls_drug_fetch` 返回的是 Astegolimab（抗IL-33R单抗），靶点与预期完全不符。

**根因**
智慧芽内部 drug_id 是自增数字或哈希 ID，并非药物通用名/代号。`ls_drug_search` 返回的 drug_id 在极少数情况下会因数据库合并/重建而指向不同药物；亦可能搜索结果中的 ID 本身就对应另一条记录。

**解决方案**
1. 拿到 drug_fetch 结果后，首先核对返回药物名和靶点是否与预期一致
2. 若不符，立即丢弃该结果，**不得**将错误数据写入报告
3. 改用 `ls_drug_search(drug_name=["<药物通用名或代号>"])` 按名称精确搜索
4. 或用 `ls_news_vector_search(query="<药物名> company developer phase indication")` 补充

**skill 更新位置**：容错规则 Rule 10；Step 4 药物逐条验证说明

---

## Issue 2：药物管线表中公司名称"未披露"

**现象**
`ls_drug_search` 返回管线品种时，`organization` 字段为空或标注"未披露"（Undisclosed Company），但药物代号已知（如 STAR-0310、IMG-007）。

**根因**
`ls_drug_search` 的搜索结果为摘要条目，部分字段（尤其早期/小公司品种）存在缺失。完整公司信息通常存在于 `ls_drug_fetch` 的详情记录中，或可通过新闻搜索获得。

**解决方案**
1. Step 4 对 Phase 1-3 所有品种执行 `ls_drug_fetch`，公司名以 fetch 结果为准
2. 若 fetch 后仍为空：`ls_news_vector_search(query="<药物名> company developer organization")`
3. 若新闻仍无结果：`ls_web_search(query="<药物名> company")`
4. 仅在上述三步均无结果时才标注"⚠ 开发商待核实"

**实际案例结果**
- STAR-0310：fetch 后确认为 Astria Therapeutics / Ichnos Glenmark Innovation（Phase 1，非 Phase 2）
- IMG-007：fetch 后确认为 Inmagene Biopharmaceuticals / HUTCHMED 和黄医药（Phase 2，非耗竭机制）

**skill 更新位置**：Step 4 药物逐条验证；Step 5.2 公司名称质控说明

---

## Issue 3：开发阶段错误（Phase 2 vs Phase 1）

**现象**
`ls_drug_search` 摘要中 STAR-0310 显示 Phase 2，但 `ls_drug_fetch` 详情和新闻均确认为 Phase 1。

**根因**
搜索结果摘要的 `highest_phase` 字段可能反映的是历史最高阶段或数据录入时的状态，而非当前活跃阶段。数据更新频次低于临床进展速度。

**解决方案**
1. 管线表中每个品种的阶段以 `ls_drug_fetch` 详情为准
2. 发现不一致时，优先以 fetch > search > 新闻搜索的优先级采信
3. 对高价值品种（Phase 3）追加 `ls_clinical_trial_search(drug=["<药物名>"])` 交叉验证

**skill 更新位置**：Step 4 药物逐条验证（字段：开发阶段）

---

## Issue 4：BD 交易终止状态未反映在 `ls_drug_fetch` 中

**现象**
Amgen/Kyowa Kirin（KKC）关于 rocatinlimab 的 BD 合作已终止，但 `ls_drug_fetch` 的开发商列表中仍保留 Amgen，可能被误解为活跃合作。

**根因**
`ls_drug_fetch` 的 organization 字段采用宽泛的"曾参与"逻辑，而非"当前活跃"逻辑。BD 合作终止后，开发商字段不会自动清除原合作方。

**解决方案**
1. 不要单独依赖 `drug_fetch` 的 organization 字段判断合作状态
2. 对每个重要 BD 交易执行 `ls_drug_deal_fetch`，检查 `status` 字段
3. 同时检查交易标题/描述中的终止关键词：`exit`、`terminate`、`jilt`、`walk away`、`discontinue partnership`
4. 并行执行 `ls_news_vector_search(query="<药物名> <公司名> terminate exit deal collaboration")` 交叉确认
5. 发现终止交易后，**立即**在报告中以红色警示框标注，并说明权益归属预期

**实际案例结果**
`ls_drug_deal_fetch` 返回 status=Terminated，标题原文："Amgen jilts Kyowa, exiting $400M autoimmune pact after running vast pivotal program"

**skill 更新位置**：Step 4 BD 交易状态交叉验证；Step 5.7 已终止交易单独列示；容错规则 Rule 12

---

## Issue 5：配体伴侣未搜索（免疫受体靶点仅搜索受体）

**现象**
用户输入 `/target-intel OX40`，初始报告只研究 OX40 受体，未搜索 OX40L（配体/TNFSF4）。导致：
- 漏掉 Amlitelimab（Sanofi，抗OX40L，Phase 3）—— 该领域最重要的在研品种
- 漏掉 IBI-356（信达，抗OX40L，Phase 2）
- 漏掉 Brivekimig（Sanofi，OX40L×TNFα 双抗，Phase 2）
- 错误地将竞争格局评估为"以OX40受体拮抗为主"

**根因**
skill 原始设计仅考虑靶点本身，未有对生物配体/受体伴侣的系统性识别和并行搜索机制。

**解决方案**
1. Step 0 增加"免疫靶点识别"模块，自动识别 TNFR 家族/CD28 家族/细胞因子受体
2. 识别到配体伴侣后，Step 1 同时标准化配体名称
3. Step 2 同时执行配体的 `ls_target_fetch` 和 `ls_drug_search`
4. 报告中"靶点概览"节并列展示受体和配体；管线表增加"靶向受体/靶向配体"筛选维度
5. 免疫靶点必须包含 MOA 机制概览节（`#moa`），三栏展示：激动剂/受体拮抗剂/配体拮抗剂

**适用范围**
所有属于以下家族的靶点均需执行配体伴侣搜索：
- TNFR 超家族：OX40(←OX40L)、CTLA-4(←CD80/CD86)、CD40(←CD40L)、DR5(←TRAIL)、GITR(←GITRL)、4-1BB(←4-1BBL)
- CD28 超家族：PD-1(←PD-L1/PD-L2)、ICOS(←ICOSL)、TIGIT(←CD155/CD112)、TIM-3(←Galectin-9)、LAG-3(←MHC-II)
- 细胞因子受体：IL-4Rα(←IL-4/IL-13)、IL-13Rα1(←IL-13)、TSLPR(←TSLP)、IL-31RA(←IL-31)

**skill 更新位置**：Step 0 免疫靶点识别；Step 1 配体标准化；Step 2 配体并行搜索；Step 3 MOA 专项搜索；HTML #moa 节；容错规则 Rule 11

---

## Issue 6：关键管线品种被遗漏（数据库收录延迟）

**现象**
Amlitelimab（Sanofi，抗OX40L，Phase 3 COAST-1 2025年9月阳性）未出现在 `ls_drug_search` 的返回结果中，用户明确指出后才补充。

**根因**
智慧芽数据库存在6-12个月的收录延迟，近期入组或近期公布关键数据的品种可能缺失。`ls_drug_search` 对靶点（OX40）的精确匹配可能会遗漏靶向配体（OX40L）的药物（需用 OX40L 单独搜索）。

**解决方案**
1. Step 2 中增加"管线覆盖率补充验证"步骤（强制）：
   ```
   ls_news_vector_search(query="<靶点名> <配体伴侣名> new drug Phase 3 Phase 2 clinical 2024 2025", top_k=15)
   ```
2. 将新闻提及的药物名与 drug_search 结果列表对比，发现未收录品种立即补充查询
3. 若用户或已有知识指出某品种，不得以"数据库无记录"为由忽略，必须单独补充搜索

**skill 更新位置**：Step 2 管线覆盖率补充验证（新增强制步骤）；容错规则 Rule 13

---

## Issue 7：`ls_patent_search` 靶点索引延迟导致新公开 WO 专利遗漏

**现象**
SDC2 调研中，WO2026030235A1（2026-02-05 公开，Yale+VST-Bio）和 WO2025101747A1（2025-05-15 公开，VST-Bio）均可在 `patsnap_search` 检索到，但 `ls_patent_search(target=["SDC2"])` 未返回。

**根因**
Pharma Intelligence 专利库的靶点标注（`target` 字段）依赖半自动索引，WO 新公开专利存在 6-12 个月延迟。`patsnap_search` 使用全文关键词匹配，无此延迟。

**解决方案**
1. 专利检索必须双轨交叉验证：`ls_patent_search`（结构化靶点索引）+ `patsnap_search`（全文关键词）
2. 对管线公司追加 `patsnap_search(keywords=["<公司名>", "<靶点名> patent"])` 确保覆盖公司最新申请
3. 报告中对 ls_patent_search 未收录的专利标注"⚠ 靶点索引延迟"

**实际案例结果**
- `ls_patent_search(target=["SDC2"])` 返回 5 件专利
- `patsnap_search(keywords=["SDC2"])` 额外发现 2 件新公开专利
- 原因：SDC2 作为极早期靶点（仅 2 个临床前品种），靶点标注优先级低，索引更慢

**skill 更新位置**：Step 2 专利双轨交叉验证（升级为必做）；Step 4 专利 UUID 解析说明

---

## Issue 8：管线公司来源文献缺失

**现象**
SDC2 报告原有 6 篇核心文献均为靶点生物学论文，缺少 VST-Bio（Ristori 2022 Nat CVR、André 2025 TVST）和 Orbsen（Brady 2020、Alagesan 2022）的公司来源文献。这些论文才是管线药物最直接的机理/疗效证据。

**根因**
Skill Step 2 的 `ls_paper_search(target=[...])` 只按靶点搜索文献，不按公司搜索。Step 4 虽有 `ls_organization_fetch`，但不检索公司发表的论文。

**解决方案**
1. Step 4 增加"管线公司来源文献"子步骤：对每个有管线药物的公司并行 `ls_paper_search(organization=["<公司名>"], target=["<靶点名>"])` 和 `ls_paper_search(organization=["<公司名>"])`
2. 公司来源文献在报告中以"管线公司来源文献"子节独立呈现
3. 标注公司名和管线品种关联

**实际案例结果**
- VST-Bio：1 篇直接发表（André 2025）+ Yale 联合发表（Ristori 2022）→ VST-002 的机制基础和 AMD 临床前数据
- Orbsen：13 篇 MSC 文献，其中 3 篇直接使用 CD362(SDC2) 作为 MSC 分选标记 → VTS-201 的给药方案和制造工艺

**skill 更新位置**：Step 4 新增"管线公司来源文献"必做步骤

---

## Issue 9：专利 Analytics 链接 UUID 获取路径未文档化

**现象**
生成 Analytics 链接需要 `patentId` UUID（含连字符），但 `ls_patent_search`/`ls_patent_fetch` 返回 `patent_id` 为 32 位 hex（不含连字符），无法直接用于组装 URL。

**根因**
两个 MCP 服务（pharma_intelligence vs patsnap_patent_search）使用不同的 ID 格式：
- `ls_patent_search` → `patent_id`: `efc64f575fa942fe8ad756ef95010b72`（32 位 hex）
- `patsnap_search` → `id`: `84e2b026-6a0c-4f71-b8b8-e9f9f2325678`（UUID with hyphens）

**解决方案**
对报告需呈现的每个专利号，用 `patsnap_search(keywords=["<专利号>"])` 获取 UUID，然后组装 Analytics 链接。

**skill 更新位置**：Step 4 新增"专利 Analytics UUID 解析"说明

---

---

# MCP 协议层错误

以下问题发生在工具调用的**基础设施层**（Claude API ↔ MCP Server 通信层），与数据内容无关。已用 `mcp_proxy.py` 作为本地代理统一处理。

---

## MCP Error A：`inputSchema` 含 `anyOf/oneOf/allOf` 导致 Claude API 400 错误

> **2026-05-21 更新**：初版记录仅覆盖 `pharma_intelligence`；经深查发现
> `biology_modality`（6个工具）和 `chemical_molecular`（2个工具）也存在相同问题。
> 修复方案已升级为**三服务全代理**，详见"当前修复"节。

---

### 错误现象

调用任意 `ls_*` 工具时，Claude API 返回 400，报错信息：

```
API Error: 400 tools.11.custom.input_schema:
  input_schema does not support oneOf, allOf, or anyOf at the top level
```

错误中的序号（`tools.11`）指的是 Claude API 合并所有 MCP 服务后的工具列表中，
第 12 个（0-indexed）工具的 schema 不合法。**所有工具均无法使用**。

---

### 根因

智慧芽三个 MCP 服务的工具 `inputSchema`，在**属性（properties）层**使用了
`anyOf/oneOf/allOf`（JSON Schema 组合关键字），通常用于表达"可选参数类型为
`string | null`"或"多条件至少满足其一"。

Claude API 要求 `inputSchema` 根层必须为 `{ "type": "object" }`，且不允许
属性值中存在 `anyOf/oneOf/allOf`（即便不在根层）。两者规范不兼容，
导致工具注册阶段全量失败。

---

### 问题分布（通过直连 MCP 服务端实测，2026-05-21）

以下用 Python 脚本直接调用各服务 `tools/list`，检查每个工具的 schema：

```python
# 检测脚本（可复用）
import json, urllib.request, ssl

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
APIKEY = "sk-3F0NsY7KOt2ZyO72XkgwUIwD80xSfBjCNKp7juA92d0HWpKu"

def check_service(name, url):
    body = json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}).encode()
    req = urllib.request.Request(url, data=body,
        headers={'Content-Type':'application/json','Accept':'application/json,text/event-stream'},
        method='POST')
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as r:
        raw = r.read().decode()
    for line in raw.splitlines():
        if line.startswith('data:'):
            tools = json.loads(line[5:]).get('result', {}).get('tools', [])
            for t in tools:
                s = t.get('inputSchema', {})
                top_bad = any(k in s for k in ('anyOf','oneOf','allOf'))
                bad_props = [p for p,v in s.get('properties',{}).items()
                             if isinstance(v,dict) and any(k in v for k in ('anyOf','oneOf','allOf'))]
                flag = "❌" if (top_bad or bad_props) else "✅"
                print(f"  {flag} {t['name']} | top={top_bad} | bad_props={bad_props[:3]}")
```

**实测结果：**

```
=== pharma_intelligence (096456/logic-mcp) ===  [30个工具，全部经代理]
  ❌ ls_drug_search        | top=False | bad_props=['drug', 'target', 'disease']
  ❌ ls_patent_search      | top=False | bad_props=['drug', 'target', 'organization']
  ❌ ls_clinical_trial_search | top=False | bad_props=['drug', 'target', 'disease']
  ❌ ls_paper_search       | top=False | bad_props=['drug', 'target', 'disease']
  ❌ ls_drug_deal_search   | top=False | bad_props=['drug', 'organization', 'target']
  ... (共约15个工具受影响)
  ✅ ls_drug_fetch         | top=False | bad_props=[]
  ✅ ls_patent_fetch       | top=False | bad_props=[]
  ✅ ls_ner_nor_normalize  | top=False | bad_props=[]

=== biology_modality (06e741/logic-mcp) ===  [8个工具]
  ❌ ls_sequence_search_submit   | top=False | bad_props=['evalue', 'database', 'perc_identity']
  ❌ ls_modification_search_submit | top=False | bad_props=['sequence', 'subject_length']
  ❌ ls_sequence_search_get_results | top=False | bad_props=['order', 'sort_field', 'perc_identity']
  ❌ ls_antibody_antigen_search  | top=False | bad_props=['filter']
  ❌ ls_sequence_alignment       | top=False | bad_props=['query_sequence']
  ❌ ls_patent_sequence_fetch    | top=False | bad_props=['pn', 'patent_id']
  ✅ ls_sequence_search_check_status | top=False | bad_props=[]
  ✅ ls_sequence_fetch           | top=False | bad_props=[]

=== chemical_molecular (713886/logic-mcp) ===  [7个工具]
  ❌ ls_structure_search         | top=False | bad_props=['threshold']
  ❌ ls_patent_structure_fetch   | top=False | bad_props=['pn', 'patent_id']
  ✅ ls_admet_predict            | top=False | bad_props=[]
  ✅ ls_chemical_mcs_analyze     | top=False | bad_props=[]
  ✅ ls_structure_fetch          | top=False | bad_props=[]
  ✅ ls_sar_submit               | top=False | bad_props=[]
  ✅ ls_sar_fetch                | top=False | bad_props=[]
```

**受影响工具汇总：pharma_intelligence ~15 个 + biology_modality 6 个 + chemical_molecular 2 个**

---

### 具体 Schema 示例（以 `ls_patent_sequence_fetch` 为例）

```json
// 原始 schema（biology_modality，Claude API 拒绝）
{
  "properties": {
    "patent_id": {
      "anyOf": [{"type": "string"}, {"type": "null"}],  // ← 问题在这里
      "description": "Patent ID used to fetch related sequences.",
      "title": "Patent Id"
    },
    "pn": {
      "anyOf": [{"type": "string"}, {"type": "null"}],  // ← 同上
      "description": "Patent number ...",
      "title": "Pn"
    }
  }
}

// 代理修复后（Claude API 接受）
{
  "properties": {
    "patent_id": {
      "type": "string",      // anyOf [string, null] → string（非必填由 required 控制）
      "description": "Patent ID used to fetch related sequences.",
      "title": "Patent Id"
    },
    "pn": {
      "type": "string",
      "description": "Patent number ...",
      "title": "Pn"
    }
  }
}
```

---

### 当前修复：三服务全代理（2026-05-21）

**代理脚本**：`/Users/nihil/Claude/bio-intelligence/mcp_proxy.py`（支持 `--port`/`--upstream` 参数）

**修复原理**（`fix_input_schema` 函数）：
1. 剥离 `inputSchema` 根层的 `anyOf/oneOf/allOf`
2. 递归遍历 `properties`，将 `anyOf: [real_type, null]` → `real_type`
3. 多于一个非 null 选项时保留（不能简化），但实践中未见此情况

**每次新会话启动命令（三条）：**

```bash
# pharma_intelligence → 端口 3099（30个工具）
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &

# biology_modality → 端口 3100（8个工具）
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py \
  --port 3100 \
  --upstream https://connect.zhihuiya.com/06e741/logic-mcp &

# chemical_molecular → 端口 3101（7个工具）
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py \
  --port 3101 \
  --upstream https://connect.zhihuiya.com/713886/logic-mcp &
```

**Claude Code MCP 配置（已配置，无需重做）：**

| 服务名 | 配置端点 | 原直连地址 |
|--------|---------|-----------|
| `pharma_intelligence` | `http://127.0.0.1:3099/mcp` | `096456/logic-mcp` |
| `biology_modality` | `http://127.0.0.1:3100/mcp` | `06e741/logic-mcp` |
| `chemical_molecular` | `http://127.0.0.1:3101/mcp` | `713886/logic-mcp` |

**验证代理已就绪（修复后测试数据）：**

```bash
# 验证 biology_modality 代理（最关键，之前直连有问题）
curl -s --max-time 5 -X POST http://127.0.0.1:3100/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}'
# 预期返回: data: {"result":{"serverInfo":{"name":"..."}}}  → ✅

# 验证 schema 修复效果（Python）
python3.10 -c "
import json, urllib.request
for name, port in [('biology_modality',3100),('chemical_molecular',3101)]:
    url = f'http://127.0.0.1:{port}/mcp'
    body = json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}}).encode()
    req = urllib.request.Request(url, data=body,
        headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
    for line in raw.splitlines():
        if line.startswith('data:'):
            tools = json.loads(line[5:]).get('result',{}).get('tools',[])
            bad = [t['name'] for t in tools if
                   any(k in t.get('inputSchema',{}).get('properties',{}).get(p,{})
                       for p in t.get('inputSchema',{}).get('properties',{})
                       for k in ('anyOf','oneOf','allOf'))]
            print(f'{name}: {len(tools)} tools — {\"✅ all clean\" if not bad else \"❌ still bad: \"+str(bad)}')
"
# 预期输出:
# biology_modality: 8 tools — ✅ all clean
# chemical_molecular: 7 tools — ✅ all clean
```

**真实端到端验证（2026-05-21 实测）：**
调用 `ls_patent_sequence_fetch(pn="WO2023045977A1")` → 返回 49 条蛋白序列，无 400 错误。

---

### 问题历史（Timeline）

| 日期 | 事件 |
|------|------|
| 2026-05-15 之前 | 初次发现 pharma_intelligence 直连报 400，编写代理 mcp_proxy.py，配置端口 3099 |
| 2026-05-21 | 再次出现 400 错误。排查发现 biology_modality（6工具）和 chemical_molecular（2工具）直连未经代理。CLAUDE.md 中"直连无问题"的记录是错误的 |
| 2026-05-21 | mcp_proxy.py 改造支持 `--port`/`--upstream` 参数；新增 :3100/:3101 两个代理实例；MCP 配置更新；CLAUDE.md 修正 |

---

### 解决方案性质评估

| 维度 | 评估 |
|------|------|
| **稳定性** | 中等。代理进程无守护，会话重启后需手动重启 |
| **透明度** | 高。代理仅修改 `tools/list` 响应，工具实际调用原样透传 |
| **安全性** | 低风险。跳过 SSL 验证（见 MCP Error B），本机内网环境可接受 |
| **可扩展性** | 好。新增服务只需新端口，一个脚本统一管理 |

**永久解决方案（需 PatSnap 配合）**：
将属性中的 `anyOf: [{"type": "string"}, {"type": "null"}]` 改为 `{"type": "string"}`，
将可选性通过 `required` 数组控制而非 `anyOf`。此修改对服务端零影响。

**如何向 PatSnap 反馈（见文末"反馈渠道"节）**

---

## MCP Error B：SSL 证书验证失败

**现象**
`mcp_proxy.py` 转发请求至 `https://connect.zhihuiya.com` 时，Python `urllib` 抛出：
```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
```
工具调用全部失败，代理返回 `-32603 Internal error`。

**根因**
可能原因（按优先级）：
1. 企业 VPN / 代理服务器进行了 SSL 中间人解包（MITM），插入自签名证书
2. 操作系统 CA 证书库不含智慧芽服务器的证书链（macOS Python 独立安装时常见）
3. 网络环境对 `zhihuiya.com` 的 SNI 做了干扰

**解决方案（当前）：临时 Workaround**
`mcp_proxy.py` 中已设置跳过证书验证：
```python
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE
```

**解决方案性质**：**临时（有安全风险）**
- 可接受：本机内网环境，且不传输敏感用户数据（仅传递 API Key + 查询词）
- 不可接受：在共享服务器或生产环境中部署代理时，必须改为信任正确 CA

**永久解决方案（自行修复，无需 PatSnap）**
```python
# 方案1：信任系统 CA（推荐）
import certifi
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# 方案2：若企业 VPN 有自定义 CA，导出证书后：
SSL_CTX = ssl.create_default_context(cafile="/path/to/corporate-ca.crt")
```

---

## MCP Error C：工具调用超时（上游 60s 无响应）

**现象**
`ls_*` 工具调用长时间无返回，最终 Claude Code 收到代理返回的错误：
```json
{"jsonrpc":"2.0","error":{"code":-32603,"message":"timed out"}}
```

**根因**
智慧芽服务器处理复杂查询（向量检索、大量结果排序）时延迟较高，尤其在并行发出 10+ 工具调用时，部分查询可能超过代理设定的 60 秒超时阈值。

**解决方案（当前）：可配置**
调整 `mcp_proxy.py` 中的 `timeout` 参数：
```python
# 当前值（第 109 行）
with urllib.request.urlopen(req, context=SSL_CTX, timeout=60) as resp:

# 建议调整为 90-120 秒（针对向量搜索密集的调研场景）
with urllib.request.urlopen(req, context=SSL_CTX, timeout=120) as resp:
```

**解决方案性质**：**永久（配置调整即可）**

**Skill 容错对应**：tool 超时后改用 `ls_web_search` 补充（容错规则 Rule 2）

---

## MCP Error D：代理进程意外退出后工具全部不可用

**现象**
Claude Code 中所有 `ls_*` 工具调用均返回 "Connection refused" 或 "pharma_intelligence: disconnected"，但未显示明显错误提示。

**根因**
`mcp_proxy.py` 是通过 `&` 后台运行的普通 Python 进程，没有进程守护。终端关闭、系统睡眠唤醒、或手动 Ctrl-C 后进程退出，Claude Code 下次调用时连接到 `127.0.0.1:3099` 失败。

**解决方案（当前）**：检查并重启代理
```bash
# 检查代理是否在运行
lsof -i :3099

# 若无结果，重新启动
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &

# 验证已连接（在 Claude Code 中）
/mcp  # 确认 pharma_intelligence 状态为 Connected
```

**解决方案性质**：**临时**

**永久解决方案（自行改进，无需 PatSnap）**
用 `launchd`（macOS 系统服务）将代理设为开机自启：
```xml
<!-- ~/Library/LaunchAgents/com.local.mcp-proxy.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.local.mcp-proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/python3.10</string>
    <string>/Users/nihil/Claude/bio-intelligence/mcp_proxy.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/mcp-proxy.log</string>
  <key>StandardErrorPath</key><string>/tmp/mcp-proxy.err</string>
</dict>
</plist>
```
```bash
launchctl load ~/Library/LaunchAgents/com.local.mcp-proxy.plist
```
加载后代理开机自启、崩溃自重启，无需手动管理。

---

## 如何向 PatSnap（智慧芽）反馈

**需要反馈的问题**

| 优先级 | 问题 | 类型 | 影响范围 |
|--------|------|------|---------|
| P0 | MCP Error A：inputSchema 顶层 anyOf 与 Claude API 不兼容 | API 规范缺陷 | 所有 Claude Code 用户完全无法使用 |
| P1 | Issue 1：drug_id 在 fetch 时指向错误药物 | 数据库一致性 | 产生错误情报 |
| P1 | Issue 4：BD 交易终止状态不同步至 drug_fetch | 数据更新机制 | 产生错误情报 |
| P2 | Issue 3：highest_phase 字段滞后 | 数据更新频率 | 阶段信息偏差 |
| P2 | Issue 6：新药收录延迟 6-12 个月 | 数据库覆盖率 | 管线遗漏 |
| P3 | MCP Error C：高并发查询超时 | 性能 | 影响调研效率 |

**反馈渠道**

1. **企业支持邮件**（优先）
   - 智慧芽企业客户通常有专属客户成功经理（CSM），通过 CSM 提交 API 技术 bug
   - 邮件主题格式：`[PatSnap MCP API Bug] <问题简述>` 

2. **技术支持工单**
   - 登录智慧芽平台 → 右上角帮助中心 → 提交工单
   - 选择类型：API/开发者支持

3. **反馈模板（可直接使用）**

```
主题：[MCP API Bug] Claude API 不兼容：inputSchema 根层 anyOf 导致工具注册失败

问题描述：
贵方 MCP 服务器（https://connect.zhihuiya.com/096456/logic-mcp）的所有工具
在 inputSchema 根层使用了 anyOf/oneOf/allOf 组合关键字。Anthropic Claude API
要求 inputSchema 根层必须为 type:object，导致工具注册时全量返回 400 错误。
目前我们通过本地代理 workaround 绕过，但此方案不适合规模化使用。

复现步骤：
1. 将贵方 MCP 服务配置为 Claude Code 的 MCP 服务端点
2. 执行任意 ls_* 工具调用
3. Claude API 返回 400 Bad Request，tools.N.custom.input_schema 验证失败

期望修复：
将工具 inputSchema 根层由 anyOf 改为 type:object，将各参数设为可选属性，
在 description 中说明参数约束。参考 MCP 规范：https://spec.modelcontextprotocol.io/

环境信息：
- Claude Code 版本：最新
- 模型：claude-sonnet-4-6
- 调用方式：HTTP transport（http://127.0.0.1:3099/mcp 代理转发）
- API Key：sk-3F0NsY7KOt2ZyO72XkgwUI...（已脱敏）
```

**反馈时机**
- MCP Error A（P0）：**立即反馈**，这是基础设施级缺陷，影响所有 Claude Code 集成用户
- 数据质量问题（P1/P2）：收集 2-3 个案例后一次性反馈，附上具体 drug_id + 预期值 + 实际返回值

---

## 总结：数据可信度层级

使用以下优先级确定各字段采信来源：

| 字段 | 最高可信来源 | 备用来源 | 最低可信来源 |
|------|------------|---------|------------|
| 开发公司 | `ls_drug_fetch` organization | `ls_news_vector_search` | `ls_drug_search` 摘要 |
| 开发阶段 | `ls_drug_fetch` highest_phase + `ls_clinical_trial_search` | 新闻 | `ls_drug_search` 摘要 |
| BD 合作状态 | `ls_drug_deal_fetch` status + 新闻 | `ls_drug_deal_search` 标题 | `ls_drug_fetch` organization |
| 药物存在性 | `ls_drug_search` 精确匹配 | `ls_news_vector_search` + `ls_web_search` | Claude 训练知识 |
| 交易金额 | `ls_drug_deal_fetch` 详情 | `ls_drug_deal_search` 摘要 | 新闻 |
| 专利覆盖 | `ls_patent_search` + `patsnap_search` 交叉验证 | `patsnap_search` 全文匹配 | `ls_patent_search` 单独使用 |
| 专利 UUID | `patsnap_search` 的 `id` 字段 | — | `ls_patent_search` 的 `patent_id`（格式不兼容） |
| 公司文献 | `ls_paper_search(organization+target)` | `ls_paper_search(organization)` | `ls_paper_search(target)` 通用 |
