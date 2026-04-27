# Codex Prompt — v0.5.1 Production Verification and Hardening

请把下面整段内容直接提交给 Codex。

---

当前项目已经实现并冻结到 v0.5.0：GitHub Actions + Telegram delivery MVP。README 和 CHECKPOINT 显示当前已有：

- `.github/workflows/daily-digest.yml`
- `digests/latest.zh.md` 云端生成
- artifact 上传
- 可选 OpenAI summarizer
- Telegram Bot 推送
- `send-telegram` CLI
- `collect --language zh --fail-on-all-source-errors`
- source failure diagnostics

但我的真实目标不是“代码看起来完成”，而是：**每天自动运行、整理中文信息摘要，并稳定推送给我**。

现在启动 v0.5.1：production verification and hardening。

请不要新增 Notion、Email、WeCom、Web UI、数据库、Docker 或 VPS。当前只做 GitHub Actions + Telegram + 中文 digest 的稳定闭环。

## 总目标

让项目达到以下验收标准：

1. GitHub Actions 可以手动触发成功运行；
2. GitHub Actions 可以按计划每天自动运行；
3. workflow 能生成中文 Markdown digest；
4. workflow 能上传 digest artifact；
5. 如果配置了 Telegram Secrets，workflow 能把摘要推送到 Telegram；
6. 如果所有 source 失败，Telegram 推送的是“采集失败告警”，而不是空摘要；
7. 如果没有 OpenAI API key，workflow 仍能使用 noop/fallback 模式运行；
8. 如果配置了 OpenAI API key，workflow 能使用 OpenAI summarizer；
9. state / 去重机制在 GitHub Actions 中有明确可运行方案；
10. 所有测试通过；
11. README 给出完整的人工部署步骤。

## 一、先审查当前 v0.5.0 实现

请先读取并检查：

- `README.md`
- `CHECKPOINT.md`
- `.github/workflows/daily-digest.yml`
- `auv_intel_digest/cli.py`
- `auv_intel_digest/notifiers/telegram.py`
- 与 `collect`、`send-telegram`、OpenAI summarizer、state、artifact 相关的代码
- 当前 tests

请判断当前实现是否真的满足“每天自动生成并推送”的闭环。

重点检查：

1. workflow 是否能在 GitHub Actions Ubuntu runner 上运行；
2. workflow 使用的命令是否和当前 CLI 完全一致；
3. workflow 是否引用了不存在的文件、命令、extras、路径或环境变量；
4. workflow 是否正确安装依赖；
5. workflow 是否能在 collect 失败时仍上传错误 digest artifact；
6. workflow 是否能在 collect 失败时仍尽量发送 Telegram 告警；
7. workflow 是否最后根据 collect 退出码决定是否失败；
8. workflow 是否不会打印 secret；
9. Telegram 推送是否会泄露 token；
10. Telegram 长文本是否分段或截断；
11. `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` 缺失时是否跳过而不是崩溃；
12. `OPENAI_API_KEY` 缺失时 `--summarizer openai` 是否能回退；
13. state 文件是否真的能跨 GitHub Actions 多次运行保留；
14. 如果 state 只是 artifact，是否需要改成 `actions/cache` 或其他可恢复方案；
15. README 是否告诉我如何配置 GitHub Secrets、Variables、Telegram bot、chat id 和手动 Run workflow。

## 二、修复 GitHub Actions workflow

请确保 `.github/workflows/daily-digest.yml` 满足以下要求：

1. 支持手动触发：

```yaml
workflow_dispatch:
```

2. 支持每天定时运行。

当前默认可以保持北京时间 08:00，即 UTC 00:00：

```yaml
schedule:
  - cron: "0 0 * * *"
```

但请在 README 中明确说明：

- 这是 UTC 时间；
- 对应北京时间 08:00；
- 如果我要改成本地其他时区，需要修改 cron。

3. 使用 Ubuntu runner。

4. 设置 Python 版本，优先 3.11 或 3.12。

5. 安装依赖时必须和 `pyproject.toml` 一致。如果当前支持 dev/test extra，可以用：

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

如果不支持，请改成项目实际可用的最小安装方式。不要在 workflow 中写一个本地不可验证的安装命令。

6. 运行基础验证：

```bash
python -m compileall auv_intel_digest tests
python -m pytest -q -p no:cacheprovider
```

7. 运行 source 诊断：

```bash
python -m auv_intel_digest check-sources --sources examples/sources.example.json --timeout 20
```

如果当前 workflow 使用的是 `examples/sources.cloud.example.json`，请确认该文件确实存在；不存在就创建，或改回实际存在的 sources 文件。不要让 workflow 引用不存在的文件。

8. 运行中文 digest：

```bash
python -m auv_intel_digest collect \
  --sources examples/sources.example.json \
  --output digests/latest.zh.md \
  --limit 30 \
  --language zh \
  --summarizer "${DIGEST_SUMMARIZER:-noop}" \
  --state .auv_intel_digest/state.json \
  --fail-on-all-source-errors
```

如果 GitHub Actions shell 不支持这种默认变量写法，请用兼容写法。

