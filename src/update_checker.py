"""GitHub releases update checker"""
import requests
from typing import Optional, Tuple

REPO = "mbpz/open-daily-stock"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

class UpdateChecker:
    def __init__(self, current_version: str = "0.0.0"):
        self.current_version = current_version.strip('v')
        self._latest_version: Optional[str] = None
        self._release_notes: Optional[str] = None

    def check_latest_version(self) -> Optional[str]:
        try:
            response = requests.get(
                API_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            self._latest_version = data.get("tag_name", "")
            self._release_notes = data.get("body", "")[:200]
            return self._latest_version
        except Exception:
            return None

    def is_new_version_available(self) -> bool:
        latest = self.check_latest_version()
        if not latest:
            return False
        return self._compare_versions(self.current_version, latest) < 0

    def get_release_info(self) -> Tuple[str, str]:
        if not self._latest_version:
            self.check_latest_version()
        return (self._latest_version or self.current_version,
                self._release_notes or "")

    @staticmethod
    def _compare_versions(current: str, latest: str) -> int:
        from packaging import version
        try:
            if version.parse(current) < version.parse(latest):
                return -1
            elif version.parse(current) > version.parse(latest):
                return 1
            return 0
        except Exception:
            return 0