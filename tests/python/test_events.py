"""Tests for the progress protocol parser."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator.events import PROTOCOL_TAG, parse_line  # noqa: E402

TAB = "\t"


def record(kind: str, *fields: str) -> str:
    return TAB.join([PROTOCOL_TAG, kind, *fields])


class ParseTests(unittest.TestCase):
    def test_a_record_becomes_kind_and_fields(self) -> None:
        event = parse_line(record("task_begin", "index=3", "id=storage", "name=GPT partitioning"))

        assert event is not None
        self.assertEqual(event.kind, "task_begin")
        self.assertEqual(event.integer("index"), 3)
        self.assertEqual(event.get("name"), "GPT partitioning")

    def test_a_trailing_newline_is_not_part_of_the_value(self) -> None:
        event = parse_line(record("plan", "total=15") + "\n")
        assert event is not None
        self.assertEqual(event.integer("total"), 15)

    def test_a_carriage_return_is_stripped_too(self) -> None:
        event = parse_line(record("plan", "total=15") + "\r\n")
        assert event is not None
        self.assertEqual(event.get("total"), "15")

    def test_a_value_may_contain_an_equals_sign(self) -> None:
        event = parse_line(record("log", "level=COMMAND", "message=sgdisk --new=1:0:+1G"))
        assert event is not None
        self.assertEqual(event.get("message"), "sgdisk --new=1:0:+1G")

    def test_ordinary_output_is_not_an_event(self) -> None:
        for line in ("[01/15] GPT partitioning …", "", "AFI0\tplan\ttotal=1", "AFI1"):
            self.assertIsNone(parse_line(line), line)

    def test_an_unknown_kind_is_kept_rather_than_rejected(self) -> None:
        """A newer installer than the front-end must not look like a corrupt one."""
        event = parse_line(record("something_new", "field=value"))
        assert event is not None
        self.assertEqual(event.kind, "something_new")

    def test_a_field_with_no_value_is_ignored(self) -> None:
        event = parse_line(record("plan", "total", "=orphan", "real=1"))
        assert event is not None
        self.assertEqual(dict(event.fields), {"real": "1"})

    def test_missing_numbers_and_flags_have_defaults(self) -> None:
        event = parse_line(record("run_end", "status=nonsense"))
        assert event is not None
        self.assertEqual(event.integer("status", -1), -1)
        self.assertEqual(event.integer("absent", 7), 7)
        self.assertFalse(event.flag("interrupted"))


if __name__ == "__main__":
    unittest.main()
