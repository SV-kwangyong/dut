from pathlib import Path
from typing import Any

import pytest

from misc_converter.adapters.aptiv import AptivAdapter
from misc_converter.adapters.base import Adapter
from misc_converter.engine.models import WorkItem
from misc_converter.engine.scanner import expand_inputs, scan


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.dvl").write_bytes(b"x")
    (tmp_path / "b.DVL").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "d.dvl").write_bytes(b"x")
    (tmp_path / "done.dvl").write_bytes(b"x")
    (tmp_path / "done.asc").write_bytes(b"converted")
    return tmp_path


def test_scan_directory_matches_and_skips(tree):
    entries = scan([tree], AptivAdapter(), AptivAdapter().merge_options({"asc": True}))
    names = [e.item.source.name for e in entries]
    assert names == ["a.dvl", "b.DVL", "done.dvl", "d.dvl"]
    skip = {e.item.source.name: e.skip for e in entries}
    assert skip == {"a.dvl": False, "b.DVL": False, "done.dvl": True, "d.dvl": False}
    # 출력 디렉터리 미지정 → 원본 옆
    assert entries[3].item.output_dir == tree / "sub"


def test_scan_asc_input_excludes_self_conversion(tree):
    opts = AptivAdapter().merge_options({"input_format": "asc", "asc": True})
    entries = scan([tree], AptivAdapter(), opts)
    assert entries == []  # done.asc → done.asc 자기 변환은 제외
    opts = AptivAdapter().merge_options({"input_format": "asc", "dvl": True})
    entries = scan([tree], AptivAdapter(), opts)
    assert [e.item.source.name for e in entries] == ["done.asc"]


def test_scan_force_ignores_existing(tree):
    entries = scan([tree], AptivAdapter(), {"asc": True}, force=True)
    assert all(not e.skip for e in entries)


def test_scan_explicit_output_dir(tree, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    entries = scan([tree / "a.dvl"], AptivAdapter(), {"asc": True}, output_dir=out)
    assert len(entries) == 1 and entries[0].item.output_dir == out


def test_scan_single_file_and_wildcard(tree):
    assert len(scan([tree / "a.dvl"], AptivAdapter(), {"asc": True})) == 1
    entries = scan([str(tree / "*.dvl")], AptivAdapter(), {"asc": True})
    names = [e.item.source.name for e in entries]
    assert "a.dvl" in names and "done.dvl" in names and "c.txt" not in names  # 대소문자는 OS glob에 따름


def test_expand_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        expand_inputs([tmp_path / "nope"])
    with pytest.raises(FileNotFoundError):
        expand_inputs([str(tmp_path / "*.zzz")])


class _SessionAdapter(Adapter):
    name = "sess"
    unit = "session_parent"
    options = []

    def match(self, path: Path, opts: dict[str, Any]) -> bool:
        return path.is_dir() and any(path.glob("*_can*.txt"))

    def build_argv(self, item: WorkItem, opts: dict[str, Any], tool_path: str, backend: Any) -> list[str]:
        return [tool_path]

    def expected_outputs(self, item: WorkItem, opts: dict[str, Any]) -> list[Path]:
        return [item.source / s / f"{s}_ccan.csv" for s in item.extra["sessions"]]


def test_scan_session_parent_groups_by_parent(tmp_path):
    for parent, sessions in {"P1": ["S1", "S2"], "P2": ["S3"]}.items():
        for s in sessions:
            d = tmp_path / parent / s
            d.mkdir(parents=True)
            (d / f"{s}_can1.txt").write_bytes(b"x")
    (tmp_path / "P1" / "S1" / "S1_ccan.csv").write_bytes(b"x")  # 부분 완료 → 부모 단위로는 미완료
    entries = scan([tmp_path], _SessionAdapter(), {})
    assert [(e.item.source.name, e.item.extra["sessions"], e.skip) for e in entries] == [
        ("P1", ["S1", "S2"], False),
        ("P2", ["S3"], False),
    ]
    (tmp_path / "P2" / "S3" / "S3_ccan.csv").write_bytes(b"x")
    entries = scan([tmp_path], _SessionAdapter(), {})
    assert entries[1].skip is True
