# dut Constitution — 저장소 헌법

> dut 저장소 8개 프로젝트가 **엄격히 준수**하는 불변 원칙(무엇/왜). 구현 세부(어떻게)는 [`RULE.md`](./RULE.md).
> 모든 작업·PR은 머지 전 본 헌법 준수를 검증한다.

## Core Principles

### I. 프로젝트 독립성 (NON-NEGOTIABLE)

dut은 8개 **독립 프로젝트**의 모노레포다. 각 프로젝트는 의존성·실행 환경·언어가 독립적이다.

- 한 프로젝트 작업이 **다른 프로젝트 코드를 수정해서는 안 된다**. 작업 범위를 단일 프로젝트로 한정한다.
- 공유 대상은 공통 거버넌스(`docs/`, `.claude/`, 루트 설정 파일)뿐이다.
- 프로젝트 고유 문서(요구사항·설계·계획)는 해당 프로젝트 하위(`<프로젝트>/docs/`)에 둔다. 루트 `docs/`는 저장소 전체에 걸친 공통 문서 전용이다(→ §XIV).
- 8개 프로젝트: `aptiv_map_group_v8.1`(Python), `ingestion_map_folder_restructure`(Python), `pc_dashboard_service`(Node.js), `sampling_tool`(Python + Next.js), `storageops`(Python 3.11+ / FastAPI + CDN React 18), `dut_db`(Docker Compose + MySQL 8.4), `scripter`(Python 3.11 / uv 독립 관리), `data_qc`(Python 3.10+ / pandas·numpy·OpenCV).

### II. 기술 스택 경계

- **Python 프로젝트**(aptiv / ingestion / sampling / storageops / scripter / data_qc): **Python 3.10+**. storageops는 Python 3.11+ 필요(FastAPI 0.115 + uvicorn, 원격 Linux 서버), scripter는 Python 3.11(`.python-version`) + uv.
- **Node 프로젝트**(pc_dashboard_service): Node.js 20+, Express(backend) + React/CRA(frontend), **순수 JavaScript**(TypeScript 미사용).
- **storageops 프로젝트**: Python 3.11+(FastAPI 0.115 + uvicorn) + CDN React 18(Babel standalone, 빌드 없음). npm·Node.js 미사용. index.html은 브라우저 동작 확인으로 검증.
- `ruff` / `mypy`는 **Python 전용**(aptiv / ingestion / sampling / storageops / data_qc). Node는 ESLint(`react-app`) + `npm run build`로 검증.
- **scripter**: 자체 `pyproject.toml` + uv로 린트·의존성을 독립 관리한다(`uv run ruff check .`). 루트 pre-commit mypy 훅에서는 제외된다.
- 스택 변경은 ADR(`docs/architecture/adr/`) 기록 필수.

### III. Git·브랜치 전략 (→ RULE §1)

- `main` **직접 push 절대 금지**. feature 브랜치 생성 → 작업 → PR 병합만 허용.
- 브랜치 네이밍: `<type>/<scope>-<요약-kebab-case>`.
- 병합 완료 브랜치는 로컬·원격 모두 삭제.

### IV. 커밋 규칙 (→ RULE §2)

- **Conventional Commits**: `type(scope): 한국어 설명`. `type` = feat / fix / refactor / style / docs / test / chore.
- 기능 변경과 리팩토링은 **반드시 별도 커밋**으로 분리한다.

### V. 코딩 스타일 (→ RULE §3)

- **Python**: PEP 8, 최대 줄 길이 **120자**, 들여쓰기 공백 4칸, f-string 권장.
- **네이밍**: `snake_case`(파일/폴더/함수/변수/파라미터), `PascalCase`(클래스), `UPPER_SNAKE_CASE`(상수/Enum 멤버).
- **Node/React**: ESLint `react-app`, 들여쓰기 2칸, 컴포넌트 파일·함수명 PascalCase.

### VI. 타입 안전성 (→ RULE §6)

- 신규 Python 함수 시그니처에 **타입 힌트 필수**(파라미터 + 반환값).
- `mypy` 통과(신규 코드 기준). Python 3.10+ 문법 사용: `int | None`(not `Optional`), `list[str]`(not `List`).
- Node(순수 JS): mypy/tsc 미적용 — ESLint로 대체.

### VII. 주석·문서화 스타일

- 주석은 **WHY**가 자명하지 않을 때만 작성. WHAT을 설명하는 주석 금지.
- Docstring: 자명한 함수에는 작성 금지. 외부 API·복잡 알고리즘에만 한 줄 요약.

### VIII. 린트 — ruff (→ RULE §4)

- Python: `ruff check` **violation 0개** 유지, `ruff format` 적용 후 머지.
- 설정은 루트 `pyproject.toml [tool.ruff]`. Node 프로젝트·레거시 경로는 `extend-exclude`로 명시 제외.

### IX. 테스트 표준 (→ RULE §7)

