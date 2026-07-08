"""Tests for the StatusList2021-style revocation bitstring."""
import pytest

from pancake_services.grants.statuslist import StatusList


def test_default_all_unrevoked():
    sl = StatusList()
    assert not sl.is_revoked(0)
    assert not sl.is_revoked(65535)


def test_set_and_check():
    sl = StatusList()
    sl.set(42)
    assert sl.is_revoked(42)
    assert not sl.is_revoked(41)
    assert not sl.is_revoked(43)


def test_unset():
    sl = StatusList()
    sl.set(7)
    sl.set(7, revoked=False)
    assert not sl.is_revoked(7)


def test_encode_decode_roundtrip():
    sl = StatusList()
    for idx in (0, 1, 100, 65535):
        sl.set(idx)
    decoded = StatusList.decode(sl.encode())
    assert decoded.size == sl.size
    for idx in (0, 1, 100, 65535):
        assert decoded.is_revoked(idx)
    assert not decoded.is_revoked(2)


def test_out_of_range_raises():
    sl = StatusList(size=8)
    with pytest.raises(IndexError):
        sl.set(8)
    with pytest.raises(IndexError):
        sl.is_revoked(-1)


def test_invalid_size_rejected():
    with pytest.raises(ValueError):
        StatusList(size=0)
    with pytest.raises(ValueError):
        StatusList(size=12)


def test_encoding_is_compact():
    sl = StatusList()  # 64K bits, all zero
    assert len(sl.encode()) < 100  # zlib collapses the zero run
