"""토스 OpenAPI HTTP 클라이언트.

- Authorization: Bearer {token} + X-Tossinvest-Account 헤더 자동 부착
- 응답 헤더 노출 (rate-limit 실측용, Phase 0-7)
- 에러코드 파싱해 알기 쉬운 예외로 변환
"""
from __future__ import annotations

from typing import Any

import requests

from .auth import TokenManager
from .config import Config
from .errors import TossApiError, TossConfigError  # noqa: F401  (TossApiError re-export: 기존 import 호환)


class TossClient:
    def __init__(self, cfg: Config, token_manager: TokenManager | None = None):
        self.cfg = cfg
        self.tokens = token_manager or TokenManager(cfg)
        self.session = requests.Session()
        self.last_headers: dict[str, str] = {}  # rate-limit 헤더 실측용 (Phase 0-7)

    def _headers(self, need_account: bool, token: str | None = None) -> dict[str, str]:
        # token을 받으면 그걸 쓴다. 401 재시도가 방금 재발급받은 토큰을 넘기기 위한 것 —
        # 캐시를 다시 읽으면 거부된 옛 토큰이 돌아올 수 있다(_write_cache는 조건부다).
        headers = {"Authorization": f"Bearer {token or self.tokens.get_token()}"}
        if need_account:
            if not self.cfg.has_account:
                raise TossConfigError(
                    "[설정 오류] 이 API는 X-Tossinvest-Account가 필요합니다.\n"
                    "  Phase 0-2(01_accounts.py)로 계좌식별자를 확인해 .env의 TOSS_ACCOUNT에 넣으세요."
                )
            headers["X-Tossinvest-Account"] = self.cfg.account
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        need_account: bool = True,
        params: dict | None = None,
        json_body: dict | None = None,
        timeout: int = 15,
        _retry: bool = False,
        _token: str | None = None,
    ) -> Any:
        url = f"{self.cfg.base_url}{path}"
        resp = self.session.request(
            method,
            url,
            headers=self._headers(need_account, _token),
            params=params,
            json=json_body,
            timeout=timeout,
        )
        self.last_headers = dict(resp.headers)
        # 개선11: 401(만료 토큰)이면 강제 재발급 후 1회만 재시도(_retry로 상한).
        # 401은 미처리 거부라 POST /orders 재시도도 안전(clientOrderId 멱등키 이중안전망).
        if resp.status_code == 401 and not _retry:
            # 재발급 토큰을 **직접 넘긴다.** 반환값을 버리고 캐시를 다시 읽으면,
            # _write_cache가 expires_in > 0 일 때만 쓰므로 응답에 expires_in이 없거나 0이면
            # 아직 유효한(파일 기준) 옛 항목이 돌아온다 — 서버가 이미 거부한 그 토큰이다.
            # 재시도도 401이 되고 _retry=True라 TossApiError로 끝나 401 복구가 영구 불능이 된다.
            fresh = self.tokens.get_token(force_refresh=True)
            return self.request(
                method, path, need_account=need_account, params=params,
                json_body=json_body, timeout=timeout, _retry=True, _token=fresh,
            )
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        if not (200 <= resp.status_code < 300):
            raise TossApiError(method, path, resp.status_code, body)
        return body

    def get(self, path: str, **kw) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> Any:
        return self.request("POST", path, **kw)

    def rate_limit_headers(self) -> dict[str, str]:
        """마지막 응답에서 rate-limit 관련 헤더만 추린다."""
        return {
            k: v
            for k, v in self.last_headers.items()
            if "rate" in k.lower() or "limit" in k.lower() or "remaining" in k.lower()
        }
