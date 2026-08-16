# 리서치 — 실계좌 학습의 통계적 가능성과 고정 원금 운용 best practice

- 조사일: 2026-08-16
- 목적: (1) 실계좌 매매 결과로부터 "내 전략이 되는지"를 언제 통계적으로 판별할 수 있는가,
  (2) 고정 원금 포트폴리오 운용에서 문헌이 실제로 뒷받침하는 규칙은 무엇인가
- 방법: 1차 출처(논문 PDF·학술지 초록·기관 리서치 원본)만 인용. PDF는 내려받아 본문을 직접 읽었다.
  본문을 열지 못한 항목은 §5에 따로 적었다.

---

## 0. 요약 — 확립된 것 vs 통설

**확립된 것 (1차 출처로 확인)**

1. Sharpe ratio 추정치의 표준오차는 `SE(SR) = sqrt((1 + SR²/2)/T)` 이다 (Lo 2002, Equation 9).
   이 식을 그대로 풀면 **연 SR=0.5를 0과 구분하는 데 t=2 기준 약 16년, 검정력 80% 기준 약 32년이 필요하다.**
2. ★ **표본 주기를 월→주→일로 올려도 필요 연수가 거의 줄지 않는다.** 16.2년(월) → 16.0년(주) → 16.0년(일).
   "데이터를 자주 찍으면 빨리 안다"는 직관은 Sharpe 판별에 관한 한 틀렸다.
3. 개인투자자가 매매로 학습하기는 한다. 다만 **생존편의를 제거하면 100거래당 연 30bp**이고,
   보정 전 추정치는 이보다 **2~4배 부풀려져 있다** (Seru, Shumway & Stoffman 2010).
   그리고 학습의 상당 부분은 "실력 없는 사람이 그만두는 것"이지 "실력이 느는 것"이 아니다.
4. 대만 데이 트레이더 전수 데이터에서 **지속적으로 수익을 내는 사람은 하루 평균 활동 트레이더의 3% 미만**,
   선행 연구 기준으로는 **1% 미만**이다. 75%가 2년 안에 그만둔다 (Barber, Lee, Liu, Odean & Zhang).
5. 백테스트에서 독립 설정을 **N=45개만 시도해도 5년치 데이터는 소진된다** — 진짜 실력이 0인데도
   in-sample 연 Sharpe 1이 기대값으로 나온다 (Bailey, Borwein, López de Prado & Zhu 2014, Notices of the AMS).
6. 리밸런싱 빈도·임계에 **지배적인 최적값은 없다.** Vanguard 자신의 1926–2018 데이터에서
   월간 0% ~ 연간 10% 임계까지 세후 수익률이 8.19%~8.39%로 사실상 동일했다.
7. 1/N은 좀처럼 지지 않는다. 평균-분산 최적화가 1/N을 이기려면 25종목에서 **약 3,000개월**,
   50종목에서 **약 6,000개월**의 추정 표본이 필요하다 (DeMiguel, Garlappi & Uppal 2009).

**통설이지만 1차 근거가 약하거나 반대인 것**

1. ★ **"리밸런싱 보너스"는 수익률 증가가 아니다.** Vanguard 표에서 **리밸런싱하지 않은 포트폴리오가
   세후 연 8.74%로 가장 높았다** (리밸런싱한 경우 8.19~8.39%). 리밸런싱이 산 것은 수익이 아니라
   변동성(14.0% → 11.4~11.8%)과 Sharpe(0.46 → 0.50~0.51)다. Perold & Sharpe(1988)도
   constant-mix가 **"방향성 없는 변동장에서만"** 유리하다고 못박는다. 무조건적 보너스는 문헌에 없다.
2. "Vanguard가 5% 밴드를 권고한다"는 널리 퍼진 인용은 **내가 공식 Vanguard 도메인에서 확인하지 못했다.**
   내가 직접 읽은 Vanguard 문서는 오히려 특정 임계를 권고하기를 명시적으로 거부한다 (§4.1, §5).
3. "half-Kelly는 성장률의 75%를 절반의 변동성으로 얻는다"는 자주 인용되는 수치인데,
   **연속시간 lognormal 가정에서는 직접 유도된다** (§4.3). 다만 이산·비정규 상황에서 그대로 성립한다는
   1차 진술은 찾지 못했다.

---

## 1. 실계좌 track record에서 실력을 판별하는 데 필요한 표본

### 1.1 표준오차 공식 — Lo (2002)

Andrew W. Lo, "The Statistics of Sharpe Ratios," *Financial Analysts Journal* 58(4), July/August 2002, pp. 36–52.

- 학술지 페이지: https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
- 본문 PDF(내가 읽은 사본): https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf
  — 페이지 머리말이 `36 ©2002, AIMR®`, `July/August 2002 37`로 찍힌 게재본 스캔이다.
  다만 **출판사 호스팅이 아니라 Berkeley 학생단체 서버의 사본**이라는 점은 밝혀 둔다.

IID 수익률 가정에서 점근분산은 (Equation 8):

> V_IID = 1 + (μ − R_f)² / (2σ²) = **1 + ½ SR²**

따라서 표준오차는 (Equation 9):

> **SE(SR) ≈ sqrt( (1 + ½ SR²) / T )**

논문 Table 1은 이 식의 값을 표로 준다 (Note: *"Returns are assumed to be IID, which implies V_IID = 1 + 1/2 SR²."*):

| SR \ T | 12 | 24 | 36 | 48 | 60 | 125 | 250 | 500 |
|---|---|---|---|---|---|---|---|---|
| 0.50 | 0.306 | 0.217 | 0.177 | 0.153 | **0.137** | 0.095 | 0.067 | 0.047 |
| 1.00 | 0.354 | 0.250 | **0.204** | 0.177 | 0.158 | 0.110 | 0.077 | 0.055 |
| 1.50 | 0.421 | 0.298 | 0.243 | 0.210 | **0.188** | 0.130 | 0.092 | 0.065 |
| 3.00 | 0.677 | 0.479 | 0.391 | 0.339 | **0.303** | 0.210 | 0.148 | 0.105 |

**검증**: 위 굵은 값들을 공식으로 직접 계산해 재현했다 — 0.137 / 0.204 / 0.188 / 0.303 모두 소수 셋째 자리까지 일치.
공식과 표가 서로 정합한다.

여기서 표의 SR은 **관측 주기 단위 SR**이다(연율화값이 아니다). 논문이 직접 든 예:

> *"in a sample of 60 observations, the standard error of the Sharpe ratio estimator is 0.188
> when the true Sharpe ratio is 1.50 but is 0.303 when the true Sharpe ratio is 3.00."*

즉 **SR이 높을수록 표준오차도 커진다** — 좋은 전략일수록 측정이 어렵다는 뜻이다.

### 1.2 그래서 몇 년이 필요한가 — 직접 계산

