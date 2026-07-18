"""Phase 0-3(실측) + 0-4(최소금액) + 0-7(rate-limit) 통합 실측 스크립트.

⚠️ 이 스크립트는 실제 계좌에 진짜 주문을 넣습니다(실제 돈). 안전장치:
  - 기본은 DRY-RUN. 실제 발주하려면 --confirm 필수.
  - 금액은 --amount 로 명시(기본값 없음). 최소금액 실측 목적이면 아주 작게(예: 1).
  - orderAmount 매수는 미국 정규장에만 가능 → 먼저 market-calendar 확인.

용도별 판독:
  - 성공        → 그 종목 소수점 매수 가능, 그 금액이 최소금액 이상.
  - market-not-supported-for-stock → 그 종목 소수점 불가 (유니버스에서 제외).
  - 최소금액 미달 관련 에러 → 메시지에서 최소 주문금액 확인 (Phase 0-4 산출물).
  - amount-order-outside-regular-hours → 정규장 아님, 정규장 시간에 재시도.

실행 예:
  # 1) 먼저 발주계획만 (안전)
  python scripts/toss_probe/04_place_test_order.py --symbol AAPL --amount 1
  # 2) 정규장 시간에 실제 발주
  python scripts/toss_probe/04_place_test_order.py --symbol AAPL --amount 1 --confirm
"""
import _bootstrap  # noqa: F401

import argparse
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from toss.client import TossApiError, TossClient
from toss.config import load_config

# 미국 정규장은 KST 자정을 가로지르므로(밤 22:30/23:30 → 익일 05:00/06:00),
# 멱등키는 로컬 벽시계 날짜가 아니라 '미국 동부 거래일'로 고정해야 세션 중 자정을
# 넘겨 재실행해도 같은 키가 나온다. (개선5: 크래시 후 재개해도 중복주문 방지)
US_MARKET_TZ = ZoneInfo("America/New_York")


def us_trading_date() -> str:
    """현재 시점의 미국 동부 거래일(YYYYMMDD)."""
    return datetime.now(US_MARKET_TZ).strftime("%Y%m%d")


def make_client_order_id(symbol: str, side: str, amount: str, run_date: str) -> str:
    """결정적 멱등키 (개선5와 동일 원리). 같은 거래일/종목/side/금액이면 동일 → 중복주문 방지.

    run_date는 US 거래일(YYYYMMDD). 리밸런싱일자를 명시적으로 넘기면 재실행·크래시
    복구 시에도 동일 키가 재현된다.
    """
    raw = f"{run_date}:{symbol}:{side}:{amount}"
    return "phase0-" + hashlib.sha1(raw.encode()).hexdigest()[:20]


def check_regular_hours(client: TossClient) -> None:
    print("🗓  정규장 확인: GET /api/v1/market-calendar/US")
    try:
        cal = client.get("/api/v1/market-calendar/US")
        print(json.dumps(cal, indent=2, ensure_ascii=False))
    except TossApiError as e:
        print(f"   (확인 실패, 계속 진행하되 주의: {e})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="AAPL")
    ap.add_argument("--amount", required=True, help="주문 금액(USD), 문자열로 전송됨. 예: 1")
    ap.add_argument("--confirm", action="store_true", help="실제 발주. 없으면 dry-run.")
    ap.add_argument("--date", default=None,
                    help="멱등키에 쓸 US 거래일(YYYYMMDD). 생략 시 현재 미국 동부 거래일.")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    amount = str(args.amount)  # 모든 숫자 필드는 문자열
    side = "BUY"
    run_date = args.date or us_trading_date()
    client_order_id = make_client_order_id(symbol, side, amount, run_date)

    body = {
        "symbol": symbol,
        "side": side,
        "orderType": "MARKET",
        "orderAmount": amount,
        "clientOrderId": client_order_id,
    }

    print("=" * 60)
    print("주문 body:")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    print("=" * 60)

    if not args.confirm:
        print("\n🟡 DRY-RUN: 실제 발주하지 않았습니다.")
        print("   실제 발주하려면 정규장 시간에 --confirm 을 추가하세요.")
        return

    cfg = load_config(require_account=True)
    client = TossClient(cfg)
    check_regular_hours(client)

    print(f"\n🔴 실제 발주: {symbol} ${amount} (clientOrderId={client_order_id})")
    try:
        resp = client.post("/api/v1/orders", json_body=body)
        print("✅ 주문 접수:")
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        print("\n👉 응답의 주문 id를 기록하세요 (Phase 0-6 결제주기 추적용).")
    except TossApiError as e:
        print(f"❌ 주문 거부: status={e.status} code={e.code}")
        print(json.dumps(e.body, indent=2, ensure_ascii=False) if isinstance(e.body, (dict, list)) else e.body)
        print("\n👉 code를 phase0-findings.md에 기록: "
              "market-not-supported-for-stock=소수점불가 / 최소금액 관련=0-4 산출물 / "
              "amount-order-outside-regular-hours=정규장 재시도")
    except requests.RequestException as e:
        # 네트워크 오류(타임아웃·연결끊김 등): 주문 접수 여부 불확실.
        print(f"⚠️  네트워크 오류로 주문 결과 불확실: {e}")
        print("   👉 실제 발주(--confirm)였다면 GET /api/v1/orders 로 체결 여부를 반드시 확인하세요.")
        print("   (같은 clientOrderId로 재시도하면 멱등성으로 중복주문은 방지됩니다.)")

    # 0-7: 주문 API 응답 헤더에서 rate-limit 실측
    rl = client.rate_limit_headers()
    print("\n⏱  주문 API rate-limit 관련 응답 헤더 (Phase 0-7):")
    print(json.dumps(rl, indent=2, ensure_ascii=False) if rl else "   (rate-limit 헤더 없음 — 전체 헤더를 확인하세요)")
    if not rl:
        print("   전체 응답 헤더:")
        print(json.dumps(client.last_headers, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _bootstrap.cli(main)
