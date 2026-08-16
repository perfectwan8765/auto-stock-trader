# 실집행 원장(SQLite) 설계

실주문이 시작되면(토스 연동, Phase 0) 주문·체결·포지션은 재생성이 불가능한 사실 데이터가 된다.
이 문서는 그 사실을 담을 SQLite 원장의 설계를 정한다. **설계 확정 문서이며 구현은 Phase 0에서 한다.**

전체 계획은 [qlib-toss.md](qlib-toss.md), 구조는 [README.md](README.md) §디렉토리 참고.

## 왜 파일 기반 SQLite인가

가격 데이터·백테스트 산출(mlruns)·시그널은 코드와 입력으로 다시 만들 수 있어 파일(.bin/pkl/JSON)로 충분하다.
반면 **실제 나간 주문과 체결은 재생성이 불가능**하고, 조회·대사·감사가 필요하다.

- RDB 서버(Postgres 등)·Docker는 이 규모(단일 사용자, 주간 리밸런싱, 단일 라이터)에 과설계다.
- SQLite는 **파일 하나**로 서버 없이 트랜잭션·SQL 조회·원자적 쓰기를 제공한다. 파일 기반의 장점을 유지하면서 JSON의 한계(집계 불가, 같은 날 덮어쓰기)를 없앤다.

## 범위

원장은 **라이브 실행의 단일 진실 원본**이다. 기존 JSON(`signals/*.json`, `execution_logs/*.json`, managed 상태)을 대체한다.

- **경계:** 원장은 라이브 전용이다. 백테스트 탭은 계속 mlruns(pkl)를 읽는다. 대시보드는 소스가 둘이 된다 — mlruns(과거 검증), ledger.db(실거래). 이는 정상이며 섞지 않는다.

## 결정 로그

| # | 결정 | 근거 |
|---|---|---|
| 1 | 전체 상태 통합(runs·signals·orders·fills·positions·managed) | 한곳에서 조회 |
| 2 | DB 단일 진실, JSON 제거 | 일원화 |
| 3 | dry-run도 orders에 저장(`dry_run` 플래그) | 대시보드·코드 경로 단일화 |
| 4 | orders + fills 2테이블(1주문→N체결) | 부분체결 정확 처리 |
| 5 | managed = instruments 상태 테이블 + meta | 관계형·조회 가능 |
| 6 | positions = run별 브로커 스냅샷(pre-trade) | 브로커가 진실, DB는 이력·대사 |
| 7 | signals = 정규화 2테이블 | orders와 조인(목표 vs 실체결) |
| 8 | 재실행 = runs append + client_order_id UNIQUE | 이력 보존 + 멱등(덮어쓰기 결함 해소) |
| 9 | stdlib sqlite3 + `src/execution/ledger.py` | 신규 의존 0, 이 규모에 ORM은 과설계 |
| 10 | `data/ledger.db`, gitignore | 실계좌 데이터는 민감(.env처럼 커밋 금지) |
| 11 | 설계만 지금, 구현 Phase 0 | 미사용 기능 위해 검증된 코드 선개조 안 함 |

정제 사항(A·B·C·E·F·D): 아래 스키마·정책에 반영.

## 스키마

금액·주식수는 REAL, 타임스탬프는 UTC ISO8601 TEXT, 영업일은 YYYYMMDD TEXT.

