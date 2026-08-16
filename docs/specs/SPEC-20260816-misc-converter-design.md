<!-- Generated: 2026-08-16 -->

# SPEC — misc_converter: 기타 인바운드 포맷 변환 웹 서비스

> 상태: v1 구현 완료 + Wine 스파이크 통과(2026-08-16, mlops14) — 배포 단계 | 작성: 2026-08-16 | 근거 대화: avi_convert 도구 통합 브레인스토밍
> 거버넌스: [`docs/CONSTITUTION.md`](../CONSTITUTION.md) → [`docs/RULE.md`](../RULE.md) 전면 적용 (dut 저장소에서 이식)

## 1. 배경과 문제

DUT 팀은 고객사로부터 데이터를 받는다. 주력 포맷인 **MF4는 별도 서비스에서 이미 변환을 담당**하지만,
간헐적으로 들어오는 **기타 포맷(AVI·dvl·mudp·asc·txt·pcap 등)** 은 개별 GUI/CLI 도구 4종을
운영자가 수동으로 다루고 있다 ([DUT] AVI Conversion Manual, pageId 48607430020).

현행 방식의 실증된 문제 (21개월 운영 로그·매뉴얼 검토 문서 근거):

| 문제 | 근거 |
|---|---|
| 멱등성 없음 — 재실행 시 기존 출력과 충돌 | AptivFileConverter.log 21개월간 ERROR 1,195건 중 `파일이 이미 있습니다` 약 740건 |
| 입력 필터 없음 — 로그 외 파일까지 변환기에 투입 | `Unrecognized file extension.` 399건 |
| 수동 명령 조립 실수 | 도구 폴더에 `--asc`, `-i`, `-o` 등 이름의 빈 디렉터리 잔존 (인용 실수 흔적) |
| 네트워크 오류 무대응 | SMB(Qumulo) 오류 시 재시도 없음 |
| 침묵 실패 | csv_extractor는 ccan/pcan을 반대로 배정해도 `Extraction finish!` 출력 — 산출물 0건인데 성공처럼 보임 |
| 성패 판정 불가 | AptivFileConversion은 WinForms 기반이라 exit code 신뢰 불가, 로그는 실패만 기록 |
| 지식 유실 위험 | 운영 함정이 매뉴얼(사람)에만 존재 — 원작성자 이미 퇴사(Deactivated) |

## 2. 정체성과 범위

**misc_converter**: MF4 외 기타 인바운드 포맷을 변환하는 **웹 서비스 + CLI**.
할당된 우분투 서버 1대에서 구동하며, 팀원은 브라우저에서 Qumulo 경로와 변환 종류를 골라 실행한다.

### 2.1 변환 단계 (블랙박스 도구 래핑)

기존 변환 도구는 **수정하지 않는다**. 전부 소스 없는 배포 바이너리이며, 21개월 로그에서 변환 로직
자체의 오류는 확인되지 않았다 — 문제는 전부 "도구를 부르는 방식"에 있다. misc_converter는
오케스트레이션 계층이다.

| 단계 | 도구 (블랙박스) | 입력 | 출력 | 실행 방식 |
|---|---|---|---|---|
| dvl2asc 등 | AptivFileConversion.exe v2.1.5 (.NET 4.6.1) | .dvl·.dvs(.dvss/.dvsu)·.mudp·.asc·.mf4 | asc·dvl·dvs·lcm·mudp·pcap·adtf (7종 라이터 전부 노출) | **Wine** (스파이크 검증 필요) |
| avi2raw | DJLPConvertTool_update7.exe (Qt5) | .avi(+_alt.avi)·.tavi·.asc·.webm·.mf4 | .raw + .timestamp.txt + SESSION_canN.txt (또는 avi/mp4/h264/jpg/png) | **Wine + xvfb** (스파이크 검증 필요) |
| txt2csv | csv_extractor-3.10.0 (Linux ELF) | SESSION_canN.txt + SESSION.txt | SESSION_ccan_3_2_1.csv + SESSION_pcan.csv | 네이티브 |
| pcap2pcd | surf_pcap2pcd_converter (Docker, gpuharbor) | .pcap (+correction csv) | `<stem>_{N}.tar` + `<stem>_convert_log.json` | docker run |
| raw2h264 | isp_conversion_runner.py (EVM 보드) | .raw | .h264 | **v2** — SSH, 실환경 필요 |

