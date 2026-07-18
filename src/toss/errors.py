"""토스 어댑터 예외 계열 (개선10).

라이브러리는 `SystemExit` 대신 `TossError` 계열을 던진다. `SystemExit` 종료 변환은
CLI 경계(`_bootstrap.cli`)에서만 → cron 자동화(Phase 5)가 서킷브레이커·kill switch·부분
이월로 잡을 수 있게 하기 위함.
"""
from __future__ import annotations

from typing import Any


class TossError(Exception):
    """토스 어댑터 공통 베이스."""


class TossConfigError(TossError):
    """설정·계좌식별자 누락 등 구성 오류."""


class TossAuthError(TossError):
    """OAuth 토큰 발급 실패."""


class TossApiError(TossError):
    """토스 OpenAPI HTTP 4xx/5xx 응답."""

    def __init__(self, method: str, path: str, status: int, body: Any):
        self.status = status
        self.body = body
        # openapi.json 에러 스키마가 code/message를 준다는 가정, 없으면 원문
        code = ""
        if isinstance(body, dict):
            code = body.get("code") or body.get("error") or ""
        self.code = code
        super().__init__(f"{method} {path} -> {status} {code}: {body}")
