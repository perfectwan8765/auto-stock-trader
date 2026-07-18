"""목표 비중 → 발주 계획 계산 (브로커 비의존, 순수 함수).

규약(qlib-toss.md Phase 5):
- 개선1 자금순환(T+N): 매수는 **현재 가용 USD 한도** 내에서만. 이번 사이클 매도대금은 T+N로
  즉시 안 잡힐 수 있어 매수 예산에 포함하지 않는다(보수적). 초과분은 다음 사이클로 이월.
- 개선5 결정적 멱등키: clientOrderId = hash(리밸일자+symbol+side+금액). 재시도·크래시 재개 시 동일.
- 개선8 최소금액: 목표 매수액이 최소주문금액 미만이면 스킵(사유 기록). 상위 갭 우선 배분.
- 매도先→매수 순서(자금 확보). 매도 대상: 편출(exit) 전량 + 초과보유(trim).
"""
from __future__ import annotations

import hashlib

from .interface import OrderIntent, RebalanceParams, RebalancePlan


def make_client_order_id(rebalance_date: str, symbol: str, side: str) -> str:
    """개선5: (일자·종목·side)로 결정적 멱등키.

    금액은 키에서 **제외** — T+N 정산으로 재실행 시 가용액·목표금액이 달라질 수 있어
    금액을 넣으면 재시도/부분매수 재개 때 키가 바뀌어 중복주문 위험(멱등 붕괴). 하루 한
    종목당 side별 1주문(주간 리밸) 가정 하에 (일자·종목·side)면 재현·중복방지 충분.
    """
    raw = f"{rebalance_date}:{symbol}:{side}"
    return "rb-" + hashlib.sha1(raw.encode()).hexdigest()[:20]


def compute_rebalance(
    target_weights: dict[str, float],
    holdings: dict[str, float],
    prices: dict[str, float],
    params: RebalanceParams,
) -> RebalancePlan:
    orders: list[OrderIntent] = []
    skipped: list[tuple[str, str]] = []

    target_usd = {s: w * params.total_equity_usd for s, w in target_weights.items() if w > 0}

    def cid(sym: str, side: str) -> str:
        return make_client_order_id(params.rebalance_date, sym, side)

    def current_usd(sym: str) -> float:
        return holdings.get(sym, 0.0) * prices.get(sym, 0.0)

    # --- 매도(先): 편출 전량 + 초과보유 trim ---
    for sym, qty in holdings.items():
        if qty <= 0:
            continue
        if sym not in target_usd:  # 편출: broker 권위값(보유수량) 그대로 — 반올림 시 over-sell 위험
            orders.append(OrderIntent(sym, "SELL", "quantity", qty, cid(sym, "SELL"), "exit"))

    for sym in target_usd:
        price = prices.get(sym, 0.0)
        excess = current_usd(sym) - target_usd[sym]
        if excess > params.min_order_usd and price > 0:
            qty = round(excess / price, 8)  # 소수점 주식수 정규화(문자열화 오차 방지)
            orders.append(OrderIntent(sym, "SELL", "quantity", qty, cid(sym, "SELL"), "trim"))

    # --- 매수(後): 가용 USD 한도 내 greedy(큰 갭 우선), 최소금액·이월 처리 ---
    buys = []
    for sym in target_usd:
        gap = target_usd[sym] - current_usd(sym)
        if gap <= 0:
            continue
        if gap < params.min_order_usd:
            skipped.append((sym, "below_min_order"))  # 개선8
            continue
        buys.append((sym, gap))
    buys.sort(key=lambda x: -x[1])

    available = params.buying_power_usd  # 개선1: 이번 사이클 매도대금 미포함(보수적)
    for sym, gap in buys:
        reason = "enter" if holdings.get(sym, 0.0) <= 0 else "add"
        if gap <= available:
            amt = round(gap, 2)
            orders.append(OrderIntent(sym, "BUY", "amount", amt, cid(sym, "BUY"), reason))
            available -= gap
        elif available >= params.min_order_usd:
            # 부분 매수(가용 잔액), 나머지 다음 사이클 이월(개선1). 키는 금액 무관(멱등).
            amt = round(available, 2)
            orders.append(OrderIntent(sym, "BUY", "amount", amt, cid(sym, "BUY"), reason))
            skipped.append((sym, "partial_insufficient_buying_power"))
            available = 0.0
        else:
            skipped.append((sym, "insufficient_buying_power"))

    return RebalancePlan(orders=orders, skipped=skipped)
