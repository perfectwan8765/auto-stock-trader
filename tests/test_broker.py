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

def test_holdings_parse_result_items():
    b = _broker({"/api/v1/holdings": {"result": {"items": [
        {"symbol": "AAPL", "quantity": "9.941577"},
        {"symbol": "TSLA", "quantity": "1"}]}}})
    assert b.get_holdings() == {"AAPL": 9.941577, "TSLA": 1.0}


def test_holdings_empty_items_ok():
    b = _broker({"/api/v1/holdings": {"result": {"items": []}}})
    assert b.get_holdings() == {}          # 보유 없음(정상) → 빈 dict
    b2 = _broker({"/api/v1/holdings": {"result": {}}})
    assert b2.get_holdings() == {}         # items 키 없음 → 빈 dict


def test_holdings_missing_field_raises_not_skip():
    """홀딩 항목 누락은 스킵 금지(화이트리스트 X 미완성=bypass) → 중단."""
    b = _broker({"/api/v1/holdings": {"result": {"items": [{"symbol": "AAPL"}]}}})
    with pytest.raises(TossError):
        b.get_holdings()


def test_holdings_bad_quantity_raises():
    b = _broker({"/api/v1/holdings": {"result": {"items": [{"symbol": "AAPL", "quantity": "N/A"}]}}})
    with pytest.raises(TossError):
        b.get_holdings()


def test_holdings_unexpected_shape_raises():
    b = _broker({"/api/v1/holdings": {"result": {"items": "not-a-list"}}})
    with pytest.raises(TossError):
        b.get_holdings()
    b2 = _broker({"/api/v1/holdings": []})   # result 래퍼 없음, dict 아님
    with pytest.raises(TossError):
        b2.get_holdings()


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


def test_daily_pnl_sums_only_managed():
    b = _broker(_holdings_pnl())
    assert b.get_daily_pnl_usd({"AAPL"}) == -13.49          # 관리셋 밖(TSM/NKE) 제외
    assert round(b.get_daily_pnl_usd({"AAPL", "TSM"}), 2) == 47.79
    assert b.get_daily_pnl_usd(set()) == 0.0                # 관리셋 비면 0


def test_daily_pnl_missing_amount_skipped():
    b = _broker({"/api/v1/holdings": {"result": {"items": [
        {"symbol": "AAPL", "quantity": "1"}]}}})           # dailyProfitLoss 없음
    assert b.get_daily_pnl_usd({"AAPL"}) == 0.0


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


def test_place_without_order_id_is_an_error():
    # orderId가 없으면 체결 추적이 불가능하다 — 성공으로 넘기면 안 된다.
    class NoIdClient(StubClient):
        def post(self, path, json_body=None):
            return {"result": {"clientOrderId": "x"}}

    with pytest.raises(TossError, match="orderId 없음"):
        TossBroker(NoIdClient()).place(OrderIntent("AAPL", "BUY", "amount", 1.0, "c", "enter"))


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
    assert fill.avg_filled_price == "101.5" and fill.commission == "0.1"
    assert fill.filled_at.startswith("2026-07-20")


def test_get_fill_returns_none_when_execution_absent():
    """미체결이면 None. 이 판정이 러너에 있으면 실응답으로 검증할 수 없다(P1-1의 요점).

    시장가라도 발주 직후에는 체결이 안 잡힐 수 있고, 그때 값을 지어내면 슬리피지가 오염된다.
    """
    b = _broker({"/api/v1/orders/ord-1": {"result": {"orderId": "ord-1"}}})
    assert b.get_fill("ord-1") is None
    b2 = _broker({"/api/v1/orders/ord-2": {"result": {"execution": {}}}})
    assert b2.get_fill("ord-2") is None
