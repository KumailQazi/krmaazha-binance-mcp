"""Unit tests verifying the institutional improvements (IMPROVEMENTS.MD).

Tests executable order-book liquidity calculations, thin book detection,
signal reproducibility, and Net R:R modeling.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from krmaazha_binance_mcp.models import OrderBookLiquidity
from krmaazha_binance_mcp.signals.engine import generate_signal
from krmaazha_binance_mcp.tools.marketdata import get_order_book_liquidity


def test_order_book_liquidity_calculation():
    """Verify spread bps and ±1% depth calculation from mock order book."""
    mock_client = MagicMock()
    # Mock mid price ~ $100.00
    mock_client.get_order_book.return_value = {
        "bids": [
            ["99.98", "10.0"],  # within 1% ($99.00 - $100.00)
            ["99.50", "20.0"],  # within 1%
            ["98.00", "50.0"],  # outside 1%
        ],
        "asks": [
            ["100.02", "10.0"], # within 1% ($100.00 - $101.00)
            ["100.50", "20.0"], # within 1%
            ["102.00", "50.0"], # outside 1%
        ],
    }
    mock_client.get_ticker.return_value = {
        "quoteVolume": "5000000.00",
        "lastPrice": "100.00",
    }

    liq = get_order_book_liquidity(mock_client, "BTCUSDT")

    assert isinstance(liq, OrderBookLiquidity)
    assert liq.symbol == "BTCUSDT"
    assert liq.venue == "Binance Spot"
    assert liq.best_bid == Decimal("99.98")
    assert liq.best_ask == Decimal("100.02")
    assert liq.touch_spread_abs == Decimal("0.04")
    # mid = 100.00 -> spread_bps = (0.04 / 100) * 10000 = 4.0 bps
    assert pytest.approx(liq.touch_spread_bps, rel=1e-2) == 4.0

    # Bid depth 1%: (99.98 * 10) + (99.50 * 20) = 999.8 + 1990 = 2989.8
    assert liq.bid_depth_1pct_usdt == Decimal("2989.80")
    # Ask depth 1%: (100.02 * 10) + (100.50 * 20) = 1000.2 + 2010 = 3010.2
    assert liq.ask_depth_1pct_usdt == Decimal("3010.20")
    assert liq.depth_1pct_usdt == Decimal("6000.00")
    # Total depth is 6,000 USDT < 50,000 USDT threshold -> thin book flagged
    assert liq.is_thin_book is True


def test_order_book_liquidity_deep_book():
    """Verify deep order book does not trigger thin book flag."""
    mock_client = MagicMock()
    mock_client.get_order_book.return_value = {
        "bids": [["100.00", "1000.0"]], # $100,000 USDT depth
        "asks": [["100.01", "1000.0"]], # $100,010 USDT depth
    }
    mock_client.get_ticker.return_value = {
        "quoteVolume": "50000000.00",
    }

    liq = get_order_book_liquidity(mock_client, "BTCUSDT")
    assert liq.is_thin_book is False
    assert liq.touch_spread_bps < 2.0


def test_signal_trade_setup_net_risk_reward():
    """Verify signal generates valid TradeSetup and calculates Net R:R."""
    sig = generate_signal(
        symbol="BTCUSDT",
        interval="1h",
        price=Decimal("60000.00"),
        ema_fast=60100.0,
        ema_slow=59800.0,
        rsi=40.0, # Bullish momentum bias
        macd_hist=10.0,
        bb_pos=0.3,
        sentiment=0.4,
        atr=500.0,
        as_of=1700000000000,
    )

    assert sig.direction == "long"
    assert sig.bar_state == "closed"
    assert sig.trade_setup is not None
    assert sig.trade_setup.direction == "long"
    assert sig.trade_setup.entry_trigger.startswith("Confirmed 1h candle close")
    assert sig.trade_setup.invalidation_level == sig.suggested_stop
    assert sig.trade_setup.target_level == sig.suggested_target
    assert sig.trade_setup.gross_risk_reward == 2.0
    # Net R:R must be strictly positive and lower than gross R:R due to friction
    assert sig.trade_setup.net_risk_reward > 0
    assert sig.trade_setup.net_risk_reward < sig.trade_setup.gross_risk_reward
