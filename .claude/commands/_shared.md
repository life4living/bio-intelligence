# _shared.md — 公共模块（所有 skills 共用）

> 本文件由各 skill 在执行前 Read 加载。包含：Pre-flight 连接检查、MCP 调用日志、数据治理框架、HTML 通用规范。

---

## Pre-flight：MCP 连接检查（每次执行前必做）

**在 Step 0 之前**，用探针验证 `pharma_intelligence` MCP 工具是否可用：

```
ls_ner_nor_normalize(user_input="test")
```

| 结果 | 状态 | 处理 |
|------|------|------|
| 返回任意 JSON | ✅ 正常 | 继续 Step 0 |
| Connection refused / tool not found / MCP disconnected | ❌ 代理未运行 | 输出诊断（见下），**暂停执行** |
| HTTP 400 / schema validation error | ❌ 代理异常（未过滤 anyOf） | 输出诊断（见下），**暂停执行** |
| 超时（>60s 无响应） | ⚠️ 网络繁忙 | 等 10s 后重试一次；二次仍超时则暂停 |

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

**执行中途单个工具失败的处理：**
- 单次调用错误（非连接断开）→ 标注 `⚠ MCP数据暂缺`，改用 `ls_web_search` 补充，**不中断整体流程**
- 同一轮 3 个以上工具连续失败 → 重新做 Pre-flight 探针，判断代理是否断开
- 超时但其他工具正常 → 缩短 limit（30→15）后重试一次

---

## MCP 调用日志（强制执行）

**每次调用智慧芽 MCP 工具后**，立即用 `Bash` 将该次调用写入日志文件。

### 日志文件路径

```
/Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log
```

### 写入时机

- **调用成功后**：写入工具名、关键参数、返回记录数/结果摘要
- **调用失败后**：写入工具名、关键参数、错误信息

### 日志写入命令（每次调用后执行）

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SKILL_NAME] TOOL_NAME | PARAMS | RESULT" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log
```

### 字段说明与示例

| 字段 | 格式 | 说明 |
|------|------|------|
| 时间戳 | `$(date '+%Y-%m-%d %H:%M:%S')` | Shell 注入，无需手填 |
| SKILL_NAME | `target-intel` / `disease-intel` / `company-intel` / `mnc-strategy` | 当前执行的 skill 名 |
| TOOL_NAME | 完整 MCP 工具名，如 `ls_drug_search` | |
| PARAMS | 关键参数，格式 `key=value` 用空格分隔 | 只写影响结果的核心参数，不写 limit/lang 等通用参数 |
| RESULT | `OK:N条` / `OK:无结果` / `ERR:错误信息` | |

**写入示例：**

```bash
# 搜索类
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [target-intel] ls_drug_search | target=ALK7 | OK:23条" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log

# fetch 类
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [target-intel] ls_drug_fetch | drug_id=578a6311... | OK" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log

# 向量搜索
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [disease-intel] ls_patent_vector_search | query=ALK7 inhibitor obesity | OK:15条" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log

# 失败
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [company-intel] ls_organization_fetch | entity_id=abc123 | ERR:timeout" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log
```

### 并行调用的处理

多个 MCP 工具并行调用时，每个工具各自完成后**分别**写入一行，无需合并。`echo ... >> file` 的追加写入在 shell 层面是原子操作，并发无冲突。

### 调用统计（每次 skill 结束时写入分隔符）

每次完整 skill 执行结束后，追加一行汇总：

```bash
echo "--- [$(date '+%Y-%m-%d %H:%M:%S')] [SKILL_NAME] 完成 | 总调用:N次 | 主题:TARGET_OR_DISEASE_NAME ---" \
  >> /Users/nihil/Claude/bio-intelligence/logs/mcp_calls.log
