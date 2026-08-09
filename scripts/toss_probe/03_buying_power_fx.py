"""Phase 0-5: 매수가능금액(KRW/USD) + 환율 조회 → 자동환전 여부 판단.

실행:  python scripts/toss_probe/03_buying_power_fx.py
판단:  USD cashBuyingPower가 있으면 통합증거금(자동환전) 가능성. USD 0/KRW만이면 선환전 필요.
실측(2026-07-20): buying-power는 `currency`, exchange-rate는 `baseCurrency`+`quoteCurrency`가
       필수 쿼리파람(없으면 400). 자동환전은 안 됨 → 봇 가동 전 KRW→USD 선환전 필요로 확정.
"""
import _bootstrap  # noqa: F401

import json

from toss.client import TossApiError, TossClient
from toss.config import load_config


def main() -> None:
    cfg = load_config(require_account=True)
    client = TossClient(cfg)

    for cur in ("USD", "KRW"):
        print(f"💰 GET /api/v1/buying-power?currency={cur}")
        bp = client.get("/api/v1/buying-power", params={"currency": cur})
        print(json.dumps(bp, indent=2, ensure_ascii=False))

    print("\n💱 GET /api/v1/exchange-rate?baseCurrency=USD&quoteCurrency=KRW")
    try:
        fx = client.get("/api/v1/exchange-rate",
                        params={"baseCurrency": "USD", "quoteCurrency": "KRW"})
        print(json.dumps(fx, indent=2, ensure_ascii=False))
    except TossApiError as e:
        print(f"   조회 실패: {e}")

    print(
        "\n👉 result.cashBuyingPower 확인:"
        "\n   - USD>0 노출 → 자동환전(통합증거금) 가정"
        "\n   - USD 0 / KRW만 → 선환전 필요 (실측 결과가 이 케이스)"
    )


if __name__ == "__main__":
    _bootstrap.cli(main)
