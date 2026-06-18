# notification.py 迁移收尾计划

> **接续：** [2026-05-09-notification-modularization.md](./2026-05-09-notification-modularization.md) — 该计划只完成了"建脚手架"的前 3 步（`src/notify/` 子模块 + 6 个 channel + dispatcher + formatters），后两步（NotificationService 搬迁、测试拆分、旧文件 shim 化删除）从未执行。

**目标：** 让 `src/notification.py`（3112 行）从代码库中消失，全部生产代码切到 `src/notify/`，测试通过数不下降（基线 818 passed / 8 skipped / 826 collected）。

**现状（2026-06-18 审计）：**

| 维度 | 旧 `src/notification.py` (3112 行) | 新 `src/notify/` (619 行) |
|------|-------------------------------------|----------------------------|
| 暴露符号 | `BotMessage`、`NotificationChannel`(Enum)、`SMTP_CONFIGS`、`ChannelDetector`、`NotificationService`、`NotificationBuilder`、`get_notification_service()`、`send_daily_report()` | `BaseChannel`、`ChannelResult`、`ChannelPriority`、`NotificationDispatcher`、`MarkdownFormatter` / `SimpleFormatter` / `DashboardFormatter`、6 个 `*Channel` 子类 |
| 生产调用方 | **5 处** in `data_service.py`、`core/pipeline.py`、`core/market_review.py`（全部走老路径） | **1 处** in `plugin_manager.py`（仅枚举 `ALL_CHANNELS` 列名字） |
| 测试 | `tests/test_notification.py` 全文测它 | 无独立测试 |
| 旧→新缺口 | 缺 `NotificationService` facade、缺 `BotMessage` / `NotificationChannel` enum / `SMTP_CONFIGS` / `ChannelDetector` / `NotificationBuilder`、缺 `get_notification_service()` 单例、缺 `send_daily_report()` 顶层函数；channel 实现里可能缺 win10toast、邮件 MIME 高级用法、discord.py 客户端模式（不是 webhook）等细节 | — |

**结论：** 新脚手架还**没承担生产流量**，旧 3112 行才是真正在跑的代码。

---

## 步骤（每步必须保持 818 测试通过）

### 第 0 步：完整审计（30 min，纯调研，无代码改动）

- [ ] 列出 `src/notification.py` 所有顶层 class / function 的公共方法签名（不只是名字）
- [ ] 对每个调用点（data_service.py × 5、core/pipeline.py × 1、core/market_review.py × 1、tests × 4）记录用了哪些方法
- [ ] 把审计结果写入本计划"附录 A：API 表面"
- [ ] **若发现 channel 类已经在新目录实现但缺关键功能**（例：discord.py 是否支持非 webhook 客户端模式、email.py 是否支持附件 / HTML / SMTP_SSL），单独标 ⚠️

### 第 1 步：把 facade 与共享类搬到 `src/notify/`

新增文件：

```
src/notify/
├── service.py        # NotificationService（facade，内部用 NotificationDispatcher）
├── types.py          # BotMessage、NotificationChannel(Enum)、SMTP_CONFIGS、ChannelDetector
├── builder.py        # NotificationBuilder
└── singletons.py     # get_notification_service()、send_daily_report()
```

- [ ] 1.1 把 `BotMessage`、`NotificationChannel(Enum)`、`SMTP_CONFIGS`、`ChannelDetector` 整体迁到 `src/notify/types.py`
- [ ] 1.2 把 `NotificationBuilder` 迁到 `src/notify/builder.py`
- [ ] 1.3 在 `src/notify/service.py` 实现 `NotificationService`，内部用 `NotificationDispatcher` + 各 channel；保持原对外签名一致
- [ ] 1.4 在 `src/notify/singletons.py` 实现 `get_notification_service()`、`send_daily_report()`
- [ ] 1.5 把第 0 步识别出的 channel 缺口（win10toast / 邮件 MIME / discord client 模式 / Bot 限流 / SMTP 重试等）逐个补到 `src/notify/channels/*.py`
- [ ] 1.6 更新 `src/notify/__init__.py`：导出新增的 `NotificationService` 等；**删除**第 7-10 行的 `try: from src.notification import NotificationChannel` 反向依赖

### 第 2 步：~~`src/notification.py` 退化为 shim（3112 行 → ~15 行）~~ **此步取消**