9. collect 即使返回 exit code 2，也必须先保留 digest 和错误信息。建议 workflow 捕获退出码：

```bash
set +e
python -m auv_intel_digest collect ...
COLLECT_EXIT_CODE=$?
echo "COLLECT_EXIT_CODE=$COLLECT_EXIT_CODE" >> "$GITHUB_ENV"
set -e
```

之后继续执行 artifact 上传和 Telegram 推送，最后再用退出码决定 workflow 是否失败。

10. 上传 artifact 必须 `if: always()`，包括：

- `digests/latest.zh.md`
- `.auv_intel_digest/state.json`
- 可选日志文件

artifact 名称建议包含日期或 run id，例如：

```text
auv-intel-digest-${{ github.run_id }}
```

11. Telegram 推送也应 `if: always()`，但缺少 secret 时应自动跳过。

12. workflow 末尾根据 collect 退出码决定是否失败：

- `0`：成功；
- `2`：所有 source 失败，workflow 可以标红，但 artifact 和 Telegram 告警必须已经处理；
- 其他非 0：失败。

## 三、修复 GitHub Actions state 持久化

当前 README 说 state 是 artifact，不会自动提交回仓库。请判断当前设计是否会导致每天重复推送旧资讯。

如果 state 目前无法跨运行恢复，请实现一个最小可行方案。

优先方案：使用 `actions/cache` 缓存 `.auv_intel_digest/state.json`。

要求：

1. workflow 运行前 restore `.auv_intel_digest/`；
2. workflow 运行后更新 `.auv_intel_digest/state.json`；
3. cache 不得包含 secret；
4. `.auv_intel_digest/` 不得提交到仓库；
5. 如果 cache restore 失败，workflow 仍可运行，只是可能重复摘要；
6. README 必须解释 cache/state 的限制。

如果你判断 `actions/cache` 不适合当前 state 更新方式，请提出替代方案，但必须实现一个实际可用的 MVP，而不是只写文档。

可选方案包括：

- cache state；
- artifact download + restore；
- private repo runtime branch；
- GitHub Gist；
- 后续 SQLite remote store。

本阶段优先选最简单可靠的。

## 四、强化 Telegram 推送

请检查并修复 Telegram notifier / `send-telegram`。

要求：

1. 只从环境变量读取：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TELEGRAM_PARSE_MODE
TELEGRAM_MAX_CHARS
```

2. 缺少 token 或 chat id 时：

- 本地命令清晰提示 skipped；
- GitHub Actions 不崩溃；
- 不泄露 secret。

3. 发送失败时：

- 输出错误类型和简短诊断；
- 不打印完整 token；
- workflow 仍能继续到最后。

4. digest 太长时：

- 自动分段；
- 每段不超过 Telegram 限制或 `TELEGRAM_MAX_CHARS`；
- 第一段包含运行摘要；
- 如果是所有 source 失败，第一段必须包含明显告警：

```text
⚠️ AUV 情报摘要采集失败
```

5. 对正常摘要，Telegram 内容至少包含：

- 标题；
- 生成时间；
- 运行摘要；
- 新条目数；
- 前 5 条重点情报；
- artifact 提示。

6. 如果当前 Telegram parse mode 容易因为 Markdown 转义失败导致发送失败，请默认不设置 parse mode，或提供安全转义。

## 五、强化 OpenAI summarizer

请检查 OpenAI summarizer 是否满足：

1. `OPENAI_API_KEY` 只来自环境变量；
2. `AUV_INTEL_LLM_MODEL` 或 CLI `--llm-model` 控制模型名；
3. key 缺失时回退 noop；
4. 单条 item 摘要失败不阻断整份 digest；
5. 不在日志、digest、state、README 中写入真实 key；
6. GitHub Actions 可通过 secret 注入；
7. 测试不真实调用 OpenAI API。

如果当前 `DIGEST_SUMMARIZER=openai` 但没有 key 会导致失败，请修复为 graceful fallback。

## 六、增加部署验收命令

请新增或改进一个 CLI 命令，用于本地和 GitHub Actions 前置检查：

```powershell
python -m auv_intel_digest deployment-check
```

或如果更适合当前 Typer 结构，也可以命名为：

```powershell
python -m auv_intel_digest doctor
```

检查项：

1. Python 版本；
2. 当前包是否可导入；
3. sources 文件是否存在；
4. `check-sources` 是否可运行；
5. `collect` 命令是否可运行；
6. `.auv_intel_digest/` 是否可写；
7. `digests/` 是否可写；
8. 是否检测到 `OPENAI_API_KEY`；
9. 是否检测到 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`；
10. 不打印 secret 值，只显示 present/missing；
11. 输出建议下一步。

如果实现成本过高，可以先做最小版本，但必须有测试。

## 七、README 必须更新成真正可部署手册

请把 README 的 v0.5 部分改成我能照着做的步骤。

必须包含：

### 1. 推送代码到 GitHub

```powershell
git remote -v
git push
git push --tags
```

如果没有 remote，说明如何添加。

### 2. 配置 GitHub Secrets

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

