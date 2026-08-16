<!-- Generated: 2026-08-16 -->

# misc_converter v1 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스펙([SPEC-20260816-misc-converter-design.md](../specs/SPEC-20260816-misc-converter-design.md))의 v1 — 블랙박스 변환 도구 4종을 감싸는 엔진 + 어댑터 + CLI + 웹 서비스 + Wine 스파이크 이미지를 dut_test 저장소에 구현한다.

**Architecture:** 표준 라이브러리만 쓰는 엔진(스캔→스킵→실행→검증→재시도→리포트)이 중심. 어댑터는 도구별 선언(입력 패턴·argv·기대 산출물·검증·실패 시 재시도 옵션), 백엔드는 실행 환경(local/wine/docker)별 argv·경로 변환. CLI와 FastAPI 웹은 엔진 위 얇은 껍데기. 성공 판정은 exit code가 아니라 산출물 존재.

**Tech Stack:** Python 3.10+, argparse, subprocess, ThreadPoolExecutor, sqlite3, FastAPI + uvicorn(웹만), 단일 index.html(CDN React 18), pytest, ruff, mypy, pre-commit, Docker(Wine 스파이크).

---

## 파일 구조

| 경로 | 책임 |
|---|---|
| `misc_converter/__init__.py` | `VERSION` |
| `misc_converter/__main__.py` | `python -m misc_converter` → `cli.main()` |
| `misc_converter/config.py` | `Config` 데이터클래스 + `config.json` 로드(도구 경로·마운트·wine·docker) |
| `misc_converter/paths.py` | `PathMapper` — UNC/Windows/Linux/Wine 경로 상호 변환 |
| `misc_converter/engine/models.py` | `WorkItem`, `ItemResult`, `FailureKind`, `RunSummary` |
| `misc_converter/engine/scanner.py` | 입력 트리 스캔, 어댑터 패턴 매칭, 스킵 판정 |
| `misc_converter/engine/runner.py` | 항목 1건 실행: subprocess, 타임아웃, 실패 분류, 재시도, 검증 |
| `misc_converter/engine/report.py` | 실행 로그 + JSON 요약 작성 |
| `misc_converter/engine/orchestrator.py` | `run_job()` — 스캔→병렬 실행→리포트, 진행 콜백 |
| `misc_converter/backends/base.py` | `Backend` 프로토콜: `wrap(argv)`, `tool_path(path)` |
| `misc_converter/backends/local.py` / `wine.py` / `docker.py` | 각 백엔드 구현 |
| `misc_converter/adapters/base.py` | `Adapter` ABC + `OptionSpec` |
| `misc_converter/adapters/aptiv.py` | AptivFileConversion(라이터 7종 테이블) |
| `misc_converter/adapters/djlp.py` | DJLPConvertTool(argv 템플릿 설정형) |
| `misc_converter/adapters/csv_extractor.py` | txt2csv + ccan/pcan 자동 스왑 |
| `misc_converter/adapters/pcap2pcd.py` | docker 변환기 + convert_log.json 판정 + 미완성 tar 정리 |
| `misc_converter/adapters/__init__.py` | `ADAPTERS` 레지스트리 |
| `misc_converter/cli.py` | argparse(어댑터 OptionSpec에서 자동 생성) |
| `misc_converter/web/jobs_db.py` | sqlite 잡 이력 |
| `misc_converter/web/server.py` | FastAPI: 잡 제출/큐/진행률/리포트/브라우즈 |
| `misc_converter/web/index.html` | 단일 파일 React UI |
| `tests/conftest.py` | 가짜 도구 실행 파일 팩토리(`make_fake_tool`) |
| `tests/test_*.py` | 모듈별 테스트 |
| `docker/Dockerfile.wine-spike`, `docker/spike.sh` | Wine 검증 스파이크 |
| `pyproject.toml`, `.pre-commit-config.yaml`, `AGENTS.md`, `README.md`, `config.json.example` | 거버넌스·설정 |

## 핵심 인터페이스 (전 태스크 공통 — 이름 고정)

