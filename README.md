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
python -m auv_intel_digest collect --sources examples/sources.example.json --output digests/latest.md --limit 30
```

调试时包含已经见过的条目：

```powershell
python -m auv_intel_digest collect --sources examples/sources.example.json --output digests/latest.md --include-seen
```

指定 state 文件：

```powershell
python -m auv_intel_digest collect --sources examples/sources.example.json --output digests/latest.md --state .auv_intel_digest/state.json
```

`scheduled-digest` 是兼容别名，推荐日常使用 `collect`。

默认 state 路径为：

```text
.auv_intel_digest/state.json
```

该目录已加入 `.gitignore`，不要提交。

Windows Task Scheduler 示例：

```powershell
cd C:\path\to\auv_intel_digest
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.md --limit 30
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

## v0.4.0 中文情报摘要

`collect` 支持中文 Markdown 模板：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh
```

默认 summarizer 是 `noop`：

- 不调用外部 API；
- 不翻译；
- 保留原始英文标题、链接和摘要；
- 在中文摘要字段中标记“未启用 LLM 中文摘要”。

可选 OpenAI summarizer：

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:AUV_INTEL_LLM_MODEL="your_model_name"

.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --summarizer openai
```

也可以通过 CLI 指定模型：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --summarizer openai --llm-model your_model_name
```

约束：

- `OPENAI_API_KEY` 只能来自环境变量，不要写入代码或提交到仓库；
- API key 缺失时会自动回退到 `noop`；
- 单条摘要失败不会中断整份 digest；
- 测试使用 fake/mock summarizer，不调用真实 LLM API。

## v0.4.1 采集失败诊断

当所有 RSS/Atom 源都采集失败时，中文 digest 不再显示“今日暂无新条目”，而是显示：

```text
本次未生成有效情报摘要，因为所有资讯源采集失败。请先检查网络、代理、防火墙、RSS URL 或运行环境权限。
```

采集错误区会为常见失败补充诊断提示，例如：

- 运行环境拒绝建立网络连接；
- 网络请求超时；
- DNS 解析失败；
- RSS URL 返回 404；
- 响应内容不是有效 RSS/Atom XML。

如果任务计划程序需要在所有 source 都失败时返回非 0 退出码，可使用：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --fail-on-all-source-errors
```

该模式下仍会写出 Markdown digest，便于查看错误；但当所有启用的 source 都失败时，进程退出码为 `2`。未传该参数时保持兼容行为：写出错误 digest，退出码仍为 `0`。

注意：所有 source 失败时，无论是否传 `--fail-on-all-source-errors`，都不会更新 `.auv_intel_digest/state.json`，也不会把任何 item 标记为 seen。该参数只用于让定时任务、CI 或监控系统感知失败退出码。

逐个诊断 RSS/Atom sources：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest check-sources --sources examples\sources.example.json --timeout 20
```

该命令会输出每个 source 的 name、url、enabled、category、HTTP status、content-type、下载字节数、是否可解析为 RSS/Atom、item 数量、错误类型、错误消息和诊断说明。单个 source 失败不会影响其他 source，最后会输出 checked / successful / failed 总计。命令不会打印 API key、token 或 webhook secret。

状态语义：

- 所有 source 失败：没有任何启用 source 成功下载并解析 RSS/Atom，因此无法判断今天是否真的没有新资讯。digest 会显示“本次未生成有效情报摘要”，采集错误区会列出失败原因，state 不更新。
- 无新增：至少有 source 成功采集并解析，但当前运行没有发现未见过的新条目。digest 可以显示“今日暂无新条目”，这是一次有效采集结果。
- 部分成功：至少一个 source 成功，同时至少一个 source 失败。digest 会输出成功源中的条目，并在采集错误区保留失败源诊断。

本地网络诊断命令示例：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest check-sources --sources examples\sources.example.json --timeout 20
Resolve-DnsName rss.arxiv.org
Test-NetConnection rss.arxiv.org -Port 443
curl.exe -I https://rss.arxiv.org/rss/cs.RO
Invoke-WebRequest -Uri https://rss.arxiv.org/rss/cs.RO -UseBasicParsing -TimeoutSec 20
netsh winhttp show proxy
```

