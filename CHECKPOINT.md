# CHECKPOINT

## 1. 当前项目目标

`auv_intel_digest` 是一个本地可运行的 Python 项目，用于每天自动收集并整理以下方向的科研资讯，生成 Markdown、JSON 和可选 HTML 日报：

- 多 AUV/UUV 协同作业
- 多智能体协同规划
- 多 AUV/UUV 协同目标跟踪
- 协同围捕 / pursuit-evasion / encirclement
- 多智能体博弈

默认模式为 `file_only`，即 QQ 或外部推送不可用时仍应正常生成本地报告。

## 2. 当前已经完成的功能

- Python 包和 CLI 骨架：`auv-digest run`、`auv-digest test-notifier`。
- `.env` 配置读取：密钥、token、QQ 目标 ID、输出路径、去重窗口等均通过环境变量配置。
- 主题配置：`config/topics.yaml`，支持中英文关键词、required/positive/negative 规则和主题标签。
- source 配置：`config/sources.yaml`，包含 arXiv、OpenAlex、Crossref、GitHub、RSS、Semantic Scholar、web_search 配置项。
- v0.2 collector MVP：
  - arXiv Atom API collector
  - OpenAlex Works API collector
  - Crossref Works API collector
  - GitHub Repository Search collector
- pipeline 已接入 collector、关键词分类、去重、报告生成和 notifier fallback。
- 去重逻辑：
  - DOI
  - arXiv ID
  - URL
  - 标准化标题
  - 标题相似度
  - 最近 90 天重复默认标记为 `repeated`
  - 同日重复标记为 `duplicate`
  - 明显新版本、代码、数据集更新可标记为 `update`
- 报告输出：
  - `reports/daily/YYYY-MM-DD.md`
  - `reports/daily/YYYY-MM-DD.json`
  - `SAVE_HTML=true` 时输出 `reports/daily/YYYY-MM-DD.html`
- Markdown 报告每个主题最多展示 `MAX_ITEMS_PER_TOPIC=5` 条精选。
- JSON 保留完整候选条目、评分、匹配关键词、去重状态、首次和最近出现日期。
- QQ notifier 抽象与 OneBot 实现：
  - 默认 `QQ_PUSH_MODE=summary`
  - `QQ_PUSH_MODE=full` 时尝试推送完整内容
  - 超过 `QQ_PUSH_MAX_CHARS` 时降级摘要
  - `STRICT_NOTIFY=false` 时推送失败不阻断主流程
- README 已包含安装、运行、配置、定时任务、GitHub Actions 和 v0.2 source 说明。

## 3. 当前目录结构和关键文件说明

```text
auv_intel_digest/
  cli.py                         # Typer CLI 入口
  config_loader.py               # topics.yaml / sources.yaml 加载
  models.py                      # IntelItem、Topic、DailyDigest 等数据模型
  pipeline.py                    # 主流程：采集、分类、去重、报告、通知
  settings.py                    # .env 配置读取

  classify/
    keyword_classifier.py        # 基于 topics.yaml 的关键词分类和初步评分

  dedupe/
    normalizer.py                # 标题标准化和相似度
    deduper.py                   # 当日和历史去重
    store.py                     # SQLite seen_items 状态库

  reports/
    markdown.py                  # Markdown/HTML 渲染辅助
    json_writer.py               # JSON 输出
    templates/daily_report.md.j2 # Markdown 报告模板

  notifiers/
    base.py                      # Notifier 抽象接口
    file_only.py                 # 默认本地文件模式
    qq_onebot.py                 # QQ OneBot 推送
    composite.py                 # 多 notifier fallback

  sources/
    base.py                      # collector 基类、窗口、查询辅助
    arxiv.py                     # arXiv collector
    openalex.py                  # OpenAlex collector
    crossref.py                  # Crossref collector
    github.py                    # GitHub collector
    factory.py                   # collector 构建和失败隔离

config/
  app.yaml                       # 产品默认配置记录
  topics.yaml                    # 主题关键词配置
  sources.yaml                   # 数据源配置

tests/
  test_classification.py         # 分类测试
  test_collectors.py             # 四个 collector 响应解析测试
  test_dedupe.py                 # 去重测试
  test_notifier_fallback.py      # notifier fallback 测试
  test_pipeline.py               # pipeline 最小集成路径测试
  test_report_generation.py      # 报告生成和 JSON 字段测试
```

