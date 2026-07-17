# Phase 2 — 데이터 파이프라인 (S&P500 파일럿 → Qlib bin)

yfinance로 미국주식 일봉을 수집하고 Qlib `.bin` 포맷으로 변환한다.
파일럿: S&P500 대형주 41종목([../../universe/sp500_pilot.txt](../../universe/sp500_pilot.txt)), 2015~현재(~2900거래일).

## 접근 (하이브리드)

- **수집**: yfinance 직접(`01_collect.py`) — 재시도·backoff·폴백 내장(개선9)
- **정규화**: Qlib `YahooNormalize1d`(v0.9.7) 로직 자작 포팅(`02_normalize.py`)
- **bin 변환**: qlib 공식 `dump_bin.py`만 vendoring([../../vendor/](../../vendor/)) 호출(`03_dump_bin.py`)

수집·정규화는 자작(가볍고 통제 쉬움), 재구현 위험 큰 bin 포맷만 공식 코드 사용.

## 실행

```bash
# 전체 파이프라인 (수집→정규화→dump→검증)
.venv/bin/python scripts/phase2/run_pipeline.py

# 개별 단계
.venv/bin/python scripts/phase2/01_collect.py            # → data/raw/*.csv
.venv/bin/python scripts/phase2/02_normalize.py          # → data/normalized/*.csv
.venv/bin/python scripts/phase2/03_dump_bin.py           # → data/qlib_us/{calendars,instruments,features}
.venv/bin/python scripts/phase2/04_verify.py             # 검증 게이트

# 부분 수집 / 재빌드만
.venv/bin/python scripts/phase2/run_pipeline.py --symbols AAPL MSFT
.venv/bin/python scripts/phase2/run_pipeline.py --skip-collect
```

Phase 3에서 `qlib.init(provider_uri="data/qlib_us", region=REG_US)`로 사용.

## 증분 갱신

**전체 재빌드로 처리** — `run_pipeline.py` 재실행. 41종목이면 1~2분.
factor 재계산·달력 드리프트 위험을 없애려 `dump_update`(증분 append) 대신 매번
전체 재빌드(멱등·안전). vendor에 `dump_update`는 있으나 파일럿 규모엔 불필요.

## 정규화 규약 (Qlib 정합)

- `factor = adjclose / close` (ffill). OHLC는 `× factor`(수정주가), volume은 `÷ factor`.
- 첫 유효 close로 정규화 → `$close` 첫날 ≈ 1.0.
- **원가(체결가) 복원**: `raw_price = $close / $factor` (백테스트 실제 거래가에 사용).
- `volume<=0`/NaN 행은 전 컬럼 NaN → **결측 유지(ffill 금지)**, lookahead 방지.

## ⚠️ 한계 (백테스트 해석 시 반드시 반영)

- **[개선3] point-in-time 미적용 / 생존편향**: 유니버스가 **현재 S&P500 구성 고정**이다.
  과거 시점의 실제 지수 구성원이 아니며, 지금 살아남은 대형주만 담겨 있다.
  → 편입/편출·폐지 종목 누락으로 **백테스트 성과가 과대평가**될 수 있다.
  파일럿 단계의 알려진 한계로 기록하며, Phase 3 결과 해석에 보정 관점으로 반영한다.
  이후 확장: 시점별 지수구성 + 폐지종목 포함 데이터 확보.
- **yfinance 취약성(개선9)**: 비공식 스크래퍼라 간헐 차단·스키마 변경 가능.
  수집기에 재시도·backoff·직전 정상 CSV 폴백을 두었으나, 지속 실패 시
  토스 candle API 폴백은 추후 검토.
- **vwap 없음**: yfinance는 vwap 미제공. Alpha158은 OHLCV+factor로 동작(vwap 불요).

## 산출물

| 경로 | 내용 | git |
|------|------|-----|
| `universe/sp500_pilot.txt` | 파일럿 티커 | 커밋 |
| `data/raw/*.csv` | yfinance 원본(OHLCV+adjclose) | 무시 |
| `data/normalized/*.csv` | 정규화(factor 포함) | 무시 |
| `data/qlib_us/` | Qlib bin (provider_uri) | 무시 |
