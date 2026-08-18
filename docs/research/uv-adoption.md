# 리서치 — uv 전환

- 조사일: 2026-08-19
- 목적: **"이 저장소를 uv 프로젝트로 완전히 옮기려면 정확히 무엇을 어떤 순서로 바꿔야 하는가"**
  에 답한다. uv 일반론이 아니라 **이 저장소의 마이그레이션 계획**이 산출물이다. 판단은 이미
  났고(전환한다), 남은 것은 절차·최종 산출물·되돌리는 법이다.
- 방법: **uv 0.12.5를 스크래치패드에 두고 실제로 돌렸다.** 이 저장소 `pyproject.toml`·
  `requirements.txt`를 스크래치패드로 **복사해** 후보 `[project]` 테이블을 만들고
  `uv lock`·`uv sync`·`uv run`·`uv export`·`uv python pin`을 실행해 출력을 받아 적었다.
  **이 저장소 `.venv`·`pyproject.toml`·`Makefile`·`requirements*.txt`·워크플로는 읽기만 했고
  한 글자도 고치지 않았다.** 문서는 `docs.astral.sh/uv` 해당 페이지를 직접 받아 원문 문장을
  인용했고, CLI 플래그는 **기억이 아니라 `--help` 출력과 실행 결과로** 확인했다. 패키지
  배포 형태는 **PyPI JSON API**로 조회했고, 변경 이력은 **GitHub raw CHANGELOG.md**를 받아
  읽었다. **실행해 본 것과 문서만 읽은 것을 §16에서 가른다.**
- 자매 문서: [`python-comments.md`](python-comments.md) — `[tool.ruff]` 설정의 근거.
  이 문서는 그 블록을 **한 글자도 바꾸지 않고** `pyproject.toml`에 동거시키는 방법을 다룬다.
- 이 문서에 계좌번호·잔액·보유 종목은 없다. 수치는 패키지 해석 결과와 도구 실행 출력뿐이다.

---

## 0. 요약 — 확립된 것 vs 통설

### 0.1 1차 출처·실행으로 확인된 것

1. ★★★ **`uv init`은 이 저장소에서 아예 실행되지 않는다.** `pyproject.toml`이 이미 있으면
   거부한다 — 실행 결과:
   `error: Project is already initialized in ... (`pyproject.toml` file exists)`.
   즉 거의 모든 블로그가 1단계로 적는 `uv init`은 **이 저장소의 마이그레이션 경로가 아니다.**
   `[project]` 테이블은 **손으로 쓴다.** (§2, §12-4)