根目录关键文件：

- `pyproject.toml`：包元数据、依赖、测试配置，当前版本 `0.2.0`。
- `.env.example`：推荐本地配置模板，不包含真实密钥。
- `.gitignore`：忽略 `.env`、venv、缓存、报告、状态库和测试临时文件。
- `README.md`：面向用户的安装、配置和运行说明。

## 4. 已通过的验证命令

```powershell
python -m compileall auv_intel_digest tests
```

结果：通过。

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

结果：`13 passed in 0.33s`。

说明：当前系统 `python` 未安装 `pytest`，测试使用项目 `.venv`。`-p no:cacheprovider` 用于规避当前 Windows 沙箱中的 pytest cache 权限问题。

## 5. 当前已知限制

- 当前目录不是 git 仓库，无法生成真实 `git diff` 或提交 checkpoint。
- collector 测试使用 mock 响应；尚未执行真实 API 联网 smoke test。
- GitHub collector 在 `config/sources.yaml` 中默认关闭。
- RSS、Semantic Scholar、web_search 仍为配置占位，尚未接入 pipeline。
- rate limit 和 retry 目前较基础；source 失败会记录状态并隔离，不会阻断其他 source。
- Markdown 中的中文要点目前基于模板固定生成；没有接入 LLM 或翻译模型生成更细粒度中文摘要。
- SQLite 当前主要记录 seen items；尚未保存完整候选结果全文结构到数据库。
- arXiv/OpenAlex/Crossref/GitHub 查询策略是关键词 MVP，尚未做 query 优化、分页深采样或跨源召回评估。
- Windows 上 `Asia/Shanghai` 已加入 fallback，并在依赖中声明 `tzdata`；其他时区仍依赖系统或 `tzdata`。

## 6. 下一阶段建议任务

优先级建议：

1. v0.3 live run hardening：
   - collector 级 retry、backoff、限流
   - 真实 API smoke test 命令
   - source enable/disable CLI
   - 空结果诊断
   - 采集统计和日志增强
2. 接入 RSS collector，并把会议、实验室、项目动态纳入日报。
3. 改进 SQLite：保存完整候选 JSON、source status、run metadata。
4. 增强报告质量：中文要点生成、低置信度区、项目动态区。
5. 增加 GitHub Actions workflow 示例文件，但默认不自动提交报告。
6. 在真实 `.env` 下执行一次 file_only live run，人工检查报告质量。

## 7. 给下一轮 Codex 的启动提示词

```text
请基于当前 v0.2.0 checkpoint 继续实现 v0.3 live run hardening。不要重构已有结构，保持现有 13 个测试通过。

目标：
1. 为 arXiv、OpenAlex、Crossref、GitHub collectors 增加 retry/backoff、基础 rate limit 和更清晰的 source status；
2. 增加 CLI 命令 `auv-digest smoke-sources`，用于真实 API smoke test，但不得依赖 QQ；
3. 增加 source enable/disable 覆盖参数，例如只跑 arxiv/openalex；
4. 增强空结果诊断，在 Markdown/JSON 中说明哪些 source 成功但无结果；
5. 保持所有密钥只从 .env 读取；
6. 更新 README 和最小测试；
7. 最后运行：
   python -m compileall auv_intel_digest tests
   .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## 8. v0.3.0 scheduled intel digest MVP 更新

当前新增能力：

- 新增 `python -m auv_intel_digest collect` 命令。
- 保留 `python -m auv_intel_digest scheduled-digest` 作为兼容别名。
- 支持从 JSON 配置读取多个 RSS/Atom sources。
- 支持 RSS 2.0 和 Atom 基本字段解析：
  - title
  - link
  - published / updated
  - source
  - summary / description
  - guid / id
- 新增本地 JSON state：
  - 默认 `.auv_intel_digest/state.json`
  - 按 guid / link / title 生成稳定 item id
  - 默认只输出新条目
  - `--include-seen` 可输出已见条目
- 新增 Markdown digest 输出：
  - run summary
  - highlights
  - source errors
- 新增示例配置：
  - `examples/sources.example.json`

新增验证范围：

- RSS fixture 解析
- Atom fixture 解析
- state 读写
- 去重状态标记
- Markdown digest 生成
- scheduled digest CLI smoke test

当前限制保持：

- 不抓取完整网页正文；
- 不接入 LLM；
- 不做自动推送；
- 不引入 Web UI 或数据库；
- pytest 使用 mock 网络或本地 fixture，不依赖真实互联网。

## 9. v0.4.0 中文情报摘要 MVP 更新

当前新增能力：

- `collect` 增加参数：
  - `--language zh|en`
  - `--summarizer noop|openai`
  - `--llm-model`
- `--language zh` 输出中文 Markdown 模板：
  - 运行摘要
  - 重点情报
  - 来源、发布时间、链接、原始标题
  - 中文摘要、关键信息、风险、机会、建议跟进
  - 采集错误
- 新增 summarizer 抽象层：
  - `noop`：默认，不调用外部 API，保留原文并标记未启用 LLM 中文摘要
  - `fake`：测试用 deterministic summarizer
  - `openai`：可选 OpenAI summarizer
- OpenAI summarizer 约束：
  - API key 从 `OPENAI_API_KEY` 读取
  - 模型从 `AUV_INTEL_LLM_MODEL` 或 `--llm-model` 读取
  - 缺 key 时回退 `noop`
  - 单条失败不阻断 digest

示例命令：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh
```