```python
# engine/models.py
class FailureKind(str, Enum): OUTPUT_MISSING, NONZERO_EXIT, NETWORK, TIMEOUT, LAUNCH_ERROR
@dataclass class WorkItem: source: Path; output_dir: Path; extra: dict[str, Any]
@dataclass class ItemResult: item, status: "converted"|"skipped"|"failed", attempts, failure: FailureKind|None, message, duration_s, argv
@dataclass class RunSummary: adapter, options, total, converted, skipped, failed, results, started_at, finished_at, log_path, json_path

# adapters/base.py
@dataclass class OptionSpec: name, kind: "flag"|"str"|"int"|"choice", default, choices, help
class Adapter(ABC):
    name: str; description: str; unit: "file"|"session_parent"; tool_key: str
    options: list[OptionSpec]
    def match(self, path: Path) -> bool                       # 입력 후보인가
    def expected_outputs(self, item, opts) -> list[Path]      # 확정 산출물(빈 리스트면 verify가 판단)
    def build_argv(self, item, opts, tool_path, backend) -> list[str]
    def verify(self, item, opts) -> bool                      # 기본: expected_outputs 전부 존재·크기>0
    def retry_options(self, item, opts, attempt) -> dict|None # 재시도 시 옵션 변경(csv 스왑). None=동일
    def prepare(self, item, opts) -> None                     # 실행 전 정리(pcap 미완성 tar 삭제)

# backends/base.py
class Backend(Protocol):
    def wrap(self, argv: list[str]) -> list[str]
    def tool_path(self, path: Path) -> str                    # 도구에 넘길 경로 문자열
```

---

### Task 1: 프로젝트 골격·거버넌스 설정

**Files:** `pyproject.toml`, `.pre-commit-config.yaml`, `misc_converter/__init__.py`, `misc_converter/__main__.py`, `tests/__init__.py`, `config.json.example`, `.gitignore`(추가)

- [ ] `pyproject.toml` — dut 루트 설정을 단일 프로젝트용으로 축약: ruff(line 120, py310, E/F/I/UP/B, ignore E501), mypy(3.10, check_untyped_defs), pytest(-v --strict-markers, markers=slow), 의존성 `fastapi`, `uvicorn` (optional-dependencies `web`), dev: pytest, httpx, ruff, mypy, pre-commit
- [ ] `.pre-commit-config.yaml` — ruff(--fix), ruff-format, mypy(--follow-imports=silent)
- [ ] `misc_converter/__init__.py`: `VERSION = "0.1.0"`; `__main__.py`: `from misc_converter.cli import main; raise SystemExit(main())`
- [ ] `config.json.example`:
```json
{
  "mounts": {"qumulo": {"linux": "/mnt/qumulo", "windows": "\\\\qumulo.stradvision.com\\datagroup"}},
  "tools": {
    "aptiv": "/opt/tools/AptivFileConversion_v2.1.5/AptivFileConversion.exe",
    "djlp": "/opt/tools/DJLPConvertTool/DJLPConvertTool_update7.exe",
    "csv_extractor": "/opt/tools/txt_to_csv/csv_extractor-3.10.0",
    "pcap2pcd_image": "surf_pcap2pcd_converter:latest"
  },
  "wine": {"bin": "wine", "prefix": "/opt/wineprefix", "xvfb": true},
  "docker": {"bin": "docker"},
  "djlp_argv_template": ["{exe}", "{input}"],
  "workers": 4, "retries": 2, "timeout_s": 1800,
  "log_dir": "logs", "web_port": 8768
}
```
- [ ] `.gitignore`에 `config.json`, `logs/`, `*.db` 추가
- [ ] `pip install -e ".[web,dev]"`, `pre-commit install`, `pytest`(수집 0건 OK) 확인
- [ ] 커밋: `chore(scaffold): misc_converter 프로젝트 골격·린트·pre-commit 설정`

### Task 2: config + paths (TDD)

**Files:** `misc_converter/config.py`, `misc_converter/paths.py`, `tests/test_config.py`, `tests/test_paths.py`

- [ ] 테스트: `load_config(tmp json)` → `Config` 필드 매핑; 파일 없으면 `example` 기본값 사용 안 함, `FileNotFoundError`
- [ ] 테스트 paths: `PathMapper({"qumulo": {"linux": "/mnt/qumulo", "windows": r"\\qumulo.stradvision.com\datagroup"}})`
  - `to_local(r"\\qumulo.stradvision.com\datagroup\a\b")` == `PurePosixPath("/mnt/qumulo/a/b")`
  - `to_local("/mnt/qumulo/a")` 그대로; 미등록 경로 → `ValueError`
  - `to_wine(PurePosixPath("/mnt/qumulo/a"))` == `r"Z:\mnt\qumulo\a"`
