# dut Implementation Rules — 구현 세부 패턴

> **헌법(CONSTITUTION.md)이 "무엇/왜"라면, 본 문서는 "어떻게"다.**
> 헌법 각 원칙이 본 문서 해당 섹션을 참조한다. 원칙의 근거는 `docs/CONSTITUTION.md`에서 확인하라.
> 구현 전 반드시 `docs/CONSTITUTION.md` → 본 문서 → 해당 `AGENTS.md` 순으로 참조할 것.

---

## 목차

1. [브랜치 네이밍](#1-브랜치-네이밍-헌법-iii)
2. [커밋 메시지](#2-커밋-메시지-헌법-iv)
3. [코드 스타일 상세](#3-코드-스타일-상세-헌법-v-vii)
4. [ruff 설정·실행](#4-ruff-설정실행-헌법-viii)
5. [pre-commit 셋업](#5-pre-commit-셋업-헌법-x)
6. [typecheck 실행](#6-typecheck-실행-헌법-vi)
7. [프로젝트별 테스트 실행법](#7-프로젝트별-테스트-실행법-헌법-ix)
8. [PR 체크리스트](#8-pr-체크리스트-헌법-전-원칙-게이트)
9. [Definition of Done](#9-definition-of-done--완료-기준)
10. [버전 관리·릴리스](#10-버전-관리릴리스-헌법-xi)

---

## 1. 브랜치 네이밍 (헌법 §III)

### 패턴

```
<type>/<scope>-<요약-kebab-case>
```

| 필드 | 허용값 | 설명 |
|------|--------|------|
| `type` | `feat` / `fix` / `refactor` / `style` / `docs` / `test` / `chore` | Conventional Commits type |
| `scope` | 프로젝트 약칭 또는 모듈명 | `aptiv` / `ingestion` / `pc-dashboard` / `sampling` / `docs` / `ci` 등 |
| `요약` | 영문 소문자 kebab-case | 작업 내용 2~5 단어 |

### 예시

```
feat/sampling-axera-overlay
fix/pc-dashboard-socket-reconnect
refactor/aptiv-group-id-split
docs/rule-initial
test/ingestion-restructure-dry-run
chore/pre-commit-setup
```

### 규칙

- `main` 직접 push **절대 금지**. feature 브랜치 생성 → 작업 → PR 병합만 허용.
- 브랜치 이름에 이슈 번호 포함 권장 (예: `feat/sampling-axera-overlay-#42`).
- 오래된 병합 브랜치는 로컬·원격 모두 삭제(혼란 방지).

---

## 2. 커밋 메시지 (헌법 §IV)

### 포맷

```
type(scope): 한국어 설명

[선택] 본문 — WHY, 변경 맥락, 참조 이슈. 72자 줄바꿈.

[선택] Co-Authored-By: <name> <email>
```

| 필드 | 규칙 |
|------|------|
| `type` | feat / fix / refactor / style / docs / test / chore |
| `scope` | 프로젝트 약칭(aptiv/ingestion/pc-dashboard/sampling) 또는 모듈명 |
| 설명 | **한국어** 필수. 현재형 동사로 시작. 명사형 종결 금지 ("추가됨" 아닌 "추가"). |

### 좋은 예

```
feat(sampling): AXERA 파이프라인에 오버레이 생성 단계 추가

RAW 변환 결과에 바운딩박스 오버레이를 합성한다.
기존 convert_raw_to_image() 시그니처 유지, overlay 파라미터 기본 False.
```

```
fix(pc-dashboard): 소켓 재연결 시 중복 이벤트 리스너 등록 방지
```

```
refactor(aptiv): group_id 분리 로직을 parse_group_id() 함수로 추출
```

### 나쁜 예

```
# 영문 설명 — 한국어 필수
feat(sampling): add AXERA overlay generation

# scope 없음 — 어느 프로젝트인지 불명확
feat: 오버레이 추가

# 기능+리팩토링 혼합 — 별도 커밋으로 분리할 것
feat(aptiv): 그룹 파싱 추가 및 기존 코드 정리
```

### 리팩토링 분리 원칙

기능 변경과 리팩토링은 **반드시 별도 커밋**으로 분리한다.
리뷰어가 동작 변경과 코드 정리를 구분할 수 있어야 한다.

---

## 3. 코드 스타일 상세 (헌법 §V, §VII)

### Python (Python 프로젝트 공통)

| 항목 | 규칙 |
|------|------|
| 최대 줄 길이 | 120자 (`pyproject.toml` `line-length = 120`) |
| 들여쓰기 | 공백 4칸 |
| import 정렬 | ruff isort(`I` 룰) 자동 적용 |
| 문자열 | f-string 권장 (Python 3.10+) |
| 주석 | **WHY만** 작성. WHAT 설명 ("변수를 초기화한다") 금지. |
| docstring | 자명한 내용 금지. 외부 API·복잡 알고리즘에만 작성. |

**네이밍:**

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일 / 폴더 / 함수 / 변수 / 파라미터 | `snake_case` | `parse_group_id`, `output_path` |
| 클래스 | `PascalCase` | `SamplingJob`, `GroupMapper` |
| 상수 / Enum 멤버 | `UPPER_SNAKE_CASE` | `MAX_WORKERS`, `DRY_RUN` |

### Node / React (`pc_dashboard_service`)

| 항목 | 규칙 |
|------|------|
| ESLint | `react-app` config 준수 (`eslint-config-react-app`) |
| 들여쓰기 | 공백 2칸 |
| 컴포넌트 | PascalCase 파일명·함수명 |
| ruff / mypy | **미적용** — `npm run build` + ESLint 경고로 검증 |

---

## 4. ruff 설정·실행 (헌법 §VIII)

### 설정 위치

루트 `pyproject.toml` `[tool.ruff]` 섹션. **Node 프로젝트는 `extend-exclude`로 명시 제외.**
`scripter`는 자체 `pyproject.toml` + uv로 린트를 독립 관리한다(헌법 §II) — 루트 ruff 실행 명령 대상이 아니다.

```toml
[tool.ruff]
line-length = 120
target-version = "py310"
extend-exclude = [
    "pc_dashboard_service",          # Node 프로젝트 — ruff 미적용
    "node_modules", "build", "dist", ".next", "out",
    ".venv", "venv",
    "sampling_tool/controls", # dead code (헌법 §XII)
    "sampling_tool/rest",
    "ingestion_map_folder_restructure/preview_structure.py",
    "ingestion_map_folder_restructure/analyze_groups.py",
    "data_qc/trajectory_analysis",
]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
# E: pycodestyle  F: pyflakes  I: isort  UP: pyupgrade  B: bugbear
extend-ignore = ["E501"]   # 줄 길이는 ruff format이 관리
```

### 실행 명령

```bash
# 린트 검사 (violation 0 유지)
ruff check aptiv_map_group_v8.1 ingestion_map_folder_restructure sampling_tool data_qc

# 자동 수정 가능한 violation 수정
ruff check --fix aptiv_map_group_v8.1 ingestion_map_folder_restructure sampling_tool data_qc

# 포맷 적용
ruff format aptiv_map_group_v8.1 ingestion_map_folder_restructure sampling_tool data_qc

# 커밋 전 최종 확인 (violation 0 필수)
ruff check aptiv_map_group_v8.1 ingestion_map_folder_restructure sampling_tool data_qc \
  && echo "ruff clean"

# scripter — 자체 uv 환경에서 독립 실행
cd scripter && uv run ruff check .
```

> `pc_dashboard_service`는 ruff 대상이 아니다. Node 빌드 검증은 §7 참조.
> `scripter`는 위 루트 명령 대상이 아니다 — `uv run ruff check .`로 검사한다(§7 scripter).

---

## 5. pre-commit 셋업 (헌법 §X)

### 초기 설치 (필수 — clone 후 즉시)

> **모든 기여자는 저장소 clone 직후 `pre-commit install`을 반드시 실행한다.**
> 미설치 시 커밋 게이트(ruff/mypy)가 우회되어 헌법 §X 위반이 된다. 선택이 아닌 의무다.

```bash
# pre-commit 설치 (uv 권장)
uv tool install pre-commit
# 또는
pip install pre-commit

# 훅 등록 (저장소 clone 후 1회 — 필수, 미실행 시 게이트 무효)
pre-commit install
```

### 훅 구성 (루트 `.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.10
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, pandas-stubs, types-PyMySQL]
        exclude: >
          (?x)^(
            pc_dashboard_service/|
            dut_db/qumulo_to_db/|
            .*(controls|rest)/|
            ingestion_map_folder_restructure/(preview_structure|analyze_groups)\.py|
            scripter/|
            data_qc/trajectory_analysis/
          )$
```

> `scripter`는 uv 독립 관리 프로젝트이므로 mypy 훅에서 제외된다(헌법 §II). ruff 훅은 그대로 적용된다.
> `data_qc/trajectory_analysis/`는 dead code이므로 ruff·mypy 양쪽에서 제외된다(헌법 §XII).

### 실행 명령

```bash
# 전체 파일 검사 (CI 또는 설정 변경 후)
pre-commit run --all-files

# 커밋 시 자동 실행됨 (별도 명령 불필요)
git commit -m "feat(sampling): ..."

# hook rev 갱신 (주기적 권장)
pre-commit autoupdate
```

### 규칙

- `--no-verify` 플래그 사용 **절대 금지**.
- 훅 실패 시 원인 해결 후 재커밋. 실패 무시 불가.

---

## 6. typecheck 실행 (헌법 §VI)

**선택 도구: mypy** (성숙·안정, Python 3.10+ 완전 지원, CI 보편적)

> ty(astral)는 2026년 기준 pre-1.0 alpha 수준 — 운영 거버넌스 도구로 채택하지 않는다.
> `pc_dashboard_service`는 TypeScript 미사용(순수 JS) 이므로 mypy/tsc 미적용. ESLint만 사용.

### 설정 위치

루트 `pyproject.toml` `[tool.mypy]` 섹션:

```toml
[tool.mypy]
python_version = "3.10"
ignore_missing_imports = true     # 레거시·stub 부재 친화
check_untyped_defs = true
warn_redundant_casts = true
warn_unused_ignores = true
exclude = [
    'pc_dashboard_service/',
    'dut_db/qumulo_to_db/',
    '(controls|rest)/',
    'preview_structure\.py',
    'analyze_groups\.py',
    'data_qc/trajectory_analysis/',
]

# 점진 강화: 신규 작업 모듈 (추후 disallow_untyped_defs = true로 승급)
[[tool.mypy.overrides]]
module = ["sampling_tool.api.*", "sampling_tool.pipelines.*"]
disallow_untyped_defs = false
```

### 실행 명령

```bash
# 프로젝트별 독립 실행 (헌법 §I 프로젝트 독립성)
mypy aptiv_map_group_v8.1/src
mypy ingestion_map_folder_restructure \
  --exclude preview_structure --exclude analyze_groups
mypy sampling_tool/api sampling_tool/pipelines sampling_tool/util
mypy data_qc   # trajectory_analysis/는 exclude 등록됨 (헌법 §XII)

# pc_dashboard_service: mypy 미적용 (Node 프로젝트)
# scripter: mypy 미적용 (uv 독립 관리 — pre-commit mypy 훅 제외, 헌법 §II)
```

### 타입힌트 작성 규칙

- 신규 함수 시그니처에는 **반드시** 타입힌트 작성 (파라미터 + 반환값).
- Python 3.10+ 문법 사용: `int | None` (not `Optional[int]`), `list[str]` (not `List[str]`).

### 점진 강화 정책

| 단계 | 적용 대상 | 설정 |
|------|----------|------|
| 현재 (관대) | 전체 | `ignore_missing_imports=true`, `check_untyped_defs=true` |
| 다음 (신규 코드 엄격) | 신규 함수/모듈 | 파라미터+반환 타입힌트 필수. mypy override로 강화. |
| 미래 (전체 엄격) | 프로젝트 전체 | `disallow_untyped_defs=true` (프로젝트별 준비 완료 후 선언) |

---

## 7. 프로젝트별 테스트 실행법 (헌법 §IX)

### aptiv_map_group_v8.1

```bash
# 단위 테스트 (신규 작성 시 실행)
pytest aptiv_map_group_v8.1/tests -v

# 기능 검증 (대화형)
python -m src.production
```

> 현재 `tests/` 디렉토리 없음 — 신규 함수 작성 시 `aptiv_map_group_v8.1/tests/` 생성하여 pytest 추가.

### ingestion_map_folder_restructure

```bash
# 단위 테스트
pytest ingestion_map_folder_restructure/tests -v

# 수동 검증 — DRY_RUN=True 선행 필수 (False 직접 실행 시 대량 파일 복사 발생)
DRY_RUN=True uv run ingestion_map_folder_restructure/restructure_folders.py

# 결과 확인 후 실제 실행
DRY_RUN=False uv run ingestion_map_folder_restructure/restructure_folders.py
```

> 운영 코드는 `restructure_folders.py` **단 하나**.
> `preview_structure.py` / `analyze_groups.py` / `plan.md` / `solution_analysis.md`는 레거시 — 수정·실행 금지.

### pc_dashboard_service

```bash
# 백엔드 기동 및 API 검증
node pc_dashboard_service/backend/server.js
curl http://localhost:8092/api/resource-hw

# 프론트엔드 빌드 검증 (PR 머지 전 필수)
cd pc_dashboard_service/frontend && npm run build

# 통합 개발 서버 기동 (backend 8092 + frontend 8093)
cd pc_dashboard_service && npm run dev
```

> **서버 혼용 금지**: `server.js`(prod, 포트 8092) vs `server.dev.js`(dev, 포트 8082) — 동작·포트 다름.
> ruff/mypy 미적용. ESLint 경고는 `npm run build` 출력으로 확인.

### sampling_tool

```bash
# 단위 테스트 (tests/ 디렉토리 신규 생성 필요)
pytest sampling_tool/tests -v

# CLI 실행 검증
python sampling_tool/sampling_tool.py run \
  --path /data/lidar \
  --data-type LIDAR_POINTCLOUD \
  --output /tmp/output

# E2E (Docker Compose)
cd sampling_tool && docker-compose up

# API 서버 기동 (FastAPI)
cd sampling_tool && uvicorn api.main:app --reload
```

> 신규 작업 위치: `pipelines/` · `api/` · `util/`.
> `controls/` · `rest/` · 일부 `dto/`는 dead code — 무비판 참조·수정 금지.
>
> **버전 동기화**: `main()` 시그니처 변경 시 CLI run 커맨드 + API `_run_job()` **양쪽** 갱신 필수.
> 버전 변경 시 `sampling_tool/consts.py VERSION` + `web/package.json` **동시** 갱신.

### dut_db

```bash
# Qumulo 적재 패키지
python -m unittest discover -s dut_db/qumulo_to_db -p "test_*.py" -v

# Qumulo naming/structure 검증 패키지
python -m unittest discover -s dut_db/qumulo_naming_validator -p "test_*.py" -v

# Qumulo-DLM 취득시간 통계 패키지
python -m unittest discover -s dut_db/qumulo_dlm_acquisition_stats -p "test_*.py" -v
python dut_db/qumulo_dlm_acquisition_stats/apply_acq_stat_schema.py --dry-run

# DLM Excel current-state 적재 패키지
python -m unittest discover -s dut_db/dlm_excel_to_db -p "test_*.py" -v
python dut_db/dlm_excel_to_db/import_dlm_workbook.py --xlsx "<Data_Lifecycle_Management.xlsx>" --dry-run
```

> `qumulo_dlm_acquisition_stats`의 Excel loader 검증은 원본 workbook을 커밋하지 않고 `--xlsx`로 전달해 dry-run한다. 라이브 DB 적용은 별도 운영 검증이다.

### storageops

```bash
# 린트/포맷 (Python — pyproject.toml 루트 설정 적용)
ruff check storageops/
ruff check storageops/ --fix   # 자동 수정 가능한 violation 처리
ruff format storageops/

# 타입 체크 (신규 코드 기준)
mypy storageops/server.py

# pre-commit 전체 검사
pre-commit run --all-files

# 서버 실행 (원격 Linux에서)
cd storageops && bash run.sh
# 또는 개발 모드 (파일 변경 시 자동 재시작)
uvicorn server:app --host 127.0.0.1 --port 8765 --reload

# 테스트 (기능 추가·버그 수정 시 필수)
pytest storageops/tests -v
```

> `index.html`(CDN React 18): 빌드 없음 — 브라우저 동작 확인으로 검증(SSH 터널 → http://localhost:8765).
> 원격 서버 배포: `bash storageops/run.sh` (venv 자동 생성·uvicorn 기동).
> `storageops/tests/` 디렉토리 없음 → 신규 기능 추가 시 생성하여 pytest 추가.

### scripter

```bash
# 린트/포맷 (자체 pyproject.toml + uv — 루트 ruff 명령 대상 아님)
cd scripter && uv run ruff check .
cd scripter && uv run ruff format .

# 의존성 동기화
cd scripter && uv sync

# 단위 테스트 (unittest 기반)
cd scripter && uv run python -m unittest discover -s tests -v

# 스크립트 실행 (각 스크립트 단독 실행)
cd scripter && uv run python organizer.py <소스_경로> --output <출력_루트> ...
```

> Python 3.11(`.python-version`) + uv로 의존성·린트를 **독립 관리**한다(헌법 §II).
> 루트 pre-commit **mypy 훅에서 제외**된다(ruff 훅은 적용).
> 주요 스크립트: `organizer.py`(수집 폴더 표준 구조 복사·정리) · `parking_detector.py` · `parking_stopper_detector.py` · `hcp_delete.py` · `s3_usage.py` · `aptiv_parking_slots_counter.py` · `video_duration_report.py`.
> 파괴적 동작(복사·이동·삭제)은 `--dry-run` 선행 검증 필수. 상세는 `scripter/AGENTS.md`·`scripter/README.md`.

### data_qc

```bash
# 린트/포맷 (루트 pyproject.toml 설정 적용)
ruff check data_qc
ruff format data_qc

# 타입 체크
mypy data_qc

# 단위 테스트 (tests/ 디렉토리 신규 생성 필요)
pytest data_qc/tests -v

# 배치 실행 — main.py 하단 root_dirs에 검증 대상 경로 지정 후 실행
cd data_qc && python main.py
```

> CAN 데이터·카메라 파라미터·영상 품질 점검 도구(구 `can_validation`, 퇴사자 인수인계분).
> Python 3.10+ / pandas · numpy · OpenCV(cv2) · matplotlib.
> `trajectory_analysis/`는 dead code — ruff·mypy `exclude` 등록(헌법 §XII). 무비판 참조·수정 금지.
> **온보딩 진행 중**: ruff violation 정비·테스트 신설이 남아 있다. 신규 코드에는 violation 0·타입힌트 필수 기준을 그대로 적용한다.
> 설계·요구사항 문서는 `data_qc/docs/specs/`·`data_qc/docs/user_requests/`(헌법 §XIV).

---

## 8. PR 체크리스트 (헌법 전 원칙 게이트)

PR 생성 전 아래 항목을 모두 확인한다. 미충족 항목이 있으면 해결 후 병합 요청한다.

```
[ ] feature 브랜치에서 작업 (main 직접 push 아님)
[ ] 브랜치 네이밍 패턴 준수 (<type>/<scope>-<요약>)
[ ] 커밋 메시지 Conventional Commits 포맷 + 한국어 설명
[ ] 리팩토링과 기능 변경 별도 커밋으로 분리됨
[ ] (Python) ruff check violation 0개 확인
[ ] (Python) ruff format 적용 완료
[ ] (Python) mypy 신규 코드 통과
[ ] (Python) pre-commit run --all-files 통과
[ ] (Node) cd frontend && npm run build 성공 및 ESLint 경고 확인
[ ] 기능 추가·버그 수정 시 테스트 작성 및 통과
[ ] 커밋·push 전 해당 프로젝트 pytest 전체 통과 (실패 0 — 실패 상태 커밋·push 금지)
[ ] 비밀 정보(API 키·토큰·비밀번호·자격증명) 미포함
[ ] 단일 프로젝트 범위 (타 프로젝트 코드 미변경)
[ ] 레거시·dead code 무비판 참조·수정 안 함
[ ] 문서·주석·커밋 메시지 한국어 작성
[ ] CONSTITUTION 신규 위반 없음
[ ] .gitignore에 .env·시크릿 파일 등록 확인
```

> **주의 — `.gitignore` 화이트리스트 필요**: 현재 `.gitignore`가 `.claude/` 전체를 무시하고 있다.
> `.claude/skills/` · `.claude/agents/` · `.claude/CLAUDE.md`는 팀 공유 대상이므로 커밋되어야 한다.
> 수정 방법: `.claude/settings.local.json` · `.omc/`만 무시하고,
> `!.claude/` · `!.claude/skills/` · `!.claude/agents/` · `!.claude/CLAUDE.md`를 화이트리스트로 추가할 것.

---

## 9. Definition of Done — 완료 기준

하나라도 미달이면 완료가 아니다. 원인 해결 후 재검증한다.

프로젝트군이 8개로 늘어 게이트를 열이 아닌 **행 기준**으로 정리한다.

| 프로젝트군 | 린트·포맷 | 타입 | pre-commit | 테스트 | 동작 | 보안 |
|-----------|----------|------|-----------|--------|------|------|
| Python (aptiv / ingestion / sampling / data_qc) | `ruff check` violation **0** + `ruff format` 적용 | `mypy` 신규 코드 통과 | `pre-commit run --all-files` 통과 | `pytest` 통과 (기능 추가·버그 수정 시 필수) | 수동 또는 자동 검증 완료 | 시크릿 미노출, SQL parameterized query 사용 |
| storageops | `ruff check storageops/` violation **0** + `ruff format storageops/` 적용 | `mypy storageops/server.py` 신규 코드 통과 | `pre-commit run --all-files` 통과 | `pytest storageops/tests` 통과 (기능 추가·버그 수정 시 필수) | 브라우저 동작 확인 (SSH 터널 → http://localhost:8765) | 시크릿 미노출 (config.yaml에 자격증명 없음) |
| scripter | `uv run ruff check .` violation **0** + `uv run ruff format .` 적용 | — (mypy 훅 제외, 헌법 §II) | ruff 훅만 적용 (mypy 훅 제외) | `uv run python -m unittest discover -s tests` 통과 | `--dry-run` 선행 검증 완료 | 시크릿 미노출 (S3/HCP 자격증명은 `.env`·`~/.aws/credentials`) |
| Node (pc_dashboard) | `npm run build`에서 ESLint 경고 확인 | — (TypeScript 미사용) | — | `npm run build` 성공 | 수동 동작 확인 | 시크릿 미노출 |

> **data_qc 온보딩 예외 없음**: 온보딩 중이라 기존 코드에 ruff violation·테스트 부재가 남아 있으나, **신규·수정 코드는 위 게이트를 그대로 충족**해야 한다. 정비 작업은 별도 PR로 진행한다.

> **커밋·push 게이트**: 커밋·push 전 해당 프로젝트 `pytest` 전체가 **완벽히 통과**(실패 0)해야 한다.
> 실패가 남은 상태로 커밋·push 금지(헌법 §IX). pre-commit(ruff/mypy)와 별개로 수동 또는 CI에서 확인한다.
>
> **커버리지 게이트(`--cov-fail-under`)는 현재 미적용.**
> dut 대부분 프로젝트가 테스트 부재 상태이므로 강제 적용 시 모든 PR이 차단된다.
> 프로젝트별 테스트 성숙 후 `pyproject.toml`에 `addopts = ["--cov-fail-under=60"]` 추가 예정.

---

## 10. 버전 관리·릴리스 (헌법 §XI)

### Semantic Versioning — `a.b.c`

S.W. 버전을 `a.b.c`로 표기할 때 각 자리는 다음과 같이 정의한다. 각 프로젝트는 자체 버전을 독립적으로 관리한다(헌법 §I).

| 자리 | 이름 | 증가 조건 | 예시 |
|------|------|-----------|------|
| `a` | Main (MAJOR) | 큰 변화가 있을 때 | 하위호환 깨짐, 아키텍처 전환, 대규모 재설계 |
| `b` | Minor (MINOR) | 새로운 기능이 추가되었을 때 | 신규 파이프라인 단계, 신규 API 엔드포인트 |
| `c` | Patch (PATCH) | Minor 기준 업데이트·버그 픽스가 있을 때 | 버그 수정, 소규모 보정, 의존성 패치 |

> **다중 버전 표기 동시 갱신**: 한 프로젝트가 버전을 여러 곳에 기록하면 **반드시 동시 갱신**한다.
> 예) `sampling_tool`: `consts.py` `VERSION` ↔ `web/package.json` `version`.

### Docker 이미지 배포 — 3개 태그 동시 push (필수)

Docker 이미지를 배포하는 프로젝트(`pc_dashboard_service`·`sampling_tool`)는 배포 시 아래 **3개 태그를 동시에 push**한다.

| 태그 | 의미 | 형식·예시 |
|------|------|-----------|
| `<version>` | 현재 툴의 **정확한 버전** 명시 | `1.0.0` |
| `latest` | **최신 툴** 명시. **검증 완료되어 운영 인원이 사용해도 무방한 상태**여야 함 | `latest` |
| `<shortSHA>` | Docker 이미지 ↔ **Git 커밋 매핑** 식별용(빌드 아티팩트 추적) | `7b9f8d1` (7자 short SHA) |

```bash
# 배포 예시 — 3개 태그 동시 push
VERSION=1.0.0
SHORT_SHA=$(git rev-parse --short HEAD)   # 예: 7b9f8d1
IMAGE=<registry>/<image-name>

docker build -t "$IMAGE:$VERSION" .
docker tag "$IMAGE:$VERSION" "$IMAGE:latest"
docker tag "$IMAGE:$VERSION" "$IMAGE:$SHORT_SHA"

docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"
docker push "$IMAGE:$SHORT_SHA"
```

### 규칙

- `latest` 태그는 **검증 완료 상태에서만** 갱신한다. 미검증 빌드를 `latest`로 올리지 않는다(운영 인원이 신뢰하는 태그).
- `<version>` 태그는 **불변(immutable)** — 동일 버전 재배포 시 코드가 바뀌면 PATCH를 올린다. 같은 버전 태그 덮어쓰기 금지.
- `<shortSHA>`는 `git rev-parse --short HEAD` 결과(기본 7자). 빌드 시점 커밋과 이미지를 1:1 매핑해 롤백·추적에 사용한다.
- 헌법 변경 시 `CONSTITUTION.md` 하단 **Version** 증가 + 근거를 ADR/progress에 기록한다.

---

*최종 갱신: 2026-08-08 | 헌법 버전 참조: CONSTITUTION.md v1.2.0*