- AptivFileConversion의 7종 라이터 전 조합을 옵션으로 노출한다 (사용자 결정 사항).
  래퍼 로직은 가짜 실행 파일로 전 조합 테스트 가능하므로 §IX 테스트 의무와 충돌하지 않는다.
- MF4 입력은 AptivFileConversion이 읽을 수 있어 부수적으로 동작하지만 **설계 목표가 아니다**
  (별도 MF4 서비스 존재).
- 라이다 pcap2pcd는 [[DUT] PCAP -> PCD 변환](pageId 50046206116) 문서 기준.

### 2.2 버전 로드맵

| 버전 | 내용 |
|---|---|
| v1 | 웹 서비스 + 엔진 + 어댑터 4종(dvl2asc·avi2raw·txt2csv·pcap2pcd) + CLI. **구현 1단계는 Wine 검증 스파이크** |
| v2 | raw2h264(EVM SSH 자동화), 우분투 다중 호스트 분산(필요 시) |
| 제외 | MF4 전용 경로(별도 서비스), 변환 로직 자체 수정, DBC 신호 디코딩(후단 도구 몫) |

## 3. 아키텍처

```
misc_converter (우분투 서버 1대)
├─ web/       FastAPI + 단일 index.html (CDN React 18, 빌드 없음)  ← storageops 패턴
│             잡 제출(Qumulo 경로 + 변환 종류 + 옵션) · 큐 · 진행률 · 리포트 · 이력
├─ engine/    스캔 → 스킵 판정 → 실행 → 산출물 검증 → 재시도 → 리포트   (1회 구현, 전 어댑터 공유)
├─ adapters/  단계별 선언 1파일: 입력 패턴 · argv 조립 · 기대 산출물 · 성공 판정 · 실패 시 조치
├─ backends/  실행 백엔드 인터페이스: local / wine / docker  (v2: ssh)
├─ paths.py   Qumulo 상대 경로 ↔ 호스트별 마운트 매핑 (UNC ↔ /mnt/qumulo…)
└─ cli.py     엔진 위 얇은 CLI (자동화·테스트·비상시 수동 실행용)
```

### 3.1 엔진 (핵심 원칙)

1. **파일 단위 실행** — 디렉터리 통째 전달 대신 입력 파일 1개당 도구 1회 호출.
   스킵·재시도·병렬·리포트의 단위가 된다. (예외: csv_extractor·pcap2pcd 배치 모드는
   세션 폴더 단위가 자연 단위 — 어댑터가 자기 작업 단위를 선언한다.)
2. **무상태 검증** — "어디까지 됐나"는 상태 파일이 아니라 **기대 산출물의 존재·크기(>0)** 로
   판정한다. 중단·재실행·수동 개입이 섞여도 항상 진실에서 출발하며, 멱등성이 공짜로 확보된다.
   기대 산출물 전부 존재 → 스킵. 일부만 존재 → 불완전으로 간주, overwrite 재실행.
3. **exit code 불신** — 성공 판정은 어댑터가 선언한 산출물 검증만 신뢰한다
   (AptivFileConversion은 실패 시에도 0 반환 가능, csv_extractor는 침묵 실패).
4. **argv 리스트 전달** — 문자열 셸 조립 금지. 인용 실수 원천 차단.
5. **재시도** — 실패 유형 분류(산출물 미생성/프로세스 이상 종료/네트워크 오류/타임아웃) 후
   백오프 재시도(기본 2회, 5s→25s). 파일당 타임아웃 기본 30분.