如果出现 `[WinError 10013]`、`socket_permission_denied` 或 permission denied，通常表示当前 Windows 运行环境不允许 Python 建立该网络连接。常见原因包括 Windows 防火墙、杀毒软件、代理、沙箱网络限制或系统权限策略。

GitHub Actions 运行在云端 Linux runner，可能绕过本地 Windows 防火墙、杀毒软件或沙箱网络限制；但云端也可能遇到 DNS、HTTP、RSS 格式、rate limit 或目标站点屏蔽问题。程序仍应正确报告 source 成功/失败、错误类型和诊断说明。GitHub Actions 更适合 `file_only` 或公网 webhook，不适合依赖本地 OneBot 服务的 QQ 推送。

## v0.5.0 GitHub Actions + Telegram

本阶段新增云端定时运行 MVP：

- GitHub Actions 每天 UTC 00:00 运行，对应北京时间 08:00；
- 生成中文 digest：`digests/latest.zh.md`；
- 上传 digest artifact；
- 可选使用 OpenAI 生成中文摘要；
- 可选通过 Telegram Bot 推送 digest；
- 不依赖本地 Windows 电脑开机。

workflow 文件：

```text
.github/workflows/daily-digest.yml
```

GitHub 仓库需要配置 Secrets：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
OPENAI_API_KEY              # 可选，仅 --summarizer openai 时需要
```

可选配置 GitHub Variables：

```text
DIGEST_SUMMARIZER=noop      # 可改为 openai
AUV_INTEL_LLM_MODEL=gpt-4o-mini
TELEGRAM_MAX_CHARS=3800
```

本地测试 Telegram 发送：

```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"

.\.venv\Scripts\python.exe -m auv_intel_digest send-telegram --markdown digests\latest.zh.md --title "AUV 情报摘要"
```

只生成中文 digest，不发送：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh
```

启用 OpenAI 摘要：

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:AUV_INTEL_LLM_MODEL="gpt-4o-mini"

.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --summarizer openai
```

说明：

- Telegram token 和 chat id 只从环境变量或 GitHub Actions Secrets 读取，不写入代码。
- workflow 先生成 digest，再上传 artifact，再发送 Telegram；即使所有 source 失败，也会上传错误 digest 并尝试推送诊断内容。
- workflow 最后会根据 `collect --fail-on-all-source-errors` 的退出码决定是否标红失败；这样 artifact 和 Telegram 仍有机会保留错误信息。
- Telegram 推送目前使用 `sendMessage`，按 `TELEGRAM_MAX_CHARS` 分段，不做文件上传。
- Notion、Email、WeCom/微信替代渠道本阶段不实现，只保留后续扩展空间。

## v0.5.1 生产部署核验

### 1. 推送代码到 GitHub

先确认 remote：

```powershell
git remote -v
```

如果没有 remote，先在 GitHub 创建仓库，然后添加：

```powershell
git remote add origin https://github.com/<your-user>/<your-repo>.git
git branch -M main
```

推送代码和 tag：

```powershell
git push -u origin main
git push --tags
```

### 2. 配置 GitHub Secrets 和 Variables

路径：

```text
GitHub repo -> Settings -> Secrets and variables -> Actions
```

Secrets：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
OPENAI_API_KEY
```

`OPENAI_API_KEY` 是可选项。没有 OpenAI key 时，workflow 仍可使用 `noop` 摘要器运行，只是中文深度摘要质量有限。

Variables：

```text
DIGEST_SUMMARIZER=noop
AUV_INTEL_LLM_MODEL=gpt-4o-mini
TELEGRAM_MAX_CHARS=3800
```

