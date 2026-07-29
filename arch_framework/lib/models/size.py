"""Binary size values.

The Bash implementation accepted ``1024MiB``, ``32GiB`` and ``1TiB`` and did
arithmetic in MiB. That format is kept so existing configs and documentation
stay meaningful, but the conversion to the suffixes ``sgdisk`` actually accepts
(``M``/``G``/``T``, which already mean MiB/GiB/TiB) now lives in one place.
Emitting ``MiB`` to sgdisk was a real bug in the Bash version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

_PATTERN = re.compile(r"^([1-9][0-9]*)(MiB|GiB|TiB)$")
_MULTIPLIER_MIB = {"MiB": 1, "GiB": 1024, "TiB": 1024 * 1024}

_MIB = 1024 * 1024


@dataclass(frozen=True, order=True)
class Size:
    """A size expressed as a whole number of MiB."""

    mib: int

    @classmethod
    def parse(cls, value: str) -> "Size":
        match = _PATTERN.match(value.strip())
        if match is None:
            raise ValueError(
                f"unsupported size {value!r}: use 1024MiB, 32GiB or 1TiB"
            )
        number, unit = match.groups()
        return cls(int(number) * _MULTIPLIER_MIB[unit])

    @classmethod
    def from_bytes(cls, value: int) -> "Size":
        return cls(value // _MIB)

    @property
    def bytes(self) -> int:
        return self.mib * _MIB

    def sgdisk(self) -> str:
        """Suffix form sgdisk understands. ``M`` already means MiB."""
        return f"{self.mib}M"

    def __str__(self) -> str:
        if self.mib % (1024 * 1024) == 0:
            return f"{self.mib // (1024 * 1024)}TiB"
        if self.mib % 1024 == 0:
            return f"{self.mib // 1024}GiB"
        return f"{self.mib}MiB"

    def human(self) -> str:
        value = float(self.bytes)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if value < 1024 or unit == "TiB":
                if unit == "B":
                    return f"{int(value)} B"
                return f"{value:.2f} {unit}"
            value /= 1024
        raise AssertionError("unreachable")

    # -- pydantic integration ----------------------------------------------

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(cls._validate),
            python_schema=core_schema.no_info_plain_validator_function(cls._validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def _validate(cls, value: Any) -> "Size":
        if isinstance(value, Size):
            return value
        if isinstance(value, str):
            return cls.parse(value)
        raise ValueError(f"expected a size string such as '32GiB', got {value!r}")
