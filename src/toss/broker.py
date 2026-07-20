"""TossBroker — execution.interface.Broker의 토스 구체 구현(transport glue).

TossClient(HTTP)를 감싸 리밸런싱 로직에 브로커 능력을 제공한다.
응답 필드는 Phase 0(2026-07-20) 실측으로 확정 — phase0-findings.md "응답 필드 실측" 참고.
공통 래퍼 `{"result": ...}`를 해제하고, market-calendar는 isOpen 필드가 없어 정규장
시각([start,end)) 비교로 개장을 판정한다.

파싱 실패 시 정책: **조용히 스킵하지 않고 `TossError`로 중단**한다. holdings를 부분/빈 값으로
반환하면 화이트리스트(개선14) 제외셋 X가 미완성돼 사용자 수동 보유가 매매 대상이 될 수 있다
(bypass). 중단은 fail-safe(주문 미발생)이고, TossError는 개선10 예외체계·cron 자동화가 잡는다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from execution.interface import OrderIntent

from .client import TossClient
from .errors import TossError

# market-calendar 시각 포맷: "2026-07-20T22:30:00.000+09:00" (밀리초 3자리 + tz offset).
# 3.10 datetime.fromisoformat는 이 포맷을 못 읽어 strptime으로 파싱한다.
_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"


def _result(resp):
    """토스 응답 공통 래퍼 `{"result": ...}`를 해제. 래퍼가 없으면 원본 반환."""
    if isinstance(resp, dict) and "result" in resp:
        return resp["result"]
    return resp


def _num(value, field: str) -> float:
    """숫자 문자열 → float. 실패 시 조용히 넘기지 않고 TossError(진단 가능·automation이 잡음)."""
    try:
        return float(value)
    except (ValueError, TypeError):
        raise TossError(f"[응답 파싱] {field} 숫자 변환 실패: {value!r}")


def _regular_market_open(resp, now: datetime) -> bool:
    """market-calendar 응답의 오늘 정규장 구간 [start, end) 안이면 True.

    시각은 모두 tz 포함(+09:00). isOpen 불린 필드가 없어 시각 비교로 판정한다.
    파싱 불가·필드 누락이면 보수적으로 닫힘(False)."""
    result = _result(resp)
    if not isinstance(result, dict):
        return False
    regular = (result.get("today") or {}).get("regularMarket") or {}
    start, end = regular.get("startTime"), regular.get("endTime")
    if not (start and end):
        return False
    try:
        t0 = datetime.strptime(start, _TS_FMT)
        t1 = datetime.strptime(end, _TS_FMT)
    except (ValueError, TypeError):
        return False
    return t0 <= now < t1


class TossBroker:
    def __init__(self, client: TossClient):
        self.client = client

    def get_holdings(self) -> dict[str, float]:
        """symbol -> 보유 주식수. 화이트리스트 X 동결의 근거이므로 부분 반환 금지:
        모양이 예상과 다르거나 항목 필드가 누락/파싱불가면 TossError로 중단한다."""
        result = _result(self.client.get("/api/v1/holdings"))
        if not isinstance(result, dict):
            raise TossError(f"[응답 파싱] holdings 예상 밖 형태: {type(result).__name__}")
        items = result.get("items", [])
        if not isinstance(items, list):
            raise TossError("[응답 파싱] holdings.items가 리스트가 아님")
        out: dict[str, float] = {}
        for it in items:  # result.items[]: symbol, quantity(str)
            sym, qty = it.get("symbol"), it.get("quantity")
            if sym is None or qty is None:
                raise TossError(f"[응답 파싱] holdings 항목에 symbol/quantity 누락: {it}")
            out[str(sym)] = _num(qty, "holdings.quantity")
        return out

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        resp = self.client.get("/api/v1/prices", params={"symbols": ",".join(symbols)})
        items = _result(resp)
        if not isinstance(items, list):
            raise TossError(f"[응답 파싱] prices 예상 밖 형태: {type(items).__name__}")
        out: dict[str, float] = {}
        for it in items:  # result[]: symbol, lastPrice(str)
            sym, price = it.get("symbol"), it.get("lastPrice")
            if sym is None or price is None:
                continue  # 특정 심볼 미제공은 스킵(sizing에서 가격 없는 종목은 자연 제외)
            out[str(sym)] = _num(price, "prices.lastPrice")
        return out

    def get_buying_power_usd(self) -> float:
        # currency 쿼리파람 필수(없으면 400). USD 가용 현금 = result.cashBuyingPower.
        resp = self.client.get("/api/v1/buying-power", params={"currency": "USD"})
        result = _result(resp)
        if not isinstance(result, dict) or result.get("cashBuyingPower") is None:
            return 0.0  # 알 수 없으면 보수적 0 (매수 안 함)
        return _num(result["cashBuyingPower"], "buying-power.cashBuyingPower")

    def is_market_open(self) -> bool:
        resp = self.client.get("/api/v1/market-calendar/US", need_account=False)
        return _regular_market_open(resp, datetime.now(timezone.utc))

    def place(self, intent: OrderIntent) -> dict:
        # 모든 숫자 필드는 문자열(API 규약)
        body = {
            "symbol": intent.symbol,
            "side": intent.side,
            "orderType": "MARKET",
            "clientOrderId": intent.client_order_id,  # 개선5 멱등키
        }
        if intent.kind == "amount":
            body["orderAmount"] = f"{intent.value}"   # 소수점 매수(US MARKET 전용)
        else:
            body["quantity"] = f"{intent.value}"      # 소수점 매도
        return self.client.post("/api/v1/orders", json_body=body)
