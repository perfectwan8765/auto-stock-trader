"""리밸런싱 실행 오케스트레이션 (브로커 비의존).

흐름: 브로커 상태 스냅샷(보유·가격·가용) → compute_rebalance → dry-run(계획만) 또는
실발주(안전장치 통과 후). 브로커는 주입(TossBroker 실전 / MockBroker 테스트).
개선4(kill switch·서킷브레이커)·개선6(정규장 확인 후 발주).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .interface import Broker, RebalanceParams, RebalancePlan
from .rebalance import compute_rebalance
from .safety import CircuitBreaker, check_kill_switch


@dataclass
class RunResult:
    plan: RebalancePlan
    dry_run: bool
    placed: list[str] = field(default_factory=list)  # 발주된 clientOrderId
    aborted_reason: str | None = None                # 예: "market_closed"


class RebalanceRunner:
    def __init__(
        self,
        broker: Broker,
        min_order_usd: float,
        kill_switch_path: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.broker = broker
        self.min_order_usd = min_order_usd
        self.kill_switch_path = kill_switch_path
        self.cb = circuit_breaker

    def _build_plan(self, target_weights: dict[str, float], rebalance_date: str) -> RebalancePlan:
        holdings = self.broker.get_holdings()
        symbols = sorted(set(target_weights) | set(holdings))
        prices = self.broker.get_prices(symbols)
        buying_power = self.broker.get_buying_power_usd()
        held_value = sum(holdings.get(s, 0.0) * prices.get(s, 0.0) for s in holdings)
        total_equity = held_value + buying_power  # 평가액 = 보유 + 가용현금
        params = RebalanceParams(
            total_equity_usd=total_equity,
            buying_power_usd=buying_power,   # 개선1: 매수는 가용 USD 한도
            min_order_usd=self.min_order_usd,
            rebalance_date=rebalance_date,
        )
        return compute_rebalance(target_weights, holdings, prices, params)

    def run(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool = True) -> RunResult:
        plan = self._build_plan(target_weights, rebalance_date)
        if dry_run:
            return RunResult(plan=plan, dry_run=True)

        # --- 실발주: 안전장치 ---
        if self.kill_switch_path:
            check_kill_switch(self.kill_switch_path)     # KillSwitchActive
        if not self.broker.is_market_open():             # 개선6: 정규장 확인 후만
            return RunResult(plan=plan, dry_run=False, aborted_reason="market_closed")

        placed: list[str] = []
        for order in plan.orders:  # 매도先→매수 순서(compute_rebalance 보장)
            if self.cb is not None:
                self.cb.guard()                          # CircuitBreakerTripped
            self.broker.place(order)                     # 멱등키 포함
            placed.append(order.client_order_id)
            if self.cb is not None:
                self.cb.record_order()
        return RunResult(plan=plan, dry_run=False, placed=placed)
