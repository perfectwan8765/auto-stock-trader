"""TossBroker 응답 파싱·발주 body 단위테스트 (StubClient — 실 API 불요).

응답 필드는 Phase 0(2026-07-20) 실측 구조로 고정 — phase0-findings.md 참고.
공통 래퍼 `{"result": ...}` 해제, market-calendar는 시각 비교로 개장 판정.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from execution.interface import OrderIntent
from toss.broker import TossBroker, _regular_market_open
from toss.errors import TossError


class StubClient:
    """TossClient 대역: 경로별 응답을 주입, post는 기록."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.posted: list[tuple[str, dict]] = []

    def get(self, path, **kw):
        return self.responses[path]

    def post(self, path, json_body=None):
        self.posted.append((path, json_body))
        return {"status": "ACCEPTED", "clientOrderId": json_body.get("clientOrderId")}


def _broker(responses=None):
    return TossBroker(StubClient(responses))


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
