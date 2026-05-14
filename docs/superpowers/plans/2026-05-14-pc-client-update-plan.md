# PC Client Update Feature + Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add version display, update checking, and icon generation to the PC client

**Architecture:** App reads version from VERSION constant in gui/app.py. Update checker calls GitHub API on startup (if enabled). Settings page shows version + update status. Icon generated via Python PIL script.

**Tech Stack:** Python PIL for icon generation, requests for GitHub API, flet for UI

---

## File Structure

```
gui/app.py                    # VERSION constant + init UpdateChecker
src/update_checker.py        # NEW - GitHub API update checker
gui/components/update_banner.py  # NEW - update notification UI
gui/pages/config.py           # Add version display + update settings
scripts/generate_icon.py      # NEW - icon generation script
.github/workflows/build.yml   # FIX - homebrew-tap job
.github/workflows/release-dmg.yml  # FIX - finalize job
```

---

## Task 1: Icon Generation Script

**Files:**
- Create: `scripts/generate_icon.py`
- Output: `assets/icon.png` (1024x1024), `assets/icon.icns`, `assets/icon.ico`

- [ ] **Step 1: Write icon generation script**

```python
#!/usr/bin/env python3
"""Generate ODS app icon with purple-blue gradient"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size=1024):
    """Create ODS icon with gradient and letter styling"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient colors: purple (#8B5CF6) to blue (#3B82F6)
    gradient_colors = [
        (139, 92, 246),   # #8B5CF6 - purple
        (99, 102, 241),   # #6366F1
        (59, 130, 246),   # #3B82F6 - blue
    ]

    # Draw rounded rectangle background with gradient
    # Create gradient background
    for y in range(size):
        ratio = y / size
        r = int(139 + (59 - 139) * ratio)
        g = int(92 + (130 - 92) * ratio)
        b = int(246 + (246 - 246) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Draw ODS text - using simple shapes since font may not be available
    padding = size // 8
    letter_width = (size - 2 * padding) // 3

    # O - circle with stock chart inside
    o_x = padding + letter_width // 2
    o_y = size // 2
    o_radius = letter_width // 2
    draw.ellipse([o_x - o_radius, o_y - o_radius,
                  o_x + o_radius, o_y + o_radius],
                 fill=(255, 255, 255, 255), outline=(255, 255, 255, 255), width=3)

    # Stock chart line inside O
    chart_y = [o_y - o_radius//2, o_y + o_radius//4, o_y - o_radius//4, o_y + o_radius//3]
    for i in range(len(chart_y)-1):
        x1 = o_x - o_radius//2 + i * (o_radius // (len(chart_y)-1))
        x2 = o_x - o_radius//2 + (i+1) * (o_radius // (len(chart_y)-1))
        draw.line([(x1, chart_y[i]), (x2, chart_y[i+1])],
                  fill=(139, 92, 246, 255), width=2)

    # D - vertical bar with curve
    d_x = padding + letter_width + letter_width // 2
    draw.rectangle([d_x - 8, -o_radius, d_x + 8, o_radius], fill=(255, 255, 255, 255))
    draw.ellipse([d_x - 8, -o_radius, d_x + 60, o_radius],
                 fill=(255, 255, 255, 255))

    # S - curved S shape
    s_x = padding + 2 * letter_width + letter_width // 2
    # Draw S using arcs
    draw.arc([s_x - 25, -o_radius//2, s_x + 25, o_radius//2],
             start=0, end=180, fill=(255, 255, 255, 255), width=8)
    draw.arc([s_x - 25, -o_radius//2, s_x + 25, o_radius//2],
             start=180, end=360, fill=(255, 255, 255, 255), width=8)

    return img

if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)

    # Generate 1024x1024 PNG
    icon = create_icon(1024)
    icon.save("assets/icon.png", "PNG")
    print("Created assets/icon.png")

    # Generate ICNS (macOS) - simplified, just copy PNG for now
    icon.save("assets/icon.icns", "PNG")
    print("Created assets/icon.icns (as PNG)")

    # Generate ICO (Windows) - multiple sizes embedded
    ico_sizes = [256, 128, 64, 48, 32, 16]
    ico_images = []
    for sz in ico_sizes:
        ico_images.append(create_icon(sz))
    icon.save("assets/icon.ico", "ICO", sizes=[(s, s) for s in ico_sizes])
    print("Created assets/icon.ico")
```

- [ ] **Step 2: Run script to verify icon generation**

Run: `python scripts/generate_icon.py`
Expected: Creates assets/icon.png, .icns, .ico

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_icon.py assets/
git commit -m "feat: add icon generation script"
```

---

## Task 2: Update Checker Service

**Files:**
- Create: `src/update_checker.py`
- Test: `tests/test_update_checker.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_update_checker.py
import pytest
from unittest.mock import patch, Mock

