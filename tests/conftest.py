"""pytest 공통 설정: src/를 import 경로에 추가.

pytest가 테스트 수집 전 conftest.py를 먼저 로드 → 각 테스트 파일의 sys.path 부트스트랩 중복 제거.
"""
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# --- 리팩터 격리 지점 (B1) ---------------------------------------------------
# 특성화 테스트(test_runner_behaviour.py)는 러너의 관찰 가능한 동작만 고정한다. 그런데
# 러너를 돌리려면 Broker 구현과 생성자 시그니처를 알아야 하므로, 그 두 가지에 간접
# 의존한다. seam 리팩터(B3~B5)가 Protocol과 생성자를 바꾸면 어딘가는 반드시 고쳐야 한다.
#
# 그 변경 지점을 아래 두 팩토리로 국소화한다. 특성화 테스트 본문은 팩토리만 호출하고
# Broker 메서드도 RebalanceRunner 생성자도 직접 만지지 않는다 → 리팩터 후 본문 무수정
# 통과가 곧 "동작이 안 바뀌었다"의 증거가 된다.

def _as_broker_error(code):
    """테스트 편의: 코드 문자열 → 정규화된 실패 예외. 어댑터가 하는 번역을 흉내낸다."""
    from execution.errors import BrokerMarketClosed, BrokerRateLimited, OrderRejected

    if code == "rate-limit-exceeded":
        return BrokerRateLimited(code)
    if code in ("order-hours-closed", "amount-order-outside-regular-hours"):
        err = BrokerMarketClosed(code)
        err.code = code
        return err
    if code in ("insufficient-buying-power", "market-not-supported-for-stock"):
        return OrderRejected(code)
    # 미분류는 번역하지 않는다 — 어댑터와 같은 정책. 러너가 잡지 않고 상위로 전파해 중단한다.
    return RuntimeError(code)


class _FactoryBroker:
    def __init__(self, holdings, prices, buying_power, sellable, daily_pnl,
                 market_open, place_errors):
        self._holdings = dict(holdings)
        self._prices = dict(prices)
        self._buying_power = buying_power
        self._sellable = dict(sellable)
        self._daily_pnl = dict(daily_pnl)
        self._market_open = market_open
        self._place_errors = {k: list(v) for k, v in place_errors.items()}
        self.placed = []

    def get_holdings(self):
        return dict(self._holdings)

    def get_prices(self, symbols):
        return {s: self._prices.get(s, 100.0) for s in symbols}

    def get_buying_power_usd(self):
        return self._buying_power

    def get_sellable_quantity(self, symbol):
        return self._sellable.get(symbol, self._holdings.get(symbol, 0.0))

    def get_daily_pnl_usd(self, symbols):
        return sum(self._daily_pnl.get(s, 0.0) for s in symbols)

    def is_market_open(self):
        return self._market_open

    def place(self, intent):
        errs = self._place_errors.get(intent.symbol)
        if errs:
            raise _as_broker_error(errs.pop(0))
        self.placed.append(intent)
        return f"ord-{len(self.placed)}"

    def get_fill(self, order_id):
        return None


def _make_broker(holdings=None, prices=None, buying_power=10_000.0, sellable=None,
                daily_pnl=None, market_open=True, place_errors=None):
    """특성화 테스트용 브로커. Protocol이 바뀌면 **이 함수만** 고친다."""
    return _FactoryBroker(holdings or {}, prices or {}, buying_power, sellable or {},
                          daily_pnl or {}, market_open, place_errors or {})


def _make_runner(broker, min_order_usd=1.0, budget_usd=None, rebalance_band=0.10,
                managed_state=None, circuit_breaker=None):
    """특성화 테스트용 러너. 생성자 시그니처가 바뀌면 **이 함수만** 고친다."""
    from execution.runner import RebalanceRunner

    return RebalanceRunner(
        broker, min_order_usd=min_order_usd, budget_usd=budget_usd,
        rebalance_band=rebalance_band, managed_state=managed_state,
        circuit_breaker=circuit_breaker, order_sleep_s=0, rate_limit_backoff_s=0,
    )


@pytest.fixture
def make_broker():
    return _make_broker


@pytest.fixture
def make_runner():
    return _make_runner