- [ ] 구현: `Config` 데이터클래스(위 example 필드), `load_config(path) -> Config`, `PathMapper.to_local/to_wine/is_allowed`
- [ ] 커밋: `feat(paths): 설정 로더와 Qumulo 경로 매퍼 추가`

### Task 3: engine/models + backends (TDD)

**Files:** `misc_converter/engine/models.py`, `misc_converter/backends/{base,local,wine,docker}.py`, `tests/test_backends.py`

- [ ] 테스트: `LocalBackend().wrap(["x","-i","a"]) == ["x","-i","a"]`, `tool_path(Path("/a")) == "/a"`
- [ ] 테스트: `WineBackend(bin="wine", prefix="/p", xvfb=True).wrap(["/t.exe","-i","a"]) == ["xvfb-run","-a","wine","/t.exe","-i","a"]`, `env()["WINEPREFIX"]=="/p"`, `tool_path(Path("/mnt/q/a.dvl")) == r"Z:\mnt\q\a.dvl"`; xvfb=False면 `["wine", ...]`
- [ ] 테스트: `DockerBackend(bin="docker", image="img", volumes=["/mnt/qumulo:/mnt/qumulo"], user="1000:1000").wrap(["-p","x"]) == ["docker","run","--rm","--user","1000:1000","-v","/mnt/qumulo:/mnt/qumulo","img","-p","x"]`
- [ ] 구현 (Backend 프로토콜에 `env() -> dict[str,str]` 포함, 기본 `os.environ` 복사)
- [ ] 커밋: `feat(backends): local·wine·docker 실행 백엔드 추가`

### Task 4: adapters/base + aptiv 어댑터 (TDD)

**Files:** `misc_converter/adapters/base.py`, `misc_converter/adapters/aptiv.py`, `tests/test_adapter_aptiv.py`

- [ ] 테스트: `AptivAdapter().match(Path("a.dvl"))` True, `.DVL` True, `.txt` False, `.asc`는 True(입력 가능 포맷)
- [ ] 테스트: `build_argv(item(src=/in/a.dvl, out=/out), {"asc": True, "ascbase": "hex"}, "/t.exe", LocalBackend())` == `["/t.exe","-i","/in/a.dvl","-o","/out","-y","--asc","--ascbase=hex","--asctimeref=absolute"]` (`-y`는 항상 — 스킵 판정은 엔진이 하므로 exe는 무조건 덮어씀)
- [ ] 테스트: `expected_outputs(item, {"asc":True,"dvl":True})` == `[/out/a.asc, /out/a.dvl]`; `{"dvs":True,"dvsextension":"dvsu"}` → `[/out/a.dvsu]`; `{"lcm":True}` → `[]`(미실측 → verify는 `stem.*` 신규 파일 존재로 판단)
- [ ] 테스트: 출력 포맷 하나도 없으면 `build_argv`가 `ValueError`
- [ ] 구현: `WRITERS` 테이블(asc/.asc, dvl/.dvl, dvs/가변, mudp/.mudp, pcap/.pcap, lcm/None, adtf/None) + `options` (asc, ascbase choice hex|dec, asctimeref choice absolute|relative, dvl, dvlversion choice, dvs, dvsextension, dvssectionname, dvssectionsize int, lcm, lcmvideo1, mudp, ethernetmap choice, ethsrcmac…ethdestport, pcap, pcapmtu int, adtf); `verify` 기본 구현은 base에: expected 전부 존재·size>0, expected 비어 있으면 `output_dir.glob(f"{stem}.*")` 중 source 아닌 파일 존재
- [ ] 커밋: `feat(adapters): 어댑터 기반 클래스와 AptivFileConversion 어댑터 추가`

### Task 5: scanner (TDD)

**Files:** `misc_converter/engine/scanner.py`, `tests/test_scanner.py`

