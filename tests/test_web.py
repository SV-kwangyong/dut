import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from misc_converter.config import config_from_dict
from misc_converter.web.server import create_app


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "mnt" / "qumulo"
    d = root / "proj" / "raw"
    d.mkdir(parents=True)
    (d / "a.dvl").write_bytes(b"x")
    (d / "b.dvl").write_bytes(b"x")
    return root, d


@pytest.fixture
def client(tmp_path, tree, make_fake_tool, monkeypatch):
    root, _ = tree
    tool = make_fake_tool("ok")
    from misc_converter.backends import wine as wine_mod

    monkeypatch.setattr(wine_mod.WineBackend, "tool_path", lambda self, p: p.as_posix())
    monkeypatch.setattr("misc_converter.runtime.PathMapper.to_wine", staticmethod(lambda p: str(p)))
    cfg = config_from_dict(
        {
            "mounts": {"qumulo": {"linux": root.as_posix(), "windows": "\\\\qumulo.stradvision.com\\datagroup"}},
            "tools": {"aptiv": tool.path, "csv_extractor": tool.path},
            "wine": {"bin": sys.executable, "prefix": "", "xvfb": False},
            "log_dir": str(tmp_path / "logs"),
            "workers": 2,
            "retries": 0,
        }
    )
    app = create_app(cfg, db_path=tmp_path / "jobs.db")
    with TestClient(app) as c:
        c.tool = tool  # type: ignore[attr-defined]
        yield c


def _wait(client, job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("잡이 제한 시간 안에 끝나지 않음")


def test_adapters_endpoint(client):
    data = client.get("/api/adapters").json()
    names = {a["name"] for a in data}
    assert names == {"aptiv", "djlp", "csv", "pcap2pcd"}
    aptiv = next(a for a in data if a["name"] == "aptiv")
    assert any(o["name"] == "asc" and o["kind"] == "flag" for o in aptiv["options"])


def test_submit_dry_run_and_complete(client, tree):
    _, d = tree
    r = client.post(
        "/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}, "dry_run": True}
    )
    assert r.status_code == 202
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done"
    assert job["summary"]["planned"] == 2 and job["progress_done"] == 2 and job["progress_total"] == 2
    assert client.tool.calls == 0


def test_submit_real_run(client, tree):
    _, d = tree
    r = client.post("/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}})
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done" and job["summary"]["converted"] == 2
    assert (d / "a.asc").exists()
    listing = client.get("/api/jobs").json()
    assert listing[0]["id"] == job["id"] and "summary" not in listing[0]


def test_unc_input_is_mapped(client, tree):
    _, d = tree
    unc = "\\\\qumulo.stradvision.com\\datagroup\\proj\\raw"
    r = client.post("/api/jobs", json={"adapter": "aptiv", "inputs": [unc], "options": {"asc": True}, "dry_run": True})
    assert r.status_code == 202
    job = _wait(client, r.json()["id"])
    assert job["inputs"] == [d.as_posix()] and job["status"] == "done"


def test_reject_outside_mount_and_unknown_adapter(client, tmp_path):
    r = client.post("/api/jobs", json={"adapter": "aptiv", "inputs": ["/etc"], "options": {}})
    assert r.status_code == 400
    r = client.post("/api/jobs", json={"adapter": "nope", "inputs": ["/x"], "options": {}})
    assert r.status_code == 400
    r = client.post("/api/jobs", json={"adapter": "djlp", "inputs": [str(tmp_path)], "options": {}})
    assert r.status_code == 400  # tools.djlp 미설정 → 설정 오류로 거부


def test_failed_job_status(client, tree):
    _, d = tree
    client.tool.set_behavior("silent_fail")
    r = client.post("/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}})
    job = _wait(client, r.json()["id"])
    assert job["status"] == "failed" and job["summary"]["failed"] == 2


def test_jobs_run_serially(client, tree):
    _, d = tree
    ids = []
    for _ in range(2):
        r = client.post(
            "/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}, "force": True}
        )
        ids.append(r.json()["id"])
    j1, j2 = (_wait(client, i) for i in ids)
    assert j1["finished_at"] <= j2["started_at"]


def test_cancel_queued_job(client, tree):
    _, d = tree
    client.tool.set_behavior("hang")
    r1 = client.post(
        "/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}, "timeout_s": 2}
    )
    r2 = client.post("/api/jobs", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}})
    c = client.post(f"/api/jobs/{r2.json()['id']}/cancel").json()
    assert c["status"] == "cancelled"
    assert client.get(f"/api/jobs/{r2.json()['id']}").json()["status"] == "cancelled"
    _wait(client, r1.json()["id"], timeout=15)


def test_browse(client, tree):
    root, d = tree
    r = client.get("/api/browse", params={"path": root.as_posix()})
    assert r.status_code == 200 and r.json()["dirs"] == ["proj"]
    r = client.get("/api/browse", params={"path": d.as_posix()})
    assert r.json()["files"] == ["a.dvl", "b.dvl"]
    assert client.get("/api/browse", params={"path": "/etc"}).status_code == 400
    assert client.get("/api/browse", params={"path": (root / "nope").as_posix()}).status_code == 404


def test_meta_and_index(client):
    assert client.get("/api/meta").json()["version"]
    r = client.get("/")
    assert r.status_code == 200 and "misc_converter" in r.text


def test_presets_endpoint(client):
    data = client.get("/api/presets").json()
    ids = [p["id"] for p in data]
    assert ids[0] == "dvl2asc" and {"avi2raw", "txt2csv", "pcap2pcd"} <= set(ids)
    assert data[0]["adapter"] == "aptiv" and data[0]["options"]["asc"] is True


def test_preview_counts_without_running(client, tree):
    _, d = tree
    (d / "a.asc").write_bytes(b"done")
    r = client.post("/api/preview", json={"adapter": "aptiv", "inputs": [d.as_posix()], "options": {"asc": True}})
    assert r.status_code == 200
    j = r.json()
    assert (j["total"], j["todo"], j["skipped"]) == (2, 1, 1)
    assert [Path(x).name for x in j["sample_todo"]] == ["b.dvl"] and client.tool.calls == 0
    r = client.post("/api/preview", json={"adapter": "aptiv", "inputs": [(d / "nope").as_posix()], "options": {}})
    assert r.status_code == 404