> 决策 1 选了"切到新契约"——pipeline.py 已要重写，旧文件**没必要再做 shim 中转**。
> 改为：第 1 步完成后**直接进第 3 步切流量**（每个调用点改 import 路径 + 改调用方式），中间不留兼容层。

旧路径：第 1 步完成 → 第 2 步 shim（保流量） → 第 3 步切流量 → 第 4 步删
新路径：第 1 步完成 → 第 3' 步切流量+调用方式（一次到位） → 第 5 步删

### 第 3' 步：切流量 + 重写调用方（每个调用点单独 commit）

- [ ] 3.1 `src/data_service.py` × 5：仅 `from src.notify import NotificationService` + `NotificationService().send(message)` 改成 `notifier.send(message).any_success` 或类似——具体形式取决于第 1 步 facade 设计
- [ ] 3.2 `src/core/pipeline.py:28`：`from src.notification import NotificationService, NotificationChannel, BotMessage` → `from src.notify import NotificationService, BotMessage` + `from src.notify.types import NotificationChannel`
- [ ] 3.3 `src/core/pipeline.py:632-664`：30 行重写为新契约形式（用 `notifier.has_channel()` + `notifier.send_to_channel()` + `from src.notify.reports import generate_wechat_dashboard`）
- [ ] 3.4 `src/core/market_review.py:17,27`：仅改 import（类型签名 `notifier: NotificationService` 不变）
- [ ] 3.5 每改一处跑一次完整测试，单独 commit 便于二分

### 第 4 步：测试迁移与拆分

- [ ] 4.1 `tests/test_notification.py` 中 4 处 `from src.notification import ...` → `from src.notify import ...`
- [ ] 4.2 跑测试确认 818 passed
- [ ] 4.3 （可选，可推到下一轮）按原 2026-05-09 计划拆分：
  ```
  tests/test_notify/
  ├── test_channels.py      # 各 channel 单元测试
  ├── test_formatters.py    # formatter 单元测试
  ├── test_dispatcher.py    # dispatcher 路由测试
  └── test_service.py       # facade / builder / singletons
  ```

### 第 5 步：删除 shim

- [ ] 5.1 全仓 `grep -rn "from src.notification\|import src.notification" --include="*.py"` 必须 0 命中（除 src/notification.py 本身）
- [ ] 5.2 `git rm src/notification.py`
- [ ] 5.3 跑 `pytest -q` 确认 818 passed
- [ ] 5.4 跑 `python -c "from src.notify import NotificationService; s = NotificationService(); print('ok')"` smoke test
- [ ] 5.5 提交：`refactor: complete notification.py modularization (P0-2 finish)`

### 第 6 步：同向清理（顺手做，可选）

- [ ] 6.1 `src/notify/__init__.py` 第 7-10 行的 `try: from src.notification import NotificationChannel` fallback 已在 1.6 删过，再确认一遍
- [ ] 6.2 `src/plugin_manager.py:238` 的 `from src.notify.channels import ALL_CHANNELS` 检查是否最优 import 路径
- [ ] 6.3 更新 `ROADMAP.md` 把 P0-2 从"已完成"重新标注，附本计划链接（路线图当前的 P0-2 状态实际是 50%）

---

## 风险与回退

| 风险 | 识别方式 | 回退 |
|------|----------|------|
| 旧文件里塞了散落 helper（SMTP 重试、Bot 限流、富文本组装）漏迁 | 第 0 步审计完成 + 第 1 步分子模块迁移 + 测试覆盖 | 第 1 步内每个 channel 单 commit；shim 已取消，靠测试断言而非 reexport 兜底 |
| Discord 客户端模式（非 webhook）逻辑漏迁 | 第 0 步已识别 → 1.A discord.py 增强 task | 同上 |
| ~~`tests/test_pipeline.py:361` 用 `NotificationChannel` 的方式~~ | 已审计：仅 1 处 enum 引用，第 4.1 步 import 改路径 | — |
| win10toast 仅 Windows 加载，CI 上跑不到 | 1.A windows.py 保留 try/except 平台门控 | — |
| **决策 1 副作用**：pipeline.py 30 行重写 + test_pipeline.py mock 重写 | 第 3'.3 步实施时单独 commit，先 mock 后真跑 | 单 commit 可 revert |
| **决策 2 副作用**：调 `generate_wechat_dashboard()` 的地方需要从 `notifier.X()` 改成 `from src.notify.reports import X` | 仅 pipeline.py 一处 | 同上 |

