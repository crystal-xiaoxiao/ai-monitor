# AI Native App Monitor

全球 AI Native App + Foundation Model 实时监控 Dashboard。
追踪 OpenAI、Anthropic、Cursor、Perplexity 等核心公司的 ARR、估值、Token 消耗等指标。
每天 UTC 08:00（北京时间 16:00）自动更新数据。

---

## 🚀 部署步骤（15分钟完成）

### 第一步：创建 GitHub 仓库

1. 登录 [github.com](https://github.com) → 点击右上角 **+** → **New repository**
2. 仓库名填：`ai-monitor`（或任意名称）
3. 选 **Public**（GitHub Pages 免费托管需要 Public）
4. 不要勾选任何初始化选项，直接 **Create repository**

### 第二步：上传文件

把这个 zip 包里的所有文件上传到仓库：

**方法A（网页拖拽，最简单）：**
- 进入仓库页面 → 点击 **Add file** → **Upload files**
- 把 `index.html`、`data.json`、`update_data.py` 拖入
- 提交（Commit changes）

**方法B（命令行）：**
```bash
cd ai-monitor
git init
git remote add origin https://github.com/你的用户名/ai-monitor.git
git add .
git commit -m "init: AI monitor dashboard"
git push -u origin main
```

上传 `.github/workflows/daily-update.yml` 时需要先创建这个目录结构。
如果用网页上传，在文件名处直接输入 `.github/workflows/daily-update.yml`，GitHub 会自动建目录。

### 第三步：开启 GitHub Pages

1. 仓库页面 → **Settings** → 左侧 **Pages**
2. Source 选择：**Deploy from a branch**
3. Branch 选：**main**，目录选：**/ (root)**
4. 点击 **Save**

等约 1 分钟，页面顶部会显示你的网址，类似：
```
https://你的用户名.github.io/ai-monitor
```

### 第四步：配置自动更新（需要 Anthropic API Key）

1. 仓库页面 → **Settings** → 左侧 **Secrets and variables** → **Actions**
2. 点击 **New repository secret**
3. Name 填：`ANTHROPIC_API_KEY`
4. Secret 填：你的 Anthropic API Key（从 [console.anthropic.com](https://console.anthropic.com) 获取）
5. 点击 **Add secret**

配置完成后，每天 UTC 08:00 会自动运行 `update_data.py`，用 Claude API 搜索最新 AI 行业新闻，有确认数据时更新 `data.json` 并自动部署。

**手动触发更新：**
- 仓库页面 → **Actions** → **Daily Data Update** → **Run workflow**

---

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `index.html` | Dashboard 前端，从 `data.json` 动态加载数据 |
| `data.json` | 所有数据（每日自动更新） |
| `update_data.py` | 每日更新脚本，调用 Claude API + web search |
| `.github/workflows/daily-update.yml` | GitHub Actions 定时任务配置 |

---

## 🔧 手动更新数据

直接编辑 `data.json` 中的数值，commit 推送后网页立即生效。

---

## 📊 数据说明

- **Foundation Model 收入**：Annualized API Revenue，来源为公司融资公告、Bloomberg、The Information
- **AI App ARR**：年化经常性收入，来源为 Sacra、公司公开发言、媒体报道
- **Token 消耗量**：基于 API 定价反推 + OpenAI 官方披露（15B tokens/min, 2026.3）校验
- 所有数据为研究性估算，不构成投资建议

---

## ⚙️ 自定义

**修改监控公司列表：** 编辑 `data.json` 的 `models` 或 `apps` 数组

**调整更新频率：** 修改 `.github/workflows/daily-update.yml` 中的 cron 表达式
- 每天一次：`0 8 * * *`
- 每周一次：`0 8 * * 1`
- 每 12 小时：`0 8,20 * * *`

**每次更新 API 费用：** Claude Sonnet 约 $0.002–0.01/次（含 web search），每月 < $0.5
