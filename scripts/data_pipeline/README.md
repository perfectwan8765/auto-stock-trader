# Phase 2 — 데이터 파이프라인 (S&P500 → Qlib bin)

yfinance로 미국주식 일봉을 수집하고 Qlib `.bin` 포맷으로 변환한다.
**기본 유니버스: S&P500 전체 503종목 + 벤치 SPY**([../../universe/sp500_full.txt](../../universe/sp500_full.txt), Wikipedia 스크랩 `gen_sp500_universe.py`), 2015~현재(~2900거래일).
파일럿 41종목([../../universe/sp500_pilot.txt](../../universe/sp500_pilot.txt))은 `QLIB_UNIVERSE=sp500_pilot.txt`로 재현.

## 접근 (하이브리드)

- **수집**: yfinance 직접(`01_collect.py`) — 재시도·backoff·폴백 내장(개선9)
- **정규화**: Qlib `YahooNormalize1d`(v0.9.7) 로직 자작 포팅(`02_normalize.py`)
- **bin 변환**: qlib 공식 `dump_bin.py`만 vendoring([../../vendor/](../../vendor/)) 호출(`03_dump_bin.py`)

수집·정규화는 자작(가볍고 통제 쉬움), 재구현 위험 큰 bin 포맷만 공식 코드 사용.

## 실행

```bash
# 전체 파이프라인 (수집→정규화→dump→검증)
uv run python scripts/data_pipeline/run_pipeline.py

# 개별 단계
uv run python scripts/data_pipeline/01_collect.py            # → data/raw/*.csv
uv run python scripts/data_pipeline/02_normalize.py          # → data/normalized/*.csv
uv run python scripts/data_pipeline/03_dump_bin.py           # → data/qlib_us/{calendars,instruments,features}
uv run python scripts/data_pipeline/04_verify.py             # 검증 게이트

# 부분 수집 / 재빌드만
uv run python scripts/data_pipeline/run_pipeline.py --symbols AAPL MSFT
uv run python scripts/data_pipeline/run_pipeline.py --skip-collect
```

Phase 3에서 `qlib.init(provider_uri="data/qlib_us", region=REG_US)`로 사용.

## 증분 갱신

**전체 재빌드로 처리** — `run_pipeline.py` 재실행. 파일럿 41종목 1~2분, 전체 503+SPY ~20분(yfinance 순차 수집).
factor 재계산·달력 드리프트 위험을 없애려 `dump_update`(증분 append) 대신 매번
전체 재빌드(멱등·안전). vendor에 `dump_update`는 있으나 파일럿 규모엔 불필요.

## 정규화 규약 (Qlib 정합)

- `factor = adjclose / close` (ffill). OHLC는 `× factor`(수정주가), volume은 `÷ factor`.
- 첫 유효 close로 정규화 → `$close` 첫날 ≈ 1.0.
- **원가(체결가) 복원**: `raw_price = $close / $factor` (백테스트 실제 거래가에 사용).
- `volume<=0`/NaN 행은 전 컬럼 NaN → **결측 유지(ffill 금지)**, lookahead 방지.
- **`$vwap` 프록시** = 조정·정규화된 `(H+L+C)/3`. Alpha158이 `$vwap`을 참조하는데
  yfinance가 미제공 → 표준 프록시로 합성(당일값이라 lookahead 없음). 아래 한계 참조.

## ⚠️ 한계 (백테스트 해석 시 반드시 반영)

- **[개선3] point-in-time 미적용 / 생존편향**: 유니버스가 **현재 S&P500 구성 고정**이다.
  과거 시점의 실제 지수 구성원이 아니며, 지금 살아남은 대형주만 담겨 있다.
  → 편입/편출·폐지 종목 누락으로 **백테스트 성과가 과대평가**될 수 있다.
  파일럿 단계의 알려진 한계로 기록하며, Phase 3 결과 해석에 보정 관점으로 반영한다.
  이후 확장: 시점별 지수구성 + 폐지종목 포함 데이터 확보.
- **yfinance 취약성(개선9)**: 비공식 스크래퍼라 간헐 차단·스키마 변경 가능.
  수집기에 재시도·backoff·직전 정상 CSV 폴백을 두었으나, 지속 실패 시
  토스 candle API 폴백은 추후 검토.
- **vwap 프록시**: Alpha158은 `$vwap`을 참조(feature `$vwap/$close` 등, 전체 158개 중 1~2개).
  yfinance는 실제 vwap 미제공 → `(H+L+C)/3`(전형적 프록시)로 합성. 실제 거래량가중가와
  다르므로 vwap 기반 feature는 근사. 영향 범위 작음(feature 1~2개).

## 산출물

| 경로 | 내용 | git |
|------|------|-----|
| `universe/sp500_full.txt` | 전체 503+SPY 티커 (기본) | 커밋 |
| `universe/sp500_pilot.txt` | 파일럿 41 티커 | 커밋 |
| `data/raw/*.csv` | yfinance 원본(OHLCV+adjclose) | 무시 |
| `data/normalized/*.csv` | 정규화(factor 포함) | 무시 |
| `data/qlib_us/` | Qlib bin (provider_uri) | 무시 |

## make 로 돌리기

의존 관계는 루트 [Makefile](../../Makefile)에 파일 단위로 선언돼 있다. 필요한 선행만 돌아간다.

```bash
make test              # 테스트 전량
make bundle-sp500      # S&P500 qlib 번들 재빌드
make bundle-microcap   # 마이크로캡 번들 (QLIB_UNIVERSE·QLIB_DATASET 자동 설정)
make check-dag         # 선언된 데이터 노드에 규칙이 다 있는지 확인

make data/events_addv.csv   # 이 산출물과 그 선행만
```

`universe/microcap_tradable.txt`는 `scripts/toss_probe/06_microcap_coverage.py`가 만드는
`data/toss_stock_meta.csv`에 의존한다 — 이 디렉터리만 봐서는 알 수 없는 교차 의존이라
Makefile에 명시돼 있다.

## 스테이지 구조

번호 붙은 파일(`01_collect.py` 등)은 CLI 껍데기이고 로직은 import 가능한 모듈에 있다.
번호로 시작하는 파일명은 Python 식별자가 아니라 import·단위테스트가 불가능하기 때문이다.

| CLI | 알맹이 |
|---|---|
| `01_collect.py` | `collect.py` — `download_one` · `last_date_of` |
| `02_normalize.py` | `normalize.py` — `normalize_one` |
| `04_verify.py` | `verify.py` — `stale_in_bundle` · `delisted_symbols` |