연율 Sharpe를 `SR_a`, 연간 관측수를 `m`이라 하면 주기 SR은 `SR_a/√m`, 총 관측수는 `T = n·m`.
`t = SR/SE = z` 를 풀면 대수적으로 정리된다:

> **n_years = z² / SR_a² + z² / (2m)**

두 번째 항은 무시할 만큼 작다. **즉 필요한 햇수는 사실상 `z²/SR_a²`이고, 관측 주기와 거의 무관하다.**

**t = 2 기준 (양측 5%, 검정력 약 50%)**

| 연율 SR | 월간 관측수 | 필요 연수 | 주간 관측수 | 필요 연수 | 일간 관측수 | 필요 연수 |
|---|---|---|---|---|---|---|
| 0.30 | 535 | 44.6 | 2,313 | 44.5 | 11,202 | 44.5 |
| **0.50** | **194** | **16.2** | **834** | **16.0** | 4,034 | 16.0 |
| 0.75 | 87 | 7.3 | 372 | 7.1 | 1,794 | 7.1 |
| 1.00 | 50 | 4.2 | 210 | 4.0 | 1,010 | 4.0 |
| 1.50 | 23 | 1.9 | 94 | 1.8 | 450 | 1.8 |
| 2.00 | 14 | 1.2 | 54 | 1.0 | 254 | 1.0 |

★ **핵심**: SR=0.5를 0과 구분하려면 월간이든 주간이든 일간이든 **약 16년**이다.
주간으로 찍으면 관측수는 834개로 늘지만 각 관측의 신호도 같은 비율로 줄어 상쇄된다.
"고빈도로 관측해서 빨리 판별한다"는 발상은 이 프레임에서 작동하지 않는다.

**t=2는 검정력 50%짜리 기준이라는 점이 중요하다.** t=2를 "참인 SR이 정확히 0.5일 때 기대되는 t값"으로
잡았으므로, 실제로 유의성을 얻을 확률은 절반뿐이다. 80% 검정력을 원하면
`z = 1.96 + 0.84 = 2.80`을 써야 하고 필요 표본은 약 1.96배가 된다:

| 연율 SR | 80% 검정력 필요 연수 (월간) | (주간) |
|---|---|---|
| 0.30 | 87.5년 | 87.3년 |
| **0.50** | **31.7년** | **31.5년** |
| 1.00 | 8.2년 | 7.9년 |

### 1.3 López de Prado 계열 — MinTRL과 MinBTL은 서로 다른 질문이다

#### MinTRL (Minimum Track Record Length)

Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier," *Journal of Risk* 15(2), 2012.
공동저자 본인 사이트 PDF: https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf

Equation (13):

> **MinTRL = 1 + [ 1 − γ̂₃·ŜR + (γ̂₄−1)/4 · ŜR² ] · ( Z_α / (ŜR − SR*) )²**

여기서 γ̂₃는 왜도, γ̂₄는 첨도, SR*는 비교 기준. 논문의 수치 예 (95% 신뢰, IID Normal):

> *"a 2.73 years track record is required for an annualized Sharpe of 2 to be considered greater than 1
> at a 95% confidence level."* (일간 데이터 기준)

주기별 비교 — 같은 연율 Sharpe 2, 같은 기준 SR*=1:

| 데이터 주기 | MinTRL | 일간 대비 |
|---|---|---|
| 일간, IID Normal | 2.73년 | — |
| 주간, IID Normal | 2.83년 | +3.7% |
| 월간, IID Normal | 3.24년 | +18.7% |
| 월간, 헤지펀드 왜도·첨도 적용 | **4.99년** | **+82.8%** |

★ 여기서도 주기 효과는 작고(2.73 → 3.24년), **비정규성 효과가 훨씬 크다**(3.24 → 4.99년).

논문이 스스로 붙인 경고:

> *"It is important to note that MinTRL is expressed in terms of number of observations,
> not annual or calendar terms. ... CLT is typically assumed to hold for samples in excess of
> 30 observations (Hogg and Tanis (1996)). So even though a MinTRL may demand less than 2.5 years
> of monthly data, ... the moments inputted in Eq. (13) must be computed on longer series for CLT to hold."*

**Lo와의 교차검증**: MinTRL을 정규 가정(γ₃=0, γ₄=3), SR*=0, 95% 단측(z=1.645)으로 놓고 연율 SR=0.5를 넣으면
월간 132개월 = **11.0년**, 주간 565주 = **10.9년**이 나온다. Lo 공식에 z=1.645를 넣은 값
(1.645²/0.25 = 10.8년)과 일치한다. **두 1차 출처가 독립적으로 같은 답을 준다.**

#### MinBTL (Minimum Backtest Length) — 이건 다른 문제다

Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism:
The Effects of Backtest Overfitting on Out-of-Sample Performance," *Notices of the AMS* 61(5),
May 2014, pp. 458–471. 출판사 오픈액세스 PDF: https://www.ams.org/notices/201405/rnoti-p458.pdf

논문이 두 개념을 명시적으로 구분한다:

> *"MinTRL was developed to evaluate a strategy's track record (a single realized path, N = 1).
> The question we are asking now is different, because we are interested in the backtest length needed
> to avoid selecting a skill-less strategy among N alternative specifications."*

Theorem 2:

> **MinBTL ≈ [ ((1−γ)Z⁻¹[1−1/N] + γZ⁻¹[1−1/(Ne)]) / E[max_N] ]² < 2·ln[N] / E[max_N]²**

수치 결과 (모두 실제 OOS Sharpe = 0인 전략들 사이에서):

- *"if the researcher tries only N = 10 alternative configurations of an investment strategy,
  she is expected to find a strategy with a Sharpe ratio IS of **1.57** despite the fact that
  all strategies are expected to deliver a Sharpe ratio of zero OOS."*
- *"if only **five years** of data are available, no more than **forty-five** independent model
  configurations should be tried or we are almost guaranteed to produce strategies with an
  annualized Sharpe ratio IS of 1 but an expected Sharpe ratio OOS of zero."*
- *"After trying only **seven** independent strategy configurations, the expected maximum SR IS is 1
  for a **two-year** long backtest, while the expected SR OOS is 0."*
- 모형 복잡도와의 연결: 이진 파라미터 5개면 `N = 2⁵ = 32`. 파라미터 몇 개만 늘려도 예산이 소진된다.

논문의 자기 한계 진술:

> *"a backtest may be overfit even if it is computed on a sample greater than MinBTL.
> From that perspective, MinBTL should be considered a necessary, nonsufficient condition."*

★ **실계좌 운용에 주는 함의**: 실계좌는 N=1이므로 MinTRL 영역이고, 위 §1.2 표가 그대로 적용된다.
반면 백테스트로 설정을 고르는 단계는 MinBTL 영역이라 훨씬 가혹하다.
**두 예산은 별개로 소비되며, 백테스트에서 N번 시도한 뒤 실계좌를 켜도 실계좌의 MinTRL은 줄어들지 않는다.**

