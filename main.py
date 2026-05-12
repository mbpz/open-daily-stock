# -*- coding: utf-8 -*-
"""
open-daily-stock - A股自选股智能分析系统 (GUI only)

仅支持 GUI 模式，打包后双击即可运行。
"""
import sys
import os
import re
import logging
from pathlib import Path


def _get_version() -> str:
    """Read version from pyproject.toml."""
    pyproject = Path(__file__).parent / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if m:
            return m.group(1)
    return "0.0.0"


__version__ = _get_version()


def setup_logging():
    """Configure basic logging for GUI mode."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filename=log_dir / f"gui_{__version__}.log",
        encoding='utf-8'
    )


def main():
    """GUI entry point — launches Flet desktop app directly."""
    setup_logging()

    # Check for update flag before GUI launch
    if "--check-update" in sys.argv:
        from src.update_service import UpdateService
        latest, url = UpdateService.check_latest_version()
        current = UpdateService.get_current_version()
        if latest:
            print(f"发现新版本: {latest} (当前: {current})")
            print(f"下载链接: {url}")
        else:
            print(f"已是最新版本: {current}")
        return 0

    # Launch GUI
    import flet as ft
    from gui.app import StockApp

    def main(page: ft.Page):
        app = StockApp(page)

    ft.app(target=main)


if __name__ == "__main__":
    sys.exit(main())
