"""Tests for src/shared/sparkline.py"""
import pytest
from src.shared.sparkline import (
    SPARKLINE_CHARS,
    generate_sparkline,
    generate_sparkline_with_color,
    generate_change_sparkline,
)


class TestGenerateSparkline:
    """Tests for generate_sparkline function."""

    def test_empty_list(self):
        result = generate_sparkline([])
        assert result == ""

    def test_single_value(self):
        result = generate_sparkline([42.0])
        assert result == ""

    def test_uptrend(self):
        # Steadily increasing prices
        values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
        result = generate_sparkline(values, width=5)
        # All chars should be from SPARKLINE_CHARS
        for ch in result:
            assert ch in SPARKLINE_CHARS
        # Should be 5 chars wide
        assert len(result) == 5
        # Last char should be highest (block 8 or near it)
        assert result[-1] == SPARKLINE_CHARS[8]

    def test_downtrend(self):
        # Steadily decreasing prices
        values = [24.0, 22.0, 20.0, 18.0, 16.0, 14.0, 12.0, 10.0]
        result = generate_sparkline(values, width=5)
        for ch in result:
            assert ch in SPARKLINE_CHARS
        assert len(result) == 5
        # Last char should be lowest
        assert result[-1] == SPARKLINE_CHARS[0]

    def test_flat_values(self):
        # All values equal
        values = [15.0, 15.0, 15.0, 15.0, 15.0]
        result = generate_sparkline(values, width=5)
        assert result == "▄▄▄▄▄"

    def test_flat_short(self):
        # All values equal, fewer than width
        values = [15.0, 15.0, 15.0]
        result = generate_sparkline(values, width=8)
        assert result == "▄▄▄"

    def test_long_list_resampled_to_width(self):
        # 20 values, resample to 8 chars
        values = [10.0 + i * 0.5 for i in range(20)]
        result = generate_sparkline(values, width=8)
        assert len(result) == 8
        for ch in result:
            assert ch in SPARKLINE_CHARS
        # Should end with highest char since trend is up
        assert result[-1] == SPARKLINE_CHARS[8]

    def test_normal_variation(self):
        # Mixed values, should produce non-trivial sparkline
        values = [10.0, 12.5, 11.0, 14.0, 13.0, 15.5, 16.0]
        result = generate_sparkline(values, width=4)
        assert len(result) == 4
        for ch in result:
            assert ch in SPARKLINE_CHARS

    def test_default_width(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = generate_sparkline(values)
        # Default width is 8, values count is 8, so should use all
        assert len(result) == 8
        assert result[-1] == SPARKLINE_CHARS[8]


class TestGenerateSparklineWithColor:
    """Tests for generate_sparkline_with_color function."""

    def test_with_color_uptrend_green(self):
        values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        sparkline, color = generate_sparkline_with_color(values, width=5)
        assert len(sparkline) == 5
        assert color == "green"

    def test_with_color_downtrend_red(self):
        values = [20.0, 18.0, 16.0, 14.0, 12.0, 10.0]
        sparkline, color = generate_sparkline_with_color(values, width=5)
        assert len(sparkline) == 5
        assert color == "red"

    def test_with_color_flat_grey(self):
        values = [15.0, 15.0, 15.0, 15.0, 15.0]
        sparkline, color = generate_sparkline_with_color(values, width=4)
        assert sparkline == "▄▄▄▄"
        assert color == "grey"

    def test_with_color_single_value(self):
        sparkline, color = generate_sparkline_with_color([42.0])
        assert sparkline == ""
        assert color == "grey"


class TestGenerateChangeSparkline:
    """Tests for generate_change_sparkline function."""

    def test_empty(self):
        result = generate_change_sparkline([])
        assert result == ""

    def test_all_positive_changes(self):
        changes = [0.5, 1.0, 1.5, 2.0, 2.5]
        result = generate_change_sparkline(changes, width=5)
        assert len(result) == 5
        for ch in result:
            assert ch in SPARKLINE_CHARS

    def test_mixed_changes(self):
        changes = [-2.0, -1.0, 0.0, 1.0, 2.0]
        result = generate_change_sparkline(changes, width=5)
        assert len(result) == 5
        # Middle value (0%) should be centered at level 4
        # First char should be lower than last char
        assert ord(result[0]) < ord(result[-1])

    def test_resampled(self):
        changes = [v * 0.3 for v in range(-5, 15)]
        result = generate_change_sparkline(changes, width=5)
        assert len(result) == 5
        for ch in result:
            assert ch in SPARKLINE_CHARS

    def test_zero_centered(self):
        # When all changes are zero, max_abs is 0, or 1 via fallback
        changes = [0.0, 0.0, 0.0]
        result = generate_change_sparkline(changes, width=3)
        assert len(result) == 3
        # All should be at center level 4
        for ch in result:
            assert ch == SPARKLINE_CHARS[4]
