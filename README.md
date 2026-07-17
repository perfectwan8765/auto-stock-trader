# qlib-toss

Qlib으로 미국주식을 예측·백테스트하고, 토스증권 OpenAPI로 주간 리밸런싱을 자동 발주하는 개인 프로젝트.

> 상세 설계·의사결정은 [qlib-toss.md](qlib-toss.md) 참고.
> $700 규모의 **학습·검증 목적** 프로젝트입니다. 실전 수익을 보장하지 않습니다.

## 개요

| 항목 | 값 |
|------|-----|
| 시장 / 유니버스 | 미국주식 / S&P 500 |
| 팩터 / 모델 | Alpha158 / LightGBM |
| 포트폴리오 | TopkDropout, 롱온리, K=15~20 |
| 리밸런싱 | 주간 |
| 발주 | 토스증권 OpenAPI (소수점 금액주문) |

## 개발 환경

- macOS (Apple Silicon) + pyenv
- Python 3.10.13 (`.python-version`)

```bash
brew install libomp                        # LightGBM OpenMP 런타임
python -m venv .venv                        # pyenv 3.10.13 기준
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c "import qlib, lightgbm, xgboost"   # 검증
```

## 진행 상태

- [x] **Phase 1** 개발 환경 구축 (M1 + pyenv, qlib/lightgbm/xgboost)
- [ ] **Phase 0** 토스 실측 (키 승인 대기 중) — `scripts/phase0/` 참고
- [x] **Phase 2** 데이터 파이프라인 (S&P500 파일럿 41종목 → Qlib bin) — `scripts/phase2/` 참고
- [ ] **Phase 3** 모델 학습 + 백테스트
- [ ] **Phase 4** 시그널 생성
- [ ] **Phase 5** 토스 발주 어댑터
- [ ] **Phase 6~7** 스모크 테스트 + 소액 실전

## 구조

```
src/toss/          토스 OpenAPI 공통 모듈 (config·auth·client) — Phase 0/5 공용
scripts/phase0/    Phase 0 실측 툴킷 (키 발급 후 순서대로 실행)
scripts/phase2/    Phase 2 데이터 파이프라인 (수집→정규화→dump→검증)
universe/          유니버스 티커 리스트 (S&P500 파일럿)
vendor/            외부 원본 파일 (qlib dump_bin.py) — 수정 금지
qlib-toss.md       전체 작업계획서
requirements.txt   의존성 핀 (재현용)
```

## 보안

- 자격증명은 **`.env`에서만** 읽으며 코드/저장소에 넣지 않는다 (`.env.example` 참고).
- `.env`, `.cache/`(토큰), `phase0-findings.md`(계좌식별자)는 `.gitignore`로 커밋 차단.
- 저장소는 **Private** 권장.
