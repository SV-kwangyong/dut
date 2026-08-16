"""csv_extractor-3.10.0 어댑터 — SESSION_canN.txt + SESSION.txt → SESSION_ccan_3_2_1.csv / SESSION_pcan.csv.

매뉴얼([DUT] AVI Conversion Manual §3.2)의 함정을 코드로 옮긴다:
- `-d`/`-t`는 세션 폴더가 아니라 **상위 폴더**를 받는다 → 작업 단위 = session_parent.
- ccan/pcan을 반대로 주면 에러 없이 "Extraction finish!"가 뜨고 csv는 0개다(침묵 실패)
  → 산출물 검증 실패 시 --ccan/--pcan을 맞바꿔 1회 자동 재시도(auto_swap).
- `--aptiv/--ccan/--pcan`은 `--help`에 안 나오지만 동작한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter, OptionSpec
from misc_converter.backends.base import Backend
from misc_converter.engine.models import WorkItem

CCAN_SUFFIX = "_ccan_3_2_1.csv"
PCAN_SUFFIX = "_pcan.csv"


class CsvExtractorAdapter(Adapter):
    name = "csv"
    description = "csv_extractor — SESSION_canN.txt → _ccan_3_2_1.csv / _pcan.csv (ccan/pcan 자동 스왑)"
    unit = "session_parent"
    tool_key = "csv_extractor"
    backend_kind = "local"
    options = [
        OptionSpec("ccan", "str", "can2", help="CCAN 버스로 배정할 canN (예: can2)"),
        OptionSpec("pcan", "str", "can1", help="PCAN 버스로 배정할 canN (예: can1)"),
        OptionSpec("auto_swap", "flag", True, help="csv 미생성 시 ccan/pcan을 맞바꿔 1회 재시도"),
    ]

    def match(self, path: Path, opts: dict[str, Any]) -> bool:
        return path.is_dir() and any(path.glob("*_can*.txt"))

    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Backend) -> list[str]:
        parent = backend.tool_path(item.source).rstrip("/") + "/"
        return [
            tool_path,
            "-d",
            parent,
            "-t",
            parent,
            "--aptiv",
            "--ccan",
            str(opts["ccan"]),
            "--pcan",
            str(opts["pcan"]),
            "-f",
        ]

    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        outs: list[Path] = []
        for s in item.extra.get("sessions", []):
            outs.append(item.source / s / f"{s}{CCAN_SUFFIX}")
            outs.append(item.source / s / f"{s}{PCAN_SUFFIX}")
        return outs

    def retry_options(self, item: WorkItem, opts: dict[str, Any], attempt: int) -> dict[str, Any] | None:
        if attempt == 1 and opts.get("auto_swap"):
            return {"ccan": opts["pcan"], "pcan": opts["ccan"]}
        return None
