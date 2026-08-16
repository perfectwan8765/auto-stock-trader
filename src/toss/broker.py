"""TossBroker — execution.interface.Broker의 토스 구체 구현(transport glue).

TossClient(HTTP)를 감싸 리밸런싱 로직에 브로커 능력을 제공한다.
응답 필드는 Phase 0(2026-07-20) 실측으로 확정 — 구조는 tests/test_broker.py 픽스처가 고정한다.
공통 래퍼 `{"result": ...}`를 해제하고, market-calendar는 isOpen 필드가 없어 정규장
시각([start,end)) 비교로 개장을 판정한다.

파싱 실패 시 정책: **조용히 스킵하지 않고 `TossError`로 중단**한다. holdings를 부분/빈 값으로
반환하면 화이트리스트 제외셋 X가 미완성돼 사용자 수동 보유가 매매 대상이 될 수 있다.
중단은 fail-safe(주문 미발생)이고, TossError는 CLI·cron 자동화가 잡는다.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from execution.errors import BrokerMarketClosed, BrokerRateLimited, OrderRejected
from execution.interface import AccountSnapshot, Fill, OrderIntent

from .client import TossClient
from .errors import TossApiError, TossError

# market-calendar 시각 포맷: "2026-07-20T22:30:00.000+09:00" (밀리초 3자리 + tz offset).
# 3.10 datetime.fromisoformat는 이 포맷을 못 읽어 strptime으로 파싱한다.
_TS_FMT = "%Y-%m-%dT%H:%M:%S.%f%z"

# 토스 에러코드 → execution의 정규화된 실패 어휘. 이 표가 **어댑터에 있다는 것**이 요점이다:
# 러너가 토스 코드 문자열을 알면 두 번째 브로커를 붙일 때 러너를 고쳐야 한다.
_RATE_LIMIT_CODES = {"rate-limit-exceeded"}
_MARKET_CLOSED_CODES = {"amount-order-outside-regular-hours", "order-hours-closed"}
_ORDER_REJECT_CODES = {"insufficient-buying-power", "market-not-supported-for-stock"}


def _normalized(exc: TossApiError):
    """TossApiError를 execution 예외로 번역. 미분류면 원본을 그대로 돌려준다(전파)."""
    code = getattr(exc, "code", "") or ""
    if code in _RATE_LIMIT_CODES:
        return BrokerRateLimited(str(exc))
    if code in _MARKET_CLOSED_CODES:
        err = BrokerMarketClosed(str(exc))
        err.code = code
        return err
    if code in _ORDER_REJECT_CODES:
        return OrderRejected(code, str(exc))
    return exc


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


def _opt_num(value, field: str) -> float | None:
    """있으면 float, 없으면 None. 토스는 숫자를 문자열로 주는데 그대로 흘리면
    슬리피지(체결가 − 결정가) 계산이 TypeError로 죽는다."""
    return None if value is None else _num(value, field)


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
    def __init__(self, client: TossClient, read_sleep_s: float = 1.0,
                 read_retries: int = 3, read_backoff_s: float = 2.0):
        self.client = client
        self.read_sleep_s = read_sleep_s      # ACCOUNT 그룹 1 TPS — 읽기 사이 간격
        self.read_retries = read_retries
        self.read_backoff_s = read_backoff_s

    def _get(self, path: str, **kw):
        """모든 읽기가 지나는 경로. 에러코드를 번역하고 속도제한은 백오프 재시도한다.

        읽기 하나하나에 번역이 빠지면 raw TossApiError가 러너를 뚫어, 어댑터에 백오프가
        있는데도 리밸 전체가 주문 한 건 없이 죽는다.
        """
        for attempt in range(self.read_retries + 1):
            try:
                return self.client.get(path, **kw)
            except TossApiError as exc:
                err = _normalized(exc)
                if isinstance(err, BrokerRateLimited) and attempt < self.read_retries:
                    time.sleep(self.read_backoff_s * (attempt + 1))
                    continue
                raise err from exc
        raise AssertionError("unreachable")

    def get_holdings_raw(self) -> list[dict]:
        """holdings 응답 항목을 파싱 없이 그대로 반환.

        get_holdings는 symbol·quantity만 취하는데, 실제 비용은 `cost.commission`에 있다
        (주문 응답의 commission은 전부 0이다 — Phase 0 실측). 비용 캘리브레이션의 입력.

        Returns:
            result.items[] 원소를 그대로 담은 리스트.
        Raises:
            TossError: 응답 형태가 예상과 다를 때.
        """
        result = _result(self._get("/api/v1/holdings"))
        if not isinstance(result, dict):
            raise TossError(f"[응답 파싱] holdings 예상 밖 형태: {type(result).__name__}")
        items = result.get("items", [])
        if not isinstance(items, list):
            raise TossError("[응답 파싱] holdings.items가 리스트가 아님")
        return items

    def snapshot(self, target_symbols: list[str]) -> AccountSnapshot:
        """계좌 상태를 한 시점에 모아 온다. holdings는 **1회만** 조회한다.

        Args:
            target_symbols: 목표 비중에 있는 심볼. 가격은 이 집합 ∪ 보유 종목에 대해 받는다.
        """
        items = self.get_holdings_raw()
        holdings: dict[str, float] = {}
        daily_pnl: dict[str, float] = {}
        for it in items:
            sym, qty = it.get("symbol"), it.get("quantity")
            if sym is None or qty is None:
                raise TossError(f"[응답 파싱] holdings 항목에 symbol/quantity 누락: {it}")
            holdings[str(sym)] = _num(qty, "holdings.quantity")
            amount = (it.get("dailyProfitLoss") or {}).get("amount")
            if amount is not None:
                daily_pnl[str(sym)] = _num(amount, "holdings.dailyProfitLoss.amount")

        symbols = sorted(set(target_symbols) | set(holdings))
        self._pause()
        prices = self.get_prices(symbols) if symbols else {}
        self._pause()
        return AccountSnapshot(holdings=holdings, prices=prices,
                               buying_power_usd=self.get_buying_power_usd(),
                               daily_pnl=daily_pnl)

    def _pause(self) -> None:
        if self.read_sleep_s > 0:
            time.sleep(self.read_sleep_s)

    def get_sellable(self, symbols: list[str]) -> dict[str, float]:
        """심볼별 매도가능수량. 호출 사이에 간격을 두고 속도제한은 재시도한다.

        토스는 단건 조회만 받아 심볼 수만큼 왕복한다. ACCOUNT 그룹은 한도가 낮아
        (실측 1 TPS) 연속 호출하면 속도제한에 걸린다.
        """
        out: dict[str, float] = {}
        for n, sym in enumerate(symbols):
            if n and self.read_sleep_s > 0:
                time.sleep(self.read_sleep_s)
            out[sym] = self.get_sellable_quantity(sym)
        return out

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        resp = self._get("/api/v1/prices", params={"symbols": ",".join(symbols)})
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

    def get_prices_raw(self, symbols: list[str]) -> list[dict]:
        """prices 응답 항목을 파싱 없이 그대로 반환.

        get_prices는 lastPrice만 취하므로 호가(bid/ask) 노출 여부를 알 수 없다.
        단계 0 집행가능성 게이트에서 원 응답 필드를 확인하는 용도.

        Args:
            symbols: 조회할 심볼 목록.
        Returns:
            result[] 원소를 그대로 담은 리스트. 미제공 심볼은 빠진다.
        Raises:
            TossError: 응답이 리스트가 아닐 때.
        """
        items = _result(self._get("/api/v1/prices", params={"symbols": ",".join(symbols)}))
        if not isinstance(items, list):
            raise TossError(f"[응답 파싱] prices 예상 밖 형태: {type(items).__name__}")
        return items

    def get_stock_info(self, symbols: list[str]) -> dict[str, dict]:
        """symbol -> 종목 메타(market·securityType·status·listDate·delistDate 등).

        Phase 0-3 실측 엔드포인트. 취급 여부(=응답에 존재하는가), 거래소(OTC 배제),
        상장/폐지일 확인에 쓴다. 미취급 심볼은 응답에서 빠지므로 결과에 없는 것이 곧 미취급 신호.

        Args:
            symbols: 조회할 심볼 목록.
        Returns:
            symbol -> 원 응답 dict. 미취급 심볼은 키 자체가 없다.
        Raises:
            TossError: 응답이 리스트가 아닐 때.
        """
        items = _result(self._get("/api/v1/stocks", params={"symbols": ",".join(symbols)}))
        if not isinstance(items, list):
            raise TossError(f"[응답 파싱] stocks 예상 밖 형태: {type(items).__name__}")
        return {str(it["symbol"]): it for it in items if it.get("symbol") is not None}

    def get_buying_power_usd(self) -> float:
        # currency 쿼리파람 필수(없으면 400). USD 가용 현금 = result.cashBuyingPower.
        resp = self._get("/api/v1/buying-power", params={"currency": "USD"})
        result = _result(resp)
        if not isinstance(result, dict) or result.get("cashBuyingPower") is None:
            return 0.0  # 알 수 없으면 보수적 0 (매수 안 함)
        return _num(result["cashBuyingPower"], "buying-power.cashBuyingPower")

    def get_sellable_quantity(self, symbol: str) -> float:
        # T+N 미결제분을 제외한 실제 매도가능수량. 보유수량과 다를 수 있어 매도 상한으로 쓴다.
        try:
            resp = self._get("/api/v1/sellable-quantity", params={"symbol": symbol})
        except TossApiError as exc:
            raise _normalized(exc) from exc
        result = _result(resp)
        if not isinstance(result, dict) or result.get("sellableQuantity") is None:
            return 0.0  # 알 수 없으면 보수적 0 (매도 안 함)
        return _num(result["sellableQuantity"], "sellable-quantity.sellableQuantity")

    def get_order(self, order_id: str) -> dict:
        """주문 단건 조회. 체결가(`execution.averageFilledPrice`)의 유일한 출처다.

        발주 응답에는 체결 정보가 없고 `{orderId, clientOrderId}`뿐이라, 슬리피지를 재려면
        이 조회가 필요하다. 시장가 주문이라 발주 직후에는 아직 미체결일 수 있다.

        Returns:
            result dict. 미체결이면 `execution`이 없거나 비어 있다.
        Raises:
            TossError: 응답이 dict가 아닐 때.
        """
        result = _result(self._get(f"/api/v1/orders/{order_id}"))
        if not isinstance(result, dict):
            raise TossError(f"[응답 파싱] orders/{{id}} 예상 밖 형태: {type(result).__name__}")
        return result

    def is_market_open(self) -> bool:
        resp = self._get("/api/v1/market-calendar/US", need_account=False)
        return _regular_market_open(resp, datetime.now(timezone.utc))

    def place(self, intent: OrderIntent) -> dict:
        # 모든 숫자 필드는 문자열(API 규약)
        body = {
            "symbol": intent.symbol,
            "side": intent.side,
            "orderType": "MARKET",
            "clientOrderId": intent.client_order_id,  # 멱등키
        }
        if intent.kind == "amount":
            body["orderAmount"] = f"{intent.value}"   # 소수점 매수(US MARKET 전용)
        else:
            body["quantity"] = f"{intent.value}"      # 소수점 매도
        try:
            resp = self.client.post("/api/v1/orders", json_body=body)
        except TossApiError as exc:
            raise _normalized(exc) from exc
        # POST가 이미 성공했다 — 주문은 브로커에 살아 있다. 여기서 예외를 던지면 러너가
        # placed에 담지 못해 화이트리스트에도 안 들어가고, 그 종목은 청산도 trim도 안 되면서
        # 다음 사이클에 다시 매수된다. 추적 불가는 빈 문자열로 알리고 기록은 남긴다.
        result = _result(resp)
        order_id = result.get("orderId") if isinstance(result, dict) else None
        return str(order_id) if order_id else ""

    def get_fill(self, order_id: str) -> Fill | None:
        """체결 실측. 미체결이면 None.

        발주 응답에는 체결 정보가 없고 `{orderId, clientOrderId}`뿐이라 슬리피지를 재려면
        이 조회가 필요하다. 응답 필드명(camelCase)의 해석은 **여기가 유일한 지점**이다 —
        러너가 알면 스키마가 틀렸을 때 검증할 수 없는 위치에 파싱이 놓인다.

        Returns:
            체결 정보가 있으면 `Fill`, 아직 미체결이면 `None`.
        """
        ex = (self.get_order(order_id) or {}).get("execution") or {}
        if not ex:
            return None
        return Fill(
            filled_quantity=_opt_num(ex.get("filledQuantity"), "execution.filledQuantity"),
            avg_filled_price=_opt_num(ex.get("averageFilledPrice"), "execution.averageFilledPrice"),
            filled_amount=_opt_num(ex.get("filledAmount"), "execution.filledAmount"),
            commission=_opt_num(ex.get("commission"), "execution.commission"),
            tax=_opt_num(ex.get("tax"), "execution.tax"),
            filled_at=ex.get("filledAt"),
            settlement_date=ex.get("settlementDate"),
        )
