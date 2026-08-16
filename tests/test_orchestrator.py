import json
import threading

import pytest

from misc_converter.adapters.aptiv import AptivAdapter
from misc_converter.engine.models import ItemStatus
from misc_converter.engine.orchestrator import run_job
from misc_converter.engine.report import format_summary


@pytest.fixture
def tree(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    for n in ["a", "b", "done"]:
        (d / f"{n}.dvl").write_bytes(b"x")
    (d / "done.asc").write_bytes(b"already")
    return d


def _job(tree, tool, backend, **kw):
    kw.setdefault("workers", 2)
    kw.setdefault("retries", 0)
    kw.setdefault("timeout_s", 10)
    kw.setdefault("backoff", (0.0,))
    return run_job([tree], AptivAdapter(), {"asc": True}, backend, tool.path, **kw)


def test_run_job_counts_and_report_files(tree, tmp_path, make_fake_tool, py_backend):
    tool = make_fake_tool("ok")
    calls = []
    logs = tmp_path / "logs"
    s = _job(tree, tool, py_backend, log_dir=logs, progress=lambda d, t, r: calls.append((d, t, r.status)))
    assert (s.total, s.converted, s.skipped, s.failed) == (3, 2, 1, 0)
    assert len(calls) == 3 and calls[-1][0] == 3 and all(t == 3 for _, t, _ in calls)
    assert s.log_path and s.log_path.exists() and s.json_path and s.json_path.exists()
    data = json.loads(s.json_path.read_text(encoding="utf-8"))
    assert data["converted"] == 2 and len(data["results"]) == 3
    assert [r["status"] for r in data["results"]] == ["converted", "converted", "skipped"]  # 스캔 순서 유지
    text = s.log_path.read_text(encoding="utf-8")
    assert "변환 2" in text and "[skipped]" in text
    assert (tree / "a.asc").exists() and (tree / "b.asc").exists()
    assert (tree / "done.asc").read_bytes() == b"already"  # 스킵된 항목은 손대지 않는다


def test_run_job_dry_run_executes_nothing(tree, make_fake_tool, py_backend):
    tool = make_fake_tool("ok")
    s = _job(tree, tool, py_backend, dry_run=True)
    assert tool.calls == 0
    assert s.count(ItemStatus.PLANNED) == 2 and s.skipped == 1
    planned = [r for r in s.results if r.status is ItemStatus.PLANNED]
    assert all("--asc" in r.argv for r in planned)


def test_run_job_dry_run_reports_argv_error(tree, make_fake_tool, py_backend):
    tool = make_fake_tool("ok")
    s = run_job([tree], AptivAdapter(), {}, py_backend, tool.path, dry_run=True)
    assert s.failed == 2 and "출력 포맷" in s.results[0].message


def test_run_job_failure_summary_text(tree, make_fake_tool, py_backend):
    tool = make_fake_tool("silent_fail")
    s = _job(tree, tool, py_backend)
    assert s.failed == 2
    text = format_summary(s)
    assert "실패 목록" in text and "output_missing" in text


def test_run_job_cancel_marks_remaining(tree, make_fake_tool, py_backend):
    tool = make_fake_tool("ok")
    ev = threading.Event()
    ev.set()
    s = _job(tree, tool, py_backend, cancel=ev)
    assert s.count(ItemStatus.CANCELLED) == 2 and s.skipped == 1 and tool.calls == 0


def test_run_job_force_reconverts(tree, make_fake_tool, py_backend):
    tool = make_fake_tool("ok")
    s = _job(tree, tool, py_backend, force=True)
    assert s.converted == 3 and s.skipped == 0


def test_run_job_no_log_dir_leaves_paths_none(tree, make_fake_tool, py_backend):
    s = _job(tree, make_fake_tool("ok"), py_backend)
    assert s.log_path is None and s.json_path is None