- [ ] 테스트(tmp_path 트리: `a.dvl`, `b.DVL`, `c.txt`, `sub/d.dvl`, `done.dvl`+`done.asc`(size>0)): `scan([tmp], AptivAdapter(), {"asc":True}, output_dir=None)` → items 4건, `done.dvl`은 `skip=True`; `output_dir=None`이면 산출물은 원본 옆
- [ ] 테스트: 파일 경로 직접 지정 시 1건; 와일드카드 `tmp/"*.dvl"` 지원; 존재하지 않는 경로 → `FileNotFoundError`
- [ ] 테스트: `unit="session_parent"` 어댑터(가짜)는 `match(dir)`로 세션 디렉터리를 찾고 부모별로 1 item(`extra["sessions"]`)
- [ ] 구현: `scan(inputs, adapter, opts, output_dir, force) -> list[ScanEntry(item, skip: bool)]`; 정렬 안정
- [ ] 커밋: `feat(engine): 입력 스캔과 스킵 판정 추가`

### Task 6: runner — 실행·검증·재시도 (TDD, 가짜 도구)

**Files:** `misc_converter/engine/runner.py`, `tests/conftest.py`, `tests/test_runner.py`

- [ ] `conftest.make_fake_tool(tmp_path, behavior)` — Python 스크립트를 만들어 `sys.executable script ...`로 실행: `"ok"`(argv의 `-o` 뒤 디렉터리에 `<stem>.asc` 생성, exit 0), `"silent_fail"`(exit 0, 산출물 없음), `"crash"`(exit 3), `"network"`(stderr에 `예기치 않은 네트워크 오류`, exit 1), `"hang"`(sleep 30), `"flaky:N"`(N번째 호출부터 ok — 카운터 파일)
- [ ] 테스트: ok → `status="converted"`, attempts 1; silent_fail → failed/OUTPUT_MISSING, attempts=retries+1; crash → NONZERO_EXIT; network → NETWORK; hang(timeout_s=1) → TIMEOUT; flaky:2 + retries 2 → converted attempts 2; 존재하지 않는 exe → LAUNCH_ERROR attempts 1(재시도 안 함)
- [ ] 테스트: `retry_options` 반환하는 가짜 어댑터 → 2번째 시도 argv에 반영
- [ ] 구현: `run_item(item, adapter, opts, backend, tool_path, retries, timeout_s, backoff=(5,25), sleep=time.sleep) -> ItemResult`; 실패 분류 `classify(returncode, stdout, stderr, verified)`; 네트워크 패턴: `네트워크`, `network`, `Host is down`, `STATUS_`, `I/O error`, `핸들이 잘못`, `Input/output error`; 실행 전 `adapter.prepare`
- [ ] 커밋: `feat(engine): 항목 실행기(검증·실패 분류·재시도) 추가`

### Task 7: report + orchestrator (TDD)

**Files:** `misc_converter/engine/report.py`, `misc_converter/engine/orchestrator.py`, `tests/test_orchestrator.py`

- [ ] 테스트: `run_job(inputs, adapter, opts, backend, tool_path, output_dir, workers=2, retries=0, timeout_s=10, log_dir=tmp, progress=cb, dry_run=False)` — 가짜 트리 3건(1건 기완료) + ok 도구 → summary total 3, converted 2, skipped 1, failed 0; `cb` 호출 3회; `log_dir`에 `convert_YYYYMMDD_HHMMSS.log`·`.json` 생성, JSON에 results 배열
- [ ] 테스트: `dry_run=True` → 도구 실행 안 함(카운터 0), 결과 status `"planned"`
- [ ] 테스트: `cancel=threading.Event()` set 시 남은 항목 `"cancelled"`
- [ ] 구현: `report.write(summary, log_dir)`; `orchestrator.run_job(...) -> RunSummary`; ThreadPoolExecutor
- [ ] 커밋: `feat(engine): 오케스트레이터와 리포트 작성기 추가`

### Task 8: csv_extractor 어댑터 (TDD)

**Files:** `misc_converter/adapters/csv_extractor.py`, `tests/test_adapter_csv.py`

