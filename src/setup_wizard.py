# -*- coding: utf-8 -*-
"""首次启动引导 - 配置 API keys 和自选股

P5-4: 提供双路径入口 —— 快速体验(演示模式) 或 开始配置(正式模式)
"""
import getpass
import json
import os
from pathlib import Path


def run_wizard(allow_demo: bool = True):
    """交互式引导配置

    Args:
        allow_demo: 是否允许演示模式入口。CLI 模式默认 True。

    Returns:
        str: "demo" if user chose demo mode, "live" if configured.
    """
    if allow_demo:
        print("=" * 50)
        print("  欢迎使用 open-daily-stock")
        print("  智能股票分析系统")
        print("=" * 50)
        print()
        print("  请选择启动方式：")
        print()
        print("  [1] 快速体验 —— 加载演示数据，无需配置，立即体验")
        print("  [2] 开始配置 —— 配置 API Key 和自选股，正式使用")
        print()
        print("=" * 50)

        while True:
            choice = input("  请输入选择 [1/2]: ").strip()
            if choice == "1":
                return _enter_demo_mode()
            elif choice == "2":
                return _run_configuration()
            else:
                print("  无效选择，请输入 1 或 2")
    else:
        return _run_configuration()


def _enter_demo_mode() -> str:
    """进入演示模式，加载演示数据"""
    print()
    print("=" * 50)
    print("  演示模式")
    print("=" * 50)
    print("  正在加载演示数据...")
    print()

    from src.demo_data import apply_demo_mode
    from src.config import get_config, Config

    config = get_config()
    apply_demo_mode(config)

    # Write basic config.json if it doesn't exist
    config_path = Path("config.json")
    if not config_path.exists():
        default_config = {
            "stock_list": [s["code"] for s in __import__("src.demo_data").DEMO_STOCKS],
            "theme": "dark",
            "mode": "demo",
            "keybindings": {
                "q": "quit",
                "1": "markets",
                "2": "tasks",
                "3": "analyze",
                "4": "config",
                "5": "logs",
                "tab": "next_module",
                "r": "refresh",
                "?": "help",
                "t": "toggle_theme",
            },
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

    # Flush demo stock list into config
    from src.demo_data import DEMO_STOCKS
    config.stock_list = [s["code"] for s in DEMO_STOCKS]

    print("  ✓ 演示数据已加载")
    print("  ✓ 包含 5 只热门股票：贵州茅台、平安银行、腾讯、Apple、五粮液")
    print("  ✓ AI 分析使用预计算结果（演示模式）")
    print()
    print("  提示：配置 API Key 后即可解锁实时 AI 分析")
    print("       在「配置」页面点击「退出演示模式」开始正式配置")
    print("=" * 50)
    print()
    return "demo"


def _run_configuration() -> str:
    """运行原有的三步配置向导"""
    print()
    print("=" * 50)
    print("  配置模式")
    print("=" * 50)

    # API Keys
    gemini_key = getpass.getpass("Gemini API Key (回车跳过): ")
    openai_key = getpass.getpass("OpenAI/MiniMax API Key (回车跳过): ")

    # 自选股
    stocks_input = input("自选股代码（逗号分隔，如 600519,000001）: ")
    stocks = [s.strip() for s in stocks_input.split(",") if s.strip()]

    # Save to .env file
    env_path = Path(".env")
    env_lines = []
    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").strip().split("\n")
        env_lines = [l for l in env_lines if l.strip()]

    if gemini_key:
        env_lines.append(f"GEMINI_API_KEY={gemini_key}")
    if openai_key:
        env_lines.append(f"OPENAI_API_KEY={openai_key}")
    if stocks:
        env_lines.append(f"STOCK_LIST={','.join(stocks)}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines) + "\n")

    # 保存 config.json
    config_data = {
        "stocks": stocks,
        "theme": "dark",
        "mode": "live",
    }
    config_path = Path("config.json")
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            existing.update(config_data)
            config_data = existing
    except Exception:
        pass

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

    # 刷新配置单例
    from src.config import Config
    Config.reset_instance()

    print()
    print("  配置已保存！")
    return "live"


def run_exit_demo_wizard():
    """从演示模式退出，进入正式配置向导。

    Returns:
        bool: True if user completed config, False if cancelled.
    """
    print("=" * 50)
    print("  退出演示模式")
    print("=" * 50)
    print("  完成以下配置后，系统将切换到正式模式。")
    print()
    return _run_configuration() == "live"


if __name__ == "__main__":
    run_wizard()