6. **병렬** — 잡 내부 파일 단위 병렬(기본 workers=4). 잡 큐는 **직렬**(동시 1잡) —
   pcap 문서의 "동일 경로 동시 실행 금지" 교훈을 큐 수준에서 강제한다.
7. **리포트** — 실행별 로그(UTF-8·한국어) + JSON 요약(전체/변환/스킵/실패+사유).
   CLI exit code: 0=전부 성공, 1=실패 존재, 2=인자 오류.

### 3.2 어댑터별 특기 사항 (운영 지식의 코드화)

- **txt2csv**: 실행 후 `_ccan_3_2_1.csv`/`_pcan.csv` 생성 검증. 0건이면 `--ccan`/`--pcan`을
  **맞바꿔 자동 재시도** — 매뉴얼의 최대 함정(반나절 손실 사례)을 기계가 해결.
  `-d`/`-t`는 세션 폴더의 상위 경로를 지정해야 함(어댑터가 자동 계산).
- **pcap2pcd**: `convert_log.json`의 `"success": true`로 판정. 미완성 tar(프레임 수 접미사
  없는 `*.tar`)는 재실행 전 자동 정리. `--user $(id -u):$(id -g)` 자동 부여(root 소유 산출물 방지).
- **dvl2asc(AptivFileConversion)**: 출력 포맷별 기대 확장자 테이블 기반 검증.
  lcm·adtf 출력 확장자는 문서에 없어 구현 시 실측 후 테이블 확정 (열린 항목).
- **avi2raw(DJLP)**: CLI 옵션 표면 실측 필요 (열린 항목 — 바이너리에서 CLI 모드 존재는 확인).

### 3.3 웹 (storageops 패턴)

- FastAPI + uvicorn, 단일 `index.html`(CDN React 18, Babel standalone, 빌드 없음).
  포트 기본 8768(설정 가능). 사내망 전용, 인증 없음(storageops와 동일 전제).
- 기능: ① 잡 제출 — Qumulo 경로 입력(또는 디렉터리 브라우즈) + 변환 종류 + 옵션,
  ② 잡 큐·진행률(파일 단위 %), ③ 완료 리포트(변환/스킵/실패+사유), ④ 잡 이력.
- 잡 이력·상태는 SQLite(표준 라이브러리 sqlite3). 변환 진행 상태 자체는 무상태 검증이
  진실 소스이고 SQLite는 이력·감사용.
- 실행 중 서버 재시작 시: 잡은 "중단" 처리하고 재제출 유도 — 무상태 검증 덕에 재제출은
  이어하기와 동일하다.

### 3.4 경로 추상화

같은 데이터가 호스트마다 다르게 보인다: `\\qumulo.stradvision.com\datagroup\...`(Windows) ↔
`/mnt/qumulo/...`(Linux) ↔ `Z:\...`(Wine drive mapping). `paths.py`가 "Qumulo 상대 경로 +
호스트별 마운트 매핑(설정 파일)"으로 변환을 전담한다. Wine 백엔드는 리눅스 경로를 Wine 드라이브
문자로 변환해 exe에 전달한다.

## 4. Wine 검증 스파이크 (구현 1단계 — 선결 과제)

Windows 상시 호스트가 없으므로(사용자 확인) Wine이 유일한 실행 경로다. 실측 전에는 성패를
알 수 없어 **구현 1단계를 스파이크로 고정**한다.

- 대상: ① AptivFileConversion.exe 콘솔 모드(dvl→asc 실변환 1건), ② DJLPConvertTool CLI 모드(avi→raw 1건)
- 환경: Docker 이미지에 Wine + wine-mono(또는 winetricks dotnet46) + xvfb 고정 — 재현성 확보
- 판정: 산출물이 Windows 실행 결과와 동일(크기·헤더 수준 비교)하면 성공
- 실패 분기: 실패한 exe의 단계는 설계를 유지한 채 **그 시점에 대안을 재결정**한다
  (예: 해당 단계만 당분간 수동 GUI 유지, 웹에는 안내 표시). 성공한 단계는 그대로 진행.