```

---

## 数据可信度框架（Data Governance）

### 来源分级（Source Tier）

| 等级 | 标记 | 来源类型 | 解释 |
|------|------|---------|------|
| **S** | 🟢 S | MCP `*_fetch`（带唯一 ID） | 数据库原始记录，ID 可复现验证 |
| **A** | 🟢 A | MCP `*_search`（结构化检索） | 经索引结构化数据，ID 列表可追溯 |
| **B** | 🟡 B | MCP `*_vector_search`（语义检索） | 语义匹配，重要数值应用 fetch 交叉验证 |
| **W** | 🟡 W | `ls_web_search` 补充 | MCP 无数据时的公开网络信息 |
| **C** | 🔴 C | Claude 模型推断 / 综合分析 | 非实测数据；必须列出所依赖的具体数据点 |

### 核实验证规则（6条，强制执行）

- **R1 临床数据**（mPFS/OS/ORR/批准日期）：必须来自 `*_fetch` [S]，附 trial_id / drug_id；仅 vector_search 来源标注 `⚠ 待 fetch 验证`
- **R2 市场/流行病学/融资数据**：注明数据机构 + 预测年份；推算数据写明公式和区间；Claude 知识标注 `[C, 截至 2025-08]`
- **R3 BD 交易金额**：来自 `drug_deal_fetch.deal_value` [S]；`disclosed=false` 时标注 `[金额未披露]`，禁止推测
- **R4 定性判断**（评分、评级、KOL 认定）：必须标注 `[C]` + 列出至少 2 个 S/A/B 级依据数据点
- **R5 MCP 无数据处理链**：MCP 空 → `ls_web_search`(1次) → 仍无则在报告中显式写明「数据缺失，以下为推断 [C]」
- **R6 关联公司展开（强制）**：BD 交易 / 管线 / 临床试验检索时，必须同时检索目标公司的**关联实体**（子公司、母公司、合作 NewCo、国际授权主体），不能仅搜索品牌最知名的那个名字。见下方《关联公司识别与展开规程》。

### 行内标注格式

```
数值/结论 [等级, 来源ID或工具名]
```
例：`mPFS 27.5mo [S, ct_result: 028e294]` | `市场$78亿 [W, GlobalData]` | `评级：高 [C, 依据: 数据A(S)+数据B(A)]`

---

## 关联公司识别与展开规程（R6 详细说明）

> **触发条件**：凡执行 `ls_drug_deal_search` / `ls_drug_search` / `ls_clinical_trial_search` / `ls_patent_search` 时，**必须**先完成本规程，再发出检索请求。

### Step A：识别关联实体

用 `ls_organization_fetch` 获取目标公司的子公司/母公司结构，同时结合 Claude 知识列举：

```
ls_organization_fetch(organization=["<目标公司>"])
# 检查返回的 subsidiaries / parent_company / affiliates 字段
```

**重点关注以下关联模式（高漏检风险）：**

| 模式 | 典型场景 | 示例 |
|------|---------|------|
| 中国公司 + 国际授权主体 | 境内运营公司 / 境外合作子公司名称不同 | 华深智药 → Helixon Therapeutics → **Earendil Labs**（对外 BD 主体） |
| MNC 全资子公司 | MNC 以子公司名义签约 | Sanofi Genzyme、Sanofi Pasteur、Synthorx（被收购后以原名签协议） |
| 合资/平台 NewCo | 两家公司成立的独立合作实体 | 罗氏+合作方 → JointCo Ltd. |
| 原研公司被收购后 | 数据库仍用原公司名索引 | Principia Biopharma（→ Sanofi）的专利/临床仍挂 Principia |
| License 分区主体 | 同一产品不同地区的授权主体不同 | 全球权益在 Co. A，Greater China 在 Co. B |

**中国公司特别说明**：中国创新药公司通常有三层主体：
1. **境内实体**（有限公司，A 股 / 非上市）— MCP 可能用中文名索引
2. **境外上市/持股实体**（开曼/BVI 注册，港股/美股）— MCP 可能用英文名索引
3. **国际 BD 专属主体**（单独注册，用于对外 License-out）— MCP **最可能漏收**

### Step B：展开检索实体列表

将识别到的所有关联名称加入搜索参数：

```python
# 示例：检索 Helixon/Earendil 相关的所有 BD 交易
ls_drug_deal_search(
    licensor=["Helixon Therapeutics", "Earendil Labs", "华深智药", "华深智药科技（北京）有限公司"],
    limit=30
)

