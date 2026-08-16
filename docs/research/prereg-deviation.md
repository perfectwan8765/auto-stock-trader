# 리서치 — 사전등록 이탈 규범과 표본 감쇠 허용 임계

- 조사일: 2026-08-12
- 목적: `../project/microcap-insider-prereg.md` §3.3(kill 조건 재명세)의 정당성과 기록 형식, 그리고
  `../project/microcap-insider.md` §6(3)의 "결측 퇴출 비율 kill 임계 15%"에 문헌 근거가 있는지 확인
- ⚠️ **한계**: WWC 1차 문서는 전부 PDF이고 렌더링에 실패해 **본문을 직접 열지 못했다.**
  아래 WWC 수치는 **1차 문서에 대한 검색 요약**에서 온 것이며, 확정 인용 전에 PDF를 직접 확인해야 한다.
  COS·Willroth & Atherton은 본문을 직접 읽었다.

---

## 1. 사전등록 이탈은 언제 정당한가

### 1.1 COS의 선 — "데이터 분석 시작 전"이고, 요약통계 계산도 분석에 포함된다

[Center for Open Science, "Preregistration: A Plan, Not a Prison"](https://www.cos.io/blog/preregistration-plan-not-prison)

- 데이터 수집 중이라도 **"데이터 분석 시점까지는"** 새 사전등록을 만드는 것이 자유롭고 권장된다:
  *"you are free and encouraged to make a new preregistration up to the point of data analysis"*
- ★ 그런데 그 "데이터 분석"의 정의가 넓다 — **"which includes calculating summary statistics"**
- 그 선을 넘으면: *"After data analysis has begun, it becomes nearly impossible to determine if
  decisions are justifiable and are outcome-independent, as the outcome is now known"*
- 분석 시작 후의 새 분석은 **confirmatory가 아니라 exploratory로 이름 붙여야 한다**:
  *"label ... as what they are: data-dependent, exploratory analyses"*
- 이탈 시 요구되는 것: 원본 사전등록 보존 · 버전 간 링크 · **무엇을 왜 바꿨는지 명시** ·
  "a trail of ideas" 유지
- **아직 공개·확정되지 않은 사전등록**은 데이터 수집 전이라면 같은 OSF 프로젝트에서
  새 사전등록을 시작하면 된다(원본은 철회하거나 참고용으로 남긴다)

### 1.2 Willroth & Atherton — 이탈 **시점**이 5단계로 분류돼 있다

[Willroth & Atherton (2024), "Best Laid Plans: A Guide to Reporting Preregistration Deviations",
*AMPPS*](https://journals.sagepub.com/doi/full/10.1177/25152459231213802)

이탈 시점 taxonomy (본문 인용):

> *"Deviations can occur at any point in the research process, including before data were collected,
> during data collection, **after data collection but before data were accessed**,
> **after data were accessed but before results of preregistered approach were known**,
> and after results of preregistered approach were known."*

★ **네 번째 항목이 이 프로젝트의 상황과 정확히 일치한다** — 데이터에는 접근했지만
사전등록된 접근법의 *결과*(CAR)는 아직 모르는 상태. **이 구분은 문헌에 실재하는 범주다.**

다만 같은 논문이 못박는다: **"data-dependent deviations increase risk of bias."**
시점 범주가 있다는 것이 면죄부라는 뜻은 아니다.

**이탈 유형 8~10개 범주**: study design · inclusion/exclusion criteria · research question ·
hypotheses · sample size · data preparation · variable operationalization · analytic approach ·
covariates · **inferential criteria**

**이탈 사유 6개 범주**: 오타/실수 · 데이터 수집 오류 · **사전등록 계획이 불가능하거나 부적절함** ·
연구자가 새 지식을 얻음 · 리뷰어/편집자 제안 · 공저자 간 소통 오류

**실증**: 사전등록 연구의 **82%가 최소 1건 이탈**했고 **55%만 보고**했다.
*Psychological Science*에서는 93%가 이탈, **64%만 보고**. → **이탈은 정상이고, 미보고가 실패다.**

### 1.3 방향성(제약 완화 vs 강화)

Willroth & Atherton은 **완화/강화를 명시적으로 구분하지 않는다.** 다만 편집자들이
**투명성을 1순위 판단 요인**으로 꼽았고, "개선으로 인식되는 이탈"이 "악화로 인식되는 이탈"보다
호의적으로 평가됐다고 보고한다.

---

## 2. 이탈 기록의 표준 형식

### 2.1 Preregistration Deviations Table (Willroth & Atherton)

필드가 정해져 있다:

| 필드 | 내용 |
|---|---|
| 번호 | 행 식별자 |
| **Type** | §1.2의 유형 범주에서 선택 |
| **Reason** | §1.2의 사유 범주에서 선택 |
| **Timing** | §1.2의 시점 범주에서 선택 |
| **Original wording** | 사전등록 원문 그대로 |
| **Deviation description** | 무엇으로 바꿨는가 |
| **Reader impact statement** | 독자가 결과를 해석할 때 이 이탈이 어떤 영향을 주는가 |

### 2.2 OSF amendment 메커니즘

[COS blog](https://www.cos.io/blog/preregistration-plan-not-prison) 및 관련 가이드 기준:

- admin contributor가 update를 요청하고 **변경 사유를 적으며**, **바꾸는 필드만** 수정한다
- 초기 등록과 **같은 심사 절차**(48시간 admin 승인)를 거친다
- ★ **원본 등록은 그대로·날짜와 함께 남고**, 수정은 **별도 타임스탬프의 독립된 개정**으로 기록된다
- 별도로 **Transparent Changes 문서** 템플릿이 있고, 등록을 시작한 OSF 프로젝트에 업로드해
  결과 보고 시 참조한다

**핵심 원칙**: *"Any decision that you would make differently if you already knew the direction of
your results is a deviation that requires transparent reporting."*

---

## 3. 표본 감쇠(attrition) 허용 임계

### 3.1 What Works Clearinghouse — 유일하게 숫자 경계가 규정된 표준

1차 문서: [WWC Standards Handbook v4.1](https://ies.ed.gov/ncee/WWC/Docs/referenceresources/WWC-Standards-Handbook-v4-1-508.pdf) ·
[WWC Standards Attrition Brief](https://ies.ed.gov/ncee/wwc/Docs/ReferenceResources/WWC-Attrition-Brief-v4_508_updated.pdf) ·
[Handbook v5.0](https://ies.ed.gov/ncee/wwc/Docs/referenceresources/Final_WWC-HandbookVer5.0-0-508.pdf)

⚠️ **아래 수치는 위 PDF의 검색 요약에서 온 것이다. PDF 본문 렌더링에 실패했다.**

**구조**: `(전체 감쇠율, 차등 감쇠율)` 평면을 세 영역으로 나눈다 —
① 모든 가정에서 저편향 ② 가정에 따라 갈림 ③ 모든 가정에서 고편향.
**cautious 경계**는 ①만 low attrition으로 보고, **optimistic 경계**는 ①+②를 low로 본다.

`Table II.1 — Highest Differential Attrition Rate for a Sample to Maintain Low Attrition,
by Overall Attrition Rate, Under "Optimistic" and "Cautious" Assumptions`

| 전체 감쇠율 | 최대 차등 감쇠 (cautious) | 최대 차등 감쇠 (optimistic) |
|---:|---:|---:|
| 0% | **5.7 %p** | **10.0 %p** |
| 13% | **6.1 %p** | **10.8 %p** |
| 65% | **어떤 값도 low attrition 불가** | 0.3 %p |

**어느 경계를 쓰는가**: 개입이 감쇠에 영향을 줄 개연성이 있으면 cautious,
없으면 optimistic. (예: 중퇴 예방 프로그램 → cautious / 1학년 읽기 프로그램 → optimistic)

**확인하지 못한 것**: cautious 경계에서 "전체 감쇠율이 X% 넘으면 무조건 high"의 정확한 X값,
high attrition 판정의 구체적 귀결(배제인지 조건부 인정인지), 경계를 도출한 편향 모형의 가정.

### 3.2 다른 표준

- **Cochrane RoB 2 / ROBINS-I**, **CONSORT** — 이번 조사에서 **구체적 수치 경계를 확인하지 못했다.**
  Cochrane은 숫자 컷오프보다 "결측 메커니즘이 결과와 관련되는가"를 판단하는 도메인 방식으로 알고 있으나
  **1차 출처로 확인하지 않았으므로 인용하지 않는다.**

### 3.3 금융·자산가격 분야

이번 조사에서 **사전등록 이탈이나 감쇠 임계를 규정한 금융 분야 표준을 찾지 못했다.**
관련 인접 문헌은 계획서가 이미 인용 중이다 — delisting bias 보정값
([Shumway 1997](https://www.tylergshumway.org/Shumway-DelistingBiasCRSP-1997.pdf)),
다중검정 허들([Harvey-Liu-Zhu 2016](https://academic.oup.com/rfs/article-abstract/29/1/5/1843824)).
**금융에는 WWC 같은 감쇠 경계 규정이 없다는 것이 이번 조사의 결론이다.**

---

## 4. 이 프로젝트에 대한 함의

### 4.1 문헌이 **지지하는** 것

1. **"데이터는 봤지만 결과는 안 봤다"는 구분은 실재한다.**
   Willroth & Atherton의 시점 taxonomy에 *"after data were accessed but before results of
   preregistered approach were known"* 가 독립 범주로 있다.
2. **미커밋 사전등록의 수정은 가장 방어하기 쉬운 자리다.**
   COS는 분석 시작 전이라면 새 사전등록을 만드는 것을 "free and encouraged"라 한다.
3. **이탈 자체는 정상이다.** 82%가 이탈하고 55%만 보고한다. **실패 지점은 이탈이 아니라 미보고다.**
4. **"계획이 부적절했음"은 인정된 이탈 사유 범주다**(preregistered plan not possible/inappropriate).
   kill 조건이 잘못 명세됐다는 판단은 지어낸 변명 유형이 아니다.

### 4.2 문헌이 **지지하지 않는** 것 — 반드시 함께 읽을 것

1. ★ **COS의 선은 우리가 생각한 것보다 앞에 있다.** *"data analysis ... includes calculating
   summary statistics."* 우리는 퇴출 시점 분위수·ADDV 분포·클러스터 분포를 계산했다.
   **COS 기준으로는 이미 "분석 시작" 이후다.**
   - 완화 논거: 그 통계는 **결과변수(CAR)가 아니라 공변량·구조**에 대한 것이다
   - 그러나 COS 문구는 그 구분을 두지 않는다. **이 완화 논거는 우리 해석이지 문헌의 문구가 아니다**
2. **시점 범주가 면죄부가 아니다.** *"data-dependent deviations increase risk of bias."*
3. **제약을 느슨하게 하는 이탈을 별도로 허용하는 규정은 없다.** 다만 편집자들은
   "개선으로 보이는 이탈"에 호의적이었다 — 이는 규범이 아니라 관찰이다.
4. **15%라는 숫자에 문헌 근거가 없다.** WWC 경계는 **RCT의 처치/대조 간 차등 감쇠**에 대한 것이고,
   우리에게는 **처치군이 없어 차등 감쇠가 정의되지 않는다.** 우리가 재는 "보유기간 내 퇴출 비율"은
   WWC가 재는 것과 다른 양이다. **15%는 프로젝트 고유의 임의값이며 그렇게 표기해야 한다.**

### 4.3 전체 결측률(16%)에 대해서는 WWC를 유비할 수 있다

주 표본 커버리지 84% → **전체 결측 16%**. 차등 감쇠는 정의되지 않으므로 **≈0으로 놓으면**
WWC 표에서 13% 전체 감쇠에 cautious 6.1%p까지 허용되는 영역 안에 들어온다 →
**"저감쇠(low attrition)" 영역**으로 볼 수 있다.

⚠️ 단, WWC의 차등 감쇠가 잡으려는 위험(결측이 처치와 상관)의 우리 쪽 대응물은
**"결측이 신호와 상관"** 이고, 계획서 §7.3(a)가 이미 이를 **가장 위험한 실패 모드**로 지목했다.
**그 위험은 전체 결측률 16%로 해소되지 않는다** — 별도로 다뤄야 한다.

### 4.4 권고 — 무엇을 바꿔야 하는가

| # | 조치 |
|---|---|
| 1 | **§3.11.5·prereg §3.3을 Willroth & Atherton의 Deviations Table 형식으로 재작성.** 지금은 산문이라 `Type`·`Reason`·`Reader impact`가 빠져 있다. 유형 = **inferential criteria**, 사유 = **preregistered plan not possible/inappropriate**, 시점 = **after data were accessed but before results were known** |
| 2 | **COS 기준으로는 이미 분석 시작 이후임을 문서에 적을 것.** 완화 논거(공변량 vs 결과변수)는 **우리 해석임을 명시**하고, 반대 해석의 여지를 남긴다 |
| 3 | **15%를 "문헌 근거 없는 프로젝트 고유 임의값"으로 표기.** WWC를 근거로 끌어오지 말 것 — 재는 양이 다르다 |
| 4 | **전체 결측률 16%에 대해서는 WWC 유비를 근거로 쓸 수 있다**(저감쇠 영역). 단 "차등 감쇠 미정의" 단서를 함께 |
| 5 | 사전등록 커밋 시 **원본과 개정을 둘 다 남긴다**(OSF amendment 관행). 이미 §3.11.5가 그렇게 하고 있다 — **유지** |

---

## 5. 확인하지 못한 것

- WWC PDF 본문(렌더링 실패). 위 수치는 1차 문서에 대한 검색 요약이다 — **확정 인용 전 직접 확인 필요**
- cautious 경계의 전체 감쇠 상한 정확값
- Cochrane RoB 2 / ROBINS-I / CONSORT의 구체적 수치 기준
- 금융 저널(Critical Finance Review 등)의 registered report 정책 본문
