"""설정 로더 — config.json (표준 라이브러리만 사용)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Mount:
    linux: str
    windows: str


@dataclass(frozen=True)
class WineConfig:
    bin: str = "wine"
    prefix: str = ""
    xvfb: bool = True


@dataclass(frozen=True)
class DockerConfig:
    bin: str = "docker"
    volumes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    tools: dict[str, str] = field(default_factory=dict)
    mounts: dict[str, Mount] = field(default_factory=dict)
    wine: WineConfig = WineConfig()
    docker: DockerConfig = DockerConfig()
    djlp_argv_template: list[str] = field(default_factory=lambda: ["{exe}", "{input}"])
    workers: int = 4
    retries: int = 2
    timeout_s: int = 1800
    log_dir: str = "logs"
    web_port: int = 8768


def load_config(path: Path | str) -> Config:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"설정 파일이 없습니다: {p} (config.json.example을 복사해 작성)")
    raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    return config_from_dict(raw)


def config_from_dict(raw: dict[str, Any]) -> Config:
    mounts = {k: Mount(linux=v["linux"], windows=v["windows"]) for k, v in raw.get("mounts", {}).items()}
    wine_raw = raw.get("wine", {})
    docker_raw = raw.get("docker", {})
    return Config(
        tools=dict(raw.get("tools", {})),
        mounts=mounts,
        wine=WineConfig(
            bin=wine_raw.get("bin", "wine"),
            prefix=wine_raw.get("prefix", ""),
            xvfb=bool(wine_raw.get("xvfb", True)),
        ),
        docker=DockerConfig(bin=docker_raw.get("bin", "docker"), volumes=list(docker_raw.get("volumes", []))),
        djlp_argv_template=list(raw.get("djlp_argv_template", ["{exe}", "{input}"])),
        workers=int(raw.get("workers", 4)),
        retries=int(raw.get("retries", 2)),
        timeout_s=int(raw.get("timeout_s", 1800)),
        log_dir=str(raw.get("log_dir", "logs")),
        web_port=int(raw.get("web_port", 8768)),
    )
