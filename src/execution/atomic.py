"""상태 파일 원자적 쓰기.

`managed_state.json`·`circuit_breaker.json`은 라이브 실행의 상태 저장소다. `write_text`로
직접 쓰면 도중에 죽었을 때 잘린 JSON이 남고, 다음 실행이 그걸 읽는다. 화이트리스트가 잘리면
봇 관리셋을 잃고, 서킷브레이커가 잘리면 카운터가 0에서 다시 센다 — 둘 다 안전판 무력화다.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: str | Path, text: str) -> None:
    """임시파일에 쓴 뒤 `os.replace`로 교체한다. 부분 쓰기 상태를 남기지 않는다.

    임시파일은 반드시 **대상과 같은 디렉터리**에 만든다 — `os.replace`의 원자성은 동일
    파일시스템 안에서만 보장되고, `/tmp`는 다른 파일시스템일 수 있다.

    Args:
        path: 최종 경로. 부모 디렉터리가 없으면 만든다.
        text: 파일 내용.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())  # 교체 전에 내용이 디스크에 닿아야 크래시에도 남는다
        os.replace(tmp, p)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)  # 실패 시 임시파일을 남기지 않는다
        raise
