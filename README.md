# auv_intel_digest

每日科研资讯自动梳理与推送系统，面向多 AUV/UUV 协同作业、多智能体协同规划、协同目标跟踪、协同围捕 / pursuit-evasion / encirclement 和多智能体博弈方向。

默认运行模式是 `file_only`：即使 QQ 或 webhook 不可用，也会正常生成本地 Markdown、JSON，可选 HTML 报告。

## 安装

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Linux/macOS:

```bash
python -m venv .venv
./.venv/bin/python -m pip install -e ".[dev]"
```

复制 `.env.example` 为 `.env`，密钥、token、webhook、QQ 目标 ID 都只通过 `.env` 配置，不允许硬编码。

## 关键配置

```env
CONTACT_EMAIL=920062755@qq.com
TIMEZONE=Asia/Shanghai
DAILY_RUN_TIME=08:00
OUTPUT_DIR=reports
STATE_DB_PATH=data/state.sqlite

MAX_ITEMS_PER_TOPIC=5
DEDUP_WINDOW_DAYS=90
REPORT_LANGUAGE=zh_with_original_en
SAVE_HTML=false

NOTIFIER_MODE=file_only
STRICT_NOTIFY=false

QQ_TARGET_TYPE=private
QQ_TARGET_ID=920062755
QQ_PUSH_MODE=summary
QQ_PUSH_MAX_CHARS=3500

ENABLE_GITHUB_ACTIONS=false
ENABLE_AUTO_COMMIT_REPORTS=false
```

产品决策已经冻结：

- 日报默认按北京时间每天 `08:00` 运行，`TIMEZONE=Asia/Shanghai`，`DAILY_RUN_TIME=08:00`。
- Markdown/HTML 每个主题最多展示 `MAX_ITEMS_PER_TOPIC=5` 条精选。
- JSON 和 SQLite 保留完整候选、评分、去重状态和首次/最近出现日期。
- 如果某主题当天没有高相关条目，报告保留该主题并显示“今日暂无高相关更新”。
- 默认不自动提交报告到 GitHub。
- 默认 QQ 只推送摘要，完整日报保存在本地。
- 默认避免最近 `DEDUP_WINDOW_DAYS=90` 天重复进入日报精选。
- 报告中文为主，保留英文原题和 multi-AUV、cooperative planning、pursuit-evasion、Markov game 等技术术语。

## 运行

```bash
auv-digest run
```

指定日期：

```bash
auv-digest run --date 2026-04-27
```

输出文件：

```text
reports/daily/YYYY-MM-DD.md
reports/daily/YYYY-MM-DD.json
reports/daily/YYYY-MM-DD.html  # SAVE_HTML=true 时生成
```

JSON 条目保留完整字段：

```text
title, authors, source, url, published_date, abstract, topic,
matched_keywords, score, reason, tags, duplicate_status,
first_seen_date, last_seen_date
```

## topics.yaml

主题配置在 `config/topics.yaml`，支持中英文关键词：

- `positive`：命中后加分。
- `required_any`：至少命中一个，否则不归入该主题。
- `negative`：命中后排除或降级。
- `weight`：主题权重。
- `tags`：归类后附加标签。

新增或调整方向时优先改 `config/topics.yaml`，不要改代码。

## sources.yaml

数据源配置在 `config/sources.yaml`。建议优先使用正规 API：

- arXiv API
- Crossref API
- OpenAlex API
- Semantic Scholar API
- RSS
- GitHub repository search
- 可配置网页搜索 API

不要抓取付费论文全文；不要绕过 robots 或 API rate limit。缺少 token 的 source 应自动跳过，不能影响日报生成。

v0.2 collector MVP 已接入：

- `arxiv`：Atom API，按主题关键词和 arXiv category 查询。
- `openalex`：Works API，按日期窗口和主题关键词查询。
- `crossref`：Works API，按发布日期窗口和主题关键词查询。
- `github`：Repository Search API，默认关闭；启用后按最近更新、stars 和主题关键词查询。

每个 collector 会把结果规范化为统一字段，然后进入分类、评分、90 天去重、Markdown/JSON/SQLite 保存流程。任一 source 失败只会写入报告的“采集状态”，不会阻断其他 source。

## QQ 推送

默认：

```env
NOTIFIER_MODE=file_only
QQ_PUSH_MODE=summary
```

摘要内容包括：

- 今日总条目数；
- 每个主题精选条目数；
- 今日最值得关注的 3 条；
- Markdown/HTML 报告路径。

如果设置：

```env
NOTIFIER_MODE=file_only,qq
QQ_PUSH_MODE=full
```

