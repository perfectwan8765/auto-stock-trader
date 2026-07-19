"""TossBroker 응답 파싱·발주 body 단위테스트 (StubClient — 실 API 불요).

⚠️ 응답 필드명은 Phase 0 실측 확정 전 가정값. 이 테스트는 현재 방어파싱 규약을 고정하고,
Phase 0에서 실제 응답으로 필드가 바뀌면 함께 갱신한다.
"""
from __future__ import annotations

import pytest

from execution.interface import OrderIntent
from toss.broker import TossBroker


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


# --- get_holdings ---

def test_holdings_dict_form_mixed_types():
    b = _broker({"/api/v1/holdings": {"holdings": [
        {"symbol": "AAPL", "quantity": "3.5"}, {"symbol": "MSFT", "quantity": 2}]}})
    assert b.get_holdings() == {"AAPL": 3.5, "MSFT": 2.0}


def test_holdings_list_form():
    b = _broker({"/api/v1/holdings": [{"symbol": "AAPL", "quantity": 1}]})
    assert b.get_holdings() == {"AAPL": 1.0}


def test_holdings_empty_and_missing_fields():
    b = _broker({"/api/v1/holdings": {"holdings": [{"symbol": "AAPL"}, {"quantity": 5}]}})
    assert b.get_holdings() == {}          # 필드 누락 항목은 스킵
    b2 = _broker({"/api/v1/holdings": {}})
    assert b2.get_holdings() == {}


# --- get_prices ---

def test_prices_parse():
    b = _broker({"/api/v1/prices": {"prices": [
        {"symbol": "AAPL", "price": "100.5"}, {"symbol": "MSFT", "price": 200}]}})
    assert b.get_prices(["AAPL", "MSFT"]) == {"AAPL": 100.5, "MSFT": 200.0}


# --- get_buying_power_usd (필드 폴백) ---

@pytest.mark.parametrize("resp,expected", [
    ({"usdBuyingPower": "700.25"}, 700.25),
    ({"usd": 500}, 500.0),
    ({"USD": 42.0}, 42.0),
    ({}, 0.0),                              # 알 수 없으면 0(보수적)
])
def test_buying_power_field_fallback(resp, expected):
    assert _broker({"/api/v1/buying-power": resp}).get_buying_power_usd() == expected


# --- is_market_open (필드 폴백) ---

@pytest.mark.parametrize("resp,expected", [
    ({"isOpen": True}, True),
    ({"open": False}, False),
    ({"regularOpen": True}, True),
    ({}, False),                            # 알 수 없으면 닫힘(보수적)
])
def test_market_open_field_fallback(resp, expected):
    assert _broker({"/api/v1/market-calendar/US": resp}).is_market_open() == expected


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
