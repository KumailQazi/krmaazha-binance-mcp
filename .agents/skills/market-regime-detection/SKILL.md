---
name: market-regime-detection
description: >-
  Quantitative market regime classification (Trending Bull/Bear, Mean-Reverting Range, High Volatility
  Expansion, Liquidity Crisis) with dynamic parameter adaptation for systematic crypto models and spot portfolios.
---

# Quantitative Market Regime Detection Skill

This skill governs the identification of macroeconomic and volatility regimes in crypto markets, enabling adaptive algorithmic parameters and risk budgeting.

---

## 1. The Four Primary Market Regimes

Systematic trading performance depends critically on matching strategies to prevailing market regimes:

| Regime | Mathematical Criteria | Optimal Strategy | Risk Allocation |
|---|---|---|---|
| **Bullish Expansion** | Price > EMA 200, Mayer Multiple 1.0–2.4, RSI > 55, +DMI > -DMI | Momentum / Trend Following (Rule 3) | 100% normal spot allocation |
| **Bear Capitulation** | Price < EMA 200, 200-day SMA slope negative, RSI < 40 | Cash Preservation / Inactivity (Rule 3) | Cash / USDT Standard |
| **Mean-Reverting Range** | ADX < 20, Bollinger Band width contracted, RSI oscillating 40–60 | Grid Trading / Mean Reversion | Reduced notional, tight stops |
| **Liquidity Shock / Crisis** | ATR spike > 3σ, Touch spread > 15 bps, Depth ±1% drop > 60% | Emergency Halt / Confirmer Lockout | 0% execution (Rule 6 discipline) |

---

## 2. Quantitative Indicators & Classification Formulas

### 2.1 Trend Regime Detection
- **Mayer Multiple**:
  $$\text{MM} = \frac{\text{Current Close Price}}{\text{200-day SMA}}$$
  * $\text{MM} < 0.6$: Historical cycle bottom / cyclical accumulation zone.
  * $0.6 \le \text{MM} < 1.0$: Bear market recovery.
  * $1.0 \le \text{MM} < 2.4$: Healthy bull trend accumulation.
  * $\text{MM} \ge 2.4$: Overextended euphoric top warning (Rule 5 profit harvesting).

- **EMA Momentum Alignment**:
  Fast EMA (12-period) vs Slow EMA (26-period):
  $$\text{Trend Score} = \frac{\text{EMA}_{12} - \text{EMA}_{26}}{\text{EMA}_{26}} \times 100$$

### 2.2 Volatility & Liquidity Regime Detection
- **Normalized ATR (NATR)**:
  $$\text{NATR} = \frac{\text{ATR}_{14}}{\text{Close Price}} \times 100$$
  * $\text{NATR} < 2.0\%$: Compressed volatility (breakout impending).
  * $2.0\% \le \text{NATR} \le 5.0\%$: Normal crypto trading volatility.
  * $\text{NATR} > 7.5\%$: Extreme volatility expansion (widen stops, halve position sizing).

- **Order-Book Liquidity Ratio**:
  $$\text{Liquidity Health} = \frac{\text{Depth}_{\pm 1\%}}{\text{24h Volume Notional}}$$

---

## 3. Adaptive Parameter Tuning Rules

When regime changes are detected, autonomous models must adapt parameters rather than using static constants:
1. **In High Volatility**: Stop loss distance must expand from $2.5\%$ to $1.5 \times \text{ATR}$, with position size scaled down proportionally to keep $1R$ risk constant.
2. **In Compressed Ranges**: Trend-following breakout triggers require 2 consecutive closed candles outside range boundaries to filter false breakouts.
3. **In Illiquid / Thin Books**: Maximum single order size capped at $2\%$ of $\pm 1\%$ depth.
