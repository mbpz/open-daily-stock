"""[TEMP] 占位模块 — 等待逐步迁移。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_service import DataService


def register(service: "DataService") -> None:
    """占位 — 待 P0-4 后续 phase 填充。"""
    return