### 1.4 개인투자자는 실제로 매매에서 배우는가

#### Seru, Shumway & Stoffman (2010) — 배우기는 하는데, 대부분 "그만두기"를 배운다

*"Learning by Trading,"* **Review of Financial Studies** 23(2), Feb 2010, pp. 705–739.
공동저자 본인 사이트 PDF: http://tylergshumway.org/Seru-LearningTrading-2010.pdf
데이터: 핀란드 개인투자자 전체 거래기록, 1995–2003 (9년).

초록:

> *"We find evidence of two types of learning: some investors become better at trading with experience,
> while others stop trading after realizing that their ability is poor. A substantial part of overall
> learning by trading is explained by the second type. **By ignoring investor attrition, the existing
> literature significantly overestimates how quickly investors become better at trading.**"*

**핵심 수치 (생존편의 보정 후)**:

> *"after accounting for survivorship, an extra 100 trades is associated with an improvement in average
> returns of approximately **3.6 basis points (bp) over a 30-day horizon (or about 30 bp per year)**,
> and a reduction in the disposition effect of about 2%. **If we measure experience with the number of
> years an individual has been trading instead of the number of trades he or she has placed, the
> improvement is negligible.** ... the magnitude of the learning estimates presented above is about
> **two to four times higher when not adjusted for investor attrition.**"*

**보정 전 추정치를 저자들 스스로 기각한다** — 이게 이 논문에서 가장 값진 대목이다:

> *"An additional year of experience increases average 30-day post-purchase returns by 41 − 4 = 37 bp,
> or approximately 3% at an annualized rate. ... While these estimates are encouraging, **the speed of
> learning they imply seems almost implausibly large.** For instance, taking the regression parameters
> at face value, an investor with eight years of experience should outperform a new investor by about
> **22% per year.** While we observe some heterogeneity in investor ability ..., it is not nearly
> large enough to justify these large coefficients."*

부수 수치:

- 탈락 메커니즘: *"a decrease in returns of one standard deviation increases the probability that the
  individual will cease to trade in the next period by around **15%**."*
- 성과 지속성: 연도 t 수익률을 t−1에 회귀한 계수 **0.183** (p < 0.0001);
  1995–1999 vs 2000–2003 Spearman 순위상관 **0.164** (p < 0.0001).
- Disposition effect: 중앙값 계수 1.04 → 신규 투자자는 손실 종목보다 이익 종목을 **2.8배** 더 잘 판다.
- 결론: *"the primary way that low-ability investors learn is by learning to stop trading."*

★ **읽는 법**: 100거래당 연 30bp라는 숫자를 §1.2 표와 나란히 놓아야 한다.
연 30bp 개선은 SR로 환산하면 극히 작고, 그 개선이 실재하는지 확인하는 데 필요한 표본은
개선 자체보다 훨씬 크다. **피드백 루프가 열려 있긴 하지만 대역폭이 사실상 0에 가깝다.**

#### 데이 트레이더 생존 — Barber, Lee, Liu, Odean & Zhang

*"Do Day Traders Rationally Learn About Their Ability?"* (2017년 10월 working paper)
Odean 본인 교수 페이지 PDF:
https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf
데이터: 대만증권거래소 전체 거래·주문·투자자 식별자, 1992–2006 (15년).

생존율 (Kaplan-Meier, 최소 10일 이상 데이트레이딩한 사람 기준):

> *"Only **2.5%** drop out within one month, while survival rates at one, two, and three years are
> **44%, 24% and 15%** respectively."*
> *"more that 75% of all day traders quit within two years"*

수익성:

> *"On average, day traders lose **7 basis points** on their day trading before costs (t = −10.2).
> ... trading costs more than triple the losses to **23.9 basis points per day**."*
> *"In aggregate, day trading is a losing proposition; day trading is an industry that consistently
> and reliably loses money."*

지속적 수익자의 비중:

> *"only 9.81% (3.20%+6.61%) of day trading volume is generated by predictably profitable day traders.
> From column 8, we can calculate that these predictably profitable traders constitute
> **less than 3% of all day traders on an average day**."*

선행 연구(Barber, Lee, Liu & Odean 2010)를 인용하며:

> *"a small subset of day traders (**less than 1% of the day trading population**) predictably earn profits."*

★ 다만 **학습의 증거도 있다**는 점은 공정하게 적어야 한다:

> *"profitable traders with more than **40 days** of day trading experience in the last year earn more
> than enough to cover their transaction costs. These results confirm that an extensive history of
> profitability is a strong predictor of future profitable. **However, very few traders are predictably
> profitable.**"*

즉 "과거 수익성 + 충분한 경험"은 미래 수익성의 강한 예측변수다.
문제는 그 조건을 만족하는 사람이 3% 미만이라는 것이다.

#### 매매 자체의 비용 — Barber & Odean

**"Trading Is Hazardous to Your Wealth,"** *Journal of Finance* 55(2), April 2000, pp. 773–806.
Odean 본인 페이지 PDF:
https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/Individual_Investor_Performance_Final.pdf
데이터: 대형 할인증권사 66,465 가구, 1991–1996.

> *"those that trade most earn an annual return of **11.4 percent**, while the market returns
> **17.9 percent**. The average household earns an annual return of **16.4 percent**, ...
> and turns over **75 percent** of its portfolio annually."*

★ 인과의 핵심 — **총수익은 같은데 순수익만 갈린다**:

> *"there is very little difference in the **gross** performance of households that trade frequently
> (with monthly turnover in excess of 8.8 percent) and those that trade infrequently. In contrast,
> households that trade frequently earn a **net** annualized geometric mean return of **11.4 percent**,
> and those that trade infrequently earn **18.5 percent**."*

즉 회전율이 만든 **7.1%p 격차는 전적으로 거래비용**이다. 종목선택 능력 차이가 아니다.

거래비용 수준 (1990년대 할인증권사 기준):

> *"The average round-trip trade in excess of $1,000 costs **three percent in commissions and
> one percent in bid-ask spread**."* (= 왕복 4%)

벤치마크 대비:

> *"the average household underperforms a value-weighted market index by about **9 basis points per month**
> (or 1.1 percent annually). After accounting for the fact that the average household tilts its common
> stock investments toward small value stocks with high market risk, the underperformance averages
> **31 basis points per month (or 3.7 percent annually)**."*

**"Boys Will Be Boys,"** *Quarterly Journal of Economics* 116(1), Feb 2001, pp. 261–292.
PDF: https://faculty.haas.berkeley.edu/odean/papers/gender/boyswillbeboys.pdf
데이터: 35,000+ 가구, 1991년 2월 – 1997년 1월.

> *"We document that men trade **45 percent more** than women. Trading reduces men's net returns by
> **2.65 percentage points a year** as opposed to **1.72 percentage points** for women."*