2. ★★★ **`[project]`를 선언해도 `[build-system]`이 없으면 uv는 이 저장소를 빌드하지도
   설치하지도 않는다.** 스크래치패드에서 `[project]`만 있고 `[build-system]`이 없는
   `pyproject.toml`로 `uv sync`를 돌린 결과, 의존성 5개만 설치되고 프로젝트 자신은
   site-packages에 없었다. 문서 원문도 같다 —
   *"uv uses the presence of a build system to determine if a project contains a package that
   should be installed in the project virtual environment."*
   (빌드 시스템이 있느냐로 프로젝트 자신을 설치할지 판단한다.)
   [projects/config](https://docs.astral.sh/uv/concepts/projects/config/) (§2)
3. ★★★ **핀은 하나도 안 풀린다. 설치 순서도 필요 없다.** `requirements.txt` 전량을
   `[project.dependencies]`로 옮겨 `uv lock`을 돌리니 **244개 패키지가 2.61초에 해석**됐고,
   `uv sync` 후 `numpy·pandas·torch·lightgbm·xgboost·sklearn·qlib·streamlit·yfinance`가
   **전부 정상 import**됐다(macOS arm64, 212개 dist). (§8)
4. ★★★ **`requirements.txt` 헤더의 "설치 순서가 중요" 주석은 폐물이다 — 브리핑의 추측이 맞다.**
   PyPI JSON API 확인: `pyqlib 0.9.7`은 **wheel 18개, sdist 0개**. 게다가 핀 전량
   (`numpy·pandas·torch·lightgbm·xgboost`)이 **macOS arm64와 linux x86_64 양쪽에 cp310 wheel이
   있다.** 소스 빌드가 한 건도 일어나지 않으므로 `numpy<2 → cython<3 → pyqlib` 순서가
   개입할 지점이 없다. **`cython==0.29.37`은 런타임 의존이 아니다** — `pyqlib`의
   `requires_dist`에 cython이 없다. (§8.3)
5. ★★★ **CI용 `requirements-ci.txt`의 "핀을 손으로 맞춘다" 문제는 그룹이 실제로 없앤다.**
   `[project.dependencies]`에만 `numpy==1.26.4`를 두고 `checks` 그룹에는 넣지 않은 채
   `uv sync --only-group checks`를 돌리니 **`numpy==1.26.4`가 들어왔다.** 그룹 설치도
   **같은 하나의 락**에서 나오기 때문이다. 손으로 맞출 대상이 사라진다. (§7.3)
6. ★★★ **그러나 CI에서 맨 `uv run`은 무거운 스택을 통째로 되살린다.** 실측:
   `uv sync --only-group checks`로 21개만 깔린 환경에서 `uv run python -c ...` 한 번에
   **175개가 추가 설치되고 pyqlib이 들어왔다**(21 → 196 dist). `uv run`은 기본이
   "락·환경을 최신으로 맞춘다"이기 때문이다. **CI는 반드시 `uv run --no-sync`** 를 쓴다. (§9.2)
7. ★★★ **pyenv shim과 uv는 실제로 충돌하고, 조용한 발산이 아니라 하드 에러다.**
   `.python-version`이 없는 디렉터리에서 (pyenv global이 3.9.12일 때) uv가
   `~/.pyenv/shims/python3.10`을 조회하자 shim이 exit 127로 죽었고 uv는 그대로 중단했다:
   `error: Failed to inspect Python interpreter from search path at .../shims/python3.10`
   / `pyenv: python3.10: command not found`.
   **반대로 `.python-version`(=3.10.13)이 있는 디렉터리에서는 정확히 pyenv 인터프리터를 쓴다** —
   `Using CPython 3.10.13 interpreter at: /Users/…/.pyenv/versions/3.10.13/bin/python3.10`.
   결론: **이 저장소 루트의 `.python-version`은 uv를 망가뜨리는 게 아니라 uv를 구하고 있다.**
   지우거나 바꾸면 안 된다. (§4)
8. ★★☆ **uv는 기존 `.venv`를 부수지 않고 재사용한다. 다만 락에 없는 패키지는 지운다.**
   pip로 만들고 `six`를 깐 venv에 `uv sync`를 돌린 결과 `pyvenv.cfg`는 그대로였고
   (`home = …/.pyenv/versions/3.10.13/bin`), `+ idna` / **`- six`** 가 찍혔다. 문서 원문 —
   *"`uv sync` performs 'exact' syncing by default, which means it will remove any packages that
   are not present in the lockfile."* (§5)
9. ★★☆ **락파일은 커밋한다. 문서가 직접 그렇게 쓴다** —
   *"This file should be checked into version control, allowing for consistent and reproducible
   installations across machines."*
   그리고 **하나의 락이 양 플랫폼을 다 담는다** —
   *"`uv.lock` is a universal or cross-platform lockfile that captures the packages that would be
   installed across all possible Python markers such as operating system, architecture, and Python
   version."* [projects/layout](https://docs.astral.sh/uv/concepts/projects/layout/) (§6)
10. ★★☆ **`sys.path.insert`는 23개 중 5개만 사라진다.** 나머지 18개는 `src/` 와 무관하다 —
    15개가 `sys.path.insert(0, str(Path(__file__).resolve().parent))`, 즉 **스크립트가 자기
    디렉터리를 넣어 옆 모듈(`_common`)을 import** 하는 관용구다. 패키징으로 안 풀린다.
    `# noqa: E402` 21개 중에서는 **16개가 사라지고 5개가 남는다.** (§3)
11. ★★☆ **CI에서 `actions/setup-python`은 필요 없어진다.** `setup-uv`가 `python-version`
    입력을 받고, 캐시는 **기본이 `auto`** 라 GitHub 호스티드 러너에서 켜진다. 키는
    `cache-dependency-glob` 기본값(`**/uv.lock`·`**/pyproject.toml` 등) 해시다. (§10)
12. ★☆☆ **`uv run`의 재동기화 비용은 실측 ~60ms다.** warm 기준 기본 89ms,
    `--no-sync` 25ms, `--frozen` 26ms. Makefile 도입을 막을 이유가 못 된다. (§9.1)

### 0.2 널리 반복되지만 출처가 없거나 이 저장소에서는 틀린 것

- ❌ **"uv 전환은 `uv init`으로 시작한다."** — 이 저장소에서는 **실행 자체가 거부된다**(0.1-1).
- ❌ **"`[project]`를 넣으면 uv가 저장소를 패키지로 빌드하려 들어서 깨진다."** — 확인 결과
  **`[build-system]`이 없으면 빌드하지 않는다**(0.1-2). `[tool.uv] package = false`는
  안전벨트일 뿐 필수가 아니다. 표준 쪽 근거도 있다 —
  *"Tools should not require the existence of the `[build-system]` table."*
  ([pyproject.toml 명세](https://packaging.python.org/en/latest/specifications/pyproject-toml/))
- ❌ **"uv는 자기 파이썬을 내려받아서 pyenv와 조용히 갈린다."** — 이 저장소에서는 **안 그런다.**
  `.python-version`이 3.10.13을 요구하고 pyenv가 그걸 PATH에 제공하므로 uv는 그걸 쓴다(0.1-7).
  다운로드는 **못 찾았을 때만** 일어난다. 위험은 "조용한 발산"이 아니라 **"pyenv global이
  딴 버전일 때 shim이 127로 죽어서 uv가 멈추는 것"** 이다 — 정반대 실패 모드다.
- ❌ **"`uv run`이 매번 재해석해서 느리다."** — warm 60ms다(0.1-12). 이 저장소의 DAG 레시피는
  SEC 전량 다운로드·340만 행 파싱을 하는데 60ms를 걱정할 자리가 아니다.
- ❌ **"`requirements.txt`를 넣으면 핀이 풀린다."** — `uv add -r requirements.txt` 결과
  `==` 핀이 **문자 그대로** `[project.dependencies]`에 들어갔다(0.1-3, §8.1).
- ⚠️ **"uv는 `uv pip`만 써도 충분하다."** — 부분적으로만 맞다. `uv pip`는 **락파일을 안 쓴다.**
  이 저장소가 원하는 "핀 하나만 고치면 CI와 로컬이 같이 움직인다"는 락에서 오는 성질이라
  `uv pip`로는 안 온다(§1).
- ⚠️ **"`cython` 핀은 qlib 빌드에 필요하다."** — 폐물이다(0.1-4). 다만 **이번 마이그레이션에서
  같이 빼지는 않는다** — 순수 번역 커밋과 의존성 변경 커밋을 섞지 않기 위해서다(§12-12).

---

## 1. 두 인터페이스 — `uv pip` vs 프로젝트

uv에는 두 얼굴이 있다.

| | `uv pip …` | 프로젝트 인터페이스 |
|---|---|---|
| 진입 명령 | `uv pip install -r requirements.txt` | `uv add` / `uv lock` / `uv sync` / `uv run` |
| 요구하는 파일 | 없음 (`requirements.txt`면 족함) | `pyproject.toml` + `[project]` |
| 락파일 | **없음** | `uv.lock` (universal) |
| 여분 패키지 | 안 지움 | `uv sync`가 **지움**(exact) |
| 플랫폼 | 지금 이 머신 | 락 하나가 전 플랫폼 |

`uv pip`는 pip 대체재다. 문서 원문 —
*"uv is designed as a drop-in replacement for common `pip` and `pip-tools` workflows"*
그러나 *"uv is _not_ intended to be an _exact_ clone of `pip`"*
([pip/compatibility](https://docs.astral.sh/uv/pip/compatibility/)).

**이 저장소에는 프로젝트 인터페이스가 맞다.** 이유는 속도가 아니라 세 가지다.

1. **`requirements-ci.txt`의 존재 이유가 락으로 사라진다.** 지금은 두 파일의 핀을 손으로
   맞춰야 하고, 파일 자신이 그렇게 경고하고 있다
   (`⚠️ 핀은 requirements.txt 와 손으로 맞춘다`). 그룹 + 단일 락이면 그 경고문이 필요 없어진다(§7.3).
2. **macOS arm64와 linux x86_64가 한 파일로 묶인다.** `uv pip`에는 그 성질이 없다.
3. **`uv sync`가 exact다.** pip은 "설치돼 있던 것"이 남는다 — 로컬에서만 되는 상태가 쌓인다.

### `uv sync`가 `uv pip install`과 다른 점 (핵심 하나)

> *"`uv sync` performs 'exact' syncing by default, which means it will remove any packages that
> are not present in the lockfile."*
> (기본이 '정확한' 동기화다 — 락파일에 없는 패키지는 **지운다**.)
> — [projects/sync](https://docs.astral.sh/uv/concepts/projects/sync/)

실측으로 확인했다(§5). 이게 장점이자 §12-8의 유일한 파괴적 단계다.

---

## 2. `[project]` 테이블 — 필수인가, 그리고 빌드를 유발하는가

### 2.1 필수다

uv 프로젝트 인터페이스는 `pyproject.toml`로 프로젝트 루트를 찾는다 —
*"Python project metadata is defined in a `pyproject.toml` file. uv requires this file to identify
the root directory of a project."* ([projects/layout](https://docs.astral.sh/uv/concepts/projects/layout/))

PEP 621 쪽 필수 필드는 얇다 —
*"The only keys required to be statically defined are: `name`"*, 그리고
*"The keys which are required but may be specified either statically or listed as dynamic are:
`version`"*. (정적으로 반드시 있어야 하는 건 `name` 하나, `version`은 정적이거나 `dynamic`
목록에 있거나.) — [pyproject.toml 명세](https://packaging.python.org/en/latest/specifications/pyproject-toml/)

즉 **`name`과 `version` 두 줄이면 성립한다.**

### 2.2 그런데 빌드를 유발하는가 — **아니다. 실행해서 확인했다**

이게 브리핑이 "critical"로 표시한 질문이고, 답은 명확한 **아니오**다.

스크래치패드에 `[project]`만 있고 `[build-system]`이 **없는** `pyproject.toml`과
`src/execution/__init__.py`·`src/toss/__init__.py`를 두고 `uv sync`를 돌린 결과:

```
Resolved 6 packages in 5ms
Prepared 5 packages in 157ms
Installed 5 packages in 4ms
 + certifi==2026.7.22
 + charset-normalizer==3.5.1
 + idna==3.19
 + requests==2.34.2
 + urllib3==2.7.0
```

`Building …` 줄이 **없고**, site-packages에 프로젝트 자신이 **없다**. 문서가 말하는 대로다:

> *"uv uses the presence of a build system to determine if a project contains a package that
> should be installed in the project virtual environment."*
> (프로젝트 가상환경에 설치할 패키지가 들어 있는지를, uv는 **빌드 시스템의 존재 여부로** 판단한다.)
> — [projects/config](https://docs.astral.sh/uv/concepts/projects/config/)

대조군도 확인했다. 같은 디렉터리에 `[build-system]`(hatchling)과
`packages = ["src/execution", "src/toss"]`를 넣자 이번엔 **빌드했다**:

```
   Building qlib-research @ file:///…/pkgtest
      Built qlib-research @ file:///…/pkgtest
 + qlib-research==0 (from file:///…/pkgtest)
```

### 2.3 문서화된 탈출구 (그대로 인용)

> *"Setting `tool.uv.package = false` will force a project package **not** to be built and
> installed into the project environment."*
> (`tool.uv.package = false`를 두면 프로젝트 패키지를 빌드·설치하지 **않도록 강제**한다.)
> — [projects/config](https://docs.astral.sh/uv/concepts/projects/config/)

그리고 같은 페이지가 판단 기준을 준다:

> *"You probably **do not** need a package if you are: Writing scripts, Building a simple
> application, Using a flat layout."*

**이 저장소는 스크립트를 쓴다.** 따라서 **`[build-system]`을 넣지 않고, `package = false`를
명시**한다. 앞의 실험대로 `package = false`는 없어도 동작하지만, **의도를 파일에 남기려고**
적는다 — 나중에 누가 `[build-system]`을 무심코 추가해도 이 줄이 막는다.

### 2.4 uv 0.12.0의 변경이 이 판단을 흔들지 않는가

흔들지 않는다. 0.12.0이 `uv init` 기본값을 "빌드 시스템 있음"으로 되돌렸지만 CHANGELOG가
못을 박는다:

> *"**Existing projects are unaffected.** Use `uv init --no-package example` to create the previous
> unpackaged layout without a build system."*
> — [CHANGELOG 0.12.0](https://github.com/astral-sh/uv/blob/main/CHANGELOG.md)

바뀐 건 `uv init`의 기본값뿐이고, 이 저장소는 §2.1대로 **`uv init`을 아예 못 쓴다.**

---

## 3. `sys.path.insert`는 사라지는가 — 정직한 회계

**결론: 부분적으로만. 그리고 이번 마이그레이션의 범위가 아니다.**

### 3.1 기술적으로는 된다 (확인함)

`[build-system]` + hatchling `packages = ["src/execution", "src/toss"]`로 `uv sync` 하면
uv가 **editable로** 설치하고(`_editable_impl_qlib_research.pth`),
`uv run python -c "import execution, toss"`가 **성공한다**. 두 개의 top-level 패키지를
`src/` 아래 두는 배치는 문제없이 동작했다.

### 3.2 그런데 실제로 몇 개가 없어지나 — 세어 봤다

`sys.path.insert` **23개**의 실제 인자를 분류한 결과:

| 대상 | 개수 | 패키징으로 해결? |
|---|---:|---|
| `str(Path(__file__).resolve().parent)` — **자기 디렉터리** | **15** | ❌ |
| `…/"scripts"/"data_pipeline"` (2건) + `_DIR`(1건) | 3 | ❌ |
| `ROOT / "src"` (3건) + `_SRC`(1건) + `parent.parent/"src"`(1건) | **5** | ✅ |
| 합계 | 23 | **5개만** |

**15개가 "스크립트가 자기 디렉터리를 넣어 옆의 `_common`을 import 한다"** 는 관용구다.
`src/`를 패키지로 만드는 것과 **아무 상관이 없다.** 이걸 없애려면 `scripts/data_pipeline/`을
패키지로 승격하거나 pytest rootdir 설정을 손봐야 하는데, **별건 리팩터다.**

### 3.3 `# noqa: E402` 21개는 16개가 없어진다

21개가 6개 파일에 몰려 있다:

| 파일 | noqa 수 | 사유 | 제거 가능? |
|---|---:|---|---|
| `scripts/live/rebalance.py` | 9 | `ROOT/"src"` 삽입 후 import | ✅ |
| `scripts/live/snapshot_holdings.py` | 3 | 〃 | ✅ |
| `scripts/model_backtest/dry_run_rebalance.py` | 3 | 〃 | ✅ |
| `tests/conftest.py` | 1 | 〃 | ✅ |
| `scripts/data_pipeline/fetch_candidate_closes.py` | 3 | **2개는 `warnings.filterwarnings` 뒤**, 1개는 `_common` | ❌ |
| `scripts/data_pipeline/gen_universe_by_mcap.py` | 2 | **1개는 `filterwarnings` 뒤**, 1개는 `_common` | ❌ |

즉 **16개 제거 / 5개 잔존**. 잔존 5개 중 3개는 `sys.path`와 무관하다 —
`warnings.filterwarnings("ignore")`를 `import pandas`보다 먼저 실행해야 해서 생긴 것이고,
`gen_universe_by_mcap.py:29`에는 그 이유가 주석으로 이미 적혀 있다
(`# noqa: E402  (filterwarnings가 import 시점 경고를 먼저 막아야 한다)`). **패키징으로는 절대
안 없어진다.**

### 3.4 판정 — **이번 범위 밖**

과장하지 않겠다. 이걸 하려면:

- `[build-system]` + 빌드 백엔드 선택 → §2의 "빌드 안 함" 판단을 뒤집는다
- `src/execution`·`src/toss` 두 개를 top-level로 배포하는 형태를 확정
- 21곳 중 16곳의 import 재배치 + `RUF100`이 남은 5개를 오탐으로 잡지 않는지 재검
- editable 설치가 `.venv`에 생기므로 §5의 첫 sync 절차가 달라짐

**얻는 것은 noqa 16개, 치르는 것은 §2 판단 번복 + 파일 6개 수정 + 린트 규칙 재검증**이다.
마이그레이션과 같은 커밋에 넣으면 "uv 때문에 깨졌나 리팩터 때문에 깨졌나"를 가를 수 없다.
**uv 전환이 안착한 뒤 별도 브랜치로 다룰 것을 권한다.** uv 전환은 이 결정을 막지 않는다 —
`[build-system]`을 나중에 추가하는 것은 언제든 가능하다.

---

## 4. `.python-version` 충돌 — pyenv와 uv

브리핑이 "가장 유력한 footgun"으로 지목한 항목이다. **실제로 충돌이 있는데, 예상과 방향이 반대다.**

### 4.1 uv도 같은 파일을 읽는다

> *"The `.python-version` file can be used to create a default Python version request. uv searches
> for a `.python-version` file in the working directory and each of its parents."*
> — [python-versions](https://docs.astral.sh/uv/concepts/python-versions/)

실행 로그가 그대로 보여준다:

```
DEBUG Reading Python requests from version file at `…/.python-version`
DEBUG Using Python request `3.10.13` from version file at `.python-version`
```

### 4.2 pyenv 파이썬은 uv에게 "system" 파이썬이다

> *"uv does not distinguish between Python versions installed by the operating system vs those
> installed and managed by other tools. For example, if a Python installation is managed with
> `pyenv`, it would still be considered a _system_ Python version in uv."*
> (pyenv가 관리하는 설치도 uv에게는 **system** 파이썬이다.)

### 4.3 기본값은 확실히 `managed` 우선이고, 다운로드도 켜져 있다

[reference/settings](https://docs.astral.sh/uv/reference/settings/) 확인:

| 설정 | 기본값 | 의미(원문) |
|---|---|---|
| `python-preference` | `"managed"` | *"Prefer managed Python installations over system Python installations"* |
| `python-downloads` | `"automatic"` | *"Automatically download managed Python installations when needed"* |

그리고 **3.10.13은 managed 빌드가 실제로 존재한다** —
`uv python list --all-versions`에 `cpython-3.10.13-macos-aarch64-none <download available>`가 있다.
즉 **"uv가 자기 3.10.13을 받아서 pyenv 3.10.13과 갈릴 수 있다"는 시나리오는 원리적으로 성립한다.**
같은 3.10.13이라도 pyenv 것은 `--enable-shared`·homebrew openssl@3·clang 17로 빌드됐고
(이 머신 `CONFIG_ARGS` 실측), astral 빌드는 다르다.

### 4.4 **그러나 이 저장소에서는 그 일이 안 일어난다 — 돌려서 확인했다**

`.python-version`(=3.10.13)이 있는 디렉터리에서, 다운로드를 막지 않은 상태로:

```
DEBUG Found `cpython-3.10.13-macos-aarch64-none` at `/Users/…/.pyenv/shims/python3.10`
Using CPython 3.10.13 interpreter at: /Users/…/.pyenv/versions/3.10.13/bin/python3.10
Resolved 244 packages
```

`managed` "우선"은 **이미 설치된 managed 설치를 먼저 본다**는 뜻이지 "system을 제쳐두고
내려받는다"가 아니다. 탐색 순서는 ①`UV_PYTHON_INSTALL_DIR`의 managed 설치 → ②PATH의
`python`/`python3`/`python3.x` 이고, ②에서 pyenv가 3.10.13을 내주므로 **다운로드 단계까지
가지 않는다.**

### 4.5 진짜 위험은 정반대다 — pyenv shim이 uv를 **죽인다**

`.python-version`이 **없는** 디렉터리(pyenv global = 3.9.12)에서 uv를 돌리면:

```
DEBUG Skipping bad interpreter at /Users/…/.pyenv/shims/python3.10 …
      failed with exit status exit status: 127
error: Failed to inspect Python interpreter from search path at `/Users/…/.pyenv/shims/python3.10`
  Caused by: … pyenv: python3.10: command not found
    The `python3.10' command exists in these Python versions:
      3.10.13
```

pyenv shim은 "지금 선택된 버전"에 그 실행파일이 없으면 **127로 죽는다.** uv는 그걸
치명적 오류로 보고 중단한다. 조용한 발산이 아니라 **요란한 정지**다 — 다행히도.

**따라서 규칙은 하나다: 저장소 루트의 `.python-version`을 지우지도, 바꾸지도, `uv python pin`으로
건드리지도 말 것.** 그게 지금 uv를 pyenv에 붙들어 매고 있는 유일한 끈이다.

### 4.6 `uv python pin`은 덮어쓴다 (확인함)

```
$ uv python pin 3.11
Updated `.python-version` from `3.10.13` -> `3.11`
```

**말없이 덮어쓴다.** 다만 `[project] requires-python`이 있으면 방어된다 — `requires-python =
"==3.10.*"`를 둔 상태에서 같은 명령은:

```
error: The requested Python version `3.11` is incompatible with the project `requires-python`
value of `==3.10.*`.
```

이고 **파일은 3.10.13 그대로였다.** `requires-python`을 적는 것이 `.python-version`의 방탄복이 된다.

### 4.7 이 저장소가 취할 설정

`[tool.uv] python-preference = "only-system"`을 **넣지 않는다.** 이유:

- §4.4대로 현재 동작이 이미 pyenv를 쓴다 — 안 고장난 걸 고치지 않는다
- `only-system`은 CI에서 역효과다. GitHub Actions에는 pyenv가 없고 `setup-uv`가 managed
  파이썬을 쓰는 편이 자연스럽다. 로컬 전용 설정을 추적 파일에 박으면 CI가 갈린다
- 정말로 다운로드를 막고 싶으면 `UV_PYTHON_DOWNLOADS=never`를 **셸에서** 주는 편이 낫다

대신 **`requires-python = "==3.10.*"` 을 적어 `uv python pin` 사고를 막는다**(§4.6).

---

## 5. 기존 `.venv` — 재사용하는가

**재사용한다. 다만 락에 없는 것은 지운다.** 스크래치패드 실험:

```
# pyenv 3.10.13 + python -m venv + pip install six==1.16.0 로 만든 .venv 에
$ uv sync
Resolved 2 packages in 4ms
Uninstalled 1 package in 1ms
Installed 1 package in 1ms
 + idna==3.19
 - six==1.16.0
```

- `pyvenv.cfg`는 **변경 없음** (`home = …/.pyenv/versions/3.10.13/bin` 유지) → **venv를 다시 만들지 않았다**
- `pip` 자신은 **남았다** (seed 패키지는 건드리지 않음)
- `six`는 **삭제됐다** — 락에 없으므로. 이게 exact sync다(§1)

### 이 저장소에서 이게 뜻하는 것

`.venv`에 지금 pip으로 깔려 있는 것 중 **`requirements.txt`에 없는 것은 첫 `uv sync`에서
전부 사라진다.** 임시로 깔아 둔 디버깅 도구, 손으로 넣은 패키지가 있다면 그렇다.

**안전한 순서** (§12-8이 이걸 그대로 쓴다):

1. 지우기 전에 현재 상태를 **찍어 둔다**: `.venv/bin/python -m pip freeze > /tmp/venv-before.txt`
2. `.venv`를 **옮긴다**(지우지 말고): `mv .venv .venv.bak`
3. `uv sync` — 새로 만들게 한다
4. 검증 후 `.venv.bak` 삭제. 문제 생기면 `rm -rf .venv && mv .venv.bak .venv`로 즉시 복귀

기존 `.venv`에 바로 `uv sync`를 때리는 것보다 이쪽이 낫다. 되돌리는 데 1초면 되고,
`⚠️ 다른 세션이 같은 워킹트리에서 작업 중`이라는 전제(브리핑) 아래에서는 **파괴적 연산을
되돌릴 수 있게 두는 것**이 특히 중요하다.

---

## 6. 락파일

### 6.1 커밋한다 — 문서가 그렇게 쓴다

> *"This file should be checked into version control, allowing for consistent and reproducible
> installations across machines."*
> — [projects/layout](https://docs.astral.sh/uv/concepts/projects/layout/)

uv 문서는 라이브러리/애플리케이션을 갈라서 다른 지침을 주지 **않는다**. "애플리케이션은
커밋하고 라이브러리는 안 한다"는 pip-tools 시절 관행이며, **uv 문서에는 그런 문장이 없다.**
(이 저장소는 어차피 애플리케이션이라 논쟁 자체가 무의미하다.)

### 6.2 macOS arm64 + linux x86_64를 한 파일로 — 확인함

> *"`uv.lock` is a universal or cross-platform lockfile that captures the packages that would be
> installed across all possible Python markers such as operating system, architecture, and Python
> version."*

실제 락파일(244 패키지, 3461줄)을 열어 보면 한 패키지 아래에 플랫폼별 wheel이 나열돼 있다:

```
name = "pyqlib"  version = "0.9.7"
  pyqlib-0.9.7-cp310-cp310-macosx_10_9_universal2.whl
  pyqlib-0.9.7-cp310-cp310-macosx_13_0_x86_64.whl
  pyqlib-0.9.7-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
  pyqlib-0.9.7-cp310-cp310-win_amd64.whl
```

**torch는 의존성 자체가 플랫폼별로 갈린다** — 락에 그게 마커로 박힌다:

```
name = "torch"  version = "2.13.0"
dependencies = [
    { name = "cuda-bindings",       marker = "sys_platform == 'linux'" },
    { name = "cuda-toolkit", extra = [...], marker = "sys_platform == 'linux'" },
    { name = "nvidia-cudnn-cu13",   marker = "sys_platform == 'linux'" },
    { name = "nvidia-nccl-cu13",    marker = "sys_platform == 'linux'" },
    { name = "triton",              marker = "sys_platform == 'linux'" },
    { name = "filelock" }, { name = "sympy" }, …
]
```

락 안에 **`nvidia-*` 패키지가 16개 + `triton`** 이 들어 있다. macOS에서는 마커가 거짓이라
설치되지 않고, **linux에서 기본 그룹을 sync 하면 CUDA 스택이 통째로 깔린다.** §11의 위험
항목이고, CI가 `--only-group checks`를 쓰는 이유이기도 하다.

### 6.3 `--locked` vs `--frozen` — 실측한 차이

| 플래그 | 원문 정의 | 락이 낡았을 때 | CI에 적합? |
|---|---|---|---|
| `--locked` | *"Assert that the `uv.lock` will remain unchanged"* | **에러로 멈춤** | ✅ |
| `--frozen` | *"Sync without updating the `uv.lock` file"* | **조용히 낡은 락으로 설치** | ❌ |

`pyproject.toml`에 `six`를 추가한 뒤 실행한 결과:

```
$ uv sync --locked
error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.
hint: To update the lockfile, run `uv lock`.

$ uv lock --check
error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.

$ uv sync --frozen
 + xgboost==3.2.0   … (변경을 무시하고 옛 락 그대로 설치)
```

**CI에는 `--locked`.** "누가 `pyproject.toml`만 고치고 `uv lock`을 안 돌린 채 PR을 올렸다"를
CI가 잡아 준다 — 지금 `requirements-ci.txt`를 손으로 맞추다 놓치는 사고와 같은 종류를 막는다.

`--frozen`은 **락을 신뢰하고 속도만 원할 때**(로컬 Makefile 등) 쓸 수는 있으나, 이 계획에서는
쓰지 않는다. 대신 CI 두 번째 단계는 `--no-sync`를 쓴다(§9.2).

---

## 7. 의존성 그룹(PEP 735) vs extras

### 7.1 PEP 735 원문

> *"This PEP defines a new section (table) in `pyproject.toml` files named `dependency-groups`.
> The `dependency-groups` table contains an arbitrary number of user-defined keys, each of which
> has, as its value, a list of requirements."*

그리고 결정적인 두 문장:

> *"Build backends MUST NOT include Dependency Group data in built distributions as package metadata."*
> (빌드 백엔드는 의존성 그룹을 배포물 메타데이터에 **넣어서는 안 된다**.)
> *"Installation of a dependency group does not imply installation of a package's dependencies or
> the package itself."*
> (그룹 설치가 패키지 자신이나 그 의존성의 설치를 **함의하지 않는다**.)
> — [PEP 735](https://peps.python.org/pep-0735/)

두 번째 문장이 이 저장소에 정확히 맞는다. **extras(`[project.optional-dependencies]`)는
패키지를 전제한다** — `pip install mypkg[ci]`는 `mypkg`를 깐다. 이 저장소는 §2대로 패키지가
아니므로 **extras는 애초에 쓸 수 없고, 그룹이 유일한 선택지다.** PEP 735가 그걸 명시적 동기로
든다 — 그룹은 *"support non-package projects"*.

### 7.2 `dev`는 특별 취급된다

> *"The `dev` group is special-cased; there are `--dev`, `--only-dev`, and `--no-dev` flags to
> toggle inclusion or exclusion of its dependencies."* 그리고 *"the `dev` group is synced by default."*
> — [projects/dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)

`[tool.uv] default-groups`의 기본값은 `["dev"]`다([reference/settings](https://docs.astral.sh/uv/reference/settings/)).

**이 저장소는 그룹 이름을 `checks`로 한다.** `dev`가 아니라 `checks`인 이유: Makefile 타깃
(`lint`/`test`/`check-docrefs`)과 워크플로 이름(`checks`)이 이미 그 어휘를 쓴다. 대신
`dev`의 자동 동기화 편의는 잃으므로 **`default-groups = ["checks"]`를 명시**해 되찾는다.
그러면 로컬에서 맨 `uv sync`가 무거운 스택 + pytest·ruff를 다 깔고, CI만 `--only-group checks`를 쓴다.

### 7.3 ★ 그룹이 `requirements-ci.txt`의 병을 실제로 고친다 — 확인함

`requirements-ci.txt`의 자기 경고는 이렇다:
`⚠️ 핀은 requirements.txt 와 손으로 맞춘다. 그쪽을 올리면 여기도 올릴 것.`

그룹은 이걸 **구조적으로** 없앤다. 확인 실험 — `numpy==1.26.4`를 `[project.dependencies]`에만
두고 `checks` 그룹에는 **넣지 않은 채**:

```
$ uv sync --only-group checks
 + numpy==1.26.4      ←  그룹에 없는데 들어왔다
 + pandas==2.1.4
 + pytest==9.1.1
 + ruff==0.16.3
 …  (총 20개)
```

`checks` 그룹은 `pandas`만 요구했지만, **락이 하나이므로** pandas가 끌어온 numpy도 프로젝트
의존성의 `numpy==1.26.4` 해석 결과를 그대로 받는다. **두 파일의 핀을 맞출 일이 사라진다.**

### 7.4 정확한 형태와 호출

`pyproject.toml`:

```toml
[dependency-groups]
checks = [
  "pandas==2.1.4",
  "requests>=2.31,<3",
  "python-dotenv>=1.0,<2",
  "pytest==9.1.1",
  "ruff==0.16.3",
]

[tool.uv]
default-groups = ["checks"]
```

| 상황 | 명령 |
|---|---|
| 로컬 전체(무거운 스택 + 검사 도구) | `uv sync` |
| CI — 검사 도구만 | `uv sync --locked --only-group checks` |
| 무거운 스택만, 검사 도구 빼고 | `uv sync --no-default-groups` |

`numpy`는 그룹에 **안 적는다**(§7.3에서 락이 보증). `requirements-ci.txt`가 numpy를 적었던
것은 락이 없어서였다.

**왜 `pandas`·`requests`·`python-dotenv`가 `checks`에 필요한가** — 실측: `tests/`의 최상위
import는 `pandas`·`pytest` + 로컬 패키지(`execution`·`toss`·`_common`)뿐이고,
`src/`의 서드파티 import는 `requests`·`dotenv` 둘뿐이다. `scripts/data_pipeline/verify.py`는
`qlib`을 쓰지만 **함수 안에서 늦게 import** 한다(`def lag_by_symbol(): … import qlib`) —
그래서 CI에 pyqlib이 없어도 수집이 깨지지 않는다. 지금 `requirements-ci.txt`가 성립하는
이유와 정확히 같고, 그룹은 그 목록을 그대로 옮긴 것이다.

---

## 8. 기존 핀을 옮기기

### 8.1 `uv add -r requirements.txt`는 실재한다 — 그리고 핀을 안 푼다

플래그 확인(`uv add --help`):

```
  -r, --requirements <REQUIREMENTS>   Add the packages listed in the given files
  -c, --constraints <CONSTRAINTS>     Constrain versions using the given requirements files
```

공식 마이그레이션 가이드도 이 경로를 쓴다 —
*"`uv add -r requirements.in -c requirements.txt`"* … *"Your existing versions will be retained
when producing a `uv.lock` file"*
([guides/migration/pip-to-project](https://docs.astral.sh/uv/guides/migration/pip-to-project/)).

실행 결과 — 이 저장소 `requirements.txt`를 그대로 먹였더니:

```toml
dependencies = [
    "altair==6.2.2",
    "bidask==2.1.0",
    "cython==0.29.37",
    "fire==0.7.1",
    "lightgbm==4.6.0",
    …
    "torch==2.13.0",
    "xgboost==3.2.0",
    "yfinance==1.5.1",
]
```

**`==` 핀이 문자 그대로 보존되고**, 알파벳순으로 정렬되며, `>=2.31,<3` 같은 범위도 그대로다.

### 8.2 ★ `[tool.ruff]`의 한글 주석은 살아남는다 — 확인함

이게 이 저장소에서 제일 걱정될 만한 지점이다. `uv add`는 `pyproject.toml`을 **다시 쓴다.**
`[tool.ruff]` 블록에는 규칙마다 왜 껐는지가 한글로 붙어 있고, 그 근거는
[`python-comments.md`](python-comments.md) §5.5다. 날아가면 큰 손실이다.

실제 파일을 복사해 `[project]`를 앞에 붙이고 `uv add -r requirements.txt --no-sync`를 돌린 뒤
`[tool.ruff]` 이후를 diff 한 결과: **완전 동일.** uv는 TOML을 보존적으로 편집한다.

그래도 **§12-4는 `uv add`를 쓰지 않고 손으로 쓰는 쪽을 택한다.** 이유는 두 가지다 —
①`uv add`는 `pytest`·`ruff`까지 `[project.dependencies]`에 넣어 버려서 어차피 손으로
`checks` 그룹으로 옮겨야 하고, ②주석(`# --- Qlib 스택 ---`, torch OpenMP 경고 등)은
`requirements.txt`에만 있고 `uv add`가 옮겨 주지 않는다. **그 주석들이야말로 옮길 가치가 있다.**

### 8.3 ★ `numpy<2` 는 어디에 적나 — 그리고 애초에 순서 이야기가 맞나

**먼저 순서 주석부터 반박한다.** `requirements.txt` 헤더는 이렇게 말한다:

```
# 설치 순서가 중요: 선행 핀 → pyqlib → xgboost
# --- 선행 핀 (Qlib 호환: numpy<2, pandas<2.2, cython<3) ---
```

PyPI JSON API로 확인한 사실:

| 패키지 | 배포 형태 | mac arm64 cp310 | linux x86_64 cp310 |
|---|---|---|---|
| `pyqlib 0.9.7` | **wheel 18, sdist 0** | `macosx_10_9_universal2` ✅ | `manylinux_2_17_x86_64` ✅ |
| `numpy 1.26.4` | wheel 35 + sdist | ✅ | ✅ |
| `pandas 2.1.4` | wheel 24 + sdist | ✅ | ✅ |
| `torch 2.13.0` | wheel 24 | ✅ | ✅ |
| `lightgbm 4.6.0` | wheel 5 + sdist | ✅ | ✅ |
| `xgboost 3.2.0` | wheel 5 + sdist | ✅ | ✅ |

**두 대상 플랫폼 모두 소스 빌드가 한 건도 필요 없다.** 순서가 중요했던 이유는
"pyqlib을 sdist에서 빌드할 때 그 시점의 numpy/cython ABI에 맞춰진다"였는데, **빌드가 없으면
그 인과가 없다.** 그리고 `pyqlib 0.9.7`의 `requires_dist`에는 **cython이 아예 없다**
(런타임 의존이 아니다).

실행이 이를 확정한다 — 순서 지시 없이 한 번에 `uv sync` 한 뒤:

```
  OK  numpy        1.26.4      OK  torch        2.13.0      OK  qlib         0.9.7
  OK  pandas       2.1.4       OK  lightgbm     4.6.0       OK  streamlit    1.59.2
  OK  sklearn      1.7.2       OK  xgboost      3.2.0       OK  yfinance     1.5.1
```

**→ 브리핑의 추측이 맞다. 순서 주석은 폐물이다.** 이전할 때 그 문장을 그대로 옮기지 말 것.

**그럼 `numpy<2`는 어디에?** — **`[project.dependencies]`에 `numpy==1.26.4`로.**
`[tool.uv] constraint-dependencies`가 **아니다.** 차이는 이렇다:

| | `[project.dependencies]` | `[tool.uv] constraint-dependencies` |
|---|---|---|
| 정의(원문) | 프로젝트가 **요구하는** 것 | *"Constraints to apply when resolving the project's dependencies."* |
| 설치 유발 | 한다 | **안 한다** — 버전을 좁히기만 함 |
| 표준 | PEP 621 | uv 전용 |

`numpy`는 이 저장소가 **직접 import 하는** 패키지다(`_common.py` 경유로 tests까지). 그러니
"제3자가 끌어올 때만 좁힌다"는 constraint가 아니라 **진짜 의존성**이다. 게다가 §7.3에서
확인했듯 `[project.dependencies]`에 두면 그룹 설치에도 그 핀이 전파된다 — constraint로는
안 오는 성질이다.

`constraint-dependencies`가 맞는 경우는 **"내가 안 쓰는데 남이 끌어오는 걸 좁혀야 할 때"** 다.
지금 그런 항목은 없다. **넣지 않는다.**

---

## 9. Makefile 통합

### 9.1 `uv run`의 비용 — 실측 (warm)

| 호출 | 시간 |
|---|---|
| `uv run python -c "print('ok')"` (기본: 락 검사 + 환경 동기화) | **89 ms** |
| `uv run --frozen …` | 26 ms |
| `uv run --no-sync …` | 25 ms |

문서가 기본 동작을 설명한다 —
*"Prior to every `uv run` invocation, uv will verify that the lockfile is up-to-date with the
`pyproject.toml`, and that the environment is up-to-date with the lockfile, keeping your project
in-sync without the need for manual intervention."*
([guides/projects](https://docs.astral.sh/uv/guides/projects/))

**60ms의 추가 비용으로 "환경이 낡았다"는 사고 유형이 통째로 사라진다.** 이 저장소의 DAG
레시피는 SEC DERA 전량 다운로드와 340만 행 파싱을 하고, `make test`는 pytest 기동이 그보다
훨씬 비싸다. **기본 `uv run`을 쓴다.**

### 9.2 ★ 그런데 CI에서는 기본 `uv run`이 재앙이다 — 확인함

`uv sync --only-group checks`로 21개만 깔린 환경에서 **맨 `uv run`을 한 번** 부르면:

```
$ uv run python -c "print('ran')"
Downloading pyarrow (34.3MiB)
Downloading lightgbm (1.4MiB)
Installed 175 packages in 1.17s
ran
```

**21개 → 196개, pyqlib 포함.** `uv run`이 "환경을 락의 기본 그룹에 맞춘다"를 성실히 수행한
결과다. `requirements-ci.txt`를 만든 목적이 통째로 무효가 된다 — 게다가 linux에서는 여기에
CUDA 스택 16개가 얹힌다(§6.2).

**→ CI는 `uv run --no-sync`.** 환경은 앞 단계의 `uv sync --locked --only-group checks`가
이미 정확히 만들어 놨으므로 재동기화는 필요 없을 뿐 아니라 **해로운** 것이다.

### 9.3 Make 3.81에서 되는 형태 — 확인함

기존 Makefile의 설계 의도(주석에 적혀 있다)는 "**CI가 명령줄 대입으로 경로만 바꿔 낀다**"이다.
그 구조를 그대로 유지하되 교체 지점을 **하나**로 줄인다:

```make
UV   := uv run
PY   := $(UV) python
RUFF := $(UV) ruff
```

GNU Make 3.81에서 실제로 확인:

```
$ make show
PY=[uv run python]
RUFF=[uv run ruff]

$ make show UV="uv run --no-sync"
PY=[uv run --no-sync python]
RUFF=[uv run --no-sync ruff]
```

`:=`(즉시 확장)인데도 명령줄 대입이 먹는다 — 명령줄 변수는 makefile 파싱 **전에** 설정되기
때문이다. **CI는 `make lint UV="uv run --no-sync"` 하나로 두 변수를 다 덮는다.**

### 9.4 Make 3.81에서 깨지는 것 — 없다

`uv run`은 레시피 줄의 명령 접두사일 뿐이라 Make 버전과 무관하다. 브리핑이 짚은
grouped target(`&:`) 부재는 이미 stamp 파일로 우회돼 있고(`.make/candidates.stamp`),
**uv 도입이 그 설계를 건드리지 않는다.** `check-dag`가 `$(MAKE) -p`로 규칙 DB를 조회하는
방식도 그대로 동작한다 — 변수 이름만 바뀌지 규칙 구조는 불변이다.

한 가지만 주의: `.venv/bin/python`을 **문자열로 박아 둔 곳**이 Makefile 밖에도 있다.
docstring의 실행 예시(`실행:  .venv/bin/python scripts/…`)가 그렇다. 동작에는 영향이 없지만
낡은 안내가 되므로 §12-11에서 함께 훑는다.

---

## 10. CI — `astral-sh/setup-uv`

### 10.1 캐시는 기본으로 켜진다

`setup-uv` README의 입력 기본값 확인:

| 입력 | 기본값 |
|---|---|
| `enable-cache` | `"auto"` |
| `cache-dependency-glob` | `**/*requirements*.txt`, `**/*requirements*.in`, `**/*constraints*.txt`, `**/*constraints*.in`, `**/pyproject.toml`, `**/uv.lock`, `**/*.py.lock` |
| `python-version` | `""` |
| `prune-cache` | `"false"` |

`"auto"`의 의미(README 원문):
*"enabled on GitHub-hosted runners except for release, tag push, pull_request_target, and
workflow_run events; disabled on self-hosted runners"*

이 저장소 워크플로는 `push: [main]` + `pull_request`이므로 **둘 다 캐시가 켜진다.**
`enable-cache: true`를 명시할 필요조차 없지만, **의도를 남기려고 적는다.**

캐시 키는 `cache-dependency-glob` 매치 파일들의 해시에서 나온다. 기본 glob이 이미
`**/uv.lock`과 `**/pyproject.toml`을 포함하므로 **따로 설정할 것이 없다.**

### 10.2 `setup-python`은 필요 없다

`setup-uv`가 `python-version` 입력을 받고, uv 자신이 파이썬을 조달한다. 공식 가이드가
두 경로를 다 보여주지만([guides/integration/github](https://docs.astral.sh/uv/guides/integration/github/)),
**러너에 pyenv가 없으므로 §4.5의 shim 함정도 없고, uv managed 파이썬이 가장 단순하다.**

`python-version: "3.10"`을 준다. 지금 워크플로 주석의 근거("패치까지 고정하면 그 패치가
내려갈 때 검사와 무관하게 깨진다")는 uv에서도 그대로 유효하다. 로컬은
`.python-version`(3.10.13)으로 pyenv를 쓰고, CI는 마이너만 맞춘다 — `requires-python =
"==3.10.*"`가 양쪽을 다 받는다.

> ⚠️ `setup-uv`에 `python-version`을 주면 그 값이 `.python-version` 파일보다 우선하도록
> `UV_PYTHON`을 설정한다. 로컬의 3.10.13과 CI의 3.10.x가 갈릴 수 있는 유일한 지점인데,
> **락은 `requires-python = "==3.10.*"` 하나로 해석돼 있어 패치 차이는 해석에 영향이 없다**
> (universal 해석은 마커 단위이고 패치는 마커가 아니다).

### 10.3 CI가 무거운 스택을 안 깔게 하는 두 겹의 방어

1. `uv sync --locked --only-group checks` — 기본 그룹을 제외하고 `checks`만
2. `make … UV="uv run --no-sync"` — §9.2의 되살아남을 차단

**둘 다 있어야 한다.** 1번만 하면 2번이 무너뜨린다(실측). 검증 방법은 §12-10에 적었다.

---

## 11. 최종 산출물 — 복붙 가능한 형태

### 11.1 `pyproject.toml` (전문)

기존 `[tool.ruff]` 블록은 **현재 파일에서 그대로 가져온 것이며 한 글자도 바꾸지 않았다.**
새로 추가되는 것은 파일 맨 앞의 `[project]`·`[dependency-groups]`·`[tool.uv]` 뿐이다.

```toml
# 이 저장소는 배포되는 패키지가 아니다 — 스크립트와 테스트를 돌리기 위한 환경 선언이다.
# 따라서 [build-system]을 두지 않는다. uv는 빌드 시스템의 존재로 "이 프로젝트 자신을
# 설치할지"를 판단하므로, 없으면 의존성만 깔고 저장소를 빌드하지 않는다.
# 근거·실측은 docs/research/uv-adoption.md §2.
[project]
name = "auto-stock-trader"
version = "0.0.0"
# pyenv 3.10.13 과 CI 의 3.10.x 를 함께 받는다. 이 줄이 `uv python pin` 오조작으로부터
# .python-version 을 지키는 방탄복이기도 하다 (§4.6).
requires-python = "==3.10.*"
dependencies = [
  # 선행 핀이 아니라 그냥 의존성이다 — pyqlib 0.9.7 은 wheel 만 배포하므로 설치 순서가
  # 개입할 지점이 없다. 옛 requirements.txt 의 "설치 순서가 중요" 주석은 폐물이다 (§8.3).
  # numpy 상한은 여전히 필요하다: pyqlib 메타데이터에는 numpy 상한이 없어서
  # 풀어 두면 해석기가 numpy 2.x 를 고른다.
  "numpy==1.26.4",
  "pandas==2.1.4",
  # cython 은 런타임 의존이 아니다(pyqlib requires_dist 에 없음). 순수 이전을 위해
  # 일단 그대로 두고, 별건 커밋에서 제거한다 (§12-12).
  "cython==0.29.37",

  # --- Qlib 스택 ---
  "pyqlib==0.9.7",
  "lightgbm==4.6.0",
  "xgboost==3.2.0",
  "scikit-learn==1.7.2",

  # --- DL 실험 ---
  # macOS 는 torch↔lightgbm OpenMP 충돌로 무음 크래시 → 실행 시 OMP_NUM_THREADS=1 필수
  # (run_experiment.py 참고). linux 에서는 이 핀이 CUDA 스택 16개를 함께 끌어온다 —
  # 그래서 CI 는 이 그룹을 설치하지 않는다 (§6.2·§10.3).
  "torch==2.13.0",

  # --- 토스 어댑터 ---
  "requests>=2.31,<3",
  "python-dotenv>=1.0,<2",

  # --- 데이터 파이프라인 ---
  # yfinance: S&P500 일봉 수집 (비공식 스크래퍼 — 재시도·폴백 필요)
  "yfinance==1.5.1",
  # vendor/dump_bin.py 직접 의존 (pyqlib 딸림이지만 명시 핀)
  "fire==0.7.1",
  "loguru==0.7.3",
  "tqdm==4.68.4",

  # --- 대시보드 ---
  # mlruns pkl·execution_logs 를 읽어 Streamlit 화면 렌더. altair 는 차트에 직접 import.
  "streamlit==1.59.2",
  "altair==6.2.2",

  # --- 추정량 ---
  "bidask==2.1.0",              # EDGE 스프레드 추정량
]

# 옛 requirements-ci.txt 를 대체한다. 그 파일의 "⚠️ 핀은 손으로 맞춘다" 경고는 여기서
# 사라진다 — 그룹도 [project.dependencies] 와 같은 하나의 uv.lock 에서 설치되므로
# numpy 를 안 적어도 1.26.4 가 온다 (실측: §7.3).
#
# 들어갈 것의 기준은 "tests/ 가 실제로 import 하는 것"이다. 실측 결과 tests 의 최상위
# import 는 pandas·pytest + 로컬 패키지뿐이고, src/ 의 서드파티는 requests·dotenv 둘뿐이다.
# verify.py 는 qlib 을 쓰지만 함수 안에서 늦게 import 하므로 수집이 깨지지 않는다.
[dependency-groups]
checks = [
  "pandas==2.1.4",
  "requests>=2.31,<3",
  "python-dotenv>=1.0,<2",
  "pytest==9.1.1",
  "ruff==0.16.3",
]

[tool.uv]
# 이 저장소를 패키지로 빌드·설치하지 않는다. [build-system] 부재만으로도 같은 결과지만
# 의도를 파일에 남긴다 — 나중에 누가 [build-system] 을 넣어도 이 줄이 막는다 (§2.3).
package = false
# uv 기본값은 ["dev"] 인데 이 저장소의 그룹 이름은 checks 다. 명시하지 않으면 로컬에서
# 맨 `uv sync` 가 pytest·ruff 를 빼고 깐다 (§7.2).
default-groups = ["checks"]

# 주석·docstring 린트 설정. 근거·검출 실측은 docs/research/python-comments.md §5.5.
#
# ignore 목록이 이 설정의 핵심이다. 한글 docstring은 영어 문장 규칙을 전제한 규칙들을
# 조용히 통과한다 — 켜 두면 "검사됐다"와 "검사되지 않았다"가 같은 0으로 보인다.
# 그래서 발화하지 않는 것으로 실측된 규칙은 끄고, 왜 껐는지를 각 줄에 남긴다.

[tool.ruff]
line-length = 100
target-version = "py310"   # requirements.txt 기준 pyenv 3.10.13. 올릴 때 함께 고칠 것
extend-exclude = ["vendor", ".venv"]

[tool.ruff.lint]
select = [
  "ERA001",   # 주석 처리된 코드. 현재 0건 — 예방용이며 한글 서술에 오탐이 안 났다
  "D",        # docstring. convention=google 이 방언 관련 12개를 알아서 끈다
  "W505",     # 주석·docstring 줄 길이. max-doc-length 를 줘야 발화한다
  "TD",       # TODO 형식. 현재 0건 — 첫 TODO 가 들어오는 순간부터 형식을 강제한다
  "FIX",      # TODO/FIXME/XXX/HACK 존재 자체를 보고. TD 와 목적이 다르다
  # 아래 넷은 한 묶음이다. RUF100(불필요한 noqa)은 억제 대상 규칙이 켜져 있어야만
  # 판정할 수 있어서, 이 저장소가 쓰는 세 규칙을 함께 켠다. 켜지 않고 RUF100만 켜면
  # "억제할 규칙이 없다"는 이유로 정당한 지시까지 오탐이 된다.
  "F401",     # 쓰이지 않는 import
  "E402",     # 최상단 아닌 import. ruff는 sys.path 조작은 면제하고 그 밖의 호출만 잡는다
  "BLE001",   # except Exception. 이 저장소는 네트워크·스크래퍼 경계에서만 허용한다
  "RUF100",   # 아무것도 억제하지 않는 noqa. 검증되지 않은 지시가 21건 있었다
]
ignore = [
  "D100",     # module docstring 누락 — 현재 0건이라 강제 불필요. 스크립트에 노이즈만 준다
  "D104",     # package docstring 누락 — 같은 이유
  "D203",     # class docstring 앞 빈 줄. D211 과 상호배타라 하나는 꺼야 한다
  "D213",     # multi-line 요약을 둘째 줄에. D212(첫 줄)와 상호배타
  "D400",     # 첫 줄 마침표. 한글 서술문에 마침표를 강제할 근거가 없다(PEP 8은 영어 규칙)
  "D415",     # 같은 것의 google 판(., ?, ! 중 하나)
  "D401",     # 명령형. 한글에서 273건 중 2건만 발화 = 검사되지 않는다. google 이 이미 끈다
  "D403",     # 첫 단어 대문자화. 11건 전부 오탐이고 자동수정이 식별자 case 를 바꾼다
  "D205",     # 요약 뒤 빈 줄. 한 줄 요약 + 본문 이어쓰기가 이 저장소 문체다
  "TD002",    # TODO 작성자. 1인 저장소에서 git blame 이 더 정확하다
  "TD003",    # TODO 이슈 링크. 이슈 트래커가 없다
]

[tool.ruff.lint.pycodestyle]
max-doc-length = 100                    # PEP 8의 72는 한글에 이식 불가. 현 문체의 자연 상한이 100
ignore-overlong-task-comments = true    # 긴 TODO 를 길이 규칙으로 두 번 때리지 않는다

[tool.ruff.lint.pydocstyle]
convention = "google"                   # Args:/Returns:/Raises: 를 이미 쓰고 있다

[tool.ruff.lint.per-file-ignores]
"tests/**"   = ["D1"]                            # 테스트 이름이 명세다. pydantic·polars 선례
"scripts/**" = ["D103", "D102", "D101", "D107"]  # 엔트리포인트 스크립트. 공개 API 가 아니다
```

> **이 블록은 그대로 실행해 검증했다.** 위 TOML을 파일로 떼어 내
> (`[tool.ruff]` 이후가 현재 `pyproject.toml`과 **byte 단위로 동일**함을 diff로 확인)
> `.python-version`만 옆에 두고 돌린 결과:
> `uv lock` → `Resolved 244 packages`, `uv lock --check` → exit 0,
> `uv sync --locked --only-group checks` → **21개 설치, pyqlib·torch·nvidia-* 0개,
> 그리고 `numpy==1.26.4` 포함**(§7.3의 성질이 최종 산출물에서도 성립).
> ruff도 이 파일에서 설정을 읽어 정상 발화했다(F401 검출 확인).

### 11.2 `.github/workflows/checks.yml` (전문 교체)

```yaml
# lint·test·문서참조 세 검사. Makefile 타깃을 그대로 부른다 — 로컬과 CI가 갈리면
# "내 머신에서는 통과한다"가 시작된다.
#
# UV 를 명령줄에서 덮는다. Makefile 은 `uv run` 을 기본값으로 두는데, CI 에서 그대로
# 두면 재앙이다 — `uv run` 은 매번 "환경을 락의 기본 그룹에 맞추는" 동작이라
# --only-group checks 로 21개만 깔아 둔 환경에 pyqlib·torch 를 포함한 175개를 되살린다
# (실측: docs/research/uv-adoption.md §9.2). --no-sync 가 그걸 막는다.
name: checks

on:
  push:
    branches: [main]
  pull_request:

# 같은 브랜치에 새 푸시가 오면 진행 중인 실행을 버린다. 검사가 3분 안쪽이라
# 큐를 쌓을 이유가 없다.
concurrency:
  group: checks-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # setup-python 은 필요 없다 — uv 가 파이썬을 조달한다.
      # 로컬은 .python-version(pyenv 3.10.13), CI 는 마이너까지만. 패치를 고정하면
      # 그 패치가 내려갈 때 검사와 무관하게 깨진다. requires-python="==3.10.*" 가 양쪽을
      # 다 받고, 락은 마커 단위라 패치 차이가 해석에 영향을 주지 않는다.
      #
      # enable-cache 기본값은 "auto" 이고 GitHub 호스티드 러너의 push·pull_request 에서는
      # 이미 켜진다. 의도를 남기려고 명시한다. 캐시 키는 cache-dependency-glob 기본값
      # (**/uv.lock · **/pyproject.toml 포함) 해시라 따로 줄 것이 없다.
      - uses: astral-sh/setup-uv@v9
        with:
          version: "0.12.5"
          python-version: "3.10"
          enable-cache: true

      # --locked: 누가 pyproject.toml 만 고치고 uv lock 을 안 돌렸으면 여기서 멈춘다.
      # --only-group checks: 무거운 스택(pyqlib·torch)을 빼고 검사 도구만. linux 에서
      #   기본 그룹을 깔면 torch 가 CUDA 스택 16개를 함께 끌어온다.
      - name: 의존성 설치
        run: uv sync --locked --only-group checks

      - name: 주석·docstring 린트
        run: make lint UV="uv run --no-sync"

      - name: 테스트
        run: make test UV="uv run --no-sync"

      # 린터가 잡지 못하는 유일한 자동화 가능 항목. 주석 속 파일명은 산문이라
      # 문서를 개명해도 따라오지 않는다 — 실제로 5곳이 끊긴 채 커밋돼 있었다.
      - name: 문서 참조 해소
        run: make check-docrefs
```

바뀐 것만 추리면:

| 전 | 후 |
|---|---|
| `actions/setup-python@v5` + `cache: pip` | `astral-sh/setup-uv@v9` (캐시 내장) |
| `pip install -r requirements-ci.txt` | `uv sync --locked --only-group checks` |
| `make lint RUFF=ruff` | `make lint UV="uv run --no-sync"` |
| `make test PY=python` | `make test UV="uv run --no-sync"` |
| `make check-docrefs` | (그대로 — 파이썬을 안 쓴다) |

### 11.3 Makefile diff

```diff
@@
-PY  := .venv/bin/python
-RUFF := .venv/bin/ruff
+# `uv run` 은 호출마다 락·환경이 최신인지 확인하고 어긋나면 맞춘다(실측 warm 89ms,
+# --no-sync 25ms). 60ms 를 내고 "환경이 낡았다"는 사고 유형을 통째로 없앤다.
+#
+# CI 는 UV 하나만 덮어 두 변수를 다 바꾼다 — `make test UV="uv run --no-sync"`.
+# CI 에서 맨 `uv run` 을 쓰면 --only-group checks 로 좁혀 놓은 환경에 무거운 스택이
+# 되살아난다(실측: docs/research/uv-adoption.md §9.2).
+UV   := uv run
+PY   := $(UV) python
+RUFF := $(UV) ruff
 DP  := scripts/data_pipeline
 TP  := scripts/toss_probe
```

**이 세 줄이 전부다.** `$(PY)`·`$(RUFF)`를 쓰는 타깃 15곳, DAG 규칙, `check-dag`의
`$(MAKE) -p` 조회, stamp 파일 구조는 **한 줄도 안 바뀐다.**

---

## 12. 마이그레이션 체크리스트

각 단계는 `단계 → 검증 → 롤백` 세 쪽이다. **검증이 실패하면 다음으로 가지 않는다.**

> ⚠️ 전제: 브리핑대로 **다른 세션이 같은 워킹트리에서 작업 중**일 수 있다. 그래서
> ①`git add -A`를 쓰지 않고 **경로를 일일이 지정**하며 ②`.venv`를 지우지 않고 **옮긴다**
> ③각 단계가 독립적으로 되돌려진다.

1. **uv 설치·버전 확인.** 저장소에 아무것도 안 쓴다.
   → 검증: `uv --version` 이 `0.12.5` 이상 → 롤백: 없음(읽기 전용)

2. **작업 브랜치 분리.** GitHub Flow 규약대로 `main`에 직접 쓰지 않는다.
   → 검증: `git branch --show-current` 가 `feature/uv-migration`
   → 롤백: `git checkout -`

3. **`.python-version`을 건드리지 않는다는 것을 확인.** 이 단계는 "하지 않음"을 확인하는 단계다.
   → 검증: `cat .python-version` → `3.10.13` / `uv python find` 출력이
   `~/.pyenv/versions/3.10.13/…` 를 가리킴 → 롤백: 해당 없음

4. **`pyproject.toml` 맨 앞에 §11.1의 `[project]`·`[dependency-groups]`·`[tool.uv]` 3블록을
   손으로 추가.** `uv init`을 쓰지 않는다(§0.1-1: 거부당한다). `uv add -r`도 쓰지 않는다
   (§8.2: pytest·ruff가 엉뚱한 데 들어가고 주석이 안 따라온다).
   → 검증: `git diff pyproject.toml` 에서 `[tool.ruff]` 이후 변경이 **0줄**
   (`git diff -U0 pyproject.toml | grep -c '^[-+].*ruff'` 로 교차확인)
   → 롤백: `git checkout -- pyproject.toml`

5. **`uv lock` 생성.**
   → 검증: `uv lock` 성공 + `uv lock --check` 가 exit 0 + `grep -c '^\[\[package\]\]' uv.lock`
   이 240 부근 → 롤백: `rm -f uv.lock`

6. **핀이 안 풀렸는지 대조.** 이게 이 마이그레이션의 핵심 불변식이다.
   → 검증:
   `uv export --format requirements.txt --no-hashes | grep -E '^(numpy|pandas|torch|pyqlib|lightgbm|xgboost|scikit-learn|streamlit|altair|yfinance|fire|loguru|tqdm|bidask|cython)=='`
   출력이 `requirements.txt` 의 핀과 **한 줄도 다르지 않을 것**
   → 롤백: `pyproject.toml` 수정 후 `uv lock` 재실행

7. **linux 쪽 해석을 macOS에서 미리 검증.** CI가 처음 도는 곳에서 터지는 것을 막는다.
   → 검증: `uv sync --locked --only-group checks --python-platform x86_64-unknown-linux-gnu --dry-run`
   이 에러 없이 끝남 → 롤백: 해당 없음(dry-run)

8. **기존 `.venv` 교체 (유일한 파괴적 단계).**
   `.venv/bin/python -m pip freeze > /tmp/venv-before.txt` → `mv .venv .venv.bak` → `uv sync`
   → 검증: `uv run --no-sync python -c "import qlib, torch, lightgbm, pandas; print('ok')"`
   그리고 `diff <(sort /tmp/venv-before.txt) <(uv export --format requirements.txt --no-hashes | sort)`
   로 사라진 패키지 확인
   → 롤백: `rm -rf .venv && mv .venv.bak .venv` (1초)

9. **Makefile 3줄 교체 (§11.3).**
   → 검증: `make test` 와 `make lint` 가 **전과 같은 결과** / `make check-dag` 통과
   → 롤백: `git checkout -- Makefile`

10. **CI 워크플로 교체 (§11.2). PR을 올려 실제로 돌린다.**
    → 검증: ①워크플로 green ②설치 로그에 **`pyqlib`·`torch`·`nvidia-` 가 한 줄도 없을 것**
    (`uv sync` 단계 로그를 눈으로 확인 — §9.2의 되살아남이 안 일어났다는 증거)
    ③설치 패키지 수가 20개 내외
    → 롤백: `git checkout -- .github/workflows/checks.yml`

11. **`requirements.txt`·`requirements-ci.txt` 제거 + 낡은 안내 문구 정리.**
    docstring의 `실행:  .venv/bin/python scripts/…` 예시가 여럿 있다(§9.4).
    → 검증: `make check-docrefs` 통과 +
    `grep -rn 'requirements' --include='*.py' --include='*.yml' --include='Makefile' . | grep -v '\.venv'`
    가 비어 있을 것 → 롤백: `git checkout -- requirements.txt requirements-ci.txt`

12. **(별건 커밋) `cython==0.29.37` 제거.** §8.3에서 런타임 의존이 아님을 확인했다.
    순수 이전 커밋과 섞지 않는다 — 섞으면 회귀 시 원인을 못 가른다.
    → 검증: `uv lock && uv sync && uv run python -c "import qlib; print(qlib.__version__)"`
    + `make test` → 롤백: 해당 줄 복원 후 `uv lock`

**총 12단계.** 8·10번만 되돌리기에 손이 가고 나머지는 `git checkout` 한 번이다.

### 커밋 분할 제안

| 커밋 | 내용 | 단계 |
|---|---|---|
| `build(uv): pyproject 에 project·그룹 선언과 락 추가` | pyproject + uv.lock | 4–7 |
| `build(uv): Makefile 을 uv run 으로 전환` | Makefile | 9 |
| `ci(uv): setup-uv 와 그룹 동기화로 교체` | 워크플로 | 10 |
| `build(uv): requirements 파일 제거` | requirements*.txt + 안내 문구 | 11 |
| `build(deps): 런타임 의존이 아닌 cython 핀 제거` | pyproject + 락 | 12 |

`.gitignore`에는 손댈 것이 없다 — `.venv/`는 이미 제외돼 있고 `uv.lock`은 **추적해야 하므로**
아무 규칙도 추가하지 않는다(§6.1).

---

## 13. 하지 말 것

1. **`uv init`을 돌리지 말 것.** 거부당한다(§0.1-1). 성공한다면 그건 `pyproject.toml`이
   없다는 뜻이고, 더 큰 문제다.
2. **`.python-version`을 지우거나 바꾸거나 `uv python pin`으로 건드리지 말 것.**
   지금 uv를 pyenv 3.10.13에 붙들어 매고 있는 유일한 끈이다(§4.5). 없어지면 pyenv shim이
   exit 127로 죽어 uv가 멈춘다.
3. **CI에서 맨 `uv run`을 쓰지 말 것.** `--only-group checks`로 좁힌 환경에 175개를
   되살린다 — 실측(§9.2). 반드시 `UV="uv run --no-sync"`.
4. **CI에서 `--frozen`을 `--locked` 대신 쓰지 말 것.** `--frozen`은 낡은 락을 조용히
   받아들인다(§6.3). 검사의 목적이 사라진다.
5. **`uv.lock`을 `.gitignore`에 넣지 말 것.** 문서가 커밋하라고 명시한다(§6.1).
6. **`uv.lock`을 손으로 편집하지 말 것.** *"should not be edited manually."*
7. **`[build-system]`을 "혹시 몰라서" 추가하지 말 것.** 넣는 순간 uv가 저장소를 빌드·설치
   하려 든다(§2.2 대조군에서 실제로 그랬다). 그건 §3의 별건 리팩터를 시작하는 행위다.
8. **`numpy<2`를 `constraint-dependencies`로 옮기지 말 것.** 직접 import 하는 의존성이고,
   constraint는 설치를 유발하지 않아 그룹 설치에 전파되지 않는다(§8.3).
9. **`requirements.txt`의 "설치 순서가 중요" 주석을 `pyproject.toml`로 옮기지 말 것.**
   폐물이다(§8.3). 낡은 근거를 새 파일에 이식하면 다음 사람이 그걸 믿는다.
10. **§3의 `sys.path` 리팩터를 이 마이그레이션에 끼워 넣지 말 것.** 회귀가 나면 uv 탓인지
    리팩터 탓인지 못 가른다.
11. **`git add -A` 로 커밋하지 말 것.** 다른 세션이 같은 워킹트리에 있다 —
    `scripts/model_backtest/` 3개 파일이 이미 수정된 상태다.
12. **`.venv`를 `rm -rf` 하지 말 것.** `mv`로 옮긴다(§12-8). 되돌리는 비용이 1초와
    "전체 재설치" 사이의 차이다.
13. **`python-preference = "only-system"`을 추적 파일에 박지 말 것.** 로컬에서만 맞고 CI를
    깨뜨린다(§4.7).

---

## 14. 위험과 나타나는 모습

| # | 위험 | 어떻게 드러나나 | 사전 차단 | 롤백 |
|---|---|---|---|---|
| R1 | **CI에 무거운 스택이 되살아남** | CI 로그에 `Downloading pyarrow`·`nvidia-*`, 실행 3분 → 10분+ | §11.2의 `--no-sync` | 워크플로 `git checkout` |
| R2 | **linux에서 torch가 CUDA 16개를 끌어옴** | ubuntu 러너 디스크 부족/타임아웃 | CI가 기본 그룹을 안 깖(§10.3) | 정말 필요해지면 `[[tool.uv.index]] pytorch-cpu` + `explicit = true` (§14.1) |
| R3 | **첫 `uv sync`가 `.venv`의 미선언 패키지를 지움** | 잘 되던 스크립트가 `ModuleNotFoundError` | `pip freeze` 스냅샷(§12-8) | `mv .venv.bak .venv` |
| R4 | **pyenv shim이 uv를 exit 127로 죽임** | `error: Failed to inspect Python interpreter … pyenv: python3.10: command not found` | `.python-version` 보존(§13-2) | `echo 3.10.13 > .python-version` |
| R5 | **다른 세션과 충돌** | `pyproject.toml`/`Makefile` 병합 충돌, 또는 남의 `.venv` 붕괴 | 경로 지정 커밋, `.venv` 이동 방식 | 단계별 `git checkout` |
| R6 | **로컬 3.10.13 ↔ CI 3.10.x 발산** | 로컬 통과, CI만 실패 | `requires-python = "==3.10.*"` + 단일 락 | CI에 `python-version: "3.10.13"` 고정 |
| R7 | **`pyqlib` 해석 실패** | `uv lock` 이 no-solution 으로 실패 | — **실측으로 배제됨**: 244개가 2.61초에 해석됐다 | 해당 없음 |

### 14.1 R2의 탈출구 (지금은 쓰지 않는다)

linux에서 CPU torch가 필요해지면 문서가 형태를 준다:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cpu" }]
```

`explicit = true`의 뜻(원문): *"the index is only used for `torch`, `torchvision`, and other
PyTorch-related packages, as opposed to generic dependencies like `jinja2`, which should continue
to be sourced from the default index (PyPI)."*
— [guides/integration/pytorch](https://docs.astral.sh/uv/guides/integration/pytorch/)

**지금은 넣지 않는다.** 학습은 macOS에서만 돌고 CI는 torch를 아예 안 깐다. 필요 없는 인덱스
설정은 락을 복잡하게 만들 뿐이다.

### 14.2 전면 롤백 (한 번에 되돌리기)

12단계를 다 밟은 뒤에도 되돌릴 수 있다:

```
git revert <커밋들>            # 또는 브랜치를 버린다
rm -rf .venv && python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`requirements.txt`는 §12-11에서야 지워지므로, **그 전까지는 롤백에 아무 준비가 필요 없다.**
그 뒤라면 `uv export --format requirements.txt --no-hashes > requirements.txt`로 재생성된다
(실측: 락에서 `numpy==1.26.4`·`torch==2.13.0` 등이 그대로 나온다).

---

## 15. uv가 **해결하지 않는** 것

기대를 미리 깎아 둔다.

1. **`sys.path.insert` 23개 중 18개.** §3. 스크립트가 자기 디렉터리를 넣는 관용구는
   패키징과 무관하다.
2. **`# noqa: E402` 5개.** 그중 3개는 `warnings.filterwarnings`를 import보다 먼저 실행해야
   해서 생긴 것으로, **어떤 패키징으로도 안 없어진다**(§3.3).
3. **macOS의 torch↔lightgbm OpenMP 무음 크래시.** `OMP_NUM_THREADS=1`은 여전히 필요하다.
   uv는 설치를 관리하지 런타임 환경변수를 관리하지 않는다.
4. **`brew install libomp` 같은 시스템 라이브러리.** uv는 PyPI 밖을 모른다.
5. **`vendor/dump_bin.py` 같은 벤더링된 코드.** 의존성이 아니라 파일이다.
6. **핀을 언제 올릴지에 대한 판단.** 문서 원문 —
   *"uv will not consider lockfiles outdated when new versions of packages are released—the
   lockfile needs to be explicitly updated if you want to upgrade dependencies."*
   `uv lock --upgrade`를 **사람이** 불러야 한다.
7. **테스트가 무엇을 import 하는지에 대한 규율.** `checks` 그룹의 내용은 여전히 손으로
   정한다. 락이 없애 주는 것은 **버전 동기화**이지 **목록 결정**이 아니다.
8. **데이터 DAG.** Makefile의 파일 의존 그래프는 uv와 무관하게 그대로다.
9. **다른 세션과의 워킹트리 공유 문제.** 오히려 `.venv`를 공유 자원으로 만들어 **조금 더**
   민감해진다 — 한쪽이 `uv sync --only-group checks`를 돌리면 다른 쪽 환경이 좁아진다.

---

## 16. 확인하지 못한 것

**실행해서 본 것과 문서만 읽은 것을 가른다.** 이 절을 빼면 위의 확신이 과대평가된다.

### 16.1 돌려 보지 못한 것 (문서·메타데이터로만 판단)

1. **linux x86_64에서 실제 설치·테스트를 못 했다.** 이 머신은 macOS arm64뿐이다. linux 쪽
   근거는 ①락파일의 `manylinux` wheel 항목 ②`--python-platform x86_64-unknown-linux-gnu
   --dry-run` 성공 ③PyPI의 wheel 목록 — **셋 다 "해석"이지 "설치·import"가 아니다.**
   §12-7이 dry-run까지만 하는 이유이고, **진짜 검증은 §12-10의 첫 PR이다.**
2. **CI 워크플로를 GitHub Actions에서 돌려 보지 못했다.** §11.2 YAML은 공식 가이드와
   `setup-uv` README 대조로 조립한 것이다. `astral-sh/setup-uv@v9`가 최신 메이저인지는
   가이드가 v9 해시를 예시로 쓰는 것으로 미뤄 짐작했을 뿐 **릴리스 목록을 확인하지 않았다.**
3. **캐시 적중률·절약 시간을 재지 못했다.** `enable-cache: "auto"` 기본값과 glob 목록은
   README **문자열로만** 확인했다.
4. **linux에서 torch가 실제로 CUDA 16개를 끌어오는지 설치로 확인하지 않았다.**
   락파일의 `marker = "sys_platform == 'linux'"` 항목을 센 것이다.
5. **`pyqlib 0.9.7`이 numpy 2.x에서 실제로 깨지는지 확인하지 않았다.** 확인한 것은
   **메타데이터에 numpy 상한이 없다**는 사실뿐이다. 즉 `numpy==1.26.4` 핀의 필요성은
   기존 저장소 판단을 승계한 것이지 이번에 재검증한 것이 아니다.
6. **§3의 리팩터를 이 저장소에서 실행하지 않았다.** 스크래치패드에 같은 구조를 재현해
   `import execution, toss`가 동작함을 봤을 뿐, **실제 6개 파일을 고쳐 `make test`를
   통과시키지 않았다.** "16개 제거 가능"은 정적 분석 결과다.

### 16.2 돌려서 본 것 (근거가 실행 출력인 것)

`uv init` 거부 · `[build-system]` 유무에 따른 빌드/미빌드 · `uv lock` 244개 해석 ·
전체 스택 import 성공 · pip venv 재사용과 `six` 삭제 · `--locked`/`--frozen`/`--check`의
차이 · `--only-group checks`가 numpy 1.26.4를 끌어옴 · 맨 `uv run`이 175개를 되살림 ·
`uv run` 3종 지연시간 · pyenv shim exit 127 · `uv python pin` 덮어쓰기와
`requires-python` 방어 · `uv add -r`의 핀·주석 보존 · Make 3.81 명령줄 override ·
`uv export`가 핀을 되뱉음.

### 16.3 범위 밖으로 둔 것

- **uv 0.12.5 기준이다.** 이후 버전의 동작 변화는 확인하지 않았다. §11.2가 CI에서
  `version: "0.12.5"`를 고정하는 이유다.
- `uv workspace`(단일 프로젝트라 불필요), `uv build`/`publish`(배포 안 함),
  `uv tool`(전역 도구 없음), `uv audit`·`uv format`·`uv check`(0.12에 있는 신규
  서브커맨드지만 이 전환과 무관).
- **`pylock.toml`**(PEP 751). `uv export --format pylock.toml`이 존재하는 것은 확인했으나
  이 저장소에 쓸 이유를 찾지 못해 조사하지 않았다.
- **`[tool.uv] environments` 로 플랫폼을 macOS+linux 둘로 좁히는 것.** 락을 작게 만들 수
  있으나 지금 244개·3461줄이 문제가 되지 않아 시도하지 않았다.
