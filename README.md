# misc_converter

고객사 인바운드 데이터 중 **MF4 외 기타 포맷**(AVI·dvl·mudp·asc·txt·pcap)을 변환하는 웹 서비스 + CLI.
기존 변환 도구(AptivFileConversion, DJLPConvertTool, csv_extractor, pcap2pcd)를 수정 없이 감싸,
멱등 실행·산출물 검증·자동 재시도·통합 리포트를 제공한다.

- 설계: [docs/specs/SPEC-20260816-misc-converter-design.md](docs/specs/SPEC-20260816-misc-converter-design.md)
- 거버넌스: [docs/CONSTITUTION.md](docs/CONSTITUTION.md) → [docs/RULE.md](docs/RULE.md) → [AGENTS.md](AGENTS.md)
- 배경 매뉴얼: [DUT] AVI Conversion Manual, [DUT] PCAP -> PCD 변환 (Confluence DUT 스페이스)

## 1. 설치 (우분투 서버)

```bash
git clone https://github.com/SV-kwangyong/dut_test.git && cd dut_test
python3 -m pip install -e ".[web,dev]"
pre-commit install                      # 헌법 §X
cp config.json.example config.json      # 도구 경로·마운트·Wine 설정 편집
```

Windows exe(Aptiv·DJLP)를 쓰려면 Wine 검증이 먼저다 → [docker/README.md](docker/README.md).

## 2. CLI

```bash
python -m misc_converter adapters                                   # 어댑터 목록
python -m misc_converter aptiv -i /mnt/qumulo/.../raw --asc --dry-run
python -m misc_converter aptiv -i /mnt/qumulo/.../raw --asc         # dvl→asc (기존 산출물 스킵)
python -m misc_converter csv   -i /mnt/qumulo/.../DRV --ccan can2 --pcan can1
python -m misc_converter pcap2pcd -i /mnt/qumulo/.../lidar
python -m misc_converter aptiv --help                               # 어댑터별 옵션
```

종료 코드: `0` 전부 성공(스킵 포함) / `1` 실패 존재 / `2` 인자·설정 오류. 실행별 로그·JSON은 `config.json` `log_dir`.

## 3. 웹

```bash
uvicorn misc_converter.web.server:app --host 0.0.0.0 --port 8768
```

브라우저에서 `http://<서버>:8768` — 입력 경로(UNC 그대로 붙여넣기 가능)·어댑터·옵션 선택 → 제출 → 큐·진행률·리포트 확인.

## 4. 개발

```bash
pytest                       # 가짜 도구 기반 — 진짜 도구 없이 전 흐름 검증
ruff check . && ruff format --check . && mypy misc_converter
```