**"Just How Much Do Individual Investors Lose by Trading?"** *Review of Financial Studies* 22(2), 2009.
PDF: https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf
데이터: 대만 전체 투자자, 1995–1999.

> *"the aggregate portfolio of individuals suffers an annual performance penalty of
> **3.8 percentage points**. Individual investor losses are equivalent to **2.2% of Taiwan's gross
> domestic product** or 2.8% of the total personal income."*

손실 분해 — ★ **절반 이상이 순수 마찰비용**이다:

> *"trading losses (**27%**), commissions (**32%**), transaction taxes (**34%**), and market-timing
> losses (**7%**)."*

기관과의 대비: *"institutions enjoy an annual performance boost of **1.5 percentage points**."*

---

## 2. 노이즈가 학습을 어떻게 무력화하는가 — 종합

이 항목에 대해 "finance에서의 outcome bias" 자체를 다룬 엄밀한 1차 논문은 찾지 못했다(§5 참조).
대신 위 출처들에서 직접 도출되는 정량적 진술을 정리한다.

1. **신호 대 잡음비가 구조적으로 낮다.** SR=0.5 전략의 1년치 월간 데이터(T=12)에서
   주기 SR은 0.144, SE는 sqrt((1+0.0104)/12) = 0.290. 즉 **t ≈ 0.5**. 1년 성과는 정보가 아니다.
2. **학습 신호가 잡음보다 훨씬 작다.** Seru et al.의 생존편의 보정 학습률은 100거래당 연 30bp인데,
   같은 기간 개인 포트폴리오의 연 변동성은 통상 15~25%다. 개선분을 검출하는 데 필요한 표본은
   전략 자체를 검출하는 데 필요한 표본보다 크다.
3. **탈락이 관측을 오염시킨다.** Seru et al.: 생존편의를 무시하면 학습 추정치가 2~4배 부풀려진다.
   자기 자신을 관측할 때는 이 편의를 제거할 표본 자체가 없다(N=1이고, 아직 살아 있다).
4. **선택 편의는 백테스트 단계에서 이미 예산을 태운다.** N=10만 시도해도 실력 0에서 IS Sharpe 1.57이 나온다
   (AMS 2014). 실계좌 성과가 좋아 보여도, 그 전략을 고른 과정이 N번의 탐색이었다면
   실계좌 성과 자체가 그 탐색의 연장선일 수 있다.
5. **추정오차는 평균에서 가장 치명적이다.** Chopra & Ziemba (1993)를 인용한 Ziemba & MacLean 챕터:
   > *"errors in the means average about **20 times** in importance in objective value than errors in
   > co-variances with errors in variances about double the co-variance errors. ... for the extreme
   > log investors with essentially zero risk aversion the errors are worth about **100:3:1**.
   > So log investors must estimate means well if they are to survive."*

   ★ 이건 §4.3(Kelly)과 직결된다. **Kelly/log 효용 사이징은 평균 추정오차에 가장 민감한 목적함수다.**
   평균을 16년 걸려야 겨우 판별하는 상황에서 Kelly를 쓰는 건 구조적으로 위험하다.

---

## 3. 실계좌 학습에 대한 실무 함의 (내 추론 — 인용 아님)

아래는 위 문헌에서 내가 끌어낸 함의이며 특정 논문의 주장이 아니다. 그렇게 표시해 둔다.

- **전략 수준 "이게 되는가"는 실계좌로 못 배운다.** SR=0.5라면 16~32년이다. 프로젝트 수명보다 길다.
- 반대로 **잘 배울 수 있는 양이 따로 있다**: 체결 슬리피지, 실제 수수료·세금, 대차 가능 여부와 비용,
  주문 미체결률, 시가/종가 갭. 이들은 **거래 단위로 직접 측정되고 복리로 누적되지 않아** 분산이 작다.
  Barber et al.(2009)이 손실의 66%를 수수료+거래세로 정확히 분해할 수 있었던 이유이기도 하다.
- 따라서 실계좌의 합리적 목표는 "전략 검증"이 아니라 **"백테스트 가정과 현실의 차이 측정"** 쪽이다.
- 판단 규칙을 사후에 바꾸지 않으려면 시작 전에 kill 조건을 못박아야 한다.
  검정력이 없다는 사실 자체가, 사후 재량이 개입할 여지를 최대로 만들기 때문이다.

---

## 4. 고정 원금 포트폴리오 운용

### 4.1 리밸런싱 빈도와 임계 — Vanguard

Vanguard, *"Getting back on track: A guide to smart rebalancing"* (Financial Planning Perspectives).
Vanguard 공식 도메인 PDF:
https://www.vanguardsouthamerica.com/content/dam/intl/americas/documents/latam/en/sa-2123766-getting-back-on-track.pdf

데이터: 1926년 1월 1일 – 2018년 12월 31일, 목표 60% 주식 / 40% 채권,
소득세 30% · 장기양도세 20% 가정한 **세후** 기준.

Figure 4 (원문 표를 그대로 옮김):

| 모니터링 주기 | 전략/임계 | 세후 연환산 수익 | 연환산 변동성 | Sharpe | 평균 주식비중 | 리밸런싱 횟수 |
|---|---|---|---|---|---|---|
| **Never** | NA | **8.74%** | **14.0%** | **0.46** | **85%** | **0** |
| Monthly | short-term gain 회피 | 8.19% | 11.7% | 0.50 | 60% | 1,107 |
| Monthly | 0% | 8.20% | 11.7% | 0.50 | 60% | 1,116 |
| Monthly | 1% | 8.20% | 11.7% | 0.50 | 60% | 426 |
| Monthly | 5% | 8.22% | 11.8% | 0.50 | 61% | 58 |
| Monthly | 10% | 8.39% | 11.8% | 0.51 | 62% | 24 |
| Quarterly | 0% | 8.26% | 11.6% | 0.51 | 60% | 372 |
| Quarterly | 1% | 8.26% | 11.6% | 0.51 | 60% | 233 |
| Quarterly | 5% | 8.31% | 11.6% | 0.51 | 61% | 47 |
| Quarterly | 10% | 8.26% | 11.7% | 0.50 | 62% | 19 |
| Annually | 0% | 8.19% | 11.4% | 0.51 | 60% | 93 |
| Annually | 1% | 8.19% | 11.4% | 0.51 | 60% | 83 |
| Annually | 5% | 8.19% | 11.4% | 0.51 | 61% | 34 |
| Annually | 10% | 8.20% | 11.6% | 0.50 | 63% | 14 |

Vanguard 자신의 결론:

> *"What's remarkable is that starkly different strategies were equally successful in controlling risk.
> At one extreme is a monthly 0% threshold strategy. ... Over the past 92 years, this strategy would have
> rebalanced a portfolio more than 1,100 times to produce an annualized return of 8.20%. At the other
> extreme is an annual 10% threshold strategy. ... This strategy led to only **14 rebalancing events**,
> also producing an annualized return of **8.20%**."*