Variables：

```text
DIGEST_SUMMARIZER=noop 或 openai
AUV_INTEL_LLM_MODEL=具体模型名
TELEGRAM_MAX_CHARS=3800
```

说明：

- 没有 OpenAI key 也能运行，只是摘要质量有限；
- 没有 Telegram secret 也能生成 artifact，但不会推送；
- 不要把 secret 写到代码、sources、README 示例真实值或 commit 中。

### 3. 创建 Telegram bot

说明：

- 使用 BotFather 创建 bot；
- 获取 bot token；
- 给 bot 发一条消息；
- 获取 chat id；
- 把 token/chat id 放入 GitHub Secrets；
- 本地可用 `send-telegram` 测试。

不要在 README 中写真实 token。

### 4. 手动触发 workflow

```text
GitHub repo -> Actions -> Daily Digest -> Run workflow
```

说明如何查看日志、artifact 和 Telegram 消息。

### 5. 验证成功标准

一次成功运行必须满足：

- workflow 完成；
- artifact 存在；
- `latest.zh.md` 可下载；
- Telegram 收到摘要或明确的失败告警；
- 没有 secret 泄露；
- 如果 source 全失败，workflow 标红可以接受，但必须有错误 digest 和 Telegram 告警。

### 6. 常见故障排查

至少包括：

- 没有收到 Telegram；
- Telegram chat id 不对；
- workflow 没有定时触发；
- RSS source 全失败；
- OpenAI summarizer 没有启用；
- artifact 找不到；
- 每天重复旧资讯；
- GitHub Actions cache/state 不生效。

## 八、测试要求

新增或更新测试，不得真实访问外部服务。

必须覆盖：

1. workflow 文件存在；
2. workflow 有 `workflow_dispatch`；
3. workflow 有 `schedule`；
4. workflow 有 collect 命令；
5. workflow 有 artifact upload；
6. workflow 有 Telegram send step；
7. workflow 不硬编码 secret；
8. workflow 能捕获 collect exit code；
9. Telegram 缺 secret 时 skipped；
10. Telegram mock HTTP 成功；
11. Telegram mock HTTP 失败；
12. Telegram 长 digest 分段；
13. 所有 source 失败时 Telegram 内容包含采集失败告警；
14. OpenAI key 缺失时 fallback；
15. deployment-check / doctor 命令不泄露 secret；
16. state/cache 相关逻辑有最小测试；
17. 所有测试不依赖真实 RSS、Telegram、GitHub Actions 或 OpenAI。

## 九、必须运行的验证命令

完成后运行：

```powershell
python -m compileall auv_intel_digest tests
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m auv_intel_digest --help
.\.venv\Scripts\python.exe -m auv_intel_digest check-sources --sources examples\sources.example.json --timeout 20
.\.venv\Scripts\python.exe -m auv_intel_digest collect --sources examples\sources.example.json --output digests\latest.zh.md --limit 30 --language zh --summarizer noop --fail-on-all-source-errors
.\.venv\Scripts\python.exe -m auv_intel_digest send-telegram --markdown digests\latest.zh.md --title "AUV 情报摘要"
```

说明：

- 如果本地 Windows 网络导致 source 全失败，`collect --fail-on-all-source-errors` 返回 2 是可接受的；
- 但它必须生成错误 digest；
- `send-telegram` 在没有环境变量时应 skipped，不应崩溃；
- 如果配置了 Telegram 环境变量，则应能实际发送。

如果你新增了 `deployment-check` 或 `doctor`，也要运行：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest deployment-check
```

或：

```powershell
.\.venv\Scripts\python.exe -m auv_intel_digest doctor
```

## 十、最终输出报告

不要执行 git commit，不要执行 git tag，不要 push。

最后只输出一份收口报告，包括：

1. 当前 v0.5.1 修复了哪些问题；
2. 新增/修改文件清单；
3. GitHub Actions workflow 是否可手动触发；
4. GitHub Actions workflow 每天几点运行；
5. artifact 保存了哪些文件；
6. state/cache 是否能跨运行去重；
7. Telegram 推送是否完整；
8. 所有 source 失败时的行为；
9. OpenAI summarizer 是否可选启用；
10. 本地验证命令和结果；
11. 我需要在 GitHub 上手动配置哪些 Secrets / Variables；
12. 我需要手动点击哪里 Run workflow；
13. 当前是否已经达到“每天自动整理并推送给我”的验收标准；
14. 如果还没有，列出剩余阻断项，不要含糊；
15. 是否建议冻结为 `v0.5.1-cloud-telegram-production-hardening`；
16. 建议 commit message。

验收标准非常严格：

只有当以下条件都满足时，才可以建议冻结 v0.5.1：

- 本地测试通过；
- workflow YAML 自洽；
- 没有硬编码 secret；
- artifact 上传逻辑存在；
- Telegram 推送逻辑存在；
- collect 失败时仍能上传/推送错误摘要；
- state/cache 有明确方案；
- README 是可操作部署手册；
- 用户只需要配置 GitHub Secrets/Variables 并手动 Run workflow 就能验证。
