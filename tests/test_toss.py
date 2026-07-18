"""src/toss 단위테스트 (개선10 예외화 · 개선13 redact · 토큰 캐싱).

mock으로 requests를 대체해 실 API 없이 검증. 개선11(401 재시도)은 Phase 5로 유보 → 미포함.
실행:  .venv/bin/python -m pytest tests/test_toss.py -q
"""
from __future__ import annotations

import time
from unittest import mock

import pytest

from toss.auth import TokenManager
from toss.client import TossClient
from toss.config import Config, load_config
from toss.errors import TossApiError, TossAuthError, TossConfigError, TossError


def _cfg(account: str = "acct-1") -> Config:
    return Config(client_id="cid", client_secret="secret", base_url="https://x", account=account)


def _resp(status: int, json_body=None, text: str = "", raise_json: bool = False):
    r = mock.Mock()
    r.status_code = status
    r.headers = {}
    r.text = text
    if raise_json:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_body
    return r


# --- 개선10: 예외 계열 ---

def test_error_hierarchy():
    for exc in (TossConfigError, TossAuthError, TossApiError):
        assert issubclass(exc, TossError)


def test_load_config_missing_raises_config_error(monkeypatch):
    for k in ("TOSS_CLIENT_ID", "TOSS_CLIENT_SECRET", "TOSS_ACCOUNT"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(TossConfigError):
        load_config()


def test_client_missing_account_raises_config_error():
    client = TossClient(_cfg(account=""))
    with mock.patch.object(client.tokens, "get_token", return_value="tok"):
        with pytest.raises(TossConfigError):
            client._headers(need_account=True)


def test_api_error_on_4xx():
    client = TossClient(_cfg())
    with mock.patch.object(client.tokens, "get_token", return_value="tok"), \
         mock.patch.object(client.session, "request",
                           return_value=_resp(404, {"code": "not-found"})):
        with pytest.raises(TossApiError) as ei:
            client.get("/api/v1/holdings")
    assert ei.value.status == 404
    assert ei.value.code == "not-found"


def test_api_error_non_json_body_not_leaked():
    """개선13 일관: 비-JSON 응답(502 HTML 등) resp.text는 메시지에 덤프 안 됨."""
    client = TossClient(_cfg())
    leak = "<html>UPSTREAM_SECRET_TOKEN_IN_HTML</html>"
    with mock.patch.object(client.tokens, "get_token", return_value="tok"), \
         mock.patch.object(client.session, "request",
                           return_value=_resp(502, text=leak, raise_json=True)):
        with pytest.raises(TossApiError) as ei:
            client.get("/api/v1/holdings")
    assert leak not in str(ei.value)      # 원문 미노출
    assert "502" in str(ei.value)
    assert ei.value.body == leak          # 단 프로그래매틱 접근은 보존


# --- 개선13: OAuth 에러 redact (resp.text 미노출) ---

def test_auth_failure_redacts_resp_text():
    tm = TokenManager(_cfg())
    leak = "SECRET_RAW_BODY_SHOULD_NOT_LEAK"
    resp = _resp(401, {"error": "invalid_client", "error_description": "bad secret"}, text=leak)
    with mock.patch("toss.auth.requests.post", return_value=resp):
        with pytest.raises(TossAuthError) as ei:
            tm._request_new()
    msg = str(ei.value)
    assert leak not in msg                 # 원문 본문 미노출
    assert "invalid_client" in msg         # 표준 OAuth error는 노출(진단)
    assert "401" in msg


def test_auth_failure_non_json_status_only():
    tm = TokenManager(_cfg())
    resp = _resp(503, text="<html>gateway</html>", raise_json=True)
    with mock.patch("toss.auth.requests.post", return_value=resp):
        with pytest.raises(TossAuthError) as ei:
            tm._request_new()
    msg = str(ei.value)
    assert "gateway" not in msg
    assert "503" in msg


def test_auth_missing_token_raises_auth_error():
    tm = TokenManager(_cfg())
    resp = _resp(200, {"expires_in": 3600})  # access_token 없음
    with mock.patch("toss.auth.requests.post", return_value=resp):
        with pytest.raises(TossAuthError):
            tm._request_new()


# --- 토큰 캐싱 (expires_in 기반) ---

def test_token_cache_reuse_and_expiry(tmp_path):
    tm = TokenManager(_cfg(), cache_path=tmp_path / "tok.json")
    with mock.patch.object(tm, "_request_new", return_value=("tok-A", 3600)) as m:
        assert tm.get_token() == "tok-A"
        assert tm.get_token() == "tok-A"      # 캐시 재사용
        assert m.call_count == 1

    # 만료(skew 이내) → 재발급
    tm.cache_path.write_text(
        '{"client_id": "cid", "access_token": "old", "expires_at": %d}' % int(time.time() + 10)
    )
    with mock.patch.object(tm, "_request_new", return_value=("tok-B", 3600)) as m:
        assert tm.get_token() == "tok-B"
        assert m.call_count == 1
