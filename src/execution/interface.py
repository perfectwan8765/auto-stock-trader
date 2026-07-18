"""리밸런싱 로직이 의존하는 브로커 인터페이스·데이터 모델 (브로커 비의존)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OrderIntent:
    """발주 의도(계획). dry-run은 이 리스트만 만들고 실발주는 broker.place로."""

    symbol: str
    side: str            # "BUY" | "SELL"
    kind: str            # "amount"(USD, 매수) | "quantity"(주식수, 매도)
    value: float         # 매수=USD 금액, 매도=주식수
    client_order_id: str  # 결정적 멱등키(개선5)
    reason: str          # "exit" | "trim" | "enter" | "add"


@dataclass(frozen=True)
class RebalanceParams:
    total_equity_usd: float   # 총 평가액(목표 비중 → 금액 환산 기준)
    buying_power_usd: float   # 가용 USD(개선1: 매수는 이 한도 내에서만)
    min_order_usd: float      # 최소 주문금액(개선8, Phase 0 실측 전 placeholder)
    rebalance_date: str       # YYYYMMDD, 멱등키 재현용


@dataclass(frozen=True)
class RebalancePlan:
    """리밸런싱 산출물. orders는 실행 순서(매도先→매수, 개선1). skipped는 사유 기록."""

    orders: list[OrderIntent]
    skipped: list[tuple[str, str]]  # (symbol, reason): below_min_order | insufficient_buying_power | partial_insufficient_buying_power


class Broker(Protocol):
    """리밸런싱이 요구하는 브로커 능력. src/toss가 구체 구현(TossBroker)."""

    def get_holdings(self) -> dict[str, float]: ...          # symbol -> 보유 주식수
    def get_prices(self, symbols: list[str]) -> dict[str, float]: ...
    def get_buying_power_usd(self) -> float: ...
    def is_market_open(self) -> bool: ...
    def place(self, intent: OrderIntent) -> dict: ...        # 실발주(멱등키 포함)
