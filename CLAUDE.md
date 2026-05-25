# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`bio-intelligence/` — 药物情报分析工具集。所有分析技能均基于 **PatSnap 智慧芽 MCP 服务**（`ls_*` 工具集），不依赖任何本地数据库或外部代码。输出为交互式 HTML 报告，保存至 `/Users/nihil/Claude/`。

## MCP 服务配置

所有 skills 均依赖本地 MCP Schema 代理（`mcp_proxy.py`），代理再转发至智慧芽服务器。

**必须先启动全部四个代理，再使用任何 skill：**

```bash
# 每次新会话前执行一次（四个服务各占一个端口）：
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &                                                    # pharma_intelligence → :3099
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py --port 3100 --upstream https://connect.zhihuiya.com/06e741/logic-mcp &   # biology_modality → :3100
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py --port 3101 --upstream https://connect.zhihuiya.com/713886/logic-mcp &   # chemical_molecular → :3101
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py --port 3102 --upstream https://connect.zhihuiya.com/2b0355/logic-mcp &   # patsap_patent_search → :3102

# 验证代理已就绪：
/mcp
# 确认四个服务均显示 Connected
```

> **为什么四个服务都需要代理？** PatSnap 所有 MCP 服务器的工具 `inputSchema` 属性中
> 均含有 `anyOf`/`oneOf`/`allOf`，Claude API 一律拒绝（400 错误）。
> `mcp_proxy.py` 透明地递归去除这些 combiner 后再转发给 Claude Code，不影响工具功能。
> MCP 配置：pharma_intelligence → :3099，biology_modality → :3100，chemical_molecular → :3101，patsap_patent_search → :3102。

## Skills

所有 skills 位于 `.claude/commands/`，在此目录下打开 Claude Code 即可通过 `/skill-name` 调用：

| Skill | 命令 | 核心问题 |
|-------|------|---------|
| 靶点立项情报 | `/target-intel <靶点> [模态]` | 这个靶点值不值得立项？ |
| 适应症全景 | `/disease-intel <疾病> [市场/治疗线]` | 这个适应症有哪些机会？ |
| 公司全维度情报 | `/company-intel <公司> [维度]` | 这家公司的管线/平台/BD全貌？ |
| MNC 战略需求 | `/mnc-strategy <MNC> [领域]` | 这家大药企最想买什么资产？ |

示例：`/target-intel ALK7 siRNA`、`/disease-intel NSCLC`、`/mnc-strategy AstraZeneca 肿瘤`

## 通用执行模式（所有 skills 共享）

每个 skill 均遵循 7 步流程：

1. **解析参数** — 提取靶点/疾病/公司名、模态偏好、聚焦维度
2. **实体标准化** — `ls_ner_nor_normalize()` 单独调用，获取标准化 ID + 别名（后续查询均用标准化名称）
3. **广度并行扫描** — 10-15 个结构化工具同时发出（drug_search、patent_search、clinical_trial_search、deal_search、paper_search 等）
4. **深度向量挖掘** — 按模态/疾病类型分支，并行发出 `*_vector_search` 语义检索
5. **重点数据拉取** — 对 Step 3-4 筛选出的关键条目批量 `*_fetch` 获取全文
6. **生成 HTML 报告** — 深色主题、sticky 导航、Chart.js 图表、交互式筛选/排序，保存至 `/Users/nihil/Claude/<name>_<type>_report.html`
7. **输出摘要** — 含 MCP 数据覆盖统计、核心发现、综合评分、报告路径

**关键约束**：
- Step 2（实体标准化）必须单独调用，在 Step 3 之前完成
- 结构化搜索（`_search`）优先，向量搜索（`_vector_search`）作为补充
- MCP 无结果时回退至 `ls_web_search`，并在报告中标注数据来源
- HTML 报告日期必须使用系统注入的 `currentDate`，禁止推断

## 主要 MCP 工具分类

| 类型 | 工具 |
|------|------|
| 实体标准化 | `ls_ner_nor_normalize` |
| 结构化搜索 | `ls_drug_search`, `ls_patent_search`, `ls_clinical_trial_search`, `ls_drug_deal_search`, `ls_paper_search`, `ls_translational_medicine_search`, `ls_clinical_trial_result_search` |
| 向量语义搜索 | `ls_*_vector_search`（patent/paper/clinical_trial/epidemiology/news/financial_report/guideline/fda_label） |
| 详情拉取 | `ls_*_fetch`（drug/patent/paper/clinical_trial/drug_deal/organization/translational_medicine 等） |
| 补充 | `ls_web_search` |

## 报告输出规范

- **保存路径**：`/Users/nihil/Claude/<name>_<type>_report.html`（`_report` 后缀统一）
- **配色**：深色底 `#0d1117`，主色按靶点类别/疾病类型/公司类型区分（蓝/红/绿/紫/橙/金）
- **图表库**：Chart.js CDN（唯一 JS 依赖）
- `/mnc-strategy` 的核心可视化是**专利悬崖瀑布图**（x=年份，y=收入敞口）
