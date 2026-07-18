"""TossBroker — execution.interface.Broker의 토스 구체 구현(transport glue).

TossClient(HTTP)를 감싸 리밸런싱 로직에 브로커 능력을 제공한다.
⚠️ 응답 JSON 필드명은 openapi.json에 스키마가 없어 **Phase 0 실측으로 확정 필요**.
   아래 파싱은 방어적 가정(FIELD_* 상수) — 키 승인 후 실제 응답으로 교체한다.
"""
from __future__ import annotations

from execution.interface import OrderIntent

from .client import TossClient


class TossBroker:
    def __init__(self, client: TossClient):
        self.client = client

    def get_holdings(self) -> dict[str, float]:
        resp = self.client.get("/api/v1/holdings")
        items = resp.get("holdings", []) if isinstance(resp, dict) else (resp or [])
        out: dict[str, float] = {}
        for it in items:  # ⚠️ Phase 0: 필드명(symbol/quantity) 실측 확정
            sym, qty = it.get("symbol"), it.get("quantity")
            if sym is not None and qty is not None:
                out[str(sym)] = float(qty)
        return out

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        resp = self.client.get("/api/v1/prices", params={"symbols": ",".join(symbols)})
        items = resp.get("prices", []) if isinstance(resp, dict) else (resp or [])
        out: dict[str, float] = {}
        for it in items:  # ⚠️ Phase 0: 필드명(symbol/price) 실측 확정
            sym, price = it.get("symbol"), it.get("price")
            if sym is not None and price is not None:
                out[str(sym)] = float(price)
        return out

    def get_buying_power_usd(self) -> float:
        resp = self.client.get("/api/v1/buying-power")
        # ⚠️ Phase 0: USD 매수가능금액 필드 실측 확정
        for k in ("usdBuyingPower", "usd", "USD"):
            if isinstance(resp, dict) and resp.get(k) is not None:
                return float(resp[k])
        return 0.0

    def is_market_open(self) -> bool:
        resp = self.client.get("/api/v1/market-calendar/US", need_account=False)
        # ⚠️ Phase 0: 개장 여부 필드 실측 확정
        for k in ("isOpen", "open", "regularOpen"):
            if isinstance(resp, dict) and k in resp:
                return bool(resp[k])
        return False

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
