# docker/ — Wine 스파이크 및 운영 이미지

## 목적
Windows 전용 변환기(AptivFileConversion.exe, DJLPConvertTool_update7.exe)를 우분투 서버에서 Wine으로 구동할 수 있는지
검증한다(스펙 §4). 같은 이미지가 운영 런타임(uvicorn)으로도 쓰인다.

## 빌드
```bash
docker build -f docker/Dockerfile.wine-spike -t misc_converter:spike .
```

## 스파이크 실행
```bash
docker volume create wineprefix     # dotnet 설치를 재사용하기 위한 영속 prefix
docker run --rm -it \
  -v wineprefix:/opt/wineprefix -v /opt/tools:/opt/tools:ro -v /mnt/qumulo:/mnt/qumulo \
  misc_converter:spike spike.sh \
  /opt/tools/AptivFileConversion_v2.1.5/AptivFileConversion.exe \
  /opt/tools/DJLPConvertTool/DJLPConvertTool_update7.exe \
  /mnt/qumulo/<샘플>.dvl [/mnt/qumulo/<샘플>.avi]
```

## 판정 기준
| 단계 | PASS 조건 |
|---|---|
| dotnet | wine-mono 또는 winetricks dotnet461 설치 성공 |
| aptiv_help | `--help` 출력에 `--asc` 포함 |
| aptiv_convert | `.asc` 산출물 크기 > 0 (Windows 실행 결과와 헤더 비교 권장) |
| djlp_help | 프로세스가 정상 종료 — 출력에서 CLI 옵션 표면을 실측해 `config.json` `djlp_argv_template`에 반영 |
| djlp_convert | `.raw` 산출물 존재 |

## 실패 분기 (스펙 §4)
FAIL한 exe의 단계는 웹에서 비활성 안내로 두고 나머지 단계는 그대로 배포한다. 대안(예: 해당 단계만 GUI 수동 유지)은 그 시점에 재결정.

## 운영 실행
```bash
docker run -d --name misc_converter -p 8768:8768 \
  -v wineprefix:/opt/wineprefix -v /opt/tools:/opt/tools:ro -v /mnt/qumulo:/mnt/qumulo \
  -v $PWD/config.json:/app/config.json:ro -v misc_logs:/app/logs -v /var/run/docker.sock:/var/run/docker.sock \
  misc_converter:spike
```
`docker.sock` 마운트는 pcap2pcd 어댑터(컨테이너 안에서 `docker run`)를 위한 것이다 — 이 경우 `config.json` `docker.volumes`는 호스트 경로 기준으로 적는다.
