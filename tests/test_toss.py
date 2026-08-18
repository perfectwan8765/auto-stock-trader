"""src/toss 단위테스트 (개선10 예외화 · 개선13 redact · 토큰 캐싱).

mock으로 requests를 대체해 실 API 없이 검증. 개선11(401 재시도)은 Phase 5로 유보 → 미포함.
실행:  uv run pytest tests/test_toss.py -q
"""
from __future__ import annotations

import time
from pathlib import Path
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


def test_api_error_nested_error_object():
    """Phase 0 실측: 토스 에러는 {"error":{"code","message","data"}} 중첩."""
    client = TossClient(_cfg())
    body = {"error": {"requestId": "abc", "code": "account-not-found",
                      "message": "해당 계좌번호를 찾을 수 없습니다."}}
    with mock.patch.object(client.tokens, "get_token", return_value="tok"), \
         mock.patch.object(client.session, "request", return_value=_resp(400, body)):
        with pytest.raises(TossApiError) as ei:
            client.get("/api/v1/holdings")
    assert ei.value.code == "account-not-found"
    assert "account-not-found" in str(ei.value)


# --- 개선11: 401 → 토큰 강제 재발급 후 1회 재시도 ---

def test_request_retries_once_on_401():
    client = TossClient(_cfg())
    gt = mock.Mock(return_value="tok")
    with mock.patch.object(client.tokens, "get_token", gt), \
         mock.patch.object(client.session, "request",
                           side_effect=[_resp(401, {"code": "invalid-token"}), _resp(200, {"ok": 1})]) as req:
        assert client.get("/api/v1/holdings") == {"ok": 1}
    assert req.call_count == 2                 # 최초 + 재시도 1회
    gt.assert_any_call(force_refresh=True)     # 재시도 전 토큰 강제 재발급


def test_401_retry_uses_fresh_token_even_when_cache_not_written(tmp_path):
    """★ 재발급 토큰을 버리고 캐시를 다시 읽으면 거부된 옛 토큰을 재전송한다.

    _write_cache는 expires_in > 0 일 때만 쓴다. 응답에 expires_in이 없거나 0이면 캐시가
    갱신되지 않고, _headers가 get_token() -> _read_cache()로 (파일 기준) 아직 유효한 옛
    항목을 돌려준다. 그 토큰은 서버가 이미 거부했으니 재시도도 401이고, _retry=True라
    TossApiError로 끝난다 — 401 복구가 영구 불능이 된다.
    """
    cfg = _cfg()
    tm = TokenManager(cfg, cache_path=tmp_path / "tok.json")
    tm.cache_path.write_text(
        '{"client_id": "cid", "access_token": "stale", "expires_at": %d}' % int(time.time() + 3600)
    )
    client = TossClient(cfg, token_manager=tm)
    sent = []

    def capture(method, url, headers=None, **kw):
        sent.append(headers["Authorization"])
        return _resp(401, {}) if len(sent) == 1 else _resp(200, {"ok": 1})

    # 재발급 자체는 성공하지만 expires_in=0 이라 캐시에 남지 않는다.
    with mock.patch.object(tm, "_request_new", return_value=("fresh", 0)), \
         mock.patch.object(client.session, "request", side_effect=capture):
        assert client.get("/api/v1/holdings") == {"ok": 1}

    assert sent == ["Bearer stale", "Bearer fresh"]
    # 거부된 토큰이 캐시에 남으면 다음 요청이 다시 401을 맞는다 — 강제 재발급이
    # 캐시할 수 없으면(만료 미상) 옛 항목을 지워야 한다.
    assert not tm.cache_path.exists()


def test_request_401_twice_raises_no_second_retry():
    client = TossClient(_cfg())
    with mock.patch.object(client.tokens, "get_token", return_value="tok"), \
         mock.patch.object(client.session, "request",
                           side_effect=[_resp(401, {}), _resp(401, {})]) as req:
        with pytest.raises(TossApiError) as ei:
            client.get("/api/v1/holdings")
    assert ei.value.status == 401 and req.call_count == 2   # 재시도 상한 1회


def test_request_non_401_error_no_retry():
    client = TossClient(_cfg())
    with mock.patch.object(client.tokens, "get_token", return_value="tok"), \
         mock.patch.object(client.session, "request", side_effect=[_resp(404, {"code": "x"})]) as req:
        with pytest.raises(TossApiError):
            client.get("/api/v1/holdings")
    assert req.call_count == 1                 # 401 아니면 재시도 안 함


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

def test_token_cache_file_is_owner_only(tmp_path, monkeypatch):
    """★ 토큰 캐시는 **만들어지는 순간부터** 0600이어야 한다.

    종전에는 write_text로 만든 뒤 chmod했다. 그 사이 브로커 액세스 토큰이 umask 기본
    권한(보통 0644)으로 디스크에 놓이고, 두 줄 사이에서 프로세스가 죽으면 영구히 0644로 남는다.

    최종 모드만 보면 종전 구현도 통과하므로(chmod가 결국 조인다) 경합을 못 잡는다.
    사후 `Path.chmod`를 무력화해 **그 안전망 없이도** 파일이 0600인지 본다 — 그게 "만들어지는
    순간부터 0600"의 검증 가능한 형태다.
    """
    monkeypatch.setattr(Path, "chmod", lambda self, mode: None)

    tm = TokenManager(_cfg(), cache_path=tmp_path / "tok.json")
    with mock.patch.object(tm, "_request_new", return_value=("tok", 3600)):
        tm.get_token()
    assert oct(tm.cache_path.stat().st_mode)[-3:] == "600"


def test_token_cache_tightens_preexisting_loose_file(tmp_path):
    """이미 0644로 남아 있던 캐시도 조인다 — O_CREAT의 mode는 신규 생성에만 적용된다."""
    tm = TokenManager(_cfg(), cache_path=tmp_path / "tok.json")
    tm.cache_path.write_text("{}")
    tm.cache_path.chmod(0o644)
    with mock.patch.object(tm, "_request_new", return_value=("tok", 3600)):
        tm.get_token()
    assert oct(tm.cache_path.stat().st_mode)[-3:] == "600"


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
