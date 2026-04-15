# ============================================================
# AI联盟 Notion 同步系统
# ============================================================

这个项目用于将本地 Markdown 文件同步到 Notion。

## 📁 项目结构

```
e:\Founders Wall\
├── sync_to_notion.py          # 同步脚本
├── requirements.txt            # Python依赖
├── .github/
│   └── workflows/
│       └── sync-to-notion.yml # GitHub Action工作流
├── Notion系统/                 # Notion数据库结构文档
│   ├── 00-Notion-1.0-系统架构.md
│   ├── 01-Memory-记忆库.md
│   ├── 02-Agents-节点库.md
│   ├── 03-Projects-项目系统.md
│   ├── 04-Flows-流程系统.md
│   ├── 05-Knowledge-知识库.md
│   └── 06-Dashboard-仪表盘.md
└── AI创业者联盟/               # 其他文档
```

## 🚀 快速开始

### 1. 配置 Notion Integration

1. 访问 [Notion Developers](https://www.notion.so/my-integrations)
2. 点击 "New integration"
3. 填写名称（如 "AI联盟同步"）
4. 选择工作空间
5. 复制 API Token

### 2. 设置 Database

在 Notion 中创建以下 Database，并分享给 Integration：

- **Memory** - 记忆库
- **Agents** - Agent节点库
- **Projects** - 项目系统
- **Flows** - 流程系统
- **Knowledge** - 知识库
- **Default** - 默认数据库

每个 Database 需要包含以下属性：
- `Name` (Title)
- `Type` (Select)
- `Tags` (Multi-select)
- `Importance` (Select: ★★★★★ 到 ★☆☆☆☆)
- `Status` (Select)
- `Source` (Select)
- `File Path` (Text)

### 3. 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret Name | Description |
|------------|-------------|
| NOTION_API_TOKEN | Notion Integration Token |
| NOTION_DATABASE_DEFAULT | 默认数据库 ID |
| NOTION_DATABASE_MEMORY | 记忆库数据库 ID |
| NOTION_DATABASE_AGENTS | Agent节点库数据库 ID |
| NOTION_DATABASE_PROJECTS | 项目系统数据库 ID |
| NOTION_DATABASE_FLOWS | 流程系统数据库 ID |
| NOTION_DATABASE_KNOWLEDGE | 知识库数据库 ID |

### 4. 获取 Database ID

从 Notion Database URL 获取 ID：
```
https://notion.so/workspace/DATABASE_ID?v=xxx
                         ^^^^^^^^^^^^
                         这是 Database ID（32位）
```

## 🔄 同步规则

### 文档类型自动识别

| 文件名/内容 | 同步到 Database |
|------------|----------------|
| 包含"记忆库" | Memory |
| 包含"节点库"/"Agents" | Agents |
| 包含"项目系统"/"Projects" | Projects |
| 包含"流程系统"/"Flows" | Flows |
| 包含"知识库"/"知识" | Knowledge |
| 其他 | Default |

### Frontmatter 支持

```markdown
---
title: 文档标题
type: memory
tags: AI, 创业
importance: 5
status: 已处理
source: local
---

# 文档内容
```

## 📝 本地使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 设置环境变量

```bash
export NOTION_API_TOKEN="your-token-here"
export NOTION_DATABASE_DEFAULT="your-database-id"
```

### 运行同步

```bash
# 同步全部
python sync_to_notion.py

# 同步指定目录
python sync_to_notion.py --subdir "AI创业者联盟/Notion系统"

# Dry run（仅解析不实际同步）
python sync_to_notion.py --dry-run
```

## ⚙️ GitHub Action 自动同步

每次推送到 main 分支，都会自动触发同步：

1. 代码推送到 GitHub
2. GitHub Action 自动运行
3. 脚本解析 Markdown 文件
4. 调用 Notion API 创建/更新页面
5. 同步结果记录到日志

### 手动触发

可以在 GitHub Actions 页面手动触发：
1. 进入仓库 → Actions
2. 选择 "Sync to Notion"
3. 点击 "Run workflow"
4. 可选填入子目录参数

## 🛠️ 自定义

### 修改同步逻辑

编辑 `sync_to_notion.py` 中的 `MarkdownParser` 和 `MarkdownToNotionConverter` 类。

### 添加新的 Database

1. 在 Notion 创建新 Database
2. 添加到 `DATABASE_MAPPING` 和 `TYPE_TO_DATABASE`
3. 在 GitHub Secrets 中添加新的 Database ID
4. 更新 GitHub Action workflow

## 📊 统计

同步脚本会记录：
- 创建的页面数
- 更新的页面数
- 跳过的文件数
- 错误数

## ⚠️ 注意事项

1. **API 限制**: Notion API 每秒最多 3 次请求
2. **内容长度**: Notion block 内容有大小限制
3. **同步方向**: 当前为单向同步（GitHub → Notion）
4. **文件路径**: 用于追踪已存在的页面，请勿随意修改

## 🔒 安全

- API Token 存储在 GitHub Secrets
- 不提交敏感信息到仓库
- 使用环境变量传递配置

## 📄 License

MIT License
