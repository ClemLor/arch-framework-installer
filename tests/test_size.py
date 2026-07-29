from __future__ import annotations

import pytest

from arch_framework.lib.models import Size


@pytest.mark.parametrize(
    ("text", "mib"),
    [("512MiB", 512), ("1GiB", 1024), ("32GiB", 32768), ("1TiB", 1048576)],
)
def test_parse(text: str, mib: int) -> None:
    assert Size.parse(text).mib == mib


@pytest.mark.parametrize("text", ["32GB", "0GiB", "-1GiB", "32 GiB", "GiB", "1.5GiB"])
def test_parse_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        Size.parse(text)


def test_sgdisk_suffix_is_not_mib() -> None:
    """sgdisk accepts M/G/T, never MiB. Emitting MiB was a real bug."""
    assert Size.parse("1GiB").sgdisk() == "1024M"
    assert "MiB" not in Size.parse("1GiB").sgdisk()


def test_str_round_trips_through_parse() -> None:
    for text in ("512MiB", "1GiB", "32GiB", "1TiB"):
        assert str(Size.parse(text)) == text


def test_non_round_size_renders_as_mib() -> None:
    assert str(Size(1025)) == "1025MiB"


def test_bytes_and_from_bytes() -> None:
    assert Size.parse("1GiB").bytes == 1073741824
    assert Size.from_bytes(1073741824) == Size.parse("1GiB")


def test_ordering() -> None:
    assert Size.parse("1GiB") < Size.parse("2GiB")
