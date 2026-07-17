# Phase 0 실측 툴킷

계획서(`qlib-toss.md`) Phase 0의 미확정 값을 실측으로 확정한다.
**0-1(키 발급)은 사람이 하는 수동 작업**, 나머지는 아래 스크립트로 측정한다.

## 사전 준비 (1회)
```bash
# 이미 .venv(3.10.13)가 만들어져 있고 requests/python-dotenv가 설치됨.
cp .env.example .env          # 그리고 .env에 발급받은 키를 채운다
```
스크립트는 항상 프로젝트 루트에서 `.venv/bin/python scripts/toss_probe/XX.py` 로 실행.

## 0-1. 키 발급 (수동)
1. 토스 앱에서 토스증권 계좌 개설(비대면)
2. PC 웹 `https://developers.tossinvest.com` → 계좌 연동 로그인
3. OpenAPI 사전신청 → 승인 후 `client_id`/`client_secret` 발급
4. `.env`의 `TOSS_CLIENT_ID`/`TOSS_CLIENT_SECRET`에 입력 (git 커밋 금지)

## 실행 순서
| 스크립트 | 계획 항목 | 하는 일 |
|----------|-----------|---------|
| `00_check_token.py` | 0-1 검증 | 토큰 발급 성공 확인 |
| `01_accounts.py` | 0-2 | 계좌 목록 → 계좌식별자 확인 후 `.env`의 `TOSS_ACCOUNT`에 입력 |
| `05_holdings_settlement.py` | 0-2 검증 / 0-6 | holdings 200 확인 / 매도 후 반복 실행해 T+N 관찰 |
| `02_stock_info.py AAPL MSFT` | 0-3 | 종목 시장·통화·상장상태 + 장운영시간 |
| `03_buying_power_fx.py` | 0-5 | 매수가능금액(USD 노출 여부)·환율 → 환전 방식 판단 |
| `04_place_test_order.py` | 0-3·0-4·0-7 | ⚠️ **실제 소액 주문**. 소수점 가능 여부·최소금액·rate-limit 실측 |

## ⚠️ 04_place_test_order.py 안전 사용
- 기본은 **dry-run**(발주 안 함). 실제 발주는 `--confirm` 필요.
- `orderAmount` 매수는 **미국 정규장에만** 성공 → 정규장 시간에 실행.
- 최소금액 실측이면 `--amount 1` 처럼 아주 작게.
```bash
# 1) 계획만 확인(안전)
.venv/bin/python scripts/toss_probe/04_place_test_order.py --symbol AAPL --amount 1
# 2) 정규장 시간에 실제 발주
.venv/bin/python scripts/toss_probe/04_place_test_order.py --symbol AAPL --amount 1 --confirm
```
에러코드 판독은 스크립트 출력 안내 및 `qlib-toss.md` §1 참고.

## 결과 기록
모든 측정값은 `phase0-findings.md`에 기록. 7개 항목 + K값/유니버스 확정 시 Phase 1 착수.
