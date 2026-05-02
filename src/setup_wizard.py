# -*- coding: utf-8 -*-
"""首次启动引导 - 配置 API keys 和自选股"""
import getpass
import json
import os
from pathlib import Path


def run_wizard():
    """交互式引导配置"""
    print("=" * 50)
    print("首次使用配置")
    print("=" * 50)

    # API Keys
    gemini_key = getpass.getpass("Gemini API Key: ")
    deepseek_key = getpass.getpass("DeepSeek API Key: ")

    # 自选股
    stocks_input = input("自选股代码（逗号分隔，如 600519,000001）: ")
    stocks = [s.strip() for s in stocks_input.split(",") if s.strip()]

    # 保存配置
    config = {
        "stocks": stocks,
        "apis": {
            "gemini_key": gemini_key,
            "deepseek_key": deepseek_key
        }
    }

    config_path = Path("config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print("配置已保存！")
    return config


if __name__ == "__main__":
    run_wizard()