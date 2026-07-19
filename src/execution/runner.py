"""리밸런싱 실행 오케스트레이션 (브로커 비의존).

흐름: 브로커 상태 스냅샷 → (화이트리스트 필터) → compute_rebalance → dry-run(계획만) 또는
실발주(안전장치 통과 후). 브로커는 주입(TossBroker 실전 / MockBroker 테스트).

화이트리스트(managed.ManagedState): 봇은 관리셋 M 종목만 매매하고, 제외셋 X(사용자 수동
보유)는 건드리지 않는다. 예산 상한(budget_usd)으로 계좌 공유 현금 과지출도 막는다.
개선4(kill switch·서킷브레이커)·개선6(정규장 확인 후 발주).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ExecutionError
from .interface import Broker, RebalanceParams, RebalancePlan
from .managed import ManagedState
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
        budget_usd: float | None = None,
        managed_state: ManagedState | None = None,
        kill_switch_path: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        log_dir: str | None = None,
    ):
        self.broker = broker
        self.min_order_usd = min_order_usd
        self.budget_usd = budget_usd
        self.state = managed_state if managed_state is not None else ManagedState(path=None)
        self.kill_switch_path = kill_switch_path
        self.cb = circuit_breaker
        self.log_dir = log_dir  # 설정 시 실발주 결과를 execution_logs로 영속화(대시보드 소스)

    def _build_plan(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool) -> RebalancePlan:
        holdings = self.broker.get_holdings()

        # 제외셋 X·관리셋 M 결정. dry-run은 state를 절대 변경하지 않는다(read-only) —
        # dry-run이 bootstrapped 플래그를 오염시켜 이후 라이브 보호가 무력화되는 걸 방지(F1).
        if self.state.bootstrapped:
            excluded, managed = self.state.excluded, self.state.managed
        else:
            excluded = {s for s, q in holdings.items() if q > 0}  # 현재 보유가 곧 X
            managed = set()
            if not dry_run:  # 실발주에서만 X 확정·영속
                self.state.bootstrap(holdings)
                self.state.save()

        # 목표에서 X 제거(봇은 사용자 수동 보유 종목을 담지 않음)
        excluded_targets = [s for s in target_weights if s in excluded]
        target = {s: w for s, w in target_weights.items() if s not in excluded}

        # 봇이 관리하는 보유만 리밸 대상 → X 종목은 매도·trim에서 원천 제외
        bot_holdings = {s: q for s, q in holdings.items() if s in managed}

        symbols = sorted(set(target) | set(bot_holdings))
        prices = self.broker.get_prices(symbols)

        # 보유 종목 가격 누락 시 예산 계산이 왜곡돼 과지출 위험 → 안전 중단(F2)
        missing = [s for s in bot_holdings if prices.get(s, 0.0) <= 0]
        if missing:
            raise ExecutionError(f"보유 종목 가격 누락 → 예산 계산 불가(안전 중단): {missing}")

        account_bp = self.broker.get_buying_power_usd()
        bot_value = sum(bot_holdings[s] * prices[s] for s in bot_holdings)

        if self.budget_usd is None:  # 예산 미설정: 봇 보유 + 계좌현금 전체(구 동작)
            total_equity, buying_power = bot_value + account_bp, account_bp
        else:                        # 예산 상한: 목표 규모=budget, 매수는 남은 예산·계좌현금 내
            total_equity = self.budget_usd
            buying_power = max(0.0, min(account_bp, self.budget_usd - bot_value))

        params = RebalanceParams(total_equity, buying_power, self.min_order_usd, rebalance_date)
        plan = compute_rebalance(target, bot_holdings, prices, params)
        if excluded_targets:  # frozen plan 직접 mutate 대신 재구성(F3)
            plan = RebalancePlan(
                orders=plan.orders,
                skipped=plan.skipped + [(s, "excluded_manual") for s in excluded_targets],
            )
        return plan

    def run(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool = True) -> RunResult:
        plan = self._build_plan(target_weights, rebalance_date, dry_run)
        if dry_run:
            return RunResult(plan=plan, dry_run=True)

        # --- 실발주: 안전장치 ---
        if self.kill_switch_path:
            check_kill_switch(self.kill_switch_path)
        if not self.broker.is_market_open():             # 개선6: 정규장 확인 후만
            return RunResult(plan=plan, dry_run=False, aborted_reason="market_closed")

        placed: list[str] = []
        for order in plan.orders:  # 매도先→매수 순서(compute_rebalance 보장)
            if self.cb is not None:
                self.cb.guard()
            self.broker.place(order)
            placed.append(order.client_order_id)
            if self.cb is not None:
                self.cb.record_order()

        self.state.update_after_place(plan.orders, placed)  # M 갱신(실발주분만)
        self.state.save()

        result = RunResult(plan=plan, dry_run=False, placed=placed)
        if self.log_dir:
            from pathlib import Path

            from .orderlog import write_order_log  # lazy: orderlog ↔ runner 순환 import 회피
            write_order_log(result, rebalance_date, Path(self.log_dir))
        return result