系统会尝试分段或完整推送日报；当内容超过 `QQ_PUSH_MAX_CHARS` 时自动降级为摘要。若 QQ 推送失败且 `STRICT_NOTIFY=false`，主流程不会失败，日志会记录错误，报告文件仍然已经生成。

GitHub Actions 更适合 `file_only` 或公网 webhook，不适合依赖本地 OneBot 服务的 QQ 推送。

## 定时运行

### Windows Task Scheduler

北京时间每天 08:00：

- Trigger：Daily，08:00
- Action：

```powershell
C:\path\to\auv_intel_digest\.venv\Scripts\python.exe -m auv_intel_digest.cli run
```

- Start in：

```text
C:\path\to\auv_intel_digest
```

如需日志，可让任务执行 PowerShell：

```powershell
cd C:\path\to\auv_intel_digest
.\.venv\Scripts\python.exe -m auv_intel_digest.cli run *> logs\daily.log
```

### cron

服务器时区如果已经是 `Asia/Shanghai`：

```cron
0 8 * * * cd /opt/auv_intel_digest && ./.venv/bin/python -m auv_intel_digest.cli run >> logs/daily.log 2>&1
```

服务器时区如果是 UTC，北京时间 08:00 对应 UTC 00:00：

```cron
0 0 * * * cd /opt/auv_intel_digest && TZ=Asia/Shanghai ./.venv/bin/python -m auv_intel_digest.cli run >> logs/daily.log 2>&1
```

### GitHub Actions

默认不自动提交报告：

```env
ENABLE_GITHUB_ACTIONS=false
ENABLE_AUTO_COMMIT_REPORTS=false
```

报告可能包含个人研究判断、筛选偏好和未公开的研究关注点，默认不建议提交到公开仓库。

北京时间每天 08:00 对应 GitHub Actions UTC 00:00：

```yaml
name: Daily AUV Intel Digest

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .
      - run: auv-digest run
        env:
          CONTACT_EMAIL: ${{ secrets.CONTACT_EMAIL }}
          TIMEZONE: Asia/Shanghai
          DAILY_RUN_TIME: "08:00"
          NOTIFIER_MODE: file_only
          ENABLE_GITHUB_ACTIONS: "true"
          ENABLE_AUTO_COMMIT_REPORTS: "false"
      - uses: actions/upload-artifact@v4
        with:
          name: auv-intel-digest
          path: reports/daily/
```

只有同时满足以下条件，才允许扩展 workflow 自动 commit：

- `ENABLE_AUTO_COMMIT_REPORTS=true`
- `GITHUB_TOKEN` 存在
- 仓库可接受报告内容被提交

## 测试

```bash
pytest
```

覆盖范围：

- 分类；
- 去重；
- 报告生成；
- notifier fallback。

## v0.3.0 Scheduled RSS/Atom Digest

本阶段新增一个独立的本地定时资讯摘要命令，优先面向 RSS/Atom 源，不抓取完整网页正文，不调用 LLM，不自动推送。

示例 sources 配置：

```text
examples/sources.example.json
```

配置格式：

```json
{
  "sources": [
    {
      "name": "arXiv cs.RO RSS",
      "url": "https://rss.arxiv.org/rss/cs.RO",
      "category": "robotics",
      "enabled": true
    }
  ]
}
```

运行一次采集并生成 Markdown digest：

```powershell
python -m auv_intel_digest scheduled-digest --sources examples/sources.example.json --output digests/latest.md --limit 30
```

调试时包含已经见过的条目：

```powershell
python -m auv_intel_digest scheduled-digest --sources examples/sources.example.json --output digests/latest.md --include-seen
```

指定 state 文件：

```powershell
python -m auv_intel_digest scheduled-digest --sources examples/sources.example.json --output digests/latest.md --state .auv_intel_digest/state.json
```

默认 state 路径为：

```text
.auv_intel_digest/state.json
```

该目录已加入 `.gitignore`，不要提交。

Windows Task Scheduler 示例：

```powershell
cd C:\path\to\auv_intel_digest
.\.venv\Scripts\python.exe -m auv_intel_digest scheduled-digest --sources examples\sources.example.json --output digests\latest.md --limit 30
```

建议设置：

- Trigger: Daily, 08:00
- Start in: 项目根目录
- Action: 项目虚拟环境中的 Python

当前限制：

- 目前只做 RSS/Atom；
- 不抓取完整网页正文；
- 不做 LLM 深度总结；
- 不做自动推送；
- pytest 不依赖真实互联网，网络测试使用 mock。
