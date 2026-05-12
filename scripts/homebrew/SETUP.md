# Homebrew Tap Setup Guide

Cask 由 CI 自动维护在 `mbpz/homebrew-tap`，无需手动操作。

## 一次性初始化（手动）

发布前只需做一次：

### 1. 创建 tap 仓库

```bash
gh repo create mbpz/homebrew-tap --public --description "Homebrew tap for open-daily-stock"
```

或手动创建：https://github.com/new → 仓库名 `homebrew-tap`，Owner `mbpz`，Public

### 2. 初始化仓库结构

```bash
git clone https://github.com/mbpz/homebrew-tap.git
cd homebrew-tap
mkdir -p Formula
echo "# homebrew-tap" > README.md
echo "# Formula directory — managed by CI" > Formula/.gitkeep
git add README.md Formula/.gitkeep
git commit -m "init"
git push -u origin main
```

### 3. 添加 TAP_REPO_TOKEN 秘钥

在 https://github.com/mbpz/open-daily-stock/settings/secrets/actions 新建：

- **Name**: `TAP_REPO_TOKEN`
- **Value**: 有 `repo` 权限的 GitHub PAT
  - https://github.com/settings/tokens → Generate new token (classic) → 勾选 `repo`

## 发布流程（自动）

```bash
git tag v0.5.0 && git push origin v0.5.0
```

CI 自动：
1. macos-14 构建 arm64 DMG + ad-hoc 签名
2. macos-13 构建 x64 DMG + ad-hoc 签名
3. 发布到 GitHub Release
4. **推送 Cask 到 `mbpz/homebrew-tap`**（含真实 SHA256）

## 用户安装

```bash
brew install --cask mbpz/tap/open-daily-stock
```
