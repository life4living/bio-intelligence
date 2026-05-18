# 已知问题与解决方案汇总

基于实际调研案例（OX40 全模态，2026-05-15）积累的 MCP 工具使用经验。

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

---

# MCP 协议层错误

以下问题发生在工具调用的**基础设施层**（Claude API ↔ MCP Server 通信层），与数据内容无关。已用 `mcp_proxy.py` 作为本地代理统一处理。

---

## MCP Error A：`inputSchema` 顶层 `anyOf` 导致 Claude API 400 错误

**现象**
Claude Code 启动时或调用任意 `ls_*` 工具时，返回 400 Bad Request。所有工具均不可用，报错信息类似：
```
Error: 400 {"type":"error","error":{"type":"invalid_request_error",
"message":"tools.N.custom.input_schema: Input validation error..."}}
```

**根因**
智慧芽 MCP server 的 15 个工具在 `inputSchema` **根层**使用了 `anyOf`（或 `oneOf`/`allOf`），其语义是"以下参数至少需要传一个"。例如：
```json
{
  "inputSchema": {
    "anyOf": [
      { "required": ["drug_name"] },
      { "required": ["target"] },
      { "required": ["organization"] }
    ],
    "properties": { ... }
  }
}
```
Claude API（Anthropic）的工具规范要求 `inputSchema` **根层必须是 `type: object`**，不允许在根层使用 JSON Schema 组合关键字（`anyOf/oneOf/allOf`）。这是 Claude API 的设计约束，而非智慧芽的单方面问题。但两者规范不兼容，导致注册工具时全量失败。

**解决方案（当前）：临时 Workaround**
在本地运行 `mcp_proxy.py`，代理拦截 `tools/list` 响应并在返回给 Claude Code 之前：
1. 剥离 `inputSchema` **根层**的 `anyOf/oneOf/allOf`
2. 递归处理嵌套属性中的 `anyOf/oneOf/allOf`（`[real_type, null]` → `real_type`）

```bash
# 每次新会话前执行：
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &
```

代理运行在 `http://127.0.0.1:3099/mcp`，已配置为 Claude Code 的 MCP 端点。

**解决方案性质**：**临时（Workaround）**
- 优点：完全透明，不影响工具功能；不修改上游服务器
- 缺点：每次新会话需手动启动代理；代理进程意外退出后工具全部失效；需要 Python 3.10+ 环境
- 不稳定场景：代理端口被占用（换 `PROXY_PORT`）；MCP 协议版本升级后 SSE 格式变化

**永久解决方案（需 PatSnap 配合）**
智慧芽需将工具的 `inputSchema` 改为符合 Claude API 规范的格式：
```json
// 修改前（当前，Claude API 不支持）
{
  "inputSchema": {
    "anyOf": [{"required": ["drug_name"]}, {"required": ["target"]}],
    "properties": { "drug_name": {...}, "target": {...} }
  }
}

// 修改后（标准写法：所有参数设为可选，description 说明约束）
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "drug_name": { "type": "string", "description": "Drug name (required if target not provided)" },
      "target": { "type": "string", "description": "Target gene (required if drug_name not provided)" }
    }
  }
}
```
这不会损失任何功能，服务端仍可在收到请求后做参数校验。

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
