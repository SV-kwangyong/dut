import json

import pytest

from misc_converter.config import Config, load_config


def test_load_config_maps_fields(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "mounts": {"qumulo": {"linux": "/mnt/qumulo", "windows": "\\\\q\\datagroup"}},
                "tools": {"aptiv": "/t/a.exe", "csv_extractor": "/t/csv"},
                "wine": {"bin": "wine64", "prefix": "/wp", "xvfb": False},
                "docker": {"bin": "podman", "volumes": ["/mnt/qumulo:/mnt/qumulo"]},
                "djlp_argv_template": ["{exe}", "{input}", "--x"],
                "workers": 2,
                "retries": 1,
                "timeout_s": 60,
                "log_dir": "mylogs",
                "web_port": 9000,
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.tools["aptiv"] == "/t/a.exe"
    assert cfg.wine.bin == "wine64" and cfg.wine.prefix == "/wp" and cfg.wine.xvfb is False
    assert cfg.docker.bin == "podman" and cfg.docker.volumes == ["/mnt/qumulo:/mnt/qumulo"]
    assert cfg.djlp_argv_template == ["{exe}", "{input}", "--x"]
    assert (cfg.workers, cfg.retries, cfg.timeout_s, cfg.web_port) == (2, 1, 60, 9000)
    assert cfg.log_dir == "mylogs"
    assert cfg.mounts["qumulo"].linux == "/mnt/qumulo"


def test_load_config_defaults_for_missing_optional(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"tools": {}}), encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.workers == 4 and cfg.retries == 2 and cfg.timeout_s == 1800
    assert cfg.wine.bin == "wine" and cfg.docker.bin == "docker"
    assert cfg.mounts == {}


def test_load_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.json")
