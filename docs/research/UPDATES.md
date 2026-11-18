# Futures Research Engine — Implementation Updates

**Status**: Phase 0 — 7 of 8 Modules Verified & Shipped  
**Date**: `17-11-2026`  
**Test Suite**: 97/97 tests passed (100%) · Subpackage Coverage: 96.8% · 0 warnings · `mypy --strict` clean

---

## 1. Verified Architecture Overview

![Futures Research Engine Overview](../assets/futures-phase0-overview.png)

---

## 2. Test Execution & Coverage Audit

![Futures Test Suite Coverage](../assets/futures-test-suite-coverage.png)

---

## 3. Module Breakdown & Verification Results

### 3.1 [`futures/universe.py`](../../src/krmaazha_binance_mcp/futures/universe.py) — Point-in-Time Universe
* **Status**: ✅ **done** · 14 tests · 92% coverage
* **Mathematical Invariant**: Guaranteed $t \le \text{as\_of\_date}$ filtering eliminating survivorship bias.
* **Key Achievements**:
  - Full ingestion and reconstruction of 986 USD-M perpetual symbols from Binance's archives.
  - Recovers **306 delisted USDT perps** alongside the 527 currently active contracts.
  - Automatically isolates 13 denomination-multiplier symbols (e.g. `1000PEPEUSDT`, `1000SHIBUSDT`, `1000000BOBUSDT`) from their raw predecessors, preventing synthetic +99,900% returns that corrupt momentum ranking.

### 3.2 [`futures/costs.py`](../../src/krmaazha_binance_mcp/futures/costs.py) — Realistic Cost & Funding Engine
* **Status**: ✅ **done** · 24 tests · 99% coverage
* **Mathematical Invariant**: Zero-commission prohibited by design; slippage is always strictly adverse.
* **Key Achievements**:
  - `FeeModel` enforces explicit taker/maker fees (raises `ValueError` on 0 fee rate).
  - `FixedBasisPointSlippage` and `VolumeImpactSlippage` penalize both entry and exit legs adversely.
  - `accrue_funding_events()` reads dynamic funding intervals (4h/8h) directly from historical archive timestamps, correctly computing long payments and short receipts based on signed funding rates.

### 3.3 [`futures/portfolio.py`](../../src/krmaazha_binance_mcp/futures/portfolio.py) — Multi-Symbol Portfolio Simulator
* **Status**: ✅ **done** · 19 tests · 98% coverage
* **Mathematical Invariant**: Dual liquidation assertions: end-of-bar equity check AND intra-bar High/Low wick breaches.
* **Key Achievements**:
  - Models multi-symbol long/short weights with volatility targeting ($\sigma_{\text{target}}$) and strict leverage limits.
  - Exact Binance maintenance margin tier modeling per symbol.
  - Real-time anti-ruin assertion: wicks breaching liquidation thresholds raise `AccountLiquidatedError` immediately, preventing backtests from ignoring catastrophic intra-candle wipeouts.
  - Graceful force-closure of positions upon symbol delisting events.

### 3.4 [`futures/stats.py`](../../src/krmaazha_binance_mcp/futures/stats.py) — Institutional Statistics & Overfitting Corrections
* **Status**: ✅ **done** · 14 tests · 99% coverage
* **Mathematical Invariant**: Pure mathematical implementation using `math.erf` (zero SciPy dependency).
* **Key Achievements**:
  - Exact higher moments: sample skewness and kurtosis.
  - Annualized Sharpe, Sortino, Calmar, and maximum drawdown calculations.
  - **Deflated Sharpe Ratio (DSR)**: Penalizes trial count ($N$), variance of trials, and non-normal return distributions to adjust for data mining.
  - **Probability of Backtest Overfitting (PBO)** via Combinatorially Symmetric Cross-Validation (CSCV): Partitions $T$ period returns across $S$ combinations to calculate true out-of-sample degradation.

### 3.5 [`futures/research.py`](../../src/krmaazha_binance_mcp/futures/research.py) — Walk-Forward Engine & Institutional Gate
* **Status**: ✅ **done** · 12 tests · 98% coverage
* **Mathematical Invariant**: Triple anti-lookahead protection ($[:-1]$ closed bar slicing, signal at $t$ executes at open $t+1$, dynamic PIT universe).
* **Key Achievements**:
  - Decoupled In-Sample (IS) parameter calibration and Out-of-Sample (OOS) evaluation across rolling and anchored windows.
  - Pre-registered 6-point institutional gate:
    1. OOS return net of costs $> 0$.
    2. Annualized Sharpe $> 1.0$.
    3. Deflated Sharpe Ratio (DSR) $> 0.0$.
    4. PBO via CSCV $< 0.5$.
    5. Beats buy-and-hold in $> 50\%$ of out-of-sample windows.
    6. Minimum 50 OOS trades for statistical validity.

### 3.6 [`futures/db/`](../../src/krmaazha_binance_mcp/futures/db/) — PostgreSQL on Railway
* **Status**: ✅ **done** · 14 tests · 93% coverage
* **Mathematical Invariant**: Concurrent migration safety via `pg_advisory_lock(14022026)` and immutable SHA-256 script hashing.
* **Key Achievements**:
  - Versioned migration engine (`schema_migrations`) with `MigrationTamperedError` detection.
  - High-throughput `COPY ... FROM STDIN WITH (FORMAT csv)` streaming for millions of trial period returns without row-by-row `INSERT` bottlenecks.
  - `load_trial_return_matrix(run_id)`: Instant reconstruction of the complete $T \times N$ period return matrix for post-hoc multiple testing corrections.
  - `live_vs_model` auditing table tracking fee, slippage, and funding discrepancies in basis points (bps).

