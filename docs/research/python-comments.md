# 리서치 — 파이썬 주석·docstring 규율과 기계 검사 가능성

- 조사일: 2026-08-19
- 목적: **"주석을 어떻게 쓰고 무엇을 지우는가"** 에 관해 (1) 1차 출처가 실제로 규정하는 것과
  나중에 관행으로 굳은 것을 가르고, (2) 사람이 판단해야 하는 것과 린터가 잡을 수 있는 것의
  경계를 확정한다. 이 저장소에는 **린트 설정이 아예 없으므로** 도구 권고는 전부 그린필드
  결정이며, 권고한 규칙은 실제로 돌려서 검출 수를 확인했다.
- 방법: PEP은 `peps.python.org` HTML과 **`python/peps` 저장소의 reST 원본**을 내려받아 문자열을
  직접 잘라 붙였다. Ruff 규칙 코드는 **`astral-sh/ruff` 저장소 `crates/ruff_linter/src/codes.rs`
  원본**과 규칙 페이지 양쪽에서 대조했고, 스크래치 venv에 **ruff 0.16.3을 설치해 이 저장소에
  직접 돌려** 검출 수를 실측했다. 타 프로젝트 설정은 각 저장소의 설정 파일 원본을 받아 grep했다.
  **논문은 저자 배포·arXiv PDF를 내려 본문을 판독했고, 열지 못한 것은 §12에 전부 적었다** —
  이 조사에서 **동료심사 논문 4편을 초록조차 열지 못했다.**
- ⚠️ **조사 방법 경고 (자매 문서 `trial-accounting.md` §9와 같은 종류를 또 겪었다).**
  웹 페이지 요약 도구에 "`lint.pydocstyle.convention`이 각 값에서 어떤 D 규칙을 끄는가"를
  물었더니 **존재하지 않는 규칙 코드(D220~D235)를 나열한 표**를 그럴듯하게 돌려줬다.
  §3.4의 대응표는 그래서 **Ruff 소스 `rules/pydocstyle/settings.rs`의
  `rules_to_be_ignored()` 매치문을 직접 읽어** 만든 것이다.
  같은 조사에서 **검색엔진이 존재하지 않는 논문 제목과 출처 없는 수치를 만들어 냈다**(§12 하단).
  **요약본으로 규칙 코드·절 번호·논문 수치를 인용하지 말 것.**
- 자매 문서: [`study-pitfalls.md`](../project/study-pitfalls.md) — 착수 전 필독 함정 목록.
  이 문서 §7의 "코드 주석이 가리키는 문서가 사라진다"는 그쪽과 같은 계열의 실패다.
- ★ **이 문서가 판정 대상으로 삼는 정책은 저장소 안에 없다.** 주석 규율(§11)은
  `~/.claude/CLAUDE.md` §6 "Comments"에 있고, 그 파일은 이 저장소가 아니라 사용자 홈에 있다.
  프로젝트 `CLAUDE.md`는 [`.gitignore`](../../.gitignore) 45행으로 추적 제외다. **둘 다 클론에
  가지 않는다.** 그래서 이 문서는 §6 정책을 **링크하지 않고 인용해 옮겨 적는다** — 추적 문서가
  추적 밖 파일을 링크하지 않는다는 프로젝트 규칙과, 이 문서 §7이 진단하는 링크 부패 양쪽 때문이다.

---

## 0. 요약 — 확립된 것 vs 통설

### 확립된 것 (1차 출처로 확인)

1. **주석에 관한 MUST는 파이썬 어디에도 없다.** PEP 8은 `Type: Process`이고 적용 범위를
   스스로 표준 라이브러리로 한정하며, **프로젝트 규칙이 자기보다 우선한다고 명시**한다.
   PEP 257은 `Type: Informational`이고 "conventions, not laws"라고 자기 성격을 규정한다(§1.1).
   → **이 저장소가 PEP 8과 다른 규칙을 정하는 것은 PEP 8 자신이 허용한 행위다.**
2. **PEP 257에는 `Args:` · `Returns:` · `Parameters\n----------` 문법이 없다.** 유일한 인자
   문서화 예시는 `Keyword arguments:` + `real -- the real part (default 0.0)`이다. Google ·
   NumPy · Sphinx 방언은 전부 **PEP 이후의 관행 누적**이고, PEP 727이 이를 "microsyntaxes"라
   부르며 **"there is no formalized standard"** 라고 못 박는다(§3.1).
3. **docstring에 타입을 다시 쓰는 것은 PEP 484가 명시적으로 기각한 대안이다.** PEP 3107의 집필
   동기가 "docstring을 파싱해 타입을 읽는" 관행의 대체였고, PEP 484는 Sphinx `:type arg1:`
   표기를 **"pretty verbose … and not very elegant"** 로 기각했다. Google은 이를 규칙으로 옮겨
   **"if the code does not contain a corresponding type annotation"** 조건을 붙였다(§3.3).
4. **반대로 `Raises:`는 타입 힌트가 대체하지 못한다 — PEP 484가 그 일을 docstring에 명시적으로
   위임했다**: *"No syntax for listing explicitly raised exceptions is proposed … the
   recommendation is to put this information in a docstring."* → **`Args:`에서 타입은 빼고
   `Raises:`는 남기는 것**이 1차 출처가 지지하는 유일한 조합이다(§3.3).
5. **"public API만 docstring"은 출처가 있다.** 단 **흔히 인용되는 절반이 잘려 있다** — PEP 8은
   private에 대해 면제가 아니라 *"but you should have a comment that describes what the method
   does"* 를 요구한다(§4.1). Google은 기준을 셋으로 넓힌다 — public API **또는** nontrivial size
   **또는** non-obvious logic(§4.2).
