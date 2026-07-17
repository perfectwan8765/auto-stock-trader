# Phase 3 — 모델 학습 + 백테스트

Alpha158 + LightGBM으로 주간 리밸런싱 롱온리 전략을 학습·백테스트한다.
grilling 결정(2026-07-17, [../../qlib-toss.md](../../qlib-toss.md) Phase 3)의 **유니버스 2단계(B3)**:

- **① 41종목 배선 스모크** ✅ — "돌아가나 / 지표 계산되나 / 라벨·주간스텝 맞나"만 확인.
- **② S&P500 전체(500) 확장** ✅ — 실제 엣지 판독 + SPY 벤치마크.

⚠️ **① 41종목 지표로 전략 우열 판단 금지.** K=20이면 유니버스의 ~49% 보유 → 횡단 랭킹 무의미. 배선 확인용.

## 실행

```bash
# ① 배선 스모크 (41종목). QLIB_UNIVERSE 미설정 시 data/qlib_us는 ② 전체가 덮어씀 주의.
.venv/bin/python scripts/phase3/run_smoke.py --config workflow_config_alpha158_lgb_pilot.yaml
# ② 엣지 판독 (S&P500 500종목, SPY 벤치)
.venv/bin/python scripts/phase3/run_smoke.py --config workflow_config_alpha158_lgb_sp500.yaml
```

러너는 config 구동. `--config`의 handler `instruments`가 `sp500`이면 `instruments/sp500.txt`
(= `all.txt` − SPY, 매매 유니버스)를 자동 생성하고 `benchmark: SPY`를 쓴다. `benchmark: null`이면
매매 유니버스 등가중을 벤치로 주입. 학습 → SignalRecord/SigAnaRecord/PortAnaRecord → 4개 게이트 검증.

## ② 결과 (S&P500 500종목, 2026-07-17) — 실제 엣지 판독

**정직한 결론: 이 베이스라인 config로는 SPY 대비 exploitable 엣지 없음.** (과최적 아님 — 반대로 약함)

| 지표 | 값 | 해석 |
|------|-----|------|
| IC / RankIC | 0.012 / 0.008 | 약함(qlib CSI300 벤치 ~0.03-0.04 대비 낮음). 노이즈 근처 |
| ICIR / Rank ICIR | 0.12 / 0.09 | 미약한 양(+) |
| 초과수익(비용전) 연 / IR | +0.19% / 0.012 | 그로스로 SPY와 거의 동일 |
| 초과수익(비용후) 연 / IR | **-9.9% / -0.62** | MDD -44%. 비용이 압도 |
| LGB best iter | **[1]** | 즉시 early-stop → 언더피팅 |

**핵심 인과**: n_drop=5/topk=20 → 주간 회전율 ~25% × 편도 0.40% ≈ **연 ~10% 비용 드래그**.
비용전 ≈ SPY인데 비용이 전부 갉아먹음.

**해석 주의 (결론 못 박기 전 레버)**:
1. **비용이 결정적** → 개선2 placeholder(0.40%/편도)는 보수적·과대 가능. Phase 0 실측 비용으로
   교체 시 결과 크게 바뀔 수 있음. 회전율↓(n_drop↓ 또는 월간 리밸)도 직접적.
2. **하이퍼파라미터 부적합** — CN(CSI300) 튜닝값이 US 500·주간라벨엔 과도 정규화(L1=205/L2=580)
   → 즉시 early-stop. train/valid로 재튜닝 필요. "엣지 없음"이 아니라 "이 config로 미검출".
3. 수집 실패 3종목(FDXF/HONA/Q, Wikipedia 파싱 잡음). 매매 유니버스 500 확정.

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

## ⚠️ 한계 (①·② 공통)

- **overlapping 라벨(B2)**: 일간 샘플 + 5일 fwd → valid IC 자기상관 오염. 엄밀판(주간 비겹침 샘플링) 미적용.
- **①: 41종목 유니버스**: 횡단 랭킹 무의미(B3). 지표로 전략 판단 금지(배선용).
- **$700/최소주문 granularity 미반영**: 백테스트 소수점·min_cost=0 → 낙관 편향.
- **비용 placeholder**: 실측 아님. Phase 0(키 승인 대기) `GET /commissions`+환율로 교체 필요. ②에서 비용이 결과 지배.
- **생존편향/point-in-time(개선3)**: 현 S&P500 구성 고정 → 성과 과대평가 가능.
- **벤치마크 폴백**: qlib이 `benchmark=None`을 CSI300으로 폴백 → ①은 등가중 주입, ②는 SPY 사용.
- **mlflow**: 신버전이 파일스토어 차단 → 러너가 `MLFLOW_ALLOW_FILE_STORE=true` 설정.

## 다음 단계 (③ 후보, 규율: valid로만 튜닝·test 재관측 금지)

- **하이퍼파라미터 재튜닝**: CN 튜닝값이 US엔 과도 정규화(즉시 early-stop). L1/L2↓ 등 train/valid로 탐색.
- **회전율/비용 대응**: n_drop↓ 또는 월간 리밸로 비용 드래그(~연 10%) 완화. Phase 0 실측 비용 반영.
- **walk-forward 1회 이상** (현재 단일 split).
- 라벨 엄밀판(주간 비겹침), 생존편향 보정(시점별 지수구성).