```sql
-- 스키마 버전·부트스트랩 플래그 등
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- 목표 포트폴리오(시그널 헤더). generate_signal이 기록.
CREATE TABLE signals (
    id         INTEGER PRIMARY KEY,
    signal_date TEXT NOT NULL,          -- YYYYMMDD
    strategy   TEXT NOT NULL,
    topk       INTEGER,
    created_at TEXT NOT NULL,           -- UTC ISO8601
    UNIQUE(signal_date, strategy)
);

CREATE TABLE signal_weights (
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    symbol    TEXT NOT NULL,
    weight    REAL NOT NULL,
    PRIMARY KEY(signal_id, symbol)
);

-- 리밸런싱 실행 1건. 매 실행마다 append. (B) 계좌 스냅샷 컬럼 포함(pre-trade).
CREATE TABLE runs (
    id                INTEGER PRIMARY KEY,
    rebalance_date    TEXT NOT NULL,     -- YYYYMMDD
    strategy          TEXT,
    signal_id         INTEGER REFERENCES signals(id),
    dry_run           INTEGER NOT NULL,  -- 0/1
    aborted_reason    TEXT,              -- 예: market_closed
    cash_usd          REAL,              -- (B) pre-trade 계좌현금
    buying_power_usd  REAL,              -- (B) pre-trade 가용 USD
    equity_usd        REAL,              -- (B) pre-trade 평가액(보유+현금)
    created_at        TEXT NOT NULL      -- UTC ISO8601
);

-- 발주(intent + 브로커 접수 ack). client_order_id로 멱등.
CREATE TABLE orders (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,       -- BUY | SELL
    kind            TEXT NOT NULL,       -- amount(USD) | quantity(주식수)
    value           REAL NOT NULL,       -- kind=amount→USD, quantity→주식수
    reason          TEXT,                -- enter | add | trim | exit
    client_order_id TEXT NOT NULL UNIQUE,-- 결정적 멱등키. 재발주는 INSERT OR IGNORE
    broker_order_id TEXT,                -- place() ack
    status          TEXT NOT NULL,       -- placed | filled | partial | rejected | canceled
    dry_run         INTEGER NOT NULL,
    placed_at       TEXT,                -- UTC ISO8601
    created_at      TEXT NOT NULL
);

-- 체결(사후 주문조회로 기록). 1주문→N체결(부분체결). (F) client_order_id 병기.
CREATE TABLE fills (
    id              INTEGER PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id),  -- 해소 전엔 NULL(고아 체결 보존)
    client_order_id TEXT NOT NULL,        -- (F) 브로커 조회 키. 이걸로 order_id 해소
    fill_qty        REAL NOT NULL,
    fill_price      REAL NOT NULL,
    fee             REAL,
    broker_fill_id  TEXT,
    filled_at       TEXT NOT NULL,        -- UTC ISO8601
    created_at      TEXT NOT NULL
);

-- (A) 스킵된 주문(발주 안 됨). "왜 X를 안 샀나" 감사.
CREATE TABLE skipped (
    id         INTEGER PRIMARY KEY,
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    symbol     TEXT NOT NULL,
    reason     TEXT NOT NULL,   -- below_min_order | insufficient_buying_power | ... | excluded_manual
    created_at TEXT NOT NULL
);

-- run 시점 브로커 보유 스냅샷(pre-trade).
CREATE TABLE positions_snapshot (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    symbol      TEXT NOT NULL,
    qty         REAL NOT NULL,
    price       REAL,           -- 스냅샷 시점 가격
    value       REAL,           -- qty*price
    snapshot_at TEXT NOT NULL,
    UNIQUE(run_id, symbol)
);

-- managed 상태. 봇 관리(M) vs 사용자 수동보유(X, 봇 비관여).
CREATE TABLE instruments (
    symbol     TEXT PRIMARY KEY,
    status     TEXT NOT NULL,   -- managed | excluded
    updated_at TEXT NOT NULL
);
```

관계: `runs 1→N orders·skipped·positions_snapshot`, `runs N→1 signals`, `signals 1→N signal_weights`, `orders 1→N fills`.

인덱스: `orders(run_id)`, `fills(order_id)`, `fills(client_order_id)`, `positions_snapshot(run_id)`, `runs(rebalance_date)`, `skipped(run_id)`. (`orders(client_order_id)`는 UNIQUE로 자동.)

## 정책

### 금액·수량 타입 (D)

REAL(double)로 저장한다. 이 규모($10k 이하, 소수점 주식)에서 double 오차는 1센트에 훨씬 못 미치고, 정산 권위는 브로커다. 원장의 합산은 표시·분석용이다.

