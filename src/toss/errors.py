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
    """토스 OpenAPI HTTP 4xx/5xx 응답.

    개선13 일관: 비-JSON 응답 본문(resp.text, 임의·잠재 누설)은 메시지에 덤프하지 않는다.
    구조화 에러(code/message)만 메시지에 노출. 원문은 `self.body`로 프로그래매틱 접근만 허용.
    """

    def __init__(self, method: str, path: str, status: int, body: Any):
        self.status = status
        self.body = body
        code, msg = "", ""
        if isinstance(body, dict):
            code = body.get("code") or body.get("error") or ""
            msg = body.get("message") or body.get("error_description") or ""
        self.code = code
        detail = f" {code}{': ' + msg if msg else ''}".rstrip()
        super().__init__(f"{method} {path} -> {status}{detail}")
