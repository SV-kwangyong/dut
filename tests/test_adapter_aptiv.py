import pytest

from misc_converter.adapters.aptiv import AptivAdapter
from misc_converter.backends.local import LocalBackend
from misc_converter.engine.models import WorkItem


@pytest.fixture
def adapter():
    return AptivAdapter()


@pytest.fixture
def item(tmp_path):
    src = tmp_path / "in" / "a.dvl"
    src.parent.mkdir()
    src.write_bytes(b"x")
    out = tmp_path / "out"
    out.mkdir()
    return WorkItem(source=src, output_dir=out)


def test_match_input_extensions(tmp_path, adapter):
    any_opts = adapter.merge_options({"input": "any"})
    for name in ["a.dvl", "b.DVL", "c.dvs", "d.dvsu", "e.mudp", "f.asc", "g.mf4"]:
        p = tmp_path / name
        p.write_bytes(b"x")
        assert adapter.match(p, any_opts), name
    (tmp_path / "h.txt").write_bytes(b"x")
    assert not adapter.match(tmp_path / "h.txt", any_opts)
    assert not adapter.match(tmp_path, any_opts)  # 디렉터리


def test_match_default_input_filter_is_dvl(tmp_path, adapter):
    opts = adapter.merge_options({})
    (tmp_path / "a.dvl").write_bytes(b"x")
    (tmp_path / "f.asc").write_bytes(b"x")
    assert adapter.match(tmp_path / "a.dvl", opts)
    assert not adapter.match(tmp_path / "f.asc", opts)
    assert adapter.match(tmp_path / "f.asc", adapter.merge_options({"input": "asc"}))


def test_build_argv_asc_defaults(adapter, item):
    opts = adapter.merge_options({"asc": True})
    argv = adapter.build_argv(item, opts, "/t.exe", LocalBackend())
    assert argv == [
        "/t.exe",
        "-i",
        item.source.as_posix(),
        "-o",
        item.output_dir.as_posix(),
        "-y",
        "--asc",
        "--ascbase=hex",
        "--asctimeref=absolute",
    ]


def test_build_argv_multiple_writers_no_duplicate_suboptions(adapter, item):
    opts = adapter.merge_options({"mudp": True, "pcap": True, "ethsrcip": "10.0.0.1"})
    argv = adapter.build_argv(item, opts, "/t.exe", LocalBackend())
    assert argv.count("--ethernetmap=default") == 1
    assert "--ethsrcip=10.0.0.1" in argv
    assert "--pcapmtu=1500" in argv
    assert "--mudp" in argv and "--pcap" in argv


def test_build_argv_requires_writer(adapter, item):
    with pytest.raises(ValueError):
        adapter.build_argv(item, adapter.merge_options({}), "/t.exe", LocalBackend())


def test_expected_outputs(adapter, item):
    out = item.output_dir
    assert adapter.expected_outputs(item, adapter.merge_options({"asc": True, "dvl": True})) == [
        out / "a.asc",
        out / "a.dvl",
    ]
    assert adapter.expected_outputs(item, adapter.merge_options({"dvs": True, "dvsextension": "dvsu"})) == [
        out / "a.dvsu"
    ]
    assert adapter.expected_outputs(item, adapter.merge_options({"lcm": True})) == []


def test_verify_expected(adapter, item):
    opts = adapter.merge_options({"asc": True})
    assert not adapter.verify(item, opts)
    (item.output_dir / "a.asc").write_bytes(b"")
    assert not adapter.verify(item, opts)  # 0바이트는 실패
    (item.output_dir / "a.asc").write_bytes(b"data")
    assert adapter.verify(item, opts)


def test_verify_unknown_extension_uses_stem_glob(adapter, item):
    opts = adapter.merge_options({"lcm": True})
    assert not adapter.verify(item, opts)
    (item.output_dir / "a.lcmlog").write_bytes(b"data")
    assert adapter.verify(item, opts)


def test_verify_stem_glob_ignores_source_when_same_dir(adapter, tmp_path):
    src = tmp_path / "a.dvl"
    src.write_bytes(b"x")
    it = WorkItem(source=src, output_dir=tmp_path)
    assert not adapter.verify(it, adapter.merge_options({"lcm": True}))


def test_describe_lists_options(adapter):
    d = adapter.describe()
    assert d["name"] == "aptiv" and d["backend"] == "wine"
    names = [o["name"] for o in d["options"]]
    assert {"asc", "dvl", "dvs", "lcm", "mudp", "pcap", "adtf"} <= set(names)
