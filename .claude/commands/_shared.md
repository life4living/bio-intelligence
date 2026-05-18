# _shared.md — 公共模块（所有 skills 共用）

> 本文件由各 skill 在执行前 Read 加载。包含：Pre-flight 连接检查、数据治理框架、HTML 通用规范。

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

## 数据可信度框架（Data Governance）

### 来源分级（Source Tier）

| 等级 | 标记 | 来源类型 | 解释 |
|------|------|---------|------|
| **S** | 🟢 S | MCP `*_fetch`（带唯一 ID） | 数据库原始记录，ID 可复现验证 |
| **A** | 🟢 A | MCP `*_search`（结构化检索） | 经索引结构化数据，ID 列表可追溯 |
| **B** | 🟡 B | MCP `*_vector_search`（语义检索） | 语义匹配，重要数值应用 fetch 交叉验证 |
| **W** | 🟡 W | `ls_web_search` 补充 | MCP 无数据时的公开网络信息 |
| **C** | 🔴 C | Claude 模型推断 / 综合分析 | 非实测数据；必须列出所依赖的具体数据点 |

### 核实验证规则（5条，强制执行）

- **R1 临床数据**（mPFS/OS/ORR/批准日期）：必须来自 `*_fetch` [S]，附 trial_id / drug_id；仅 vector_search 来源标注 `⚠ 待 fetch 验证`
- **R2 市场/流行病学/融资数据**：注明数据机构 + 预测年份；推算数据写明公式和区间；Claude 知识标注 `[C, 截至 2025-08]`
- **R3 BD 交易金额**：来自 `drug_deal_fetch.deal_value` [S]；`disclosed=false` 时标注 `[金额未披露]`，禁止推测
- **R4 定性判断**（评分、评级、KOL 认定）：必须标注 `[C]` + 列出至少 2 个 S/A/B 级依据数据点
- **R5 MCP 无数据处理链**：MCP 空 → `ls_web_search`(1次) → 仍无则在报告中显式写明「数据缺失，以下为推断 [C]」

### 行内标注格式

```
数值/结论 [等级, 来源ID或工具名]
```
例：`mPFS 27.5mo [S, ct_result: 028e294]` | `市场$78亿 [W, GlobalData]` | `评级：高 [C, 依据: 数据A(S)+数据B(A)]`

---

## HTML 报告通用规范

### 基础设计

- 深色主题：背景 `#0d1117`，表面 `#161b22`，次表面 `#21262d`
- 固定顶部导航（sticky nav），各节滚动时自动高亮
- Hero 区显示 `📡 MCP实时数据` + `🧠 Claude知识融合` 双徽章 + MCP 检索量统计
- JS 依赖：仅 Chart.js CDN，不引入其他库

### 数据透明度（每份报告必含）

- 数据表格增加「可信度」列：🟢 S/A（数据库直接记录）🟡 B/W（搜索/网络）🔴 C（模型推断）
- 关键数值附上标引用编号 `[n]`，对应报告末尾参考列表（tool name + record ID）
- 推断/估算数据用斜体 + `（推断）` 或 `（估算，±X%）` 标注
- **数据说明节（报告末尾必含）**：来源统计 / 关键引用列表 / 数据缺失清单（缺失原因 + 对结论影响）/ 推断方法 / 截止日期 `currentDate`

### 日期规范

**⚠ 报告生成日期必须使用系统注入的 `currentDate`（格式 YYYY-MM-DD），禁止使用训练截止年份推断。文件内所有年份字段在写入前统一核查。**

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