可选 LLM：

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:AUV_INTEL_LLM_MODEL="your_model_name"
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --summarizer openai
```

测试要求：

- 不依赖真实网络；
- 不依赖真实 LLM API；
- OpenAI 相关测试使用 mock response 或缺 key fallback。

## 10. v0.4.1 collector diagnostics and failure guard

当前修正：

- 当 `sources_checked > 0` 且 `successful == 0` 且 `failed > 0` 时，digest 不再写“今日暂无新条目”。
- 中文 digest 改为提示：

```text
本次未生成有效情报摘要，因为所有资讯源采集失败。请先检查网络、代理、防火墙、RSS URL 或运行环境权限。
```

- source error 增加 `diagnostic` 字段。
- 采集错误区会输出诊断提示。
- 增加常见错误分类：
  - Windows socket 权限 / 防火墙 / 沙箱网络权限；
  - timeout；
  - DNS 解析失败；
  - 404；
  - 非 RSS/Atom XML。
- 修复 `scheduled_digest` 与 `sources` 包之间的循环导入风险。

测试新增覆盖：

- 所有 source 失败时不显示“今日暂无新条目”；
- 所有 source 失败时显示 failure guard 文案；
- source diagnostics 出现在 Markdown 中。

追加行为：

- `collect` / `scheduled-digest` 支持 `--fail-on-all-source-errors`。
- 传入该参数且所有启用 source 都失败时：
  - 仍写出 Markdown digest；
  - 终端 summary 输出 `All sources failed: true`；
  - 进程退出码为 `2`；
  - 不更新 state 文件；
  - 不把任何 item 标记为 seen。
- 未传该参数时保持兼容：写出错误 digest，退出码仍为 `0`。
- 所有 source 失败时，无论是否传入该参数，都不更新 state，也不标记任何 item 为 seen；该参数只改变退出码。

状态语义：

- `全部失败`：`sources_checked > 0`、`successful == 0`、`failed > 0`。没有任何启用 source 成功下载并解析 RSS/Atom，不能判断是否真的没有新资讯；digest 显示 failure guard 文案并保留错误诊断。
- `部分成功`：至少一个 source 成功，同时至少一个 source 失败。digest 输出成功源中的可用条目，并在采集错误区记录失败源。
- `无新增`：采集源成功解析，但当前运行没有发现未见过的新条目。此时可以显示“今日暂无新条目”。

新增源诊断命令：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest check-sources --sources examples\sources.example.json --timeout 20
```

输出字段：

- name / url / enabled / category
- HTTP status
- content-type
- byte count
- parseable RSS/Atom
- item count
- error type / error message
- diagnostic

单个 source 失败不影响其他 source；总计输出 checked / successful / failed。测试使用 mock 网络。

