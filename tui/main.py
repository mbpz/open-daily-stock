"""TUI entry point."""
import sys
import time

def main():
    # Print startup message immediately (before heavy imports)
    print("\n" + "=" * 50)
    print("  open-daily-stock TUI 启动中...")
    print("  按 Ctrl+C 退出")
    print("=" * 50 + "\n", flush=True)

    # Defer heavy imports to avoid startup delay
    t0 = time.perf_counter()
    from tui.app import TUIApp

    print(f"  模块加载完成 ({(time.perf_counter()-t0)*1000:.0f}ms)\n", flush=True)

    app = TUIApp()
    app.run()

if __name__ == "__main__":
    sys.exit(main())
