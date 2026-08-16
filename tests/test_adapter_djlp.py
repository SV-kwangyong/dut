from misc_converter.adapters.djlp import DjlpAdapter
from misc_converter.backends.local import LocalBackend
from misc_converter.engine.models import WorkItem


def test_match_excludes_alt(tmp_path):
    a = DjlpAdapter()
    for n in ["a.avi", "a_alt.avi", "b.tavi", "c.webm", "d.mp4"]:
        (tmp_path / n).write_bytes(b"x")
    assert a.match(tmp_path / "a.avi", {})
    assert not a.match(tmp_path / "a_alt.avi", {})
    assert a.match(tmp_path / "b.tavi", {}) and a.match(tmp_path / "c.webm", {})
    assert not a.match(tmp_path / "d.mp4", {})


def test_build_argv_default_and_custom_template(tmp_path):
    src = tmp_path / "a.avi"
    src.write_bytes(b"x")
    it = WorkItem(source=src, output_dir=tmp_path)
    assert DjlpAdapter().build_argv(it, {}, "/t.exe", LocalBackend()) == ["/t.exe", "-s", src.as_posix()]
    custom = DjlpAdapter(argv_template=["{exe}", "--cli", "{input}", "--out", "{output_dir}", "--name", "{stem}"])
    assert custom.build_argv(it, {}, "/t.exe", LocalBackend()) == [
        "/t.exe",
        "--cli",
        src.as_posix(),
        "--out",
        tmp_path.as_posix(),
        "--name",
        "a",
    ]


def test_precheck_requires_asc(tmp_path):
    src = tmp_path / "a.avi"
    src.write_bytes(b"x")
    it = WorkItem(source=src, output_dir=tmp_path)
    a = DjlpAdapter()
    assert "선행 .asc 없음" in (a.precheck(it, a.merge_options({})) or "")
    assert a.precheck(it, a.merge_options({"require_asc": False})) is None
    (tmp_path / "a.asc").write_bytes(b"asc")
    assert a.precheck(it, a.merge_options({})) is None


def test_expected_outputs(tmp_path):
    src = tmp_path / "a.avi"
    it = WorkItem(source=src, output_dir=tmp_path)
    assert DjlpAdapter().expected_outputs(it, {}) == [tmp_path / "a.raw", tmp_path / "a.timestamp.txt"]