- [ ] 테스트: 트리 `P/S1/S1_can1.txt, S1_can2.txt, S1.txt`, `P/S2/...` → `match(P/S1)` True(디렉터리에 `*_can*.txt` 존재), scanner가 unit=session_parent로 `P` 1건 `extra["sessions"]==["S1","S2"]`
- [ ] 테스트: `build_argv(item, {"ccan":"can2","pcan":"can1"}, "/csv_extractor", Local)` == `["/csv_extractor","-d","P/","-t","P/","--aptiv","--ccan","can2","--pcan","can1","-f"]`
- [ ] 테스트: `expected_outputs` == 각 세션 `S1/S1_ccan_3_2_1.csv`, `S1/S1_pcan.csv` ...
- [ ] 테스트: `retry_options(item, {"ccan":"can2","pcan":"can1"}, attempt=1)` == `{"ccan":"can1","pcan":"can2"}`(스왑), attempt=2 → None(한 번만); 옵션 `auto_swap` False면 항상 None
- [ ] 구현: options ccan(str, default can2), pcan(str, default can1), auto_swap(flag, default True)
- [ ] 커밋: `feat(adapters): csv_extractor 어댑터(ccan/pcan 자동 스왑) 추가`

### Task 9: pcap2pcd 어댑터 (TDD)

**Files:** `misc_converter/adapters/pcap2pcd.py`, `tests/test_adapter_pcap.py`

- [ ] 테스트: `match(x.pcap)`; `build_argv(item(src=/mnt/q/a.pcap), {}, "surf:latest", DockerBackend(...))` == `[docker run ... surf:latest -p /mnt/q/a.pcap -o /mnt/q]`
- [ ] 테스트: `verify` — `a_3001.tar` + `a_convert_log.json{"success": true}` → True; json success false → False; json 없음 → False
- [ ] 테스트: `prepare` — `a.tar`(접미사 없는 미완성) 삭제, `a_3001.tar` 유지
- [ ] 테스트: `expected_outputs` == `[a_convert_log.json]`(tar는 N 가변이라 verify에서 glob)
- [ ] 구현: options `pattern`(str, 기본 없음—배치 아님, 파일 단위), `cpus`(int, 선택 → 백엔드 wrap 앞에 `--cpus` 넣기 위해 `build_argv`가 백엔드에 `extra_docker_args` 전달 대신 DockerBackend 생성 시 cpus 지정)
- [ ] 커밋: `feat(adapters): pcap2pcd 어댑터(convert_log 판정·미완성 tar 정리) 추가`

### Task 10: djlp 어댑터 (TDD)

**Files:** `misc_converter/adapters/djlp.py`, `tests/test_adapter_djlp.py`

- [ ] 테스트: `match(a.avi)` True, `a_alt.avi` False(보조 파일), `.tavi/.webm` True
- [ ] 테스트: `DjlpAdapter(argv_template=["{exe}","{input}","--out","{output_dir}"]).build_argv(...)` 치환 결과; 기본 템플릿 `["{exe}","{input}"]`
- [ ] 테스트: `expected_outputs` == `[out/a.raw, out/a.timestamp.txt]`; 옵션 `require_asc`(flag, 기본 True)일 때 `a.asc` 형제 없으면 `precheck(item)`가 메시지 반환 → runner가 실행 없이 failed/LAUNCH_ERROR "선행 .asc 없음"
- [ ] 구현 (+ `Adapter.precheck(item, opts) -> str | None` 기본 None; runner Task 6에 반영)
- [ ] 커밋: `feat(adapters): DJLPConvertTool 어댑터(argv 템플릿·선행 asc 검사) 추가`

### Task 11: 어댑터 레지스트리 + CLI (TDD)

**Files:** `misc_converter/adapters/__init__.py`, `misc_converter/cli.py`, `tests/test_cli.py`

- [ ] 테스트: `main(["--config",cfg,"aptiv","-i",tree,"--asc","--dry-run"])` → exit 0, stdout에 `planned` 건수; 없는 어댑터 → exit 2; 실패 존재 → exit 1(가짜 도구 silent_fail)
- [ ] 테스트: `main(["adapters"])` → 4개 이름·설명 출력
- [ ] 구현: `ADAPTERS = {"aptiv": AptivAdapter, "djlp": DjlpAdapter, "csv": CsvExtractorAdapter, "pcap2pcd": Pcap2PcdAdapter}`; `build_parser()`가 어댑터별 서브커맨드 + OptionSpec→argparse; 공통 `-i/--input`(nargs+), `-o/--output-dir`, `--workers`, `--retries`, `--timeout`, `--force`, `--dry-run`, `--config`; 백엔드 선택은 어댑터의 `backend_kind`("local"|"wine"|"docker") + config로 자동
- [ ] 커밋: `feat(cli): 어댑터 레지스트리와 CLI 진입점 추가`

### Task 12: 웹 — jobs_db + server (TDD)

