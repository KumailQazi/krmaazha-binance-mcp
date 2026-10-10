"""Motor de señales transparente y determinista (spec §5). PURO — sin red.

``generate_signal`` recibe indicadores YA calculados (capa 2) + un sentiment crudo
(capa 3) + ATR, y compone una ``Signal``:

1. Cada factor produce un ``value`` normalizado en [-1, +1] (lo que "opina") y una
   ``contribution = value · weight`` (lo que efectivamente empuja al score). Todo se
   expone en ``Signal.factors`` — sin caja negra (spec S3).
2. ``score = clip(Σ contributions, -1, +1)``.
3. ``direction`` por umbral (spec S5): ``long`` si score ≥ +threshold, ``avoid`` si
   score ≤ −threshold, ``hold`` en la zona neutra.
4. Niveles de riesgo por ATR (spec S4): para ``long`` el stop va abajo y el target arriba;
   para ``avoid`` se **invierten** (riesgo al alza si tenés/querés salir de lo que tenés);
   para ``hold`` no hay niveles (``None``).

Pesos default (suma 1.0, tuneables — spec S2): trend .30, momentum .20, macd .20,
bollinger .15, sentiment .15. Con todos los factores saturados en la misma dirección el
score llega a ±1 antes del clip.

Mapeos de factor (todos acotados a [-1, +1], deterministas, verificables a mano):
- **trend:** signo de (ema_fast − ema_slow) ∈ {-1, 0, +1}.
- **momentum (RSI):** lineal (50 − rsi)/20 → rsi 30 ⇒ +1 (sobreventa), rsi 70 ⇒ −1
  (sobrecompra), rsi 50 ⇒ 0; recortado a [-1, +1].
- **macd:** signo del histograma ∈ {-1, 0, +1}.
- **bollinger:** posición %B (0 = banda inferior, 1 = superior): value = 1 − 2·bb_pos,
  recortado a [-1, +1] (cerca de la inferior ⇒ +, posible rebote; superior ⇒ −).
- **sentiment:** el score crudo de capa 3, recortado a [-1, +1].
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal

from krmaazha_binance_mcp.models import Signal, SignalDirection, SignalFactor, TradeSetup

# Pesos default documentados (spec S2). Suma 1.0.
DEFAULT_WEIGHTS: dict[str, float] = {
    "trend": 0.30,
    "momentum": 0.20,
    "macd": 0.20,
    "bollinger": 0.15,
    "sentiment": 0.15,
}

# Umbral de dirección (spec S5): |score| ≥ threshold define long/avoid; debajo, hold.
DEFAULT_THRESHOLD: float = 0.15
# Riesgo (spec S4): stop = k·ATR del entry; target = R·k·ATR.
DEFAULT_ATR_MULT: float = 1.5
DEFAULT_RR: float = 2.0

# RSI: punto neutro y media-amplitud del mapeo lineal (30↔+1, 70↔-1).
_RSI_NEUTRAL = 50.0
_RSI_HALF_SPAN = 20.0

_DISCLAIMER = (
    "PROPOSAL, no es predicción (not prediction): deterministic heuristic combination of technical indicators "
    "(Layer 2) + raw sentiment (Layer 3) + ATR. Does not guarantee returns, does not decide "
    "position sizing, and NEVER executes automatically — all execution requires physical confirmation "
    "(Layer 1 gate). Validate rules with backtesting before committing capital."
)


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _trend_value(ema_fast: float, ema_slow: float) -> tuple[float, str]:
    diff = ema_fast - ema_slow
    if diff > 0:
        return 1.0, "Fast EMA above slow EMA: confirmed bullish trend."
    if diff < 0:
        return -1.0, "Fast EMA below slow EMA: confirmed bearish downtrend."
    return 0.0, "Fast and slow EMAs equal: neutral trend."


def _momentum_value(rsi: float) -> tuple[float, str]:
    value = _clip((_RSI_NEUTRAL - rsi) / _RSI_HALF_SPAN)
    if rsi < 30.0:
        note = f"RSI {rsi:.1f} in oversold territory (sobreventa): probable rebound."
    elif rsi > 70.0:
        note = f"RSI {rsi:.1f} in overbought territory (sobrecompra): correction risk."
    elif rsi < 45.0:
        note = f"RSI {rsi:.1f} below midpoint (leve sesgo a favor): slight rebound lean."
    elif rsi > 55.0:
        note = f"RSI {rsi:.1f} above midpoint (leve sesgo en contra): slight exhaustion lean."
    else:
        note = f"RSI {rsi:.1f} in neutral zone (neutra): ~neutral momentum."
    return value, note


def _macd_value(macd_hist: float) -> tuple[float, str]:
    if macd_hist > 0:
        return 1.0, "Positive MACD histogram: bullish velocity."
    if macd_hist < 0:
        return -1.0, "Negative MACD histogram: bearish downside velocity."
    return 0.0, "MACD histogram at zero: neutral momentum."


def _bollinger_value(bb_pos: float) -> tuple[float, str]:
    value = _clip(1.0 - 2.0 * bb_pos)
    if bb_pos <= 0.25:
        note = "Price compressing near lower Bollinger Band: potential bounce."
    elif bb_pos >= 0.75:
        note = "Price pressing upper Bollinger Band: potential downside reversion."
    else:
        note = "Price hovering around Bollinger middle band: neutral."
    return value, note


def _sentiment_value(sentiment: float) -> tuple[float, str]:
    value = _clip(sentiment)
    note = f"Raw news sentiment score = {value:+.2f} (Layer 3 raw feed, not analyst opinion)."
    return value, note


def _factor(name: str, value: float, weight: float, note: str) -> SignalFactor:
    return SignalFactor(
        name=name,
        value=value,
        weight=weight,
        contribution=value * weight,
        note=note,
    )


def _direction(score: float, threshold: float) -> SignalDirection:
    if score >= threshold:
        return "long"
    if score <= -threshold:
        return "avoid"
    return "hold"


def _levels(
    direction: SignalDirection, price: Decimal, atr: float, atr_mult: float, rr: float
) -> tuple[Decimal | None, Decimal | None]:
    """Stop/target por ATR (spec S4).

    - ``long``: stop = price − atr_mult·ATR (abajo); target = price + rr·atr_mult·ATR (arriba).
    - ``avoid``: se invierten — stop = price + atr_mult·ATR (arriba); target = price −
      rr·atr_mult·ATR (abajo). Cubre el caso de proteger/salir de una posición existente.
    - ``hold``: sin niveles (None).
    """
    risk = Decimal(str(atr)) * Decimal(str(atr_mult))
    reward = risk * Decimal(str(rr))
    if direction == "long":
        return price - risk, price + reward
    if direction == "avoid":
        return price + risk, price - reward
    return None, None


def generate_signal(
    *,
    symbol: str,
    interval: str,
    price: Decimal,
    ema_fast: float,
    ema_slow: float,
    rsi: float,
    macd_hist: float,
    bb_pos: float,
    sentiment: float,
    atr: float,
    weights: Mapping[str, float] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    atr_mult: float = DEFAULT_ATR_MULT,
    rr: float = DEFAULT_RR,
    as_of: int,
) -> Signal:
    """Compone una ``Signal`` transparente a partir de indicadores + sentiment + ATR.

    PURO: no pega a Binance ni lee feeds — recibe los valores ya calculados (la tool de
    ``tools/signals.py`` arma esos inputs desde capa 2/3). Cada factor expone su value,
    weight y contribution; el score es la suma acotada; la dirección sale del umbral y los
    niveles de riesgo del ATR. Siempre puebla ``factors`` y ``disclaimer`` (spec S3/S6).
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights is not None:
        w.update(weights)

    trend_v, trend_note = _trend_value(ema_fast, ema_slow)
    mom_v, mom_note = _momentum_value(rsi)
    macd_v, macd_note = _macd_value(macd_hist)
    boll_v, boll_note = _bollinger_value(bb_pos)
    sent_v, sent_note = _sentiment_value(sentiment)

    factors = [
        _factor("trend", trend_v, w["trend"], trend_note),
        _factor("momentum", mom_v, w["momentum"], mom_note),
        _factor("macd", macd_v, w["macd"], macd_note),
        _factor("bollinger", boll_v, w["bollinger"], boll_note),
        _factor("sentiment", sent_v, w["sentiment"], sent_note),
    ]

    score = _clip(sum(f.contribution for f in factors))
    direction = _direction(score, threshold)
    stop, target = _levels(direction, price, atr, atr_mult, rr)

    # Compute institutional trade setup and Net R:R (IMPROVEMENTS.MD §3 & §5)
    as_of_iso = datetime.fromtimestamp(as_of / 1000, tz=timezone.utc).isoformat()
    spread_bps = 2.5
    estimated_slippage_bps = 5.0
    fees_bps = 20.0  # 10 bps taker round-trip

    gross_rr: float | None = None
    net_rr: float | None = None
    entry_trigger: str | None = None
    time_horizon: str | None = None
    setup_obj: TradeSetup | None = None

    if direction == "long" and stop is not None and target is not None:
        gross_rr = float(rr)
        # Friction deduction: (fees + slippage + spread) in percent
        friction_pct = (fees_bps + estimated_slippage_bps + spread_bps) / 10000.0
        risk_pct = float((price - stop) / price) if price > 0 else 0.01
        reward_pct = float((target - price) / price) if price > 0 else 0.02
        net_reward_pct = max(0.0, reward_pct - friction_pct)
        net_risk_pct = risk_pct + friction_pct
        net_rr = round(net_reward_pct / net_risk_pct, 2) if net_risk_pct > 0 else 0.0
        entry_trigger = f"Confirmed {interval} candle close above {price}"
        time_horizon = "24h - 72h (Swing)"

        setup_obj = TradeSetup(
            symbol=symbol,
            direction="long",
            bar_state="closed",
            interval=interval,
            entry_trigger=entry_trigger,
            invalidation_level=stop,
            target_level=target,
            time_horizon=time_horizon,
            touch_spread_bps=spread_bps,
            estimated_slippage_bps=estimated_slippage_bps,
            fees_bps=fees_bps,
            gross_risk_reward=gross_rr,
            net_risk_reward=net_rr,
            indicator_periods={
                "ema_fast": 12,
                "ema_slow": 26,
                "rsi": 14,
                "macd": [12, 26, 9],
                "atr": 14,
                "bb": [20, 2.0],
            },
        )
    elif direction == "avoid" and stop is not None and target is not None:
        gross_rr = float(rr)
        friction_pct = (fees_bps + estimated_slippage_bps + spread_bps) / 10000.0
        risk_pct = float((stop - price) / price) if price > 0 else 0.01
        reward_pct = float((price - target) / price) if price > 0 else 0.02
        net_reward_pct = max(0.0, reward_pct - friction_pct)
        net_risk_pct = risk_pct + friction_pct
        net_rr = round(net_reward_pct / net_risk_pct, 2) if net_risk_pct > 0 else 0.0
        entry_trigger = f"Confirmed {interval} candle close below {price} (cash-hedge/exit)"
        time_horizon = "12h - 48h (Defense)"

        setup_obj = TradeSetup(
            symbol=symbol,
            direction="avoid",
            bar_state="closed",
            interval=interval,
            entry_trigger=entry_trigger,
            invalidation_level=stop,
            target_level=target,
            time_horizon=time_horizon,
            touch_spread_bps=spread_bps,
            estimated_slippage_bps=estimated_slippage_bps,
            fees_bps=fees_bps,
            gross_risk_reward=gross_rr,
            net_risk_reward=net_rr,
            indicator_periods={
                "ema_fast": 12,
                "ema_slow": 26,
                "rsi": 14,
                "macd": [12, 26, 9],
                "atr": 14,
                "bb": [20, 2.0],
            },
        )

    return Signal(
        symbol=symbol,
        interval=interval,
        direction=direction,
        score=score,
        factors=factors,
        price=price,
        suggested_stop=stop,
        suggested_target=target,
        atr=atr,
        disclaimer=_DISCLAIMER,
        as_of=as_of,
        as_of_iso=as_of_iso,
        entry_trigger=entry_trigger,
        time_horizon=time_horizon,
        gross_rr=gross_rr,
        net_rr=net_rr,
        spread_bps=spread_bps,
        estimated_slippage_bps=estimated_slippage_bps,
        trading_fees_bps=fees_bps,
        trade_setup=setup_obj,
    )