---

## 完成标准

- [ ] `src/notification.py` 文件不存在
- [ ] `pytest -q` 输出仍是 ≥ 818 passed
- [ ] `grep -rn "src\.notification\b" --include="*.py" .` 命中 0 处（注意：`notification_center` 是另一模块，不在迁移范围）
- [ ] `wc -l src/notify/**/*.py` 总行数较 619 显著上升（吸收了原 3112 行的核心实现）

---

## 附录 A：API 表面（2026-06-18 审计完成）

### A.1 顶层符号（src/notification.py）

```python
@dataclass
class BotMessage:                                     # L56
    content: str = ""
    html_content: str = ""
    image_paths: list = None        # __post_init__ 兜底成 []
    mention_list: list = None       # __post_init__ 兜底成 []

class NotificationChannel(Enum):                      # L72
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSHOVER = "pushover"      # ⚠️ 新目录无对应 channel
    PUSHPLUS = "pushplus"      # ⚠️ 新目录无对应 channel
    CUSTOM = "custom"
    DISCORD = "discord"
    WINDOWS = "windows"        # ⚠️ 新目录无对应 channel
    UNKNOWN = "unknown"

SMTP_CONFIGS: Dict[str, Dict]                         # L87
    # 11 个域: qq/foxmail/163/126/gmail/outlook/hotmail/live/sina/sohu/aliyun/139
    # ⚠️ 新 src/notify/channels/email.py 内嵌的 SMTP_CONFIGS 只有 4 个（缺国内 7 个）

class ChannelDetector:                                # L111
    @staticmethod
    def get_channel_name(channel: NotificationChannel) -> str  # enum→中文名
    # ⚠️ 新目录完全无对应工具

class NotificationBuilder:                            # L2979
    @staticmethod
    def build_simple_alert(title, content, alert_type="info") -> str
    @staticmethod
    def build_stock_summary(results: List[AnalysisResult]) -> str
    # ⚠️ 新目录完全无对应工具

# 顶层便捷函数
def get_notification_service() -> NotificationService                # L3027
def send_daily_report(results: List[AnalysisResult]) -> bool         # L3032
```

### A.2 NotificationService 公共方法（L136-L2977，共 ~2840 行）

```python
class NotificationService:
    def __init__(self, source_message: Optional[BotMessage] = None):
        # 内部读 21 项 config（wechat_webhook_url、feishu_webhook_url、telegram_*、email_*、
        # pushover_*、pushplus_token、custom_webhook_urls/bearer_token、discord_*、
        # feishu_max_bytes、wechat_max_bytes 等）

    # ─── 状态查询 ─────────────────────────────────────────
    def is_available(self) -> bool
    def get_available_channels(self) -> List[NotificationChannel]   # ★ pipeline.py 用
    def get_channel_names(self) -> str

    # ─── 报告生成（~570 行；属"格式化"而非"分发"） ─────
    def generate_daily_report(results, report_date=None) -> str
    def generate_dashboard_report(results, report_date=None) -> str  # 内部调
    def generate_wechat_dashboard(results) -> str                    # ★ pipeline.py 用
    def generate_wechat_summary(results) -> str
    def generate_single_stock_report(result) -> str

    # ─── 单渠道精准发送（旧接口：bool 返回） ──────────
    def send_to_wechat(content) -> bool         # ★ pipeline.py 用
    def send_to_feishu(content) -> bool         # ★ pipeline.py 用
    def send_to_telegram(content) -> bool       # ★ pipeline.py 用
    def send_to_email(content, subject=None) -> bool   # ★ pipeline.py 用
    def send_to_pushover(content, title=None) -> bool  # ★ pipeline.py 用
    def send_to_pushplus(content, title=None) -> bool  # ★ pipeline.py 用
    def send_to_custom(content) -> bool         # ★ pipeline.py 用
    def send_to_discord(content) -> bool        # ★ pipeline.py 用
    def send_to_windows(content, title=None) -> bool
    def send_to_context(content) -> bool        # ★ pipeline.py 用，钉钉/飞书反向回复

    # ─── 统一分发 ────────────────────────────────────
    def send(content) -> bool                   # ★★★ data_service.py 4 处用，最热接口

    # ─── 文件落地 ────────────────────────────────────
    def save_report_to_file(content, filename=None) -> str  # ★ pipeline.py / send_daily_report 用

    # ─── 内部辅助（私有，但不少行数都是私有逻辑） ──
    # _detect_all_channels / _is_*_configured / _has_context_channel
    # _send_wechat_chunked / _send_wechat_force_chunked / _send_wechat_message_with_retry
    # _send_feishu_chunked / _send_feishu_force_chunked / _send_feishu_message_with_retry / _format_feishu_markdown
    # _markdown_to_html (130 行，邮件专用 CSS+tables+code+break-on-newline)
    # _send_telegram_chunked / _send_telegram_message_with_retry / _convert_to_telegram_markdown
    # _markdown_to_plain_text / _send_pushover_message / _send_pushover_chunked
    # _is_dingtalk_webhook / _post_custom_webhook / _post_custom_webhook_with_retry
    # _chunk_markdown_by_bytes / _send_dingtalk_chunked / _build_custom_webhook_payload
    # _send_via_source_context / _send_feishu_stream_reply
    # _send_discord_webhook / _send_discord_bot   ← discord.py 客户端模式
    # _send_chunked_messages / _truncate_to_bytes / _extract_dingtalk_session_webhook / _extract_feishu_reply_info / _get_signal_level
```

