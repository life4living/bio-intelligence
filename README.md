# Bio Intelligence — 药物情报分析工具集

基于 **PatSnap 智慧芽 MCP** 的深度药物情报 skill 集，运行于 Claude Code。

## Skills

| 命令 | 功能 | 核心问题 |
|------|------|---------|
| `/target-intel <靶点> [模态]` | 靶点立项情报分析 | 这个靶点值不值得立项？ |
| `/disease-intel <疾病> [聚焦]` | 适应症全景情报 | 这个适应症有哪些机会？ |
| `/company-intel <公司> [维度]` | 制药公司全维度情报 | 这家公司的管线/平台/BD全貌？ |
| `/mnc-strategy <MNC> [领域]` | MNC 战略资产需求 | 这家大药企最想买什么资产？ |

示例：
```
/target-intel ALK7 siRNA
/disease-intel NSCLC 中国
/company-intel 恒瑞医药
/mnc-strategy AstraZeneca 肿瘤
```

## 依赖的 MCP 服务

| 服务 | 工具数 | 用途 |
|------|--------|------|
| pharma_intelligence | 30 | 药物/临床/专利/BD 主力数据库 |
| biology_modality | 8 | 序列搜索、抗体-抗原分析 |
| chemical_molecular | 7 | 结构搜索、ADMET、SAR |
| patsap_patent_search | 2 | 语义+关键词专利搜索 |
| patent_paper_fetch | 1 | 专利/论文全文拉取 |
| novelty_search | 23 | 新颖性分析（当前不可用，后端 500） |

## 启动代理（每次新会话必须）

`pharma_intelligence` 需要本地代理来修复 schema 兼容性问题：

```bash
python3.10 /Users/nihil/Claude/bio-intelligence/mcp_proxy.py &
```

详见 `KNOWN_ISSUES.md`。

## 文件结构

```
bio-intelligence/
├── .claude/
│   └── commands/
│       ├── _shared.md          # 公共模块：Pre-flight + 数据治理框架
│       ├── target-intel.md
│       ├── disease-intel.md
│       ├── company-intel.md
│       └── mnc-strategy.md
├── mcp_proxy.py                # pharma_intelligence 代理（修复 anyOf schema）
├── CLAUDE.md                   # Claude Code 项目配置
├── KNOWN_ISSUES.md             # MCP 已知问题与数据质量规则
└── README.md
```
