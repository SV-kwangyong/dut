"""입력 스캔 — 경로(파일·디렉터리·와일드카드)를 어댑터 작업 단위로 펼치고 스킵 여부를 판정한다.

스킵 판정은 무상태다: 기대 산출물이 전부 존재하면(어댑터 verify) 이미 끝난 것으로 본다.
force=True면 검증 결과와 무관하게 전부 재변환한다.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from misc_converter.adapters.base import Adapter
from misc_converter.engine.models import WorkItem


@dataclass
class ScanEntry:
    item: WorkItem
    skip: bool


def expand_inputs(inputs: list[str | Path]) -> list[Path]:
    """와일드카드 전개 + 존재 확인. 결과는 정렬·중복 제거."""
    out: list[Path] = []
    for raw in inputs:
        text = str(raw)
        if any(ch in text for ch in "*?["):
            matches = [Path(m) for m in glob.glob(text, recursive=True)]
            if not matches:
                raise FileNotFoundError(f"패턴에 해당하는 파일이 없습니다: {text}")
            out.extend(matches)
            continue
        p = Path(text)
        if not p.exists():
            raise FileNotFoundError(f"입력 경로가 없습니다: {p}")
        out.append(p)
    return sorted(set(out))


def _walk_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def _walk_dirs(root: Path) -> list[Path]:
    return sorted([root, *(p for p in root.rglob("*") if p.is_dir())])


def collect_items(
    inputs: list[str | Path], adapter: Adapter, opts: dict[str, Any], output_dir: Path | None
) -> list[WorkItem]:
    roots = expand_inputs(inputs)
    if adapter.unit == "file":
        files: list[Path] = []
        for r in roots:
            files.extend(_walk_files(r) if r.is_dir() else [r])
        matched = [f for f in sorted(set(files)) if adapter.match(f, opts)]
        items = [WorkItem(source=f, output_dir=output_dir or f.parent) for f in matched]
        # 자기 변환(입력 == 기대 산출물) 제외 — 예: 이미 변환된 .asc가 다시 .asc 입력으로 잡히는 경우
        return [it for it in items if it.source not in adapter.expected_outputs(it, opts)]

    # session_parent: 세션 디렉터리를 찾고 부모별로 묶는다 — 도구가 부모를 받아 하위 세션 전부를 처리하기 때문
    sessions: list[Path] = []
    for r in roots:
        cands = _walk_dirs(r) if r.is_dir() else [r.parent]
        sessions.extend(d for d in cands if adapter.match(d, opts))
    by_parent: dict[Path, list[str]] = {}
    for s in sorted(set(sessions)):
        by_parent.setdefault(s.parent, []).append(s.name)
    return [
        WorkItem(source=parent, output_dir=output_dir or parent, extra={"sessions": names})
        for parent, names in sorted(by_parent.items())
    ]


def scan(
    inputs: list[str | Path],
    adapter: Adapter,
    opts: dict[str, Any],
    output_dir: Path | None = None,
    force: bool = False,
) -> list[ScanEntry]:
    items = collect_items(inputs, adapter, opts, output_dir)
    return [ScanEntry(item=it, skip=(not force) and adapter.verify(it, opts)) for it in items]
