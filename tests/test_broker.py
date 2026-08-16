"""TossBroker 응답 파싱·발주 body 단위테스트 (StubClient — 실 API 불요).

응답 필드는 Phase 0(2026-07-20) 실측 구조로 고정 — 이 픽스처가 토스 응답 계약의 원천이다.
공통 래퍼 `{"result": ...}` 해제, market-calendar는 시각 비교로 개장 판정.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from execution.interface import OrderIntent
from toss.broker import TossBroker, _regular_market_open
from execution.errors import BrokerMarketClosed, BrokerRateLimited, OrderRejected
from toss.errors import TossApiError, TossError


class StubClient:
    """TossClient 대역: 경로별 응답을 주입, post는 기록."""

    def __init__(self, responses=None, post_error=None):
        self.responses = responses or {}
        self.posted: list[tuple[str, dict]] = []
        self.post_error = post_error

    def get(self, path, **kw):
        return self.responses[path]

    def post(self, path, json_body=None):
        self.posted.append((path, json_body))
        if self.post_error is not None:
            raise self.post_error
        # 실 응답 형태(Phase 0 실측): result에 orderId·clientOrderId만 온다(체결 정보 없음)
        return {"result": {"orderId": f"ord-{len(self.posted)}",
                           "clientOrderId": json_body.get("clientOrderId")}}


def _broker(responses=None, post_error=None):
    return TossBroker(StubClient(responses, post_error))


# --- get_holdings (실측: result.items[], quantity 문자열) ---









# --- get_prices (실측: result[], lastPrice 문자열) ---

def test_prices_parse():
    b = _broker({"/api/v1/prices": {"result": [
        {"symbol": "AAPL", "lastPrice": "331.9701", "currency": "USD"},
        {"symbol": "MSFT", "lastPrice": "500", "currency": "USD"}]}})
    assert b.get_prices(["AAPL", "MSFT"]) == {"AAPL": 331.9701, "MSFT": 500.0}


def test_prices_missing_symbol_skipped():
    b = _broker({"/api/v1/prices": {"result": [
        {"symbol": "AAPL", "lastPrice": "331.97"}, {"symbol": "MSFT"}]}})
    assert b.get_prices(["AAPL", "MSFT"]) == {"AAPL": 331.97}   # 가격 없는 심볼 스킵


def test_prices_bad_price_raises():
    b = _broker({"/api/v1/prices": {"result": [{"symbol": "AAPL", "lastPrice": "oops"}]}})
    with pytest.raises(TossError):
        b.get_prices(["AAPL"])


def test_prices_unexpected_shape_raises():
    b = _broker({"/api/v1/prices": {"result": {}}})   # 리스트 아님
    with pytest.raises(TossError):
        b.get_prices(["AAPL"])


# --- get_buying_power_usd (실측: result.cashBuyingPower) ---

def test_buying_power_usd():
    b = _broker({"/api/v1/buying-power": {"result": {"currency": "USD", "cashBuyingPower": "700.25"}}})
    assert b.get_buying_power_usd() == 700.25


def test_buying_power_zero_and_missing():
    b = _broker({"/api/v1/buying-power": {"result": {"currency": "USD", "cashBuyingPower": "0"}}})
    assert b.get_buying_power_usd() == 0.0
    b2 = _broker({"/api/v1/buying-power": {"result": {}}})
    assert b2.get_buying_power_usd() == 0.0   # 필드 없으면 보수적 0


def test_buying_power_bad_value_raises():
    b = _broker({"/api/v1/buying-power": {"result": {"currency": "USD", "cashBuyingPower": "??"}}})
    with pytest.raises(TossError):
        b.get_buying_power_usd()


# --- get_sellable_quantity (실측: result.sellableQuantity) ---

def test_sellable_quantity():
    b = _broker({"/api/v1/sellable-quantity": {"result": {"sellableQuantity": "7.665831"}}})
    assert b.get_sellable_quantity("AAPL") == 7.665831


def test_sellable_missing_is_zero():
    b = _broker({"/api/v1/sellable-quantity": {"result": {}}})
    assert b.get_sellable_quantity("AAPL") == 0.0   # 알 수 없으면 보수적 0(매도 안 함)


def test_sellable_bad_value_raises():
    b = _broker({"/api/v1/sellable-quantity": {"result": {"sellableQuantity": "x"}}})
    with pytest.raises(TossError):
        b.get_sellable_quantity("AAPL")


# --- get_daily_pnl_usd (실측: holdings items[].dailyProfitLoss.amount, 관리셋만 합산) ---

def _holdings_pnl():
    return {"/api/v1/holdings": {"result": {"items": [
        {"symbol": "AAPL", "quantity": "1", "dailyProfitLoss": {"amount": "-13.49"}},
        {"symbol": "TSM", "quantity": "1", "dailyProfitLoss": {"amount": "61.28"}},
        {"symbol": "NKE", "quantity": "1", "dailyProfitLoss": {"amount": "1.49"}}]}}}






# --- is_market_open (실측: isOpen 없음 → regularMarket 시각 비교) ---

_CAL = {"result": {"today": {"regularMarket": {
    "startTime": "2026-07-20T22:30:00.000+09:00",
    "endTime": "2026-07-21T05:00:00.000+09:00"}}}}


@pytest.mark.parametrize("now_kst_hhmm,expected", [
    ("2026-07-20T20:00:00.000+09:00", False),   # 개장 전(preMarket)
    ("2026-07-20T22:30:00.000+09:00", True),    # 개장 순간 포함
    ("2026-07-21T02:00:00.000+09:00", True),    # 정규장 중(자정 넘김)
    ("2026-07-21T05:00:00.000+09:00", False),   # 종료 순간 제외([start,end))
    ("2026-07-21T06:00:00.000+09:00", False),   # afterMarket
])
def test_regular_market_open(now_kst_hhmm, expected):
    now = datetime.strptime(now_kst_hhmm, "%Y-%m-%dT%H:%M:%S.%f%z")
    assert _regular_market_open(_CAL, now) is expected


def test_market_open_missing_or_unparsable_is_closed():
    now = datetime.now(timezone.utc)
    assert _regular_market_open({"result": {"today": {}}}, now) is False
    assert _regular_market_open({}, now) is False
    bad = {"result": {"today": {"regularMarket": {"startTime": "nope", "endTime": "nope"}}}}
    assert _regular_market_open(bad, now) is False
    # offset/밀리초 없는 포맷도 파싱 실패 → 보수적 닫힘
    no_off = {"result": {"today": {"regularMarket": {
        "startTime": "2026-07-20T22:30:00Z", "endTime": "2026-07-21T05:00:00Z"}}}}
    assert _regular_market_open(no_off, now) is False


# --- place: 발주 body (숫자 문자열, amount vs quantity) ---

def test_place_buy_amount_body():
    b = _broker()
    b.place(OrderIntent("AAPL", "BUY", "amount", 35.0, "rb-abc", "enter"))
    path, body = b.client.posted[0]
    assert path == "/api/v1/orders"
    assert body == {"symbol": "AAPL", "side": "BUY", "orderType": "MARKET",
                    "clientOrderId": "rb-abc", "orderAmount": "35.0"}
    assert "quantity" not in body           # 매수는 금액만


def test_place_sell_quantity_body():
    b = _broker()
    b.place(OrderIntent("MSFT", "SELL", "quantity", 2.5, "rb-xyz", "exit"))
    _, body = b.client.posted[0]
    assert body["quantity"] == "2.5" and "orderAmount" not in body
    assert body["side"] == "SELL" and body["orderType"] == "MARKET"


def test_place_numeric_fields_are_strings():
    b = _broker()
    b.place(OrderIntent("AAPL", "BUY", "amount", 100.0, "cid", "enter"))
    _, body = b.client.posted[0]
    assert isinstance(body["orderAmount"], str)   # API 규약: 숫자 필드 문자열


# --- B3: place가 orderId를 돌려주고, 에러코드를 정규화된 예외로 번역한다 ---

def test_place_returns_order_id():
    """러너는 응답 봉투를 모른다 — 어댑터가 orderId 문자열만 건넨다."""
    b = _broker()
    assert b.place(OrderIntent("AAPL", "BUY", "amount", 35.0, "rb-abc", "enter")) == "ord-1"


def test_place_without_order_id_returns_empty_not_raise():
    """POST가 성공했는데 orderId가 없으면 **예외를 던지지 않는다.**

    주문은 이미 브로커에 살아 있다. 여기서 던지면 러너가 placed에 담지 못해 화이트리스트에
    안 들어가고, 그 종목은 청산도 trim도 안 되면서 목표에 남아 다음 사이클에 또 매수된다.
    추적 불가는 빈 문자열로 알리고, 발주 사실은 반드시 기록되게 한다.
    """
    class NoIdClient(StubClient):
        def post(self, path, json_body=None):
            return {"result": {"clientOrderId": "x"}}

    assert TossBroker(NoIdClient()).place(
        OrderIntent("AAPL", "BUY", "amount", 1.0, "c", "enter")) == ""


@pytest.mark.parametrize("code,expected", [
    ("rate-limit-exceeded", BrokerRateLimited),
    ("order-hours-closed", BrokerMarketClosed),
    ("amount-order-outside-regular-hours", BrokerMarketClosed),
    ("insufficient-buying-power", OrderRejected),
    ("market-not-supported-for-stock", OrderRejected),
])
def test_place_maps_toss_codes_to_normalized_errors(code, expected):
    """토스 코드 문자열의 해석은 어댑터에서 끝난다. 러너는 예외 타입으로만 분기한다."""
    b = _broker(post_error=TossApiError("POST", "/api/v1/orders", 422, {"error": {"code": code}}))
    with pytest.raises(expected):
        b.place(OrderIntent("AAPL", "BUY", "amount", 1.0, "c", "enter"))


def test_place_unknown_code_propagates_as_toss_error():
    # 미분류 코드는 번역하지 않는다 — 상위로 전파해 중단시키는 게 안전하다.
    b = _broker(post_error=TossApiError("POST", "/api/v1/orders", 500, {"error": {"code": "wat"}}))
    with pytest.raises(TossApiError):
        b.place(OrderIntent("AAPL", "BUY", "amount", 1.0, "c", "enter"))


# --- B3: get_fill — 응답 스키마 해석의 유일한 지점 ---

def test_get_fill_parses_execution_fields():
    b = _broker({"/api/v1/orders/ord-1": {"result": {"execution": {
        "filledQuantity": "1", "averageFilledPrice": "101.5", "filledAmount": "101.5",
        "commission": "0.1", "tax": "0", "filledAt": "2026-07-20T22:31:00.000+09:00"}}}})
    fill = b.get_fill("ord-1")
    # 토스는 숫자를 문자열로 준다. 그대로 흘리면 슬리피지 계산이 TypeError로 죽는다.
    assert fill.avg_filled_price == 101.5 and fill.commission == 0.1
    assert isinstance(fill.filled_quantity, float)
    assert fill.filled_at.startswith("2026-07-20")


def test_get_fill_returns_none_when_execution_absent():
    """미체결이면 None. 이 판정이 러너에 있으면 실응답으로 검증할 수 없다(P1-1의 요점).

    시장가라도 발주 직후에는 체결이 안 잡힐 수 있고, 그때 값을 지어내면 슬리피지가 오염된다.
    """
    b = _broker({"/api/v1/orders/ord-1": {"result": {"orderId": "ord-1"}}})
    assert b.get_fill("ord-1") is None
    b2 = _broker({"/api/v1/orders/ord-2": {"result": {"execution": {}}}})
    assert b2.get_fill("ord-2") is None


# --- B4: snapshot / get_sellable ---

def test_snapshot_fetches_holdings_once():
    """당일손익 때문에 holdings를 두 번 치던 것을 한 번으로 접었다."""
    client = StubClient({
        "/api/v1/holdings": {"result": {"items": [
            {"symbol": "AAPL", "quantity": "2", "dailyProfitLoss": {"amount": "-13.49"}}]}},
        "/api/v1/prices": [{"symbol": "AAPL", "lastPrice": "100.0"},
                           {"symbol": "MSFT", "lastPrice": "200.0"}],
        "/api/v1/buying-power": {"result": {"cashBuyingPower": "500.0"}},
    })
    seen = []
    real_get = client.get
    client.get = lambda path, **kw: (seen.append(path), real_get(path, **kw))[1]

    snap = TossBroker(client).snapshot(["MSFT"])
    assert seen.count("/api/v1/holdings") == 1
    assert snap.holdings == {"AAPL": 2.0}
    assert snap.daily_pnl == {"AAPL": -13.49}
    assert snap.buying_power_usd == 500.0
    assert set(snap.prices) == {"AAPL", "MSFT"}      # target ∪ 보유


def test_get_sellable_throttles_between_symbols(monkeypatch):
    """ACCOUNT 그룹은 한도가 낮다. 종전에는 러너가 sleep 없이 연속 호출했다."""
    slept = []
    monkeypatch.setattr("toss.broker.time.sleep", lambda s: slept.append(s))
    b = _broker({"/api/v1/sellable-quantity": {"result": {"sellableQuantity": "1.0"}}})
    b.get_sellable(["AAA", "BBB", "CCC"])
    assert len(slept) == 2                            # 심볼 사이에만 쉰다


def test_get_sellable_retries_rate_limited(monkeypatch):
    monkeypatch.setattr("toss.broker.time.sleep", lambda s: None)
    calls = {"n": 0}

    class Flaky(StubClient):
        def get(self, path, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TossApiError("GET", path, 429, {"error": {"code": "rate-limit-exceeded"}})
            return {"result": {"sellableQuantity": "2.5"}}

    assert TossBroker(Flaky()).get_sellable(["AAA"]) == {"AAA": 2.5}


def test_get_fill_keeps_absent_fields_none():
    b = _broker({"/api/v1/orders/ord-1": {"result": {"execution": {
        "filledQuantity": "1", "averageFilledPrice": "101.5"}}}})
    fill = b.get_fill("ord-1")
    assert fill.commission is None and fill.tax is None


def test_reads_retry_rate_limit_then_succeed(monkeypatch):
    """읽기 경로 전체가 번역·재시도를 지난다 — 하나라도 빠지면 raw TossApiError가 러너를 뚫는다."""
    monkeypatch.setattr("toss.broker.time.sleep", lambda s: None)
    n = {"i": 0}

    class Flaky(StubClient):
        def get(self, path, **kw):
            n["i"] += 1
            if n["i"] == 1:
                raise TossApiError("GET", path, 429, {"error": {"code": "rate-limit-exceeded"}})
            return {"result": {"cashBuyingPower": "500.0"}}

    assert TossBroker(Flaky()).get_buying_power_usd() == 500.0


def test_read_error_is_normalized_not_raw(monkeypatch):
    monkeypatch.setattr("toss.broker.time.sleep", lambda s: None)

    class Closed(StubClient):
        def get(self, path, **kw):
            raise TossApiError("GET", path, 422, {"error": {"code": "order-hours-closed"}})

    with pytest.raises(BrokerMarketClosed):
        TossBroker(Closed()).get_buying_power_usd()


def test_snapshot_paces_account_calls(monkeypatch):
    slept = []
    monkeypatch.setattr("toss.broker.time.sleep", lambda s: slept.append(s))
    b = _broker({
        "/api/v1/holdings": {"result": {"items": []}},
        "/api/v1/prices": [],
        "/api/v1/buying-power": {"result": {"cashBuyingPower": "0"}},
    })
    b.snapshot(["AAPL"])
    assert len(slept) >= 2          # holdings → prices → buying-power 사이


# --- 보유·당일손익은 snapshot을 통해서만 프로덕션 경로에 닿는다 ---

def test_snapshot_empty_items_is_ok():
    # 빈 계좌는 정상이다 — 파싱 실패와 구분해야 한다.
    b = _broker({"/api/v1/holdings": {"result": {"items": []}},
                 "/api/v1/prices": [], "/api/v1/buying-power": {"result": {"cashBuyingPower": "0"}}})
    snap = b.snapshot([])
    assert snap.holdings == {} and snap.daily_pnl == {}


def test_snapshot_parses_holdings_and_daily_pnl():
    b = _broker({
        "/api/v1/holdings": {"result": {"items": [
            {"symbol": "AAPL", "quantity": "9.941577", "dailyProfitLoss": {"amount": "-13.49"}},
            {"symbol": "TSM", "quantity": "2", "dailyProfitLoss": {"amount": "61.28"}},
            {"symbol": "NKE", "quantity": "1"},                  # 손익 필드 없음 → 생략
        ]}},
        "/api/v1/prices": [{"symbol": "AAPL", "lastPrice": "100"}],
        "/api/v1/buying-power": {"result": {"cashBuyingPower": "10"}},
    })
    snap = b.snapshot([])
    assert snap.holdings == {"AAPL": 9.941577, "TSM": 2.0, "NKE": 1.0}
    assert snap.daily_pnl == {"AAPL": -13.49, "TSM": 61.28}      # NKE는 키 자체가 없다


def test_snapshot_raises_on_unexpected_holdings_shape():
    """부분 반환 금지 — 화이트리스트 제외셋이 미완성되면 사용자 보유가 매매 대상이 된다."""
    with pytest.raises(TossError):
        _broker({"/api/v1/holdings": {"result": []}}).snapshot([])


def test_snapshot_raises_on_missing_item_field():
    with pytest.raises(TossError, match="symbol/quantity"):
        _broker({"/api/v1/holdings": {"result": {"items": [{"symbol": "AAPL"}]}}}).snapshot([])


def test_snapshot_raises_on_unparsable_quantity():
    with pytest.raises(TossError, match="숫자 변환 실패"):
        _broker({"/api/v1/holdings": {"result": {"items": [
            {"symbol": "AAPL", "quantity": "N/A"}]}}}).snapshot([])


def test_get_fill_captures_settlement_date():
    """결제일은 규칙 계산이 아니라 브로커 값을 그대로 담는다.

    미국 현지는 2024-05-28부터 T+1이지만 국내 예탁·외화결제 버퍼로 T+2가 되고, 미국
    휴장일과 한국 휴장일이 겹치면 규칙으로는 어긋난다. 세법상 양도시기·환율기준일의 근거다.
    """
    b = _broker({"/api/v1/orders/ord-1": {"result": {"execution": {
        "filledQuantity": "1", "averageFilledPrice": "101.5",
        "filledAt": "2026-07-20T22:31:00.000+09:00", "settlementDate": "2026-07-22"}}}})
    assert b.get_fill("ord-1").settlement_date == "2026-07-22"


def test_get_fill_settlement_date_absent_is_none():
    b = _broker({"/api/v1/orders/ord-1": {"result": {"execution": {"filledQuantity": "1"}}}})
    assert b.get_fill("ord-1").settlement_date is None
