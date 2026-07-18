"""환경변수 로딩. 자격증명은 .env에서만 읽고 코드에 박지 않는다."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .errors import TossConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # src/toss/config.py -> 루트
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    base_url: str
    account: str  # X-Tossinvest-Account. Phase 0-2 전에는 빈 문자열일 수 있음.

    @property
    def has_account(self) -> bool:
        return bool(self.account)


def load_config(require_account: bool = False) -> Config:
    """.env에서 설정을 읽는다. 필수 값이 없으면 명확한 에러로 안내한다."""
    client_id = os.getenv("TOSS_CLIENT_ID", "").strip()
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip()
    base_url = os.getenv("TOSS_BASE_URL", "https://openapi.tossinvest.com").strip().rstrip("/")
    account = os.getenv("TOSS_ACCOUNT", "").strip()

    missing = []
    if not client_id:
        missing.append("TOSS_CLIENT_ID")
    if not client_secret:
        missing.append("TOSS_CLIENT_SECRET")
    if require_account and not account:
        missing.append("TOSS_ACCOUNT")

    if missing:
        raise TossConfigError(
            "[설정 오류] .env에 다음 값이 없습니다: "
            + ", ".join(missing)
            + "\n  .env.example을 복사해 .env를 만들고 값을 채우세요.\n"
            + "  TOSS_ACCOUNT는 Phase 0-2(01_accounts.py) 실행 후 얻습니다."
        )

    return Config(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        account=account,
    )
