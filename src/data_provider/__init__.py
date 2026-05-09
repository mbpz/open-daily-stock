# -*- coding: utf-8 -*-
"""
===================================
数据源插件架构 - 包初始化
===================================

提供可扩展的数据源插件注册机制，支持：
1. 内置数据源（akshare, yfinance, efinance 等）
2. 外部数据源插件（Wind, 东方财富 等）

使用 ProviderRegistry 注册和查询数据源插件。
"""

from .plugin import DataProviderPlugin, ProviderRegistry

__all__ = [
    'DataProviderPlugin',
    'ProviderRegistry',
]
