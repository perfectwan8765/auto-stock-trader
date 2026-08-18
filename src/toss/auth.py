"""OAuth2 client_credentials 토큰 발급 + expires_in 기준 파일 캐싱."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from execution.atomic import write_text_atomic

from .config import Config, PROJECT_ROOT
from .errors import TossAuthError

_CACHE_PATH = PROJECT_ROOT / ".cache" / "toss_token.json"
_EXPIRY_SKEW_SEC = 60  # 만료 직전 안전 마진


def _oauth_error_detail(resp: requests.Response) -> str:
    """개선13: 표준 OAuth error/error_description(비밀 아님)만 추출. 비-JSON이면 빈 문자열.
    resp.text 전체(임의 본문·잠재 누설)는 절대 노출하지 않는다.
    """
    try:
        body = resp.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    err = body.get("error") or body.get("code") or ""
    desc = body.get("error_description") or body.get("message") or ""
    if not (err or desc):
        return ""
    return f" ({err}{': ' + desc if desc else ''})"


class TokenManager:
    """OAuth client_credentials 토큰을 발급·캐시한다.

    캐시는 `expires_in` 기준으로만 유효를 판단한다 — 만료를 모르는 토큰은 캐시하지 않고,
    이미 있던 항목도 지운다. 파일은 만들어지는 순간부터 소유자 전용(0600)이다.
    """

    def __init__(self, cfg: Config, cache_path: Path = _CACHE_PATH):
        """네트워크를 건드리지 않는다. 발급은 `get_token` 첫 호출에서 일어난다.

        Args:
            cfg: `client_id`·`client_secret`·`base_url`을 담은 설정.
            cache_path: 토큰 캐시 파일. 다른 자격증명으로 발급된 항목은 무시된다.
        """
        self.cfg = cfg
        self.cache_path = cache_path

    def _load_cache_file(self) -> dict | None:
        """캐시 파일을 읽어 이 자격증명 것이면 반환. 만료 여부는 판단하지 않는다."""
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        # 이 자격증명으로 발급된 토큰인지 확인 (client_id 바뀌면 무효)
        if data.get("client_id") != self.cfg.client_id:
            return None
        return data

    def _read_cache(self) -> dict | None:
        """유효(만료 skew 이내 아님)한 캐시만 반환. get_token 재사용 판단용."""
        data = self._load_cache_file()
        if data is None:
            return None
        if data.get("expires_at", 0) - _EXPIRY_SKEW_SEC <= time.time():
            return None
        return data

    def token_ttl_seconds(self) -> int | None:
        """캐시된 토큰의 남은 유효시간(초). 없으면 None.
        만료 skew를 적용하지 않고 파일 값 그대로 — 캐싱 동작 확인용 공개 API.
        """
        data = self._load_cache_file()
        if data is None:
            return None
        return int(data.get("expires_at", 0) - time.time())

    def _write_cache(self, token: str, expires_in: int) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "client_id": self.cfg.client_id,
            "access_token": token,
            "expires_at": time.time() + expires_in,
        }
        # 상태 파일과 같은 헬퍼를 쓴다. mkstemp가 0600으로 만들고 os.replace가 그 모드를
        # 유지하므로 **만들어지는 순간부터** 소유자 전용이고, 동시에 원자적이다 —
        # write_text 후 chmod는 그 사이 토큰이 umask 기본 권한(보통 0644)으로 놓이고,
        # O_TRUNC로 직접 쓰면 쓰기가 실패했을 때 유효하던 옛 캐시가 빈 파일로 남는다.
        write_text_atomic(self.cache_path, json.dumps(payload))

    def _request_new(self) -> tuple[str, int]:
        url = f"{self.cfg.base_url}/oauth2/token"
        resp = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if resp.status_code != 200:
            # 개선13: resp.text(임의 본문·잠재 누설) 대신 표준 OAuth error 필드만 노출.
            raise TossAuthError(
                f"[인증 실패] POST /oauth2/token -> {resp.status_code}{_oauth_error_detail(resp)}"
            )
        body = resp.json()
        token = body.get("access_token")
        expires_in = int(body.get("expires_in", 0))
        if not token:
            raise TossAuthError("[인증 실패] 응답에 access_token 없음 (status 200)")
        return token, expires_in

    def get_token(self, force_refresh: bool = False) -> str:
        """유효한 access token을 돌려준다. 캐시가 살아 있으면 재발급하지 않는다.

        Args:
            force_refresh: 캐시를 무시하고 새로 발급받는다. 401 재시도 경로가 쓴다.

        Raises:
            TossAuthError: 발급 실패 또는 응답에 `access_token` 없음.
        """
        if not force_refresh:
            cached = self._read_cache()
            if cached:
                return cached["access_token"]
        token, expires_in = self._request_new()
        if expires_in > 0:
            self._write_cache(token, expires_in)
        else:
            # 만료를 모르면 캐시할 수 없다. 그런데 옛 항목을 그대로 두면 **다음** 호출이
            # 파일 기준으로는 아직 유효한 그 토큰을 되집는다 — 방금 재발급을 부른 이유가
            # 서버가 그걸 거부해서라면 매 요청이 401을 한 번씩 더 맞는다. 지운다.
            self.cache_path.unlink(missing_ok=True)
        return token
