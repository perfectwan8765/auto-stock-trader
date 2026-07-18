"""Phase 0-2: 계좌 목록 조회 → X-Tossinvest-Account 값 확보.

실행:  python scripts/toss_probe/01_accounts.py
결과:  응답에서 계좌식별자를 찾아 .env의 TOSS_ACCOUNT에 채운다.
검증:  이후 holdings 200 반환 (05_holdings.py)
"""
import _bootstrap  # noqa: F401

import json

from toss.client import TossClient
from toss.config import load_config


def main() -> None:
    cfg = load_config()  # 이 단계에선 account 아직 불필요
    client = TossClient(cfg)
    # 계좌 목록은 계좌식별자 없이 호출 가능해야 한다.
    accounts = client.get("/api/v1/accounts", need_account=False)

    print("📋 GET /api/v1/accounts 응답:")
    print(json.dumps(accounts, indent=2, ensure_ascii=False))
    print(
        "\n👉 위 응답에서 계좌식별자(계좌번호/식별키)를 찾아 .env의 TOSS_ACCOUNT에 넣으세요."
        "\n   응답 필드명이 문서와 다를 수 있으니 실제 키 이름을 phase0-findings.md에 기록하세요."
    )


if __name__ == "__main__":
    _bootstrap.cli(main)
