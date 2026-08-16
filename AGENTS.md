<!-- Generated: 2026-08-16 -->

# misc_converter

> 공통 거버넌스(브랜치/커밋/스타일/린트/타입/테스트/보안/한국어)는 `docs/CONSTITUTION.md` → `docs/RULE.md`를 따른다(dut 저장소에서 이식, 원문 유지). 본 파일은 이 저장소 고유사항만 기술한다.

## Purpose

고객사 인바운드 데이터 중 **MF4 외 기타 포맷**(AVI·dvl·mudp·asc·txt·pcap)을 변환하는 웹 서비스 + CLI. MF4는 별도 서비스가 담당한다.
기존 블랙박스 변환 도구 4종(AptivFileConversion.exe, DJLPConvertTool_update7.exe, csv_extractor-3.10.0, surf_pcap2pcd_converter)을 **수정하지 않고** 감싸는 오케스트레이션 계층이다.
설계 근거·결정은 [`docs/specs/SPEC-20260816-misc-converter-design.md`](docs/specs/SPEC-20260816-misc-converter-design.md), 구현 계획은 [`docs/plans/`](docs/plans/).

## Structure

| 경로 | 책임 |
|---|---|
| `misc_converter/engine/` | 스캔(`scanner`) → 실행·검증·재시도(`runner`) → 병렬·리포트(`orchestrator`, `report`). 표준 라이브러리만. |
| `misc_converter/adapters/` | 도구별 선언 1파일: 입력 패턴·argv·기대 산출물·검증·재시도 옵션. `ADAPTERS` 레지스트리. |
| `misc_converter/backends/` | 실행 환경별 argv·경로 변환: `local` / `wine`(xvfb) / `docker`. |
| `misc_converter/paths.py` | UNC ↔ `/mnt/...` ↔ Wine `Z:\` 경로 매퍼. 등록 마운트 밖 경로 거부. |
| `misc_converter/runtime.py` | 설정 + 어댑터 이름 → (어댑터, 백엔드, 도구 경로). CLI·웹 공유. |
| `misc_converter/cli.py` | argparse — 어댑터 `OptionSpec`에서 서브커맨드 자동 생성. exit 0/1/2. |
| `misc_converter/web/` | FastAPI `server.py` + sqlite `jobs_db.py` + 단일 `index.html`(CDN React, 빌드 없음). |
| `tests/` | pytest. `conftest.make_fake_tool`로 진짜 도구 없이 전 흐름 검증. |
| `docker/` | Wine 스파이크·운영 이미지. |

## For AI Agents

- **엔진 3원칙을 깨지 말 것**: ① 성공 판정은 exit code가 아니라 **산출물 존재·크기**(`Adapter.verify`) — WinForms exe는 실패해도 0, csv_extractor는 침묵 실패. ② 스킵 판정은 **무상태**(산출물이 곧 진실) — 상태 파일·DB에 진행 상태를 두지 않는다(웹 sqlite는 이력용). ③ argv는 **리스트**로만 조립 — 셸 문자열 금지.
- **어댑터 추가법**: `adapters/<tool>.py`에 `Adapter` 서브클래스(`name/description/unit/tool_key/backend_kind/options` + `match/build_argv/expected_outputs`, 필요 시 `verify/prepare/precheck/retry_options`) → `adapters/__init__.py` `ADAPTERS`에 등록 → `config.json.example` `tools`에 키 추가 → 테스트(가짜 도구). CLI·웹 옵션 UI는 자동으로 따라온다.
- **미실측 항목**(스펙 §7): DJLP CLI 옵션(→ `config.json` `djlp_argv_template`로 흡수), Aptiv lcm/adtf 출력 확장자(→ `WRITERS`에 `None`, verify는 `stem.*` glob), Wine 구동 성패(→ `docker/spike.sh`). 실측되면 해당 지점만 갱신한다.
- **웹 잡 큐는 직렬**(동시 1잡) — 동일 경로 동시 쓰기 사고 방지가 목적이므로 병렬화하지 말 것. 잡 내부 파일 병렬은 `workers`.
- **바이너리·샘플 데이터·config.json·logs·*.db는 커밋 금지**. 도구 배포 채널은 Qumulo `99_management\01_tool\02_data_converter\avi_convert`.
- 테스트는 Windows 개발 PC와 우분투 서버 양쪽에서 통과해야 한다 — Windows glob 대소문자 무시, `os.getuid` 부재 등을 이미 고려하고 있으니 플랫폼 분기 추가 시 같은 기준을 지킬 것.

## 실행

```bash
pip install -e ".[web,dev]" && pre-commit install
cp config.json.example config.json   # 도구 경로·마운트 편집
python -m misc_converter adapters
python -m misc_converter aptiv -i /mnt/qumulo/.../raw --asc --dry-run
uvicorn misc_converter.web.server:app --host 0.0.0.0 --port 8768   # 웹
pytest && ruff check . && mypy misc_converter                       # 게이트(§VIII·IX)
```

## Dependencies

- 런타임: Python 3.10+ 표준 라이브러리(엔진·CLI). 웹만 `fastapi`, `uvicorn`.
- 외부 도구(설정으로 위치 지정, 미커밋): AptivFileConversion v2.1.5(Wine), DJLPConvertTool_update7(Wine+xvfb), csv_extractor-3.10.0(Linux ELF), `surf_pcap2pcd_converter` 이미지(gpuharbor).
- 서버: Ubuntu 22.04, Wine(winehq-stable)+xvfb, Docker, Qumulo 마운트(`/mnt/qumulo`).

<!-- MANUAL: 이 줄 아래 수동 메모 보존 -->
