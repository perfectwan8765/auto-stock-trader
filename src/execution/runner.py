"""리밸런싱 실행 오케스트레이션 (브로커 비의존).

흐름: 계좌 스냅샷 → 화이트리스트 필터 → compute_rebalance → 매도 sellable 상한 →
dry-run(계획만) 또는 실발주(안전장치 통과 후). 브로커는 주입한다.

화이트리스트(managed.ManagedState): 봇은 관리셋 M 종목만 매매하고, 제외셋 X(사용자 수동
보유)는 건드리지 않는다. 예산 상한으로 계좌 공유 현금 과지출도 막는다.

안전장치: kill switch · 서킷브레이커 · 정규장 확인 후 발주. 발주 루프는 주문 간 간격을
두고 속도제한은 백오프 재시도한다. 장마감·개별거부는 정규화된 예외 타입으로 분기한다 —
브로커 코드 문자열의 번역은 어댑터 책임이다.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from dataclasses import asdict, replace

from .errors import (
    BrokerMarketClosed,
    BrokerRateLimited,
    ExecutionError,
    OrderRejected,
)
from .interface import (
    AccountSnapshot,
    Broker,
    OrderIntent,
    RebalanceParams,
    RebalancePlan,
    RunnerPolicy,
    RunResult,
)
from .managed import ManagedState
from .orderlog import write_order_log
from .rebalance import compute_rebalance
from .safety import CircuitBreaker, check_kill_switch

class RebalanceRunner:
    """계획 계산과 실발주 사이의 모든 안전장치를 배선한다.

    `compute_rebalance`가 순수 계산이고 `Broker`가 브로커 고유 부분이라면, 여기는 그
    사이에 kill switch·서킷브레이커·관리셋 보호·매도가능수량 clamp를 끼우는 층이다.
    dry-run과 실발주의 유일한 분기점도 여기다.
    """

    def __init__(
        self,
        broker: Broker,
        policy: RunnerPolicy,
        *,
        managed_state: ManagedState | None = None,
        kill_switch_path: str | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        log_dir: str | None = None,
    ):
        """협력자를 받는다. 안전장치는 전부 선택이며, 넘기지 않으면 그 보호가 없다.

        Args:
            broker: 발주·조회 어댑터.
            policy: 이 실행에 적용할 정책. 실행 로그에 그대로 직렬화된다.
            managed_state: 봇 관리셋. 생략하면 인메모리라 다음 실행이 보호를 잃는다.
            kill_switch_path: 이 파일이 있으면 발주하지 않는다. 생략하면 검사하지 않는다.
            circuit_breaker: 일일 주문건수·손실 상한. 생략하면 상한이 없다.
            log_dir: 실발주 결과를 남길 디렉터리(대시보드 소스). 생략하면 남기지 않는다.
        """
        self.broker = broker
        self.policy = policy
        self.state = managed_state if managed_state is not None else ManagedState(path=None)
        self.kill_switch_path = kill_switch_path
        self.cb = circuit_breaker
        self.log_dir = log_dir  # 설정 시 실발주 결과를 execution_logs로 영속화(대시보드 소스)

    def _build_plan(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool) -> RebalancePlan:
        snap = self.broker.snapshot(sorted(target_weights))
        self._account = snap
        holdings = snap.holdings

        # dry-run은 state를 변경하지 않는다. bootstrapped 플래그가 오염되면
        # 이후 실발주에서 사용자 보유 보호가 무력화된다.
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

        prices = snap.prices

        # 가격이 없으면 봇 보유 평가액이 낮게 잡혀 예산이 과대 계산된다 → 과지출
        missing = [s for s in bot_holdings if prices.get(s, 0.0) <= 0]
        if missing:
            raise ExecutionError(f"보유 종목 가격 누락 → 예산 계산 불가(안전 중단): {missing}")

        account_bp = snap.buying_power_usd
        bot_value = sum(bot_holdings[s] * prices[s] for s in bot_holdings)

        if self.policy.budget_usd is None:  # 예산 미설정: 봇 보유 + 계좌현금 전체
            total_equity, buying_power = bot_value + account_bp, account_bp
        else:                        # 예산 상한: 목표 규모=budget, 매수는 남은 예산·계좌현금 내
            total_equity = self.policy.budget_usd
            buying_power = max(0.0, min(account_bp, self.policy.budget_usd - bot_value))

        params = RebalanceParams(total_equity, buying_power, self.policy.min_order_usd, rebalance_date,
                                 rebalance_band=self.policy.rebalance_band)
        plan = compute_rebalance(target, bot_holdings, prices, params)
        self._snapshot = {
            "target_weights": dict(target_weights),
            "prices": dict(prices),
            "holdings": dict(bot_holdings),
            "total_equity_usd": params.total_equity_usd,
            "buying_power_usd": params.buying_power_usd,
            "min_order_usd": params.min_order_usd,
            "rebalance_band": params.rebalance_band,
            "excluded_targets": list(excluded_targets),
        }
        plan = self._clamp_sells_to_sellable(plan)
        if excluded_targets:
            plan = RebalancePlan(
                orders=plan.orders,
                skipped=plan.skipped + [(s, "excluded_manual") for s in excluded_targets],
            )
        return plan

    def _clamp_sells_to_sellable(self, plan: RebalancePlan) -> RebalancePlan:
        """매도 수량을 매도가능수량(sellable)으로 상한. T+N 미결제분이 있으면 보유수량 >
        sellable → 초과매도가 거부(리밸 붕괴)되므로, sellable로 줄이거나(부분매도) 0이면 스킵.

        조회는 **실제 매도 대상 종목만** 한 번에 묶어서 한다. 보유 전 종목을 받으면
        매도 2건에 조회 30건이 나가고, throttle sleep까지 곱해져 dry-run도 느려진다.
        """
        sell_symbols = sorted({o.symbol for o in plan.orders
                               if o.side == "SELL" and o.kind == "quantity"})
        sellable_map = self.broker.get_sellable(sell_symbols) if sell_symbols else {}
        # 누락을 0으로 보면 "조회를 안 한 것"이 "미결제"로 기록되고 매도가 조용히 사라진다.
        # 청산하려던 포지션을 계속 들고 있게 되므로 중단이 낫다.
        unreported = [s for s in sell_symbols if s not in sellable_map]
        if unreported:
            raise ExecutionError(
                f"매도가능수량 미조회 종목 → 매도 판단 불가(안전 중단): {unreported}"
            )

        new_orders: list[OrderIntent] = []
        extra_skips: list[tuple[str, str]] = []
        for o in plan.orders:
            if o.side == "SELL" and o.kind == "quantity":
                sellable = sellable_map[o.symbol]
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
                    # 줄어든 exit은 reason도 바꾼다. "exit"으로 남으면 update_after_place가
                    # 잔량이 계좌에 있는데도 M에서 빼버린다 — 그 포지션은 M에도 X에도 없어
                    # 다음 사이클 bot_holdings에서 제외되고, 매도·trim·재평가 대상이 영영 아니다.
                    reason = "exit_partial" if o.reason == "exit" else o.reason
                    o = replace(o, value=clamped, reason=reason)  # 부분매도(잔량 다음 사이클)
                    extra_skips.append((o.symbol, "sell_clamped_to_sellable"))
            new_orders.append(o)
        return RebalancePlan(orders=new_orders, skipped=plan.skipped + extra_skips)

    def _place_order(self, order: OrderIntent) -> tuple[str, str | None]:
        """단건 발주. rate-limit은 백오프 재시도, 장마감/개별거부는 코드로 분류 반환.
        반환: ("placed", 주문ID) | ("skip", 사유) | ("abort", 사유). 미분류 오류는 전파한다.
        """
        attempts = 0
        while True:
            try:
                return ("placed", self.broker.place(order))
            except BrokerRateLimited:
                if attempts >= self.policy.rate_limit_retries:
                    raise
                attempts += 1
                time.sleep(self.policy.rate_limit_backoff_s * attempts)  # 선형 백오프
            except BrokerMarketClosed as exc:
                return ("abort", getattr(exc, "code", "") or "market_closed")
            except OrderRejected as exc:
                return ("skip", exc.code)
            # 그 밖의 예외는 잡지 않는다 — 미분류(버그·미지의 실패)는 상위로 전파해 중단한다.

    def _collect_fills(self, order_ids: list[tuple[OrderIntent, str]]) -> list[dict]:
        """발주한 주문의 체결 실측을 회수한다. 조회가 실패해도 발주 기록은 버리지 않는다.

        시장가라도 조회 시점에 아직 미체결일 수 있다 — 그 경우 어댑터가 `None`을 주고
        값이 빈 행을 남긴다. 나중에 다시 조회해 채우는 편이 추정으로 메우는 것보다 낫다.

        응답 스키마 해석은 어댑터(`toss.broker`)의 책임이다. 여기서는 `Fill` 필드만 읽는다.
        """
        out = []
        for intent, order_id in order_ids:
            row = {"symbol": intent.symbol, "side": intent.side,
                   "client_order_id": intent.client_order_id, "order_id": order_id}
            if not order_id:
                row["fetch_error"] = "no_order_id"   # 발주는 됐으나 응답에 주문 ID가 없었다
                out.append(row)
                continue
            try:
                fill = self.broker.get_fill(order_id)
            except Exception as exc:  # noqa: BLE001 — 조회 실패가 발주 기록을 날리면 안 된다
                row["fetch_error"] = getattr(exc, "code", "") or type(exc).__name__
            else:
                if fill is not None:
                    row.update(asdict(fill))
            out.append(row)
        return out

    def _live_result(self, plan: RebalancePlan, *, placed=(), rejected=(),
                     aborted_reason: str | None = None, fills=()) -> RunResult:
        """실발주 결과를 한 곳에서 만든다.

        종료 경로가 셋(장마감·중단·정상)이라 흩어 두면 필드를 빠뜨린다 — 실제로 장마감
        경로가 `snapshot`을 통째로 빠뜨리고 있었다.
        """
        return RunResult(plan=plan, dry_run=False, placed=list(placed),
                         rejected=list(rejected), aborted_reason=aborted_reason,
                         snapshot=self._snapshot, policy=asdict(self.policy),
                         fills=list(fills))

    def _write_log(self, result: RunResult, rebalance_date: str) -> None:
        if self.log_dir:
            write_order_log(result, rebalance_date, Path(self.log_dir))

    def run(self, target_weights: dict[str, float], rebalance_date: str, dry_run: bool = True) -> RunResult:
        """계획을 세우고, `dry_run=False`면 발주한다.

        Args:
            target_weights: 심볼 → 목표 비중.
            rebalance_date: YYYYMMDD. 멱등키와 서킷브레이커 day 키의 근거이므로
                **미국 거래일**을 넘겨야 한다(로컬 날짜가 아니다).
            dry_run: True면 발주도 상태 저장도 하지 않는다 — 오프라인 프리뷰가 라이브
                부트스트랩을 오염시키지 않게 하려는 것이다.

        Raises:
            KillSwitchActive: kill switch 파일 존재.
            CircuitBreakerTripped: 일일 상한 초과.
            ExecutionError: 보유 종목 가격 누락 등 예산 계산 불가.
        """
        self._snapshot: dict | None = None
        self._account: AccountSnapshot | None = None
        plan = self._build_plan(target_weights, rebalance_date, dry_run)
        if dry_run:
            return RunResult(plan=plan, dry_run=True, snapshot=self._snapshot,
                             policy=asdict(self.policy))

        # --- 실발주: 안전장치 ---
        if self.kill_switch_path:
            check_kill_switch(self.kill_switch_path)
        if not self.broker.is_market_open():
            # 기록을 남긴다 — 없으면 "장마감이라 안 했다"와 "cron이 안 돌았다"가 구분되지
            # 않는다. is_market_open은 파싱 실패도 닫힘으로 접으므로 스키마가 어긋나면
            # 무기한 조용한 무동작이 된다.
            result = self._live_result(plan, aborted_reason="market_closed")
            self._write_log(result, rebalance_date)
            return result

        # 봇 관리분(M)의 당일손익만 손실상한에 반영한다 — 사용자 수동 보유(X)의 손실로
        # 봇이 멈추면 안 된다.
        if self.cb is not None and self.state.managed and self._account is not None:
            daily = sum(v for s, v in self._account.daily_pnl.items() if s in self.state.managed)
            # 절대 스냅샷이므로 대입한다. 누적하면 같은 날 재실행마다 이중계상된다.
            self.cb.observe_daily_loss(-daily)

        placed: list[str] = []
        order_ids: list[tuple[OrderIntent, str]] = []
        rejected: list[tuple[str, str]] = []
        aborted_reason: str | None = None
        # try/except/finally: 루프가 중간에 끊겨도 두 가지를 지킨다 —
        # (1) finally: 이미 발주된 주문을 M에 반영·영속해 상태 불일치(재실행 시 봇 매수분을
        #     미관리로 오인)를 막는다.
        # (2) except: 주문로그를 남긴다. 종전에는 로그 기록이 try 밖이라 예외가 나면
        #     이미 나간 주문의 기록이 통째로 사라졌다.
        try:
            for i, order in enumerate(plan.orders):  # 매도先→매수 순서(compute_rebalance 보장)
                if self.cb is not None:
                    self.cb.guard(side=order.side)  # 손실 축은 매수에만 — 청산은 막지 않는다
                if i > 0 and self.policy.order_sleep_s > 0:
                    time.sleep(self.policy.order_sleep_s)   # rate-limit 준수(호출 간 간격)
                outcome, code = self._place_order(order)
                if outcome == "placed":
                    placed.append(order.client_order_id)
                    # order_id가 빈 문자열이어도 담는다 — 발주는 됐는데 추적만 안 되는
                    # 상태이므로, 기록을 빠뜨리면 나중에 조회할 실마리조차 없다.
                    order_ids.append((order, code or ""))
                    if self.cb is not None:
                        self.cb.record_order()
                elif outcome == "skip":
                    rejected.append((order.symbol, code or ""))
                else:  # abort (장마감 등) → 잔여 주문 중단
                    aborted_reason = f"aborted_midrun:{code}"
                    break
        except BaseException as exc:
            # 발주 루프가 예외로 끊겼다(서킷브레이커 트립·속도제한 소진·미분류 오류·Ctrl-C).
            # **기록이 가장 필요한 경우가 여기다** — 이미 나간 주문의 client_order_id·snapshot이
            # 어디에도 없으면 나중에 무엇이 체결됐는지 확인할 실마리가 없다.
            #
            # fills는 조회하지 않는다. 장마감·속도제한 소진 상황에서 추가 API 호출이 또
            # 실패해 시간만 끌고, 그 실패가 원 예외를 가린다.
            try:
                self._write_log(
                    self._live_result(plan, placed=placed, rejected=rejected,
                                      aborted_reason=f"aborted_error:{type(exc).__name__}"),
                    rebalance_date)
            except Exception:  # noqa: BLE001 — 기록 실패가 중단 원인을 가리면 안 된다
                pass
            raise
        finally:
            self.state.update_after_place(plan.orders, placed)  # M 갱신(실발주분만)
            self.state.save()

        result = self._live_result(plan, placed=placed, rejected=rejected,
                                   aborted_reason=aborted_reason,
                                   fills=self._collect_fills(order_ids))
        self._write_log(result, rebalance_date)   # 정상 경로는 실패를 삼키지 않는다
        return result
