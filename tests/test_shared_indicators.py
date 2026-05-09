"""Tests for src/shared/indicators.py"""
import pytest
import pandas as pd
import numpy as np
from src.shared.indicators import (
    calculate_rsi, calculate_macd, calculate_kdj,
    calculate_wr, calculate_obv, calculate_bollinger_bands,
)

class TestRSI:
    def test_rsi_14(self):
        closes = pd.Series([10, 11, 10.5, 11.5, 12, 11.5, 12.5, 13, 12.5, 13.5, 14, 13.5, 14.5, 15])
        rsi = calculate_rsi(closes, period=14)
        assert len(rsi) == len(closes)
        assert not np.isnan(rsi.iloc[-1])
    def test_rsi_short_series_returns_nan(self):
        closes = pd.Series([10, 11, 12])
        rsi = calculate_rsi(closes, period=14)
        assert rsi.isna().all()

class TestMACD:
    def test_macd_returns_three_series(self):
        closes = pd.Series([10, 11, 10.5, 11.5, 12] * 6)
        macd, signal, hist = calculate_macd(closes)
        assert len(macd) == len(closes)
        assert len(signal) == len(closes)
        assert len(hist) == len(closes)
    def test_macd_short_series(self):
        closes = pd.Series([10, 11, 12])
        macd, signal, hist = calculate_macd(closes)
        assert macd.isna().all()

class TestKDJ:
    def test_kdj(self):
        highs = pd.Series([11, 12, 11.5, 12.5, 13] * 6)
        lows = pd.Series([9, 10, 9.5, 10.5, 11] * 6)
        closes = pd.Series([10, 11, 10.5, 11.5, 12] * 6)
        k, d, j = calculate_kdj(highs, lows, closes)
        assert len(k) == len(closes)
    def test_kdj_short_series(self):
        highs = pd.Series([11, 12, 13])
        lows = pd.Series([9, 10, 11])
        closes = pd.Series([10, 11, 12])
        k, d, j = calculate_kdj(highs, lows, closes)
        assert k.isna().all()

class TestWR:
    def test_wr(self):
        highs = pd.Series([11, 12, 11.5, 12.5, 13] * 6)
        lows = pd.Series([9, 10, 9.5, 10.5, 11] * 6)
        closes = pd.Series([10, 11, 10.5, 11.5, 12] * 6)
        wr = calculate_wr(highs, lows, closes)
        assert len(wr) == len(closes)

class TestOBV:
    def test_obv_increasing(self):
        closes = pd.Series([10, 11, 12, 13, 14])
        volumes = pd.Series([100, 100, 100, 100, 100])
        obv = calculate_obv(closes, volumes)
        # OBV starts at NaN (no prior price to compare), subsequent values should be cumulative positive
        assert obv.iloc[-1] > obv.iloc[1]
    def test_obv_decreasing(self):
        closes = pd.Series([14, 13, 12, 11, 10])
        volumes = pd.Series([100, 100, 100, 100, 100])
        obv = calculate_obv(closes, volumes)
        # OBV starts at NaN, subsequent values should be cumulative negative
        assert obv.iloc[-1] < obv.iloc[1]

class TestBollingerBands:
    def test_bb(self):
        closes = pd.Series([10, 11, 10.5, 11.5, 12] * 5)
        upper, mid, lower = calculate_bollinger_bands(closes, period=20)
        # Skip first period-1 NaN values, then upper >= mid >= lower
        valid_idx = 19  # period - 1
        assert len(upper) == len(closes)
        assert all(upper[valid_idx:] >= mid[valid_idx:])
        assert all(mid[valid_idx:] >= lower[valid_idx:])
    def test_bb_short_series(self):
        closes = pd.Series([10, 11, 12])
        upper, mid, lower = calculate_bollinger_bands(closes, period=20)
        assert upper.isna().all()