"""Motor de cartera y simulación multi-activo para futuros USDⓈ-M (spec Phase 0).

Honesto por diseño y sin trampas:
1. **Multi-símbolo Long/Short real:** Permite carteras combinadas en los 986 símbolos
   (527 vivos, 306 delistados). Maneja delisteos forzando liquidación al último precio
   disponible sin desapariciones mágicas.
2. **Notional vs. Margin:** Distingue el nocional total expuesto (apalancamiento bruto) del
   colateral en cuenta (equity), computando Margin Ratio frente al Maintenance Margin (MMR).
3. **Volatility Targeting:** Escala dinámicamente el apalancamiento según la volatilidad
   realizada rodante sin lookahead, con techo duro de apalancamiento bruto (leverage cap).
4. **Accrual real de funding:** Integra `futures/costs.py` devengando pagos/cobros de funding
   reales a lo largo de los períodos de tenencia en intervalos variables.
5. **Aserción de proximidad de liquidación:** Si el equity perfora el margen de mantenimiento
   (sea al cierre de la barra o en la mecha adversa intra-barra), levanta `AccountLiquidatedError`
   y termina la corrida, impidiendo que el backtest sobreviva a quiebras reales.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from .costs import CostDecomposition, CostModel, accrue_funding_events


class AccountLiquidatedError(Exception):
    """Excepción lanzada cuando el equity de la cuenta perfora el margen de mantenimiento."""

    def __init__(
        self,
        open_time: int,
        equity: float,
        maintenance_margin: float,
        margin_ratio: float,
        reason: str,
        symbol: str | None = None,
    ) -> None:
        self.open_time = open_time
        self.equity = equity
        self.maintenance_margin = maintenance_margin
        self.margin_ratio = margin_ratio
        self.reason = reason
        self.symbol = symbol
        msg = (
            f"CUENTA LIQUIDADA en open_time={open_time}: "
            f"Equity={equity:.2f} <= MaintenanceMargin={maintenance_margin:.2f} "
            f"(MarginRatio={margin_ratio * 100:.2f}%). Causa: {reason}"
        )
        if symbol:
            msg += f" en símbolo {symbol}"
        super().__init__(msg)


@dataclass(frozen=True)
class VolatilityTargetConfig:
    """Configuración del escalado dinámico por volatilidad objetivo (Target Volatility)."""

    target_annual_vol: float  # e.g., 0.15 = 15% volatilidad anualizada objetivo
    lookback_days: int = 30  # Ventana de cálculo rodante sin lookahead
    max_gross_leverage: float = 2.5  # Límite máximo de apalancamiento bruto permitido
    min_vol_floor: float = 0.05  # Piso mínimo de volatilidad para evitar división por cero
    annualization_factor: float = math.sqrt(365.0)  # Cripto opera 365 días al año

    def __post_init__(self) -> None:
        if self.target_annual_vol <= 0.0:
            raise ValueError(
                f"target_annual_vol debe ser positivo; se recibió {self.target_annual_vol}"
            )
        if self.lookback_days < 2:
            raise ValueError(f"lookback_days debe ser >= 2; se recibió {self.lookback_days}")
        if self.max_gross_leverage <= 0.0:
            raise ValueError(
                f"max_gross_leverage debe ser positivo; se recibió {self.max_gross_leverage}"
            )
        if self.min_vol_floor <= 0.0:
            raise ValueError(f"min_vol_floor debe ser positivo; se recibió {self.min_vol_floor}")


@dataclass(frozen=True)
class MarginTierConfig:
    """Tasa de margen de mantenimiento y penalizaciones de liquidación."""

    base_mmr: float = 0.005  # 0.5% base Maintenance Margin Rate para futuros USD-M
    liquidation_fee_rate: float = 0.015  # 1.5% tasa de liquidación forzosa en quiebra

    def __post_init__(self) -> None:
        if self.base_mmr <= 0.0:
            raise ValueError(f"base_mmr debe ser positivo; se recibió {self.base_mmr}")
        if self.liquidation_fee_rate < 0.0:
            raise ValueError(
                f"liquidation_fee_rate no puede ser negativo; "
                f"se recibió {self.liquidation_fee_rate}"
            )


@dataclass(frozen=True)
class DailyPortfolioSnapshot:
    """Instantánea diaria del estado de cuenta, márgenes, riesgos y costos."""

    open_time: int
    equity: float
    cash: float
    gross_notional: float
    net_notional: float
    gross_leverage: float
    net_leverage: float
    maintenance_margin: float
    margin_ratio: float
    liquidation_buffer: float
    daily_gross_pnl: float
    daily_fee: float
    daily_slippage: float
    daily_funding: float
    daily_net_pnl: float
    positions: dict[str, float] = field(default_factory=dict)


def compute_rolling_realized_vol(
    prices: pd.Series,
    lookback: int,
    min_floor: float = 0.05,
    annualization_factor: float = math.sqrt(365.0),
) -> float:
    """Calcula la volatilidad anualizada rodante de una serie de precios SIN lookahead.

    Usa únicamente retornos históricos hasta el momento actual.
    """
    valid = prices.dropna()
    if len(valid) < 2:
        return min_floor

    recent = valid.tail(lookback + 1)
    returns = recent.pct_change().dropna()
    if len(returns) < 2:
        return min_floor

    std_daily = float(returns.std(ddof=1))
    if math.isnan(std_daily) or std_daily <= 0.0:
        return min_floor

    annual_vol = std_daily * annualization_factor
    return max(annual_vol, min_floor)


class FuturesPortfolioSimulator:
    """Simulador institucional de carteras long/short en futuros perpetuos USDⓈ-M."""

    def __init__(
        self,
        initial_equity: float,
        cost_model: CostModel,
        *,
        vol_config: VolatilityTargetConfig | None = None,
        margin_config: MarginTierConfig | None = None,
        assert_liquidation: bool = True,
        check_intra_bar_liquidation: bool = True,
    ) -> None:
        if initial_equity <= 0.0:
            raise ValueError(f"initial_equity debe ser positivo; se recibió {initial_equity}")

        self.initial_equity = float(initial_equity)
        self.cost_model = cost_model
        self.vol_config = vol_config
        self.margin_config = margin_config or MarginTierConfig()
        self.assert_liquidation = assert_liquidation
        self.check_intra_bar_liquidation = check_intra_bar_liquidation

    def _scale_weights(
        self,
        raw_weights: dict[str, float],
        closes_history: pd.DataFrame,
    ) -> dict[str, float]:
        """Aplica volatility targeting e impone techo de apalancamiento bruto (leverage cap)."""
        if not self.vol_config or not raw_weights:
            return raw_weights

        # 1. Calcular volatilidad rodante de cada símbolo participante
        vols: dict[str, float] = {}
        for sym in raw_weights:
            if sym in closes_history.columns:
                series = closes_history[sym]
                vols[sym] = compute_rolling_realized_vol(
                    series,
                    self.vol_config.lookback_days,
                    min_floor=self.vol_config.min_vol_floor,
                    annualization_factor=self.vol_config.annualization_factor,
                )
            else:
                vols[sym] = self.vol_config.min_vol_floor

        # 2. Ponderación inversa por volatilidad: w_i = s_i / vol_i
        scaled_raw: dict[str, float] = {}
        for sym, s_val in raw_weights.items():
            if s_val == 0.0:
                continue
            v = max(vols[sym], self.vol_config.min_vol_floor)
            scaled_raw[sym] = s_val / v

        if not scaled_raw:
            return {}

        # 3. Estimación conservadora de la volatilidad compuesta de la cartera
        # (Aproximación de diversificación 1/sqrt(N) con factor de escala objetivo)
        sum_abs = sum(abs(w) for w in scaled_raw.values())
        if sum_abs <= 0.0:
            return {}

        n_assets = len(scaled_raw)
        # Factor de escala hacia target_annual_vol
        scale_target = self.vol_config.target_annual_vol * math.sqrt(n_assets)
        scaled_target = {sym: w * scale_target for sym, w in scaled_raw.items()}

        # 4. Imponer límite máximo de apalancamiento bruto (Gross Leverage Cap)
        target_gross = sum(abs(w) for w in scaled_target.values())
        if target_gross > self.vol_config.max_gross_leverage:
            clamp_factor = self.vol_config.max_gross_leverage / target_gross
            return {sym: w * clamp_factor for sym, w in scaled_target.items()}

        return scaled_target

    def run(
        self,
        signals_df: pd.DataFrame,
        closes_df: pd.DataFrame,
        *,
        opens_df: pd.DataFrame | None = None,
        highs_df: pd.DataFrame | None = None,
        lows_df: pd.DataFrame | None = None,
        volumes_df: pd.DataFrame | None = None,
        funding_dfs: Mapping[str, pd.DataFrame] | None = None,
        bar_interval_ms: int = 86_400_000,
    ) -> tuple[pd.DataFrame, CostDecomposition]:
        """Ejecuta la simulación de cartera día a día con rigor institucional."""
        if signals_df.empty or closes_df.empty:
            empty_decomp = CostDecomposition(0.0, 0.0, 0.0, 0.0, 0.0)
            return pd.DataFrame(), empty_decomp

        funding_dfs = funding_dfs or {}
        time_index = sorted(closes_df.index)

        current_equity = self.initial_equity
        current_cash = self.initial_equity
        current_positions: dict[str, float] = {}  # symbol -> quantity Q_i
        prev_closes: dict[str, float] = {}

        cumulative_gross_pnl = 0.0
        cumulative_fee_cost = 0.0
        cumulative_slippage_cost = 0.0
        cumulative_funding_pnl = 0.0

        snapshots: list[DailyPortfolioSnapshot] = []

        for idx, t in enumerate(time_index):
            open_time = int(t)
            prev_t = time_index[idx - 1] if idx > 0 else None

            daily_gross_pnl = 0.0
            daily_fee_cost = 0.0
            daily_slippage_cost = 0.0
            daily_funding_pnl = 0.0

            # ── A. Accrual de Funding sobre posiciones mantenidas desde t-1 ──
            if prev_t is not None and current_positions:
                start_ms = int(prev_t)
                end_ms = open_time
                for sym, qty in list(current_positions.items()):
                    if qty == 0.0 or sym not in funding_dfs:
                        continue
                    f_df = funding_dfs[sym]
                    if f_df.empty:
                        continue
                    mark_p = prev_closes.get(sym, 0.0)
                    if mark_p <= 0.0:
                        continue

                    f_cash, _ = accrue_funding_events(f_df, qty, mark_p, start_ms, end_ms)
                    daily_funding_pnl += f_cash

            current_cash += daily_funding_pnl
            current_equity += daily_funding_pnl
            cumulative_funding_pnl += daily_funding_pnl

            # ── B. Chequeo de Liquidación Intra-Barra (Mechas adversas Low/High) ──
            if (
                self.check_intra_bar_liquidation
                and prev_t is not None
                and current_positions
                and lows_df is not None
                and highs_df is not None
            ):
                worst_case_equity = current_equity
                worst_case_mm = 0.0

                for sym, qty in current_positions.items():
                    if qty == 0.0:
                        continue
                    p_prev = prev_closes.get(sym, 0.0)
                    if p_prev <= 0.0:
                        continue

                    if qty > 0:  # Long: el peor escenario intra-barra es el Low
                        p_worst = (
                            float(lows_df.loc[t, sym])
                            if sym in lows_df.columns and not pd.isna(lows_df.loc[t, sym])
                            else p_prev
                        )
                        worst_case_equity += qty * (p_worst - p_prev)
                        worst_case_mm += self.margin_config.base_mmr * (qty * p_worst)
                    else:  # Short: el peor escenario intra-barra es el High
                        p_worst = (
                            float(highs_df.loc[t, sym])
                            if sym in highs_df.columns and not pd.isna(highs_df.loc[t, sym])
                            else p_prev
                        )
                        worst_case_equity += qty * (p_worst - p_prev)
                        worst_case_mm += self.margin_config.base_mmr * (abs(qty) * p_worst)

                if worst_case_equity <= worst_case_mm:
                    margin_ratio = (
                        (worst_case_mm / worst_case_equity) if worst_case_equity > 0.0 else 999.0
                    )
                    if self.assert_liquidation:
                        raise AccountLiquidatedError(
                            open_time=open_time,
                            equity=worst_case_equity,
                            maintenance_margin=worst_case_mm,
                            margin_ratio=margin_ratio,
                            reason="Intra-bar adverse price excursion breached maintenance margin",
                        )
                    snapshots.append(
                        DailyPortfolioSnapshot(
                            open_time=open_time,
                            equity=0.0,
                            cash=0.0,
                            gross_notional=0.0,
                            net_notional=0.0,
                            gross_leverage=0.0,
                            net_leverage=0.0,
                            maintenance_margin=0.0,
                            margin_ratio=999.0,
                            liquidation_buffer=0.0,
                            daily_gross_pnl=daily_gross_pnl,
                            daily_fee=daily_fee_cost,
                            daily_slippage=daily_slippage_cost,
                            daily_funding=daily_funding_pnl,
                            daily_net_pnl=-current_equity,
                            positions={},
                        )
                    )
                    current_equity = 0.0
                    current_cash = 0.0
                    current_positions.clear()
                    break

            # ── C. Mark-to-Market Gross PnL frente al Close de la barra actual ──
            current_prices: dict[str, float] = {}
            for sym, qty in list(current_positions.items()):
                if qty == 0.0:
                    continue
                if sym in closes_df.columns and not pd.isna(closes_df.loc[t, sym]):
                    c_price = float(closes_df.loc[t, sym])
                    current_prices[sym] = c_price
                    p_prev = prev_closes.get(sym, c_price)
                    pnl_i = qty * (c_price - p_prev)
                    daily_gross_pnl += pnl_i
                else:
                    # ── D. Gestión de Delisteo: liquidación forzosa al último precio disponible ──
                    p_last = prev_closes.get(sym, 0.0)
                    if p_last > 0.0:
                        side = -1 if qty > 0 else 1
                        fill = self.cost_model.simulate_fill(
                            nominal_price=p_last,
                            qty=abs(qty),
                            side=side,
                            is_taker=True,
                        )
                        daily_fee_cost += fill.fee
                        daily_slippage_cost += fill.slippage_cost
                        current_cash -= fill.total_friction
                        current_equity -= fill.total_friction
                    del current_positions[sym]

            current_equity += daily_gross_pnl
            current_cash += daily_gross_pnl
            cumulative_gross_pnl += daily_gross_pnl

            # ── E. Chequeo de Liquidación al Cierre de Barra (End-of-Bar) ──
            gross_notional = sum(
                abs(q) * current_prices.get(s, prev_closes.get(s, 0.0))
                for s, q in current_positions.items()
            )
            maintenance_margin = self.margin_config.base_mmr * gross_notional
            margin_ratio = (
                (maintenance_margin / current_equity) if current_equity > 0.0 else 999.0
            )

            if current_equity <= maintenance_margin:
                if self.assert_liquidation:
                    raise AccountLiquidatedError(
                        open_time=open_time,
                        equity=current_equity,
                        maintenance_margin=maintenance_margin,
                        margin_ratio=margin_ratio,
                        reason="End-of-bar equity breached maintenance margin requirement",
                    )
                snapshots.append(
                    DailyPortfolioSnapshot(
                        open_time=open_time,
                        equity=0.0,
                        cash=0.0,
                        gross_notional=0.0,
                        net_notional=0.0,
                        gross_leverage=0.0,
                        net_leverage=0.0,
                        maintenance_margin=0.0,
                        margin_ratio=999.0,
                        liquidation_buffer=0.0,
                        daily_gross_pnl=daily_gross_pnl,
                        daily_fee=daily_fee_cost,
                        daily_slippage=daily_slippage_cost,
                        daily_funding=daily_funding_pnl,
                        daily_net_pnl=(
                            daily_gross_pnl
                            - daily_fee_cost
                            - daily_slippage_cost
                            + daily_funding_pnl
                        ),
                        positions={},
                    )
                )
                current_equity = 0.0
                current_cash = 0.0
                current_positions.clear()
                break

            # ── F. Rebalanceo y Ejecución para el período siguiente (t -> t+1) ──
            if t in signals_df.index:
                raw_signals = signals_df.loc[t].dropna().to_dict()
                # Filtrar únicamente símbolos que cotizan hoy y tienen precio válido
                eligible_signals = {
                    s: float(w)
                    for s, w in raw_signals.items()
                    if s in closes_df.columns and not pd.isna(closes_df.loc[t, s])
                }

                # Aplicar Volatility Targeting sobre closes hasta t (causal sin lookahead)
                scaled_weights = self._scale_weights(
                    eligible_signals, closes_df.loc[:t]
                )

                # Calcular cantidades objetivo basadas en equity actual
                target_positions: dict[str, float] = {}
                for sym, w in scaled_weights.items():
                    price = float(closes_df.loc[t, sym])
                    if price > 0.0:
                        target_notional_i = w * current_equity
                        target_positions[sym] = target_notional_i / price

                # Determinar todas las órdenes requeridas (cambios de posición o cierres)
                all_symbols = set(current_positions.keys()).union(target_positions.keys())
                for sym in all_symbols:
                    old_qty = current_positions.get(sym, 0.0)
                    new_qty = target_positions.get(sym, 0.0)
                    delta_qty = new_qty - old_qty

                    if abs(delta_qty) > 1e-8:
                        ref_price = (
                            float(opens_df.loc[t, sym])
                            if opens_df is not None
                            and sym in opens_df.columns
                            and not pd.isna(opens_df.loc[t, sym])
                            else float(closes_df.loc[t, sym])
                        )
                        side = 1 if delta_qty > 0 else -1
                        q_vol = (
                            float(volumes_df.loc[t, sym])
                            if volumes_df is not None
                            and sym in volumes_df.columns
                            and not pd.isna(volumes_df.loc[t, sym])
                            else 0.0
                        )

                        fill = self.cost_model.simulate_fill(
                            nominal_price=ref_price,
                            qty=abs(delta_qty),
                            side=side,
                            is_taker=True,
                            quote_volume=q_vol,
                        )

                        daily_fee_cost += fill.fee
                        daily_slippage_cost += fill.slippage_cost
                        friction = fill.total_friction

                        current_cash -= friction
                        current_equity -= friction

                        if abs(new_qty) > 1e-8:
                            current_positions[sym] = new_qty
                        elif sym in current_positions:
                            del current_positions[sym]

            cumulative_fee_cost += daily_fee_cost
            cumulative_slippage_cost += daily_slippage_cost
            daily_net_pnl = (
                daily_gross_pnl - daily_fee_cost - daily_slippage_cost + daily_funding_pnl
            )

            # Actualizar precios previos para el siguiente día
            for s in closes_df.columns:
                val = closes_df.loc[t, s]
                if not pd.isna(val):
                    prev_closes[s] = float(val)

            # ── G. Registro de Instantánea Diaria ──
            gross_notional_post = sum(
                abs(q) * prev_closes.get(s, 0.0) for s, q in current_positions.items()
            )
            net_notional_post = sum(
                q * prev_closes.get(s, 0.0) for s, q in current_positions.items()
            )
            gross_lev = (
                (gross_notional_post / current_equity) if current_equity > 0.0 else 0.0
            )
            net_lev = (
                (net_notional_post / current_equity) if current_equity > 0.0 else 0.0
            )
            mm_post = self.margin_config.base_mmr * gross_notional_post
            m_ratio_post = (mm_post / current_equity) if current_equity > 0.0 else 0.0
            liq_buffer = (
                max(0.0, (current_equity - mm_post) / current_equity)
                if current_equity > 0.0
                else 0.0
            )

            snapshots.append(
                DailyPortfolioSnapshot(
                    open_time=open_time,
                    equity=current_equity,
                    cash=current_cash,
                    gross_notional=gross_notional_post,
                    net_notional=net_notional_post,
                    gross_leverage=gross_lev,
                    net_leverage=net_lev,
                    maintenance_margin=mm_post,
                    margin_ratio=m_ratio_post,
                    liquidation_buffer=liq_buffer,
                    daily_gross_pnl=daily_gross_pnl,
                    daily_fee=daily_fee_cost,
                    daily_slippage=daily_slippage_cost,
                    daily_funding=daily_funding_pnl,
                    daily_net_pnl=daily_net_pnl,
                    positions=dict(current_positions),
                )
            )

        history_df = pd.DataFrame([s.__dict__ for s in snapshots]).set_index("open_time")
        net_total_pnl = (
            cumulative_gross_pnl
            - cumulative_fee_cost
            - cumulative_slippage_cost
            + cumulative_funding_pnl
        )
        decomp = CostDecomposition(
            gross_pnl=cumulative_gross_pnl,
            fee_cost=cumulative_fee_cost,
            slippage_cost=cumulative_slippage_cost,
            funding_pnl=cumulative_funding_pnl,
            net_pnl=net_total_pnl,
        )

        return history_df, decomp