### A.3 调用点 × 已用方法矩阵

| 调用点 | 用到的方法 |
|---|---|
| `data_service.py:445` (analyze 完成通知) | `NotificationService()` + `.send(message)` |
| `data_service.py:575` (deep_analyze 完成通知) | 同上 |
| `data_service.py:1753` (大盘复盘通知) | 同上 |
| `data_service.py:2535` (价格异动告警) | 同上 |
| `core/market_review.py:17,27` | 类型签名 `notifier: NotificationService`（依赖注入） |
| `core/pipeline.py:28,51,74` | `NotificationService(source_message=...)` + `BotMessage` 入参 |
| `core/pipeline.py:632-664` | `is_available()` + `get_available_channels()` + `send_to_context()` + `generate_wechat_dashboard()` + `send_to_{wechat,feishu,telegram,email,custom,pushplus,discord,pushover}()` + `NotificationChannel.X` enum 比较 |
| `core/pipeline.py` (其他位置) | `save_report_to_file()` |
| `tests/test_notification.py` × 3 | `NotificationService()` 仅 mock-patch `src.notification.get_config` |
| `tests/test_pipeline.py:361` | `NotificationChannel` enum 引用 |

**结论**：`pipeline.py:632-664` 是最复杂的依赖点——它需要 enum 成员、`get_available_channels()` 返回 enum 列表、8 个 `send_to_X()` 方法、`generate_wechat_dashboard()` 和 `send_to_context()`。这一段几乎用到了 NotificationService 全套接口，迁移时这段 30 行不能动语义。

---

## 附录 B：新 `src/notify/` 当前状态评估

### B.1 已存在但**实现过简**（远不及旧版功能）

| 新文件 | 行数 | 旧对应实现行数 | 缺失关键功能 |
|---|---:|---:|---|
| `channels/wechat.py` | 60 | ~600 | ❌ chunked、force_chunked、retry（tenacity）、字节级截断 `_truncate_to_bytes`、wechat_max_bytes 自适应 |
| `channels/feishu.py` | 48 | ~360 | ❌ chunked、force_chunked、retry、`_format_feishu_markdown`、stream_reply 反向回复 |
| `channels/telegram.py` | 46 | ~150 | ❌ chunked、retry、`_convert_to_telegram_markdown` |
| `channels/email.py` | 90 | ~213 | ⚠️ SMTP_CONFIGS 仅 4 项（缺国内 7 项 SMTP）；`_markdown_to_html` 简化为 `markdown2.markdown(extras=['break-on-newline'])`，**丢失** tables / fenced-code-blocks / cuddled-lists 三个 extras 和 130 行邮件 CSS 样式 |
| `channels/discord.py` | 40 | ~95 | ❌ Bot 客户端模式 `_send_discord_bot`（旧版同时支持 webhook + discord.py Bot 两种） |
| `channels/custom.py` | 54 | ~200 | ❌ DingTalk 检测 `_is_dingtalk_webhook`、多 URL 循环、`_send_dingtalk_chunked`、payload 自适应构建 `_build_custom_webhook_payload`、Bearer token、retry |
| `formatters.py` | 119 | — | ✅ 三个 formatter 框架已建好；但旧 `generate_*()` 5 个方法（~570 行）未迁过来 |
| `dispatcher.py` | 89 | — | ⚠️ 接口语义和旧 `NotificationService.send()` 不同：返回 `List[ChannelResult]` 而非 `bool` |
| `base.py` | 39 | — | ✅ 抽象基类 OK |

