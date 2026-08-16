from misc_converter.adapters.csv_extractor import CsvExtractorAdapter
from misc_converter.backends.local import LocalBackend
from misc_converter.engine.models import WorkItem
from misc_converter.engine.scanner import scan


def _tree(tmp_path):
    p = tmp_path / "P"
    for s in ["S1", "S2"]:
        d = p / s
        d.mkdir(parents=True)
        (d / f"{s}_can1.txt").write_bytes(b"x")
        (d / f"{s}_can2.txt").write_bytes(b"x")
        (d / f"{s}.txt").write_bytes(b"x")
    return p


def test_match_and_scan_groups_sessions(tmp_path):
    p = _tree(tmp_path)
    a = CsvExtractorAdapter()
    assert a.match(p / "S1", {}) and not a.match(p, {}) and not a.match(p / "S1" / "S1.txt", {})
    entries = scan([tmp_path], a, a.merge_options({}))
    assert len(entries) == 1
    it = entries[0].item
    assert it.source == p and it.extra["sessions"] == ["S1", "S2"] and entries[0].skip is False


def test_build_argv(tmp_path):
    p = _tree(tmp_path)
    a = CsvExtractorAdapter()
    it = WorkItem(source=p, output_dir=p, extra={"sessions": ["S1", "S2"]})
    argv = a.build_argv(it, a.merge_options({"ccan": "can2", "pcan": "can1"}), "/csv_extractor", LocalBackend())
    parent = p.as_posix() + "/"
    assert argv == ["/csv_extractor", "-d", parent, "-t", parent, "--aptiv", "--ccan", "can2", "--pcan", "can1", "-f"]


def test_expected_outputs_and_verify(tmp_path):
    p = _tree(tmp_path)
    a = CsvExtractorAdapter()
    it = WorkItem(source=p, output_dir=p, extra={"sessions": ["S1", "S2"]})
    opts = a.merge_options({})
    assert a.expected_outputs(it, opts) == [
        p / "S1" / "S1_ccan_3_2_1.csv",
        p / "S1" / "S1_pcan.csv",
        p / "S2" / "S2_ccan_3_2_1.csv",
        p / "S2" / "S2_pcan.csv",
    ]
    assert not a.verify(it, opts)
    for f in a.expected_outputs(it, opts):
        f.write_bytes(b"csv")
    assert a.verify(it, opts)


def test_retry_options_swaps_once():
    a = CsvExtractorAdapter()
    it = WorkItem(source=__import__("pathlib").Path("/x"), output_dir=__import__("pathlib").Path("/x"))
    opts = a.merge_options({"ccan": "can2", "pcan": "can1"})
    assert a.retry_options(it, opts, 1) == {"ccan": "can1", "pcan": "can2"}
    assert a.retry_options(it, opts, 2) is None
    assert a.retry_options(it, a.merge_options({"auto_swap": False}), 1) is None
