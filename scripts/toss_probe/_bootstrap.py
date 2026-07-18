"""각 Phase 0 스크립트가 src/ 를 import 할 수 있도록 경로를 잡는다.
스크립트 맨 위에서 `import _bootstrap  # noqa` 로 불러온다.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def cli(main_fn) -> None:
    """CLI 경계: 라이브러리 TossError를 여기서만 SystemExit(clean 메시지)로 변환(개선10).
    라이브러리 자체는 SystemExit을 던지지 않는다(cron 자동화가 예외로 잡도록)."""
    from toss.errors import TossError  # sys.path 설정 후 지연 import

    try:
        main_fn()
    except TossError as e:
        raise SystemExit(str(e))