### B.2 **完全缺失**的渠道（旧 NotificationService 有，新目录无）

| 渠道 | 旧实现行数 | 缺失影响 |
|---|---:|---|
| ❌ Pushover (`pushover.py`) | ~210 | 用户手机/桌面推送丢失 |
| ❌ PushPlus (`pushplus.py`) | ~64 | 国内推送通道丢失 |
| ❌ Windows Toast (`windows.py`) | ~40 | Windows 平台桌面通知丢失（小，但承诺过） |

### B.3 **完全缺失**的非分发职责

- ❌ `BotMessage` dataclass（pipeline.py 的反向回复入参）
- ❌ `NotificationChannel` Enum（pipeline.py 用作 channel 比较 key）
- ❌ `ChannelDetector.get_channel_name()`（enum→中文名）
- ❌ `NotificationBuilder.build_simple_alert / build_stock_summary`
- ❌ `SMTP_CONFIGS` 完整 11 项域名映射
- ❌ `send_to_context()` + `_send_via_source_context()` + `_send_feishu_stream_reply()` + `_extract_dingtalk_session_webhook()` + `_extract_feishu_reply_info()`（钉钉/飞书反向回复整套）
- ❌ `save_report_to_file()`
- ❌ `generate_*()` 5 个报告生成方法（~570 行）
- ❌ `is_available()` / `get_available_channels()` / `get_channel_names()` 状态查询
- ❌ `get_notification_service()` / `send_daily_report()` 顶层便捷函数

### B.4 接口契约不一致

| 维度 | 旧 NotificationService | 新 BaseChannel / Dispatcher |
|---|---|---|
| 单渠道发送 | `send_to_wechat(content) -> bool` | `WechatChannel.send(content, **kwargs) -> ChannelResult` |
| 全分发 | `notifier.send(content) -> bool` | `dispatcher.send(content, **kwargs) -> List[ChannelResult]` |
| 渠道标识 | `NotificationChannel.WECHAT` (Enum) | 类名字符串 `"WechatChannel"` |
| 状态查询 | `is_available()` / `get_available_channels()` | 无（dispatcher 内部 `self.channels` 列表） |

→ **第 1 步必须在 service.py 里建立"旧契约 → 新实现"的适配层**，否则 pipeline.py 那 30 行不能切换。

---

## 附录 C：工作量修正

第 1 步原拟的"搬 facade 即可"严重低估。修正后清单：

### 第 1 步细化（实际工作量 ~3-4 个工作日）

#### 1.A 补齐 channel 实现（最大块）
- [ ] `notify/channels/pushover.py` 新建（迁移 ~210 行 + chunked + retry）
- [ ] `notify/channels/pushplus.py` 新建（迁移 ~64 行）
- [ ] `notify/channels/windows.py` 新建（迁移 ~40 行，平台门控）
- [ ] `notify/channels/wechat.py` 增强（补 chunked/force_chunked/retry/字节截断，行数 60→~500）
- [ ] `notify/channels/feishu.py` 增强（补 chunked/retry/format/stream_reply，行数 48→~330）
- [ ] `notify/channels/telegram.py` 增强（补 chunked/retry/markdown 转换，行数 46→~140）
- [ ] `notify/channels/email.py` 增强（补全 11 项 SMTP_CONFIGS、还原 130 行 `_markdown_to_html`、添加 SMTPAuthError 友好提示）
- [ ] `notify/channels/discord.py` 增强（补 Bot 客户端模式 `_send_discord_bot`）
- [ ] `notify/channels/custom.py` 增强（补 DingTalk 检测 + 多 URL + retry + payload 构建）
- [ ] `notify/channels/__init__.py` 把 ALL_CHANNELS 扩展到 9 个

