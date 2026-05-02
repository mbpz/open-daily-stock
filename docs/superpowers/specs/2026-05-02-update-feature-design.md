# Update Feature Design

## Overview

Two main features:
1. **Application Auto-Update (A)** — Check and download new versions via GitHub Releases API
2. **Data Full Refresh (B)** — Refresh market data + run AI analysis + send notifications

## Architecture

### Components

| Component | File | Responsibility |
|------------|------|----------------|
| UpdateService | `src/update_service.py` | Check GitHub releases, download and install updates |
| RefreshService | `src/refresh_service.py` | Orchestrate: refresh → analyze → notify |
| CLI Integration | `main.py` | `--check-update`, `--refresh-data` flags |

### Services

#### UpdateService (`src/update_service.py`)

```python
class UpdateService:
    @staticmethod
    def get_current_version() -> str:
        """Read version from pyproject.toml or git tag"""

    @staticmethod
    def check_latest_version() -> tuple[Optional[str], Optional[str]]:
        """
        Check GitHub releases for latest version.
        Returns: (version: str, download_url: str) or (None, None) if no update
        Uses: https://api.github.com/repos/mbpz/open-daily-stock/releases/latest
        """

    @staticmethod
    def download_and_install(url: str) -> bool:
        """
        Download the asset from url and replace current executable.
        Returns True on success, False on failure.
        """
```

#### RefreshService (`src/refresh_service.py`)

```python
class RefreshService:
    def __init__(self, config: Config):
        self._config = config
        self._dp = DataProviderWrapper()
        self._dp.set_stocks(config.stock_list)
        self._pipeline = StockAnalysisPipeline(config)
        self._notifier = NotificationService()

    async def refresh_all(self) -> list[AnalysisResult]:
        """
        Full refresh: fetch market data → run analysis → send notifications.
        Returns list of analysis results.
        """
        # 1. Fetch all stock data
        await self._dp.fetch_all()

        # 2. Run analysis pipeline
        results = await asyncio.to_thread(
            self._pipeline.run, self._config.stock_list, send_notification=True
        )

        # 3. NotificationService already sends via pipeline.run()
        return results
```

## GUI Integration

### Status Bar (gui/app.py)

- Left: Status text ("最后更新: 10:30:00")
- Center: App version ("v0.2.1")
- Right: Update icon button

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
)
```

### Update Button Behavior

1. **Click update icon** → Call `UpdateService.check_latest_version()`
2. **No update available** → Show snackbar "已是最新版本"
3. **Update available** → Update status bar text to "发现新版本 vX.X.X，点击更新"
4. **Click status bar** → Call `UpdateService.download_and_install()`
5. **Downloading** → Status shows "正在下载更新..."
6. **Complete** → Show "更新完成，重启应用", restart app

### Version Display

- Parse version from `pyproject.toml` or `__version__`
- Show in status bar as "v0.2.1"

## CLI Commands

### `--check-update`

```python
# main.py
if args.check_update:
    from src.update_service import UpdateService
    latest, url = UpdateService.check_latest_version()
    current = UpdateService.get_current_version()
    if latest and latest > current:
        print(f"发现新版本: {latest} (当前: {current})")
        print(f"下载: {url}")
    else:
        print(f"已是最新版本: {current}")
    return 0
```

### `--refresh-data`

```python
if args.refresh_data:
    from src.refresh_service import RefreshService
    from src.config import get_config
    import asyncio

    config = get_config()
    service = RefreshService(config)
    results = asyncio.run(service.refresh_all())
    print(f"刷新完成: {len(results)} 只股票")
    return 0
```

## Scheduled Tasks

### Auto-update Check

- On app start: Check for updates
- Every 6 hours: Background check (don't bother user unless new version)

### Auto Data Refresh

- Config option `schedule_refresh_time: str = "18:00"`
- Daily at configured time: Run `RefreshService.refresh_all()`

## Implementation Order

1. Create `src/update_service.py` with GitHub API check
2. Add `VERSION` constant and `--check-update` CLI flag
3. Create `src/refresh_service.py` with full refresh flow
4. Add `--refresh-data` CLI flag
5. Integrate update button into GUI status bar
6. Add update status to status bar
7. Add scheduled refresh task support

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/update_service.py` | Create |
| `src/refresh_service.py` | Create |
| `main.py` | Modify - add CLI flags |
| `gui/app.py` | Modify - add update button |
| `src/config.py` | Modify - add `schedule_refresh_time` |

## Testing

- `UpdateService.check_latest_version()` mock GitHub API
- `RefreshService.refresh_all()` mock data provider and pipeline
- CLI flags work correctly
- GUI update button shows correct states