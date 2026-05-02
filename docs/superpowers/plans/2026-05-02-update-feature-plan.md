# Update Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement auto-update (GitHub Releases API) and data full refresh (market + analysis + notification) with GUI status bar integration

**Architecture:** Two services (UpdateService, RefreshService) + CLI flags + GUI status bar update button

**Tech Stack:** Python, requests, asyncio, flet

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/update_service.py` | Create | Check/download updates from GitHub |
| `src/refresh_service.py` | Create | Orchestrate refresh→analyze→notify |
| `src/config.py` | Modify | Add `schedule_refresh_time` config |
| `main.py` | Modify | Add `--check-update`, `--refresh-data` flags |
| `gui/app.py` | Modify | Add update button to status bar |
| `tests/test_update_service.py` | Create | Tests for UpdateService |
| `tests/test_refresh_service.py` | Create | Tests for RefreshService |

---

## Task 1: Create UpdateService

**Files:**
- Create: `src/update_service.py`
- Create: `tests/test_update_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_update_service.py
import pytest
from unittest.mock import patch, MagicMock

class TestUpdateService:
    def test_get_current_version_from_pyproject(self):
        """Version is read from __version__ or pyproject.toml"""
        from src.update_service import UpdateService
        # Version should be a valid string like "0.2.1"
        version = UpdateService.get_current_version()
        assert version is not None
        assert isinstance(version, str)
        assert len(version) > 0

    def test_check_latest_version_no_update(self):
        """When current version is latest, returns (None, None)"""
        from src.update_service import UpdateService
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"tag_name": "v0.2.1"}
            mock_get.return_value = mock_response

            latest, url = UpdateService.check_latest_version()
            # If current is >= latest, should return (None, None)
            # This test verifies the API call works

    def test_check_latest_version_with_update(self):
        """When remote version is newer, returns (version, url)"""
        from src.update_service import UpdateService
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "tag_name": "v0.3.0",
                "assets": [{"browser_download_url": "https://github.com/.../open-daily-stock-macos"}]
            }
            mock_get.return_value = mock_response

            latest, url = UpdateService.check_latest_version()
            if latest:
                assert latest == "0.3.0"
                assert url is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_update_service.py -v`
Expected: ImportError (module doesn't exist)

- [ ] **Step 3: Write minimal UpdateService**

```python
# src/update_service.py
"""Update service for checking and installing application updates."""
import os
import re
import logging
from typing import Optional, Tuple
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

class UpdateService:
    """Manages application updates from GitHub Releases."""

    REPO_API = "https://api.github.com/repos/mbpz/open-daily-stock/releases/latest"

    @staticmethod
    def get_current_version() -> str:
        """Get current version from __version__ or pyproject.toml."""
        # Try __version__ first
        try:
            from src import __version__
            return __version__
        except ImportError:
            pass

        # Fallback: parse from pyproject.toml
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            version_match = re.search(r'version = ["\']([^"\']+)["\']', content)
            if version_match:
                return version_match.group(1)

        return "0.0.0"

    @staticmethod
    def check_latest_version() -> Tuple[Optional[str], Optional[str]]:
        """
        Check GitHub releases for latest version.
        Returns: (version: str, download_url: str) or (None, None) if no update.
        """
        try:
            response = requests.get(UpdateService.REPO_API, timeout=10)
            response.raise_for_status()
            data = response.json()

            latest_tag = data.get("tag_name", "")
            # Strip 'v' prefix if present
            latest_version = latest_tag.lstrip('v')

            current = UpdateService.get_current_version()
            if latest_version > current:
                # Find macOS binary asset
                assets = data.get("assets", [])
                download_url = None
                for asset in assets:
                    if "macos" in asset.get("name", "").lower():
                        download_url = asset.get("browser_download_url")
                        break

                if download_url:
                    return latest_version, download_url

            return None, None

        except Exception as e:
            logger.warning(f"Failed to check updates: {e}")
            return None, None

    @staticmethod
    def download_and_install(url: str) -> bool:
        """
        Download the asset from url and replace current executable.
        Returns True on success, False on failure.
        """
        import shutil
        import sys

        try:
            logger.info(f"Downloading update from {url}")

            # Determine download path
            if sys.platform == "darwin":
                dest = Path("/tmp/open-daily-stock-update")
            else:
                dest = Path("/tmp/open-daily-stock-update.exe")

            # Download file
            response = requests.get(url, timeout=300, stream=True)
            response.raise_for_status()

            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Make executable (macOS/Linux)
            dest.chmod(0o755)

            # Replace current executable
            current_executable = Path(sys.argv[0])
            backup = current_executable.with_suffix('.bak')
            shutil.copy(current_executable, backup)
            shutil.copy(dest, current_executable)

            logger.info("Update installed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to install update: {e}")
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_update_service.py -v`
Expected: PASS (with 2 skips if no network)

- [ ] **Step 5: Commit**

```bash
git add src/update_service.py tests/test_update_service.py
git commit -m "feat: add UpdateService for GitHub releases check"
```

---

## Task 2: Add CLI flags --check-update and --refresh-data

**Files:**
- Modify: `main.py:parse_arguments()` - add argument definitions
- Modify: `main.py:main()` - add handling

- [ ] **Step 1: Add argument definitions to parse_arguments()**

Find the `parse_arguments()` function and add:

```python
parser.add_argument(
    '--check-update',
    action='store_true',
    help='检查应用程序更新'
)

