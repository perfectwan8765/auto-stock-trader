"""OAuth2 client_credentials 토큰 발급 + expires_in 기준 파일 캐싱."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from .config import Config, PROJECT_ROOT
from .errors import TossAuthError

_CACHE_PATH = PROJECT_ROOT / ".cache" / "toss_token.json"
_EXPIRY_SKEW_SEC = 60  # 만료 직전 안전 마진


def _oauth_error_detail(resp: requests.Response) -> str:
    """개선13: 표준 OAuth error/error_description(비밀 아님)만 추출. 비-JSON이면 빈 문자열.
    resp.text 전체(임의 본문·잠재 누설)는 절대 노출하지 않는다."""
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
    def __init__(self, cfg: Config, cache_path: Path = _CACHE_PATH):
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
        만료 skew를 적용하지 않고 파일 값 그대로 — 캐싱 동작 확인용 공개 API."""
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
        self.cache_path.write_text(json.dumps(payload))
        # 자격증명 파생물이므로 소유자만 읽기
        self.cache_path.chmod(0o600)

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
        if not force_refresh:
            cached = self._read_cache()
            if cached:
                return cached["access_token"]
        token, expires_in = self._request_new()
        if expires_in > 0:
            self._write_cache(token, expires_in)
        return token
