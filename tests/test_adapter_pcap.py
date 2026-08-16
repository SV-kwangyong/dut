import json

from misc_converter.adapters.pcap2pcd import Pcap2PcdAdapter
from misc_converter.backends.docker import DockerBackend
from misc_converter.engine.models import WorkItem


def _item(tmp_path):
    src = tmp_path / "a.pcap"
    src.write_bytes(b"x")
    return WorkItem(source=src, output_dir=tmp_path)


def test_match(tmp_path):
    a = Pcap2PcdAdapter()
    (tmp_path / "a.pcap").write_bytes(b"x")
    (tmp_path / "b.PCAP").write_bytes(b"x")
    (tmp_path / "c.pcd").write_bytes(b"x")
    assert a.match(tmp_path / "a.pcap", {}) and a.match(tmp_path / "b.PCAP", {}) and not a.match(tmp_path / "c.pcd", {})


def test_build_argv_with_docker_backend(tmp_path):
    a = Pcap2PcdAdapter()
    it = _item(tmp_path)
    b = DockerBackend(bin="docker", image="surf:latest", volumes=["/mnt/qumulo:/mnt/qumulo"], user="1000:1000")
    argv = a.build_argv(it, a.merge_options({}), "surf:latest", b)
    assert argv == ["-p", it.source.as_posix(), "-o", tmp_path.as_posix()]
    assert b.wrap(argv)[-5:] == ["surf:latest", "-p", it.source.as_posix(), "-o", tmp_path.as_posix()]


def test_verify_requires_success_json_and_complete_tar(tmp_path):
    a = Pcap2PcdAdapter()
    it = _item(tmp_path)
    opts = a.merge_options({})
    assert not a.verify(it, opts)
    log = tmp_path / "a_convert_log.json"
    log.write_text(json.dumps({"success": False}))
    assert not a.verify(it, opts)
    log.write_text(json.dumps({"success": True}))
    assert not a.verify(it, opts)  # tar 없음
    (tmp_path / "a.tar").write_bytes(b"partial")  # 미완성(접미사 없음)
    assert not a.verify(it, opts)
    (tmp_path / "a_3001.tar").write_bytes(b"pcd")
    assert a.verify(it, opts)
    log.write_text("not json")
    assert not a.verify(it, opts)


def test_prepare_removes_incomplete_tar_only(tmp_path):
    a = Pcap2PcdAdapter()
    it = _item(tmp_path)
    (tmp_path / "a.tar").write_bytes(b"partial")
    (tmp_path / "a_3001.tar").write_bytes(b"pcd")
    a.prepare(it, {})
    assert not (tmp_path / "a.tar").exists() and (tmp_path / "a_3001.tar").exists()


def test_expected_outputs_is_log(tmp_path):
    a = Pcap2PcdAdapter()
    it = _item(tmp_path)
    assert a.expected_outputs(it, {}) == [tmp_path / "a_convert_log.json"]