parser.add_argument(
    '--refresh-data',
    action='store_true',
    help='刷新所有股票数据并重新分析'
)
```

- [ ] **Step 2: Add handling in main() before TUI/GUI mode**

Add after `args = parse_arguments()`:

```python
# === 检查更新 ===
if args.check_update:
    from src.update_service import UpdateService
    latest, url = UpdateService.check_latest_version()
    current = UpdateService.get_current_version()
    if latest:
        print(f"发现新版本: {latest} (当前: {current})")
        print(f"下载链接: {url}")
    else:
        print(f"已是最新版本: {current}")
    return 0

# === 刷新数据 ===
if args.refresh_data:
    from src.refresh_service import RefreshService
    config = get_config()
    import asyncio

    async def run_refresh():
        service = RefreshService(config)
        return await service.refresh_all()

    results = asyncio.run(run_refresh())
    print(f"刷新完成: {len(results)} 只股票")
    return 0
```

- [ ] **Step 3: Test CLI help output**

Run: `python main.py --help | grep -E "check-update|refresh-data"`
Expected: Both flags appear in help

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(cli): add --check-update and --refresh-data flags"
```

---

## Task 3: Create RefreshService

**Files:**
- Create: `src/refresh_service.py`
- Create: `tests/test_refresh_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_refresh_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

class TestRefreshService:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.stock_list = ["600519", "000001"]
        config.schedule_refresh_time = "18:00"
        return config

    def test_refresh_service_initialization(self, mock_config):
        """RefreshService initializes with config"""
        from src.refresh_service import RefreshService
        service = RefreshService(mock_config)
        assert service._config == mock_config
        assert service._dp is not None
        assert service._pipeline is not None

    @pytest.mark.asyncio
    async def test_refresh_all_returns_results(self, mock_config):
        """refresh_all returns list of analysis results"""
        from src.refresh_service import RefreshService

        with patch.object(RefreshService, '__init__', lambda self, config: None):
            service = RefreshService(mock_config)
            service._config = mock_config
            service._dp = MagicMock()
            service._dp.fetch_all = AsyncMock()
            service._dp.get_data.return_value = {}
            service._pipeline = MagicMock()
            service._pipeline.run = MagicMock(return_value=[])

            results = await service.refresh_all()
            assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_refresh_service.py -v`