> ★ *"Ultimately, we believe that investors will benefit from systematic rebalancing, but **we don't find
> a specific rebalancing threshold or frequency that consistently outperforms other forms of rebalancing.**
> It may behoove investors not to stress about the specifics but rather to choose a rebalancing strategy
> they can comfortably stick with."*

> *"The purpose of rebalancing is to **maintain a portfolio's risk and return characteristics,
> not to maximize returns.**"*

부수 수치 — 계좌 배치 최적화:

> *"By applying this tactic [rebalancing within tax-advantaged accounts] to the analysis shown in Figure 4,
> we found that after-tax returns increased by **44 basis points** on an annualized basis without
> increasing risk exposure."*

★ **이 표에서 반드시 읽어야 할 것**: 리밸런싱을 **안 한** 포트폴리오가 세후 수익률 8.74%로 최고다.
1,116회 리밸런싱한 쪽이 8.20%다. 즉 **리밸런싱은 92년에 걸쳐 연 54bp를 "지불"했고**,
그 대가로 변동성 14.0% → 11.7%와 목표 배분 유지(85% → 60%)를 샀다.
Sharpe는 0.46 → 0.50으로 올랐으니 위험조정 기준으로는 이득이다. **하지만 수익률 보너스는 아니다.**

### 4.2 "리밸런싱 보너스"는 존재하는가 — Perold & Sharpe (1988)

André F. Perold & William F. Sharpe, "Dynamic Strategies for Asset Allocation,"
*Financial Analysts Journal* 44(1), Jan/Feb 1988, pp. 16–27.
출판사 페이지: https://rpc.cfainstitute.org/research/financial-analysts-journal/1988/dynamic-strategies-for-asset-allocation

초록에서 확인한 진술:

- Buy-and-hold: *"Their performance is linearly related to the performance of the equity market."*
- Constant-mix(= 정률 리밸런싱): *"Constant-mix strategies—holding a constant fraction of wealth in stocks—
  **buy stocks as the market falls and sell them as it rises.**"*
  → ★ *"**They do best in relatively trendless but volatile markets.**"*
  → 추세장에서는 buy-and-hold에 뒤진다: *"less downside protection than, and not as much upside as,
  buy-and-hold strategies."*
- CPPI(포트폴리오 보험): *"sell stocks as the market falls and buy stocks as the market rises,"*
  *"better downside protection and better upside potential than buy-and-hold,"* 그러나
  *"**They do worse in relatively trendless, volatile markets.**"*
- 총량 제약: *"**Only buy-and-hold strategies can be followed by all investors.**"*

★ **두 주장을 반드시 분리해야 한다.**

| 주장 | 문헌 지지 여부 |
|---|---|
| 리밸런싱이 위험(변동성·배분 드리프트)을 통제한다 | **지지됨** (Vanguard Figure 4: 14.0% → 11.4~11.8%, 배분 85% → 60%) |
| 리밸런싱이 무조건 수익률을 높인다 | **지지되지 않음.** Vanguard 표에서는 오히려 낮췄고, Perold & Sharpe는 시장 국면 의존이라고 명시 |
| 리밸런싱이 위험조정 수익(Sharpe)을 높인다 | 지지됨, 다만 폭이 작다 (0.46 → 0.50~0.51) |

"rebalancing bonus"라는 표현이 성립하는 조건은 **평균회귀적이고 추세 없는 변동장**이다.
그건 자산 특성에 대한 가정이지 리밸런싱 규칙 자체의 성질이 아니다.
그리고 Perold & Sharpe가 지적하듯 **모두가 constant-mix를 할 수는 없다** —
누군가는 반대편을 받아 줘야 하므로 시장 총량 차원의 공짜 점심이 아니다.

### 4.3 포지션 사이징 — Kelly와 fractional Kelly

#### 원전 — Kelly (1956)

J. L. Kelly, Jr., "A New Interpretation of Information Rate," *Bell System Technical Journal* 35, 1956, pp. 917–926.
AT&T 허가 하 재수록본 PDF: https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf

> *"a gambler can use the knowledge given him by the received symbols to cause his money to grow
> exponentially. **The maximum exponential rate of growth of the gambler's capital is equal to the
> rate of transmission of information over the channel.**"*

성장률 정의:

> *"G = lim_{N→∞} (1/N) log(V_N / V_0)"*

★ 원전에는 "리스크 관리 기법"이라는 프레이밍이 없다. Kelly가 최대화하는 것은 **장기 성장률 하나**이며,
드로다운·단기 변동성·추정오차는 목적함수에 들어 있지 않다. 실무에서 Kelly를 줄여 쓰는 이유가 여기서 나온다.

#### Thorp — 왜 full Kelly를 쓰지 않는가

Edward O. Thorp, "Understanding the Kelly Criterion" (MacLean/Thorp/Ziemba 편저서 수록 챕터).
내가 읽은 사본: https://rybn.org/halloffame/PDFS/2008_Understanding_Kelly_New.pdf
(★ **저자·출판사 호스팅이 아닌 미러 사본**이다. 본문 각주에 `1/28/2016` 타임스탬프가 찍혀 있다.)

> ★ *"'full Kelly' is **too risky for the tastes of many, perhaps most, investors** and using instead
> an f = cf*, with fraction c where 0 < c < 1, or 'fractional Kelly' is much more to their liking.
> **Full Kelly is characterized by drawdowns which are too large for the comfort of many investors.**"*

과대베팅의 비대칭성:

> *"The 'true' scenario is worse than the supposedly conservative lower bound estimate. Then we are
> inadvertently betting more than f* and ... **we get more risk and less return, a strongly suboptimal
> result.** Betting cf*, 0 < c < 1, gives some protection against this."*

f* 자체를 과대추정하기 쉽다는 경고:

> *"Computing f* without considering the available alternative investments is one of the most common
> oversights I've seen in the use of the Kelly Criterion. It is a dangerous error because
> **it generally overestimates f***."*

처방:

> *"if, as is usually the case, **you only have estimates of future payoffs** and want to come close to
> maximizing your long term growth rate, then **to avoid damage from inadvertently betting more than
> Kelly you need to back off from your estimate of full Kelly** and consider a fractional Kelly strategy.
> In any case, **you may not like the large drawdowns that occur with Kelly fractions over ½** and may be
> well advised to choose lower values."*

이론적 정당화 (같은 챕터의 Theorem):

> *"For repeated independent trials of a two valued random variable, the mean-variance efficient frontier
> for compound growth over a finite number of trials consists precisely of the fractional Kelly strategies
> {cf* : 0 ≤ c ≤ 1}."*
> *"f* dominates the strategies for which c > 1 and they are not part of the efficient frontier."*

★ 즉 **c > 1(과대베팅)은 효율적 프론티어 밖이고, 0 < c < 1은 전부 효율적**이다.
"얼마나 줄일지"는 통계가 아니라 선호의 문제라는 게 이론의 답이다.

