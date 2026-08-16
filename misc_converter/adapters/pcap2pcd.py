"""surf_pcap2pcd_converter(Docker) 어댑터 — LiDAR .pcap → <stem>_{N}.tar + <stem>_convert_log.json.

[DUT] PCAP -> PCD 변환 문서 기준:
- 성공 판정은 `<stem>_convert_log.json`의 `"success": true`.
- 미완성 tar는 프레임 수 접미사가 없는 `<stem>.tar` → 실행 전 삭제.
- 산출물은 pcap 옆(-o = pcap 디렉터리). correction csv는 같은 폴더에 있으면 자동 인식.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter, OptionSpec
from misc_converter.backends.base import Backend
from misc_converter.engine.models import WorkItem

_COMPLETE_TAR = re.compile(r"_\d+\.tar$")


class Pcap2PcdAdapter(Adapter):
    name = "pcap2pcd"
    description = "surf_pcap2pcd_converter(Docker) — .pcap → PCD tar (convert_log.json으로 성공 판정)"
    unit = "file"
    tool_key = "pcap2pcd_image"  # config.tools 의 값은 도커 이미지 태그
    backend_kind = "docker"
    options = [
        OptionSpec("cpus", "int", None, help="컨테이너 CPU 제한(--cpus). 다중 사용자 서버에서 권장"),
    ]

    def match(self, path: Path, opts: dict[str, Any]) -> bool:
        return path.is_file() and path.suffix.lower() == ".pcap"

    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Backend) -> list[str]:
        # tool_path(이미지)는 DockerBackend가 wrap 시 삽입한다 — 여기서는 컨테이너 인자만
        return ["-p", backend.tool_path(item.source), "-o", backend.tool_path(item.output_dir)]

    def log_path(self, item: WorkItem) -> Path:
        return item.output_dir / f"{item.stem}_convert_log.json"

    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        return [self.log_path(item)]

    def verify(self, item: WorkItem, opts: dict[str, Any]) -> bool:
        log = self.log_path(item)
        if not log.is_file():
            return False
        try:
            data = json.loads(log.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if data.get("success") is not True:
            return False
        tars = [p for p in item.output_dir.glob(f"{item.stem}_*.tar") if _COMPLETE_TAR.search(p.name)]
        return any(p.stat().st_size > 0 for p in tars)

    def prepare(self, item: WorkItem, opts: dict[str, Any]) -> None:
        incomplete = item.output_dir / f"{item.stem}.tar"
        if incomplete.exists():
            incomplete.unlink()
