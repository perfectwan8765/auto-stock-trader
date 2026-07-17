# Phase 3 — 모델 학습 + 백테스트

Alpha158 + LightGBM으로 주간 리밸런싱 롱온리 전략을 학습·백테스트한다.
grilling 결정(2026-07-17, [../../qlib-toss.md](../../qlib-toss.md) Phase 3)의 **유니버스 2단계(B3)**:

- **① 41종목 배선 스모크** ← 현재 단계. "돌아가나 / 지표 계산되나 / 라벨·주간스텝 맞나"만 확인.
- **② S&P500 전체(~500) 확장** ← 실제 엣지 판독 + SPY 벤치마크. (TODO)

⚠️ **41종목 지표로 전략 우열 판단 금지.** K=20이면 유니버스의 ~49% 보유 → 횡단 랭킹 무의미. 배선 확인용.

## 실행

```bash
.venv/bin/python scripts/phase3/run_smoke.py
```

`workflow_config_alpha158_lgb_pilot.yaml` 실행 → 학습 → SignalRecord/SigAnaRecord/PortAnaRecord → 4개 스모크 게이트 검증.

## ① 설계 결정 (config 요약)

| 항목 | 값 | 근거 |
|------|-----|------|
| provider_uri / region | `data/qlib_us` / `us` | Phase 2 산출물 |
| 유니버스 | `all` (41종목) | ① 배선용 |
| 팩터 / 모델 | Alpha158(158) / LGBModel | Phase 0 전략, seed=2026 |
| **라벨 (B2)** | `Ref($close,-6)/Ref($close,-1)-1` | 주간 5거래일 fwd override |
| train/valid/test | 2015-01-02~2021-06-30 / ~2022-12-31 / ~2026-07-16 | 시간순, test 최근 30% 격리·1회만 관측 |
| 정규화 fit 구간 | train만 | valid/test 누설 방지 |
| **리밸 스텝 (B2)** | `time_per_step: week` | 주간 |
| 전략 | TopkDropout topk=20, n_drop=5 | 회전율=n_drop 제어(개선7) |
| **비용 (개선2 placeholder)** | 편도 0.40% (`open/close_cost=0.004`) | 수수료0.10%+환전0.20%+슬리피지0.10%. **실측 아님** |
| min_cost / trade_unit | 0 / null | 소수점 매수 |
| account | 700 | 실규모 미러 |
| 벤치마크 | 41종목 등가중(러너 주입) | SPY 대비는 ② (B3) |

## 스모크 게이트 (① PASS 기준)

1. Alpha158 158개 피처 계산·NaN 없음
2. 라벨이 주간 5일 fwd로 실제 override됨 (raw 라벨 vs `-6`판 corr≈1.0 > `-2`(익일) 판)
3. 백테스트가 주간 스텝으로 돎 (스텝수 ≈ 거래일/5)
4. IC/RankIC/포트폴리오 지표 산출됨

**① 결과(2026-07-17):** 4/4 PASS. corr(wk)=1.000 vs (dy)=0.441로 주간 override 확정, 주간 183스텝(거래일 886).
IC≈0.038, RankIC≈0.033. **← 배선 확인 수치일 뿐, 41종목이라 엣지 아님.**

## ⚠️ 한계 (② 확장 전까지 유효)

- **overlapping 라벨(B2)**: 일간 샘플 + 5일 fwd → valid IC 자기상관 오염(파일럿 허용). 엄밀판(주간 비겹침)은 ②.
- **41종목 유니버스**: 횡단 랭킹 무의미(B3). 지표로 전략 판단 금지.
- **$700/최소주문 granularity 미반영**: 백테스트 소수점·min_cost=0 → 낙관 편향.
- **비용 placeholder**: 실측 아님. Phase 0(키 승인 대기) `GET /commissions`+환율로 교체 필요.
- **생존편향/point-in-time(개선3)**: 현 S&P500 구성 고정 → 성과 과대평가 가능.
- **벤치마크**: ①은 41종목 등가중(SPY 아님). qlib이 `benchmark=None`을 CSI300으로 폴백해 실데이터 벤치 필요.
- **mlflow**: 신버전이 파일스토어 차단 → 러너가 `MLFLOW_ALLOW_FILE_STORE=true` 설정.

## ② 확장 TODO

- 유니버스를 현 S&P500 전체(~500)로 교체 → Phase 2 파이프라인 재수집 후 재실행.
- SPY 벤치마크 추가(초과수익·IR), 41종목 등가중 병행.
- walk-forward 1회 이상.
- Sharpe 4+ 나오면 과최적 의심 → 재검토(규율).
