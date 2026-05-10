"""
MCP Tool definitions for open-daily-stock DataService actions.

Each tool wraps a DataService action as an MCP (Model Context Protocol) tool
with JSON Schema input definitions. AI agents (e.g., Claude Code) can call
these tools via JSON-RPC 2.0 over stdio to retrieve stock data, run analysis,
and manage portfolios.

Grouped by domain:
  - Market Data: real-time quotes, K-lines, history
  - Analysis: AI analysis, news search, technical indicators, financials
  - Portfolio: position tracking
  - Trading: simulated trading and backtesting
  - Strategy: import/export trading strategies
  - Monitoring: task management, institutional data
  - Config: application settings
  - Alerts: price/condition alerts
  - Screening: A-share market screening
  - Utilities: providers, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List

# ============================================================
# MCP Tool Definitions
# ============================================================
# Each tool has: name, description, inputSchema (JSON Schema for params).

MCP_TOOLS: List[Dict[str, Any]] = [

    # ---- Market Data ----
    {
        "name": "get_markets",
        "description": "Get real-time market data for all tracked stocks. Returns price, change percentage, volume, and optional sparkline data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_sparkline": {
                    "type": "boolean",
                    "description": "Include 10-day sparkline data for each stock"
                }
            }
        }
    },
    {
        "name": "refresh",
        "description": "Refresh all market data from external data sources and check alert conditions.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_history",
        "description": "Get historical daily price data for a stock (OHLCV). Returns open, high, low, close, volume, and daily change percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519' for Kweichow Moutai)"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of trading days to retrieve (default: 30)",
                    "default": 30
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_kline_data",
        "description": "Get K-line (candlestick) chart data with optional technical indicators for a stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of trading days (default: 60)",
                    "default": 60
                },
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Technical indicators to include (e.g., ['ma5', 'ma10', 'ma20', 'rsi', 'macd', 'bollinger'])"
                }
            },
            "required": ["code"]
        }
    },

    # ---- Analysis ----
    {
        "name": "analyze",
        "description": "Trigger an AI-powered analysis of a stock. Creates an async task and returns a task ID for progress tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "search_news",
        "description": "Search for news articles related to a stock using configured search providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_indicators",
        "description": "Calculate and return technical indicators (RSI, MACD, Bollinger Bands, KDJ, WR, OBV) for a stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "indicator_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of indicator names: 'rsi', 'macd', 'bollinger', 'kdj', 'wr', 'obv'"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of trading days for calculation (default: 60)",
                    "default": 60
                }
            },
            "required": ["code", "indicator_names"]
        }
    },
    {
        "name": "get_drawing_data",
        "description": "Get support/resistance levels and Fibonacci retracement levels for a stock based on recent price action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "days": {
                    "type": "integer",
                    "description": "Lookback period in days (default: 60)",
                    "default": 60
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_financials",
        "description": "Retrieve financial statements (income, balance sheet, cash flow) for a stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_key_metrics",
        "description": "Get key financial metrics (PE, PB, ROE, market cap, growth rates, etc.) for a stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                }
            },
            "required": ["code"]
        }
    },

    # ---- Portfolio ----
    {
        "name": "add_position",
        "description": "Add a new position to the portfolio tracker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "name": {
                    "type": "string",
                    "description": "Stock name (defaults to code if omitted)"
                },
                "shares": {
                    "type": "number",
                    "description": "Number of shares purchased"
                },
                "buy_price": {
                    "type": "number",
                    "description": "Buy price per share"
                },
                "buy_date": {
                    "type": "string",
                    "description": "Buy date in ISO format (e.g., '2024-01-15')"
                }
            },
            "required": ["code", "shares", "buy_price", "buy_date"]
        }
    },
    {
        "name": "remove_position",
        "description": "Remove a position from the portfolio by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "Position ID to remove"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "update_position",
        "description": "Update an existing position (e.g., current price, shares, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "Position ID to update"
                },
                "current_price": {
                    "type": "number",
                    "description": "New current price per share"
                },
                "shares": {
                    "type": "number",
                    "description": "Updated share count"
                },
                "name": {
                    "type": "string",
                    "description": "Updated stock name"
                },
                "buy_price": {
                    "type": "number",
                    "description": "Updated buy price"
                },
                "buy_date": {
                    "type": "string",
                    "description": "Updated buy date (ISO format)"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "get_positions",
        "description": "Get all current portfolio positions with unrealized P&L.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },

    # ---- Trading ----
    {
        "name": "sim_buy",
        "description": "Execute a simulated buy order in the paper trading account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "name": {
                    "type": "string",
                    "description": "Stock name (defaults to code)"
                },
                "price": {
                    "type": "number",
                    "description": "Buy price per share"
                },
                "shares": {
                    "type": "integer",
                    "description": "Number of shares (default: 100)",
                    "default": 100
                }
            },
            "required": ["code", "price"]
        }
    },
    {
        "name": "sim_sell",
        "description": "Execute a simulated sell order in the paper trading account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code to sell"
                },
                "price": {
                    "type": "number",
                    "description": "Sell price per share"
                },
                "shares": {
                    "type": "integer",
                    "description": "Number of shares to sell (default: all)"
                }
            },
            "required": ["code", "price"]
        }
    },
    {
        "name": "sim_summary",
        "description": "Get the current summary of the simulated trading account (cash, holdings, total P&L).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sim_history",
        "description": "Get the full transaction history of the simulated trading account.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sim_reset",
        "description": "Reset the simulated trading account to its initial state.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "run_backtest",
        "description": "Run a backtest using a moving-average crossover strategy on historical data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                },
                "initial_capital": {
                    "type": "number",
                    "description": "Initial capital amount for the backtest"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of trading days to backtest (default: 60)",
                    "default": 60
                }
            },
            "required": ["code", "initial_capital"]
        }
    },

    # ---- Strategy ----
    {
        "name": "export_strategy",
        "description": "Export a backtest strategy configuration to a JSON file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Strategy name (used as filename)"
                },
                "version": {
                    "type": "string",
                    "description": "Strategy version (default: '1.0')"
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable strategy description"
                },
                "author": {
                    "type": "string",
                    "description": "Strategy author"
                },
                "params": {
                    "type": "object",
                    "description": "Strategy parameters (e.g., {'fast_ma': 5, 'slow_ma': 20, 'initial_capital': 100000})"
                },
                "code": {
                    "type": "string",
                    "description": "Strategy implementation language (default: 'python')"
                },
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Indicators used by the strategy"
                },
                "entry_rule": {
                    "type": "string",
                    "description": "Entry rule description"
                },
                "exit_rule": {
                    "type": "string",
                    "description": "Exit rule description"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "import_strategy",
        "description": "Import a strategy from JSON data (object or string) and save it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {
                    "description": "Strategy data as JSON object or JSON string"
                }
            },
            "required": ["data"]
        }
    },
    {
        "name": "list_strategies",
        "description": "List all saved strategy configurations.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "delete_strategy",
        "description": "Delete a saved strategy by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Strategy name to delete"
                }
            },
            "required": ["name"]
        }
    },

    # ---- Monitoring ----
    {
        "name": "get_tasks",
        "description": "Get all analysis tasks and their statuses (pending, running, completed, failed).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_task",
        "description": "Get the status and result of a specific analysis task by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID returned from the analyze action"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "cancel_task",
        "description": "Cancel a running or pending analysis task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to cancel"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "get_institutional",
        "description": "Get institutional trading activity for a stock (major shareholder changes, institutional research visits).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Stock code (e.g., '600519')"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_dragon_board",
        "description": "Get dragon-and-tiger board data (top traded stocks with institutional participation).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Optional date filter (ISO format, e.g., '2024-01-15')"
                }
            }
        }
    },

    # ---- Config ----
    {
        "name": "get_config",
        "description": "Get current application configuration (theme, language, data providers, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Specific config key to retrieve (omit for all config)"
                }
            }
        }
    },
    {
        "name": "update_config",
        "description": "Update application configuration values (theme, language, schedule time, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Config key to update (e.g., 'theme', 'language', 'schedule_time')"
                },
                "value": {
                    "description": "New value for the config key"
                }
            },
            "required": ["key", "value"]
        }
    },

    # ---- Alerts ----
    {
        "name": "get_alerts",
        "description": "Get all configured price/condition alerts.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "save_alert",
        "description": "Create a new price/condition alert for a stock.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stock": {
                    "type": "string",
                    "description": "Stock code or name"
                },
                "condition": {
                    "type": "string",
                    "description": "Alert condition (e.g., 'price_above', 'price_below', 'change_pct_above')"
                },
                "threshold": {
                    "type": "number",
                    "description": "Threshold value for the condition"
                },
                "channel": {
                    "type": "string",
                    "description": "Notification channel (default: 'wechat')",
                    "default": "wechat"
                }
            },
            "required": ["stock", "condition", "threshold"]
        }
    },
    {
        "name": "delete_alert",
        "description": "Delete an alert by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "Alert ID to delete"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "toggle_alert",
        "description": "Enable or disable an alert by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "Alert ID to toggle"
                }
            },
            "required": ["id"]
        }
    },

    # ---- Screening ----
    {
        "name": "screen_stocks",
        "description": "Screen stocks across the entire A-share market by criteria: market cap, PE ratio, industry, and daily change percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market_cap_min": {
                    "type": "number",
                    "description": "Minimum market cap in billions CNY"
                },
                "market_cap_max": {
                    "type": "number",
                    "description": "Maximum market cap in billions CNY"
                },
                "pe_min": {
                    "type": "number",
                    "description": "Minimum PE ratio"
                },
                "pe_max": {
                    "type": "number",
                    "description": "Maximum PE ratio"
                },
                "industry": {
                    "type": "string",
                    "description": "Industry sector to filter by"
                },
                "change_pct_min": {
                    "type": "number",
                    "description": "Minimum daily change percentage"
                },
                "change_pct_max": {
                    "type": "number",
                    "description": "Maximum daily change percentage"
                }
            }
        }
    },

    # ---- Utilities ----
    {
        "name": "list_providers",
        "description": "List all registered data provider plugins with their availability status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "market": {
                    "type": "string",
                    "description": "Filter by market type (default: 'ALL')",
                    "default": "ALL"
                }
            }
        }
    },
]