# 示例：检索 Sanofi 旗下各主体作为 licensor 的交易
ls_drug_deal_search(
    licensor=["Sanofi", "Sanofi Genzyme", "Sanofi Pasteur", "Regeneron Pharmaceuticals"],
    limit=40
)
```

### Step C：MCP 仍无结果时的补救

若上述展开检索仍返回 0 条，按以下顺序补救：

1. `ls_news_vector_search(query="<公司名> deal license acquisition partner", lang="EN/CN", top_k=15)`
2. `ls_web_search(query="<公司名> <关联公司名> deal license 2024 2025")`
3. 在报告中显式标注 `⚠ MCP数据库未收录（疑似覆盖盲区）`，数据来源标注 `[W]`

### Step D：报告中的标注要求

关联公司来源的数据必须在报告中注明关联关系：

```
Earendil Labs（Helixon Therapeutics 关联 BD 主体）$1.85B [W] — MCP未收录
```

### 已知高漏检公司类型（优先展开）

- 中国 AI 药物发现公司（Insilico Medicine、晶泰科技、华深智药等）
- 中国 Biotech 的国际授权子公司（信达/信达生物国际、百济神州 BeiGene 国际主体等）
- 被 MNC 收购但仍以原名运营的子公司（Blueprint Medicines → Sanofi 收购后 6 个月内）
- 合作 NewCo / 平台公司（两家公司联合设立，名称与母公司完全不同）

---

## HTML 报告通用规范（v1.2，Takeda 风格标准）

> **规范版本 v1.2**。以 `/Users/nihil/Claude/bio-intelligence/drug_analysis/takeda_mnc_strategy_report.html` 为设计基准。
> 所有 skills 输出的 HTML 报告必须遵循本节规范，不使用旧版 sidebar 或 cv-wrap 方式。

---

### CSS 变量 & 基础

```css
:root {
  --bg: #0d1117;  --surface: #161b22;  --surface2: #21262d;  --border: #30363d;
  --accent: #f0883e;  --accent2: #d4702e;
  --text: #e6edf3;  --text-muted: #8b949e;
  --green: #3fb950;  --blue: #58a6ff;  --purple: #bc8cff;
  --red: #f85149;  --yellow: #d29922;
}
/* 主色调按报告类型：#f0883e 战略/BD · #58a6ff 靶点/科研 · #3fb950 适应症/流行病 */
```

JS 依赖：**仅 Chart.js CDN**，不引入其他库。

---

### 打印 CSS（每份报告 head 开头必含）

```css
@page { size: A3 landscape; margin: 12mm 14mm; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  nav { display: none !important; }
  section { page-break-inside: avoid; border-bottom: 1px solid #30363d; }
  canvas { max-height: 200px !important; }
  .filter-bar, .tab-bar { display: none; }
  .tab-pane { display: block !important; margin-bottom: 10px; }
  .container { max-width: 100%; padding: 0 8px; }
  body { font-size: 12px; }
  td, th { padding: 6px 10px; font-size: 12px; }
}
```

---

### 导航栏（横向顶部 sticky）

```css
nav {
  position: sticky; top: 0; z-index: 100;
  background: rgba(13,17,23,0.95); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 4px;
  padding: 0 24px; height: 52px; overflow-x: auto;
}
.nav-brand { font-weight: 700; color: var(--accent); margin-right: 16px; font-size: 15px; white-space: nowrap; }
nav a { color: var(--text-muted); text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; transition: all 0.2s; white-space: nowrap; }
nav a:hover, nav a.active { background: var(--surface2); color: var(--text); }
```

HTML 结构（无需外层 wrapper div）：
```html
<nav>
  <div class="nav-brand">公司名 MNC 战略</div>
  <a href="#products" class="active">Top产品</a>
  <a href="#patent-cliff">专利悬崖</a>
  <a href="#bd-history">BD历史</a>
  ...
</nav>
```

Nav 高亮用 **scroll 事件**（不用 IntersectionObserver）：
```js
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('nav a');
window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(s => { if (window.scrollY >= s.offsetTop - 80) current = s.id; });
  navLinks.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + current));
});
```

---

### Hero 区（每份报告必含）

```html
<div class="hero">
  <div class="hero-inner">
    <div class="badges">
      <span class="badge badge-mcp">📡 MCP 实时数据</span>
      <span class="badge badge-ai">🧠 Claude 知识融合</span>
      <span class="badge badge-date">📅 currentDate</span>
    </div>
    <h1>公司名 <span>英文名</span> — MNC 战略资产需求分析</h1>
    <div class="hero-sub">从已上市产品逆向推断 BD/M&A 资产需求逻辑</div>
    <div class="stats-row">
      <div class="stat"><div class="stat-val">$XB</div><div class="stat-label">年收入</div></div>
      <div class="stat"><div class="stat-val">~$XB</div><div class="stat-label">市值</div></div>
      <div class="stat"><div class="stat-val">n=X</div><div class="stat-label">已批准品种</div></div>
      <div class="stat"><div class="stat-val">XXXX</div><div class="stat-label">最大 LOE 窗口</div></div>
    </div>
  </div>