## 5. 저장소·거버넌스

- 저장소: https://github.com/SV-kwangyong/dut_test — 헌법·RULE을 dut에서 원문 이식(완료).
  헌법 원문의 dut 8개 프로젝트 목록 등 dut 고유 내용은 지시대로 원문 유지하며,
  이 저장소 고유사항은 `AGENTS.md`가 규정한다.
- §III 브랜치/PR, §IV 한국어 Conventional Commits, §V 120자·snake_case, §VI 타입힌트+mypy,
  §VIII ruff, §IX pytest(커밋 전 전체 통과), §X pre-commit, §XI semver, §XIV 한국어 문서 전면 적용.
- **바이너리 미커밋** — exe·DLL·ELF의 배포 채널은 Qumulo 도구 경로
  (`99_management\01_tool\02_data_converter\avi_convert`)로 유지. 도구 위치는 호스트별
  설정 파일로 지정. 샘플 데이터·운영 산출물도 미커밋.
- 런타임 의존성: fastapi + uvicorn만 (storageops 선례). 엔진·CLI는 표준 라이브러리만.
  Python 3.10+ (우분투 22.04 기본).

```
dut_test/
├─ docs/
│  ├─ CONSTITUTION.md · RULE.md      # dut에서 이식 (완료)
│  └─ specs/                          # 본 문서
├─ misc_converter/
│  ├─ cli.py · web/ (server.py, index.html)
│  ├─ engine/ · adapters/ · backends/ · paths.py
├─ tests/                             # 가짜 실행 파일 기반 전 흐름 검증
├─ docker/                            # Wine 스파이크·운영 이미지
├─ pyproject.toml · .pre-commit-config.yaml · AGENTS.md
```

## 6. 테스트 전략 (§IX)

- **단위**: 포맷 테이블 정합성, 스캔·스킵 판정(tmp_path 가짜 트리), argv 조립(라이터 7종 전 조합),
  경로 변환(UNC↔mnt↔Wine).
- **통합**: 진짜 도구 대신 **가짜 실행 파일**(기대 산출물을 만들거나 고의 실패하는 스크립트)로
  실행→검증→재시도→리포트 전 흐름 검증. txt2csv ccan/pcan 자동 스왑 시나리오 포함.
- **웹**: FastAPI TestClient로 잡 제출→완료→리포트 흐름.
- **스모크(선택)**: 실제 도구 + 실제 샘플 존재 시에만 도는 `@pytest.mark.slow`.

## 7. 열린 항목

| # | 항목 | 해소 시점 | 코드에서의 흡수 방식 |
|---|---|---|---|
| 1 | ~~Wine에서 AptivFileConversion·DJLP 구동 성패~~ **해결(2026-08-16, mlops14, wine-11.0 + wine-mono 10.4.1, win64 prefix)**: 엔진 경유 dvl→asc 60,111줄 정상, DJLP CLI 기동 정상. 조건: Aptiv는 **pty 필수**(파이프 stdout이면 `Console.CursorLeft`로 Invalid handle — Windows에서도 동일) → Wine 백엔드 `use_pty=True` | — | `engine/runner.py` `_run_with_pty` |
| 2 | ~~DJLPConvertTool CLI 옵션 표면 실측~~ **해결(2026-08-16 스파이크)**: `-s/--source <PATH>`, 출력 위치 옵션 없음 | — | 기본 템플릿 `[exe, -s, input]` 반영 |
| 3 | AptivFileConversion lcm·adtf 출력 확장자 실측 | 샘플 변환 1회 | `adapters/aptiv.py` `WRITERS` 값 갱신 (현재 `None` → stem.* glob 검증) |
| 4 | 우분투 서버 호스트 확정(IP·마운트·docker) | 배포 전 | `config.json` |
| 5 | Aptiv 입력 포맷 필터 기본값 `dvl` — 다른 포맷은 `--input-format` 지정 | 구현 중 결정 | 자기 변환(입력==산출물)은 스캔에서 제외 |
