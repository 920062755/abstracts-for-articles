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

- 新增 `python -m auv_intel_digest scheduled-digest` 命令。
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
