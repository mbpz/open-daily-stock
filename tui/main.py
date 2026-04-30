"""TUI entry point."""
import sys
from tui.app import TUIApp

def main():
    app = TUIApp()
    app.run()

if __name__ == "__main__":
    sys.exit(main())
