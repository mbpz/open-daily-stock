"""Text-based sparkline chart generation."""
from typing import List

SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"  # 9 levels (0-8)


def generate_sparkline(values: List[float], width: int = 8) -> str:
    """Generate a Unicode sparkline string from a list of numeric values.

    Args:
        values: List of numeric values (e.g. closing prices)
        width: Number of characters in the sparkline

    Returns:
        String of Unicode block characters representing the trend
    """
    if not values or len(values) < 2:
        return ""

    # Normalize to 0-8 range
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        # All values equal - flat line
        return "▄" * min(width, len(values))

    # Evenly sample values to fit width
    n = len(values)
    if n <= width:
        indices = range(n)
    else:
        step = (n - 1) / (width - 1)
        indices = [int(i * step) for i in range(width)]

    chars = []
    for i in indices:
        normalized = (values[i] - min_val) / (max_val - min_val)
        level = min(8, max(0, round(normalized * 8)))
        chars.append(SPARKLINE_CHARS[level])

    return "".join(chars)


def generate_sparkline_with_color(values: List[float], width: int = 8) -> tuple:
    """Generate sparkline string and trend color.

    Returns: (sparkline_str, color) where color is 'green'/'red'/'grey'
    """
    sparkline = generate_sparkline(values, width)

    if len(values) >= 2:
        if values[-1] > values[0]:
            color = "green"
        elif values[-1] < values[0]:
            color = "red"
        else:
            color = "grey"
    else:
        color = "grey"

    return sparkline, color


def generate_change_sparkline(pct_changes: List[float], width: int = 5) -> str:
    """Generate sparkline from daily % changes (centered around 0)."""
    if not pct_changes:
        return ""

    max_abs = max(abs(v) for v in pct_changes) or 1

    n = len(pct_changes)
    if n <= width:
        indices = range(n)
    else:
        step = (n - 1) / (width - 1)
        indices = [int(i * step) for i in range(width)]

    chars = []
    for i in indices:
        # Map from [-max_abs, +max_abs] to [0, 8] with 4 as center
        normalized = pct_changes[i] / max_abs  # [-1, 1]
        level = min(8, max(0, round(4 + normalized * 4)))
        chars.append(SPARKLINE_CHARS[level])

    return "".join(chars)
