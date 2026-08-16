import json
import sys

import pytest

from misc_converter import cli
from misc_converter.backends import local as local_mod


@pytest.fixture
def tree(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "a.dvl").write_bytes(b"x")
    (d / "b.dvl").write_bytes(b"x")
    return d


@pytest.fixture
def cfg_path(tmp_path, make_fake_tool):
    tool = make_fake_tool("ok")
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "tools": {"aptiv": tool.path, "csv_extractor": tool.path},
                "wine": {"bin": sys.executable, "prefix": "", "xvfb": False},
                "log_dir": str(tmp_path / "logs"),
                "workers": 2,
                "retries": 0,
            }
        ),
        encoding="utf-8",
    )
    return cfg, tool


@pytest.fixture(autouse=True)
def _wine_as_python(monkeypatch):
    """테스트에서는 WineBackend가 exe 대신 python 스크립트를 실행하도록 wine 경로 변환을 무력화한다."""
    from misc_converter.backends import wine as wine_mod

    monkeypatch.setattr(wine_mod.WineBackend, "tool_path", lambda self, p: p.as_posix())
    monkeypatch.setattr("misc_converter.runtime.PathMapper.to_wine", staticmethod(lambda p: str(p)))
    assert local_mod is not None


def test_adapters_command(capsys):
    assert cli.main(["adapters"]) == 0
    out = capsys.readouterr().out
    for name in ["aptiv", "djlp", "csv", "pcap2pcd"]:
        assert name in out


def test_dry_run_exit_zero(tree, cfg_path, capsys):
    cfg, tool = cfg_path
    rc = cli.main(["--config", str(cfg), "aptiv", "-i", str(tree), "--asc", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PLN" in out and "계획 2" in out and tool.calls == 0


def test_real_run_success_and_log(tree, cfg_path, tmp_path, capsys):
    cfg, tool = cfg_path
    rc = cli.main(["--config", str(cfg), "aptiv", "-i", str(tree), "--asc"])
    assert rc == 0
    assert (tree / "a.asc").exists() and (tree / "b.asc").exists()
    assert list((tmp_path / "logs").glob("convert_*.json"))
    out = capsys.readouterr().out
    assert "변환 2" in out and "로그:" in out


def test_failure_exit_one(tree, cfg_path, capsys):
    cfg, tool = cfg_path
    tool.set_behavior("silent_fail")
    rc = cli.main(["--config", str(cfg), "aptiv", "-i", str(tree), "--asc"])
    assert rc == 1
    assert "실패 2" in capsys.readouterr().out


def test_missing_config_exit_two(tree, tmp_path, capsys):
    rc = cli.main(["--config", str(tmp_path / "nope.json"), "aptiv", "-i", str(tree), "--asc"])
    assert rc == 2 and "설정 파일" in capsys.readouterr().err


def test_missing_input_exit_two(cfg_path, tmp_path, capsys):
    cfg, _ = cfg_path
    rc = cli.main(["--config", str(cfg), "aptiv", "-i", str(tmp_path / "nope"), "--asc"])
    assert rc == 2 and "입력 경로" in capsys.readouterr().err


def test_no_writer_exit_two(tree, cfg_path, capsys):
    cfg, _ = cfg_path
    rc = cli.main(["--config", str(cfg), "aptiv", "-i", str(tree)])
    # 출력 포맷 미지정은 항목별 실패로 기록되므로 exit 1
    assert rc == 1
    assert "출력 포맷" in capsys.readouterr().out


def test_unknown_adapter_exit_two():
    with pytest.raises(SystemExit) as e:
        cli.main(["nope", "-i", "x"])
    assert e.value.code == 2


def test_flag_with_true_default_gets_no_prefix():
    p = cli.build_parser()
    ns = p.parse_args(["csv", "-i", "x", "--no-auto-swap"])
    assert ns.auto_swap is False
    ns = p.parse_args(["csv", "-i", "x"])
    assert ns.auto_swap is None  # 미지정 → 어댑터 기본값(True) 사용
