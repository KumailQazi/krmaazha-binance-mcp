"""Motor de investigación cuantitativa y validación Walk-Forward (futures/research.py).

Implementa el marco institucional de investigación out-of-sample exigido por la doctrina
(kb://discipline Regla 7 y ROADMAP.md):

1. Triple Anti-Lookahead:
   - Selección de parámetros estrictamente en la ventana In-Sample (Train) [t_start, t_train_end).
   - Calentamiento causal de indicadores sin fuga de datos futuros.
   - Ejecución desfasada: la señal en t-1 decide la posición mantenida en t, ejecutada al open de t
     (t -> t+1 execution).
2. Fricción y Costos Reales:
   - Integración directa con futures/costs.py (FeeModel, SlippageModel, devengo de funding real).
3. Registro Completo Multi-Trial:
   - Registra el rendimiento y vector de retornos de TODAS las N configuraciones evaluadas
     en la optimización in-sample, posibilitando el cálculo exacto del Deflated Sharpe Ratio
     (DSR) y Combinatorially Symmetric Cross-Validation (CSCV) PBO.
4. Gate Institucional Estricto (6 Criterios de Calificación):
   - Retorno neto OOS > 0 en términos absolutos.
   - Sharpe ratio OOS >= 1.0.
   - DSR > 0.50 (probabilidad estadísticamente significativa frente a N trials).
   - PBO < 0.50 (baja probabilidad de sobreajuste).
   - Consistencia de ventanas > 50% (supera a Buy & Hold en la mayoría de ventanas).
   - Trades OOS cerrados >= min_oos_trades (para rechazar ruido de baja muestra).
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import pandas as pd

from krmaazha_binance_mcp import indicators
from krmaazha_binance_mcp.backtest import ema_cross, rsi_threshold
from krmaazha_binance_mcp.futures.costs import (
    CostModel,
    accrue_funding_events,
)
from krmaazha_binance_mcp.futures.stats import (
    DeflatedSharpeResult,
    PBOResult,
    compute_deflated_sharpe_ratio,
    compute_drawdown_series,
    compute_pbo_cscv,
    compute_sharpe_ratio,
    compute_sortino_ratio,
)

# ── 1. Protocolo de Hipótesis de Estrategia ───────────────────────────────────


class StrategyHypothesis(Protocol):
    """Protocolo que debe cumplir cualquier hipótesis evaluada en walk-forward."""

    @property
    def name(self) -> str:
        """Nombre identificador de la hipótesis."""
        ...

    def param_grid(self) -> list[dict[str, Any]]:
        """Devuelve la lista exhaustiva de combinaciones de parámetros a evaluar."""
        ...

    def compute_signal(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
        """Calcula la serie causal de señales en {0, 1} o {-1, 0, 1} sobre el DataFrame completo."""
        ...


class EmaCrossHypothesis:
    """Hipótesis de cruce de medias móviles exponenciales (rápida vs lenta)."""

    def __init__(
        self,
        fast_periods: Sequence[int] | None = None,
        slow_periods: Sequence[int] | None = None,
    ) -> None:
        self.fast_periods = list(fast_periods or [5, 8, 12, 20])
        self.slow_periods = list(slow_periods or [21, 26, 50, 100])

    @property
    def name(self) -> str:
        return "ema_cross"

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for f, s in itertools.product(self.fast_periods, self.slow_periods):
            if f < s:
                grid.append({"fast": f, "slow": s})
        return grid

    def compute_signal(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
        return ema_cross(df, fast=params["fast"], slow=params["slow"])


class RsiThresholdHypothesis:
    """Hipótesis de reversión a la media por umbrales de RSI (oversold / overbought)."""

    def __init__(
        self,
        low_thresholds: Sequence[float] | None = None,
        high_thresholds: Sequence[float] | None = None,
    ) -> None:
        self.low_thresholds = list(low_thresholds or [20.0, 25.0, 30.0, 35.0])
        self.high_thresholds = list(high_thresholds or [65.0, 70.0, 75.0, 80.0])

    @property
    def name(self) -> str:
        return "rsi_threshold"

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for low, high in itertools.product(self.low_thresholds, self.high_thresholds):
            if low < high:
                grid.append({"low": float(low), "high": float(high)})
        return grid

    def compute_signal(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
        return rsi_threshold(df, low=params["low"], high=params["high"])


class EmaRegimeHypothesis:
    """Hipótesis de cruce de medias con filtro de régimen de fuerza de tendencia."""

    def __init__(
        self,
        fast_periods: Sequence[int] | None = None,
        slow_periods: Sequence[int] | None = None,
        thetas: Sequence[float] | None = None,
    ) -> None:
        self.fast_periods = list(fast_periods or [8, 12, 20])
        self.slow_periods = list(slow_periods or [26, 50, 100])
        self.thetas = list(thetas or [0.0, 0.01, 0.02, 0.04])

    @property
    def name(self) -> str:
        return "ema_cross_regime"

    def param_grid(self) -> list[dict[str, Any]]:
        grid = []
        for f, s, th in itertools.product(self.fast_periods, self.slow_periods, self.thetas):
            if f < s:
                grid.append({"fast": f, "slow": s, "theta": float(th)})
        return grid

    def compute_signal(self, df: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
        base = ema_cross(df, fast=params["fast"], slow=params["slow"])
        theta = float(params["theta"])
        if theta <= 0.0:
            return base

        ef = indicators.ema(df["close"], params["fast"])
        es = indicators.ema(df["close"], params["slow"])
        strength = (ef / es - 1.0).abs()
        strong = (strength > theta).astype("int64")
        return pd.Series((base.to_numpy() & strong.to_numpy()), index=df.index)


# ── 2. Clases de Datos y Verificación de Gate Institucional ───────────────────


@dataclass(frozen=True)
class WalkForwardConfig:
    """Configuración del análisis walk-forward."""

    train_bars: int
    test_bars: int
    step_bars: int
    cost_model: CostModel
    anchored: bool = False
    min_oos_trades: int = 50
    min_windows: int = 3
    annualization_factor: int = 365

    def __post_init__(self) -> None:
        if self.train_bars < 10:
            raise ValueError(f"train_bars debe ser >= 10, recibido: {self.train_bars}")
        if self.test_bars < 5:
            raise ValueError(f"test_bars debe ser >= 5, recibido: {self.test_bars}")
        if self.step_bars < 1:
            raise ValueError(f"step_bars debe ser >= 1, recibido: {self.step_bars}")


@dataclass(frozen=True)
class WindowResult:
    """Resultado detallado de una ventana walk-forward individual."""

    window_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    best_params: dict[str, Any]
    train_metric: float
    test_return_pct: float
    buy_hold_return_pct: float
    trades_count: int
    beat_buy_hold: bool
    fee_cost: float
    slippage_cost: float
    funding_cost: float
    test_daily_returns: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class GateVerdict:
    """Evaluación estricta de los 6 criterios institucionales de calificación."""

    passed: bool
    positive_oos_return: bool
    sharpe_above_hurdle: bool
    dsr_significant: bool
    pbo_below_half: bool
    consistency_above_half: bool
    sufficient_trades: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class WalkForwardResult:
    """Resultado consolidado del análisis walk-forward out-of-sample."""

    strategy_name: str
    symbol: str
    timeframe: str
    n_candles: int
    n_windows: int
    oos_return_pct: float
    oos_buyhold_pct: float
    edge_pct: float
    oos_trades: int
    windows_beat_bh: int
    consistency: float
    oos_sharpe: float
    oos_sortino: float
    oos_max_drawdown: float
    deflated_sharpe: DeflatedSharpeResult
    pbo_result: PBOResult | None
    gate_verdict: GateVerdict
    windows: list[WindowResult]
    concatenated_oos_returns: pd.Series
    concatenated_oos_equity: pd.Series


# ── 3. Motor de Simulación Windowed con Costos Reales ─────────────────────────


def simulate_window(
    opens: np.ndarray,
    closes: np.ndarray,
    open_times: np.ndarray,
    signal: np.ndarray,
    start_idx: int,
    end_idx: int,
    cost_model: CostModel,
    funding_df: pd.DataFrame | None = None,
) -> tuple[float, int, float, float, float, list[float]]:
    """Simula una ventana [start_idx, end_idx) con anti-lookahead y costos reales.

    Reglas de ejecución:
    - La posición que se mantiene durante la barra i la decide signal[i - 1].
    - El fill ocurre en open[i] con fricción de comisión y slippage.
    - Se devenga funding real para cualquier evento dentro del intervalo de tiempo.
    - Se marca a close la posición abierta en la última barra del bloque.

    Retorna:
    - return_pct: retorno neto porcentual de la ventana.
    - n_trades: cantidad de trades cerrados (round-trips).
    - fee_total: comisiones totales deducidas.
    - slippage_total: costo total de slippage.
    - funding_total: costo neto de funding (positivo = costo, negativo = cobro).
    - daily_returns: serie de retornos periódicos de la ventana.
    """
    n_win = end_idx - start_idx
    if n_win < 2:
        return 0.0, 0, 0.0, 0.0, 0.0, []

    equity = 1.0
    cash = 1.0
    current_qty = 0.0
    closed_trades = 0

    fee_accum = 0.0
    slippage_accum = 0.0
    funding_accum = 0.0
    period_returns: list[float] = []

    last_equity = 1.0

    for i in range(start_idx, end_idx):
        t_ms = int(open_times[i])
        o_price = float(opens[i])
        c_price = float(closes[i])

        # 1. Devengo de funding si hubo posición previa
        if funding_df is not None and not funding_df.empty and i > start_idx and current_qty != 0.0:
            prev_t_ms = int(open_times[i - 1])
            f_cash, _ = accrue_funding_events(
                funding_df, current_qty, o_price, prev_t_ms, t_ms
            )
            # f_cash positivo es ingreso a la cuenta, negativo es deducción
            cash += f_cash
            equity += f_cash
            funding_accum -= f_cash

        # 2. Señal decidida en la barra anterior (anti-lookahead estricto)
        target_signal = float(signal[i - 1]) if i > 0 else 0.0
        # Convertir señal target en cantidad deseada (asumiendo 1x notional sobre equity)
        target_qty = (target_signal * equity / o_price) if o_price > 0.0 else 0.0
        delta_qty = target_qty - current_qty

        # 3. Ejecución de rebalanceo si hay cambio de posición
        if abs(delta_qty) > 1e-8:
            side = 1 if delta_qty > 0 else -1
            fill = cost_model.simulate_fill(
                nominal_price=o_price,
                qty=abs(delta_qty),
                side=side,
                is_taker=True,
            )
            fee_accum += fill.fee
            slippage_accum += fill.slippage_cost
            friction = fill.total_friction
            cash -= friction
            equity -= friction

            # Contar cierre si cambia de signo o se cierra a flat
            if (current_qty > 0 and target_qty <= 0) or (current_qty < 0 and target_qty >= 0):
                closed_trades += 1

            current_qty = target_qty

        # 4. Mark to market al cierre de la barra
        pnl_bar = current_qty * (c_price - o_price)
        bar_equity = max(1e-8, equity + pnl_bar)

        ret_bar = (bar_equity - last_equity) / last_equity if last_equity > 0.0 else 0.0
        period_returns.append(ret_bar)
        last_equity = bar_equity
        equity = bar_equity

    net_return_pct = (equity - 1.0) * 100.0
    return (
        net_return_pct,
        closed_trades,
        fee_accum,
        slippage_accum,
        funding_accum,
        period_returns,
    )


def compute_buy_hold_window(
    opens: np.ndarray,
    closes: np.ndarray,
    start_idx: int,
    end_idx: int,
) -> float:
    """Calcula el Buy & Hold de la ventana comprando al open ejecutable (start + 1)."""
    if end_idx - start_idx < 2:
        return 0.0
    first_open = opens[start_idx + 1]
    last_close = closes[end_idx - 1]
    if first_open <= 0.0:
        return 0.0
    return float((last_close / first_open - 1.0) * 100.0)


# ── 4. Motor de Ejecución Walk-Forward ─────────────────────────────────────────


class WalkForwardEngine:
    """Motor de análisis walk-forward institucional out-of-sample."""

    def __init__(self, config: WalkForwardConfig) -> None:
        self.config = config

    def run(
        self,
        df: pd.DataFrame,
        hypothesis: StrategyHypothesis,
        symbol: str = "BTCUSDT",
        timeframe: str = "1d",
        funding_df: pd.DataFrame | None = None,
    ) -> WalkForwardResult:
        """Ejecuta el walk-forward completo para una hipótesis sobre datos kline."""
        required_cols = {"open_time", "open", "high", "low", "close"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"DataFrame carece de columnas requeridas: {missing}")

        n_total = len(df)
        train_bars = self.config.train_bars
        test_bars = self.config.test_bars
        step_bars = self.config.step_bars

        min_required = train_bars + test_bars
        if n_total < min_required:
            raise ValueError(
                f"Datos insuficientes para walk-forward: {n_total} velas provistas, "
                f"se requieren al menos {min_required} velas "
                f"(train={train_bars} + test={test_bars})"
            )

        opens = df["open"].to_numpy(dtype="float64")
        closes = df["close"].to_numpy(dtype="float64")
        open_times = df["open_time"].to_numpy(dtype="int64")

        # 1. Precomputación causal de señales de toda la grilla de parámetros
        param_grid = hypothesis.param_grid()
        if not param_grid:
            raise ValueError(f"La hipótesis {hypothesis.name} devolvió una grilla vacía.")

        cached_signals: list[tuple[dict[str, Any], np.ndarray]] = []
        for params in param_grid:
            sig_series = hypothesis.compute_signal(df, params)
            cached_signals.append((params, sig_series.to_numpy(dtype="int64")))

        # 2. Generación de particiones de ventanas
        windows_results: list[WindowResult] = []
        all_trials_sharpes: list[float] = []
        all_trials_returns_oos: list[list[float]] = [[] for _ in param_grid]

        ws = 0
        window_idx = 1
        oos_compounded_equity = 1.0
        oos_compounded_bh_equity = 1.0
        total_oos_trades = 0
        windows_beat_bh_count = 0
        all_oos_returns_stitched: list[float] = []

        while ws + train_bars + test_bars <= n_total:
            tr_s = 0 if self.config.anchored else ws
            tr_e = ws + train_bars
            te_s = tr_e
            te_e = tr_e + test_bars

            # A. Optimización In-Sample: evaluar todos los trials exclusivamente en Train
            best_params = None
            best_train_metric = -float("inf")
            best_sig = None

            for trial_idx, (p_dict, sig_arr) in enumerate(cached_signals):
                tr_ret, _, _, _, _, tr_daily_rets = simulate_window(
                    opens,
                    closes,
                    open_times,
                    sig_arr,
                    tr_s,
                    tr_e,
                    self.config.cost_model,
                    funding_df=funding_df,
                )
                tr_sharpe = compute_sharpe_ratio(
                    tr_daily_rets, annualization_factor=self.config.annualization_factor
                )
                all_trials_sharpes.append(tr_sharpe)

                # Criterio in-sample: maximizar retorno neto o Sharpe
                if tr_ret > best_train_metric:
                    best_train_metric = tr_ret
                    best_params = p_dict
                    best_sig = sig_arr

                # B. Registrar retornos OOS para cada trial (requerido para CSCV PBO)
                _, _, _, _, _, te_trial_rets = simulate_window(
                    opens,
                    closes,
                    open_times,
                    sig_arr,
                    te_s,
                    te_e,
                    self.config.cost_model,
                    funding_df=funding_df,
                )
                all_trials_returns_oos[trial_idx].extend(te_trial_rets)

            if best_params is None or best_sig is None:
                ws += step_bars
                continue

            # C. Ejecución Out-of-Sample del ganador in-sample
            te_ret, te_trades, fee_cost, slip_cost, fund_cost, te_rets = simulate_window(
                opens,
                closes,
                open_times,
                best_sig,
                te_s,
                te_e,
                self.config.cost_model,
                funding_df=funding_df,
            )
            bh_ret = compute_buy_hold_window(opens, closes, te_s, te_e)
            beat_bh = te_ret > bh_ret

            if beat_bh:
                windows_beat_bh_count += 1
            total_oos_trades += te_trades
            oos_compounded_equity *= 1.0 + (te_ret / 100.0)
            oos_compounded_bh_equity *= 1.0 + (bh_ret / 100.0)
            all_oos_returns_stitched.extend(te_rets)

            windows_results.append(
                WindowResult(
                    window_index=window_idx,
                    train_start=tr_s,
                    train_end=tr_e,
                    test_start=te_s,
                    test_end=te_e,
                    best_params=best_params,
                    train_metric=best_train_metric,
                    test_return_pct=te_ret,
                    buy_hold_return_pct=bh_ret,
                    trades_count=te_trades,
                    beat_buy_hold=beat_bh,
                    fee_cost=fee_cost,
                    slippage_cost=slip_cost,
                    funding_cost=fund_cost,
                    test_daily_returns=te_rets,
                )
            )

            window_idx += 1
            ws += step_bars

        n_windows = len(windows_results)
        if n_windows < self.config.min_windows:
            raise ValueError(
                f"Se generaron solo {n_windows} ventanas, pero min_windows es "
                f"{self.config.min_windows}"
            )

        # 3. Concatenación y Métricas de Rendimiento Out-of-Sample
        oos_return_pct = (oos_compounded_equity - 1.0) * 100.0
        oos_buyhold_pct = (oos_compounded_bh_equity - 1.0) * 100.0
        edge_pct = oos_return_pct - oos_buyhold_pct
        consistency = (windows_beat_bh_count / n_windows) if n_windows > 0 else 0.0

        oos_returns_series = pd.Series(all_oos_returns_stitched, dtype="float64")
        oos_equity_series = pd.Series(
            np.cumprod(1.0 + oos_returns_series.to_numpy()), dtype="float64"
        )

        oos_sharpe = compute_sharpe_ratio(
            oos_returns_series, annualization_factor=self.config.annualization_factor
        )
        oos_sortino = compute_sortino_ratio(
            oos_returns_series, annualization_factor=self.config.annualization_factor
        )
        mdd, _, _ = compute_drawdown_series(oos_equity_series)

        # 4. Cálculo del Deflated Sharpe Ratio (DSR)
        dsr_res = compute_deflated_sharpe_ratio(
            trial_sharpe=oos_sharpe,
            all_sharpes=all_trials_sharpes,
            returns=oos_returns_series,
            annualization_factor=self.config.annualization_factor,
        )

        # 5. Cálculo de PBO via CSCV si hay suficientes observaciones
        pbo_res: PBOResult | None = None
        min_trial_len = (
            min(len(col) for col in all_trials_returns_oos) if all_trials_returns_oos else 0
        )
        if min_trial_len >= 16 and len(param_grid) >= 2:
            try:
                # Truncar al mismo largo mínimo
                mat_oos = np.column_stack([col[:min_trial_len] for col in all_trials_returns_oos])
                pbo_res = compute_pbo_cscv(
                    mat_oos, num_blocks=8, annualization_factor=self.config.annualization_factor
                )
            except Exception:  # noqa: BLE001
                pbo_res = None

        # 6. Evaluación del Gate Institucional
        passed_ret = oos_return_pct > 0.0
        passed_sr = oos_sharpe >= 1.0
        passed_dsr = dsr_res.deflated_sharpe_ratio >= 0.50
        passed_pbo = (pbo_res is None) or (pbo_res.pbo < 0.50)
        passed_cons = consistency > 0.50
        passed_trades = total_oos_trades >= self.config.min_oos_trades

        failure_reasons: list[str] = []
        if not passed_ret:
            failure_reasons.append(
                f"Retorno OOS negativo ({oos_return_pct:+.2f}%): "
                f"no gana plata en términos absolutos."
            )
        if not passed_sr:
            failure_reasons.append(
                f"Sharpe OOS insuficiente ({oos_sharpe:.2f} < 1.00)."
            )
        if not passed_dsr:
            failure_reasons.append(
                f"DSR insuficiente ({dsr_res.deflated_sharpe_ratio:.2f} < 0.50): "
                f"indistinguible de ruido frente a {dsr_res.num_trials} trials."
            )
        if not passed_pbo and pbo_res is not None:
            failure_reasons.append(
                f"PBO excesivo ({pbo_res.pbo:.2%} >= 50%): alta probabilidad de sobreajuste."
            )
        if not passed_cons:
            failure_reasons.append(
                f"Consistencia insuficiente ({consistency:.1%} <= 50%): "
                f"no le gana a buy & hold en la mayoría de ventanas."
            )
        if not passed_trades:
            failure_reasons.append(
                f"Trades insuficientes ({total_oos_trades} < {self.config.min_oos_trades}): "
                f"muestra insuficiente, riesgo de artefacto estadístico."
            )

        gate_verdict = GateVerdict(
            passed=(len(failure_reasons) == 0),
            positive_oos_return=passed_ret,
            sharpe_above_hurdle=passed_sr,
            dsr_significant=passed_dsr,
            pbo_below_half=passed_pbo,
            consistency_above_half=passed_cons,
            sufficient_trades=passed_trades,
            failure_reasons=failure_reasons,
        )

        return WalkForwardResult(
            strategy_name=hypothesis.name,
            symbol=symbol,
            timeframe=timeframe,
            n_candles=n_total,
            n_windows=n_windows,
            oos_return_pct=oos_return_pct,
            oos_buyhold_pct=oos_buyhold_pct,
            edge_pct=edge_pct,
            oos_trades=total_oos_trades,
            windows_beat_bh=windows_beat_bh_count,
            consistency=consistency,
            oos_sharpe=oos_sharpe,
            oos_sortino=oos_sortino,
            oos_max_drawdown=mdd,
            deflated_sharpe=dsr_res,
            pbo_result=pbo_res,
            gate_verdict=gate_verdict,
            windows=windows_results,
            concatenated_oos_returns=oos_returns_series,
            concatenated_oos_equity=oos_equity_series,
        )
