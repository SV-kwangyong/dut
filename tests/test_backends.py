from pathlib import PurePosixPath

from misc_converter.backends.docker import DockerBackend
from misc_converter.backends.local import LocalBackend
from misc_converter.backends.wine import WineBackend


def test_local_passthrough():
    b = LocalBackend()
    assert b.wrap(["x", "-i", "a"]) == ["x", "-i", "a"]
    assert b.tool_path(PurePosixPath("/a/b")) == "/a/b"
    assert "PATH" in b.env() or b.env() == {}


def test_wine_with_xvfb():
    b = WineBackend(bin="wine", prefix="/p", xvfb=True)
    assert b.wrap(["/t.exe", "-i", "a"]) == ["xvfb-run", "-a", "wine", "/t.exe", "-i", "a"]
    assert b.env()["WINEPREFIX"] == "/p"
    assert b.env()["WINEDEBUG"] == "-all"
    assert b.tool_path(PurePosixPath("/mnt/q/a.dvl")) == "Z:\\mnt\\q\\a.dvl"


def test_wine_without_xvfb_and_prefix():
    b = WineBackend(bin="wine64", prefix="", xvfb=False)
    assert b.wrap(["/t.exe"]) == ["wine64", "/t.exe"]
    assert "WINEPREFIX" not in b.env()


def test_docker_wrap():
    b = DockerBackend(bin="docker", image="img:1", volumes=["/mnt/qumulo:/mnt/qumulo"], user="1000:1000")
    assert b.wrap(["-p", "x"]) == [
        "docker",
        "run",
        "--rm",
        "--user",
        "1000:1000",
        "-v",
        "/mnt/qumulo:/mnt/qumulo",
        "img:1",
        "-p",
        "x",
    ]
    assert b.tool_path(PurePosixPath("/mnt/qumulo/a")) == "/mnt/qumulo/a"


def test_docker_cpus_and_no_user():
    b = DockerBackend(bin="docker", image="img", volumes=[], user=None, cpus=8)
    assert b.wrap([]) == ["docker", "run", "--rm", "--cpus", "8", "img"]


def test_use_pty_flags():
    assert LocalBackend().use_pty is False
    assert DockerBackend(bin="docker", image="i", volumes=[]).use_pty is False
    assert WineBackend().use_pty is True
