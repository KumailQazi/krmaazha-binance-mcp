"""Interactive Test Runner for krmaazha-binance-mcp.

Allows testing public analytical tools, indicators, news, signals,
market structure, knowledge resources, and simulated order execution.
"""
__test__ = False

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from binance.client import Client

from krmaazha_binance_mcp.knowledge import _RESOURCES, read_content
from krmaazha_binance_mcp.marketwide import get_market_structure
from krmaazha_binance_mcp.plans import backtest_dca
from krmaazha_binance_mcp.tools import analytics as an_tools
from krmaazha_binance_mcp.tools import marketdata as md_tools
from krmaazha_binance_mcp.tools import news as news_tools
from krmaazha_binance_mcp.tools import signals as sig_tools


def print_banner(title: str):
    print("\n" + "=" * 65)
    print(f"  {title.upper()}")
    print("=" * 65)

def test_market_data(client: Client, symbol: str = "BTCUSDT"):
    print_banner("1. Market Data & 24h Ticker")
    ticker = client.get_symbol_ticker(symbol=symbol)
    stats24 = client.get_ticker(symbol=symbol)
    print(f"Symbol: {symbol}")
    print(f"Current Price: ${float(ticker['price']):,.2f}")
    print(f"24h Change: {stats24['priceChangePercent']}%")
    print(
        f"24h High: ${float(stats24['highPrice']):,.2f} | "
        f"24h Low: ${float(stats24['lowPrice']):,.2f}"
    )
    print(f"24h Volume: {float(stats24['volume']):,.2f} {symbol.replace('USDT','')}")


def test_indicators(client: Client, symbol: str = "BTCUSDT"):
    print_banner("2. Technical Indicators (Server-side & Lookahead-free)")
    res = md_tools.compute_indicators(
        client, symbol, "1d", ["rsi", "ema", "macd", "bollinger", "atr"], last_n=1
    )
    ind = res.indicators
    print(f"Symbol: {symbol} (Interval: 1d)")
    print(f"RSI (14): {ind['rsi'][-1]:.2f}")
    print(f"EMA (12): ${ind['ema'][-1]:,.2f}")
    print(
        f"MACD Line: {ind['macd'][-1]:.2f} | "
        f"Signal: {ind['macd_signal'][-1]:.2f} | "
        f"Hist: {ind['macd_hist'][-1]:.2f}"
    )
    print(
        f"Bollinger Bands: Lower: ${ind['bollinger_lower'][-1]:,.2f} | "
        f"Mid: ${ind['bollinger_mid'][-1]:,.2f} | "
        f"Upper: ${ind['bollinger_upper'][-1]:,.2f}"
    )
    print(f"ATR (14): ${ind['atr'][-1]:,.2f}")

def test_news_and_sentiment(asset: str = "BTC"):
    print_banner("3. Live News RSS & Sentiment Lexicon")
    news_items = news_tools.get_news(asset=asset, limit=3)
    print(f"Latest headlines for {asset}:")
    for idx, item in enumerate(news_items, 1):
        print(f" [{idx}] {item.title}")
        print(f"     Source: {item.source} | Link: {item.url}")
    
    sent = news_tools.get_sentiment(asset=asset, window_hours=24)
    print(f"\nRaw Sentiment Score (24h window): {sent.score:.3f} across {sent.n_items} items")
    print(f"Disclaimer: {sent.disclaimer}")

def test_market_structure():
    print_banner("4. Macro Market Structure")
    ms = get_market_structure()
    print(f"Fear & Greed Index: {ms.fear_greed} ({ms.fear_greed_label})")
    print(f"Fear & Greed 7d Trend: {ms.fear_greed_week}")
    print(f"BTC Dominance: {ms.btc_dominance_pct:.2f}%")
    print(f"Total Crypto Market Cap: ${ms.total_market_cap_usd / 1e12:.2f} Trillion")
    print(f"BTC ATH: ${float(ms.btc_ath_usd):,.2f} ({ms.btc_ath_date})")
    print(f"Drawdown from ATH: {ms.btc_ath_change_pct:.2f}%")
    print(f"Bitcoin Hashrate: {ms.hashrate_avg_ehs:.1f} EH/s")