#### half-Kelly의 3/4 성장률 — 직접 유도

연속시간 lognormal에서 성장률은 `g(f) = f·μ − f²σ²/2`, Kelly 최적은 `f* = μ/σ²`, 최대 성장률은 `g(f*) = μ²/(2σ²)`.
Thorp 챕터가 인용하는 `Var G(f) = s²f²` (Thorp 2006, eqn 7.3)에서 성장률 표준편차는 `σ_G(f) = s·f`로 **f에 선형**이다.

- `g(f*/2) = (μ/2σ²)·μ − (μ²/4σ⁴)·σ²/2 = μ²/(2σ²) − μ²/(8σ²) = (3/8)·μ²/σ² = **0.75 · g(f*)**`
- `σ_G(f*/2) = **0.5 · σ_G(f*)**`

★ **half-Kelly는 성장률의 75%를 변동성 50%로 얻는다.** 이건 위 가정 하에서 대수적으로 참이다.
다만 이 문구 자체를 1차 출처에서 인용문으로 확보하지는 못했다 (§5).

#### 시뮬레이션 증거 — Ziemba & MacLean

W. T. Ziemba & L. C. MacLean, "Using the Kelly Criterion for Investing," Ch. 1 of
*Stochastic Optimization Methods in Finance and Energy* (Springer, 2011).
대학 호스팅 사본: https://webhomes.maths.ed.ac.uk/mckinnon/blackouts/StochOptFinanceAndEnergySpringer/Chap1_KellyZiemba.pdf

설정: 미국 주식(1926–2001, 연 10.2%, σ 20.3%) vs T-bill(3.9%). Kelly 해는 `x = 1.5288` (즉 레버리지).
40년, 3,000 시나리오 시뮬레이션. Table 1.3의 **최종부 최저값(Min)**:

| Kelly 비율 | 0.26k | 0.52k | 0.78k | 1.05k | 1.31k | 1.57k |
|---|---|---|---|---|---|---|
| Mean | 12,110 | 30,937 | 76,574 | 182,645 | 416,383 | 895,952 |
| **Min** | **2,368** | **701** | **−4,970** | **−133,456** | **−6,862,763** | **−102,513,724** |
| St. Dev. | 6,147 | 35,980 | 174,683 | 815,091 | 3,634,460 | 15,004,916 |

★ **0.52k(half-Kelly)에서는 최저 종가가 여전히 양수(701)지만, 0.78k부터 파산 시나리오가 나타난다.**

챕터의 결론:

> *"**no matter how favorable the investment opportunities are or how long the finite horizon is,
> a sequence of bad scenarios can lead to very poor final wealth outcomes, with a loss of most of
> the investor's initial capital.**"*
> *"the short-term performance of Kelly and high fractional Kelly strategies is very risky"*
> *"In his lectures, Ziemba always says **when in doubt bet less** — that is certainly borne out in
> these simulations."*

Samuelson 비판에 대한 저자들의 수긍:

> *"The Kelly strategy always leads to more wealth than any essentially different strategy;
> **this we know from the simulation in this chapter is not true** since it is possible to have a large
> number of very good investments and still lose most of one's fortune."*

그리고 §2에서 인용한 Chopra & Ziemba의 **100:3:1** — log 투자자(=Kelly)는 평균 추정오차에
가장 민감하다. §1.2의 "평균은 16년 걸려야 안다"와 겹쳐 읽으면, **실전에서 full Kelly를 쓸 만큼
평균을 정확히 아는 상황은 사실상 없다**는 결론이 나온다.

### 4.4 회전율 비용의 실증 크기

| 출처 | 표본 | 수치 |
|---|---|---|
| Barber & Odean (2000) | 미국 할인증권사 가구, 1991–96 | 왕복 거래비용 **수수료 3% + 스프레드 1% = 4%** ($1,000 초과 거래 기준); 평균 회전율 **75%/년** |
| Barber & Odean (2000) | 동일 | 고회전 가구 순수익 **11.4%** vs 저회전 **18.5%** → **7.1%p 격차**, 총수익은 거의 동일 |
| Barber & Odean (2000) | 동일 | 스타일 조정 후 평균 가구 언더퍼폼 **월 31bp = 연 3.7%** |
| Barber & Odean (2001) | 미국, 1991–97 | 매매가 남성 순수익 **연 2.65%p**, 여성 **1.72%p** 잠식 |
| Barber, Lee, Liu & Odean (2009) | 대만 전체, 1995–99 | 개인 총 성과 페널티 **연 3.8%p**; 그중 수수료 32% + 거래세 34% = **66%가 마찰비용** |
| Barber, Lee, Liu, Odean & Zhang | 대만 데이트레이더, 1992–2006 | 총 −7bp/일 → 비용 후 **−23.9bp/일** (비용이 손실을 3배 이상으로 키움) |

★ **주의**: 3% 수수료는 1990년대 수치다. 현재 한국·미국 리테일 수수료는 이보다 한 자릿수 낮다.
**그러나** 대만 사례의 손실 분해에서 **거래세가 34%로 수수료(32%)보다 컸다**는 점은 유효하다 —
수수료가 0이 되어도 세금과 스프레드는 남는다. 회전율 비용은 수수료율만으로 계산하면 과소평가된다.

### 4.5 1/N vs 최적화 — DeMiguel, Garlappi & Uppal (2009)

*"Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?"*
**Review of Financial Studies** 22(5), May 2009, pp. 1915–1953.
- 출판사 페이지: https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901
- 초록 전문을 확보한 곳(RePEc/EconPapers, 출판사 초록 미러):
  https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:5:p:1915-1953

> *"Of the **14 models** evaluated across **seven empirical datasets**, none is consistently better than
> the 1/N rule in terms of **Sharpe ratio, certainty-equivalent return, or turnover**, indicating that
> out of sample, the gain from optimal diversification is more than offset by estimation error."*

★ 질문에서 찾던 구체적 수치:

> *"the **estimation window** needed for the sample-based mean-variance strategy and its extensions to
> outperform the 1/N benchmark is around **3000 months for a portfolio with 25 assets** and about
> **6000 months for a portfolio with 50 assets**."*

3,000개월 = **250년**, 6,000개월 = **500년**.

**한계 표시**: 나는 이 논문의 **초록 전문만 확보**했고 본문 PDF는 열지 못했다(§5).
다만 위 문장은 출판사 초록 텍스트이며 여러 미러에서 자구가 동일하다.

★ **함의**: "1/N보다 나은 게 없다"가 아니라 **"추정오차를 이길 만큼의 표본이 인간의 수명 안에 없다"**가 정확한 독법이다.
§1.2의 SR 판별 16년, §2의 Chopra-Ziemba 20:2:1과 같은 근원(평균 추정의 어려움)에서 나온 결과다.

### 4.6 종목 수와 소액 계좌

#### 최소 종목 수 — Statman (1987)

