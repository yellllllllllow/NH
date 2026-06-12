# AI News Agent

一款基于 Python 和 PyQt5 开发的智能新闻聚合与处理桌面应用程序，集成 DeepSeek AI 服务，提供新闻搜索、AI 摘要生成、多语言翻译等功能。

## 功能特性

### 核心功能

- **多新闻源聚合** - 支持 7 个内置新闻源（NewsAPI、MIT Technology Review、Ars Technica、TechCrunch、Hacker News、Reddit、Wired）
- **AI 摘要生成** - 使用 DeepSeek AI 自动生成新闻摘要
- **多语言翻译** - 英文新闻自动翻译为简体中文
- **语义搜索** - 智能扩展搜索关键词，提高搜索精度
- **安全存储** - AES-256-GCM 加密存储 API 密钥

### 界面特性

- Chrome 风格现代化 UI 设计
- 新闻卡片式布局，支持原文/译文/摘要三栏展示
- 新闻源在线状态实时监控
- AI 服务可用性检测

## 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python 3.10+ |
| GUI 框架 | PyQt5 |
| AI 服务 | DeepSeek API (deepseek-v4-flash) |
| 数据加密 | AES-256-GCM (cryptography) |
| HTTP 请求 | requests |
| 打包工具 | PyInstaller |

## 项目结构

```
NH/
├── app/                          # 核心业务模块
│   ├── news_sources.py           # 新闻源定义与管理
│   ├── fetcher.py                # NewsAPI 新闻获取
│   ├── multi_fetcher.py          # 多源回退获取机制
│   ├── worker.py                 # 后台工作线程
│   ├── ai_service_monitor.py     # AI 服务状态监控
│   ├── prompts.py                # Prompt 模板管理
│   ├── semantic_search.py        # 语义搜索扩展
│   └── secure_storage.py         # API 密钥加密存储
│
├── ui/                           # PyQt5 界面组件
│   ├── main_window.py            # 主窗口
│   ├── news_panel.py             # 新闻卡片面板
│   ├── ai_settings_dialog.py     # AI 设置对话框
│   ├── source_manager_dialog.py  # 新闻源管理
│   └── prompt_dialog.py          # Prompt 管理对话框
│
├── main.py                       # 应用入口
├── config.json                   # 配置文件
├── prompts.json                  # Prompt 模板
├── requirements.txt              # 依赖列表
└── README.md                     # 项目文档
```

## 安装步骤

### 环境要求

- Python 3.10 或更高版本
- Windows 操作系统

### 安装依赖

```bash
# 克隆仓库
git clone https://github.com/yellllllllllow/NH.git
cd NH

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 配置 API Key

1. 获取 DeepSeek API Key：访问 [DeepSeek 平台](https://platform.deepseek.com/)
2. 首次运行时会提示输入 API Key，或通过菜单「AI 模型设置」进行配置
3. API Key 将使用 AES-256-GCM 加密存储在本地

### 运行应用

```bash
python main.py
```

### 打包为 EXE

```bash
pyinstaller news_agent.spec --clean
```

打包后的可执行文件位于 `dist/NH/` 目录。

## 使用方法

### 基本操作流程

1. **搜索新闻** - 在搜索框输入关键词，点击搜索按钮
2. **查看新闻** - 浏览新闻卡片，查看标题、摘要、来源等信息
3. **翻译新闻** - 点击「翻译」按钮，将英文新闻翻译为中文
4. **生成摘要** - 点击「生成摘要」按钮，获取 AI 分析的新闻摘要
5. **阅读原文** - 点击「阅读原文」按钮，在浏览器中打开完整新闻

### AI 设置

点击右上角菜单按钮（⋮）→「AI 模型设置」：

- **服务商选择**：支持 DeepSeek、硅基流动、Ollama（本地）
- **模型选择**：根据服务商选择合适的模型
- **API Key 管理**：输入、验证、保存 API Key
- **网络测试**：测试 AI 服务连通性

### 新闻源管理

点击菜单 →「新闻源管理」：

- 查看所有新闻源状态
- 启用/禁用特定新闻源
- 配置新闻源优先级

### Prompt 管理

点击菜单 →「Prompt 管理」：

- 自定义摘要生成 Prompt
- 自定义翻译 Prompt
- 导入/导出 Prompt 模板

## 支持的 AI 服务商

| 服务商 | Base URL | 可用模型 |
|--------|----------|----------|
| DeepSeek | https://api.deepseek.com | deepseek-v4-flash, deepseek-v4-pro, deepseek-chat, deepseek-reasoner |
| 硅基流动 | https://api.siliconflow.cn | Qwen/Qwen2-72B-Instruct, deepseek-ai/DeepSeek-V2-Chat |
| Ollama (本地) | http://localhost:11434 | llama3.2, qwen2.5, qwen2.5-coder, deepseek-r1 |

## 贡献指南

### 代码提交规范

请使用以下格式的提交信息：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**：
```
feat(ai): add support for custom prompt templates

- Add prompt dialog for managing custom prompts
- Support import/export of prompt templates
- Add validation for prompt syntax

Closes #123
```

### 分支管理策略

- `main` - 主分支，保持稳定可发布状态
- `develop` - 开发分支，新功能合并到此分支
- `feature/*` - 功能分支，从 develop 创建
- `bugfix/*` - Bug 修复分支
- `release/*` - 发布准备分支

### PR 流程

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature-name`
3. 提交更改：`git commit -m "feat: your feature description"`
4. 推送分支：`git push origin feature/your-feature-name`
5. 创建 Pull Request 到 `develop` 分支
6. 等待代码审查和合并

### 代码风格

- 遵循 PEP 8 编码规范
- 使用 4 空格缩进
- 函数和类添加文档字符串
- 保持代码简洁，避免过度复杂化

## 许可证

本项目仅供学习和研究使用。

## 相关链接

- [DeepSeek 平台](https://platform.deepseek.com/)
- [NewsAPI 文档](https://newsapi.org/docs)
- [PyQt5 文档](https://www.riverbankcomputing.com/static/Docs/PyQt5/)

## 更新日志

### v2.1
- 修复模型名称配置错误（v4flash → deepseek-v4-flash）
- 完善配置文件结构
- 优化 AI 服务连接测试
- 添加完整的 API Key 验证机制
