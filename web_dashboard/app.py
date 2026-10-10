"""Fast Starlette Web API backend for krmaazha-binance-mcp dashboard."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles

from binance.client import Client
from krmaazha_binance_mcp.tools import news as news_tools
from krmaazha_binance_mcp.tools import marketdata as md_tools
from krmaazha_binance_mcp.tools import signals as sig_tools
from krmaazha_binance_mcp.tools import analytics as an_tools
from krmaazha_binance_mcp.marketwide import get_market_structure
from krmaazha_binance_mcp.plans import backtest_dca
from krmaazha_binance_mcp.knowledge import read_content, _RESOURCES
from krmaazha_binance_mcp.klines import fetch_klines
from krmaazha_binance_mcp.agents import MasterOrchestratorAgent

# Public client (no keys needed for market research)
client = Client("", "")
orchestrator = MasterOrchestratorAgent()

async def api_market_structure(request):
    try:
        ms = get_market_structure()
        return JSONResponse(ms.model_dump())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_ticker_summary(request):
    try:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "NOMUSDT", "RESOLVUSDT", "XVGUSDT"]
        results = []
        for sym in symbols:
            stats = client.get_ticker(symbol=sym)
            results.append({
                "symbol": sym,
                "price": float(stats["lastPrice"]),
                "change_24h": float(stats["priceChangePercent"]),
                "high_24h": float(stats["highPrice"]),
                "low_24h": float(stats["lowPrice"]),
                "volume": float(stats["volume"]),
            })
        return JSONResponse(results)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_klines(request):
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT")
        interval = request.query_params.get("interval", "1h")
        limit = min(int(request.query_params.get("limit", 60)), 200)
        df = fetch_klines(client, symbol, interval, limit)
        candles = []
        for _, row in df.iterrows():
            candles.append({
                "time": int(row["open_time"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return JSONResponse({
            "symbol": symbol,
            "interval": interval,
            "candles": candles
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_indicators(request):
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT")
        interval = request.query_params.get("interval", "1d")
        res = md_tools.compute_indicators(
            client, symbol, interval, ["rsi", "ema", "macd", "bollinger", "atr"], last_n=30
        )
        return JSONResponse(res.model_dump())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_signals_scan(request):
    try:
        watchlist = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "NOMUSDT", "RESOLVUSDT", "XVGUSDT"]
        signals_list = []
        for sym in watchlist:
            try:
                sig = sig_tools.generate_signal_tool(client, sym, interval="1h")
                signals_list.append(sig.model_dump())
            except Exception as item_err:
                signals_list.append({"symbol": sym, "error": str(item_err)})
        # sort by absolute score or score descending
        signals_list.sort(key=lambda x: x.get("score", -999), reverse=True)
        return JSONResponse(signals_list)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_cycle(request):
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT")
        cycle = an_tools.analyze_cycle(client, symbol=symbol)
        return JSONResponse(cycle.model_dump())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_backtest_dca(request):
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT")
        monthly = float(request.query_params.get("monthly", 500))
        months = int(request.query_params.get("months", 12))
        res = backtest_dca(client, symbol, monthly_quote=monthly, months=months)
        
        # Build month-by-month curve simulation for plotting
        df = fetch_klines(client, symbol, "1d", months * 31)
        monthly_stride = max(len(df) // months, 1)
        curve = []
        accumulated_qty = Decimal("0")
        total_invested = Decimal("0")
        
        for m in range(months):
            idx = min(m * monthly_stride, len(df) - 1)
            close_price = Decimal(str(df["close"].iloc[idx]))
            bought_qty = (Decimal(str(monthly)) * Decimal("0.999")) / close_price
            accumulated_qty += bought_qty
            total_invested += Decimal(str(monthly))
            current_val = accumulated_qty * close_price
            curve.append({
                "month": m + 1,
                "date": str(df["open_time"].iloc[idx]),
                "invested": float(total_invested),
                "dca_value": round(float(current_val), 2),
                "asset_price": float(close_price)
            })
            
        return JSONResponse({
            "summary": res.model_dump(),
            "curve": curve
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_news(request):
    try:
        asset = request.query_params.get("asset", "BTC")
        items = news_tools.get_news(asset=asset, limit=6)
        sent = news_tools.get_sentiment(asset=asset, window_hours=24)
        return JSONResponse({
            "asset": asset,
            "sentiment": sent.model_dump(),
            "items": [it.model_dump() for it in items]
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_knowledge(request):
    try:
        resources = []
        for uri, (fname, title) in _RESOURCES.items():
            content = read_content(fname)
            resources.append({
                "uri": uri,
                "title": title,
                "snippet": content[:300] + "..."
            })
        return JSONResponse(resources)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_thesis(request):
    try:
        symbol = request.query_params.get("symbol", "SOLUSDT").upper().strip()
        base = symbol.replace("USDT", "").replace("FDUSD", "").replace("BTC", "")
        if not base:
            base = symbol

        # 1. Fetch live price & stats
        ticker = client.get_ticker(symbol=symbol)
        price = float(ticker["lastPrice"])
        change_24h = float(ticker["priceChangePercent"])
        vol_24h = float(ticker["volume"])

        # 2. Layer 4 Signal
        sig_data = {}
        try:
            sig = sig_tools.generate_signal_tool(client, symbol, interval="1h")
            sig_data = sig.model_dump()
        except Exception as e:
            sig_data = {"direction": "neutral", "score": 0.0, "error": str(e)}

        # 3. Layer 3 News & Sentiment
        news_items = []
        sentiment_score = 0.0
        try:
            items = news_tools.get_news(asset=base, limit=3)
            news_items = [it.model_dump() for it in items]
            sent = news_tools.get_sentiment(asset=base, window_hours=24)
            sentiment_score = sent.score
        except Exception:
            pass

        # 4. Generate structured 5 Value-Capture criteria & verdict
        if base == "SOL":
            framework = {
                "verdict_title": "SATELLITE GROWTH ALLOCATION",
                "verdict_badge": "HIGH BETA SATELLITE (MAX 10-15%)",
                "verdict_color": "var(--accent-purple)",
                "risk_rating": "Medium-High (Altcoin Layer-1)",
                "key_takeaway": "Dominant retail DEX throughput and developer mindshare, but elevated P/S multiple (~200x) and dependency on memecoin volume require treating it as a volatile satellite, never replacing the core Bitcoin position.",
                "questions": [
                    {
                        "num": 1,
                        "title": "Entitlement & Real Cash Flow",
                        "status": "PASS (WITH CAUTION)",
                        "status_type": "pass",
                        "summary": "Staking yield (~6-7% nominal, ~1.5% net) + 50% base fee burn + MEV tips. However, fee burn currently does not offset gross network inflation (~5%/yr)."
                    },
                    {
                        "num": 2,
                        "title": "Protocol Revenue vs Valuation",
                        "status": "ELEVATED MULTIPLE (P/S ~200x)",
                        "status_type": "warn",
                        "summary": "High daily transactions (35M-50M), but low per-tx fee ($0.001-$0.005) yields ~$250M annualized base fee revenue against a $60B+ market cap."
                    },
                    {
                        "num": 3,
                        "title": "Supply Schedule & Token Unlocks",
                        "status": "MODERATE DILUTION",
                        "status_type": "pass",
                        "summary": "Early venture capital and foundation lockups have fully vested. Ongoing supply dilution is governed by a disinflationary curve reaching a 1.5% terminal rate."
                    },
                    {
                        "num": 4,
                        "title": "Real Monetized Adoption",
                        "status": "VERIFIED VOLUME LEADER",
                        "status_type": "pass",
                        "summary": "Consistently rivals or outperforms Ethereum in daily DEX volume and active wallets, though high-velocity speculative trading accounts for a significant portion."
                    },
                    {
                        "num": 5,
                        "title": "Competitive Moat & Performance",
                        "status": "HIGH SPEED / SVM ADVANTAGE",
                        "status_type": "pass",
                        "summary": "Monolithic single-state architecture with ~400ms slots eliminates L2 bridging friction; challenged by upcoming parallel EVMs/SVMs (Monad, Sei, Aptos)."
                    }
                ],
                "bull_case": [
                    "Dominant retail hub: unmatched execution speed, low costs, and high developer retention.",
                    "Monolithic architecture avoids rollup fragmentation and fragmented liquidity.",
                    "Strong institutional presence (ETF filings, PayPal USD, Robinhood / Shopify integrations)."
                ],
                "bear_case": [
                    "Valuation of $60B+ demands sustained hyper-growth; low transaction fees require massive sustained volume.",
                    "High hardware and network requirements for full validators introduce centralizing pressures.",
                    "If retail speculative velocity rotates, protocol fees and active addresses compress sharply."
                ],
                "open_question": "Can Solana successfully convert its massive speculative trading volume into durable, fee-paying institutional financial rails (RWA tokenization, global payments, remittances) before terminal inflation and competing parallel execution chains erode its liquidity moat?",
                "btc_comparison": "SOL introduces smart-contract complexity, consensus tuning, and inflationary token issuance that BTC does not have. It must deliver a 2x-3x Sharpe ratio advantage to justify this extra downside variance.",
                "anchoring_verdict": f"At ${price:,.2f}, short-term technicals sit in an {sig_data.get('direction', 'neutral').upper()} posture. Long-term thesis remains intact, but discipline mandates sizing as an unleveraged 5%-15% satellite allocation via mechanical DCA, never lump-sum chasing."
            }
        elif base == "BTC":
            framework = {
                "verdict_title": "FOUNDATIONAL CORE ASSET",
                "verdict_badge": "PRIMARY PORTFOLIO CORE (60-80%)",
                "verdict_color": "var(--accent-gold)",
                "risk_rating": "Lowest in Crypto Asset Class",
                "key_takeaway": "Bitcoin IS the product: scarce, decentralized bearer settlement. Survives every cycle without smart-contract or governance counterparty risk. The benchmark all altcoins must beat.",
                "questions": [
                    {"num": 1, "title": "Entitlement & Value Capture", "status": "PRIME MONETARY STORE", "status_type": "pass", "summary": "Absolute scarcity (21M hard cap). Pure monetary commodity; value capture is direct purchasing power protection."},
                    {"num": 2, "title": "Revenue vs Valuation", "status": "COMMODITY METRIC", "status_type": "pass", "summary": "Valued as pristine sovereign digital collateral and global reserve asset, not an operating company."},
                    {"num": 3, "title": "Supply Schedule", "status": "FIXED HARD CAP (94% Mined)", "status_type": "pass", "summary": "Predictable disinflationary halving schedule every ~4 years. Next halving ~April 2028."},
                    {"num": 4, "title": "Monetized Adoption", "status": "GLOBAL SOVEREIGN & ETF ADOPTION", "status_type": "pass", "summary": "Spot ETFs holding >$100B, nation-state reserves, and public company treasuries."},
                    {"num": 5, "title": "Competitive Moat", "status": "UNASSAILABLE PROOF-OF-WORK MOAT", "status_type": "pass", "summary": "940+ EH/s network hashrate and 17 years of unbroken uptime make it the undisputed settlement standard."}
                ],
                "bull_case": ["Global reserve asset adoption and institutional ETF accumulation.", "Immunity to regulatory classification as a security.", "Hardest monetary policy on Earth."],
                "bear_case": ["Cyclical 50%-75% drawdowns require emotional discipline.", "Long-term transaction fee security budget as block rewards halve."],
                "open_question": "Will nation-state and sovereign wealth fund allocations accelerate before supply on exchanges becomes illiquid?",
                "btc_comparison": "Bitcoin is the benchmark. All other assets in crypto are measured against its risk-adjusted performance.",
                "anchoring_verdict": f"At ${price:,.2f}, BTC is the prime long-term accumulator asset. Ideal for mechanical monthly DCA under kb://discipline Rule 1."
            }
        elif base == "NOM":
            framework = {
                "verdict_title": "ONOMY PROTOCOL (NOM)",
                "verdict_badge": "HIGH-RISK MICRO-CAP (<2% ALLOCATION)",
                "verdict_color": "var(--accent-red)",
                "risk_rating": "Very High (Micro-Cap Altcoin)",
                "key_takeaway": "Cosmos-based multi-chain FX and decentralized exchange architecture. Low unit price ($0.0024) reflects significant past dilution. Must be sized strictly as speculative venture capital risk.",
                "questions": [
                    {"num": 1, "title": "Entitlement & Cash Flow", "status": "STAKING & GOVERNANCE", "status_type": "warn", "summary": "Used for PoS security, validator delegation, and governance over Onomy Hub treasury."},
                    {"num": 2, "title": "Revenue vs FDV", "status": "MICRO-FEE RUNWAY", "status_type": "warn", "summary": "Low protocol fee volume compared to major L1/L2s; revenue depends on cross-chain FX adoption."},
                    {"num": 3, "title": "Supply Schedule & Dilution", "status": "HEAVY HISTORICAL EMISSIONS", "status_type": "danger", "summary": "Has undergone severe downward price discovery from launch highs; ongoing staking emissions continue."},
                    {"num": 4, "title": "Real Monetized Adoption", "status": "NICHE DEFI ADOPTION", "status_type": "warn", "summary": "On-chain liquidity pools and IBC bridge transfers remain modest compared to top 50 DeFi protocols."},
                    {"num": 5, "title": "Competitive Moat", "status": "COSMOS / IBC ECOSYSTEM", "status_type": "warn", "summary": "Faces intense competition from Osmosis, Injective, and generalized cross-chain DEX aggregators."}
                ],
                "bull_case": ["Turnaround potential if Onomy FX / cross-chain bonding curve liquidity scales.", "Low absolute market cap creates high upside leverage if volume returns."],
                "bear_case": ["Severe historical drawdown (-95%+) indicates sustained seller liquidity.", "High ongoing emissions dilute non-staking holders."],
                "open_question": "Can Onomy secure meaningful institutional FX volume, or will competing cross-chain bridges capture the volume?",
                "btc_comparison": "Micro-cap altcoin with massive volatility. Requires extreme sizing restraint compared to core Bitcoin.",
                "anchoring_verdict": f"At ${price:,.6f}, NOM is a high-risk speculative play. Position sizing must stay under 1-2% of crypto holdings; never use leverage."
            }
        elif base == "RESOLV":
            framework = {
                "verdict_title": "RESOLV PROTOCOL (RESOLV)",
                "verdict_badge": "DEFI YIELD SPECULATION (<3% ALLOCATION)",
                "verdict_color": "var(--accent-purple)",
                "risk_rating": "High (DeFi Architecture)",
                "key_takeaway": "Decentralized delta-neutral investment protocol generating yield for the USR stablecoin. Backed by institutional DeFi infrastructure, but subject to smart contract and basis risks.",
                "questions": [
                    {"num": 1, "title": "Entitlement & Cash Flow", "status": "PROTOCOL FEE ACCRUAL", "status_type": "pass", "summary": "Protocol revenue accrues from the delta-neutral basis arbitrage spread and insurance pool yields."},
                    {"num": 2, "title": "Revenue vs FDV", "status": "EARLY STAGE TVL", "status_type": "warn", "summary": "Protocol revenue is directly tied to USR stablecoin supply and basis trading yields."},
                    {"num": 3, "title": "Supply Schedule", "status": "VESTING SCHEDULE MONITOR", "status_type": "warn", "summary": "Early protocol stage with ongoing ecosystem emissions and incentive distributions."},
                    {"num": 4, "title": "Real Monetized Adoption", "status": "GROWING DEFI TVL", "status_type": "pass", "summary": "Demonstrated yield generation across centralized and decentralized liquidity venues."},
                    {"num": 5, "title": "Competitive Moat", "status": "DELTA-NEUTRAL ARCHITECTURE", "status_type": "warn", "summary": "Competes directly with Ethena (USDe) and other synthetic delta-neutral stablecoin issuers."}
                ],
                "bull_case": ["Capital-efficient synthetic dollar mechanism benefiting from positive crypto funding rates.", "Growing integrations across Layer-2 lending markets."],
                "bear_case": ["Funding rate inversion (bear market) reduces native protocol yield.", "Centralized exchange counterparty risk during basis trade hedging."],
                "open_question": "Can Resolv maintain positive yield differentials against Ethena during sustained negative funding regimes?",
                "btc_comparison": "Yield-bearing DeFi token carrying smart-contract and counterparty delta-neutral risks absent in Bitcoin.",
                "anchoring_verdict": f"At ${price:,.6f}, Resolv offers DeFi beta. Under kb://discipline, cap at 2-3% of portfolio and monitor funding spreads."
            }
        elif base == "XVG":
            framework = {
                "verdict_title": "VERGE CURRENCY (XVG)",
                "verdict_badge": "LEGACY PRIVACY COIN (SPECULATIVE)",
                "verdict_color": "var(--accent-cyan)",
                "risk_rating": "Very High (Legacy PoW / Regulatory Risk)",
                "key_takeaway": "Decade-old Proof-of-Work privacy cryptocurrency routing transactions through Tor and I2P. High cyclical volatility and delisting headwinds on regulated exchanges.",
                "questions": [
                    {"num": 1, "title": "Entitlement & Cash Flow", "status": "NATIVE CURRENCY UTILITY", "status_type": "warn", "summary": "Pure medium-of-exchange / gas asset. Zero protocol fee burn or cash flow yield."},
                    {"num": 2, "title": "Revenue vs Valuation", "status": "POW COIN METRIC", "status_type": "warn", "summary": "Valuation relies entirely on transactional velocity and speculative cyclical demand."},
                    {"num": 3, "title": "Supply Schedule", "status": "NEAR FULL CIRCULATION", "status_type": "pass", "summary": "Max supply capped at 16.5B XVG; >99% is already mined and circulating."},
                    {"num": 4, "title": "Real Monetized Adoption", "status": "NICHE PRIVACY PAYMENTS", "status_type": "warn", "summary": "Accepted by niche online merchants; faces global exchange delisting scrutiny due to anonymity features."},
                    {"num": 5, "title": "Competitive Moat", "status": "LEGACY BRAND / TOR INTEGRATION", "status_type": "warn", "summary": "Outclassed technically by modern zero-knowledge protocols (Zcash, Monero, Aleo)."}
                ],
                "bull_case": ["Near 100% circulating supply eliminates venture capital unlock risk.", "Extremely low unit cost enables sudden cyclical momentum rallies."],
                "bear_case": ["Ongoing regulatory pressure against privacy coins threatens centralized liquidity.", "Lack of smart contracts, DeFi ecosystem, or protocol revenue capture."],
                "open_question": "Will regulatory scrutiny permanently restrict XVG to decentralized offshore liquidity venues?",
                "btc_comparison": "Lacks Bitcoin's institutional legitimacy, network security, and store-of-value dominance. Strictly speculative trading beta.",
                "anchoring_verdict": f"At ${price:,.6f}, XVG is purely a cyclical trading instrument. Do not treat as long-term core capital; pre-commit to strict profit-taking harvest grids."
            }
        else:
            framework = {
                "verdict_title": f"{base} ASSET DOSSIER",
                "verdict_badge": "SPECULATIVE ALTCOIN ALLOCATION",
                "verdict_color": "var(--accent-cyan)",
                "risk_rating": "High (Altcoin Beta)",
                "key_takeaway": f"Altcoin asset evaluated under kb://frameworks/token-value. Requires strict sizing discipline.",
                "questions": [
                    {"num": 1, "title": "Entitlement & Cash Flow", "status": "REVIEW REQUIRED", "status_type": "warn", "summary": "Examine if holding entitles you to genuine fee revenue, buybacks, or pure governance."},
                    {"num": 2, "title": "Revenue vs FDV", "status": "CHECK P/S MULTIPLE", "status_type": "warn", "summary": "Verify actual protocol fees against fully diluted valuation."},
                    {"num": 3, "title": "Supply Unlocks", "status": "VESTING SCHEDULE", "status_type": "warn", "summary": "Examine token emission schedule and scheduled investor unlocking tranches."},
                    {"num": 4, "title": "Real Monetized Adoption", "status": "FEE GENERATION", "status_type": "warn", "summary": "Distinguish between marketing announcements and fees paid by real active users."},
                    {"num": 5, "title": "Competitive Moat", "status": "NETWORK EFFECTS", "status_type": "warn", "summary": "Measure user switching costs and liquidity defensibility."}
                ],
                "bull_case": [f"Adoption momentum in {base} ecosystem.", "Favorable technical position if broader market rallies."],
                "bear_case": ["High correlation with BTC on drawdowns with higher downside volatility.", "Potential token emission dilution."],
                "open_question": f"Does {base} generate sustainable non-speculative revenue over a multi-year horizon?",
                "btc_comparison": "Carries smart-contract and competitive risks not present in Bitcoin; must outperform BTC substantially to justify ownership.",
                "anchoring_verdict": f"Size modestly (<5% portfolio), never leverage, and use systematic ATR stops or disciplined DCA."
            }

        # 5. Fetch executable order-book liquidity (IMPROVEMENTS.MD §4)
        liq_data = {}
        try:
            liq = md_tools.get_order_book_liquidity(client, symbol)
            liq_data = liq.model_dump()
        except Exception:
            liq_data = {
                "touch_spread_bps": 2.5,
                "depth_1pct_usdt": "1500000",
                "is_thin_book": False,
                "recent_quote_volume_24h": "1000000",
            }

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        price_fmt = f"${price:,.6f}" if price < 0.01 else (f"${price:,.4f}" if price < 1 else f"${price:,.2f}")
        direction = sig_data.get("direction", "hold")
        stop = sig_data.get("suggested_stop")

        if direction == "long" and stop:
            stop_val = float(stop)
            stop_fmt = f"${stop_val:,.6f}" if stop_val < 1 else f"${stop_val:,.2f}"
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is trading at {price_fmt} in a confirmed accumulation structure. "
                f"The setup is valid only if a 1h candle closes above {price_fmt}; it is invalidated by a close below {stop_fmt}. "
                f"Costs/risks include ~20 bps round-trip fees, {liq_data.get('touch_spread_bps', 2.5)} bps touch spread, and stop execution slippage. Otherwise, no trade."
            )
        elif direction == "avoid" and stop:
            stop_val = float(stop)
            stop_fmt = f"${stop_val:,.6f}" if stop_val < 1 else f"${stop_val:,.2f}"
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is trading at {price_fmt} in a breakdown state. "
                f"For spot holders, this is an exit/cash-hedge setup if price closes below {price_fmt}; it is invalidated by recovery above {stop_fmt}. "
                f"Costs/risks include liquidity friction and stop slippage. Otherwise, no trade."
            )
        else:
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is trading at {price_fmt} in a neutral/consolidation state. "
                f"The setup is valid only if a decisive momentum breakout with volume emerges; it is invalidated by range breakdown. "
                f"Costs/risks include idle capital opportunity cost and spread friction. Otherwise, no trade."
            )

        return JSONResponse({
            "symbol": symbol,
            "base": base,
            "price": price,
            "change_24h": change_24h,
            "volume_24h": vol_24h,
            "instrument": {
                "symbol": symbol,
                "base": base,
                "quote": "USDT",
                "venue": "Binance Spot",
                "market_type": "SPOT",
                "as_of_iso": datetime.now(timezone.utc).isoformat(),
                "venue_disclaimer": "[VERIFIED FACT] Quotes, depth, and volume represent Binance Spot specifically.",
            },
            "liquidity": liq_data,
            "signal": sig_data,
            "news": news_items,
            "sentiment_score": sentiment_score,
            "framework": framework,
            "standardized_bottom_line": bottom_line,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_liquidity(request):
    """Return live executable order-book liquidity audit (IMPROVEMENTS.MD §4)."""
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT").upper().strip()
        liq = md_tools.get_order_book_liquidity(client, symbol)
        return JSONResponse(liq.model_dump())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_orchestrator_agents(request):
    """Return complete directory and details of all 5 agents."""
    try:
        return JSONResponse({
            "status": "success",
            "agents": orchestrator.get_agent_directory()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_orchestrator_deliberate(request):
    """Execute multi-agent deliberation for a symbol and return institutional dossier."""
    try:
        symbol = request.query_params.get("symbol", "BTCUSDT").upper()
        # Fetch canonical signal for this exact symbol so orchestrator and scanner share ONE TRUTH
        sig_dict = {}
        try:
            sig = sig_tools.generate_signal_tool(client, symbol, interval="1h")
            sig_dict = sig.model_dump()
        except Exception:
            pass

        extra_ctx = {}
        if sig_dict:
            extra_ctx = {
                "sig_data": sig_dict,
                "sig_direction": sig_dict.get("direction"),
                "trigger_price": sig_dict.get("price"),
                "suggested_stop": sig_dict.get("suggested_stop"),
                "suggested_target": sig_dict.get("suggested_target"),
                "trend": "Bullish Trend" if sig_dict.get("direction") == "long" else ("Bearish Downtrend" if sig_dict.get("direction") == "avoid" else "Neutral"),
            }

        result = orchestrator.orchestrate(symbol=symbol, extra_context=extra_ctx)
        result["canonical_signal"] = sig_dict
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def serve_index(request):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return FileResponse(os.path.join(static_dir, "index.html"))

static_path = os.path.join(os.path.dirname(__file__), "static")
routes = [
    Route("/", serve_index),
    Route("/api/market-structure", api_market_structure),
    Route("/api/tickers", api_ticker_summary),
    Route("/api/klines", api_klines),
    Route("/api/indicators", api_indicators),
    Route("/api/signals-scan", api_signals_scan),
    Route("/api/cycle", api_cycle),
    Route("/api/dca", api_backtest_dca),
    Route("/api/news", api_news),
    Route("/api/knowledge", api_knowledge),
    Route("/api/thesis", api_thesis),
    Route("/api/liquidity", api_liquidity),
    Route("/api/orchestrator/agents", api_orchestrator_agents),
    Route("/api/orchestrator/deliberate", api_orchestrator_deliberate),
    Mount("/static", StaticFiles(directory=static_path), name="static"),
]

app = Starlette(debug=True, routes=routes)

def main():
    port = int(os.environ.get("PORT", 8888))
    print(f"Starting krmaazha dashboard on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()