def test_check_update_returns_latest_version():
    """Test that check_update returns latest version from GitHub"""
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes and improvements"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker()
        latest = checker.check_latest_version()
        assert latest == "v0.5.0"

def test_check_update_detects_new_version():
    """Test detection when current version is older"""
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker(current_version="v0.4.0")
        assert checker.is_new_version_available() == True

def test_check_update_no_new_version():
    """Test when current version matches latest"""
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker(current_version="v0.5.0")
        assert checker.is_new_version_available() == False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_checker.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/update_checker.py
"""GitHub releases update checker"""
import requests
from typing import Optional, Tuple

REPO = "mbpz/open-daily-stock"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

class UpdateChecker:
    """Check for app updates via GitHub Releases API"""

    def __init__(self, current_version: str = "0.0.0"):
        self.current_version = current_version.strip('v')
        self._latest_version: Optional[str] = None
        self._release_notes: Optional[str] = None

    def check_latest_version(self) -> Optional[str]:
        """Fetch latest release version from GitHub"""
        try:
            response = requests.get(
                API_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self._latest_version = data.get("tag_name", "").strip('v')
            self._release_notes = data.get("body", "")[:200]
            return self._latest_version
        except Exception:
            return None

    def is_new_version_available(self) -> bool:
        """Check if a newer version is available"""
        latest = self.check_latest_version()
        if not latest:
            return False
        return self._compare_versions(self.current_version, latest) < 0

    def get_release_info(self) -> Tuple[str, str]:
        """Return (version, release_notes)"""
        if not self._latest_version:
            self.check_latest_version()
        return (self._latest_version or self.current_version,
                self._release_notes or "")

    @staticmethod
    def _compare_versions(current: str, latest: str) -> int:
        """Compare versions: -1 if current < latest, 0 if equal, 1 if current > latest"""
        from packaging import version
        try:
            if version.parse(current) < version.parse(latest):
                return -1
            elif version.parse(current) > version.parse(latest):
                return 1
            return 0
        except Exception:
            return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_update_checker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/update_checker.py tests/test_update_checker.py
git commit -m "feat: add GitHub release update checker"
```

---

## Task 3: Update Banner UI Component

**Files:**
- Create: `gui/components/update_banner.py`
- Modify: `gui/app.py:50` (add UpdateChecker init)

- [ ] **Step 1: Write update banner component**

```python
# gui/components/update_banner.py
"""Update notification banner and dialog"""
import flet as ft
from typing import Optional

class UpdateBanner(ft.Container):
    """Banner shown when new version is available"""

    def __init__(self, app, version: str, notes: str, on_download, on_dismiss):
        super().__init__()
        self.app = app
        self.version = version
        self.notes = notes
        self.on_download = on_download
        self.on_dismiss = on_dismiss

        self.content = ft.Container(
            bgcolor="#2D1B69",  # dark purple
            padding=10,
            border_radius=8,
            content=ft.Row([
                ft.Icon(ft.Icons.UPDATE, color=ft.Colors.WHITE),
                ft.Text(f"发现新版本 {version}", color=ft.Colors.WHITE, expand=True),
                ft.TextButton("下载", on_click=self._on_download,
                              style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                ft.IconButton(ft.Icons.CLOSE, on_click=self._on_dismiss,
                              icon_color=ft.Colors.WHITE),
            ], alignment=ft.MainAxisAlignment.CENTER),
        )

    def _on_download(self, e):
        self.on_download(self.version)

    def _on_dismiss(self, e):
        self.on_dismiss(self.version)


class UpdateDialog(ft.AlertDialog):
    """Dialog shown first time a new version is detected"""

    def __init__(self, version: str, notes: str, on_download, on_ignore):
        super().__init__()
        self.modal = True
        self.title = ft.Text(f"发现新版本 v{version}")
        self.content = ft.Column([
            ft.Text("有可用更新，建议立即升级以获得最新功能。"),
            ft.Container(height=5),
            ft.Text(notes[:100] + "..." if len(notes) > 100 else notes,
                    size=12, color=ft.Colors.GREY_600),
        ])
        self.actions = [
            ft.TextButton("下载更新", on_click=on_download),
            ft.TextButton("忽略此版本", on_click=on_ignore),
        ]
        self.actions_alignment = ft.MainAxisAlignment.END
```

- [ ] **Step 2: Integrate UpdateChecker in app**

Modify `gui/app.py` around line 50:
```python
# Add after existing init code:
from src.update_checker import UpdateChecker

class StockApp:
    def __init__(self, page: ft.Page):
        # ... existing init code ...

        # Update checker
        self._update_checker = UpdateChecker(current_version=VERSION)
        self._update_banner = None
        self._new_version_available = None

        # Check for updates on startup if enabled
        self._check_update_on_startup()
```

Add method to StockApp:
```python
def _check_update_on_startup(self):
    """Check for updates if auto_check is enabled"""
    config = get_config()
    if config.auto_check_update:
        if self._update_checker.is_new_version_available():
            version, notes = self._update_checker.get_release_info()
            self._show_update_dialog(version, notes)
```

- [ ] **Step 3: Test UI builds without error**

Run: `python -c "from gui.app import StockApp; print('OK')"`
Expected: No import errors

- [ ] **Step 4: Commit**

```bash
git add gui/components/update_banner.py gui/app.py
git commit -m "feat: add update banner and dialog UI"
```

---

## Task 4: Settings Page Version Display

**Files:**
- Modify: `gui/pages/config.py` - add version display section

- [ ] **Step 1: Add version section to settings page**

In `gui/pages/config.py`, add import:
```python
from gui.app import VERSION
```

Add version section in `__init__` after `header`:
```python
header = ft.Text(_("配置管理"), size=24, weight=ft.FontWeight.BOLD)

# Version info section
version_text = ft.Text(f"当前版本: v{VERSION}", size=14, color=ft.Colors.GREY_400)
version_row = ft.Row([
    version_text,
    ft.TextButton("检查更新", on_click=self._check_update, icon=ft.Icons.UPDATE),
])
version_section = ft.Container(
    content=ft.Column([version_text, version_row]),
    padding=15,
    bgcolor=CARD_BG,
    border_radius=10,
)
```

Add method to ConfigPage:
```python
def _check_update(self, e):
    """Manually trigger update check"""
    from src.update_checker import UpdateChecker
    checker = UpdateChecker(current_version=VERSION)
    if checker.is_new_version_available():
        version, notes = checker.get_release_info()
        self.page.show_update_dialog(version, notes)
    else:
        self.page.show_snackbar_bar(ft.SnackBar(content=ft.Text("已是最新版本")))
```

- [ ] **Step 2: Test settings page renders**

Run: `python -c "from gui.pages.config import ConfigPage; print('OK')"`
Expected: No import errors

- [ ] **Step 3: Commit**

```bash
git add gui/pages/config.py
git commit -m "feat: add version display in settings page"
```

---

## Task 5: CI Workflow Fixes

**Files:**
- Modify: `.github/workflows/build.yml:78` - change to HOMEBREW_TAP_TOKEN
- Modify: `.github/workflows/release-dmg.yml:211` - use HOMEBREW_TAP_TOKEN

- [ ] **Step 1: Fix build.yml homebrew-tap job**

Change in `.github/workflows/build.yml` line 78:
```yaml
token: ${{ secrets.HOMEBREW_TAP_TOKEN }}
```
(should already be correct, verify)

- [ ] **Step 2: Fix release-dmg.yml finalize job**

Change in `.github/workflows/release-dmg.yml` around line 211:
```yaml
env:
  TAP_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}
```
Change all occurrences of `TAP_REPO_TOKEN` to `HOMEBREW_TAP_TOKEN`

- [ ] **Step 3: Trigger test CI run**

Run: `git tag v0.5.1 && git push origin v0.5.1`
Expected: CI runs, homebrew-tap job succeeds

- [ ] **Step 4: Verify tap repo updated**

Check: `https://github.com/mbpz/homebrew-open-daily-stock/blob/main/Formula/open-daily-stock.rb`

- [ ] **Step 5: Cleanup test tag**

Run: `git tag -d v0.5.1 && git push origin :v0.5.1`

---

## Task 6: Config Auto-Update Setting

**Files:**
- Modify: `src/config.py` - add auto_check_update field
- Modify: `gui/pages/config.py` - add auto-check toggle

- [ ] **Step 1: Add auto_check_update to Config dataclass**

In `src/config.py`, add field:
```python
auto_check_update: bool = True
```

- [ ] **Step 2: Add toggle in settings page**

In `gui/pages/config.py`, add in `__init__`:
```python
auto_check_switch = ft.Switch(
    label=_("启动时自动检查更新"),
    value=config.auto_check_update,
    on_change=self._on_auto_check_change,
)
```

Add handler:
```python
def _on_auto_check_change(self, e):
    self._auto_check_enabled = e.control.value
```

And save it in `_save_config`:
```python
config.auto_check_update = self._auto_check_enabled
```

---

## Spec Coverage Check

| Spec Section | Task |
|--------------|------|
| Icon design (ODS gradient) | Task 1 |
| Version display | Task 4 |
| GitHub release check | Task 2 |
| Update notification (popup) | Task 3 |
| Update notification (badge) | Task 3 |
| Auto-check setting | Task 6 |
| CI trigger + tap update | Task 5 |
| Config persistence | Task 6 |

**Plan complete.**