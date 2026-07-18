"""Phase 0-3(문서/API 확인 부분): 대상 종목의 시장·통화·상장상태 조회 +
미국 장운영시간(market-calendar) 확인.

실행:  python scripts/toss_probe/02_stock_info.py AAPL MSFT NVDA
전제:  .env에 TOSS_ACCOUNT 설정 (계좌 헤더 필요할 수 있음)
용도:  소수점 매수 실측(04_place_test_order.py) 전에 종목 자체가 US/거래가능인지 확인.
"""
import _bootstrap  # noqa: F401

import json
import sys

from toss.client import TossApiError, TossClient
from toss.config import load_config


def main() -> None:
    symbols = sys.argv[1:] or ["AAPL"]
    # market-calendar/stocks는 MARKET_DATA·STOCK 그룹으로 계좌 헤더가 필요 없을 가능성이 크다.
    # 0-3(종목 확인)은 0-2(계좌식별자 확보)보다 먼저 할 수 있어야 하므로 계좌를 강제하지 않는다.
    # (만약 401/헤더 요구 에러가 나면 need_account=True 로 바꾸고 TOSS_ACCOUNT를 채운다.)
    cfg = load_config(require_account=False)
    client = TossClient(cfg)

    print("🗓  GET /api/v1/market-calendar/US")
    try:
        cal = client.get("/api/v1/market-calendar/US", need_account=False)
        print(json.dumps(cal, indent=2, ensure_ascii=False))
    except TossApiError as e:
        print(f"   조회 실패: {e}")

    for sym in symbols:
        print(f"\n📈 GET /api/v1/stocks (symbol={sym})")
        try:
            info = client.get("/api/v1/stocks", params={"symbol": sym}, need_account=False)
            print(json.dumps(info, indent=2, ensure_ascii=False))
        except TossApiError as e:
            print(f"   조회 실패: {e}")

    print(
        "\n👉 각 종목의 market/currency/상장상태를 phase0-findings.md에 기록하세요."
        "\n   소수점(금액주문) 실제 가능 여부는 04_place_test_order.py로 실측합니다."
    )


if __name__ == "__main__":
    _bootstrap.cli(main)