#### 1.B 抽出"非分发"职责到独立子模块
- [ ] `notify/types.py`：迁 `BotMessage` + `NotificationChannel` Enum + `SMTP_CONFIGS`（完整 11 项） + `ChannelDetector`
- [ ] `notify/builder.py`：迁 `NotificationBuilder`
- [ ] `notify/reports.py`（**新增**，~570 行）：迁 5 个 `generate_*()` 方法，作为独立报告生成模块（这是"格式化"而非"分发"，架构上应当独立）
- [ ] `notify/context.py`（**新增**）：迁 `_send_via_source_context` / `_send_feishu_stream_reply` / `_extract_dingtalk_session_webhook` / `_extract_feishu_reply_info`，承担"反向回复"职责

#### 1.C 写 facade
- [ ] `notify/service.py`：实现 `NotificationService`，对外保持旧契约（`send_to_X(content) -> bool`、`send(content) -> bool`、`get_available_channels() -> List[NotificationChannel]`），内部用 `NotificationDispatcher` + 各 channel；`__init__(source_message: Optional[BotMessage] = None)` 与旧版一致
- [ ] `notify/singletons.py`：实现 `get_notification_service()` + `send_daily_report()`
- [ ] `notify/__init__.py`：导出 `NotificationService`、`NotificationChannel`、`BotMessage`、`NotificationDispatcher`、`ChannelResult`、`get_notification_service`、`send_daily_report`、`NotificationBuilder`，**删除** L7-10 反向依赖

### 关键决策（2026-06-18 已拍板）

✅ **决策 1：facade 契约切到新风格（NotificationDispatcher 形式）**
- `service.py` 不再保留 `send_to_wechat()` / `send_to_feishu()` 等 8 个旧 bool 方法
- 暴露统一接口：`NotificationService.send(content, channels=None) -> List[ChannelResult]` 或 `dispatcher.send_to_channel(channel_name, content) -> ChannelResult`
- **代价**：`src/core/pipeline.py:632-664` 的 30 行 per-channel 调用必须重写
- 重写示例：
  ```python
  # 旧
  if NotificationChannel.WECHAT in channels:
      dashboard_content = self.notifier.generate_wechat_dashboard(results)
      wechat_success = self.notifier.send_to_wechat(dashboard_content)

  # 新
  if self.notifier.has_channel("wechat"):
      dashboard_content = generate_wechat_dashboard(results)  # 从 notify.reports 直接调
      wechat_result = self.notifier.send_to_channel("wechat", dashboard_content)
      wechat_success = wechat_result.success
  ```
- 影响范围：pipeline.py 30 行 + 对应的 test_pipeline.py mock

✅ **决策 2：5 个 `generate_*()` 报告生成方法独立成 `notify/reports.py`**
- 报告生成是"格式化"而非"分发"职责，物理拆分清晰
- 提供顶层函数：`generate_daily_report(results)` / `generate_dashboard_report(results)` / `generate_wechat_dashboard(results)` / `generate_wechat_summary(results)` / `generate_single_stock_report(result)`
- pipeline.py 调用方式从 `self.notifier.generate_wechat_dashboard()` 改为 `from src.notify.reports import generate_wechat_dashboard`
- `NotificationService` 不再背负这部分职责

---

## 附录 D：调用点清单（迁移时按此 checklist 切换）

```
src/data_service.py:445   from src.notification import NotificationService
src/data_service.py:575   from src.notification import NotificationService
src/data_service.py:1753  from src.notification import NotificationService
src/data_service.py:2535  from src.notification import NotificationService
src/core/market_review.py:17   from src.notification import NotificationService
src/core/pipeline.py:28        from src.notification import NotificationService, NotificationChannel, BotMessage
src/notify/__init__.py:8       try: from src.notification import NotificationChannel  # 反向依赖，第 1.C 步删
tests/test_notification.py:12,61,109   from src.notification import NotificationService
tests/test_pipeline.py:361     from src.notification import NotificationChannel
```

---

*起草: 2026-06-18*
*第 0 步审计完成: 2026-06-18 — 工作量从"3-5 步小迁移"修正为"3-4 工作日完整重构"*