**Files:** `misc_converter/web/jobs_db.py`, `misc_converter/web/server.py`, `tests/test_web.py`

- [ ] 테스트(TestClient, config monkeypatch): `GET /api/adapters` → 4개 + options; `POST /api/jobs {adapter:"aptiv", inputs:[...], options:{asc:true}, dry_run:true}` → 202 `{id}`; 워커 스레드가 처리 후 `GET /api/jobs/{id}` status `done`, summary 포함; `GET /api/jobs` 목록; `GET /api/browse?path=/mnt/qumulo` → 허용 루트 밖이면 400
- [ ] 테스트: 잡 2개 연속 제출 → 직렬 처리(두 번째는 첫 번째 완료 후 시작 — started_at 순서)
- [ ] 구현: `jobs_db.py`(sqlite: id, adapter, inputs json, options json, status, progress, summary json, created/started/finished); `server.py`(FastAPI, lifespan에서 워커 스레드 + `queue.Queue`, 진행 콜백으로 progress 갱신, `POST /api/jobs/{id}/cancel`, `GET /` → index.html); UNC 입력은 `PathMapper.to_local`로 변환
- [ ] 커밋: `feat(web): FastAPI 잡 서버와 sqlite 이력 추가`

### Task 13: 웹 UI index.html

**Files:** `misc_converter/web/index.html`

- [ ] storageops 스타일 토큰 차용, 단일 파일 React 18: 좌측 어댑터 목록 → 폼(입력 경로 textarea, 출력 디렉터리, 어댑터 옵션 자동 렌더, dry-run/force/workers) → 제출; 우측 잡 큐(진행률 바, 상태 배지) + 잡 상세(리포트 표: 변환/스킵/실패, 실패 사유, 로그 경로); 3초 폴링
- [ ] 브라우저 수동 확인(`uvicorn misc_converter.web.server:app`) — dry-run 잡 1건 제출·완료 표시
- [ ] 커밋: `feat(web): 변환 잡 제출·모니터링 단일 페이지 UI 추가`

### Task 14: Wine 스파이크 이미지 + 스크립트

**Files:** `docker/Dockerfile.wine-spike`, `docker/spike.sh`, `docker/README.md`

- [ ] Dockerfile: `ubuntu:22.04` + winehq-stable + winetricks + xvfb + python3; `winetricks -q dotnet461`은 빌드 시간·인터랙션 이슈로 wine-mono 대안을 1차 시도(스크립트에서 분기)
- [ ] `spike.sh`: 도구 경로·샘플 `.dvl` 인자 → (1) `wine AptivFileConversion.exe --help` 출력 확인 (2) `.dvl → .asc` 실변환 → 산출물 크기·첫 3줄 출력 (3) `xvfb-run wine DJLPConvertTool_update7.exe --help` (4) 판정 요약 표
- [ ] README: 실행법·판정 기준·실패 분기(스펙 §4)
- [ ] 커밋: `chore(docker): Wine 검증 스파이크 이미지·스크립트 추가`

### Task 15: 문서·마무리

**Files:** `AGENTS.md`, `README.md`, `docs/specs/...`(열린 항목 갱신)

- [ ] `AGENTS.md`(한국어): 목적, 구조, 실행법(CLI/웹), 어댑터 추가법, 헌법 참조, 미실측 항목
- [ ] `README.md` 교체(현재 "Test_DAT"): 설치·설정·실행 3단계
- [ ] `ruff check . && ruff format --check . && mypy misc_converter && pytest` 전부 통과
- [ ] 커밋: `docs(readme): 사용법·AGENTS 문서 추가`

## Self-Review

- 스펙 커버리지: §3.1 엔진 7원칙 → Task 5·6·7(잡 큐 직렬은 Task 12); §3.2 어댑터 특기 → Task 8·9·10; §3.3 웹 → Task 12·13; §3.4 경로 → Task 2; §4 스파이크 → Task 14; §5 거버넌스 → Task 1·15; §6 테스트 → 각 태스크 TDD + conftest 가짜 도구.
- 열린 항목 2·3(DJLP 옵션, lcm/adtf 확장자)은 설정형 템플릿·glob 검증으로 코드가 실측 전에도 동작하도록 흡수.
- 인터페이스 이름은 상단 "핵심 인터페이스" 블록을 단일 기준으로 사용.