</div>
```

CSS：
```css
.hero { background: linear-gradient(135deg, #1a0a00 0%, #0d1117 50%, #0a0d1a 100%); border-bottom: 1px solid var(--border); padding: 48px 24px 40px; }
.hero-inner { max-width: 1200px; margin: 0 auto; }
.hero h1 { font-size: 32px; font-weight: 700; margin-bottom: 8px; }
.hero h1 span { color: var(--accent); }
.hero-sub { color: var(--text-muted); font-size: 15px; margin-bottom: 20px; }
.stats-row { display: flex; gap: 32px; flex-wrap: wrap; }
.stat-val { font-size: 28px; font-weight: 700; color: var(--accent); }
.stat-label { font-size: 12px; color: var(--text-muted); }
.badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid; }
.badge-mcp { background: rgba(88,166,255,0.1); border-color: var(--blue); color: var(--blue); }
.badge-ai { background: rgba(188,140,255,0.1); border-color: var(--purple); color: var(--purple); }
.badge-date { background: rgba(240,136,62,0.1); border-color: var(--accent); color: var(--accent); }
```

---

### 图表（Chart.js，v1.2 规范）

**使用 `maintainAspectRatio: true`（默认）+ CSS `canvas { max-height: Xpx }`**，不使用 cv-wrap div：

```html
<!-- 正确写法：在 chart-wrap 容器里直接写 canvas，通过 style 限高 -->
<div class="chart-wrap">
  <h3>图表标题</h3>
  <canvas id="myChart" style="max-height:280px;"></canvas>
</div>
```

```css
.chart-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }
canvas { max-height: 300px; }   /* 全局默认，各处可用 style 覆盖 */
```

Chart.js options 通用写法：
```js
options: {
  responsive: true, maintainAspectRatio: true,
  plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
  scales: {
    y: { grid: { color: '#30363d' }, ticks: { color: '#8b949e' } },
    x: { grid: { display: false }, ticks: { color: '#8b949e' } }
  }
}
```

---

### 标签（Tag）系统

```css
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-approved { background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid rgba(63,185,80,0.3); }
.tag-ph3 { background: rgba(88,166,255,0.15); color: var(--blue); border: 1px solid rgba(88,166,255,0.3); }
.tag-ph2 { background: rgba(188,140,255,0.15); color: var(--purple); border: 1px solid rgba(188,140,255,0.3); }
.tag-ph1 { background: rgba(240,136,62,0.15); color: var(--accent); border: 1px solid rgba(240,136,62,0.3); }
.tag-high { background: rgba(248,81,73,0.15); color: var(--red); border: 1px solid rgba(248,81,73,0.3); }
.tag-mid { background: rgba(240,136,62,0.15); color: var(--accent); border: 1px solid rgba(240,136,62,0.3); }
.tag-low { background: rgba(63,185,80,0.15); color: var(--green); border: 1px solid rgba(63,185,80,0.3); }
.tag-lic { background: rgba(88,166,255,0.1); color: var(--blue); border: 1px solid rgba(88,166,255,0.3); }
.tag-acq { background: rgba(188,140,255,0.1); color: var(--purple); border: 1px solid rgba(188,140,255,0.3); }
```

### 数据源标记（.src / .src-ai）

```css
.src { font-size: 10px; padding: 1px 6px; border-radius: 3px; background: rgba(88,166,255,0.1); color: var(--blue); border: 1px solid rgba(88,166,255,0.2); }
.src-ai { background: rgba(188,140,255,0.1); color: var(--purple); border-color: rgba(188,140,255,0.2); }
```

用法：`<span class="src">📡 MCP</span>` / `<span class="src-ai">🧠 Claude</span>`

### Alert 框（替代旧版 .warn / .note）

```css
.alert { border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; border-left: 3px solid; font-size: 13px; }
.alert-warn { background: rgba(210,153,34,0.1); border-color: var(--yellow); color: #e3c06a; }
.alert-info { background: rgba(88,166,255,0.1); border-color: var(--blue); color: var(--blue); }
.alert-ok   { background: rgba(63,185,80,0.1); border-color: var(--green); color: var(--green); }
```

### BD 表格客户端过滤

每行 `<tr>` 加 `data-cat="lic imm"` 属性，按空格分隔多个分类：
```html
<tr data-cat="lic imm">...</tr>   <!-- License-in, 免疫炎症 -->
<tr data-cat="acq rare">...</tr>  <!-- 收购, 罕见病 -->
```

过滤按钮与 JS：
```html
<div class="filter-bar" id="bdFilters">
  <button class="filter-btn active" onclick="filterBD('all',this)">全部</button>
  <button class="filter-btn" onclick="filterBD('lic',this)">License-in</button>
  <button class="filter-btn" onclick="filterBD('acq',this)">收购</button>
  <button class="filter-btn" onclick="filterBD('imm',this)">免疫炎症</button>
</div>
```
```js
function filterBD(cat, btn) {
  document.querySelectorAll('#bdFilters .filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#bdTable tbody tr').forEach(tr => {
    tr.style.display = (cat === 'all' || (tr.dataset.cat||'').includes(cat)) ? '' : 'none';
  });
}
```

### Tab 切换（Combo 节）

```html
<div class="tab-bar">
  <div class="tab active" onclick="switchTab('tab-a', this)">产品A</div>
  <div class="tab" onclick="switchTab('tab-b', this)">产品B</div>
</div>
<div id="tab-a" class="tab-pane active">...</div>
<div id="tab-b" class="tab-pane">...</div>
```
```js
function switchTab(id, el) {
  el.closest('section').querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  el.closest('.tab-bar').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
}
```

### Footer（报告末尾必含）

```html
<div style="background:var(--surface); border-top:1px solid var(--border); padding:24px; text-align:center; color:var(--text-muted); font-size:12px;">
  [公司名] MNC 战略资产需求分析 · 生成日期：currentDate · 数据来源：智慧芽 MCP 实时数据库 + Claude 知识融合 · 仅供参考，不构成投资建议
</div>
```

---

### 数据透明度（每份报告必含）

- 数据表格「来源」列统一使用 `.src` / `.src-ai` 徽标
- 推断/估算数据加 `<span class="src-ai">🧠 推断</span>` 行内标注
- **数据说明节（报告末尾必含）**：来源统计 / 数据缺失清单（含原因）/ 推断方法说明 / 截止日期

### 日期规范

**⚠ 报告内所有日期必须使用系统注入的 `currentDate`（格式 YYYY-MM-DD），禁止推断。**

---

## 可用 MCP 服务速查

| 服务 | 状态 | 主要用途 |
|------|------|---------|
| `pharma_intelligence` | ✅（需代理） | 药物/临床/专利/BD/靶点/疾病主力数据 |
| `biology_modality` | ✅ 直连 | 序列搜索、抗体-抗原、化学修饰 |
| `chemical_molecular` | ✅ 直连 | 结构搜索、ADMET、SAR、MCS |
| `patsap_patent_search` | ✅ 直连 | 语义+关键词专利/论文搜索（补充专利检索） |
| `patent_paper_fetch` | ✅ 直连 | 按专利号/论文ID拉取完整 Markdown 全文 |
| `novelty_search` | ❌ 后端 500 | 新颖性分析（暂不可用，等待智慧芽修复） |

### patsap_patent_search 使用要点

```
# 语义搜索（描述技术问题/机制）
patsnap_search(
  search_strategy=["semantic"],
  semantic_query="<自然语言描述技术方案>",
  sources=["patent"],
  topk=20
)

# 关键词+过滤（公司/IPC/日期）
patsnap_search(
  search_strategy=["keyword", "filter"],
  keywords=["<关键词1>", "<关键词2>"],
  filters={"assignees": ["<公司名>"], "ipc": ["<IPC分类>"]},
  sources=["patent"],
  topk=20
)
```

### patent_paper_fetch 使用要点

```
# 按专利号拉取全文（比 ls_patent_fetch 返回更完整的 Markdown）
patsnap_fetch(
  keys=["US10858431B2", "CN113456789A"],
  key_type="pn",
  module=["basic"]        # 可选: basic, citation, legal, family
)
```

> ⚠️ **US 专利 kind code 规则（已验证）**：
> - `US12409225` → 查不到（"未找到数据"）
> - `US12409225B2` → 成功
>
> | 局号 | kind code 规则 | 示例 |
> |------|--------------|------|
> | US 授权专利 | **必须加 `B2`（新）或 `B1`（旧）** | `US10858431B2` |
> | US 公开申请 | 加 `A1` | `US20260053798A1` |
> | WO | 加 `A1`（通常） | `WO2025265060A1` |
> | CN 授权 | 加 `B`（无数字） | `CN113456789B` |
> | EP | 加 `A1`/`B1` | `EP4123456B1` |
>
> **结论**：凡是 US 格式（无字母后缀）一律追加 `B2` 再 fetch。

---

## 智慧芽链接生成规则

> 使用 MCP 工具获取数据后，按以下规则将 ID 转为可点击的智慧芽链接写入报告。
> 所有链接均指向已登录状态下可直接访问的页面（需用户已登录智慧芽账号）。

### 链接格式总表

| 实体类型 | MCP 来源工具 | ID 字段名 | ID 格式 | 链接模板 |
|---------|------------|---------|---------|---------|
| **药物** | `ls_drug_search` / `ls_drug_fetch` | `drug_id` | 32位hex（无连字符） | `https://synapse.zhihuiya.com/drug/{drug_id}` |
| **靶点** | `ls_target_fetch` / `ls_target_search` | `target_id` | 32位hex | `https://synapse.zhihuiya.com/target/{target_id}` |
| **临床试验** | `ls_clinical_trial_fetch` / `ls_clinical_trial_search` | `clinical_trial_id` | 32位hex | `https://synapse.zhihuiya.com/clinical-trial/{clinical_trial_id}` |
| **机构/公司** | `ls_organization_fetch` | `entity_id` | 32位hex | `https://synapse.zhihuiya.com/organization/{entity_id}` |
| **文献/论文** | `ls_paper_search` / `ls_paper_fetch` | `id` | UUID（含连字符） | `https://synapse.zhihuiya.com/literature-detail/{id}` |
| **BD交易（新闻）** | `ls_drug_deal_search`（`url` 字段） | URL中的UUID | UUID（含连字符） | 直接使用 `url` 字段值（已是 `synapse.zhihuiya.com/news-detail/{uuid}`） |
| **BD交易列表** | `ls_drug_deal_search` | `deal_id` | 32位hex | `https://synapse.zhihuiya.com/drug-deal-list?query_id={deal_id}`（搜索结果页） |
| **专利** | `patsnap_search`（`id` 字段） | `id` | UUID（含连字符） | `https://analytics.zhihuiya.com/patent-view/abst?patentId={id}` |

### 从 `reference` 字段快速提取 ID

MCP 返回的每条记录均含 `reference` 字段，格式为 `{docType}:{docId}`，可直接解析：

```
drug:578a6311a2d547dc88ca94f2d2f7ca52          → synapse.zhihuiya.com/drug/578a6311...
target:d9ded8f23b4140a5828314a55d2d66b4         → synapse.zhihuiya.com/target/d9ded8f2...
clinical_trial:052408352250ae092423359d8a284e3a → synapse.zhihuiya.com/clinical-trial/052408...
organization:55a844658a7cda34eb4c5aa6fef0a5f1   → synapse.zhihuiya.com/organization/55a844...
paper:d1ac7589-e67d-3c94-a7ba-c0022ab3cd1c      → synapse.zhihuiya.com/literature-detail/d1ac7589...
drug_deal:282a295d2e282a8908aea882e95dae2d       → synapse.zhihuiya.com/drug-deal-list?query_id=282a...
```

> `paper` 类型的 URL 路径是 `literature-detail`，不是 `paper`，注意区分。

### 专利链接获取流程

专利链接需两步（不能直接从 `ls_patent_fetch` 结果构建）：

```
# Step 1：用 patsnap_search 获取专利的内部 UUID（id 字段）
patsnap_search(
  search_strategy=["keyword"],
  keywords=["WO2025265060A1"],   # 或公司名+关键词
  sources=["patent"],
  topk=5
)
# 返回结果中的 id 字段即为 patentId UUID

# Step 2：构建链接
https://analytics.zhihuiya.com/patent-view/abst?patentId={result.id}
```

> `ls_patent_search` 和 `ls_patent_fetch` **不返回** analytics.zhihuiya.com 所需的 patentId UUID；只有 `patsnap_search` 结果含 `id` 字段可用于构建专利链接。

### 实测 ID 快查表（常用品种）

| 品种 / 实体 | 类型 | ID | 链接 |
|------------|------|----|------|
| Daraxonrasib | 药物 | `578a6311a2d547dc88ca94f2d2f7ca52` | [Synapse](https://synapse.zhihuiya.com/drug/578a6311a2d547dc88ca94f2d2f7ca52) |
| Elironrasib | 药物 | `cb39e80d1a934997a778f27dc3a65f3a` | [Synapse](https://synapse.zhihuiya.com/drug/cb39e80d1a934997a778f27dc3a65f3a) |
| Zoldonrasib | 药物 | `a8f028501ba7405796ae61f90b3da872` | [Synapse](https://synapse.zhihuiya.com/drug/a8f028501ba7405796ae61f90b3da872) |
| ERAS-0015 | 药物 | `356f05e129104d99bf30f8a498eb9900` | [Synapse](https://synapse.zhihuiya.com/drug/356f05e129104d99bf30f8a498eb9900) |
| Naporafenib | 药物 | `dd2c5766cbdc4018b656afb3081288b4` | [Synapse](https://synapse.zhihuiya.com/drug/dd2c5766cbdc4018b656afb3081288b4) |
| KRAS | 靶点 | `d9ded8f23b4140a5828314a55d2d66b4` | [Synapse](https://synapse.zhihuiya.com/target/d9ded8f23b4140a5828314a55d2d66b4) |
| Revolution Medicines | 机构 | `55a844658a7cda34eb4c5aa6fef0a5f1` | [Synapse](https://synapse.zhihuiya.com/organization/55a844658a7cda34eb4c5aa6fef0a5f1) |
| US12409225（IP诉讼核心专利） | 专利 | `21d63b9c-14f2-4fc2-9d08-f2de78ccb16a` | [Analytics](https://analytics.zhihuiya.com/patent-view/abst?patentId=21d63b9c-14f2-4fc2-9d08-f2de78ccb16a) |
| WO2025265060A1 | 专利 | `9665b768-acab-4edc-ad02-248af58c54b6` | [Analytics](https://analytics.zhihuiya.com/patent-view/abst?patentId=9665b768-acab-4edc-ad02-248af58c54b6) |
| WO2022266069A1（ERASCA KRAS G12D）| 专利 | `4a45f5e2-a607-4fd9-af0c-f7fffa331705` | [Analytics](https://analytics.zhihuiya.com/patent-view/abst?patentId=4a45f5e2-a607-4fd9-af0c-f7fffa331705) |