Meir Statman, "How Many Stocks Make a Diversified Portfolio?"
*Journal of Financial and Quantitative Analysis* 22(3), Sept 1987, pp. 353–363.
출판사 초록: https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/how-many-stocks-make-a-diversified-portfolio/CE5CDF2C7225FC1E0EDE3E700A3C66A7

> *"We show that a well-diversified portfolio of randomly chosen stocks must include **at least
> 30 stocks for a borrowing investor and 40 stocks for a lending investor**."*

★ 이 논문의 요점은 통설을 **반박**하는 것이었다 — 당시 통설은 "10종목이면 분산 이익이 거의 소진된다"였다.
그리고 "30종목"은 상한이 아니라 **하한**이다. `randomly chosen`이라는 단서도 중요하다 —
체계적으로 고른(따라서 상관이 높은) 포트폴리오에는 더 많은 종목이 필요하다.

**한계 표시**: 출판사 초록만 확인했고 본문은 열지 못했다(§5).

#### 개인투자자의 실제 분산 상태 — Goetzmann & Kumar

William N. Goetzmann & Alok Kumar, "Equity Portfolio Diversification," NBER Working Paper 8686, Dec 2001.
NBER 원문 PDF: https://www.nber.org/system/files/working_papers/w8686/w8686.pdf
데이터: 대형 할인증권사 40,000+ 계좌, 1991–96.

> *"we find that **a vast majority of investors in our sample are under-diversified.** ...
> Investors are aware of the benefits of diversification but they appear to adopt a **'naive'
> diversification strategy where they form portfolios without giving proper consideration to
> the correlations among the stocks.**"*

정량:

> *"the normalized variance of concentrated portfolios is approximately **3-4 times** the normalized
> variance of well diversified portfolios. For example, in 1996, the normalized variance of
> well-diversified portfolios with 11-15 stocks is **0.163** while concentrated portfolios with only
> 2 stocks on average have a normalized variance of **0.407**."*

★ **회전율과 분산의 상관** — 이 프로젝트에 특히 관련 있다:

> *"The average number of stocks (D3 measure) in portfolios in the **bottom 2 turnover deciles** are
> **7.91 and 7.22** respectively while the average number of stocks in portfolios in the
> **top 2 turnover deciles** are **5.38 and 5.05** respectively."*
> (KS 검정 p < 0.01)

즉 **많이 거래하는 사람일수록 더 집중되어 있다.** 두 실수(과회전 + 과집중)가 같이 온다.

> *"investors in low income and non-professional categories hold the least diversified portfolios.
> ... young, active investors are over-focused and hold under-diversified portfolios."*

한편 Barber & Odean (2000)은 자기 표본의 평균 보유종목이 **4개**라고 적는다:

> *"With an average holding of **four common stocks**, we believe that risk-based rebalancing is not
> a significant motivation for trading in the households that we study."*

#### 소액 계좌에서의 긴장

문헌은 **두 방향의 압력을 각각 확인해 주지만, "계좌가 얼마 이하면 종목 수를 몇 개로"라는 형태의
1차 가이드는 찾지 못했다** (§5). 확인된 것은 다음 두 사실이고, 이들이 서로 충돌한다.

1. **분산 요구는 위쪽**: Statman 30~40종목 하한; 2종목 포트폴리오의 정규화 분산이 11–15종목의 약 2.5배.
2. **고정비용 요구는 아래쪽**: Barber & Odean — *"individuals execute small trades and face
   **higher proportional commission costs** than mutual funds"*; $1,000 초과 거래도 왕복 4%가 들었다.
   계좌가 작을수록 종목 수를 늘리면 건당 주문금액이 고정비용 하한에 눌린다.

DGU(§4.5)는 이 긴장에 대해 **가중치 최적화로 풀려 하지 말라**는 답을 준다 — 최적화의 이득이
추정오차에 잡아먹히므로, 종목 수를 정한 뒤 1/N으로 두는 편이 낫다는 것이 그 논문의 직접적 함의다.
DGU가 1/N을 **turnover 기준으로도** 이겼다는 점도 소액 계좌에 유리한 방향이다.

---

## 5. 확실하지 않은 것

1차 출처로 확정하지 못한 항목을 정직하게 적는다.

### 본문을 열지 못하고 초록·요약만 확보한 것

1. **DeMiguel, Garlappi & Uppal (2009)** — SSRN(403)·Oxford Academic·LBS 리포지토리·저자 페이지
   모두 본문 PDF 접근에 실패했다. `3000개월 / 6000개월`, `14개 모형 / 7개 데이터셋` 수치는
   **출판사 초록 텍스트**(EconPapers/RePEc 미러)에서 확보한 것이며, 여러 미러에서 자구가 동일하다.
   본문의 시뮬레이션 설정과 가정은 확인하지 못했다.
2. **Statman (1987)** — Cambridge 출판사 **초록만** 읽었다. ResearchGate PDF는 403.
   `30 / 40 종목` 수치는 초록 원문이지만, 그 값이 도출된 가정(차입금리, 표본기간, 분산 잔여율 기준)은
   확인하지 못했다. 이 수치를 쓸 때는 "무작위 선택 가정"이라는 단서를 반드시 붙여야 한다.
3. **Perold & Sharpe (1988)** — CFA Institute 페이지의 초록·요약만 읽었다. 본문 PDF는 유료 장벽.
   "trendless but volatile markets" 등 인용문은 그 요약 페이지에서 온 것이다.
4. **Chopra & Ziemba (1993), *Journal of Portfolio Management*** — 원문을 읽지 못했다.
   `20:2:1`과 `100:3:1`은 **Ziemba & MacLean 챕터가 인용한 형태**로만 확보했다. 2차 인용이다.

### 1차 출처를 찾지 못했거나 수치를 확보하지 못한 것

5. **Nicolosi, Peng & Zhu (2009), "Do individual investors learn from their trading experience?",
   *Journal of Financial Markets* 12(2), 317–336.**
   ScienceDirect 403. RePEc 학술지 페이지와 Yale 워킹페이퍼 초록만 확보했다.
   초록은 *"trade quality ... **significantly increases with experience**"*, *"trading experience ...
   **significantly helps improve** investors' portfolio performance"* 수준의 **정성적 서술뿐이고,
   요청받은 효과 크기(bp, %)는 초록에 없다.** 본문을 못 열었으므로
   **이 논문에서는 어떤 정량 수치도 인용하지 않았다.**
   - https://ideas.repec.org/a/eee/finmar/v12y2009i2p317-336.html
   - https://ideas.repec.org/p/ysm/somwrk/ysm439.html

