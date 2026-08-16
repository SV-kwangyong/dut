"""DJLPConvertTool_update7.exe 어댑터 — DJLP 코덱 영상(.avi + _alt.avi + .asc) → .raw + .timestamp.txt + SESSION_canN.txt.

CLI 옵션은 Wine 스파이크(2026-08-16, wine-11.0)에서 실측: `-s, --source <PATH>` (출력 위치 옵션 없음 — 원본 옆에 생성).
argv는 config `djlp_argv_template`로 바꿀 수 있고 기본은 `[exe, -s, input]`. 치환자: {exe} {input} {output_dir} {stem}.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter, OptionSpec
from misc_converter.backends.base import Backend
from misc_converter.engine.models import WorkItem

INPUT_EXTENSIONS = {".avi", ".tavi", ".webm"}
DEFAULT_TEMPLATE = ["{exe}", "-s", "{input}"]


class DjlpAdapter(Adapter):
    name = "djlp"
    description = "DJLPConvertTool — .avi(+_alt.avi, .asc) → .raw + .timestamp.txt + SESSION_canN.txt"
    unit = "file"
    tool_key = "djlp"
    backend_kind = "wine"
    options = [
        OptionSpec("require_asc", "flag", True, help="같은 이름의 .asc가 옆에 없으면 실행하지 않음(2.1 dvl→asc 선행)"),
    ]

    def __init__(self, argv_template: list[str] | None = None) -> None:
        self.argv_template = list(argv_template or DEFAULT_TEMPLATE)

    def match(self, path: Path, opts: dict[str, Any]) -> bool:
        if not path.is_file() or path.suffix.lower() not in INPUT_EXTENSIONS:
            return False
        return not path.stem.lower().endswith("_alt")  # _alt.avi는 주 파일의 보조 입력

    def precheck(self, item: WorkItem, opts: dict[str, Any]) -> str | None:
        if opts.get("require_asc") and not (item.source.with_suffix(".asc")).is_file():
            return f"선행 .asc 없음: {item.source.with_suffix('.asc').name} (dvl→asc 변환을 먼저 수행)"
        return None

    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Backend) -> list[str]:
        subst = {
            "exe": tool_path,
            "input": backend.tool_path(item.source),
            "output_dir": backend.tool_path(item.output_dir),
            "stem": item.stem,
        }
        return [part.format(**subst) for part in self.argv_template]

    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        # exe에 출력 위치 옵션이 없어(실측) 산출물은 항상 원본 옆에 생긴다 — output_dir 지정은 무시
        d = item.source.parent
        return [d / f"{item.stem}.raw", d / f"{item.stem}.timestamp.txt"]