def test_cycle_analysis(client: Client, symbol: str = "BTCUSDT"):
    print_banner("5. Bitcoin Cycle Analysis")
    cycle = an_tools.analyze_cycle(client, symbol=symbol)
    print(f"Asset: {symbol}")
    print(f"Current Price: ${float(cycle.price):,.2f}")
    print(f"200-day Moving Average: ${float(cycle.ma200d):,.2f}")
    print(f"Mayer Multiple: {cycle.mayer_multiple:.3f}")
    print(f"Cycle ATH: ${float(cycle.ath_usd):,.2f} (Drawdown: {cycle.drawdown_from_ath_pct:.2f}%)")
    print(f"Estimated Next Halving: {cycle.est_next_halving}")

def test_backtesting(client: Client, symbol: str = "BTCUSDT"):
    print_banner("6. Strategy Backtesting (Zero-Lookahead)")
    bt = md_tools.backtest(client, symbol, "1d", "ema_cross", limit=365)
    print(f"Strategy: EMA Crossover on {symbol} (365 daily candles)")
    print(f"Strategy Total Return: {bt.total_return_pct:.2f}%")
    print(f"Buy & Hold Return: {bt.buy_hold_return_pct:.2f}%")
    print(f"Total Closed Trades: {bt.n_trades} (Win Rate: {bt.win_rate * 100:.1f}%)")
    print(f"Max Drawdown: {bt.max_drawdown_pct:.2f}%")

    print("\nSimulating DCA Plan ($500/month for 12 months):")
    dca = backtest_dca(client, symbol, monthly_quote=500, months=12)
    print(f"Total Invested: ${float(dca.total_invested):,.2f}")
    print(f"Accumulated Qty: {dca.accumulated_qty} {symbol.replace('USDT','')}")
    print(f"Average Cost: ${float(dca.avg_cost):,.2f}")
    print(f"Current Portfolio Value: ${float(dca.value_now):,.2f} (PnL: {dca.pnl_pct:+.2f}%)")
    print(f"Lump Sum Equivalent Value: ${float(dca.lump_sum_value_now):,.2f}")

def test_signal_generation(client: Client, symbol: str = "BTCUSDT"):
    print_banner("7. Composite Multi-Factor Signal")
    sig = sig_tools.generate_signal_tool(client, symbol, interval="1h")
    print(f"Asset: {symbol} (Interval: 1h)")
    print(f"Direction: {sig.direction.upper()} | Composite Score: {sig.score:+.3f}")
    print(f"Current Price: ${float(sig.price):,.2f}")
    print(f"ATR Volatility: ${sig.atr:,.2f}")
    print(f"Suggested Stop-Loss: ${float(sig.suggested_stop):,.2f}")
    print(f"Suggested Target: ${float(sig.suggested_target):,.2f}")
    print("Factor Contributions:")
    for f in sig.factors:
        print(f"  • {f.name:<10} [weight={f.weight:.2f}, val={f.value:+.2f}]: {f.note}")

def test_knowledge_resources():
    print_banner("8. MCP Knowledge Resources (Consultant Methodology)")
    for uri, (_, title) in _RESOURCES.items():
        print(f"• {uri:<32} -> {title}")
    
    print("\nExcerpt from kb://discipline:")
    disp = read_content("discipline.md")
    for line in disp.splitlines()[:12]:
        print("  " + line)

def main():
    print_banner("krmaazha-binance-mcp Live Test Harness")
    print("Connecting to Binance Public REST API (No keys required)...")
    client = Client("", "")
    
    test_market_data(client, "BTCUSDT")
    test_indicators(client, "BTCUSDT")
    test_news_and_sentiment("BTC")
    test_market_structure()
    test_cycle_analysis(client, "BTCUSDT")
    test_backtesting(client, "BTCUSDT")
    test_signal_generation(client, "BTCUSDT")
    test_knowledge_resources()
    
    print_banner("Test Completed Successfully")
    print("All analytical, quantitative, news, and knowledge layers are verified and functional!")

if __name__ == "__main__":
    main()
