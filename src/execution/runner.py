"""리밸런싱 실행 오케스트레이션 (브로커 비의존).

흐름: 브로커 상태 스냅샷 → (화이트리스트 필터) → compute_rebalance → 매도 sellable 상한(B) →
dry-run(계획만) 또는 실발주(안전장치 통과 후). 브로커는 주입(TossBroker 실전 / MockBroker 테스트).

화이트리스트(managed.ManagedState): 봇은 관리셋 M 종목만 매매하고, 제외셋 X(사용자 수동
보유)는 건드리지 않는다. 예산 상한(budget_usd)으로 계좌 공유 현금 과지출도 막는다.
개선4(kill switch·서킷브레이커)·개선6(정규장 확인 후 발주).

실발주 루프 하드닝(D): 주문 간 sleep(rate-limit), rate-limit-exceeded 백오프 재시도,
장마감/개별거부 에러코드별 처리. 손실상한(C): 봇 관리분 당일손익을 서킷브레이커에 배선.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace

from .errors import ExecutionError
from .interface import Broker, OrderIntent, RebalanceParams, RebalancePlan
from .managed import ManagedState
from .rebalance import compute_rebalance
from .safety import CircuitBreaker, check_kill_switch

# 토스 에러코드(문자열)로 처리 분기. execution↔toss 레이어 분리를 위해 예외 타입 대신
# 덕타이핑(getattr(e,"code"))으로 코드만 읽는다(개선10: toss.errors import 회피).
_RATE_LIMIT_CODES = {"rate-limit-exceeded"}
_MARKET_CLOSED_CODES = {"amount-order-outside-regular-hours", "order-hours-closed"}
_PER_ORDER_SKIP_CODES = {"insufficient-buying-power", "market-not-supported-for-stock"}


def _error_code(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    return code if isinstance(code, str) else ""


@dataclass
class RunResult:
    plan: RebalancePlan
    dry_run: bool
    placed: list[str] = field(default_factory=list)          # 발주된 clientOrderId
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (symbol, error_code) 개별 거부
    aborted_reason: str | None = None                        # 예: "market_closed"


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
        order_sleep_s: float = 1.0,       # 주문 간 간격(ACCOUNT 1 TPS 보수적; ORDER는 0-7 실측 전)
        rate_limit_retries: int = 3,      # rate-limit-exceeded 재시도 상한
        rate_limit_backoff_s: float = 2.0,
    ):
        self.broker = broker
        self.min_order_usd = min_order_usd
        self.budget_usd = budget_usd
        self.state = managed_state if managed_state is not None else ManagedState(path=None)
        self.kill_switch_path = kill_switch_path
        self.cb = circuit_breaker
        self.log_dir = log_dir  # 설정 시 실발주 결과를 execution_logs로 영속화(대시보드 소스)
        self.order_sleep_s = order_sleep_s
        self.rate_limit_retries = rate_limit_retries
        self.rate_limit_backoff_s = rate_limit_backoff_s

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
        plan = self._clamp_sells_to_sellable(plan)  # B: T+N 미결제분 초과매도 방지
        if excluded_targets:  # frozen plan 직접 mutate 대신 재구성(F3)
            plan = RebalancePlan(
                orders=plan.orders,
                skipped=plan.skipped + [(s, "excluded_manual") for s in excluded_targets],
            )
        return plan

    def _clamp_sells_to_sellable(self, plan: RebalancePlan) -> RebalancePlan:
        """매도 수량을 매도가능수량(sellable)으로 상한. T+N 미결제분이 있으면 보유수량 >
        sellable → 초과매도가 거부(리밸 붕괴)되므로, sellable로 줄이거나(부분매도) 0이면 스킵."""
        new_orders: list[OrderIntent] = []
        extra_skips: list[tuple[str, str]] = []
        for o in plan.orders:
            if o.side == "SELL" and o.kind == "quantity":
                sellable = self.broker.get_sellable_quantity(o.symbol)
                if sellable <= 0:
                    extra_skips.append((o.symbol, "not_sellable_settlement"))
                    continue
                if sellable < o.value:
                    # 반드시 sellable 이하로 내림(math.floor). round()는 뱅커스 라운딩으로
                    # 올림될 수 있어 초과매도 거부 위험 → 8자리 내림으로 상한 보장.
                    clamped = math.floor(sellable * 1e8) / 1e8
                    if clamped <= 0:
                        extra_skips.append((o.symbol, "not_sellable_settlement"))
                        continue
                    o = replace(o, value=clamped)  # 부분매도(잔량 다음 사이클)
                    extra_skips.append((o.symbol, "sell_clamped_to_sellable"))
            new_orders.append(o)
        return RebalancePlan(orders=new_orders, skipped=plan.skipped + extra_skips)

    def _place_order(self, order: OrderIntent) -> tuple[str, str | None]:
        """단건 발주. rate-limit은 백오프 재시도, 장마감/개별거부는 코드로 분류 반환.
        반환: ("placed", None) | ("skip", code) | ("abort", code). 알 수 없는 오류는 재-raise."""
        attempts = 0
        while True:
            try:
                self.broker.place(order)
                return ("placed", None)
            except Exception as exc:  # noqa: BLE001 — 아래서 코드 미해당이면 재-raise
                code = _error_code(exc)
                if code in _RATE_LIMIT_CODES and attempts < self.rate_limit_retries:
                    attempts += 1
                    time.sleep(self.rate_limit_backoff_s * attempts)  # 선형 백오프
                    continue
                if code in _MARKET_CLOSED_CODES:
                    return ("abort", code)
                if code in _PER_ORDER_SKIP_CODES:
                    return ("skip", code)
                raise  # 미분류(버그·미지의 코드) → 안전하게 상위로 전파(중단)

    def run(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool = True) -> RunResult:
        plan = self._build_plan(target_weights, rebalance_date, dry_run)
        if dry_run:
            return RunResult(plan=plan, dry_run=True)

        # --- 실발주: 안전장치 ---
        if self.kill_switch_path:
            check_kill_switch(self.kill_switch_path)
        if not self.broker.is_market_open():             # 개선6: 정규장 확인 후만
            return RunResult(plan=plan, dry_run=False, aborted_reason="market_closed")

        # C: 봇 관리분(M) 당일손익을 손실상한에 배선. 손실이면 서킷브레이커에 시드 →
        # 첫 guard()에서 상한 초과 시 트립(주문 0건). 사용자 수동 보유(X)는 제외.
        if self.cb is not None and self.state.managed:
            daily = self.broker.get_daily_pnl_usd(self.state.managed)
            if daily < 0:
                self.cb.record_loss(-daily)

        placed: list[str] = []
        rejected: list[tuple[str, str]] = []
        aborted_reason: str | None = None
        # try/finally: guard()가 루프 중간에 트립(주문건수·손실 상한)해도 이미 발주된
        # 주문을 M에 반영·영속해 상태 불일치(재실행 시 봇 매수분을 미관리로 오인)를 막는다.
        try:
            for i, order in enumerate(plan.orders):  # 매도先→매수 순서(compute_rebalance 보장)
                if self.cb is not None:
                    self.cb.guard()
                if i > 0 and self.order_sleep_s > 0:
                    time.sleep(self.order_sleep_s)   # rate-limit 준수(호출 간 간격)
                outcome, code = self._place_order(order)
                if outcome == "placed":
                    placed.append(order.client_order_id)
                    if self.cb is not None:
                        self.cb.record_order()
                elif outcome == "skip":
                    rejected.append((order.symbol, code or ""))
                else:  # abort (장마감 등) → 잔여 주문 중단
                    aborted_reason = f"aborted_midrun:{code}"
                    break
        finally:
            self.state.update_after_place(plan.orders, placed)  # M 갱신(실발주분만)
            self.state.save()

        result = RunResult(plan=plan, dry_run=False, placed=placed,
                           rejected=rejected, aborted_reason=aborted_reason)
        if self.log_dir:
            from pathlib import Path

            from .orderlog import write_order_log  # lazy: orderlog ↔ runner 순환 import 회피
            write_order_log(result, rebalance_date, Path(self.log_dir))
        return result
