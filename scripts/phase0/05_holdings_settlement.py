"""Phase 0-2 검증(holdings 200) + Phase 0-6(T+N 결제주기 관찰).

용도 1) 계좌 헤더 검증:  python scripts/phase0/05_holdings_settlement.py
용도 2) 결제주기 관찰:   소액 매도 직후 이 스크립트를 날짜별로 반복 실행하며
        buying-power(USD 가용액) 반영 시점을 기록 → 매도대금이 며칠 뒤 매수가능해지는지(T+N) 확인.
"""
import _bootstrap  # noqa: F401

import json
import time

from toss.client import TossClient
from toss.config import load_config


def main() -> None:
    cfg = load_config(require_account=True)
    client = TossClient(cfg)

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"⏰ 관찰 시각: {stamp}\n")

    print("📦 GET /api/v1/holdings")
    holdings = client.get("/api/v1/holdings")
    print(json.dumps(holdings, indent=2, ensure_ascii=False))
    print("→ 200 반환되면 Phase 0-2(계좌 헤더) 검증 통과\n")

    print("💰 GET /api/v1/buying-power (T+N 반영 관찰용)")
    bp = client.get("/api/v1/buying-power")
    print(json.dumps(bp, indent=2, ensure_ascii=False))
    print(
        "\n👉 매도 후 이 스크립트를 매일 실행하며 USD 가용액 증가 시점을 phase0-findings.md에 기록."
        "\n   (매도일 대비 며칠 뒤 반영되는지 = 미국주식 결제주기 T+N)"
    )


if __name__ == "__main__":
    main()
