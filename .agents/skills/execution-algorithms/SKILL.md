---
name: execution-algorithms
description: >-
  Algorithmic execution strategies (TWAP, VWAP, Iceberg slicing), order-book depth band analysis,
  micro-cap slippage mitigation, sub-cent tick precision, and net fee friction modeling for spot and
  perpetual crypto orders.
---

# Algorithmic Execution & Smart Order Routing Skill

This skill provides quantitative execution algorithms and liquidity management for orders submitted to Binance Spot and Futures markets.

---

## 1. Algorithmic Slicing Architectures

When executing large trades or trading illiquid micro-cap tokens (e.g., NOM, RESOLV, XVG), direct market orders incur severe market impact and slippage.

### 1.1 TWAP (Time-Weighted Average Price)
- **Objective**: Divide an order of size $Q$ into $N$ equal slices executed at regular time intervals $\Delta t$.
- **Slice Sizing**:
  $$q_i = \frac{Q}{N}$$
- **Optimal Slice Selection Rule**:
  $$\text{Slice Notional} \le \min\left(0.05 \times \text{Depth}_{\pm 1\%}, \$5,000\text{ USDT}\right)$$
- **Interval $\Delta t$**:
  Calculated across target execution window $T$ (e.g. 15 minutes to 2 hours):
  $$\Delta t = \frac{T}{N}$$

### 1.2 VWAP (Volume-Weighted Average Price)
- **Objective**: Match historical volume distribution curves throughout the trading day to minimize deviation from institutional benchmark.
- **Slice Sizing**:
  $$q_i = Q \times w_i, \quad \text{where } w_i = \frac{V_i}{\sum_{k=1}^N V_k}$$
  where $V_i$ is expected volume in time bucket $i$.

### 1.3 Iceberg Order Slicing
- Places small visible limit orders on the book (`LOT_SIZE` compliant), refilling the visible size as previous tranches get filled.
- Prevents revealing total institutional order size to adverse front-running algorithms.

---

## 2. Order Book Depth & Friction Modeling

### 2.1 Touch Spread Calculation
Touch spread measures the immediate liquidity gap between best bid and best ask:
$$\text{Spread (bps)} = \frac{\text{Ask}_{\text{best}} - \text{Bid}_{\text{best}}}{\text{Mid Price}} \times 10,000$$

### 2.2 Liquidity Band Measurement
Order book depth must be measured within normalized price bands from mid price:
- **Depth $\pm 1\%$**: Cumulative bid/ask notionals within $1\%$ of mid price:
  $$\text{Depth}_{1\%} = \sum_{|P_i - P_{\text{mid}}| \le 0.01 \cdot P_{\text{mid}}} P_i \cdot Q_i$$
- **Depth $\pm 2\%$**: Secondary cushion for volatility spikes.

### 2.3 Net Friction Equation
Total execution friction must account for all trading costs:
$$\text{Net Friction (bps)} = \text{Exchange Fee (20 bps)} + \frac{\text{Touch Spread}}{2} + \text{Market Impact Slippage}$$
Where estimated market impact slippage is modeled as:
$$\text{Impact (bps)} \approx \left(\frac{\text{Order Notional}}{\text{Depth}_{1\%}}\right) \times 80\text{ bps}$$

---

## 3. Micro-Cap Sub-Cent Precision Rules

### 3.1 Decimal Arithmetic
All prices and quantities must strictly use Python `Decimal` with exchange-defined tick sizes:
- `PRICE_FILTER`: minimum tick size (e.g. `0.00000100` for NOM).
- `LOT_SIZE`: minimum step size (e.g. `1.00000000`).
- `MIN_NOTIONAL`: minimum order value (e.g. `$5.00` USDT).

### 3.2 Scientific Notation Defense
Never allow `str(Decimal("0.00000000"))` to convert into `"0E-8"`. Always format prices using explicit decimal quantization:
```python
price_str = f"{price_decimal:.6f}" if price_decimal < 1 else f"{price_decimal:,.2f}"
```