6. **Vanguard "Best practices for portfolio rebalancing" (Jaconetti, Kinniry & Zilbering)** —
   널리 인용되는 *"annual or semiannual monitoring with rebalancing at 5% thresholds"* 권고문을
   **공식 Vanguard 도메인에서 확인하지 못했다.** 검색에 뜬 사본은 전부 Scribd, squarespace,
   pdf4pro, tinkoffjournal 등 **제3자 재호스팅**이라 1차 출처로 인용하지 않았다.
   ★ 대신 내가 실제로 읽은 Vanguard 공식 문서(§4.1)는 **특정 임계·빈도 권고를 명시적으로 거부한다**.
   따라서 "Vanguard가 5% 밴드를 권고한다"는 통설은, 적어도 내가 접근할 수 있었던 Vanguard 1차 문서만
   놓고 보면 **뒷받침되지 않는다.** 해당 문구가 구판에 실제로 있는지는 미확인 상태다.

7. **full Kelly의 드로다운 확률 공식** — "full Kelly에서 자산이 초기값의 x배까지 떨어질 확률이 x이고,
   half Kelly에서는 x³"이라는 널리 인용되는 결과의 1차 출처를 확보하지 못했다.
   Thorp (2006) "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"의
   ch3/ch7 PDF(sites.oxy.edu 호스팅)를 내려받았으나 **텍스트 레이어 없는 스캔 이미지**여서 읽지 못했다.
   따라서 이 공식은 본문에 인용하지 않았다. 확보한 정량 드로다운 근거는
   **Ziemba & MacLean의 Table 1.3 시뮬레이션**(§4.3)뿐이다.

8. **"half-Kelly = 성장률 75% + 변동성 50%"** — §4.3에서 연속시간 lognormal 가정 하에 직접 유도했고
   대수적으로 참이지만, **이 문장 형태의 1차 인용문은 확보하지 못했다.**
   유도에 쓴 `Var G(f) = s²f²`는 Thorp 챕터가 Thorp (2006) eqn (7.3)로 인용한 것이며,
   나는 Thorp (2006) 원문을 직접 확인하지 못했다.

9. **금융 분야의 outcome bias / 노이즈 하 학습에 대한 엄밀한 1차 문헌** — 요청받았으나
   해당 주제를 정면으로 다룬 논문을 특정하지 못했다.
   §2는 대신 Lo(2002)·Seru et al.(2010)·AMS(2014)·Chopra-Ziemba에서 **내가 조합한 논증**이며,
   단일 1차 출처의 주장이 아니다. 그렇게 표시해 두었다.

10. **소액 계좌의 최소 종목 수 가이드** — "계좌 규모가 X 이하일 때 종목 수 Y"라는 형태의
    1차 권고를 찾지 못했다. §4.6의 서술은 서로 다른 논문의 두 사실을 병치한 것이지,
    어느 논문도 그 트레이드오프를 직접 풀지 않았다.

### 호스팅 출처에 대한 단서

11. **Lo (2002) 본문 PDF** — Berkeley 학생단체 서버(traders.studentorg.berkeley.edu) 사본을 읽었다.
    게재본 스캔이 맞다고 판단했지만(페이지 머리말·저작권 표시·페이지 번호 36–52 일치)
    출판사 호스팅은 아니다.
12. **Thorp "Understanding the Kelly Criterion"** — rybn.org 미러를 읽었다. 저자·출판사 호스팅이 아니다.
13. **Ziemba & MacLean 챕터** — 에든버러대 개인 페이지 호스팅 사본. Springer 원본이 아니다.
14. **Seru et al. (2010)** — 공동저자 Shumway 본인 사이트의 JSTOR 스캔본. 사실상 1차로 취급했다.
15. **Vanguard 문서** — vanguardsouthamerica.com은 Vanguard 공식 도메인이다.
    표지에 *"For institutional and sophisticated investors only. Not for public distribution."*이 찍혀 있어
    미국 리테일 배포판과 판본이 다를 수 있다.

---

## 6. 참고 — 확보한 1차 출처 목록

| # | 출처 | URL | 접근 수준 |
|---|---|---|---|
| 1 | Lo (2002), *FAJ* 58(4) | https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf | 본문 전체 (제3자 사본) |
| 2 | Seru, Shumway & Stoffman (2010), *RFS* 23(2) | http://tylergshumway.org/Seru-LearningTrading-2010.pdf | 본문 전체 (저자 사이트) |
| 3 | Barber, Lee, Liu, Odean & Zhang (2017 wp) | https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf | 본문 전체 (저자 사이트) |
| 4 | Barber & Odean (2000), *JF* 55(2) | https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/Individual_Investor_Performance_Final.pdf | 본문 전체 (저자 사이트) |
| 5 | Barber & Odean (2001), *QJE* 116(1) | https://faculty.haas.berkeley.edu/odean/papers/gender/boyswillbeboys.pdf | 본문 전체 (저자 사이트) |
| 6 | Barber, Lee, Liu & Odean (2009), *RFS* 22(2) | https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf | 본문 전체 (저자 사이트) |
| 7 | Bailey & López de Prado (2012), *J. of Risk* 15(2) | https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf | 본문 전체 (저자 사이트) |
| 8 | Bailey, Borwein, López de Prado & Zhu (2014), *Notices of the AMS* 61(5) | https://www.ams.org/notices/201405/rnoti-p458.pdf | 본문 전체 (출판사 OA) |
| 9 | Kelly (1956), *BSTJ* 35 | https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf | 본문 전체 (AT&T 허가 재수록) |
| 10 | Thorp, "Understanding the Kelly Criterion" | https://rybn.org/halloffame/PDFS/2008_Understanding_Kelly_New.pdf | 본문 전체 (미러) |
| 11 | Ziemba & MacLean (2011), Springer Ch.1 | https://webhomes.maths.ed.ac.uk/mckinnon/blackouts/StochOptFinanceAndEnergySpringer/Chap1_KellyZiemba.pdf | 본문 전체 (대학 사본) |
| 12 | Vanguard, "Getting back on track" | https://www.vanguardsouthamerica.com/content/dam/intl/americas/documents/latam/en/sa-2123766-getting-back-on-track.pdf | 본문 전체 (Vanguard 공식) |
| 13 | Goetzmann & Kumar (2001), NBER WP 8686 | https://www.nber.org/system/files/working_papers/w8686/w8686.pdf | 본문 전체 (NBER 원문) |
| 14 | Perold & Sharpe (1988), *FAJ* 44(1) | https://rpc.cfainstitute.org/research/financial-analysts-journal/1988/dynamic-strategies-for-asset-allocation | 초록·요약만 |
| 15 | DeMiguel, Garlappi & Uppal (2009), *RFS* 22(5) | https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:5:p:1915-1953 | 초록만 |
| 16 | Statman (1987), *JFQA* 22(3) | https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/how-many-stocks-make-a-diversified-portfolio/CE5CDF2C7225FC1E0EDE3E700A3C66A7 | 초록만 |
| 17 | Nicolosi, Peng & Zhu (2009), *JFM* 12(2) | https://ideas.repec.org/a/eee/finmar/v12y2009i2p317-336.html | 초록만 (정량치 없음) |
