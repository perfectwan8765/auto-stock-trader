# vendor/

프로젝트 외부에서 그대로 가져온 파일. **수정 금지**(업스트림과 diff 유지).

## dump_bin.py

- 출처: https://github.com/microsoft/qlib `scripts/dump_bin.py`
- 버전: 태그 `v0.9.7` (설치된 pyqlib==0.9.7과 정합)
- 라이선스: MIT (파일 상단 헤더 유지)
- 취득일: 2026-07-17
- 이유: `dump_bin.py`는 pip 패키지(pyqlib)에 미포함, qlib 소스 repo에만 존재.
  정규화된 CSV → Qlib `.bin` 포맷 변환(calendars/instruments/features)에 사용.
- CLI: `dump_all`(전체) · `dump_fix` · `dump_update`(증분).
  Phase 2 `scripts/data_pipeline/03_dump_bin.py`가 이 파일을 호출한다.
- 의존: fire, loguru, tqdm, pandas, numpy, `qlib.utils` (requirements.txt에 핀).