- **기능 추가·버그 수정 시 테스트 작성 필수**.
- Python: `pytest`. Node: `npm run build` + 동작 검증.
- **커밋·push 전 해당 프로젝트 `pytest` 전체 통과 필수**(실패 0). 실패가 있는 상태로 커밋·push 절대 금지(NON-NEGOTIABLE).
- 커버리지 강제 게이트(`--cov-fail-under`)는 테스트 성숙 후 도입(현재 미적용).

### X. pre-commit (→ RULE §5)

- **저장소 clone 후 최초 1회 `pre-commit install` 필수 (NON-NEGOTIABLE)**. 미설치 시 커밋 게이트(ruff/mypy)가 우회되므로 헌법 위반으로 간주한다.
- 커밋 직전 pre-commit 자동 실행(ruff lint + ruff-format + mypy). 실패 시 커밋 차단.
- `--no-verify` 플래그 사용 **절대 금지**. 훅 실패는 원인 해결 후 재커밋.

### XI. 버전 관리·릴리스 (→ RULE §10)

- **Semantic Versioning** `a.b.c`. 각 프로젝트는 자체 버전을 가진다.
  - `a`(MAJOR): 큰 변화. `b`(MINOR): 기능 추가. `c`(PATCH): 버그 픽스·소규모 업데이트.
- 다중 버전 표기는 동시 갱신(예: `sampling_tool/consts.py` VERSION ↔ `web/package.json`).
- **Docker 이미지 배포 시 3개 태그 동시 push 필수**: `<version>`(정확한 버전) + `latest`(검증 완료·운영 사용 가능) + `<shortSHA>`(Git 커밋 매핑 7자). 세부는 RULE §10.
- 헌법 변경 시 버전 증가 + 근거 기록.

### XII. 레거시·dead code 경계

- 알려진 dead code/레거시는 **무비판 참조·수정 금지**:
  - `sampling_tool`: `controls/`, `rest/`, 일부 `dto/`(실행 불가) → 신규 작업은 `pipelines/`·`api/`·`util/`.
  - `ingestion_map_folder_restructure`: `preview_structure.py`, `analyze_groups.py`(구 스키마) → 운영 기준은 `restructure_folders.py`.
  - `data_qc`: `trajectory_analysis/`(import만 살아있고 호출은 주석 처리된 죽은 모듈) → ruff·mypy `exclude` 등록.
- 레거시 수정이 필요하면 별도 리팩토링 PR + ADR로 처리한다.

### XIII. 보안

- 평문 시크릿·자격증명(API 키·비밀번호·토큰) **코드·문서 노출 절대 금지** → `.env` + 환경변수.
- `.gitignore`에 `.env`·시크릿 파일 등록. `.claude/` 하네스(skills/agents/CLAUDE.md)는 추적하되 `settings.local.json`만 무시.
- SQL은 **parameterized query 필수**(문자열 보간 금지). 외부 입력은 검증 후 사용.

### XIV. 문서 언어 및 참조 표준

- 주석·문서·커밋 메시지는 **한국어 필수**(기술 용어 영문 병기 허용).
- 참조 순서: `docs/CONSTITUTION.md` → `docs/RULE.md` → 해당 프로젝트 `AGENTS.md`.
- 문서 위치: 요구사항 `user_requests/`, 설계 `specs/`, 계획 `plans/`, 결정 `architecture/adr/`.
  - **기준점**: 프로젝트 고유 문서는 `<프로젝트>/docs/` 하위, 저장소 전체 공통 문서만 루트 `docs/` 하위(§I). 예) `data_qc/docs/specs/`, `storageops/docs/plans/` ↔ 루트 `docs/specs/SPEC-20260622-governance-dedup.md`.
  - ADR은 저장소 전체 결정이므로 항상 루트 `docs/architecture/adr/`.

---

## Governance

본 헌법은 dut 저장소 8개 프로젝트 공통의 불변 원칙을 정의한다.
원칙 변경 시 근거 문서화 및 버전 번호 증가가 필수다.
모든 PR과 기능 스펙은 머지 전 본 헌법 준수 여부를 검증해야 한다(체크리스트: `RULE.md §8`).
구현 세부 패턴은 `docs/RULE.md`를 따른다.

**Version**: 1.2.0 | **Ratified**: 2026-06-18 | **Amended**: 2026-08-08 (§I 프로젝트 6개 → 8개 — `scripter`(PR #23 편입 시 문서 미갱신분 소급 반영)·`data_qc` 등재 + 프로젝트 고유 문서 위치 규정 신설; §II scripter uv 독립 관리·data_qc ruff/mypy 대상 명시; §XII `data_qc/trajectory_analysis` dead code 등재; §XIV 문서 위치 기준점 명확화)

> 이전 개정: 1.1.0 — 2026-06-23 (§XI 버전 관리·릴리스 — semver 자리 정의 + Docker 3-태그 동시 push 규칙; §IX 커밋·push 전 pytest 전체 통과 게이트 추가)
