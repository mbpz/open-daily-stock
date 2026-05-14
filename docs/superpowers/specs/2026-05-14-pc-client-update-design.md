# PC 客户端更新功能 + 图标设计

**日期：** 2026-05-14

**状态：** 已批准

## 1. 应用图标设计

### 1.1 设计规范

| 属性 | 值 |
|------|-----|
| 设计 | ODS 三个字母创意变形，O 是股票走势图，字母连成一体 |
| 配色 | 渐变紫 (#8B5CF6) → 蓝 (#3B82F6)，AI/智能感 |
| 格式 | 1024×1024 PNG + ICNS (macOS) + ICO (Windows) |
| 风格 | 扁平化现代，无多余装饰 |

### 1.2 生成方式

- 使用 Python PIL 生成 PNG
- 使用 System Integrity Protection (SIP) 兼容工具转 ICNS/ICO

---

## 2. 版本展示

### 2.1 需求

- 版本从 GitHub tag 读取
- 在设置页显示当前版本
- 版本格式：`v0.5.0`

### 2.2 实现

- GUI 从 `src/config.py` 或 `gui/app.py` 读取 VERSION 常量
- CI 构建时将 tag 版本写入 `src/version.py` 或注入到二进制
- 设置页添加版本信息区块

---

## 3. GitHub Releases 检查更新

### 3.1 需求

- 非 Homebrew 用户可在 App 内检查更新
- 启动时可选自动检查（默认开）
- 用户可在设置中关闭启动检查

### 3.2 实现

```
更新检查服务：
- 检查频率：启动时检查（可关闭）+ 用户手动触发
- API：GET https://api.github.com/repos/mbpz/open-daily-stock/releases/latest
- 比较：当前版本 vs tag 名称（如 v0.5.0）
```

### 3.3 设置项

| 配置项 | 类型 | 默认值 |
|--------|------|--------|
| auto_check_update | bool | true |
| last_check_time | datetime | null |

---

## 4. 更新通知

### 4.1 需求

- 首次检测到新版本：弹窗提醒，用户可跳转下载或忽略
- 之后在设置页显示 badge："有新版本可用"
- 直至用户升级

### 4.2 UI 设计

**弹窗设计：**
- 标题：发现新版本 v{x.x.x}
- 内容：更新内容描述（从 release notes 截取前 100 字符）
- 按钮：【下载更新】【忽略此版本】
- 可选：不再提醒checkbox

**设置页 Badge：**
- 版本信息区块下显示红色徽章"有新版本"
- 点击跳转下载页

### 4.3 数据存储

```python
# 本地存储
{
    "ignored_version": "0.5.0",  # 忽略的版本号，升级后清空
    "auto_check_update": true,
    "last_check_time": "2026-05-14T10:00:00Z"
}
```

---

## 5. CI 触发 + tap 仓库自动更新

### 5.1 当前状态

- `build.yml`：构建 three platforms (ubuntu/macos/windows)
- `release-dmg.yml`：macOS DMG 构建 + Homebrew Cask 更新
- 已创建 `mbpz/homebrew-open-daily-stock` 仓库

### 5.2 待完成

1. CI 日志显示 `homebrew-tap` job 失败（Get info step 失败）
2. `release-dmg.yml` 的 `finalize` job 使用 `TAP_REPO_TOKEN` 但 secret 名是 `HOMEBREW_TAP_TOKEN`
3. 需统一 secret 命名

### 5.3 修复项

| 文件 | 问题 | 修复 |
|------|------|------|
| `build.yml` | `HOMEBREW_TAP_TOKEN` 可能缺失 | 确认 secret 配置 |
| `release-dmg.yml` finalize job | 使用 `TAP_REPO_TOKEN` | 改为 `HOMEBREW_TAP_TOKEN` |
| `release-dmg.yml` | 使用 cask 而非 formula | 保持 cask（更标准） |

---

## 6. 技术实现计划

### 6.1 文件变更

| 文件 | 操作 |
|------|------|
| `gui/app.py` | 添加 VERSION 读取，初始化更新检查器 |
| `gui/pages/settings_page.py` | 添加版本信息显示、更新设置 |
| `src/update_checker.py` | 新文件，更新检查逻辑 |
| `gui/components/update_banner.py` | 新文件，更新弹窗/banner |
| `scripts/generate_icon.py` | 新文件，图标生成脚本 |
| `docs/superpowers/specs/2026-05-14-pc-client-update-design.md` | 本文件 |

### 6.2 更新流程

```
App 启动
  → 检查 auto_check_update 是否为 true
  → 调用 GitHub API 检查 latest release
  → 比较当前版本 vs 最新版本
  → 若有新版本：
      - 首次：弹窗提醒
      - 后续：设置页 badge
```

### 6.3 GitHub Release 检查

```python
def check_update():
    url = "https://api.github.com/repos/mbpz/open-daily-stock/releases/latest"
    response = requests.get(url, headers={"Accept": "application/vnd.github+json"})
    latest = response.json()["tag_name"]  # e.g., "v0.5.0"
    return latest != current_version
```

---

## 7. 验收标准

- [ ] App 设置页显示当前版本号
- [ ] 启动时自动检查更新（默认开，可关闭）
- [ ] 检测到新版本时弹窗提醒
- [ ] 设置页显示"有新版本"badge
- [ ] 用户可手动触发更新检查
- [ ] 图标生成脚本可生成 1024x1024 PNG + ICNS
- [ ] CI 触发后 tap 仓库自动更新