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