from pathlib import PurePosixPath

import pytest

from misc_converter.config import Mount
from misc_converter.paths import PathMapper


@pytest.fixture
def mapper():
    return PathMapper({"qumulo": Mount(linux="/mnt/qumulo", windows="\\\\qumulo.stradvision.com\\datagroup")})


def test_unc_to_local(mapper):
    assert mapper.to_local("\\\\qumulo.stradvision.com\\datagroup\\a\\b.dvl") == PurePosixPath("/mnt/qumulo/a/b.dvl")


def test_unc_case_insensitive_host(mapper):
    assert mapper.to_local("\\\\QUMULO.stradvision.com\\Datagroup\\x") == PurePosixPath("/mnt/qumulo/x")


def test_linux_path_passthrough(mapper):
    assert mapper.to_local("/mnt/qumulo/a") == PurePosixPath("/mnt/qumulo/a")


def test_forward_slash_unc(mapper):
    assert mapper.to_local("//qumulo.stradvision.com/datagroup/a") == PurePosixPath("/mnt/qumulo/a")


def test_unregistered_path_rejected(mapper):
    with pytest.raises(ValueError):
        mapper.to_local("/etc/passwd")
    with pytest.raises(ValueError):
        mapper.to_local("\\\\other\\share\\x")


def test_is_allowed(mapper):
    assert mapper.is_allowed(PurePosixPath("/mnt/qumulo/a"))
    assert not mapper.is_allowed(PurePosixPath("/mnt/qumulo2/a"))
    assert not mapper.is_allowed(PurePosixPath("/mnt/qumulo/../etc"))


def test_to_wine(mapper):
    assert mapper.to_wine(PurePosixPath("/mnt/qumulo/a b/c.dvl")) == "Z:\\mnt\\qumulo\\a b\\c.dvl"


def test_no_mounts_allows_nothing_but_passthrough_disabled():
    m = PathMapper({})
    with pytest.raises(ValueError):
        m.to_local("/mnt/qumulo/a")
