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
# TossApiError는 여기서도 쓰지만(2xx 아닌 응답) toss_probe 4개가 `toss.client` 경유로
# 가져간다 — 지역 import로 내리면 그쪽이 깨진다.
from .errors import TossApiError, TossConfigError


class TossClient:
    """토스 OpenAPI HTTP 호출. 인증 헤더·계좌 헤더 부착과 401 재시도만 담당한다.

    응답 스키마 해석은 하지 않는다 — 그건 `TossBroker`의 일이다.
    """

    def __init__(self, cfg: Config, token_manager: TokenManager | None = None):
        """세션을 열지만 토큰은 아직 받지 않는다 — 첫 요청에서 받는다.

        Args:
            cfg: 접속 설정.
            token_manager: 토큰 관리자. 생략하면 `cfg`로 새로 만든다.
        """
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
        """요청 1회. 401이면 토큰을 강제 재발급해 **1회만** 재시도한다.

        Args:
            method: HTTP 메서드.
            path: `base_url` 뒤에 붙는 경로.
            need_account: 계좌 헤더가 필요한 API인가. MARKET_DATA·STOCK 그룹은 False.
            params: 쿼리 문자열.
            json_body: 요청 본문.
            timeout: 초 단위 타임아웃.
            _retry: 내부용 — 재시도 상한 표시. 호출부가 넘기지 않는다.
            _token: 내부용 — 재발급한 토큰을 직접 전달한다. 캐시를 다시 읽으면 거부된
                옛 토큰이 돌아올 수 있기 때문이다.

        Returns:
            파싱된 JSON. 본문이 JSON이 아니면 원문 문자열.

        Raises:
            TossApiError: 2xx가 아닌 응답.
            TossConfigError: 계좌 헤더가 필요한데 `TOSS_ACCOUNT`가 비었을 때.
        """
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
        """`request("GET", ...)` 단축. 키워드 인자는 그대로 전달된다."""
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> Any:
        """`request("POST", ...)` 단축. 키워드 인자는 그대로 전달된다."""
        return self.request("POST", path, **kw)

    def rate_limit_headers(self) -> dict[str, str]:
        """마지막 응답에서 rate-limit 관련 헤더만 추린다."""
        return {
            k: v
            for k, v in self.last_headers.items()
            if "rate" in k.lower() or "limit" in k.lower() or "remaining" in k.lower()
        }