- 계산해서 쓰는 돈 값은 write 시 `round(x, 2)`. **브로커가 보고한 값은 받은 그대로 저장한다(왜곡 금지).**
- 주식수는 연속값이므로 REAL 그대로.
- 대사·동등 비교는 허용오차 `abs(Δ) < 0.005`. 부동소수 `==` 금지.
- 페니 완벽 자체회계가 필요해지면(다계좌·세무) 돈=INTEGER 센트 / 주식수=REAL 하이브리드로 승격하고 `orders.value`를 `amount_usd`/`qty`로 분리한다. 지금 규모엔 과함.

### 타임스탬프 (E)

- 모든 `*_at`은 **UTC ISO8601 TEXT**(`datetime.now(timezone.utc).isoformat()`). ledger.py의 `_utcnow()` 단일 소스. naive local 저장 금지.
- `rebalance_date`·`signal_date`는 미국장 영업일(YYYYMMDD, 시각 아님).
- ISO8601 UTC라 문자열 정렬 = 시간 정렬. 표시는 대시보드가 KST로 변환.

### 연결/동시성

- `PRAGMA foreign_keys=ON`(FK 강제, 기본 off), `PRAGMA journal_mode=WAL`(리더·라이터 동시), `PRAGMA busy_timeout=5000`(대사잡·대시보드 동시 쓰기 대비).
- 라이터는 단일(runner/스크립트), 대시보드는 리더.

## 체결 대사 흐름 (C)

`place()`는 접수 ack만 반환하고 실제 체결은 사후 주문조회로 받는다. managed(M) 갱신은 **발주 시점이 아니라 체결 확정 후**에 한다. 이것이 [managed.py](src/execution/managed.py)의 전량체결 가정 결함의 근본 해소다.

1. **발주:** orders INSERT(status=placed, broker_order_id=ack). M/X 건드리지 않음.
2. **대사(reconcile_fills):** 주문조회 → fills INSERT + order.status 갱신(filled/partial/rejected).
3. **M/X 갱신(대사 단계에서):**
   - BUY 체결 → 해당 symbol을 managed 추가
   - exit 전량체결(잔량 0) → managed 제거
   - **exit 부분체결(잔량 남음) → managed 유지** (버그 해소 지점)
   - bootstrap(첫 run에 현재 보유를 excluded로 동결)은 pre-trade 분류라 체결과 무관, 그대로.

의존성: M 갱신은 fills에 의존한다. 토스 주문조회가 붙기 전 잠정기에는 기존 전량체결 가정을 유지하고, 조회가 붙으면 위 post-fill 방식으로 전환한다.

## Phase 0 구현 체크리스트

- `src/execution/ledger.py` — 연결·스키마 init·`PRAGMA`·`_utcnow()`·record_run(계좌 포함)·record_signal·record_orders·record_skipped·record_fills·snapshot_positions·조회 API. 마이그레이션은 `PRAGMA user_version`(forward-only).
- `scripts/model_backtest/generate_signal.py` — JSON 대신 `record_signal()`.
- `src/execution/runner.py` — run 완료 시 record_run/orders/skipped/positions 기록. **발주 시 M 갱신(`update_after_place`) 제거.**
- 신규 `reconcile_fills()` — fills 기록 + order.status + **M/X 갱신**(C).
- `src/execution/managed.py` — JSON load/save → instruments 테이블.
- `scripts/dashboard/app.py` — execution_logs/signals JSON → ledger.db 조회(백테스트 탭은 mlruns 유지).
- `src/execution/orderlog.py` 제거, `.gitignore`에 `data/ledger.db`.

## 미채택·추후 검토

- **감사 필드(G):** `runs.git_commit`·`trigger`(manual/cron). 실주문이 어느 코드로 나갔는지 추적. 저렴하나 이번 범위 밖.
- **백업(J):** `data/ledger.db`는 gitignore + 재생성 불가 → 단일 소실점. run마다 `VACUUM INTO` 타임스탬프 백업 또는 사용자 백업 책임. Phase 0에서 결정.