需要启用 OpenAI 摘要时，把 `DIGEST_SUMMARIZER` 改为：

```text
openai
```

不要把 secret 写入代码、README、sources 配置或 commit。

### 3. 创建 Telegram bot

1. 在 Telegram 中打开 `BotFather`。
2. 使用 `/newbot` 创建 bot。
3. 保存 BotFather 返回的 bot token，放入 GitHub Secret `TELEGRAM_BOT_TOKEN`。
4. 给 bot 发送一条消息，或把 bot 加入目标群组。
5. 获取 chat id，放入 GitHub Secret `TELEGRAM_CHAT_ID`。
6. 本地可用以下命令测试，但不要把 token/chat id 写入文件：

```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token"
$env:TELEGRAM_CHAT_ID="your_chat_id"
.\.venv\Scripts\python.exe -m auv_intel_digest send-telegram --markdown digests\latest.zh.md --title "AUV 情报摘要"
```

如果未配置 Telegram 环境变量，`send-telegram` 会显示 skipped，不会崩溃。

### 4. 手动触发 workflow

路径：

```text
GitHub repo -> Actions -> Daily AUV Intel Digest -> Run workflow
```

运行后检查：

- workflow log；
- `auv-intel-digest-${run_id}` artifact；
- artifact 中的 `digests/latest.zh.md`；
- Telegram 是否收到摘要或明确失败告警。

### 5. 定时运行说明

workflow 使用：

```yaml
schedule:
  - cron: "0 0 * * *"
```

GitHub Actions 的 cron 是 UTC 时间。`0 0 * * *` 对应北京时间每天 08:00。若要改成其他本地时间，需要换算到 UTC 后修改 cron。

### 6. state/cache 方案

GitHub Actions 使用 `actions/cache@v4` 缓存：

```text
.auv_intel_digest/
```

运行前按分支 restore 最近的 state cache，运行后在成功 workflow 中保存新的 cache。这样可以跨多次 GitHub Actions 运行保留 `.auv_intel_digest/state.json`，减少重复推送旧资讯。

限制：

- cache restore 失败时 workflow 仍可运行，但可能重复输出旧条目；
- cache 不包含 secret；
- `.auv_intel_digest/` 已在 `.gitignore` 中，不应提交；
- 如果所有 source 都失败，程序不会更新 state。

### 7. 验证成功标准

一次可接受的生产运行应满足：

- workflow 可以手动触发；
- workflow 可以按 UTC 00:00 自动触发；
- workflow 运行 compileall 和 pytest；
- workflow 生成中文 `digests/latest.zh.md`；
- artifact 可下载；
- Telegram 收到摘要，或在所有 source 失败时收到明显失败告警；
- 没有 secret 出现在日志、digest、state 或 README 中；
- 如果 source 全部失败，workflow 可以标红，但 artifact 和 Telegram 告警应已经处理。

### 8. 常见故障排查

- 没有收到 Telegram：检查 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`，确认 bot 已收到过消息或已在群组中。
- chat id 不对：重新给 bot 发消息后通过 Telegram Bot API 或调试工具确认 chat id。
- workflow 没有定时触发：确认 workflow 已在默认分支，仓库 Actions 已启用，cron 是 UTC。
- RSS source 全失败：查看 `check-sources` step 和 digest 的“采集错误”。
- OpenAI summarizer 没有启用：确认 `DIGEST_SUMMARIZER=openai` 且 `OPENAI_API_KEY` 存在。
- artifact 找不到：检查 `Upload digest artifact` step，artifact 名称包含 GitHub run id。
- 每天重复旧资讯：检查 `Restore scheduled digest state` step 是否命中 cache，确认 `.auv_intel_digest/state.json` 在 artifact/cache 中存在。
- cache/state 不生效：GitHub cache 是按分支和 key restore 的；首次运行没有 cache 属于正常情况。

### 9. 本地部署核验

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest deployment-check
```

该命令只显示 secret 是否 present/missing，不打印 secret 值。