本地网络诊断命令：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest check-sources --sources examples\sources.example.json --timeout 20
Resolve-DnsName rss.arxiv.org
Test-NetConnection rss.arxiv.org -Port 443
curl.exe -I https://rss.arxiv.org/rss/cs.RO
Invoke-WebRequest -Uri https://rss.arxiv.org/rss/cs.RO -UseBasicParsing -TimeoutSec 20
netsh winhttp show proxy
```

`WinError 10013` / `socket_permission_denied` 通常表示当前 Windows 运行环境不允许 Python 建立该网络连接，可能来自 Windows 防火墙、杀毒软件、代理、沙箱网络限制或系统权限策略。

GitHub Actions 云端 runner 可能绕过本地 Windows 网络限制，但不保证所有 RSS/Atom 源可用；程序仍应正确输出失败源、错误类型和诊断说明。GitHub Actions 更适合 `file_only` 或公网 webhook，不适合依赖本地 OneBot 的 QQ 推送。

## 11. v0.5.0 cloud scheduled digest + Telegram delivery MVP

新增目标：

- 在 GitHub Actions 云端每天自动运行，不依赖本地 Windows 电脑开机。
- 生成中文 RSS/Atom digest：`digests/latest.zh.md`。
- 上传 GitHub Actions artifact。
- 可选通过 Telegram Bot 推送 digest。
- 可选使用 OpenAI summarizer 生成中文摘要。

新增文件：

```text
.github/workflows/daily-digest.yml
auv_intel_digest/notifiers/telegram.py
tests/test_telegram_notifier.py
```

新增 CLI：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest send-telegram --markdown digests\latest.zh.md --title "AUV 情报摘要"
```

Telegram 配置只从环境变量或 GitHub Actions Secrets 读取：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_PARSE_MODE      # 可选，默认不设置
TELEGRAM_MAX_CHARS       # 默认 3800
```

GitHub Actions 配置：

- schedule cron: `0 0 * * *`，对应北京时间 08:00。
- 运行 `python -m auv_intel_digest collect --language zh --fail-on-all-source-errors`。
- 上传 `digests/latest.zh.md` 和 `.auv_intel_digest/state.json` artifact。
- 如果配置了 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`，运行 `send-telegram`。
- 最后根据 collect 退出码决定 workflow 是否失败，确保错误 digest 已先上传/推送。

OpenAI 可选摘要：

- `DIGEST_SUMMARIZER=noop` 默认不调用外部 LLM。
- `DIGEST_SUMMARIZER=openai` 且 `OPENAI_API_KEY` 存在时调用 OpenAI summarizer。
- `AUV_INTEL_LLM_MODEL` 控制模型名。
- 测试不得真实调用 OpenAI API。

当前限制：

- Telegram 仅使用 `sendMessage` 分段推送，不上传附件。
- GitHub Actions state 是 artifact，不会自动提交回仓库。
- Notion、Email、WeCom/微信替代渠道未实现。
- RSS/Atom 网络、Telegram 和 OpenAI 测试均应使用 mock。

## 12. v0.5.1 production verification and hardening

本阶段目标是把 v0.5.0 从“功能可用”收口到“可部署、可诊断、可每天自动运行”。

修复/增强：

- GitHub Actions workflow 增加基础验证：
  - `python -m compileall auv_intel_digest tests`
  - `python -m pytest -q -p no:cacheprovider`
  - `python -m auv_intel_digest check-sources --sources examples/sources.example.json --timeout 20`
- workflow 增加 `actions/cache@v4`，缓存 `.auv_intel_digest/`，用于跨 GitHub Actions 运行恢复 state。
- workflow artifact 名称包含 `${{ github.run_id }}`：
  - `digests/latest.zh.md`
  - `.auv_intel_digest/state.json`
- workflow 捕获 collect 退出码，先上传 artifact、再尝试 Telegram，最后根据 collect 退出码决定 workflow 是否失败。
- `send-telegram` 在缺少 `TELEGRAM_BOT_TOKEN` 或 `TELEGRAM_CHAT_ID` 时返回 skipped，不崩溃。
- Telegram HTTP 错误会输出简短错误，不泄露 bot token。
- Telegram 长消息按 `TELEGRAM_MAX_CHARS` 分段。
- 所有 source 失败时，Telegram 第一段包含：

```text
⚠️ AUV 情报摘要采集失败
```

- 新增部署核验命令：

```powershell
python -m auv_intel_digest deployment-check
python -m auv_intel_digest doctor
```

部署核验命令检查：

