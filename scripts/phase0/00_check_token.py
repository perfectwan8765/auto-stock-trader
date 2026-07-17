"""Phase 0-1 검증: client_id/secret로 access_token 발급 성공 여부 확인.

실행:  python scripts/phase0/00_check_token.py
전제:  .env에 TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 설정
"""
import _bootstrap  # noqa: F401

from toss.auth import TokenManager
from toss.config import load_config


def main() -> None:
    cfg = load_config()
    tm = TokenManager(cfg)
    # 캐시 무시하고 새로 발급받아 자격증명 자체를 검증
    token = tm.get_token(force_refresh=True)
    ttl = tm.token_ttl_seconds()  # 캐시 기록 및 만료시각 확인용 (공개 API)

    print("✅ 토큰 발급 성공 (Phase 0-1 검증 통과)")
    print(f"   token: {token[:12]}... (len={len(token)})")
    if ttl is not None:
        print(f"   만료까지 약 {ttl}초 → expires_in 기준 캐싱 동작 확인")
    else:
        print("   ⚠️ 캐시 미기록 (expires_in=0 이거나 캐시 비활성) — 매 호출 재발급됩니다.")
    print("\n다음 단계: python scripts/phase0/01_accounts.py")


if __name__ == "__main__":
    main()
