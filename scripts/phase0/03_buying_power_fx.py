"""Phase 0-5: 매수가능금액(KRW/USD) + 환율 조회 → 자동환전 여부 판단.

실행:  python scripts/phase0/03_buying_power_fx.py
판단:  buying-power가 USD 매수가능금액을 반환하면 통합증거금(자동환전) 가능성.
       USD가 0/미노출이면 선환전 필요 → 발주 전 환전 로직 필요.
"""
import _bootstrap  # noqa: F401

import json

from toss.client import TossApiError, TossClient
from toss.config import load_config


def main() -> None:
    cfg = load_config(require_account=True)
    client = TossClient(cfg)

    print("💰 GET /api/v1/buying-power")
    bp = client.get("/api/v1/buying-power")
    print(json.dumps(bp, indent=2, ensure_ascii=False))

    print("\n💱 GET /api/v1/exchange-rate")
    try:
        fx = client.get("/api/v1/exchange-rate")
        print(json.dumps(fx, indent=2, ensure_ascii=False))
    except TossApiError as e:
        print(f"   조회 실패: {e}")

    print(
        "\n👉 buying-power 응답에 USD 매수가능액이 있는지 확인해 phase0-findings.md에 기록:"
        "\n   - USD 잔액 노출 O → 자동환전(통합증거금) 가정, 발주 전 환전 불필요할 수 있음"
        "\n   - USD 0 / KRW만 → 선환전 필요 (Phase 5에서 환전 처리 로직 추가)"
    )


if __name__ == "__main__":
    main()