6. **비영어 주석을 명시적으로 금지·제한하는 규범 텍스트는 두 곳이다.** PEP 8(*"please write your
   comments in English, unless you are 120% sure …"*)과 **GNU Coding Standards §5.2**
   (*"Please write the comments in a GNU program in English"* — 예외 조항 없음). 이 저장소 원격은
   public GitHub이므로 PEP 8의 예외 조건이 성립하지 않는다(§9.1).
7. ★★ **자동 낡음 탐지는 배포 가능한 수준이 아니며, 널리 인용되는 수치는 다른 것을 재고 있다.**
   실제 발생률(양성:음성 ≈ 1:38)을 유지한 유일한 대규모 평가에서 최고 성능 탐지기는
   **정밀도 64.0% · 재현율 17.1% · F1 27.0%** 였다 — **노후 주석 6개 중 5개를 놓친다**
   (Liu et al., IEEE TSE 49(1), 2023). 흔히 인용되는 **F1 87**은 인공적으로 균형을 맞춘
   데이터셋 값이고, 같은 아키텍처를 현실 분포에서 독립 재현하면 **F1 44.7**로 떨어진다
   (Xu et al., ICSE 2023). **배포된 린터·IDE 플러그인은 어느 논문에도 없다**(§6.2).
8. ★★ **"주석을 달면 이해가 좋아진다"의 측정 근거는 놀랄 만큼 약하다.** 시선추적 통제실험에서
   주석 효과는 스니펫에 따라 **−30%에서 +34%까지 갈리고, 12개 중 정답률이 유의하게 개선된 것은
   1개뿐**이었다(Abdelsalam et al., *Empirical Software Engineering*, 2025). 그리고 그 논문
   자체가 이렇게 적는다 — 참가자의 호의적 인식이 *"did **not** consistently translate into
   improved performance"* (§2.5).
9. **주석은 코드와 함께 잘 바뀌지 않는다 — 두 실증이 방향은 같고 크기는 다르다.**
   Fluri et al.(SQJ 17(4), 2009): **direct co-change의 98%는 같은 리비전**에서 일어나지만
   **co-change 자체가 전체 주석 변경의 50~69%** 뿐이다. Wen et al.(ICPC 2019, 1,500 프로젝트):
   **코드 변경의 13~20%만 주석 변경을 유발**한다(§6.4).
10. ★★ **주석 안의 링크는 실제로 썩는다 — 측정치가 있다.** 9,654,702개 링크(고유 382,650개)
    전수 접속에서 **9.1%가 404**, 드물게 참조되는 도메인은 **32~37%**가 죽어 있었고,
    **갱신된 링크는 9% 미만**이었다(Hata et al., ICSE 2019). 저자 권고: **태그·커밋 해시를 명시할
    것**(§7.6).
11. ★★ **주석↔외부문서 중복에 대한 1차 지침이 존재한다** — 처음에 "출처 없음"으로 적었다가
    정정했다. Ousterhout(CS190 강의노트, 본인 문장): *"Document each thing exactly once: don't
    duplicate documentation (it won't get maintained)"* · *"don't use comments in one place to
    describe design decisions elsewhere."* Google(*Software Engineering at Google* ch.10):
    *"it is important to designate **canonical documentation**"*(§7.5).
12. **Ruff 0.16.3의 969개 규칙 중 주석 안의 마크다운 강조·장식기호·구분선을 다루는 규칙은
    0개다**(전 규칙 explanation 전문 검색). PEP 8도 다루지 않는다. → §10은 **출처 없는 판단
    문제**이며, 그렇게 표시한다.
13. **이 저장소 실측(§5.2)**: `ERA001` **0건**, `TD`+`FIX` **0건**(TODO/FIXME/XXX/HACK이 하나도
    없다), `D` 273건(pep257 규약), docstring 커버리지 **46.4%**, `W505`를 PEP 8의 72자로 걸면
    **817건** · 100자로 걸면 **2건**.
14. **죽은 문서 참조는 1건이 아니라 5건이다**(§7.2). 그리고 그중 1건은 **추적조차 되지 않는
    문서**(`docs/findings/`)를 가리킨다 — 클론에서 영원히 해소 불가다.
15. **이 저장소에는 설정되지 않은 린터를 향한 `# noqa` 지시가 약 50개 있다**(§5.4).
    검증하는 도구가 없으므로 현재는 전부 **확인 불가능한 주장**이다.

### 널리 반복되지만 출처가 없거나, 출처가 생각과 다른 것

1. ⚠️ **"주석은 나쁜 코드에 대한 사과다."** — Martin *Clean Code* ch.4의 프레이밍이다.
   **널리 인용되는 반박 두 편(qntm, Muratori)은 주석 장을 아예 다루지 않는다** — 전문 확인.
   주석 장을 정면 비판하는 것은 Ousterhout와 bugzmanov 두 곳뿐이며, **둘 다 수사적 효과를
   문제 삼는 것이고 실증 반증이 아니다.** 그리고 Martin은 프레이밍을 철회하지 않았다(§2.4).
2. ⚠️ **"주석은 코드가 표현할 수 없는 정보만 담는다"(Ousterhout)** — 논증이며 **측정이 아니다.**
   본인이 근거로 제시하는 "50-80%", "10-100x", "5-10x"는 **자기 추정치**이고, 그가 독자에게
   권하는 것은 데이터가 아니라 자기 성찰이다(§2.3).
3. ⚠️ **"주석은 WHY를 쓰고 WHAT을 쓰지 않는다"** — 보편 합의가 아니다. **Linux kernel coding
   style은 정반대를 규정한다**: *"Generally, you want your comments to tell WHAT your code does,
   not HOW."* Ousterhout는 §13.6에서 *"what and why, not how"* 라 한다. **세 출처가 WHAT의
   위치에 관해 서로 다르다**(§2.6).
4. **"주석 줄 수 / 코드 줄 수 비율에 적정값이 있다."** — 어떤 1차 출처에도 없다. 이 저장소의
   3.0~5.7%(§5.1)를 높다/낮다고 판정할 근거는 **없다.**
5. **"주석 안의 `**bold**` · `★` · `⚠️`가 해롭다."** — 출처 없음. 판단 문제다(§10).
6. **"한글 주석이 영어 주석보다 이해도가 낮다."** — ★ **유병률 연구는 있고 효과 연구는 없다.**
   Pawelka & Jürgens(ICSME 2015)는 산업 시스템 5개에서 비영어 주석 **50~90%**를 측정했지만
   **이해도·결함 효과를 전혀 측정하지 않는다**(전문에서 `controlled experiment`·`participants`
   grep 0건). 그 논문이 "주석이 이해를 돕는다"의 근거로 인용하는 두 편은 1981년·1988년
   논문이고, **이 조사는 그 둘을 열지 못했다**(§9.3, §12).
7. **문학적 프로그래밍(Knuth 1984)이 정답이었다.** — Knuth 본인이 미채택을 인정한다:
   *"It has tens of thousands of fans, but not millions."* (§2.7)

---

## 1. 규범 텍스트의 실제 범위 — MUST는 없다

### 1.1 두 PEP의 자기 규정

| | PEP 8 | PEP 257 |
|---|---|---|
| Title | Style Guide for Python Code | Docstring Conventions |
| Status / Type | `Active` / **`Process`** | `Active` / **`Informational`** |
| 적용 범위 자기 진술 | *"coding conventions for the Python code comprising the standard library"* | *"conventions, not laws or syntax"* |
| 강제력 | **프로젝트 규칙이 우선한다고 명시** | *"the worst you'll get is some dirty looks"* |

PEP 8 서문 ([peps.python.org/pep-0008](https://peps.python.org/pep-0008/)):

> "This document gives coding conventions for the Python code comprising the standard library
> in the main Python distribution."
>
> "Many projects have their own coding style guidelines. In the event of any conflicts, such
> project-specific guides take precedence for that project."

한국어: 이 문서는 **표준 라이브러리**를 구성하는 파이썬 코드의 코딩 규약이다. 많은 프로젝트는
자체 스타일 가이드가 있으며, **충돌하는 경우 그 프로젝트에서는 프로젝트 가이드가 우선한다.**

그 다음 절 제목이 "A Foolish Consistency is the Hobgoblin of Little Minds"이고, 본문은:

> "A style guide is about consistency. Consistency with this style guide is important.
> Consistency within a project is more important. Consistency within one module or function is
> the most important.
>
> However, know when to be inconsistent -- sometimes style guide recommendations just aren't
> applicable. When in doubt, use your best judgment."

한국어: 스타일 가이드는 일관성에 관한 것이다. 이 가이드와의 일관성은 중요하다. **프로젝트 내
일관성이 더 중요하다. 한 모듈·함수 내 일관성이 가장 중요하다.** 다만 언제 어겨야 하는지도 알아야
한다 — 권고가 그냥 적용되지 않는 경우가 있다.

PEP 257 서문 ([peps.python.org/pep-0257](https://peps.python.org/pep-0257/)):

> "The PEP contains conventions, not laws or syntax."
>
> "If you violate these conventions, the worst you'll get is some dirty looks. But some
> software (such as the Docutils docstring processing system PEP 256, PEP 258) will be aware
> of the conventions, so following them will get you the best results."

한국어: 이 PEP는 **법이나 문법이 아니라 규약**을 담는다. 어겨도 최악의 결과는 눈총 정도다.
다만 일부 소프트웨어가 이 규약을 알고 있으므로, 따르면 가장 좋은 결과를 얻는다.

**따라서 §11에서 이 저장소 정책을 PEP와 대조할 때 "위반"이라는 단어는 쓰지 않는다.** PEP 8은
스스로 프로젝트 규칙에 자리를 내준다. 문제가 되는 것은 **정책이 PEP와 다른 경우가 아니라,
다르다는 사실과 그 근거가 어디에도 적혀 있지 않은 경우**다.

### 1.2 PEP 8이 주석에 관해 실제로 규정하는 전부

reST 원본 805–896행 전문에서 온 것이며, 이것이 **PEP 8의 주석 규정 전량**이다.

일반:

> "Comments that contradict the code are worse than no comments. Always make a priority of
> keeping the comments up-to-date when the code changes!"
>
> "Comments should be complete sentences. The first word should be capitalized, unless it is an
> identifier that begins with a lower case letter (never alter the case of identifiers!)."
>
> "Block comments generally consist of one or more paragraphs built out of complete sentences,
> with each sentence ending in a period."
>
> "Ensure that your comments are clear and easily understandable to other speakers of the
> language you are writing in."

한국어: 코드와 모순되는 주석은 없는 것보다 나쁘다. 코드가 바뀔 때 주석을 최신으로 유지하는 것을
항상 우선할 것. 주석은 완전한 문장이어야 한다. 첫 단어는 대문자로 — **단 소문자로 시작하는
식별자인 경우는 예외이며, 식별자의 대소문자는 절대 바꾸지 말 것.** 블록 주석은 마침표로 끝나는
완전한 문장으로 된 하나 이상의 문단이다. 주석은 **자신이 쓰는 언어의 다른 화자에게** 명확하고
이해 가능해야 한다.

블록 주석:

> "Block comments generally apply to some (or all) code that follows them, and are indented to
> the same level as that code. Each line of a block comment starts with a `#` and a single
> space (unless it is indented text inside the comment)."
>
> "Paragraphs inside a block comment are separated by a line containing a single `#`."

한국어: 블록 주석은 뒤따르는 코드에 적용되며 그 코드와 같은 수준으로 들여쓴다. 각 줄은 `#` +
공백 하나로 시작한다. **문단 구분은 `#` 하나만 있는 줄**이다.

인라인 주석:

> "Use inline comments sparingly."
>
> "Inline comments should be separated by at least two spaces from the statement. They should
> start with a # and a single space."
>
> "Inline comments are unnecessary and in fact distracting if they state the obvious. Don't do
> this: `x = x + 1                 # Increment x` … But sometimes, this is useful:
> `x = x + 1                 # Compensate for border`"

한국어: 인라인 주석은 아껴 쓸 것. 문장과 **최소 두 칸** 띄우고 `#` + 공백 하나로 시작한다.
**당연한 것을 말하는 인라인 주석은 불필요하고 실제로 산만하다.**

**여기서 끝이다.** PEP 8은 다음을 다루지 않는다 — 주석의 적정 밀도, 주석 안의 서식·기호,
주석이 외부 문서를 가리키는 방식, TODO의 형식, 주석 처리된 코드.
`# Increment x` vs `# Compensate for border` 이 대조 하나가 PEP 8이 내용에 관해 말하는 전부다.

### 1.3 PEP 8의 주석 줄 길이 — 유일하게 수치가 있는 항목

> "Limit all lines to a maximum of 79 characters.
>
> For flowing long blocks of text with fewer structural restrictions (docstrings or comments),
> the line length should be limited to 72 characters."
>
> "Some teams strongly prefer a longer line length. For code maintained exclusively or
> primarily by a team that can reach agreement on this issue, it is okay to increase the line
> length limit up to 99 characters, **provided that comments and docstrings are still wrapped
> at 72 characters.**"

한국어: 모든 줄은 79자 이하. **docstring·주석처럼 구조 제약이 덜한 긴 텍스트 블록은 72자
이하.** 팀이 합의하면 코드 줄은 99자까지 늘려도 되지만, **주석과 docstring은 여전히 72자로
줄바꿈한다는 조건**이 붙는다.

★ 이것이 PEP 8 규정 중 이 저장소와 가장 크게 어긋나는 항목이다. 72자로 걸면 **817건**,
100자로 걸면 **2건**이다(§5.2). 그리고 이 규칙은 **한글에 그대로 적용할 수 없다** — Ruff의
`W505`는 문자 수를 세지만 한글은 대부분 폰트에서 두 칸 폭을 차지하므로, "72자"의 원래 의도
(80칸 창에서 줄바꿈 없이 읽힌다)를 한글에 옮기면 **36자쯤**이 되고, 이 저장소의 서술형 주석은
그 길이로 성립하지 않는다. **PEP 8의 72자는 이 저장소에 이식 불가능하며, 그 근거는 규칙의
목적이 문자 수가 아니라 표시 폭이라는 데 있다.**

### 1.4 PEP 257이 docstring에 관해 실제로 규정하는 것

> "All modules should normally have docstrings, and all functions and classes exported by a
> module should also have docstrings. Public methods (including the `__init__` constructor)
> should also have docstrings."
>
> "For consistency, always use `"""triple double quotes"""` around docstrings."
>
> "The docstring is a phrase ending in a period. It prescribes the function or method's effect
> as a command (“Do this”, “Return that”), not as a description; e.g. don't write “Returns the
> pathname …”."
>
> "The one-line docstring should NOT be a “signature” reiterating the function/method
> parameters (which can be obtained by introspection)."
>
> "The docstring for a function or method should summarize its behavior and document its
> arguments, return value(s), side effects, exceptions raised, and restrictions on when it can
> be called (all if applicable)."
>
> "It is best to list each argument on a separate line."
>
> "Unless the entire docstring fits on a line, place the closing quotes on a line by themselves."

한국어: 모듈은 통상 전부 docstring이 있어야 하고, 모듈이 **export하는** 함수·클래스도 그렇다.
public 메서드(`__init__` 포함)도 그렇다. 항상 `"""`를 쓴다. docstring은 마침표로 끝나는 구이며,
**서술이 아니라 명령형**으로 효과를 규정한다. 한 줄 docstring은 **introspection으로 얻을 수 있는
시그니처의 재진술이어서는 안 된다.** 함수·메서드 docstring은 동작·인자·반환값·부수효과·발생
예외·호출 가능 조건을 요약한다. **인자는 한 줄에 하나씩 나열하는 것이 좋다.** 한 줄에 안 들어가면
닫는 따옴표는 자기 줄에 둔다.

★★ **그런데 PEP 257의 유일한 인자 문서화 예시는 이것이다:**

```python
def complex(real=0.0, imag=0.0):
    """Form a complex number.

    Keyword arguments:
    real -- the real part (default 0.0)
    imag -- the imaginary part (default 0.0)
    """
```

`Args:`도 `Parameters`도 `:param:`도 없다. **PEP 257에 그 문법은 존재하지 않는다.**
이 사실이 §3 전체의 출발점이다.

---

## 2. 남길 것 vs 지울 것 — 두 학파와 판정 절차

### 2.1 1차 출처가 어디에 서 있는가

주석 문헌에는 서로 다른 방향으로 미는 두 프레이밍이 있다.

- **(A) 주석은 코드가 표현할 수 없는 정보를 담는다** — 의도, 단위, 모듈 경계를 넘는 불변식,
  기각된 대안의 근거. Ousterhout 계열.
- **(B) 주석은 코드로 표현하지 못한 것에 대한 사과다** — 주석이 필요하면 코드를 고쳐라.
  Martin *Clean Code* ch.4 계열.

**PEP과 Google은 (A)에 가깝고, (B)의 강한 형태를 지지하지 않는다.** 근거:

1. PEP 8은 주석의 **존재를 전제하고 형식을 규정**한다. "주석을 줄여라"는 문장이 없다.
   있는 것은 *"Use inline comments sparingly"*(인라인 한정)와 *"unnecessary … if they state
   the obvious"* — 즉 **당연한 것을 말하는 주석**을 겨냥하며, 주석 자체를 겨냥하지 않는다.
2. Google 스타일 가이드 §3.8.5는 주석을 **적극적으로 요구**한다:

   > "The final place to have comments is in tricky parts of the code. If you're going to have
   > to explain it at the next code review, you should comment it now. Complicated operations
   > get a few lines of comments before the operations commence."

   한국어: 주석의 마지막 자리는 코드의 까다로운 부분이다. **다음 코드 리뷰에서 설명해야 할
   것이라면 지금 주석을 달아라.**
   ([google.github.io/styleguide/pyguide.html](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings))
3. 같은 절이 (B)와 겹치는 부분도 **분명히** 있다:

   > "On the other hand, never describe the code. Assume the person reading the code knows
   > Python (though not what you're trying to do) better than you do."

   한국어: 반면 **코드를 서술하지는 말 것.** 코드를 읽는 사람이 파이썬을 (당신이 하려는 일은
   몰라도) 당신보다 잘 안다고 가정하라.

→ **양쪽이 실제로 합의하는 명제는 하나다: "코드가 이미 말하는 것을 다시 말하는 주석은 지운다."**
그 이상은 (B)의 확장이고, 확장 부분은 출처가 약하다.

★ **그런데 §2.5의 실증이 (B)에 예상 밖의 지원을 준다.** 주석이 이해도를 올린다는 측정 근거가
약하기 때문이다. **이 문서는 (A)를 규범으로, (B)의 절제 요구를 실증으로 받아들인다** —
둘이 대립하지 않는 지점이 §2.8 판정표다.

### 2.2 Ousterhout — 장 구성과 실제 문장

*A Philosophy of Software Design* 1판(2018)의 주석 관련 장 제목은 **실물 목차로 검증**했다
(도서관 ToC 스캔 PDF 판독). 사용자 통념대로다:

| 장 | 제목 | 이 문서와 관련된 절 |
|---|---|---|
| 12 | Why Write Comments? The Four Excuses | 12.1 자기문서화 코드 / 12.2 시간 없음 / 12.3 낡는다 / 12.4 본 주석은 다 쓸모없다 |
| 13 | Comments Should Describe Things that Aren't Obvious from the Code | 13.2 Don't repeat the code · **13.3 Lower-level comments add precision** · **13.4 Higher-level comments enhance intuition** · 13.6 Implementation comments: what and why, not how · **13.7 Cross-module design decisions** |
| 15 | Write The Comments First | 15.3 Comments are a design tool |
| 16 | Modifying Existing Code | **16.2 keep the comments near the code** · 16.3 Comments belong in the code, not the commit log · **16.4 avoid duplication** |

⚠️ **판본 주의:** 위는 1판이다. 2판(2021-07)은 새 장이 추가됐고 **2판 목차를 확인하지 못했다.**
2판을 인용하려면 번호를 다시 확인해야 한다.

**본인 문장 — Stanford CS190 강의노트**(`web.stanford.edu/~ouster/cgi-bin/cs190-winter18/lecture.php?topic=comments`).
저자 본인이 쓴 1차 자료이며 winter18·winter19 두 URL의 본문은 동일하다:

> "Comments should describe things that are not obvious from the code."

> ```
> Comments should be at a different level of detail than code
>   Lower level comments provide precision (especially for
>     variables, arguments, return values):
>       Exactly what is this thing?
>       What are the units?
>       Boundary conditions
>       If memory is dynamically allocated, who is responsible for freeing it?
>       Invariants?
>   Higher-level comments capture intuition:
>     Abstractions: a higher-level description of what the code is doing.
>     Rationale for the current design: why the code is this way.
>     How to choose the value of a configuration parameter.
> ```

한국어: 주석은 **코드와 다른 상세 수준**이어야 한다. **더 낮은 수준**의 주석은 정밀성을 준다 —
정확히 무엇인가, **단위가 무엇인가**, 경계 조건, **불변식**. **더 높은 수준**의 주석은 직관을
포착한다 — 추상, **현 설계의 근거(왜 코드가 이런가)**, 설정 파라미터 값을 어떻게 고르는가.

→ **판정표(§2.8) 행 6·7·9의 1차 근거가 이 블록이다.** 단위·불변식·설계 근거가 **저자 본인
문장으로** 열거돼 있다.

주석을 먼저 쓰는 것(§15):

> ```
> Instead, write comments at the beginning:
>   I write class comments, method headers (signature and comments)
>     before writing the bodies of methods
> Use comments as a design tool:
>   Allows you to focus on the abstractions
>   Comments indicate interface complexity
>     Design APIs for simplest documentation
> ```

한국어: 대신 **처음에** 주석을 쓴다. 나는 메서드 본문을 쓰기 전에 클래스 주석과 메서드 헤더를
쓴다. **주석을 설계 도구로 쓴다** — 추상에 집중하게 하고, **주석이 인터페이스 복잡도를 지시한다.
가장 단순한 문서가 나오도록 API를 설계하라.**

⚠️ **인용 시 두 가지 주의:**
- **§13.1의 4종 분류**(interface / data structure member / implementation / cross-module)는
  독립된 두 개의 2차 요약이 서로 일치하지만 **원문을 열지 못했다.** 인용부호를 씌우면 안 된다.
  1차로 확보된 것은 **2종 분류**뿐이다(CS190 노트): *"Two kinds of documentation for classes and
  methods: **Interface**: what someone needs to know in order to use this class or method /
  **Implementation**: how the method or class works internally … Important to separate these:
  do not describe the implementation in the interface documentation!"*
- **"clutter"라는 단어를 Ousterhout에게서 찾지 못했다.** 확인된 것은 절 제목 `13.2 Don't repeat
  the code`뿐이다. `Clutter`는 *Clean Code*의 휴리스틱 이름(`G12: Clutter`, p.293)이며
  **두 책 사이에서 섞인 것으로 보인다.**

### 2.3 ★ Ousterhout의 인식론적 지위 — 측정이 아니다

가장 강한 1차 증거는 Ousterhout–Martin 공개 토론 문서
([github.com/johnousterhout/aposd-vs-clean-code](https://github.com/johnousterhout/aposd-vs-clean-code),
Ousterhout 본인 사이트가 링크하므로 저자 승인 1차 자료). 그가 자기 근거를 직접 서술한다:

> "I often hear people complain about stale comments (usually as an excuse for writing no
> comments at all) but I have not found them be a significant problem over my career. …
> In contrast, I waste *enormous* amounts of time because of inadequate documentation; it's not
> unusual for me to spend 50-80% of my development time wading through code to figure out
> things that would be obvious if the code was properly commented."

> "For me the cost of missing comments is easily 10-100x the cost of incorrect comments."

> "I invite everyone reading this article to ask yourself the following questions: * How much
> does your software development speed suffer because of incorrect comments? * How much does
> your software development speed suffer because of missing comments?"

한국어: 나는 낡은 주석 불평을 자주 듣지만 **내 경력에서 유의미한 문제였던 적이 없다.** 반면
문서가 부실해서 낭비하는 시간은 **엄청나다** — 개발 시간의 **50–80%**를 코드를 헤집는 데 쓰는
일이 드물지 않다. **주석 누락의 비용은 잘못된 주석 비용의 10–100배**다. … 이 글을 읽는 모든
분께 **스스로 물어보시길** 권한다.

★ **"50-80%" · "10-100x" · "5-10x"는 측정치가 아니라 자기 추정치다.** 실험도 통계도 없고,
저자가 독자에게 권하는 검증 방법은 **자기 성찰**이다. **그리고 §2.5의 측정 결과는 그의 추정과
같은 방향이 아니다.** 이 문서가 (A)를 규범으로 채택하면서도 "측정된 것"으로 부르지 않는 이유다.

다만 그가 제시하는 **비-경험적 논거 하나는 강하다**(같은 문서):

> "The first reason for comments is abstraction. Simply put, without comments there is no way
> to have abstraction or modularity."
>
> "If you choose not to write an interface comment for methods, then you leave the interface of
> that method undefined. Even if someone reads the code of the method, they won't be able to
> tell which parts of the implementation are expected to remain the same and which parts may
> change (**there is no way to specify this 'contract' in code**)."

한국어: 주석이 필요한 첫째 이유는 **추상**이다. 주석 없이는 추상도 모듈성도 있을 수 없다.
인터페이스 주석을 쓰지 않으면 그 메서드의 인터페이스는 **정의되지 않은 채** 남는다. 코드를 읽어도
구현의 어느 부분이 유지될 것이고 어느 부분이 바뀔 수 있는지 알 수 없다 —
**이 '계약'을 코드로 명시할 방법이 없기 때문이다.**

→ **이것은 논리 논거이고 측정과 무관하게 성립한다.** 이 저장소에 정확히 해당하는 예가 있다:
[`src/execution/interface.py`](../../src/execution/interface.py) `:127`의 `get_sellable` 계약
주석이 그 "코드로 명시할 수 없는 계약"이며, **주석 자신이 그 사실을 적어 둔다**
("러너의 미조회 중단 가드가 이 계약에 의존하므로, 지키지 않는 구현은 가드를 죽은 코드로 만든다").

### 2.4 (B)를 인용할 때 — 논쟁의 정확한 범위

*Clean Code* ch.4의 목차는 **출판사 배포 샘플 PDF**로 완전 검증했다
([informit.com](https://www.informit.com/content/images/9780132350884/samplepages/9780132350884.pdf)).
"good comments" 8종(Legal / Informative / Explanation of Intent / Clarification / Warning of
Consequences / TODO / Amplification / Javadocs in Public APIs)과 "bad comments" 17종이 실재한다.

★ **주목할 항목: bad comments에 `Nonlocal Information`(p.69)이 있다** — 주석이 자기 위치와
무관한, 다른 곳에 사는 정보를 담는 것. **§7의 주석↔외부문서 문제에 대한 정식 항목이다.**
(본문은 열지 못했다 — 제목만 검증.)

**★ 페이지 배분이 산술적으로 편향을 보여준다: Good Comments 4쪽(55→59) vs Bad Comments 15쪽(59→74).**

유명한 프레이밍은 **Ousterhout가 p.54로 명시해 인용**하고, **같은 문서에서 Martin이 답하되 인용
자체를 부정하지 않는다:**

> "The proper use of comments is to compensate for our failure to express ourselves in code.
> Note that I use the word failure. I meant it. Comments are always failures."
> — Ousterhout가 *Clean Code* p.54에서 인용

Martin의 응답(본인 문장, 같은 문서):

> "That chapter begins with these words: *Nothing can be quite so helpful as a well placed
> comment.* It goes on to say that comments are a *necessary* evil."
>
> "If we had the perfect programming language (TM) we would never write another comment."
>
> "I prefer long names to comments. I don't trust comments to be maintained, nor do I trust
> that they will be read."

★★ **논쟁의 범위를 정확히 그어 둔다 — 이것이 이 절의 요점이다.**

| 비판 | 무엇을 겨냥하나 | 주석 장을 다루나 |
|---|---|---|
| qntm, "It's probably time to stop recommending Clean Code" ([qntm.org/clean](https://qntm.org/clean)) | ch.2·3·6·8의 예제 코드 품질, 단위테스트·포매팅·JUnit 장 | ❌ **ch.4를 단 한 번도 다루지 않는다**(전문 확인) |
| Casey Muratori, "Clean Code, Horrible Performance" | "Prefer polymorphism to if/else" 규칙 하나. 측정은 성능뿐(1.5배·35→24 사이클) | ❌ **주석과 무관** |
| **Ousterhout**, aposd-vs-clean-code | **주석 장 정면** | ✅ |
| **bugzmanov**, "Clean Code Critique" ([bugzmanov.github.io/cleancode-critique](https://bugzmanov.github.io/cleancode-critique/)) | **주석 장 정면.** 개인 블로그이며 심사 문헌 아님 | ✅ |

→ **"Clean Code의 주석 장은 논박됐다"고 쓰면 과대주장이다.** qntm·Muratori로는 주석 장을 반박할
수 없다. 실제 비판은 두 곳뿐이고 **둘 다 수사적 효과를 문제 삼는다:**

> Ousterhout: "Chapter 4 spends 4 pages talking about good comments, followed by 15 pages
> talking about bad comments. … 'Comments are always failures' is so catchy that it's the one
> thing readers are most likely to remember from the chapter."
>
> bugzmanov: "Both editions of this book are seriously lacking examples of good comments. The
> chapter about comments has a section 'Good comments' and all examples are comically bad."

한국어(Ousterhout): 4장은 좋은 주석에 4쪽, 나쁜 주석에 15쪽을 쓴다. … "주석은 늘 실패다"는
너무 귀에 붙어서 **독자가 그 장에서 기억할 가능성이 가장 높은 한 문장**이 된다.

**그리고 Martin은 프레이밍을 철회하지 않았다** — 위 응답이 그 증거다. 이 문서는 §2.1의 결론
(합의 지점은 "코드 재진술 삭제" 하나)을 유지한다.

### 2.5 ★★ 주석이 실제로 이해를 돕는가 — 측정 근거는 약하다

**이 절이 이 문서에서 가장 예상 밖의 부분이다.**

> **개정 기록 (2026-08-19, 2차 조사):** 초판은 이 분야의 고전 실험 3편을 "열지 못했다"고
> 적었다. 2차 조사에서 **Tenny 1985·Tenny 1988·Takang 1996의 전문을 확보**했고, 그 원문이
> 초판의 결론을 바꾸지 않고 **훨씬 더 강하게 만들었다.** Woodfield 1981은 여전히 초록까지만
> 열렸다. 새로 확보한 통제실험 3편(Börstler 2016·Nurvitadhi 2003·Salviulo 2014)도 아래에 넣었다.

#### 2.5.1 통제실험 9편 판정표

| 연구 | N | 피험자 | 주석 효과 | 유의성 | 판정 |
|---|---|---|---|---|---|
| Woodfield+ 1981 (ICSE) | 48 | experienced programmers | "more questions" | ⚠️ **초록에 유의성 표기 없음** | 불명 (전문 미확보) |
| Tenny 1985 (SIGCSE Bull.) | 81 | 학부 4학년 | 4.90 vs 4.12 (+18.9%) | **p<.10 — marginal** | ❌ **저자 스스로 무효 선언** |
| Tenny 1988 (TSE) | 148 | 학부 4학년 | 5.55 vs 4.76 (+16.6%) | **F(1,142)=4.34, p<.05** | ✅ **단, 무프로시저 조건에서만** |
| Takang+ 1996 (JPL) | 89 | 학부 1·2학년 | 9.40 vs 7.82 (+20.2%) | **F(1,83)=9.34, p=0.003** | ✅ **단, 객관식에서만** |
| Nurvitadhi+ 2003 (FIE) | 103 | CS1 초심자 | method ✓ / class ✗ | 초록에 값 없음 | ⚠️ 부분 |
| Salviulo+ 2014 (EASE) | 30 | 학생18+주니어12 | 식별자 > 주석 | 질적 연구 | ❌ |
| Börstler+ 2016 (TSE) | 104 | 학부 1·2학년 | Acc 0.43~0.45 전부 | **비유의** | ❌ |
| Nielebock+ 2019 (EMSE) | **277** | 전문가227+학생50 | 소규모 태스크엔 미미 | 초록에 값 없음 | ❌ |
| Abdelsalam+ 2026 (EMSE) | 20 | CS 학생 | −30% ~ +34% | **12중 1개만 유의** | ❌ 맥락의존 |

★ **1980~90년대 학생 대상 소규모 연구에서만 유의했고, 2016년 이후 연구에서는 재현되지 않았다.**
재현된 효과는 "주석이 있으면 읽기 쉬워 **보인다**"는 주관적 인지뿐이다.

#### 2.5.2 ★★ 초록과 본문이 어긋난다 — 이 분야 인용 관행의 결함

**Tenny, "Procedures and Comments vs. the Banker's Algorithm", *ACM SIGCSE Bulletin* 17(3):44–53,
1985** (DOI [10.1145/382208.382523](https://doi.org/10.1145/382208.382523), 전문 판독).
N=81, University of Oklahoma CS 4263, Pascal Banker's Algorithm 1개 × 4 editions, 2×2 요인설계.

초록은 *"the author's comments improve its readability"* 라고 쓴다. 그런데 본문은:

> "The results are tantalizing but statistically disappointing. An analysis of variance indicates
> that the main effect of comments is **marginally significant** (DF = (1,77), F = 3.64, **p < .10**)"

그리고 결론 절 첫 문장:

> "CONCLUSIONS **Statistical conclusions can not be justified at these levels of significance.**"

한국어: 이 유의수준에서는 통계적 결론을 정당화할 수 없다.

⚠️ **초록만 인용하면 원문을 왜곡한다.** 저자가 명시적으로 무효라고 선언한 결과다.

같은 결함이 Woodfield에도 있다. **Woodfield, Dunsmore & Shen, ICSE 1981, pp.215–223**
(DOI [10.5555/800078.802534](https://dl.acm.org/doi/10.5555/800078.802534)) — 전문은 끝까지
열리지 않았고 초록만 확보했다(OpenAlex `W2039603939` 보관 ACM 레코드). 그 초록 원문:

> "Those subjects whose programs contained comments **were able to answer more questions** than
> those without comments. Also, those subjects who were given the abstract data type version of the
> program were able to do **significantly better** than those with any other type of modularization."

★ **ADT 효과에는 "significantly"가 붙었지만 주석 효과에는 붙지 않았다.** 그런데 이 논문을
인용하는 현대 논문들은 유의성을 붙여 쓴다 — 예: arXiv 2409.10781이
*"including comments in the program **significantly** enhances programmers' comprehension"* 이라
쓴다. **원문이 하지 않은 말이다.** 이 저장소에서 Woodfield를 근거로 쓰지 말 것.

#### 2.5.3 유의했던 두 편 — 조건이 붙어 있다

**Tenny, "Program Readability: Procedures Versus Comments", *IEEE TSE* 14(9):1271–1279, 1988**
(DOI [10.1109/32.6171](https://doi.org/10.1109/32.6171), 전문 판독). N=148, 3×2 요인설계,
PL/I 프로그램 1개 × 6 editions, 12문항.

| edition | 조건 | N | mean (만점 12) | SD |
|---|---|---|---|---|
| 0 | inline, **주석 없음** | 23 | 4.52 | 1.81 |
| 1 | inline, **주석 있음** | 24 | **5.96** | 2.78 |
| 2 | internal proc, 없음 | 25 | 4.76 | 2.20 |
| 3 | internal proc, 있음 | 26 | 5.12 | 2.22 |
| 4 | external proc, 없음 | 27 | 4.96 | 2.71 |
| 5 | external proc, 있음 | 23 | 5.61 | 1.95 |

> "The main effect of comments is significant at the 0.05 level [F(1,142) = 4.34, p < 0.05] as is
> the simple effect of comments in the procedureless program [F(1,142) = 4.52, p < 0.05]."

저자의 결론이 조건을 명시한다:

> "But the effect of comments is significant **only in the absence of procedures**, i.e., when the
> code for the subtasks has been merged into the main program."
> "it would seem that comments have **rescued a small program which is not modular** (edition 1) and
> made it as readable as the modular editions."

한국어: 주석의 효과는 **프로시저가 없을 때만** 유의하다. 주석이 **모듈화되지 않은 작은 프로그램을
구제**해 모듈화된 판본만큼 읽히게 만든 것으로 보인다.

★ **이것이 이 문서 §2.1의 "이름·구조가 주석보다 먼저"와 정확히 같은 방향이다** — 코드가 이미
쪼개져 있으면 주석의 측정된 효과가 사라진다.

**Takang, Grubb & Macredie, "The effects of comments and identifier names on program
comprehensibility", *Journal of Programming Languages* 4(3):143–167, 1996** (DOI 없음, 전문 판독).
N=89, Modula-2 프로그램(252 LOC) 1개 × 4 versions, 2×2 무작위배정.

객관식 15문항: 주석군 M=9.40 vs 무주석군 M=7.82 → **F(1,83)=9.34, p=0.003** (유의).
그런데 **같은 실험의 주관 이해도 7점 척도에서는 F(1,76)=0.672, p=0.415** (비유의).

> "only hypothesis (i) was supported in the light of the objective test scores but only hypothesis
> (ii) was supported when the subjective scores were analysed. The discrepancy in these findings
> raises questions about the **reliability of using just a single method to measure program
> comprehension**."

저자들의 한계 진술 — 이 저장소가 그대로 인용할 만하다:

> "These results must be treated with some caution considering that the participants were **not
> professional programmers** and the experimental setting was **not typical of a 'real-world'
> programming environment**."
> "While this study has tried to test hypotheses based on the **presence** of comments and
> identifiers, **little attention has been paid to their quality**."

★ **마지막 문장이 이 문서 전체의 전제와 맞물린다** — 실증 문헌은 주석의 **유무**만 조작했고
**품질**은 조작한 적이 없다. 그러므로 §2.8 판정표는 실증이 아니라 설계 원칙에 근거해야 한다.

#### 2.5.4 ★★ 가장 강한 반증 — 느낌은 바뀌고 이해도는 안 바뀐다

**Börstler & Paech, "The Role of Method Chains and Comments in Software Readability and
Comprehension—An Experiment", *IEEE TSE* 42(9):886–898, 2016**
(DOI [10.1109/TSE.2016.2527791](https://doi.org/10.1109/TSE.2016.2527791), 전문 판독).
N=104. ★ **이 실험은 주석을 3분해한 유일한 것이다:**

> "1) **GC (good comments)**: … useful strategic comments that give additional information beyond
> the actual code it explains. 2) **BC (bad comments)**: … all source code comments replaced by
> comments that **just repeat what the code does** without explaining its purpose. 3) **NC (no
> comments)**"

즉 이 저장소 정책이 금지하는 "코드를 되풀이하는 주석"이 실제 실험 조건으로 들어갔다. 결과:

> "Regarding RQ1, there are significant differences between the comment variants (χ2 = 16.1;
> α = 0.003). Code snippets with good comments (GC) are perceived as the most readable and the
> variants without comments (NC) are perceived as the least readable. **The Acc means for the MC and
> comment variants are all between 0.43 and 0.45. All differences are insignificant.**"

> "Regarding comprehension, there are **no significant differences** between method chain or comment
> variants." (초록)

한국어: **인지된 가독성은 GC > BC > NC로 유의하게 갈렸지만(p=0.003), 실제 이해도(cloze 정확도)는
0.43~0.45에 몰려 차이가 전부 비유의했다.**

★★ **이것이 이 문서에서 가장 불편한 발견이다.** "좋은 주석"이 "코드를 되풀이하는 주석"보다
**읽기 쉬워 보이지만**, 측정된 이해도에서는 셋이 구분되지 않았다. 저자들의 결론:

> "Perceived readability might therefore be **insufficient as the sole measure** of software
> readability or comprehension."

#### 2.5.5 현대 아이트래킹 — 맥락 의존

**Abdelsalam, Peitek, Bergum, Apel, "The Effect of Comments on Program Comprehension: An
Eye-tracking Study", *Empirical Software Engineering* 31(4), article 94, 2026** (DOI
[10.1007/s10664-025-10721-2](https://doi.org/10.1007/s10664-025-10721-2), 저자 원고 판독).
N=20 학생, Java 스니펫 12개 × 2조건(주석 없음 / 주석 있음), within-subject.

> "the effect of comments on supporting program comprehension **varies significantly across
> code snippets**, ranging from a **30% decrease to a 34% increase** in performance"

한국어: 주석이 프로그램 이해를 돕는 효과는 **스니펫 간에 유의하게 갈리며**, 성능 기준으로
**30% 감소에서 34% 증가**까지 분포한다.

스니펫별 정답률(직접 판독):

| 스니펫 | 주석 없음 | 주석 있음 | 정답률 p | 시간 |
|---|---|---|---|---|
| 1 | 70% | **30%** | 0.059 | 느려짐 (p=0.002) |
| 3 | 50% | 30% | 0.211 | 느려짐 (p=0.008) |
| 5 | 50% | 70% | 0.211 | 느려짐 (p=0.017) |
| 8 | 60% | 60% | 1.000 | 빨라짐 (p<0.001) |
| **9** | 60% | **100%** | **<0.001** | 빨라짐 (p<0.001) |
| 11 | 10% | 10% | 1.000 | 빨라짐 (p=0.002) |

★ **12개 중 정답률이 유의하게 개선된 것은 1개(스니펫 9)뿐이고, 스니펫 1은 오히려 음의 경향이다.**

시선 배분: *"about 23% of visual attention has been allocated to them… 92 out of 397 fixations were
directed at comments"* — 주석이 읽히지 않아서 효과가 없는 것이 **아니다.** 읽고도 효과가 없다.

그리고 논문 자신의 결론:

> "this favorable perception did **not consistently translate into improved performance** or
> reduced perceived difficulty across snippets. This discrepancy between perceived and actual
> contribution highlights the necessity of **prioritizing quantitative metrics over subjective
> viewpoints**"

저자들이 선행 연구와의 관계를 직접 정리한다:

> "suggesting a **more nuanced effect than the uniformly positive improvements** reported by
> Dunsmore [30] and Tenny [114, 115]."

**표본이 가장 큰 연구 — 이 문서는 원문을 열지 못했다.** Nielebock, Krolikowski, Krüger, Leich,
Ortmeier, "Commenting source code: is it worth it for small programming tasks?", *EMSE* 24(3),
2019 ([10.1007/s10664-018-9664-z](https://doi.org/10.1007/s10664-018-9664-z)). **N=277**(전문가
227 + 학생 50, Wyrich 재현패키지 row S27로 구성 확인), 주로 실무 개발자. 초록 원문:

> "Our results indicate that comments seem to be **considered more important in previous studies and
> by our participants than they are for small programming tasks.** While other mechanisms, such as
> **proper identifiers, are considered more helpful** by our participants, they also emphasize the
> necessity of comments in certain situations."

⚠️ **Springer 페이월로 본문 수치는 확보하지 못했다**(§12). 초록 방향만 위 판정표에 반영했다.

#### 2.5.6 이 문헌 전체의 한계 — 인용 시 반드시 함께 적을 것

| 한계 | 구체 증거 |
|---|---|
| **낡았다** | 핵심 4편이 1981·1985·1988·1996. Wyrich: *"Studies using older languages like Fortran, Cobol, Pascal, Algol, Basic, PL/I, or Modula-2 were all published before 2000, with a median year of 1987."* Tenny 1985/1988·Takang은 **종이 인쇄물**로 코드를 제시했다 |
| **N이 작다** | Tenny 1985 N=81(셀 20), Takang N=89(셀 21~24), Abdelsalam N=**20**(조건당 10명). Wyrich: 95편 **median N=34**. 예외는 Nielebock N=277뿐 |
| **학생 표본** | Woodfield만 "experienced programmers". 나머지는 전원 학부생 또는 CS1 초심자. Wyrich: *"About half of the 95 papers (**53.7%**) reported a sample that consisted entirely of students. For nine papers (9.5%), only professionals were included."* |
| **프로그램 1개** | Tenny 1985/1988·Takang·Nurvitadhi 모두 **단일 프로그램의 변형**만 비교했다. Abdelsalam만 12개 스니펫이고, 그래서 효과가 갈린다는 것을 발견할 수 있었다 |
| **태스크가 비현실적** | Tenny: 50분 수업시간 단답 12문항(*"Superficially the questions resemble an hour exam."*). Takang: 5지선다 15문항. Abdelsalam: "출력값을 적으시오". Börstler: cloze test. **유지보수·디버깅을 측정한 것이 하나도 없다** |
| **효과크기 미보고** | Woodfield·Tenny 1985·Tenny 1988·Takang·Börstler **다섯 편 전부** 표준화 효과크기를 보고하지 않는다(F/χ²/p만). 2026년 Abdelsalam조차 Cohen's d 없이 %차이만 준다. ⚠️ 위 표의 상대% 값은 **보고된 평균에서 역산한 파생치**이며 논문에 없다 |
| **무작위배정 아님** | Tenny 1985·1988 모두 GPA+선수과목 성적 순위로 층화 배정했다. Tenny 본인이 검정력을 깎았다고 인정한다: *"part of the scatter within each cell was systematically introduced by the method of cell construction"* |
| **측정 도구가 결론을 뒤집는다** | Takang: 객관식 p=0.003 유의 / 주관 점수 p=0.415 비유의. Börstler: 인지 가독성 p=0.003 유의 / cloze 정확도 비유의. **"주석이 도움된다"가 측정 도구의 함수다** |
| **품질을 조작한 실험이 하나뿐** | Börstler 2016의 GC/BC/NC만 주석 **품질**을 조작했고, 그 실험이 **이해도 차이를 찾지 못했다.** 나머지 전부 유/무만 비교했다 |

**→ 이 절이 §11 판정 7("Minimal by default")에 주는 결론:** "최소로 유지한다"는 정책은
**출처 있는 규칙은 아니지만, 측정 근거가 반대편보다 오히려 조금 낫다.** 어느 쪽도 강하지 않다.
**그러므로 밀도 논쟁에 시간을 쓰지 말고 §2.8 판정표의 내용 기준만 적용하는 것이 합리적이다** —
어느 실증도 "몇 %가 맞다"를 지지하지 않기 때문이다.

★★ **그리고 §2.5.4가 판정 3("코드를 되풀이하는 주석 금지")에 주는 단서:** 그 규칙은 PEP 8·Google·
Ousterhout에 **출처가 있지만**, 유일하게 그것을 측정한 실험(Börstler)은 **되풀이하는 주석과 좋은
주석 사이에 이해도 차이를 찾지 못했다.** 규칙을 폐기할 근거는 아니다 — cloze test가 그 차이를
잴 수 있는 도구인지부터 의심스럽고, 저자들도 측정 타당성을 문제 삼는다. 다만 **"되풀이 주석이
해롭다"를 실증으로 주장할 수는 없다.** 근거는 설계 원칙(중복은 낡는다·§6.4)이지 실험이 아니다.
### 2.6 ⚠️ "why not what"은 보편 합의가 아니다

이 저장소 정책 첫 문장이 "Comment the *why*, not the *what*"이다. **세 출처가 갈린다:**

| 출처 | 규정 |
|---|---|
| **Linux kernel coding style** ([kernel.org … coding-style.html](https://www.kernel.org/doc/html/latest/process/coding-style.html) §8) | *"NEVER try to explain HOW your code works in a comment … Generally, you want your comments to tell **WHAT** your code does, not HOW."* |
| **Ousterhout** §13.6 (검증된 절 제목) | *"Implementation comments: **what and why**, not how"* |
| **Google** §3.8.5 | *"never describe the code"* — WHAT을 서술하지 말라 |

한국어(커널): 코드가 **어떻게(HOW)** 동작하는지를 주석으로 설명하려 하지 말 것 — 동작이 자명하게
드러나도록 코드를 쓰는 편이 훨씬 낫다. 일반적으로 주석은 코드가 **무엇을 하는지(WHAT)** 를
말하게 하고, 어떻게 하는지는 말하지 않게 하라.

→ **세 출처가 "what"의 위치에 관해 서로 다르다.** 커널은 WHAT을 요구하고, Google은 금지하고,
Ousterhout는 WHAT과 WHY를 함께 요구하며 HOW만 뺀다. **공통분모는 "HOW를 쓰지 않는다"뿐이다.**

★ **판정: 정책의 "why, not what"은 세 출처 중 어느 하나를 그대로 따른 것이 아니다.**
Google에 가장 가깝다. 정책을 유지하되 **"HOW는 어디에서도 지지받지 않는다"를 추가**하는 것이
1차 출처를 가장 정확히 반영한다(§11 판정 6).

### 2.7 Knuth — 문학적 프로그래밍은 채택되지 않았다

Knuth, "Literate Programming", *The Computer Journal* 27(2):97–111, 1984
(DOI [10.1093/comjnl/27.2.97](https://doi.org/10.1093/comjnl/27.2.97); 게재본은 유료라
`literateprogramming.com/knuthweb.pdf`의 **투고 원고 재조판본**을 판독했다):

> "Let us change our traditional attitude to the construction of programs: Instead of imagining
> that our main task is to instruct a computer what to do, let us concentrate rather on
> explaining to human beings what we want a computer to do."

한국어: 프로그램 작성에 대한 전통적 태도를 바꾸자 — 우리 주된 과업이 컴퓨터에게 무엇을 하라고
지시하는 것이라 상상하는 대신, **사람에게 우리가 컴퓨터로 무엇을 하려는지 설명하는 데** 집중하자.

**Knuth 본인이 미채택을 인정한다** (Binstock 인터뷰, InformIT 2008-04-25; 미러 PDF 판독):

> "Literate programming is a very personal thing. I think it's terrific, but that might well be
> because I'm a very strange person. **It has tens of thousands of fans, but not millions.**"
>
> "Jon Bentley probably hit the nail on the head … a small percentage of the world's population
> is good at programming, and a small percentage is good at writing; apparently I am asking
> everybody to be in both subsets."

한국어: 문학적 프로그래밍은 매우 개인적인 것이다. 나는 훌륭하다고 생각하지만 내가 아주 특이한
사람이기 때문일 수도 있다. **수만 명의 팬은 있지만 수백만은 아니다.** … Bentley가 정곡을 찔렀다 —
프로그래밍을 잘하는 사람도 소수, 글쓰기를 잘하는 사람도 소수인데 **나는 모두가 두 부분집합에
다 들어가라고 요구하는 셈**이다.

→ **이 저장소에 옮길 것은 방법론이 아니라 논거 하나다: 문서의 독자는 컴퓨터가 아니라 사람이다.**
그리고 **Bentley의 진단이 §9.3의 언어 문제와 정확히 겹친다** — 비모국어로 쓰면 "글쓰기를 잘하는
소수"에 들기가 한 단계 더 어려워진다.

### 2.8 판정표 — 주석 한 줄에 기계적으로 적용한다

위에서 아래로 읽고 **처음 걸리는 행에서 멈춘다.**

| # | 물음 | YES면 | 근거 |
|---|---|---|---|
| 1 | 주석 처리된 **실행 가능 코드**인가? | **지운다.** git이 기억한다 | Ruff `ERA001`: *"Commented-out code is dead code … It should be removed."* · *Clean Code* bad comments `Commented-Out Code` |
| 2 | 주석이 **코드와 모순**하는가? | **지운다 또는 고친다.** 판단 유보 금지 | PEP 8: *"worse than no comments"* |
| 3 | 코드 한 줄을 **자연어로 번역**한 것인가? | **지운다** | PEP 8 `# Increment x` 반례 · Google *"never describe the code"* · Ousterhout §13.2 |
| 4 | 코드가 **어떻게(HOW)** 동작하는지 설명하는가? | **지운다.** 세 출처 중 **어느 것도 지지하지 않는다** | Linux kernel *"NEVER try to explain HOW"* · Ousterhout §13.6 |
| 5 | **타입 힌트가 이미 말하는 것**인가? (`x (int):`) | **지운다.** 타입으로 옮긴다 | PEP 484 기각 대안 · Google *"if the code does not contain a corresponding type annotation"* |
| 6 | **코드로 표현할 수 있는가?** (`Literal`·`Enum`·상수 이름·함수 분리) | **코드로 옮기고 지운다** | Google §3.8.4 *"should not repeat unnecessary information"* |
| 7 | **단위·범위·부호 규약**인가? | **남긴다.** 타입이 표현하지 못한다 | Ousterhout CS190: *"What are the units?"* (본인 문장) · PEP 257 |
| 8 | **모듈 경계를 넘는 불변식**인가? | **남긴다.** 어느 한쪽 코드에도 담기지 않는다 | Ousterhout: *"there is no way to specify this 'contract' in code"* · CS190 `Invariants?` |
| 9 | **발생 예외**인가? | **`Raises:`에 남긴다** | PEP 484: 예외 나열 문법을 만들지 않고 **docstring에 위임** |
| 10 | **왜 이렇게 안 했는가**(기각된 대안·워크어라운드·실측 반증)인가? | **남긴다** | Ousterhout CS190: *"Rationale for the current design: why the code is this way"* · Google *"tricky parts"* |
| 11 | **외부 문서를 요약**한 것인가? | **§7.5의 절차로.** 요약을 지우고 **해소 가능한 포인터** 하나만 | Ousterhout: *"Document each thing exactly once"* · SWE at Google: *"designate canonical documentation"* · *Clean Code* `Nonlocal Information` |
| 12 | 위 어디에도 안 걸리는가? | **남긴다.** 확신 없이 지우지 않는다 | PEP 8 *"When in doubt, use your best judgment"* |

**행 5·6이 이 저장소에서 가장 많이 발화한다.** 구체적 예:
[`src/execution/interface.py`](../../src/execution/interface.py) `:13`의

```python
    side: str            # "BUY" | "SELL"
```

는 **행 5·6에 동시에 걸린다** — `Literal["BUY", "SELL"]`로 쓰면 주석이 필요 없고 타입 검사기가
검증한다. 같은 파일 `:14`의 `kind: str  # "amount"(...) | "quantity"(...)`도 같다.

---

## 3. docstring 규약 — 기준선 하나와 방언 셋

### 3.1 방언은 표준이 아니다 (1차 출처로 확정)

PEP 727 "Documentation in Annotated Metadata"는 **`Status: Withdrawn`** 이다. 그런데 이 PEP의
Motivation이 현 상황을 가장 정확히 기술한다
([peps.python.org/pep-0727](https://peps.python.org/pep-0727/)):

> "Currently there is no formalized standard to provide documentation strings for other types
> of symbols: parameters, return values, class-scoped variables …
>
> Nevertheless, to allow documenting most of these additional symbols, several conventions have
> been created as microsyntaxes inside of docstrings, and are currently commonly used: Sphinx,
> numpydoc, Google, Keras, etc."

한국어: 현재 **파라미터·반환값·클래스 스코프 변수**에 문서 문자열을 제공하는 **형식화된 표준은
없다.** 그럼에도 이들을 문서화하기 위해 **docstring 내부의 microsyntax로** 여러 규약이 만들어졌고
널리 쓰인다 — Sphinx, numpydoc, Google, Keras 등.

그리고 이 PEP는 기각됐다:

> "The reception of this PEP was mostly negative, with concerns raised about **verbosity and
> readability**. As a result, this PEP has been withdrawn."

→ **표준화 시도가 있었고 "장황하다"는 이유로 기각됐다.** §3.3의 결론을 보강한다.

### 3.2 세 방언이 실제로 규정하는 것

| | Google | NumPy (numpydoc) | Sphinx / reST |
|---|---|---|---|
| 1차 출처 | [pyguide.html](https://google.github.io/styleguide/pyguide.html) §3.8 | [numpydoc … format.html](https://numpydoc.readthedocs.io/en/latest/format.html) | [sphinx-doc … domains/python.html](https://www.sphinx-doc.org/en/master/usage/domains/python.html) |
| 인자 표기 | `Args:` + `name: description`, 2 또는 4칸 hanging indent | `Parameters` + `----------` + `x : type` | `:param x:` / `:type x:` (또는 `:param int x:` 축약) |
| **타입 필수?** | **아니오** — *"if the code does not contain a corresponding type annotation"* | **반환값은 필수** — *"The type of each return value is always required."* | 필드 존재, 필수 여부 규정 없음 |
| 반환값 | `Returns:` — None만 반환하면 생략. `"Return(s)/Yield(s)"`로 시작하고 충분하면 생략 가능 | `Returns` — 이름 optional, **타입 항상 필수** | `:returns:` / `:rtype:` |
| 예외 | `Raises:` — *"You should not document exceptions that get raised if the API specified in the docstring is violated"* | `Raises` | `:raises X:` |
| 절 순서 | 규정 있음 | **15절 정규 순서 규정** | 규정 없음 |
| 도구 | Ruff `D`(google), pydoclint, napoleon | Ruff `D`(numpy), numpydoc validation | Sphinx 네이티브 |

★ **numpydoc의 *"The type of each return value is always required"* 는 타입 힌트와 정면 중복이며,
numpydoc 문서에는 PEP 484 애노테이션과의 관계를 정리한 문장이 없다**(직접 확인).
**numpy 스타일을 고르면 중복을 규약으로 받아들이는 것이다.**

그리고 Google은 numpy 스타일의 특정 관행을 **명시적으로 금지**한다:

> "Do not imitate older 'NumPy style', which frequently documented a tuple return value as if
> it were multiple return values with individual names (never mentioning the tuple)."

### 3.3 타입 힌트가 무엇을 몰아냈는가 — 3단 논증, 전부 1차 출처

**단계 1 — PEP 3107(Final)의 집필 동기가 애초에 docstring 타입 파싱의 대체였다**
([peps.python.org/pep-3107](https://peps.python.org/pep-3107/)):

> "Because Python's 2.x series lacks a standard way of annotating a function's parameters and
> return values, a variety of tools and libraries have appeared to fill this gap. Some utilise
> the decorators introduced in PEP 318, while others **parse a function's docstring, looking for
> annotations there.** This PEP aims to provide a single, standard way of specifying this
> information, reducing the confusion caused by the wide variation in mechanism and syntax."

**단계 2 — PEP 484가 docstring을 대안으로 검토하고 명시적으로 기각했다**
([peps.python.org/pep-0484](https://peps.python.org/pep-0484/), Rejected alternatives):

> "* Docstrings. There is an existing convention for docstrings, based on the Sphinx notation
> (`:type arg1: description`). This is **pretty verbose** (an extra line per parameter), and
> **not very elegant**. We could also make up something new, but the annotation syntax is hard
> to beat (**because it was designed for this very purpose**)."

한국어: **docstring.** Sphinx 표기에 기반한 기존 규약이 있다. 이는 **상당히 장황하고**(파라미터당
한 줄 추가) 별로 우아하지 않다. 새로 만들 수도 있지만 **애노테이션 문법을 이기기 어렵다** —
바로 이 목적으로 설계됐기 때문이다.

**단계 3 — Google이 이를 실행 규칙으로 옮겼다** (§3.8.3):

> Args: "The description should include required type(s) **if the code does not contain a
> corresponding type annotation.**"
>
> Returns: "Describe the semantics of the return value, including any type information **that
> the type annotation does not provide.**"

**결론: 타입 힌트가 있는 코드에서 `Args: x (int): …`는 출처 있는 안티패턴이다.** 근거는 세 겹 —
PEP 3107의 집필 동기, PEP 484의 명시적 기각, Google의 조건절.

**반대 방향도 같은 강도로 성립한다.** PEP 484 "Exceptions":

> "No syntax for listing explicitly raised exceptions is proposed. Currently the only known use
> case for this feature is documentational, in which case **the recommendation is to put this
> information in a docstring.**"

→ **타입 시스템이 의도적으로 비워 둔 칸이 `Raises:`다.**

★ 이 저장소는 이미 그렇게 하고 있다.
[`scripts/model_backtest/_common.py`](../../scripts/model_backtest/_common.py)의
`best_valid_mse`는 `Args:` · `Returns:` · `Raises:`를 쓰면서 **타입을 하나도 적지 않는다.**
Google §3.8.3을 이미 만족한다. **§11의 정책 문장보다 코드가 더 정확하다.**

**기계로 강제할 수도 있다.** `pydoclint`에 정확히 이 규칙이 있다
([jsh9.github.io/pydoclint](https://jsh9.github.io/pydoclint/)):

> `--arg-type-hints-in-docstring` (default: `True`) — "If `False`, there cannot be any type
> hints in the argument list of a docstring"
>
> "Note: if users choose `True` for both options, the argument type hints in the signature and
> in the docstring need to match, otherwise there will be a style violation."

→ 위반 코드가 **`DOC111`**("The option `--arg-type-hints-in-docstring` is `False` but there are
type hints in the docstring arg list")이다. **§3.3의 결론을 린터로 강제하는 유일한 경로다.**
⚠️ 단 **기본값이 `True`** 이므로, 아무 설정 없이 pydoclint를 켜면 **중복을 요구하게 된다.**
그리고 Ruff의 `DOC` 계열에는 이 규칙이 없다(§5.2).

### 3.4 `lint.pydocstyle.convention`이 실제로 끄는 규칙 (Ruff 소스에서 직접)

**`crates/ruff_linter/src/rules/pydocstyle/settings.rs`의 `Convention::rules_to_be_ignored()`**
매치문을 읽고 `codes.rs`로 코드 번호를 맞춘 것이다. **요약 도구가 이 표를 물었을 때 존재하지
않는 코드를 반환했으므로 소스가 유일한 근거다.**

| convention | 자동으로 꺼지는 규칙 |
|---|---|
| `"google"` | D203, D204, D213, D215, D400, **D401**, D404, D406, D407, D408, D409, D413 |
| `"numpy"` | **D107**, D203, D212, D213, D402, D413, D415, D416, **D417** |
| `"pep257"` | D203, D212, D213, D214, D215, D404, D405, D406, D407, D408, D409, D410, D411, D413, D415, D416, **D417**, D420 |

읽어야 할 두 줄:

- **`pep257`과 `numpy`는 `D417`(undocumented-param)을 끈다.** `pep257`이 끄는 것은 정합적이다 —
  §1.4에서 봤듯 **PEP 257에는 `Args:` 문법이 없으므로** 인자 문서화를 강제할 근거가 없다.
- **`google`은 `D401`(non-imperative-mood)을 끈다.** Google이 서술형·명령형 둘 다 허용하기
  때문이다. PEP 257은 명령형을 규정하므로 여기서 두 출처가 갈린다.

→ **이 저장소는 `convention = "google"`을 쓴다**(§5.5). 한글 docstring에서 `D401`은 사실상
작동하지 않으므로(§5.3) 어차피 의미가 없고, `google`을 고르면 그 규칙이 **설정 한 줄 없이
자동으로 꺼진다.**

---

## 4. public vs private — "공개 API만"의 출처와 그 한계

### 4.1 PEP 8·PEP 257이 실제로 말하는 것

PEP 8 "Documentation Strings":

> "Write docstrings for all public modules, functions, classes, and methods. **Docstrings are
> not necessary for non-public methods, but you should have a comment that describes what the
> method does. This comment should appear after the `def` line.**"

한국어: 모든 **public** 모듈·함수·클래스·메서드에 docstring을 쓴다. **non-public 메서드에는
docstring이 필요하지 않지만, 그 메서드가 무엇을 하는지 서술하는 주석은 있어야 한다.**

★★ **"public API만"의 출처는 확실히 있다. 그런데 흔히 인용되는 절반이 잘려 있다.**
PEP 8은 private에 대해 "면제"가 아니라 **"docstring 대신 주석"** 을 요구한다.
정책의 "private is optional"은 그 조건절을 떨어뜨렸다(§11 판정 2).

PEP 8은 "public"이 무엇인지도 규정한다("Public and Internal Interfaces"):

> "Documented interfaces are considered public … All undocumented interfaces should be assumed
> to be internal."
>
> "To better support introspection, modules should explicitly declare the names in their public
> API using the `__all__` attribute."

→ **순환이 있다.** "public이면 문서화하라"와 "문서화되면 public이다"가 맞물린다. PEP 8이 제시하는
탈출구는 `__all__`이다. **이 저장소에는 `__all__`이 없으므로**(확인함) **"public"의 유일한 운영
정의는 밑줄 접두사**이며, 그것이 정확히 Ruff `D1xx`와 `interrogate`가 쓰는 정의다.

### 4.2 Google은 기준을 셋으로 넓힌다

> "**A docstring is mandatory for every function that has one or more of the following
> properties:** being part of the public API / nontrivial size / non-obvious logic"

→ **"public만"보다 넓다.** private이지만 크고 까다로운 함수는 Google 기준에서 필수다.
그리고 Google은 반대 방향으로도 자른다(§3.8.2.1):

> "Module-level docstrings for test files are not required. …
> **Docstrings that do not provide any new information should not be used.**
> `"""Tests for foo.bar."""`"

§3.8.4에서 형식적 docstring을 직접 반례로 든다 — `"""Raised when no more cheese is
available."""`가 **No**이고 `"""No more cheese is available."""`가 **Yes**다.
*"The class docstring should not repeat unnecessary information, such as that the class is a
class."*

**요컨대 Google은 "커버리지 100%"를 요구하지 않는다. 정보 없는 docstring을 명시적으로 금지한다.**
`interrogate --fail-under 100`은 이 지침과 충돌한다.

**Google에는 면제 조항이 하나 더 있다**(§3.8.3.1): `@override`로 명시 데코레이트된 오버라이드
메서드는 docstring이 필요 없다 — *"unless the overriding method's behavior materially refines the
base method's contract."*

### 4.3 실제 프로젝트는 무엇을 켜는가 (설정 파일 직접 확인)

| 프로젝트 | 설정 파일 | `D` | convention | `ERA` | `TD`/`FIX` | `DOC` | 주목할 점 |
|---|---|---|---|---|---|---|---|
| **Ruff** 자신 | `pyproject.toml` | ✗ | — | ✗ | ✗ | ✗ | `E501` 무력화: *"Leave it to the formatter to split long lines and the judgement of all of us."* |
| **pandas** | `pyproject.toml` | ✗ | — | ✗ | ✗ | ✗ | `E`,`W` 선택 + `line-length = 88` |
| **CPython** | `.ruff.toml` (root) | ✗ | — | ✗ | ✗ | ✗ | `line-length = 79` 위에 주석 `# PEP 8` 한 줄. 루트에 `select` 없음 |
| **pydantic** | `pyproject.toml` | **✓** | `google` | ✗ | ✗ | ✗ | `ignore = ['D105','D107','D205','D415','E501',…]`; **`'tests/*' = ['D',…]`**, `'docs/*' = ['D']` |
| **polars** | `py-polars/pyproject.toml` | **✓** (+`D417`) | `numpy` | ✗ | **✓** | ✗ | **`max-doc-length = 88`**; `E501` 무력화(*"Line length regulated by formatter"*); `ignore` = `D100,D104,D105,D401,TD002,TD003`; `tests/**` → `D100,D102,D103` 면제 |
| **Home Assistant** | `pyproject.toml` | **✓** | `google` | ✗ | ✗ | ✗ | `E501` 무력화 |
| scikit-learn · mypy · black · pip · FastAPI · Sphinx | 각 `pyproject.toml` | ✗ | — | ✗ | ✗ | ✗ | 주석·docstring 계열 전무. `line-length`만 |

읽어야 할 네 줄:

1. **조사한 10개 프로젝트 중 `ERA001`을 켜는 곳은 0개다.** 문서화된 오탐 위험(§5.2) 때문으로
   보이지만 **어느 프로젝트도 그 이유를 설정 파일에 적지 않았으므로 이는 추정이다.**
2. **`D`를 켜면서 `tests`를 명시 면제하는 곳이 둘 있다**(pydantic·polars). Google §3.8.2.1과
   일치한다. (Home Assistant의 `per-file-ignores` 전문은 확인하지 않았다 — §12.)
3. **`E501`은 켜는 곳보다 끄는 곳이 많다** — 포매터가 처리하니까. 반면 **polars는 `E501`을 끄고
   `max-doc-length`는 켠다.** 코드 줄 길이는 포매터에, **주석 줄 길이는 린터에** 맡기는 구분이며,
   이 저장소에 그대로 이식할 수 있는 유일한 선례다.
4. **`DOC`(pydoclint)를 켜는 곳은 0개다.** Ruff에서 preview 상태(§5.2)라 당연하다.

**→ "고신뢰 프로젝트가 하는 대로"를 근거로 삼으면 결론은 "거의 아무것도 켜지 마라"가 된다.**
이 문서는 그 결론을 그대로 받지 않는다 — 이 저장소는 라이브 발주 코드를 담고 있고 §7의 링크
부패가 **이미 5건 발생했다.** 다만 **권고를 "업계 표준"이라 부르지 않는다.** polars가 가장 가까운
선례다.

---

## 5. 기계로 검사되는 것 — 실측

### 5.1 이 저장소의 출발점 (직접 계산, 검증됨)

| 항목 | 값 | 확인 방법 |
|---|---|---|
| `#` 주석 줄 / 전체 줄 — `src/` | **91 / 1583 (5.7%)** | `grep -h -E '^\s*#'` + `wc -l` |
| 같은 것 — `scripts/` | **164 / 5488 (3.0%)** | 같음 |
| 같은 것 — `tests/` | **114 / 2480 (4.6%)** | 같음 |
| `.py` 파일 수 | 77 | `find` |
| module docstring 누락 | **0 / 77** | `ast.get_docstring` |
| `def`/`class` 총수 / docstring 누락 | 514 / **317** | `ast.walk` |
| `interrogate` 커버리지 | **46.4%** (591 노드 중 274) — 기본 기준선 80% **FAILED** | `interrogate -v src scripts tests` |
| 주석 안 마크다운 강조 | **16건** (제시된 19건이 아니다) | `grep -rn -E '#[^"'"'"']*\*\*'` |
| 주석 안 `★`/`⚠️` | **6건** (일치) | `grep -rn -E '#.*(★\|⚠️)'` |
| 주석 안 ASCII 구분선 | **8건** | `grep -rn -E '^\s*#\s*-{6,}\|^\s*#\s*={6,}'` |
| TODO/FIXME/XXX/HACK | **0건** | `grep -rn -E '#.*(TODO\|FIXME\|XXX\|HACK)'` |
| `# noqa` 지시 | **약 50건** | §5.4 |
| `개선N` ID 참조 | **35건 / 13개 파일** | §7.4 |
| 린트 설정 파일 | **없음** (`pyproject.toml`·`setup.cfg`·`tox.ini`·`.flake8`·`ruff.toml` 전부 부재) | `ls` |
| `.venv`의 린터 | **없음** (ruff·flake8·pylint·black·pydocstyle·interrogate·vulture 전무) | `ls .venv/bin` |
| 최장 줄 | 154자. `>79`: 1921/9551 · `>88`: 1474 · `>99`: 991 | `awk length` |

⚠️ **제시된 수치 중 하나를 정정한다** — 마크다운 강조는 **19건이 아니라 16건**이다.
`src/scripts/tests`의 `.py`에서 `#` 뒤에 `**`가 오는 줄(인라인 포함)을 센 값이다.
19를 재현하는 조합을 찾지 못했다(`docs/`나 `.md`를 포함하면 훨씬 커진다).

### 5.2 규칙별 실측 — ruff 0.16.3을 직접 돌렸다

**모든 규칙 코드는 `codes.rs` 원본과 대조해 존재를 확인했다.**

| 규칙 | 이름 | 이 저장소 검출 | 상태 | 비고 |
|---|---|---|---|---|
| `ERA001` | commented-out-code | **0** | stable | §5.4 |
| `D` (전체, `pep257`) | pydocstyle | **273** | stable | D103 170 · D102 34 · D205 13 · D400 12 · D107 11 · D209 11 · D403 11 · D101 9 · D401 2 |
| `D` (전체, `google`) | 같음 | **286** | stable | D415 12 · D410 7 · D411 7 · D417 1 이 추가되고 D400/D401 이 빠진다 |
| `D1` 만, 디렉터리별 | 누락 docstring | `src` **32** · `scripts` **60** · `tests` **132** | stable | tests가 절반을 넘는다 |
| `D209` | new-line-after-last-paragraph | **11** | stable, **자동수정** | PEP 8이 *"most importantly"* 라고 명시한 항목 |
| `D403` | first-word-uncapitalized | **11** | stable, 자동수정 | ★ **11건 전부 오탐** — §5.3 |
| `D401` | non-imperative-mood | **2** | stable | ★ 한글에 사실상 무력 — §5.3 |
| `W505` | doc-line-too-long | **817**(@72) / **2**(@100) | stable(v0.0.219~) | `max-doc-length` **미설정 시 선택해도 무시된다** |
| `E501` | line-too-long | **122**(@100) | stable | 코드 줄. 포매터 영역 |
| `TD001`–`TD007` | flake8-todos | **0** | stable | TODO가 하나도 없다 |
| `FIX001`–`FIX004` | flake8-fixme | **0** | stable | 같음 |
| `DOC102/201/202/402/403/501/502` | pydoclint (Ruff 구현) | **110** (DOC201 89 · DOC501 19 · DOC402 1 · DOC502 1) | **preview** | `--preview` 없으면 *"Selection `DOC501` has no effect because preview is not enabled."* |
| `RUF002`/`RUF003` | ambiguous-unicode | 18 / **9** | stable | ★ 9건 전부 오탐 — §5.3 |
| `RUF100` | unused-noqa | **50** | stable | §5.4 |
| `CPY001` | missing-copyright-notice | (미실행) | preview | 이 저장소에 라이선스 헤더 정책이 없다 |

★ **Ruff의 `DOC` 계열은 pydoclint의 부분집합이며 번호 대응이 완전하지 않다.**
`codes.rs`에 **`DOC101`이 없다**(직접 확인). pydoclint의 `DOC101`(인자 누락)에 해당하는 일은
Ruff에서 **`D417`**이 한다. 그리고 §3.3의 핵심 규칙 **`DOC111`(docstring에 타입 금지)은 Ruff에
없다** — pydoclint를 별도로 돌려야 한다.

`ERA001`의 문서화된 한계
([docs.astral.sh/ruff/rules/commented-out-code](https://docs.astral.sh/ruff/rules/commented-out-code/)):

> **Known problems:** "Prone to false positives when checking comments that resemble Python
> code, but are not actually Python code."

`W505`의 문서화된 전제조건
([docs.astral.sh/ruff/rules/doc-line-too-long](https://docs.astral.sh/ruff/rules/doc-line-too-long/)):

> "(**If no value is provided, this rule will be ignored, even if it's added to your `--select`
> list.**)"

그리고 `W505`는 실용적 예외 셋을 둔다 — 공백 없는 단일 "단어", 임계 전에 시작하는 **URL로 끝나는
줄**, 임계 전에 시작하는 **pragma 주석**(`# type: ignore`·`# noqa`)으로 끝나는 줄.
→ **§7의 문서 URL 참조는 `W505`에 걸리지 않는다.** 유용한 설계다.

### 5.3 ★★ 한글 주석에서 조용히 무력해지거나 거꾸로 작동하는 규칙 — 3종

이것이 이 저장소에 고유한 발견이다.

**(1) `D403`은 11건 전부 오탐이며, 자동수정이 PEP 8을 어긴다.**

```
scripts/model_backtest/_common.py:22:5: D403 First word of the docstring should be capitalized: `config` -> `Config`
src/toss/broker.py:128:9:              D403 ... `holdings` -> `Holdings`
scripts/data_pipeline/measure_power.py:32:5: D403 ... `winsor` -> `Winsor`
```

11건의 첫 단어는 `artifacts` `symbol` `concept` `symbol` `winsor` `config` `valid` `kill`
`holdings` `prices` `symbol` — **전부 식별자 또는 도메인 용어**다. PEP 8은 바로 이 경우를 예외로
둔다: *"unless it is an identifier that begins with a lower case letter (**never alter the case of
identifiers!**)"*

→ `ruff --fix`로 `D403`을 고치면 `holdings` → `Holdings`가 되어 **PEP 8이 괄호까지 쳐서 금지한
일**을 하게 된다. **반드시 `ignore`에 넣는다.**

**(2) `D401`(명령형)은 한글 docstring에서 사실상 발화하지 않는다 — 273건 중 2건.**

발화한 2건은 첫 단어가 영어(`valid`, `holdings`)인 경우뿐이다. 이 규칙은 **한글 docstring을
검사하지 않고 조용히 통과시킨다.** PEP 257의 명령형 요구는 이 저장소에서 **기계로 강제 불가**다.

**(3) `RUF003`(주석의 모호한 유니코드)은 9건 전부 오탐이다.**

```
src/execution/interface.py:60:16: RUF003 Comment contains ambiguous `−` (MINUS SIGN). Did you mean `-`?
src/execution/interface.py:89:48: RUF003 Comment contains ambiguous `∪` (UNION). Did you mean `U`?
scripts/model_backtest/_common.py:44:40: RUF003 Comment contains ambiguous `×` (MULTIPLICATION SIGN). Did you mean `x`?
```

`−`(체결가 − 결정가) · `∪`(target ∪ holdings) · `×`(3.46² / 12) 는 모두 **의도된 수학 표기**다.
이 규칙의 목적은 homoglyph 혼동 방지이며, 수식을 유니코드로 적는 저장소에서는 100% 오탐이 된다.

**세 사례의 공통 교훈: 린터의 "주석 내용" 규칙은 대부분 영어를 가정한다. 검출 수가 0에 가깝다는
것이 "통과"가 아니라 "검사되지 않았다"일 수 있다.** §6.1의 핵심 논지다.

### 5.4 ★ `ERA001`은 0건이고, `# noqa` 50개는 존재하지 않는 린터를 향한다

**`ERA001` 검출 0건** — `All checks passed!` 이다. 정책의 "No commented-out dead code" 조항은
**이미 지켜지고 있다.**

문서화된 오탐 위험이 이 저장소 문체에서 실제로 발생하는지 직접 시험했다:

```python
# group_by="ticker"면 종목이 1개여도 컬럼이 MultiIndex다(yfinance 1.5.1).
# sign=False(기본)는 sqrt(|s2|)라 음수가 지워져 합격선 판정이 무의미해진다
# rebalance_band = 0.10 이 정책 기본값이다
# return None 이면 미체결이라는 뜻이다
# self.cache_path.unlink(missing_ok=True) 를 호출하는 이유는 아래에 적었다
# x = compute(1, 2)
# print("debug")
# import os
```

**결과: 뒤 3줄만 검출, 한글 5줄은 0건.** 한글 조사(`~면`·`~이다`·`~를`)가 파스를 깨기 때문에
eradicate 휴리스틱이 코드로 인정하지 않는다. → **이 저장소 주석 문체에서 `ERA001`의 오탐 위험은
실측상 발현하지 않는다.** (일반적 위험이 없다는 뜻은 아니다.)

★★ **그런데 `RUF100`이 50건을 잡았다.** 이 저장소에는 `# noqa: E402` · `# noqa: BLE001` ·
`# noqa: F401` 지시가 약 50개 있다:

```
src/toss/client.py:15: from .errors import TossApiError, TossConfigError  # noqa: F401  (TossApiError re-export: 기존 import 호환)
src/execution/runner.py:196: except Exception as exc:  # noqa: BLE001 — 조회 실패가 발주 기록을 날리면 안 된다
scripts/data_pipeline/fetch_candidate_closes.py:21: import pandas as pd  # noqa: E402
```

**린터가 설정된 적이 없으므로 이 50개는 아무것도 억제하지 않는다.** 형식은 기계 판독형이지만
실질은 사람에게 남긴 메모이며, **아무도 그 주장을 검증한 적이 없다.**

→ **실무적 귀결:** `RUF100`을 켜려면 `F401`·`E402`·`BLE001`도 함께 켜야 한다. 그러지 않으면
"억제할 규칙이 없다"는 이유로 50건 전부가 오탐처럼 뜬다(실측 확인). §5.5의 권고 설정은 `RUF100`을
**뺀다** — 주석 규율 범위를 넘기 때문이다. 이 50개를 **§12의 미해결 항목**으로 남긴다.

### 5.5 권고 설정 — 이 저장소용, 실행 검증됨

이 저장소에는 `pyproject.toml`이 없으므로 **새로 만드는 것이다.** 아래 블록은 그대로 붙여 쓸 수
있고, **실제로 돌려 검출 수를 확인했다**(ruff 0.16.3).

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = ["vendor", ".venv", "Users"]

[tool.ruff.lint]
select = [
  "ERA001",   # 주석 처리된 코드. 현재 0건 — 예방용이며, 한글 서술에는 오탐이 안 났다(§5.4)
  "D",        # docstring. convention=google 이 방언 관련 12개 규칙을 알아서 끈다(§3.4)
  "W505",     # 주석·docstring 줄 길이. max-doc-length 를 줘야 발화한다(§5.2)
  "TD",       # TODO 형식. 현재 0건 — 첫 TODO 가 들어오는 순간부터 형식을 강제한다
  "FIX",      # TODO/FIXME/XXX/HACK 존재 자체를 보고. TD 와 목적이 다르다
]
ignore = [
  "D100",     # module docstring 누락 — 현재 0건이라 강제 불필요. 스크립트에 노이즈만 준다
  "D104",     # package docstring 누락 — 같은 이유
  "D203",     # class docstring 앞 빈 줄. D211 과 상호배타라 하나는 꺼야 한다
  "D213",     # multi-line 요약을 둘째 줄에. D212(첫 줄)와 상호배타
  "D400",     # 첫 줄 마침표. 한글 서술문에 마침표를 강제할 근거가 없다(PEP 8 은 영어 문장 규칙)
  "D415",     # 같은 것의 google 판(., ?, ! 중 하나)
  "D401",     # 명령형. 한글에서 273건 중 2건만 발화 = 검사되지 않는다(§5.3). google 이 이미 끈다
  "D403",     # 첫 단어 대문자화. 11건 전부 오탐이고 자동수정이 PEP 8 을 어긴다(§5.3)
  "D205",     # 요약 뒤 빈 줄. 13건. 한 줄 요약 + 본문 이어쓰기가 이 저장소 문체다
  "TD002",    # TODO 작성자. 1인 저장소에서 git blame 이 더 정확하다. polars 도 끈다
  "TD003",    # TODO 이슈 링크. 이슈 트래커가 없다. polars 도 끈다
]

[tool.ruff.lint.pycodestyle]
max-doc-length = 100            # PEP 8 의 72 는 한글에 이식 불가(§1.3). 현 문체의 자연 상한이 100이다
ignore-overlong-task-comments = true   # 긴 TODO 를 길이 규칙으로 두 번 때리지 않는다

[tool.ruff.lint.pydocstyle]
convention = "google"           # D401 등 12개가 자동으로 꺼진다(§3.4). Args:/Returns:/Raises: 를 이미 쓰고 있다

[tool.ruff.lint.per-file-ignores]
"tests/**"   = ["D1", "DOC"]                        # Google §3.8.2.1 · pydantic · polars 선례(§4.3)
"scripts/**" = ["D103", "D102", "D101", "D107"]     # 엔트리포인트 스크립트. 공개 API 가 아니다
```

**실측 결과: 60건**(자동수정 가능 25건).

```
17 D102  undocumented-public-method
11 D209  new-line-after-last-paragraph   [자동수정]
 7 D101  undocumented-public-class
 7 D107  undocumented-public-init
 7 D410  no-blank-line-after-section     [자동수정]
 7 D411  no-blank-line-before-section    [자동수정]
 2 W505  doc-line-too-long
 1 D103  undocumented-public-function
 1 D417  undocumented-param
```

**273건이 60건이 됐고, 남은 60건은 전부 `src/`의 실제 공개 표면이다.** 첫 도입이 현실적이라는 것이
이 설정의 유일한 정당화 근거다.

**`DOC`(pydoclint)는 넣지 않았다.** preview이고, `DOC201`이 89건을 낸다 — 한글 docstring이
반환값을 **서술로** 적기 때문이다(`"""… (cfg, 해석된 경로) 반환."""`). `Returns:` 절을 89개 새로
만들라는 요구는 정보를 늘리지 않는다. 다만 **`DOC501`(19건)은 다르다** — §3.3에서 봤듯 `Raises:`는
PEP 484가 docstring에 명시적으로 위임한 유일한 칸이므로, **preview가 stable로 승격되면 `DOC501`만
선택할 가치가 있다.**

### 5.6 `Makefile` 통합

[`Makefile`](../../Makefile)은 `test: $(PY) -m pytest tests/ -q` 하나로 검사를 돌리고 `.PHONY`에
등록한다. 같은 모양으로 붙인다:

```make
.PHONY: help test lint bundle-sp500 bundle-microcap check-dag check-docrefs clean-bundle
#                ^^^^                                  ^^^^^^^^^^^^^ 추가

lint:
	.venv/bin/ruff check src scripts tests

lint-fix:
	.venv/bin/ruff check --fix src scripts tests
```

`help` 타깃에 `@echo "lint             주석·docstring 린트"` 한 줄을 추가한다.
[`requirements.txt`](../../requirements.txt)의 `# --- 테스트 ---` 절 아래에 핀을 넣는다:

```
ruff==0.16.3                  # 주석·docstring 린트 (docs/research/python-comments.md)
```

⚠️ **`$(PY) -m ruff`가 아니라 `.venv/bin/ruff`를 썼다** — ruff는 파이썬 패키지가 아니라 바이너리를
배포하며, `python -m ruff` 진입점 제공 여부를 확인하지 않았다(§12).

### 5.7 각 규칙이 이 저장소의 관측된 문제 4개를 잡는가

브리핑이 지목한 문제 4개에 대한 **직답**이다. 3개는 잡히지 않는다.

| 관측된 문제 | 잡는 규칙 | 실제로 잡히는가 |
|---|---|---|
| **주석 처리된 코드** | `ERA001` | **해당 사항 없음** — 검출 **0건**. 규칙은 예방적 가치만 있다 |
| **마크다운 강조 16건 · `★`/`⚠️` 6건** | **없음** | ❌ **잡히지 않는다.** Ruff 969개 규칙 중 0개(§10.2). `RUF003`은 다른 것(수학 기호)을 잡고 그것도 전부 오탐(§5.3) |
| **죽은 문서 참조 5건** | **없음** | ❌ **잡히지 않는다.** 어떤 파이썬 린터도 주석 안의 파일 경로를 해소하지 않는다. 이 저장소용 스크립트가 유일한 답이다(§7.7) |
| **docstring 커버리지 46.4%** | `D1xx` · `interrogate` | ✅ **잡힌다.** 권고 설정 후 `src/` 32건으로 좁혀진다 |

**넷 중 하나만 린터가 닫는다.** §6이 그래서 필요하다.

---

## 6. 기계가 잡지 못하는 것 — 린터는 고리를 닫지 않는다

### 6.1 원리적으로 검사 불가능한 것

| 주장 | 왜 검사 불가능한가 |
|---|---|
| "이 주석은 코드를 재진술한다" | 자연어 문장과 AST의 의미 동등성 판정. 판정표 행 3(§2.8)은 **사람 전용**이다 |
| "이 주석은 낡았다" | §6.2 — 연구는 있고 배포된 도구는 없다 |
| "이 주석은 설계 문서를 중복한다" | 두 자연어 텍스트의 의미 중복 판정. §7 |
| "이 `# noqa`가 정당하다" | 해당 규칙을 **켜야만** 알 수 있다. 이 저장소의 50건이 그 상태다(§5.4) |
| "72자 규칙의 의도가 지켜졌다" | 규칙은 문자를 세고 의도는 표시 폭이다. 한글에서 둘이 갈린다(§1.3) |
| "이 docstring이 호출자에게 충분하다" | Google *"should give enough information to write a call to the function without reading the function's code"* — 충분성은 판정 불가 |

★ **그리고 §5.3이 더 위험한 범주를 보여준다: 규칙이 켜져 있고 0건인데 검사되지 않은 경우.**
`D401`이 한글 docstring 271개를 조용히 통과시켰다. **"린트 통과"를 "규율 준수"로 읽으면 안 된다.**
`ERA001` 0건은 진짜 0건이고(§5.4에서 시험했다) `D401` 2건은 미검사이며, **리포트 상으로 둘은
구별되지 않는다.**

### 6.2 ★★ 자동 낡음 탐지 — 측정된 한계

**이 절이 §5.7의 "린터가 고리를 닫지 않는다"를 문헌으로 뒷받침한다.**

먼저 **인용 함정**을 분리해야 한다. 이 분야 수치는 두 종류가 섞여 유통된다:
**(a) 주석을 해석하는 정확도**(90~100%)와 **(b) 코드와 대조해 불일치를 잡는 정밀도**(43~75%).
**널리 인용되는 "90% 정확도"는 (a)다.**

| 도구 / 논문 | 문제 범위 | (a) 주석 해석 | **(b) 탐지 정밀도** | 재현율 |
|---|---|---|---|---|
| **iComment** (Tan, Yuan, Krishna, Zhou — SOSP 2007, [10.1145/1294261.1294276](https://doi.org/10.1145/1294261.1294276)) | lock·call **2개 주제** | 90.8–100% | **61.2%** (60/98) | 미측정 |
| **aComment** (Tan et al. — **ICSE 2011**, pp.11–20) | 인터럽트 on/off, Linux 한 시스템 | 52.1% | 75% (9/12 버그) | 미측정 |
| **@tComment** (Tan, Marinov, Tan, Leavens — ICST 2012) | null 관련 Javadoc `@param`/`@throws` | 98–100% | **42.6%** (29/68) | 미측정 |
| **Fraco** (Ratol & Robillard — ASE 2017, [10.1109/ASE.2017.8115624](https://doi.org/10.1109/ASE.2017.8115624)) | **이름 바꾼 식별자의 옛 이름이 주석에 남았는가** | — | 78–100% | 93–100% (**상한 근사**) |
| **Panthaplackel et al.** (AAAI 2021, [arXiv:2010.01625](https://arxiv.org/abs/2010.01625)) | Java `@param`/`@return`/summary | — | **F1 87.1** (정제 300) / **79.6** (전체 3,944) | — |
| ★ **OCD** (Liu, Xia, Lo, Yan, Li — **IEEE TSE 49(1):1–23**, [10.1109/TSE.2021.3138909](https://doi.org/10.1109/TSE.2021.3138909)) | 같음, **실제 발생률 유지** | — | **64.0%** | **17.1%** (F1 **27.0**) |
| **독립 재현** (Xu et al. — ICSE 2023) | Panthaplackel 아키텍처 재훈련 | — | **F1 44.7%**(시간분할) / **41.8%**(프로젝트분할) | — |

★★ **가장 정직한 숫자는 OCD의 것이다.** 454K 테스트셋에서 양성:음성 ≈ **1:38**:

> "the Whole dataset is highly imbalanced and the ratio of the positive samples to the negative
> samples in it is about **1/38**"
>
> "OCD achieves a Precision of 64.0% and a Recall of 17.1%. Although such performance is
> **not perfect** …"

혼동행렬: TP 1,650 / FP 932 / FN 7,997 / TN 443K → **노후 주석 6개 중 5개를 놓친다.**

★ **그리고 균형 학습 모델을 실제 분포에 배포하면 정밀도가 붕괴한다** (같은 논문):

| | Precision | Recall | F1 |
|---|---|---|---|
| OCD_balanced | **11.4%** | 67.3% | 19.5% |
| OCD | 64.0% | 17.1% | 27.0% |

**F1 87을 내는 논문의 데이터셋은 인공 균형이다** — Panthaplackel의 원 분포 양성률은 **11.6%**이고
저자들이 음성을 다운샘플링했다. 라벨은 커밋 이력 휴리스틱이며 저자들이 **17–20% 오라벨**
(summary 주석은 **26–28%**)을 직접 측정했다. **87.1은 그 노이즈를 저자 1명이 걷어낸 300개
샘플 위의 값이다.**

**세 개의 추가 확인이 결론을 굳힌다:**

1. **휴리스틱이 딥러닝을 이긴다.** HebCUP(Lin et al., ICPC 2021)은 학습 없이 CUP을
   **25.6% vs 15.8%**로 이기고 **1,700배 빠르다.** Panthaplackel 논문 부록에서도 `@param`에서
   **2010년 규칙 한 줄이 F1 93.8**로 신경망(91.8)을 이긴다.
2. **사람은 제안을 대체로 거부한다.** 실사용 평가(Panthaplackel et al., ACL 2020, N=10 ×
   500 평가)에서 최고 모델 제안 채택률 **30.2%**, *"Users selected none of the suggested
   comments 55% of the time"*.
3. **Fraco가 유일하게 P·R 둘 다 90%대인 이유는 문제를 극단적으로 좁혔기 때문이다** — "이름 바꾼
   식별자의 옛 이름이 주석에 남았는가". 저자 본인이 일반화를 차단한다:

   > "the way to interpret the results … is as an **illustration of the potential** of the
   > approach in six distinct contexts, **as opposed to a general prediction of the operational
   > performance** of the tool."

   그리고 재현율은 진짜 값이 아니다 — *"an **upper bound** approximation of the true recall"*.

**→ 정직하게 쓸 수 있는 문장:** 연구 프로토타입은 **좁게 정의된 주석 범주 안에서** 주석을
90~100% 정확도로 **해석**하지만, 코드와 대조해 실제 불일치를 **잡는** 정밀도는 43~75%다.
실제 발생률을 유지한 유일한 대규모 평가에서는 **정밀도 64% · 재현율 17% · F1 27%**였고, 흔히
인용되는 F1 87은 인공 균형 데이터셋 값이며 독립 재현 시 F1 45로 떨어진다.
**배포된 린터·IDE 플러그인은 어느 논문에도 없다 — 산출물은 전부 연구 코드다.**

그리고 **도구 지형 확인(직접)**: Ruff 0.16.3의 969개 규칙, pydocstyle, pydoclint, darglint,
interrogate, vulture, pylint의 주석 관련 메시지 전량을 조사했고 **주석의 낡음을 판정하는 규칙은
하나도 없다.** 가장 가까운 것들은 전부 다른 것을 본다:

- `pydoclint` / Ruff `DOC` — docstring **절**과 **시그니처**의 불일치. 자연어 내용은 안 본다.
- `pylint` `W9015` missing-param-doc · `W9011` missing-return-doc — 존재 여부만
  (`pylint.extensions.docparams` 확장 필요). `W0511` fixme는 TODO 존재만 본다.
- `vulture` — 죽은 **코드**. 주석은 안 본다.
- `interrogate` — docstring **존재**만.

**PEP 8이 *"Always make a priority of keeping the comments up-to-date"* 라고 요구하는 바로 그
항목이 전적으로 사람 몫이다.** 그리고 §6.4가 사람이 실제로는 그걸 잘 안 한다는 것을 보여준다.

### 6.3 그래서 사람이 언제 보는가

기계가 못 잡는 항목은 **코드를 고치는 순간**에만 값싸게 확인된다.

1. **함수 본문을 고쳤으면 그 함수의 docstring과 위쪽 블록 주석을 같은 커밋에서 읽는다.**
   판정표(§2.8) 행 2·3만 적용한다 — 두 물음이고 초 단위다. **§6.4의 실증이 "같은 커밋"을
   지지한다** — co-change의 98%가 같은 리비전에서 일어나고, 그 시점을 놓치면 사실상 영구히 놓친다.
2. **수치·상수를 고쳤으면 그 수치를 언급하는 주석을 grep한다.**
   실제 예: [`scripts/live/rebalance.py`](../../scripts/live/rebalance.py)의 `--max-loss` 주석이
   *"기본값은 --budget 기본값 700의 10%"* 라고 적는다. `--budget` 기본값을 바꾸면 이 주석이 즉시
   거짓이 되고, **주석 자신이 그렇게 경고한다**("두 기본값의 연동은 코드에 없으니 예산을 바꾸면
   이 값도 함께 봐야 한다"). 좋은 주석이지만 **기계가 지킬 수 없는 계약**이다.
3. **문서를 이름 바꾸거나 지웠으면 §7.7의 스크립트를 돌린다.** 이것만 자동화된다.

### 6.4 실증 — 주석은 코드와 함께 잘 바뀌지 않는다

**Fluri, Würsch, Giger, Gall, "Analyzing the co-evolution of comments and source code",
*Software Quality Journal* 17(4):367–394, 2009**
([10.1007/s11219-009-9075-x](https://doi.org/10.1007/s11219-009-9075-x); 8개 시스템,
275,392 리비전, 115,226 주석 변경 — 본문 판독):

> "During the evolution of all systems, **98% of direct co-changes happen in the same
> revision** … In contrast, between **57% (Eclipse Core) and 93% (jEdit)** of scope co-changes
> happen in the same revision."

★ **그런데 co-change 자체가 전체 주석 변경의 50.06%(jEdit)~68.80%(Azureus)뿐이다**(Table 4).
그리고 새로 추가된 코드가 주석을 받는 비율은 **프로젝트마다 27%~100%로 극단적으로 갈린다:**

> "newly added code is **barely commented in half of the systems** … only between **27%
> (Eclipse PDE) and 42% (jEdit)** commented source code. In contrast, ArgoUML, Eclipse Core,
> JFreeChart, and Webframework have between **53% … and 100% (JFreeChart)**"

> "The growth factor of source code and comments are equal. **This does not mean that every new
> line of code gets commented**"

⚠️ **인용 함정 두 개** (판독 중 확인):
- **WCRE 2007 판의 초록·결론이 말하는 "97% of comment changes"는 모집단을 떨어뜨린 축약**이다.
  실제 모집단은 **코드 변경이 유발한 주석 변경(전체의 23~52%)**뿐이다. **이 축약 때문에 인용
  사슬이 널리 왜곡돼 있다.**
- **SQJ 2009 초록의 "with statistical significance"는 과한 주장이다.** 상관계수도 p-value도 없고
  n=9~14의 t값만 있으며, 구조가 **귀무가설을 채택해 등가성을 주장**하는 형태다(등가성 검정이 아니다).

**Wen, Nagy, Bavota, Lanza, "A Large-Scale Empirical Study on Code-Comment Inconsistencies",
ICPC 2019, pp.53–64** ([10.1109/ICPC.2019.00019](https://doi.org/10.1109/ICPC.2019.00019);
1,500 Java 프로젝트, 3,323,198 커밋, 13억 AST 변경 — 본문 판독):

> "we observe a co-evolution of code and comments happening in **7% of cases for method's
> comments and 13% of cases for class's comments** … **13% to 20% of code changes trigger a
> comment change**"

⚠️ **저자가 직접 못박은 경고 — 이걸 빼고 인용하면 저자 의도 왜곡이다:**

> "This does **not** imply that in the remaining ∼80% of cases code-comment inconsistencies are
> introduced, but they represent a **possibility**"

한국어: 이것이 남은 약 80%에서 주석-코드 불일치가 **도입된다는 뜻은 아니다.** 다만 **가능성**을
나타낸다.

**→ §6.3의 절차가 이 실증에 기대는 지점:** 주석이 갱신될 확률이 가장 높은 순간은 **코드 변경과
같은 커밋**이고(98%), 그 순간을 놓치면 대부분 영구히 놓친다. **그러므로 규율의 개입 지점은
코드 리뷰가 아니라 커밋이다.**

### 6.5 TODO 위생 — 이 저장소는 0건이고, 그것이 좋은 상태다

`TD`/`FIX`가 0건이므로 **권고는 예방적**이다. 문헌은 TODO를 남기는 쪽의 비용을 측정했다:

| 논문 | 측정 |
|---|---|
| Potdar & Shihab, ICSME 2014 (**4개** 프로젝트) | SATD 포함 **파일 2.4~31.0%**. Eclipse 3.0→3.1에서 26.3% 제거, **7릴리스 후에도 약 63% 잔존.** Apache: "**After four major releases (in 10 years), 25.45% remains**" |
| Bavota & Russo, MSR 2016 (**159개** 프로젝트, 20억 주석) | 프로젝트당 평균 51건. 생존 **중위 266 커밋 / 평균 1,087 커밋.** *"in **63% of cases the developer paying-back the debt is the same** who introduced it"*. **도입 대비 약 57%만 나중에 수정**된다. ⚠️ 수동 검증 시 **오탐 25%** |
| Maldonado, Abdalkareem, Shihab, Serebrenik, ICSME 2017 (5개 프로젝트, 5,733 제거) | 제거율 **40.5–90.6%**(평균 74.4%). 자기제거 평균 **54.4%**. 생존 **중위 18.2–172.8일 / 평균 82–613.2일** |
| Wang et al., ACM TOSEM 2024 | *"About **46.7% of TODO comments** in open-source repositories are of **low-quality**"* · 평균 수명 **166.31일** · 전체 TODO 중 **해결 14.5% / 해결 없이 삭제 17.5%**(저품질은 삭제가 **29.2%**) |

⚠️ **인용 주의 두 개:**
- **세 논문의 "% SATD"는 분모가 다르다** — Potdar는 **파일** 기준(2.4~31%), Bavota는 **주석**
  기준(0.3%), Maldonado TSE 2017도 **주석** 기준(평균 1.86%). **같은 축에 놓으면 틀린다.**
- **Maldonado의 생존 시간은 "결국 제거된 것들"만의 수명이다.** 영구 잔존분(평균 25.6%)은 평균에
  들어가지 않는다. "SATD는 중위 18–172일 산다"로 쓰면 틀린다.

→ **이 저장소에 주는 결론:** TODO를 남기면 **절반 가까이가 저품질이고, 6분의 1은 해결 없이 그냥
삭제되며, 살아남는 것은 릴리스 여러 개를 넘긴다.** `TD`/`FIX`를 켜는 이유는 이미 있는 TODO를
고치기 위해서가 아니라 **0건 상태를 의식적으로 유지하기 위해서**다. 첫 TODO가 들어올 때
`FIX002`가 그것을 보고하게 한다.

---

## 7. 주석 ↔ 외부 문서 — 중복과 링크 부패

### 7.1 이 저장소에서 실제로 일어난 일

브리핑은 죽은 문서 참조 1건을 지목했다. **직접 세어 보니 5건이다.**

| 위치 | 참조 | 상태 |
|---|---|---|
| [`src/execution/interface.py`](../../src/execution/interface.py) `:31` | `qlib-toss.md` | **죽음** |
| [`src/execution/rebalance.py`](../../src/execution/rebalance.py) `:3` | `qlib-toss.md` | **죽음** |
| 같은 파일 `:11` | `qlib-toss.md` | **죽음** |
| [`scripts/toss_probe/01_accounts.py`](../../scripts/toss_probe/01_accounts.py) `:25` | `qlib-toss.md` | **죽음** |
| [`scripts/toss_probe/06_microcap_coverage.py`](../../scripts/toss_probe/06_microcap_coverage.py) `:155` | `phase0b-execution-gate.md` | **죽음 — 그리고 영구적** |
| `scripts/model_backtest/README.md` `:4` | `../../qlib-toss.md` | **죽음** (`.md`이므로 링크 검사기가 잡는다) |
| `scripts/model_backtest/_common.py` 등 8곳 | `trial-accounting.md` · `trial-ledger.md` · `docs/research/training-gates.md` | 살아 있음 |

### 7.2 ★★ 가장 나쁜 유형 — 설계상 해소 불가능한 참조

`phase0b-execution-gate.md`는 이제 `docs/findings/execution-gate.md`이고,
[`.gitignore`](../../.gitignore)가 `docs/findings/`를 **의도적으로 영구 제외**한다(계좌 고유
실측값). 그런데 그 파일을 가리키는 쪽은 **추적되는 스크립트**이고, 참조가 주석도 아니라 **런타임
`print` 문**이다:

```python
print("\n👉 결과를 phase0b-execution-gate.md에 기록.")
```

→ **클론한 사람이 이 스크립트를 돌리면 존재하지 않고 앞으로도 존재할 수 없는 파일에 기록하라는
지시를 받는다.** 이름 변경으로 깨진 것이 아니라 **설계상 해소 불가능**하다.

프로젝트 `CLAUDE.md`는 *"추적 문서(`project/`·`research/`)는 `docs/plans/`를 링크하지 않는다"* 는
규칙을 이미 갖고 있다. **그 규칙이 `.py`에는 적용된 적이 없다. 규칙에 구멍이 있다.**

그리고 Google 스타일 가이드가 TODO에 대해 적은 원리가 여기 그대로 걸린다(§3.12):

> "A bug reference is preferable **because bugs are tracked and have follow-up comments.**"

→ **참조 대상은 "추적되는 것"이어야 한다.** `docs/findings/`는 정확히 그 반대다.

### 7.3 ★ 비대칭 — 마크다운은 고쳐졌고 파이썬은 안 고쳐졌다

`qlib-toss.md`는 `docs/project/roadmap.md`로 이름이 바뀌었다. 이름 변경 시:

- **`.md` 문서는 재연결됐다** — `docs/research/dashboard-features.md`는
  `[qlib-toss.md](../project/roadmap.md)`로 적는다(레이블은 낡았지만 **링크는 작동한다**).
  `docs/project/microcap-insider-prereg.md`는 매핑 표에
  `qlib-toss.md → docs/project/roadmap.md`를 기록해 뒀다.
- **`.py` 주석은 하나도 안 고쳐졌다** — 5건 전부 남아 있다.

**이유는 명백하다: 마크다운 링크는 문법이고 주석 안 파일명은 산문이다.** 링크는 도구가 볼 수
있고 사람 눈에도 `[…](…)` 구조로 띈다. 산문 속 `qlib-toss.md`는 grep 대상일 뿐이며, **이름을
바꾼 사람이 `.py`를 grep할 이유가 없었다.**

→ **판정표(§2.8) 행 11의 근거가 이것이다.** 주석이 외부 문서를 가리키면 **그 참조는 검사되지
않는 채널로 들어간다.**

### 7.4 ★★ 또 다른 유형 — 해소 안내가 없는 ID 참조

이 저장소는 `개선1` ~ `개선14`라는 **번호 ID**로 검토 항목을 참조한다. `.py`에서 **35회**
등장한다(13개 파일).

```python
"""개선13: 표준 OAuth error/error_description(비밀 아님)만 추출. …"""   # src/toss/auth.py:20
# 개선13: resp.text(임의 본문·잠재 누설) 대신 표준 OAuth error 필드만 노출.   # :99
```

직접 대조한 결과:

- **14개 ID 전부 `docs/project/roadmap.md`에 `[개선N]` 형태로 정의돼 있다** (추적됨 ✅).
- `.py`에서 인용되는 11개 중 **정의 없는 것은 0개다.** 링크 부패가 아니다.
- ★ **그런데 `roadmap.md`를 이름으로 부르는 `.py` 파일은 0개다.**

→ **참조는 유효하지만 해소 경로가 어디에도 없다.** `개선13`을 만난 독자는 저장소 전체를 grep해야
하고, 그 ID 공간이 `roadmap.md`에 있다는 사실은 **어느 코드에도 적혀 있지 않다.**

그리고 상황이 정확히 뒤집혀 있다:

- 코드가 **파일명**을 부를 때는 → 죽은 옛 이름(`qlib-toss.md`)을 부른다.
- 코드가 **ID**를 부를 때는 → 살아 있는 ID를 부르지만 그 집이 어딘지 말하지 않는다.
- **그리고 그 죽은 파일명의 새 이름이 바로 ID들이 사는 집이다** — `roadmap.md`.

**→ 하나의 치환이 두 문제를 동시에 닫는다:** `qlib-toss.md` → `docs/project/roadmap.md`.
그러면 참조가 해소되고, `개선N`에게 주소가 생긴다.

### 7.5 ★★ 중복에 관한 1차 지침 — 존재한다 (초고의 "출처 없음"을 정정한다)

**Ousterhout 본인 문장** (CS190 강의노트, §2.2와 같은 출처). **이것이 주석↔외부문서 중복 문제를
직접 다루는 1차 텍스트다:**

> ```
> Challenges with comments:
>   It must be easy for people to find the right documentation at the right time
>   The documentation must get updated as the code changes
> Techniques:
>   Document each thing exactly once: don't duplicate documentation
>     (it won't get maintained)
>     Use references rather than repeating documentation:
>       "See documentation for xyz method".
>   Put documentation as close as possible to the relevant code
>   Don't say anything more in documentation than you need to
>     e.g., don't use comments in one place to describe design decisions elsewhere
>     Higher-level comments are less likely to become obsolete
>   Look for "obvious" locations where people can easily find documentation
> ```

한국어: 주석의 난점 — 사람이 **적시에 올바른 문서를 찾기 쉬워야** 하고, 문서는 코드가 바뀔 때
갱신돼야 한다. 기법: **각 사항을 정확히 한 번만 문서화하라. 문서를 중복하지 말라(유지되지
않는다).** 반복 대신 **참조를 쓰라** — "xyz 메서드 문서 참조". 문서를 관련 코드에 최대한 가까이
두라. 필요 이상을 말하지 말라 — 예컨대 **한 곳의 주석으로 다른 곳의 설계 결정을 서술하지 말 것.**
**고수준 주석이 낡을 가능성이 더 낮다.** 사람이 문서를 쉽게 찾을 수 있는 "자명한" 위치를 찾으라.

책 목차도 이를 뒷받침한다(검증된 절 제목): `16.2 keep the comments near the code` ·
`16.3 Comments belong in the code, not the commit log` · `16.4 avoid duplication`.

**Google, *Software Engineering at Google* ch.10 "Documentation"**
([abseil.io/resources/swe-book/html/ch10.html](https://abseil.io/resources/swe-book/html/ch10.html),
무료 전문). 먼저 범위 진술 — **이 장은 주석을 문서로 센다:**

> "When we refer to 'documentation,' we're talking about every supplemental text that an
> engineer needs to write to do their job: not only standalone documents, but **code comments
> as well**. (In fact, most of the documentation an engineer at Google writes comes in the form
> of code comments.)"

**단일 진실원천 — 이 질문의 핵심 답:**

> "Documents without owners become stale and difficult to maintain. … Of course, documents with
> different owners can still conflict with one another. In those cases, **it is important to
> designate canonical documentation: determine the primary source and consolidate other
> associated documents into that primary source (or deprecate the duplicates).**"

한국어: 소유자 없는 문서는 낡고 유지가 어려워진다. … 소유자가 다른 문서들은 서로 충돌할 수 있다.
그런 경우 **정전(canonical) 문서를 지정하는 것이 중요하다 — 주 출처를 정하고 관련 문서들을 그
주 출처로 통합하라(또는 중복을 폐기하라).**

> "Most reference documentation, even when provided as separate documentation from the code, is
> generated from comments within the codebase itself. (As it should; **reference documentation
> should be single-sourced as much as possible.**)"

**중복이 정당한 예외 — 중요한 뉘앙스:**

> "In almost all cases, a conceptual document is meant to **augment, not replace**, a reference
> documentation set. Often this leads to **duplication of some information, but with a purpose:
> to promote clarity.** … In this case, sacrificing some accuracy is acceptable for clarity."

한국어: 거의 모든 경우 개념 문서는 참조 문서를 **대체하는 것이 아니라 보완**한다. 그래서 **일부
정보가 중복되곤 하는데, 목적이 있다 — 명료성**이다. 이 경우 명료성을 위해 정확성을 일부 희생하는
것이 허용된다.

**어느 모듈에도 속하지 않는 설명 — Ousterhout §13.7과 같은 문제, 같은 결론:**

> "One problem engineers face when writing conceptual documentation is that it often **cannot be
> embedded directly within the source code because there isn't a canonical location to place
> it.** … The only logical place to document such complex behavior is through a **separate
> conceptual document.** If comments are the unit tests of documentation, conceptual documents
> are the integration tests."

**노후화 대책 — freshness date:**

> "At Google, we often attach '**freshness dates**' to documentation. Such documents note the
> last time a document was reviewed, and metadata in the documentation set will send email
> reminders when the document hasn't been touched in, for example, three months."

> "when a document no longer serves any purpose, either remove it or **identify it as obsolete**
> (and, if available, indicate where to go for new information). Even for unowned documents,
> someone adding a note that 'This no longer works!' is more helpful than saying nothing and
> leaving something that seems authoritative but no longer works."

**→ 세 출처가 같은 처방에 수렴한다:**

| 원리 | Ousterhout | SWE at Google | 이 저장소 적용 |
|---|---|---|---|
| 한 번만 쓴다 | *"Document each thing exactly once"* | *"designate canonical documentation"* | `docs/project/roadmap.md`가 `개선N`의 정전이다. 주석은 요약하지 않고 가리킨다 |
| 반복 대신 참조 | *"Use references rather than repeating documentation"* | *"reference documentation should be single-sourced"* | §7.4의 치환 |
| 남의 결정을 여기 쓰지 않는다 | *"don't use comments in one place to describe design decisions elsewhere"* | *Clean Code* `Nonlocal Information`도 같은 항목 | §7.1의 5건이 전부 이 유형이다 |
| 고수준이 덜 낡는다 | *"Higher-level comments are less likely to become obsolete"* | — | 주석에 **수치**를 쓰면 낡는다(§6.3 예 2) |

★ **다만 SWE at Google의 예외 조항을 함께 읽어야 한다** — "명료성을 위한 목적 있는 중복"은
허용된다. **§2.8 행 11이 "요약을 지우고 포인터만 남긴다"고 한 것은 이 예외를 좁게 해석한 것이며,
그것이 판단임을 밝혀 둔다.**

### 7.6 ★★ 링크 부패는 측정됐다

**Hata, Treude, Kula, Ishio, "9.6 Million Links in Source Code Comments: Purpose, Evolution,
and Decay", ICSE 2019, pp.1211–1221**
([10.1109/ICSE.2019.00123](https://doi.org/10.1109/ICSE.2019.00123);
[arXiv:1901.07440](https://arxiv.org/abs/1901.07440) 프리프린트 판독).
25,925개 저장소, **9,654,702개 링크**, 고유 링크 **382,650개** 전수 접속.

> "Links are rarely updated, but many link targets evolve. **Almost 10% of the links included
> in source code comments are dead.**"

전수 접속 결과(Table VIII): `2xx` **81.2%** · **`404 not found` 34,689 (9.1%)** · `500` 5.0% ·
`405` 2.6% · `403` 1.0% · 기타 1.1%.

★ **그리고 드물게 참조되는 도메인일수록 훨씬 더 죽어 있다** (도메인 빈도 3계층 표본):

> "we can conclude with a 95% confidence that **between 32 and 42% of all links to domains
> which are rarely linked from source code comments are dead or inaccessible.**"

계층별 404 비율 — 흔한 도메인 **7%** / 간헐 **32%** / 희귀 **37%**.

**갱신은 거의 일어나지 않는다:**

> "**Links are rarely updated (less than 9%).** Common modifications are updating licenses and
> organization homepages."

그리고 **갱신된 링크 중 20개는 여전히 404**였다.

**404의 최대 출처가 GitHub이다:**

> "The domain with the largest number of 404s is **github.com, with 3,346 links** no longer
> available or pointing to private repositories."

**저자 권고 — 이 저장소에 그대로 적용된다:**

> "Try referencing permanent links, as it is reported that **more than 30% of links will not
> work after a 4 year period**. … **Explicitly mentioning tags or commit hashes to referenced
> code in GitHub would be recommended, as software structure can be changed.**"
>
> "**Check link targets for new information on a regular basis**, as referenced external
> resources can be considered to be software documentation."

("30%/4년"의 출처는 Koehler, *JASIST* 53(2):162–171, 2002 — 이 문서는 원 논문을 열지 않았다.)

★★ **이 논문이 프로젝트 `CLAUDE.md`의 기존 규칙을 독립적으로 확증한다.** 그 규칙은
*"조치 근거를 가리켜야 하면 **커밋 해시**를 쓴다 — 행 번호와 달리 안 낡는다"* 라고 적는데,
Hata et al.의 권고가 정확히 같다(*"mentioning tags or commit hashes"*).
**이 저장소가 이미 옳게 정한 규칙이며, 문헌 근거가 붙었다.**

⚠️ **한계(저자 명시):** *"we cannot generalize our findings to industry nor open source projects
in general"*, 여러 줄에 걸친 링크는 추출하지 못했다. 그리고 이 문서가 판독한 것은 프리프린트다.
**RQ3(링크 목적) 분류 코드 목록은 확인하지 않았다**(§12).

### 7.7 실행 가능한 완화 — `Makefile` 타깃 하나

린터가 없으니(§5.7) 직접 만든다:

```make
check-docrefs:
	@grep -rno '[A-Za-z0-9_./-]*\.md' --include='*.py' src scripts tests \
	  | while IFS=: read -r f l ref; do \
	      test -f "$$ref" -o -f "docs/project/$$ref" -o -f "docs/research/$$ref" \
	        || echo "죽은 문서 참조: $$f:$$l -> $$ref"; \
	    done; true
```

⚠️ **한계 두 개를 분명히 해 둔다.**
(1) **`docs/plans/`·`docs/findings/`를 일부러 후보에서 뺐다** — 그쪽은 추적 밖이므로 로컬에서
통과하고 클론에서 실패한다. `Makefile`의 `check-dag` 주석이 이미 같은 함정을 기록해 뒀다
(*"정작 신규 클론에서만 실패하는 정반대 동작"*). 여기서는 **추적 밖 문서를 가리키는 것 자체를
위반으로 취급**한다.
(2) **ID 참조(`개선N`)는 잡지 못한다** — 파일명 문법이 없기 때문이다. §7.4의 치환을 사람이 한 번
해야 한다.

**§7.6이 시사하는 확장:** 이 스크립트는 로컬 파일만 본다. 주석에 외부 URL이 들어오기 시작하면
**9.1%가 언젠가 404가 된다**는 것이 측정치다. 그때는 `W505`의 URL 예외(§5.2)처럼 URL을 별도로
취급하는 검사가 필요해진다 — **지금은 이 저장소에 주석 URL이 거의 없으므로 만들지 않는다.**

---

## 8. 이 저장소에 즉시 적용할 것 — 우선순위

| 순위 | 조치 | 근거 | 비용 |
|---|---|---|---|
| 1 | `qlib-toss.md` → `docs/project/roadmap.md` **5곳 치환** | §7.4 — 죽은 참조와 무주소 ID를 동시에 닫는다 | grep + 5줄 편집 |
| 2 | `06_microcap_coverage.py:155`의 `print` 문에서 **추적 밖 문서 지시 제거** | §7.2 — 클론에서 해소 불가 | 1줄 |
| 3 | `pyproject.toml` 생성 + `Makefile` `lint` 타깃 | §5.5 — 60건, 25건 자동수정 | 설정 1개 |
| 4 | `Makefile` `check-docrefs` 타깃 | §7.7 — 린터가 못 잡는 유일한 자동화 가능 항목 | 8줄 |
| 5 | `ruff --fix`로 `D209`·`D410`·`D411` 25건 정리 | PEP 8이 *"most importantly"* 라 명시(D209) | 자동 |
| 6 | `src/`의 `D102`·`D101`·`D107` 31건 | §4.1 — 실제 공개 표면 | 사람 작업 |
| 7 | `side: str  # "BUY" \| "SELL"` → `Literal[...]` | §2.8 행 5·6 | 소규모 |
| 8 | `# noqa` 50건 검증(= `F401`·`E402`·`BLE001` 켜기) | §5.4 — 검증되지 않은 주장 50개 | 별도 판단 |

---

## 9. 비영어·이중언어 주석

### 9.1 규범 텍스트는 둘이고, 둘 다 이 저장소와 어긋난다

**(1) PEP 8**, Comments 절:

> "Ensure that your comments are clear and easily understandable to other speakers of the
> language you are writing in.
>
> Python coders from non-English speaking countries: please write your comments in English,
> **unless you are 120% sure that the code will never be read by people who don't speak your
> language.**"

한국어: 주석은 **자신이 쓰는 언어의 다른 화자**에게 명확해야 한다. 비영어권 파이썬 개발자들:
주석을 영어로 쓸 것 — **당신의 언어를 못 하는 사람이 그 코드를 읽을 일이 절대 없다고 120%
확신하지 않는 한.**

같은 PEP의 식별자 규정(별도 항목):

> "All identifiers in the Python standard library MUST use ASCII-only identifiers, and SHOULD
> use English words wherever feasible … **Open source projects with a global audience are
> encouraged to adopt a similar policy.**"

**(2) GNU Coding Standards §5.2 "Comments"**
([gnu.org/prep/standards](https://www.gnu.org/prep/standards/standards.html)) — **예외 조항이
없다:**

> "Please write the comments in a GNU program **in English**, because English is the one
> language that nearly all programmers in all countries can read. If you do not write English
> well, please write comments in English as well as you can, then **ask other people to help
> rewrite them.** If you can't write comments in English, please find someone to work with you
> and **translate your comments into English.**"

한국어: GNU 프로그램의 주석은 **영어로** 써 주시길 — 영어가 모든 나라의 거의 모든 프로그래머가
읽을 수 있는 유일한 언어이기 때문이다. 영어를 잘 못 쓰면 **최선을 다해 영어로 쓴 뒤 다른 사람에게
다시 써 달라고 부탁**하라. 영어로 주석을 쓸 수 없다면 함께 일할 사람을 찾아 **주석을 영어로
번역**하라.

★★ **이 저장소 원격은 public GitHub이다. 따라서 PEP 8의 예외 조건이 성립하지 않는다** —
"절대 읽히지 않는다"를 120% 확신할 수 없는 것이 공개 저장소의 정의다. 정책의 "prose 한글"은
**두 규범 텍스트와 어긋나고, 그 어긋남의 근거가 어디에도 적혀 있지 않다.**

**다만 §1.1을 잊지 말 것** — PEP 8은 프로젝트 규칙이 자기보다 우선한다고 명시한다. **문제는
정책이 다르다는 것이 아니라, 다르다는 사실과 그 근거가 기록되지 않은 것이다.**

### 9.2 다른 스타일 가이드 — 확인 결과

| 소스 | 주석 언어 규정 |
|---|---|
| **GNU Coding Standards** §5.2 | ✅ **영어 명시 요구.** 예외 없음 |
| **PEP 8** | ✅ **영어 요구 + "120% 확신" 예외** |
| **LLVM Coding Standards** ([llvm.org/docs/CodingStandards.html](https://llvm.org/docs/CodingStandards.html)) | ⚠️ **간접적** — *"write them as **English prose**, using proper capitalization, punctuation"*. 문체 규정이지만 영어를 전제한다 |
| **Google Python Style Guide** | ❌ **없음.** §3.8 전문에 언어 정책 문구 전무(raw md 확인). §3.8.6은 *"Pay attention to punctuation, spelling, and grammar"* 만 요구하고 언어를 말하지 않는다 |
| **Google C++ Style Guide** | ❌ **주석 언어 규정 없음.** 인접 규정만 — "Non-ASCII characters should be rare, and must use UTF-8"(문자열 리터럴 대상) |
| **Linux kernel coding style** | ❌ **없음.** §8 Commenting은 언어를 언급하지 않는다 |
| **Django coding style** | ❌ **없음.** 폭(79자)과 인칭(*"Avoid use of 'we' in comments"*)만 |
| **pandas contributing** | ❌ **없음** |

→ **영어를 명시적으로 요구하는 것은 PEP 8과 GNU 둘이고, GNU 쪽이 더 강하다.**
그리고 **PEP 8만 예외 조항을 둔다** — 사내·개인 저장소의 비영어 주석을 정당화할 수 있는 유일한
1차 문구이며, **public 원격에서는 쓸 수 없다.**

### 9.3 ★★ 측정된 효과 — 유병률은 있고 효과는 없다

**Pawelka & Jürgens, "Is This Code Written in English? A Study of the Natural Language of
Comments and Identifiers in Practice", ICSME 2015, pp.401–410**
([10.1109/ICSM.2015.7332491](https://doi.org/10.1109/ICSM.2015.7332491); 저자 소속 CQSE 배포
PDF 판독). 오픈소스 13개 + 산업 10개, 산업 쪽 115,904 주석 / 176,554 식별자 / 3,641,976 LOC.

> "There are **five industry systems which contain a percentage of non-English comments from
> about 50% up to almost 90%** and three industry systems with about 28% up to 45% non-English
> identifiers."

> "non-English comments or identifiers **exclusively occur in the industry projects**. In fact
> half of the industry systems contain non-English comments or identifiers, whereas **none of
> the analyzed open-source systems contain any other natural language than English.**"

한국어: 산업 시스템 **5개가 비영어 주석 비율 약 50%~거의 90%**를 보이고, 3개는 비영어 식별자
28%~45%를 보인다. … 비영어 주석·식별자는 **산업 프로젝트에서만 나타난다.** 산업 시스템의 절반이
비영어 주석·식별자를 포함하는 반면, **분석한 오픈소스 시스템 중 영어 외의 자연어를 포함한 것은
하나도 없었다.**

★ **그리고 이 저장소 정책의 패턴이 이 논문의 관찰과 정확히 일치한다** — RQ3: 주석과 식별자를 다
가진 프로젝트에서 **식별자 쪽이 유의하게 적고, "식별자만 비영어"인 프로젝트는 0개**였다.
정책의 "code/identifiers English, prose 한글"은 **측정된 실무 패턴 그 자체다.**
**출처가 규범이 아니라 유병률이라는 점이 중요하다** — 흔한 것이 옳다는 근거는 아니다.

★★ **이 논문은 이해도·결함 효과를 전혀 측정하지 않는다.** 전문에서 `subjects` ·
`participants` · `controlled experiment`를 grep한 결과 **0건**이다. 순수 유병률 연구다.
초록의 *"a developer without knowledge of this language will almost perceive the code to be
undocumented or even obfuscated"* 는 **측정이 아니라 동기 서술**이다.

**그리고 결정적으로** — 이 논문이 "주석이 이해를 돕는다"의 근거로 인용하는 두 참고문헌이
**정확히 Woodfield 1981과 Tenny 1988**이고, **이 조사는 그 둘을 열지 못했다**(§12).
**2015년 논문도 30년 전 실험에 의존한다.**

**판정: 비영어 주석이 독자의 이해도·생산성에 미치는 효과를 측정한 신뢰할 만한 동료심사 연구를
찾지 못했다.** 없다고 단언하지 않는다 — 못 찾았다고 적는다. 검색 범위는 §12에 있다.

### 9.4 그러므로 §9의 결론은 무엇에 기대는가

측정이 아니라 **세 가지 확인된 사실**이다:

1. **두 규범 텍스트가 공개 저장소에서 한글 주석을 지지하지 않는다**(§9.1).
2. ★ **§5.3이 측정된 대가를 보여준다** — 한글 주석을 쓰면 `D401`·`D403` 같은 **내용 규칙이 조용히
   무력해지거나 거꾸로 작동한다.** 273건 중 `D401`이 2건만 발화한 것은 통과가 아니라 미검사다.
   **이것이 이 문서가 제시할 수 있는, 비영어 주석의 유일한 실측 비용이다.** 그리고 이 비용은
   §5.5의 `ignore` 목록으로 **관리 가능**하다 — 없는 척하는 것보다 낫다.
3. **Knuth/Bentley의 진단이 여기 겹친다**(§2.7) — "프로그래밍 잘하는 소수 ∩ 글쓰기 잘하는 소수"에
   들라는 요구가 이미 어려운데, **비모국어는 그 교집합을 한 번 더 좁힌다.**

**판단(출처 없음, 그렇게 표시함):** 이 저장소의 주석은 §2.8 판정표 행 7·8·10에 해당하는 것들,
즉 **단위·모듈 경계 불변식·왜 이렇게 안 했는가**가 대부분이며(§5.1의 낮은 밀도가 그 증거다)
그런 내용은 비모국어로 정확히 쓰기 가장 어려운 종류다. **정책을 영어로 뒤집으면 §2.8 행 10의
주석 품질이 떨어질 위험**이 있고, 그 위험을 측정한 근거도 이 문서에 없다.
**그래서 §11은 언어 정책의 전환을 권고하지 않고, 근거의 명문화를 권고한다.**

---

## 10. 서식 노이즈 — 마크다운·장식기호·구분선

### 10.1 이 저장소의 실제 양

| 유형 | 건수 | 예 |
|---|---|---|
| 마크다운 강조 `**…**` | **16** | `# ⚠️ 주문 응답의 commission·tax는 **실측상 항상 0이다**(Phase 0, n=38).` |
| `★` · `⚠️` | **6** | `# ★ 이 표가 있어야 하는 이유는 **부호가 모델마다 반대**라는 것이다` |
| ASCII 구분선 | **8** | `# ------------------------------------------------------- 학습 건전성 게이트 (게이트 A)` |

### 10.2 출처 조사 결과 — 없다

- **PEP 8**: 주석 안 서식·기호에 관한 규정이 **없다.** 가장 가까운 것은 *"Comments should be
  complete sentences"* 와 *"Block comments generally consist of one or more paragraphs built out
  of complete sentences"* 이며, **문단·문장 단위를 전제**하지만 강조 표기를 금지하지도 허용하지도
  않는다. `#` 하나만 있는 줄로 문단을 나누라는 규정은 있으나 **ASCII 구분선을 다루지 않는다.**
- **Ruff 0.16.3**: 전 규칙의 `explanation` 전문을 `ruff rule --all --output-format json`으로 받아
  `markdown` · `emphasis` · `asterisk` · `divider` · `banner` · `bold` · `decorative` · `emoji`로
  검색했다. → **969개 규칙 중 0개.**
- **pydocstyle · pydoclint · interrogate · pylint**: 주석 안 서식을 다루는 검사 없음(§6.2).
- **Google 스타일 가이드**: §3.8.6이 문장부호·철자·문법을 요구하지만 마크업은 언급하지 않는다.
- **가장 가까운 1차 언급은 *Clean Code* ch.4 bad comments의 `Position Markers`(p.67)** 이다 —
  ASCII 구분선에 해당하는 항목이다. ⚠️ **본문을 열지 못했으므로 제목만 근거다.**

**→ 출처 거의 없음. 판단 문제다. 그렇게 표시한다.**

### 10.3 판단 — 정직하게

**전제는 사실이다:** `#` 주석의 `**bold**`는 어디에서도 렌더링되지 않는다. 파이썬 주석을 마크다운으로
처리하는 도구가 없다(docstring은 다르다 — Sphinx·napoleon·MkDocs가 처리한다). 따라서 `**…**`는
**네 글자의 문자 그대로의 노이즈**다.

**그런데 반대 논거가 더 강하다고 본다:**

1. **강조가 실제로 정보를 담는다.** `# ⚠️ **값을 알 수 없는 심볼은 결과에 키를 넣지 않는다.**`
   ([`src/execution/interface.py`](../../src/execution/interface.py) `:127`)에서 강조된 문장은
   **계약**이고 나머지는 그 이유다. 강조가 둘을 가른다. 강조를 지우면 **정보가 준다.**
   §2.8 행 8(모듈 경계 불변식)에 정확히 해당하며, Ousterhout가 *"there is no way to specify this
   'contract' in code"* 라 한 바로 그 유형이다(§2.3).
2. **한글은 대문자가 없다.** 영어권 코드가 강조에 쓰는 수단(`MUST`, `NOTE:`, 대문자)이 한글에
   없다. `**…**`는 그 공백을 메우는 대체물이며, **§9.4에서 말한 "언어 선택이 서식 선택을 강제한다"의
   구체적 사례다.**
3. **PEP 8의 문단 규정과 충돌하지 않는다.** `#` 하나로 문단을 나누라는 규정은 지켜도 되고, 실제로
   이 저장소가 지킨다.
4. **비용이 측정 가능하게 낮다.** 16 + 6 = 22건이다. 어느 규칙도 잡지 않고(§10.2) 어느 도구도
   방해받지 않는다.

**★ 반면 ASCII 구분선 8건은 다르게 본다.** PEP 8이 문단 구분 수단을 **명시적으로 지정하고
있으므로**(*"separated by a line containing a single `#`"*) 구분선은 **규정된 수단의 대체물**이며,
`W505`가 문자 수를 세는 만큼 길이 규칙과도 부딪친다. 그리고
[`scripts/model_backtest/_common.py`](../../scripts/model_backtest/_common.py) `:41`의
`# ---- 학습 건전성 게이트 (게이트 A)` 같은 구분선은 **섹션 이름을 담고 있다** — §2.8 행 6에
걸린다: **코드로 표현할 수 있다.** 그 섹션이 진짜 단위라면 모듈로 분리하거나 클래스로 묶는 것이
정답이고, 아니라면 구분선이 없어도 된다. (*Clean Code*의 `Position Markers` 항목이 같은 판단이지만
본문 미확인.)

**권고:**

| 유형 | 권고 | 근거 |
|---|---|---|
| `**강조**` (16) | **유지.** 단 "계약 vs 이유"를 가르는 용도로만 | 정보를 담는다 · 한글에 대문자가 없다 · 출처 없는 금지를 만들지 않는다 |
| `★`/`⚠️` (6) | **유지.** 6건이고 전부 §2.8 행 7·8에 해당한다 | 같음 |
| ASCII 구분선 (8) | **점진 제거.** 이름이 든 구분선은 모듈 분리 신호로 읽는다 | PEP 8이 문단 구분 수단을 지정했다 · §2.8 행 6 |

**이 표의 어느 행에도 확실한 1차 출처가 없다.** §2.8 판정표와 달리 이것은 **의견**이며,
그 사실을 지우지 않는다.

---

## 11. `~/.claude/CLAUDE.md` §6 판정 — 항목별

정책 원문(사용자 홈의 전역 지침. 서문에서 밝힌 이유로 링크하지 않고 옮긴다):

> **Comment the *why*, not the *what*. Minimal by default — let code read itself.**
> - Language: code/identifiers English, prose 한글.
> - No comments that restate code (`i++  // increment i` 금지).
> - Comment only 꿀 설명 — non-obvious decisions, workarounds, edge cases, "왜 이렇게 했는지".
> - Prefer better names/smaller functions over comments. …
> - No commented-out dead code — delete it (git이 기억함).
> - Keep comments in sync with code. Stale comment worse than none.
> - Match the file's existing comment style and density.
> - Docstring required for public/exported functions only (args, return, 예외); private is optional.

| # | 조항 | 판정 | 근거 |
|---|---|---|---|
| 1 | "prose 한글" | ⚠️ **두 규범 텍스트와 어긋나고 근거가 없다** | PEP 8과 **GNU Coding Standards §5.2**가 영어를 요구하고, PEP 8의 "120% 확신" 예외는 public 원격에서 성립하지 않는다(§9.1). 정책 전환은 권고하지 않되(§9.4) **근거를 명문화할 것.** ★ 참고: 이 패턴 자체는 Pawelka & Jürgens가 측정한 실무 패턴과 정확히 일치한다(§9.3) — 흔하지만 지지받지는 않는다 |
| 2 | "private is optional" | ⚠️ **출처의 조건절이 잘려 있다** | PEP 8: *"not necessary for non-public methods, **but you should have a comment that describes what the method does**"*. Google은 nontrivial size·non-obvious logic도 필수로 본다(§4.2). **"private은 docstring 대신 주석"으로 고칠 것** |
| 3 | "No comments that restate code" | ✅ **출처 있음** | PEP 8 `# Increment x` 반례 · Google *"never describe the code"* · Ousterhout §13.2. 정책 예시가 `i++  // increment i`인데 **`//`는 파이썬 주석이 아니다** — 사소하지만 파이썬 정책에서 C 예시를 쓰는 것은 고칠 만하다 |
| 4 | "No commented-out dead code" | ✅ **출처 있고 이미 지켜진다** | `ERA001` **0건**(§5.4) · *Clean Code* bad comments `Commented-Out Code`. **정책이 옳고 코드가 따르고 있다** |
| 5 | "Keep comments in sync" | ✅ **출처 있음.** 단 ★ **기계가 도울 수 없고, 사람도 잘 못 한다** | PEP 8: *"worse than no comments"*. 낡음 탐지 도구는 **정밀도 64% · 재현율 17%** 수준이며 배포된 것이 없다(§6.2). 실증: 코드 변경의 **13~20%만** 주석 변경을 유발한다(§6.4) → **§6.3의 "같은 커밋" 절차가 필수** |
| 6 | "Comment the *why*, not the *what*" | ⚠️ **보편 합의가 아니다** | **Linux kernel이 정반대를 규정한다**(*"comments to tell WHAT your code does"*), Ousterhout는 *"what and why, not how"*, Google은 *"never describe the code"*(§2.6). **공통분모는 "HOW를 쓰지 않는다"뿐이다. 그 항을 추가할 것** |
| 7 | "Minimal by default" | ⚠️ **출처 없음. 단 측정 근거는 반대편보다 약간 낫다** | 어떤 1차 출처도 밀도를 규정하지 않고 Google은 *"you should comment it now"* 라 한다. 반면 시선추적 실험에서 주석 효과는 **12개 중 1개만 유의**했다(§2.5). **어느 쪽도 강하지 않으므로 밀도 논쟁을 하지 말고 §2.8의 내용 기준만 적용할 것** |
| 8 | "Docstring required … (args, return, 예외)" | ⚠️ **셋을 같은 급으로 놓았는데 1차 출처는 갈라 놓는다** | `args`의 **타입**은 PEP 484가 기각했고, `예외`는 PEP 484가 docstring에 **명시적으로 위임**했다(§3.3). **"args는 이름과 의미만, 타입은 애노테이션에, 예외는 반드시 `Raises:`"로 정밀화할 것.** 기계 강제 경로는 pydoclint `DOC111`이며 Ruff에는 없다 |
| 9 | (부재) **문서 참조 규율** | ❌ **누락. 이 저장소에서 5번 실패했다** | §7.1. 프로젝트 `CLAUDE.md`에 *"추적 문서는 `docs/plans/`를 링크하지 않는다"* 는 규칙이 있으나 **`.py`에 적용된 적이 없다.** 1차 지침이 존재한다 — Ousterhout *"Document each thing exactly once"* · SWE at Google *"designate canonical documentation"*(§7.5). 측정치도 있다 — 주석 링크의 **9.1%가 404**(§7.6) |
| 10 | (부재) **주석 줄 길이** | ❌ **누락** | PEP 8의 72자는 한글에 이식 불가하고(§1.3) 이 저장소의 실질 상한은 100이다(§5.2). 명문화하지 않으면 `W505`를 설정할 근거가 없다 |
| 11 | (부재) **HOW 금지** | ❌ **누락** | 판정 6 참조. 세 출처가 유일하게 합의하는 항목이 정책에 없다 |

★★ **가장 중요한 판정은 표 밖에 있다: 이 정책 자체가 클론에 가지 않는다.**
§6 "Comments"는 `~/.claude/CLAUDE.md`, 즉 **저장소 밖 사용자 홈**에 있다. 프로젝트 `CLAUDE.md`는
`.gitignore` 45행으로 제외된다. **주석 규율을 정한 문서가 §7이 진단한 것과 정확히 같은 실패 상태에
있다 — 참조 가능하지만 해소 불가능하다.**

그리고 §7.5의 1차 지침이 이 진단을 그대로 뒷받침한다:

- Ousterhout: *"It must be easy for people to find the right documentation at the right time"* ·
  *"Look for 'obvious' locations where people can easily find documentation"*
- SWE at Google: *"Documents without owners become stale"* · *"determine the primary source"*

→ **규율을 코드가 따라야 한다면 그 규율은 추적되는 곳에 있어야 한다. `docs/project/`가 그 자리다.**

---

## 12. 확인하지 못한 것

**이 절을 비워 두지 않는 것이 이 문서의 조건이다.**

### 12.1 논문·도서 — 접근 상태별

| 대상 | 상태 | 이 문서에 어떻게 반영했나 |
|---|---|---|
| **Storey et al., "TODO or to bug", ICSE 2008, pp.251–260** | ❌ **초록조차 열지 못했다** — Unpaywall `oa_status: closed`, 리포지터리 사본 없음, ACM 403, Semantic Scholar가 출판사 요청으로 초록 삭제 | **인용하지 않았다.** §6.5는 Potdar·Bavota·Maldonado·Wang으로만 세웠다. ⚠️ 검색엔진이 만들어 낸 *"97% of surveyed developers"* 는 **출처가 없으므로 절대 인용하지 말 것** |
| **Woodfield, Dunsmore & Shen, ICSE 1981, pp.215–223** | ⚠️ **초록만** — 전문은 2차 조사에서도 실패(ACM 403, Purdue e-Pubs cstech 인덱스 전수 스캔 0건, Internet Archive에 ICSE'81 회의록 없음, 저자 박사논문 ProQuest 게이팅). 초록은 OpenAlex 보관 ACM 레코드(`W2039603939`)로 확보 | §2.5.2. **주석 효과의 근거로 쓰지 않았다** — 초록이 주석에는 "significantly"를 붙이지 않는데 현대 인용들이 붙이고 있다는 **인용 결함의 증거로만** 썼다. ⚠️ 검색요약이 이 논문 언어를 "Fortran"이라 단정하는데 **초록에 언어 표기가 없다** — 인용 금지 |
| **Tenny, IEEE TSE 14(9):1271–1279, 1988** | ✅ **2차 조사에서 전문 확보** — IEEE는 여전히 페이월이나 scispace 호스팅 PDF를 리더 프록시로 통과. 러닝헤더로 진본 확인 | §2.5.3에 셀별 평균·SD·N과 `F(1,142)=4.34, p<0.05` 를 원문 인용으로 넣었다. **초판의 "열지 못했다"는 이 개정으로 해소됐다** |
| **Nielebock et al., EMSE 24(3), 2019 (N=277)** | ⚠️ **초록은 원문 확보, 본문은 여전히 미열람** — Springer 페이월 확정(Unpaywall `is_oa: false`), 저자 PDF 없음. 표본 구성(전문가 227 + 학생 50)은 Wyrich 재현패키지 row S27로 확인 | §2.5.5에 **초록 방향만** 반영했다. ★ **여전히 §2.5의 가장 큰 공백이다** — 표본이 가장 크고 유일하게 실무자 위주인데 조건별 점수·p값을 못 봤다 |
| ***A Philosophy of Software Design* 본문** | ⚠️ **원문 미열람**(유료). 목차는 **실물 ToC 스캔으로 검증** | §2.2는 **CS190 강의노트(저자 본인 1차)** 와 **aposd-vs-clean-code 문서(저자 승인 1차)** 로만 인용했다. **§13.1의 4종 분류와 "clutter" 표현은 인용부호를 씌우지 않았다.** §13.7 본문도 못 열었다 |
| **2판 목차** | ⚠️ **미확인** | §2.2에 판본 주의를 적었다. 저자 배포 2판 발췌 PDF는 받았으나 **벡터 윤곽선으로 그려져 텍스트 추출 불가**였다 |
| ***Clean Code* ch.4 본문 (pp.53–74)** | ⚠️ **원문 미열람.** 목차는 **출판사 샘플 PDF로 완전 검증** | §2.4의 "The proper use of comments…" p.54 인용은 **Ousterhout의 인용을 통한 것**이다. `Nonlocal Information`·`Position Markers` 항목은 **제목만** 근거다(§10.2에 명시) |
| ***Clean Code* 2판** | ❌ **미열람** | 인용하지 않았다 |
| **Knuth 1984 게재본** (CJ 27(2)) | ⚠️ **투고 원고 재조판본으로 대체** | §2.7에 밝혔다. 축자 정확성은 프리프린트 기준 |
| **Hata et al. ICSE 2019 게재본** | ⚠️ **arXiv 프리프린트 판독** | §7.6에 밝혔다. **RQ3(링크 목적) 분류 코드 목록은 추출하지 않았다** |
| **Koehler, *JASIST* 53(2), 2002** ("30%/4년") | ❌ **미열람** | Hata의 참조목록에서 서지만 확인. §7.6에서 Hata의 인용으로만 전달했다 |
| **Fluri WCRE 2007 판** | ⚠️ **폰트 인코딩 파손** — 표준 추출기가 숫자를 뭉갠다 | §6.4는 **SQJ 2009 판 본문 판독**에 근거한다. WCRE 판은 **인용 함정 경고에만** 썼다 |
| **Wen et al. ICPC 2019 — 요청했던 두 수치** | ⚠️ **논문에 없다** | (a) 불일치 **도입 vs 수정 빈도 비율**, (b) 불일치가 코드 변경 쪽인지 주석 변경 쪽인지의 분할 — 설계가 단방향이라 그 질문을 던지지 않는다. **§6.4에서 주장하지 않았다** |
| **Potdar & Shihab 내부 수치 불일치** | ⚠️ **재구성 실패** | 초록·결론의 제거율 상한 "63.5%"가 Table IX의 Apache 74.55%와 모순된다. **§6.5에 63.5%를 쓰지 않았다** |
| **Zhiyong Liu et al., COMPSAC 2018** | ❌ **미열람** | 인용하지 않았다. ⚠️ 문헌에서 **Zhongxin Liu(저장대, CUP)와 상습 혼동**된다 |
| **Takang, Grubb & Macredie, *J. Programming Languages* 4(3):143–167, 1996** | ✅ **2차 조사에서 전문 확보** — DOI 미등록. Wayback에 남은 King's College London 아카이브 PDF. 폰트 인코딩이 파손돼 글리프를 직접 디코드했다(단어 사이 공백 소실) | §2.5.3에 두 측정(객관식 p=0.003 / 주관 p=0.415)과 저자들의 한계 진술을 넣었다 |
| **CoCC의 "precision over 90%"** | ❌ **원 논문 특정 실패** | **절대 인용하지 말 것으로 표시한다** |
| **Ribeiro, dos Santos & Travassos, *EMSE* 28(6), 2023** — 가독성·이해도 국소연구 통합 | ❌ **초록조차 열지 못했다** — Springer 페이월, Unpaywall `is_oa: false`, Semantic Scholar가 출판사 요청으로 초록 삭제 명시 | **인용하지 않았다.** ★ **이 문서가 찾던 "주석-이해도 실험 메타분석"에 가장 가까운 후보인데 내용 확인 불가.** 같은 저자들의 선행 오픈액세스판(*CLEI Electronic Journal* 21(1), 2018)은 전문을 열었으나 Woodfield·Tenny·Takang을 참고문헌으로만 인용하고 수치를 재보고하지 않아 쓸 것이 없었다 |
| **Dunsmore 1985** (EFISS II 도서 챕터, Plenum Press, pp.189–196) | ❌ **전문·초록 모두 못 구했다** — 도서 챕터라 온라인 사본 없음 | **인용하지 않았다.** Abdelsalam et al.이 [30]으로 인용하며 Woodfield 실험의 후속으로 보이나 확인 불가 |
| **Nurvitadhi, Leung & Cook, FIE 2003 (N=103)** | ⚠️ **초록만** — IEEE 게이팅, CiteSeerX 404 | §2.5.1 판정표에 방향만 넣었다(method comments ✓ / class comments ✗). 조건별 점수·p값 없음. ⚠️ 2저자 미들네임이 OpenAlex(Wing Wah)와 Semantic Scholar(Wing-Pui)에서 **불일치**한다 |
| **Diátaxis / Divio 4분면** | ⚠️ **열었으나 §7에 쓰지 않았다** | 중복 문제를 직접 다루지 않는다. reference는 코드에서 생성, explanation은 코드 밖이라는 배치 원칙만 얻었고 §7.5의 세 출처로 충분했다 |

### 12.2 도구·설정 — 확인 상태

| 대상 | 상태 | 비고 |
|---|---|---|
| **Home Assistant가 `tests`를 `D`에서 면제하는가** | ⚠️ **미확인** | §4.3에서 **"`D`를 켜는 3곳 전부"라는 표현을 쓰지 않은 이유다.** pydantic·polars만 설정 원문으로 확인했다 |
| **`python -m ruff` 진입점** | ⚠️ **미확인** | §5.6은 `.venv/bin/ruff`를 쓰도록 고쳤다 |
| **`codes.rs`가 0.16.3과 일치하는가** | ⚠️ **부분 확인** | 규칙 목록은 `main` 소스에서 뽑았고 **설치본 0.16.3으로 실제 실행해 교차 확인**했다. 단 `D421`·`DOC102`는 **실행으로 확인하지 않았고 권고하지 않는다** |
| **`CPY001`** | ❌ **미실행** | 라이선스 헤더 정책이 없어 판단 대상이 아니다. 코드 존재는 `codes.rs`로 확인 |
| **`interrogate`의 "품질은 안 본다"는 명시 문언** | ⚠️ **문언 부재 확인** | README에 그런 문장이 **없다.** §6.2의 "존재만 본다"는 **도구 동작에서 추론**한 것이며 문언 인용이 아니다 |
| **`# noqa` 50건의 정당성** | ⚠️ **미검증, 그리고 현재 검증 불가** | §5.4. `F401`·`E402`·`BLE001`을 켜야 확인된다. §5.5는 이를 범위 밖으로 남겼다 |
| **pydoclint 실행** | ❌ **미실행** | §3.3의 `DOC111` 권고는 **문서 확인에만** 근거한다. 이 저장소에 돌려 보지 않았다 |
| **이 저장소의 `__all__`** | ✅ **부재 확인** | §4.1의 "public의 운영 정의는 밑줄뿐"이 여기서 나온다 |
| **마크다운 강조 19건**(브리핑 제시값) | ⚠️ **재현 실패 — 16건으로 정정** | §5.1 |

### 12.3 ⚠️ 방법론 경고 — 이번 조사에서 실제로 겪은 오답 4종

1. **웹 요약 도구가 `lint.pydocstyle.convention` 대응표에 존재하지 않는 코드(D220~D235)를
   나열했다.** → Ruff 소스를 직접 읽어 잡았다(§3.4).
2. **브리핑의 전제가 틀렸다** — Google 스타일 가이드 **§2.19는 "Power Features"이고 타입
   애노테이션은 §2.21**이다. → 스타일 가이드 전문을 읽어 잡았다.
3. **검색엔진이 존재하지 않는 논문을 만들어 냈다** — Fluri의 "Discovering, Reporting, and
   Merging…"과 Storey의 "TODO or To Bury"는 **그런 제목의 논문이 없다.** 실제는 각각
   Software Quality Journal 17(4) 2009(저자 4명)와 ICSE 2008 "TODO or to bug"다.
   ⚠️ **aComment는 ISSTA 2011이 아니라 ICSE 2011**이고, **Pawelka의 이름은 Matheus가 아니라
   Timo**다.
4. **검색엔진이 출처 없는 수치를 만들어 냈다** — Storey의 *"97% of surveyed developers"*.
   원 논문을 아무도 열 수 없는 상태에서 나온 값이므로 **인용 금지로 표시했다**(§12.1).

5. **2차 조사에서 추가로 걸러낸 것 — 이 주제 연구가 아닌 것들.** **Lutz Prechelt**에게는 주석-이해도
   통제실험이 **없다**(그의 실험은 프로그래밍 언어 비교와 pair programming이다). **Salvaneschi et al.**
   (reactive programming)과 **Rodeghero et al.** (ICSE 2014 아이트래킹)도 **주석 유/무를 조작한 실험이
   아니다.** ⚠️ 이 셋은 이 주제 문헌 목록에 자주 섞여 들어오므로 **인용 금지**로 표시한다.
6. **검색요약이 Tenny 1988을 "significant"라고만 요약했다** — 원문은 **"only in the absence of
   procedures"** 라는 조건을 달고 있다(§2.5.3). **조건을 떼면 논문이 하지 않은 주장이 된다.**

★ **그리고 문헌 자체에도 오류가 있다** — Bavota와 Maldonado가 둘 다 Potdar를 "five projects"로
오인용했다(실제 **4개**). CUP 논문은 Table 2(1612)와 본문(1672)이 어긋난다.
**"논문에 적혀 있다"가 "맞다"는 아니다.**

★★ **마지막으로, 이 문서가 스스로 지키는 구분: "규칙을 켰다"가 "검사됐다"는 아니다.**
§5.3이 그 실측이다 — 한글 docstring 271개가 `D401`을 조용히 통과했다. **린트 리포트의 0은 두 가지
뜻을 가지며, 리포트는 둘을 구별해 주지 않는다.** 이 문서에서 `ERA001` 0건만 "진짜 0"이라고 쓴
이유는 **별도로 시험했기 때문**이다(§5.4).
