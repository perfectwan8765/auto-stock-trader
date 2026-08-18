"""파이프라인 공통 유틸 — 원자적 쓰기.

잘린 CSV가 남으면 01_collect에서는 그게 **다음 실행의 폴백 대상**이 되어 손상이 영속한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "data_pipeline"))
import _common


def test_write_csv_atomic_keeps_old_file_on_failure(tmp_path, monkeypatch):
    out = tmp_path / "d.csv"
    pd.DataFrame({"a": [1, 2]}).pipe(_common.write_csv_atomic, out, index=False)
    before = out.read_text()

    def boom(src, dst):
        raise OSError("디스크 가득")

    monkeypatch.setattr(_common.os, "replace", boom)
    with pytest.raises(OSError):
        _common.write_csv_atomic(pd.DataFrame({"a": [9]}), out, index=False)

    assert out.read_text() == before                    # 기존 내용 보존
    assert list(tmp_path.glob(".*tmp")) == []           # 임시파일 잔여 없음


def test_write_csv_atomic_replaces_content(tmp_path):
    out = tmp_path / "d.csv"
    _common.write_csv_atomic(pd.DataFrame({"a": [1]}), out, index=False)
    _common.write_csv_atomic(pd.DataFrame({"a": [2]}), out, index=False)
    assert pd.read_csv(out)["a"].tolist() == [2]


def test_write_text_atomic_keeps_old_file_on_failure(tmp_path, monkeypatch):
    out = tmp_path / "r.json"
    _common.write_text_atomic(out, '{"ok": 1}')

    monkeypatch.setattr(_common.os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(OSError):
        _common.write_text_atomic(out, "부분")

    assert out.read_text() == '{"ok": 1}'
    assert list(tmp_path.glob(".*tmp")) == []
