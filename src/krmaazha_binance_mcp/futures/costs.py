"""Modelo de costos para futuros USDⓈ-M (spec Phase 0, ROADMAP.md).

Honesto por diseño y sin trampas:
1. **Comisión obligatoria sin default silencioso:** Binance USD-M tiene comisiones maker/taker
   según nivel VIP. No existe un default universal: exigir `taker_fee` y `maker_fee`
   explícitamente evita que un backtest asuma comisiones cero o el nivel VIP de otra cuenta.
2. **Accrual real de funding:** El funding no es una constante del 0.01% cada 8 horas.
   Binance ajusta dinámicamente `funding_interval_hours` (8h, 4h, 2h, 1h) en momentos de alta
   volatilidad. El devengo debe respetar los timestamps reales (`calc_time`) y las tasas
   históricas (`last_funding_rate`) del archivo público.
3. **Slippage que NUNCA es cero:** Ningún trade real se llena al precio exacto del open.
   Un slippage nulo en el backtest genera bordes ilusorios en activos de baja liquidez o
   estrategias de alta rotación. Se impone `slippage > 0` tanto en piso fijo como en impacto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class FeeModel:
    """Modelo de comisiones de exchange.
    
    Sin defaults: ambos parámetros deben pasarse explícitamente.
    """

    taker_fee: float
    maker_fee: float

    def __post_init__(self) -> None:
        if self.taker_fee < 0.0 or self.maker_fee < 0.0:
            raise ValueError(
                f"Las comisiones no pueden ser negativas: "
                f"taker={self.taker_fee}, maker={self.maker_fee}"
            )
        if self.taker_fee == 0.0 and self.maker_fee == 0.0:
            raise ValueError(
                "Comisión cero prohibida; la ejecución en futuros siempre incurre en comisiones."
            )

    def calculate_fee(self, notional: float, *, is_taker: bool = True) -> float:
        """Calcula el costo monetario de la comisión sobre el notional de la orden."""
        rate = self.taker_fee if is_taker else self.maker_fee
        return abs(notional) * rate


@runtime_checkable
class SlippageModel(Protocol):
    """Protocolo de slippage: el deslizamiento de precio siempre es estrictamente positivo (> 0)."""

    def calculate_effective_price(
        self,
        nominal_price: float,
        side: int,
        *,
        notional: float = 0.0,
        quote_volume: float = 0.0,
    ) -> float:
        """Devuelve el precio efectivo de ejecución ajustado adversamente por slippage.

        `side`: +1 para COMPRA (el precio sube), -1 para VENTA (el precio baja).
        """
        ...

    def calculate_slippage_cost(
        self,
        nominal_price: float,
        side: int,
        qty: float,
        *,
        quote_volume: float = 0.0,
    ) -> float:
        """Calcula la pérdida monetaria debida al slippage (|efectivo - nominal| * qty)."""
        ...


@dataclass(frozen=True)
class FixedBasisPointSlippage:
    """Slippage fijo en puntos básicos (bps), donde 1 bps = 0.0001 (0.01%).
    
    `bps` debe ser estrictamente > 0.
    """

    bps: float

    def __post_init__(self) -> None:
        if self.bps <= 0.0:
            raise ValueError(
                f"El slippage debe ser estrictamente positivo (> 0); se recibió {self.bps} bps."
            )

    def calculate_effective_price(
        self,
        nominal_price: float,
        side: int,
        *,
        notional: float = 0.0,
        quote_volume: float = 0.0,
    ) -> float:
        if nominal_price <= 0.0:
            raise ValueError(f"El precio nominal debe ser positivo: {nominal_price}")
        if side not in (1, -1):
            raise ValueError(f"side debe ser +1 (buy) o -1 (sell); se recibió {side}")

        penalty_fraction = self.bps * 1e-4
        if side > 0:
            return nominal_price * (1.0 + penalty_fraction)
        return nominal_price * (1.0 - penalty_fraction)

    def calculate_slippage_cost(
        self,
        nominal_price: float,
        side: int,
        qty: float,
        *,
        quote_volume: float = 0.0,
    ) -> float:
        eff_price = self.calculate_effective_price(
            nominal_price, side, notional=nominal_price * abs(qty), quote_volume=quote_volume
        )
        return abs(eff_price - nominal_price) * abs(qty)


@dataclass(frozen=True)
class VolumeImpactSlippage:
    """Modelo de impacto de mercado no lineal con piso obligatorio de medio spread.
    
    `floor_bps` es el slippage mínimo ineludible (> 0 bps) incluso para órdenes infinitesimales.
    `impact_factor` pondera la relación entre el notional de la orden y el volumen de la barra.
    """

    floor_bps: float
    impact_factor: float
    power: float = 0.5  # Ley de raíz cuadrada por defecto

    def __post_init__(self) -> None:
        if self.floor_bps <= 0.0:
            raise ValueError(
                f"El piso de slippage (floor_bps) debe ser estrictamente positivo (> 0); "
                f"se recibió {self.floor_bps} bps."
            )
        if self.impact_factor < 0.0:
            raise ValueError(
                f"impact_factor no puede ser negativo; se recibió {self.impact_factor}"
            )
        if self.power <= 0.0:
            raise ValueError(f"power debe ser positivo; se recibió {self.power}")

    def effective_bps(self, notional: float, quote_volume: float) -> float:
        """Calcula los puntos básicos efectivos sumando el piso y el impacto de participación."""
        notional_abs = abs(notional)
        if quote_volume > 0.0 and notional_abs > 0.0:
            participation = notional_abs / quote_volume
            impact_bps = self.impact_factor * (participation**self.power) * 10_000.0
            return float(self.floor_bps + impact_bps)
        return float(self.floor_bps)

    def calculate_effective_price(
        self,
        nominal_price: float,
        side: int,
        *,
        notional: float = 0.0,
        quote_volume: float = 0.0,
    ) -> float:
        if nominal_price <= 0.0:
            raise ValueError(f"El precio nominal debe ser positivo: {nominal_price}")
        if side not in (1, -1):
            raise ValueError(f"side debe ser +1 (buy) o -1 (sell); se recibió {side}")

        eff_bps = self.effective_bps(notional, quote_volume)
        penalty_fraction = eff_bps * 1e-4
        if side > 0:
            return nominal_price * (1.0 + penalty_fraction)
        return nominal_price * (1.0 - penalty_fraction)

    def calculate_slippage_cost(
        self,
        nominal_price: float,
        side: int,
        qty: float,
        *,
        quote_volume: float = 0.0,
    ) -> float:
        eff_price = self.calculate_effective_price(
            nominal_price, side, notional=nominal_price * abs(qty), quote_volume=quote_volume
        )
        return abs(eff_price - nominal_price) * abs(qty)


@dataclass(frozen=True)
class ExecutionFill:
    """Resultado de la ejecución simulada de una orden con comisiones y slippage desglosados."""

    nominal_price: float
    effective_price: float
    qty: float
    side: int
    notional: float
    fee: float
    slippage_cost: float
    total_friction: float


@dataclass(frozen=True)
class FundingEvent:
    """Evento individual de liquidación de funding."""

    calc_time: int
    funding_interval_hours: float
    rate: float
    position_qty: float
    mark_price: float
    cash_flow: float  # Negativo = pago; Positivo = cobro/ingreso


@dataclass(frozen=True)
class CostDecomposition:
    """Desglose completo de costos y retornos para la tabla live_vs_model."""

    gross_pnl: float
    fee_cost: float
    slippage_cost: float
    funding_pnl: float  # Positivo si recibió funding, negativo si pagó
    net_pnl: float

    @property
    def total_drag(self) -> float:
        """Pérdida total por fricciones operativas (comisión + slippage - funding_recibido)."""
        return self.fee_cost + self.slippage_cost - self.funding_pnl


@dataclass(frozen=True)
class CostModel:
    """Modelo integrado de costos de negociación en futuros USDⓈ-M.
    
    Sin parámetros por default: obliga a definir explícitamente fee y slippage.
    """

    fee_model: FeeModel
    slippage_model: SlippageModel

    def simulate_fill(
        self,
        nominal_price: float,
        qty: float,
        side: int,
        *,
        is_taker: bool = True,
        quote_volume: float = 0.0,
    ) -> ExecutionFill:
        """Simula el llenado de una orden aplicando slippage adverso y comisiones."""
        qty_abs = abs(qty)
        nominal_notional = nominal_price * qty_abs
        effective_price = self.slippage_model.calculate_effective_price(
            nominal_price, side, notional=nominal_notional, quote_volume=quote_volume
        )
        effective_notional = effective_price * qty_abs
        slippage_cost = abs(effective_price - nominal_price) * qty_abs
        fee = self.fee_model.calculate_fee(effective_notional, is_taker=is_taker)
        total_friction = fee + slippage_cost

        return ExecutionFill(
            nominal_price=nominal_price,
            effective_price=effective_price,
            qty=qty_abs,
            side=side,
            notional=effective_notional,
            fee=fee,
            slippage_cost=slippage_cost,
            total_friction=total_friction,
        )


# ── Accrual de Funding ────────────────────────────────────────────────────────


def calculate_funding_cash_flow(
    position_qty: float,
    mark_price: float,
    funding_rate: float,
) -> float:
    """Calcula el flujo de caja de una liquidación de funding.
    
    Convención de futuros perpétuos:
    - Long (position_qty > 0): paga cuando funding_rate > 0 (flujo negativo).
    - Long (position_qty > 0): cobra cuando funding_rate < 0 (flujo positivo).
    - Short (position_qty < 0): cobra cuando funding_rate > 0 (flujo positivo).
    - Short (position_qty < 0): paga cuando funding_rate < 0 (flujo negativo).
    
    Fórmula unificada: cash_flow = - position_qty * mark_price * funding_rate
    """
    return -position_qty * mark_price * funding_rate


def accrue_funding_events(
    funding_df: pd.DataFrame,
    position_qty: float,
    mark_price: float,
    start_time_ms: int,
    end_time_ms: int,
) -> tuple[float, list[FundingEvent]]:
    """Calcula el flujo total de funding y lista de eventos entre dos timestamps."""
    if funding_df.empty or position_qty == 0.0:
        return 0.0, []

    # Filtrar eventos que caen dentro del período de tenencia [start_time_ms, end_time_ms)
    mask = (funding_df["calc_time"] >= start_time_ms) & (funding_df["calc_time"] < end_time_ms)
    events_in_range = funding_df[mask]

    total_cash_flow = 0.0
    events: list[FundingEvent] = []

    for _, row in events_in_range.iterrows():
        calc_time = int(row["calc_time"])
        interval = float(row["funding_interval_hours"])
        rate = float(row["last_funding_rate"])
        flow = calculate_funding_cash_flow(position_qty, mark_price, rate)
        total_cash_flow += flow
        events.append(
            FundingEvent(
                calc_time=calc_time,
                funding_interval_hours=interval,
                rate=rate,
                position_qty=position_qty,
                mark_price=mark_price,
                cash_flow=flow,
            )
        )

    return total_cash_flow, events


def accrue_funding_panel(
    positions_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    funding_dfs: dict[str, pd.DataFrame],
    *,
    bar_interval_ms: int = 86_400_000,
) -> pd.DataFrame:
    """Calcula la matriz de flujo de caja de funding (fechas x símbolos).
    
    Alinea cada liquidación histórica de funding con el período de la barra
    `[open_time, open_time + bar_interval_ms)`.
    """
    if positions_df.empty or prices_df.empty:
        return pd.DataFrame()

    aligned_pnl = pd.DataFrame(0.0, index=positions_df.index, columns=positions_df.columns)

    for symbol in positions_df.columns:
        if symbol not in funding_dfs or funding_dfs[symbol].empty:
            continue
        if symbol not in prices_df.columns:
            continue

        f_df = funding_dfs[symbol]
        pos_series = positions_df[symbol]
        price_series = prices_df[symbol]

        for open_time in positions_df.index:
            qty = pos_series.loc[open_time]
            if pd.isna(qty) or qty == 0.0:
                continue
            price = price_series.loc[open_time]
            if pd.isna(price) or price <= 0.0:
                continue

            start_ms = int(open_time)
            end_ms = start_ms + bar_interval_ms
            flow, _ = accrue_funding_events(f_df, float(qty), float(price), start_ms, end_ms)
            aligned_pnl.loc[open_time, symbol] = flow

    return aligned_pnl


def accrue_funding_returns_panel(
    weights_df: pd.DataFrame,
    funding_dfs: dict[str, pd.DataFrame],
    *,
    bar_interval_ms: int = 86_400_000,
) -> pd.DataFrame:
    """Calcula el rendimiento porcentual (drag o yield) generado por funding en carteras ponderadas.
    
    Para una posición con peso W_s:
    Return_funding = - W_s * sum(funding_rates_en_la_barra)
    """
    if weights_df.empty:
        return pd.DataFrame()

    returns_df = pd.DataFrame(0.0, index=weights_df.index, columns=weights_df.columns)

    for symbol in weights_df.columns:
        if symbol not in funding_dfs or funding_dfs[symbol].empty:
            continue

        f_df = funding_dfs[symbol]
        w_series = weights_df[symbol]

        for open_time in weights_df.index:
            w = w_series.loc[open_time]
            if pd.isna(w) or w == 0.0:
                continue

            start_ms = int(open_time)
            end_ms = start_ms + bar_interval_ms
            mask = (f_df["calc_time"] >= start_ms) & (f_df["calc_time"] < end_ms)
            rates = f_df.loc[mask, "last_funding_rate"]
            if not rates.empty:
                sum_rates = float(rates.sum())
                # Si long (w > 0) y sum_rates > 0, el rendimiento es negativo
                returns_df.loc[open_time, symbol] = -float(w) * sum_rates

    return returns_df


def compute_turnover_friction(
    delta_weights_df: pd.DataFrame,
    cost_model: CostModel,
    volumes_df: pd.DataFrame | None = None,
    portfolio_equity: float = 1_000_000.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula el arrastre monetario de comisión y slippage ante rebalanceos de peso.

    `delta_weights_df`: cambio absoluto en pesos |W_t - W_{t-1}|.
    Devuelve (fee_drag_df, slippage_drag_df).
    """
    if delta_weights_df.empty:
        empty = pd.DataFrame()
        return empty, empty

    fee_df = pd.DataFrame(0.0, index=delta_weights_df.index, columns=delta_weights_df.columns)
    slippage_df = pd.DataFrame(0.0, index=delta_weights_df.index, columns=delta_weights_df.columns)

    for symbol in delta_weights_df.columns:
        delta_w = delta_weights_df[symbol]
        for t in delta_weights_df.index:
            dw = delta_w.loc[t]
            if pd.isna(dw) or dw <= 0.0:
                continue

            notional = float(dw) * portfolio_equity
            fee = cost_model.fee_model.calculate_fee(notional, is_taker=True)
            fee_df.loc[t, symbol] = fee

            quote_vol = 0.0
            if volumes_df is not None and symbol in volumes_df.columns:
                v = volumes_df.loc[t, symbol]
                if not pd.isna(v):
                    quote_vol = float(v)

            # Para turnover, el costo de slippage se aproxima sobre el notional transaccionado
            if isinstance(cost_model.slippage_model, FixedBasisPointSlippage):
                bps = cost_model.slippage_model.bps
            elif isinstance(cost_model.slippage_model, VolumeImpactSlippage):
                bps = cost_model.slippage_model.effective_bps(notional, quote_vol)
            else:
                bps = 1.0  # Fallback si se usa un protocolo custom

            slippage_cost = notional * (bps * 1e-4)
            slippage_df.loc[t, symbol] = slippage_cost

    return fee_df, slippage_df