- Python 版本；
- 包导入；
- sources 文件是否存在；
- `.auv_intel_digest/` 是否可写；
- `digests/` 是否可写；
- `OPENAI_API_KEY` 是否 present/missing；
- `TELEGRAM_BOT_TOKEN` 是否 present/missing；
- `TELEGRAM_CHAT_ID` 是否 present/missing；
- 不打印 secret 值。

GitHub Actions 当前运行语义：

- 支持手动触发：`workflow_dispatch`。
- 支持每日计划：UTC 00:00，即北京时间 08:00。
- Ubuntu runner，Python 3.11。
- 安装命令：`python -m pip install -e ".[dev]"`。
- `DIGEST_SUMMARIZER=noop` 默认不调用 OpenAI。
- `DIGEST_SUMMARIZER=openai` 且 `OPENAI_API_KEY` 存在时启用 OpenAI summarizer。
- Telegram secrets 缺失时 workflow 仍生成 artifact；`send-telegram` 输出 skipped。
- 所有 source 失败时，collect 返回 2，workflow 最终标红；但 artifact 上传和 Telegram 告警会先执行。

README 已补充可操作部署手册：

- 推送代码到 GitHub；
- 配置 GitHub Secrets / Variables；
- 创建 Telegram bot；
- 手动 Run workflow；
- 验证 artifact / Telegram / logs；
- state/cache 限制；
- 常见故障排查。

当前限制：

- Telegram 仍只使用 `sendMessage`，不上传附件。
- state 通过 GitHub cache 恢复；首次运行或 cache miss 可能重复输出旧条目。
- Notion、Email、WeCom/微信、Web UI、Docker、VPS 均未实现。
## v0.6.0 email delivery + SiliconFlow/OpenAI-compatible summarizer MVP

当前新增能力：

- 新增 SMTP Email notifier：`auv_intel_digest/notifiers/email.py`。
- 新增 CLI：`python -m auv_intel_digest send-email --markdown digests/latest.zh.md --title "AUV 情报摘要"`。
- 默认收件人配置为 `EMAIL_TO=920062755@qq.com`。
- 支持 QQ 邮箱 SMTP，推荐配置：
  - `SMTP_HOST=smtp.qq.com`
  - `SMTP_PORT=465`
  - `SMTP_USERNAME=920062755@qq.com`
  - `SMTP_PASSWORD=<QQ邮箱授权码>`
  - `EMAIL_FROM=920062755@qq.com`
  - `EMAIL_TO=920062755@qq.com`
  - `EMAIL_USE_SSL=true`
- 新增 OpenAI-compatible summarizer：`auv_intel_digest/summarizers/openai_compatible.py`。
- SiliconFlow 通过以下配置启用：
  - `DIGEST_SUMMARIZER=siliconflow`
  - `AUV_INTEL_LLM_BASE_URL=https://api.siliconflow.cn/v1`
  - `AUV_INTEL_LLM_API_KEY=<secret>`
  - `AUV_INTEL_LLM_MODEL=<model>`
- 新增 GitHub Actions workflow：
  - `.github/workflows/daily-digest.yml`
  - UTC 00:00 / 北京时间 08:00 运行；
  - 支持 `workflow_dispatch` 手动触发；
  - 运行 compileall、pytest、deployment-check、check-sources；
  - 生成 `digests/latest.zh.md`；
  - 上传 `digests/latest.zh.md` 和 `.auv_intel_digest/state.json` artifact；
  - 使用 `actions/cache@v4` 缓存 `.auv_intel_digest/`；
  - `EMAIL_ENABLED=true` 时执行 `send-email`。

安全约束：

- SMTP 密码必须使用 QQ 邮箱授权码，放在 GitHub Secrets 或环境变量中。
- 不在代码、README 示例真实值、state 或日志中写入 API key、SMTP 密码。
- `deployment-check` 只输出 present/missing，不打印 secret 值。
- SMTP、SiliconFlow/OpenAI、RSS 网络相关测试均使用 mock。

当前限制：

- Email 使用纯文本邮件，不上传附件。
- Telegram 保留后续扩展空间，但不是默认推送方式。
- QQ OneBot 仍适合本地或公网 OneBot endpoint，不适合默认 GitHub Actions 云端推送。
- GitHub Actions state 依赖 cache，首次运行或 cache miss 时可能重复输出旧资讯。
