"""각 Phase 0 스크립트가 src/ 를 import 할 수 있도록 경로를 잡는다.
스크립트 맨 위에서 `import _bootstrap  # noqa` 로 불러온다.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