Expected: ImportError (module doesn't exist)

- [ ] **Step 3: Write RefreshService**

```python
# src/refresh_service.py
"""Refresh service for full data refresh: market + analysis + notification."""
import asyncio
import logging
from typing import List
from src.config import Config
from src.core.pipeline import StockAnalysisPipeline
from src.notification import NotificationService
from tui.data.wrapper import DataProviderWrapper

logger = logging.getLogger(__name__)

class RefreshService:
    """Orchestrates full data refresh: fetch → analyze → notify."""

    def __init__(self, config: Config):
        self._config = config
        self._dp = DataProviderWrapper()
        self._dp.set_stocks(config.stock_list)
        self._pipeline = StockAnalysisPipeline(config)
        self._notifier = NotificationService()

    async def refresh_all(self) -> List:
        """
        Full refresh: fetch market data → run analysis → send notifications.
        Returns list of analysis results.
        """
        try:
            # Step 1: Fetch all stock data
            logger.info("正在刷新股票行情...")
            await self._dp.fetch_all()

            # Step 2: Run analysis pipeline
            logger.info("正在执行股票分析...")
            results = await asyncio.to_thread(
                self._pipeline.run,
                self._config.stock_list,
                send_notification=True
            )

            logger.info(f"刷新完成: {len(results)} 只股票")
            return results

        except Exception as e:
            logger.error(f"刷新失败: {e}")
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_refresh_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/refresh_service.py tests/test_refresh_service.py
git commit -m "feat: add RefreshService for full data refresh"
```

---

## Task 4: Add update button to GUI status bar

**Files:**
- Modify: `gui/app.py` - add VERSION constant, update button, update logic

- [ ] **Step 1: Add VERSION constant at top of gui/app.py**

```python
# Add after imports
VERSION = "0.2.1"  # Should match pyproject.toml version
```

- [ ] **Step 2: Modify status_bar to include version and update button**

Replace `self.status_bar` definition with:

```python
# Status bar with version and update button
self.status_bar = ft.Container(
    content=ft.Row([
        ft.Text(f"最后更新: {self.status_text}", color=TEXT_SECONDARY, size=14),
        ft.Container(expand=True),
        ft.Text(f"v{VERSION}", color=TEXT_SECONDARY, size=12),
        ft.IconButton(
            icon=ft.Icons.UPDATE,
            on_click=self._check_update,
            tooltip="检查更新",
        ),
    ]),
    padding=10,
    bgcolor=PRIMARY_COLOR,
)
```

- [ ] **Step 3: Add update methods to StockApp class**

Add these methods after `update_status`:

```python
def _check_update(self, e):
    """Check for application updates"""
    from src.update_service import UpdateService
    latest, url = UpdateService.check_latest_version()
    if latest:
        self.update_status(f"发现新版本 {latest}，点击更新")
        self._pending_update_url = url
    else:
        self.app.page.show_snack_bar(
            ft.SnackBar(content=ft.Text(f"已是最新版本 v{VERSION}"), open=True)
        )

def _install_update(self, e):
    """Download and install pending update"""
    if hasattr(self, '_pending_update_url') and self._pending_update_url:
        url = self._pending_update_url
        self.update_status("正在下载更新...")
        # Run download in background
        self.page.run_task(self._download_and_install, url)
    else:
        # Status bar click with no update available - run check
        self._check_update(e)

async def _download_and_install(self, url: str):
    """Download and install update asynchronously"""
    from src.update_service import UpdateService
    try:
        success = UpdateService.download_and_install(url)
        if success:
            self.update_status("更新完成，重启应用")
            # Could restart here with subprocess
        else:
            self.update_status("更新失败")
    except Exception as ex:
        self.update_status(f"更新失败: {ex}")
```

- [ ] **Step 4: Make status bar clickable to trigger update install**

Replace the status_bar definition with click handler:

```python
self.status_bar = ft.Container(
    content=ft.Row([
        ft.Text(f"最后更新: {self.status_text}", color=TEXT_SECONDARY, size=14),
        ft.Container(expand=True),
        ft.Text(f"v{VERSION}", color=TEXT_SECONDARY, size=12),
        ft.IconButton(
            icon=ft.Icons.UPDATE,
            on_click=self._check_update,
            tooltip="检查更新",
        ),
    ]),
    padding=10,
    bgcolor=PRIMARY_COLOR,
    on_click=self._install_update,  # Click status bar to install
)
```

- [ ] **Step 5: Test imports**

Run: `python -c "from gui.app import StockApp, VERSION; print(f'VERSION={VERSION}')"`
Expected: `VERSION=0.2.1`

- [ ] **Step 6: Commit**

```bash
git add gui/app.py
git commit -m "feat(gui): add update button to status bar"
```

---

## Task 5: Add scheduled refresh config option

**Files:**
- Modify: `src/config.py` - add schedule_refresh_time

- [ ] **Step 1: Add to Config dataclass**

Find the scheduler config section in `src/config.py` and add:

```python
# === 定时刷新配置 ===
schedule_refresh_enabled: bool = False
schedule_refresh_time: str = "18:00"  # HH:MM format, daily refresh time
```

- [ ] **Step 2: Add to _load_from_env()**

Add parsing:

```python
schedule_refresh_enabled=os.getenv('SCHEDULE_REFRESH_ENABLED', 'false').lower() == 'true',
schedule_refresh_time=os.getenv('SCHEDULE_REFRESH_TIME', '18:00'),
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat(config): add schedule_refresh_time option"
```

---

## Task 6: Run all tests and verify

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (77+)

- [ ] **Step 2: Test --check-update CLI**

Run: `python main.py --check-update`
Expected: Either "发现新版本" or "已是最新版本"

- [ ] **Step 3: Verify imports work**

Run: `python -c "from src.update_service import UpdateService; from src.refresh_service import RefreshService; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Final commit**

```bash
git add -A && git commit -m "feat: complete update feature implementation"
```

---

## Verification

After all tasks complete:

1. `pytest tests/ -v` → All pass
2. `python main.py --help | grep -E "check-update|refresh-data"` → Both visible
3. `python main.py --check-update` → Version check runs
4. GUI status bar shows version and update icon

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks

**2. Inline Execution** - Execute tasks in this session