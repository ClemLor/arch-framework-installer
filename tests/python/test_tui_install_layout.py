"""Tests for the installation screen's layout, with no terminal and no child.

The model is built from hand-written protocol records, so what is checked here is
purely how a state of the run is presented.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator.events import PROTOCOL_TAG, parse_line  # noqa: E402
from configurator.runner import InstallModel, TaskStatus  # noqa: E402
from configurator.tui import layout  # noqa: E402
from configurator.tui.glyphs import ASCII, UNICODE  # noqa: E402

TAB = "\t"


def record(kind: str, *fields: str) -> str:
    return TAB.join([PROTOCOL_TAG, kind, *fields])


def feed(model: InstallModel, *lines: str) -> None:
    for line in lines:
        event = parse_line(line)
        assert event is not None, line
        model.apply(event)


def started() -> InstallModel:
    model = InstallModel()
    feed(
        model,
        record("run_begin", "dry_run=true"),
        record("plan", "total=3"),
        record("plan_task", "index=1", "id=environment", "name=Environment"),
        record("plan_task", "index=2", "id=storage", "name=GPT partitioning"),
        record("plan_task", "index=3", "id=filesystem", "name=Btrfs layout"),
    )
    return model


class TaskLineTests(unittest.TestCase):
    def test_a_pending_task_carries_no_mark(self) -> None:
        model = started()
        line = layout.task_line(model.tasks[0], width=80, glyphs=ASCII, total=3)

        self.assertIn("[01/03]", line)
        self.assertIn("Environment", line)
        self.assertTrue(line.startswith("   ["))

    def test_a_running_task_shows_its_phase(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=1", "id=environment", "name=Environment"),
            record("phase", "id=environment", "phase=verify"),
        )
        line = layout.task_line(model.tasks[0], width=80, glyphs=ASCII, total=3)

        self.assertIn("verify", line)
        self.assertIn(ASCII.cursor, line)

    def test_a_finished_task_shows_its_duration(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=1", "id=environment", "name=Environment"),
            record("task_end", "index=1", "id=environment", "duration=12"),
        )
        line = layout.task_line(model.tasks[0], width=80, glyphs=UNICODE, total=3)

        self.assertIn("12s", line)
        self.assertIn(UNICODE.tick, line)

    def test_a_failed_task_names_the_phase(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=2", "id=storage", "name=GPT partitioning"),
            record("task_failed", "index=2", "id=storage", "phase=execute", "status=7"),
        )
        line = layout.task_line(model.tasks[1], width=80, glyphs=UNICODE, total=3)

        self.assertIn("failed in execute", line)
        self.assertIn(UNICODE.cross, line)

    def test_a_task_never_reached_says_so_rather_than_looking_failed(self) -> None:
        model = started()
        model.apply_child_exit(1)
        line = layout.task_line(model.tasks[2], width=80, glyphs=ASCII, total=3)

        self.assertEqual(model.tasks[2].status, TaskStatus.SKIPPED)
        self.assertIn("not reached", line)

    def test_a_narrow_terminal_truncates(self) -> None:
        model = started()
        for width in (60, 30, 12):
            line = layout.task_line(model.tasks[1], width=width, glyphs=ASCII, total=3)
            self.assertLessEqual(len(line), width, width)


class InstallLinesTests(unittest.TestCase):
    def test_one_line_per_task_with_the_running_one_highlighted(self) -> None:
        model = started()
        feed(model, record("task_begin", "index=2", "id=storage", "name=GPT partitioning"))
        lines = layout.install_lines(model, width=80, glyphs=ASCII)

        self.assertEqual(len(lines), 3)
        self.assertEqual([line.row for line in lines], [0, 1, 2])
        self.assertEqual(lines[1].style, "selected")

    def test_a_failure_is_styled_as_blocking(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=2", "id=storage", "name=GPT partitioning"),
            record("task_failed", "index=2", "id=storage", "phase=execute", "status=7"),
        )
        lines = layout.install_lines(model, width=80, glyphs=ASCII)
        self.assertEqual(lines[1].style, "blocked")


class ChromeTests(unittest.TestCase):
    def test_the_header_counts_finished_tasks_and_names_the_kind(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=1", "id=environment", "name=Environment"),
            record("task_end", "index=1", "id=environment", "duration=1"),
        )
        header = layout.install_header(model)

        self.assertIn("1/3", header)
        self.assertIn("dry run", header)

    def test_the_status_says_what_is_happening(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=2", "id=storage", "name=GPT partitioning"),
            record("phase", "id=storage", "phase=execute"),
        )
        self.assertEqual(layout.install_status(model), "GPT partitioning: execute")

    def test_the_status_explains_a_failure_and_its_rollback(self) -> None:
        model = started()
        feed(
            model,
            record("task_begin", "index=2", "id=storage", "name=GPT partitioning"),
            record("rollback_begin", "id=storage", "scope=partial"),
            record("task_failed", "index=2", "id=storage", "phase=execute", "status=7"),
            record("run_end", "status=7", "rolled_back=true"),
        )
        status = layout.install_status(model)

        self.assertIn("GPT partitioning", status)
        self.assertIn("execute", status)
        self.assertIn("Rolled back", status)

    def test_a_deliberate_stop_is_not_reported_as_incomplete(self) -> None:
        model = started()
        feed(model, record("run_end", "status=0", "stopped_after=storage"))
        status = layout.install_status(model)

        self.assertIn("storage", status)
        self.assertIn("Nothing failed", status)

    def test_an_interrupt_is_reported_as_one(self) -> None:
        model = started()
        feed(model, record("run_end", "status=130", "interrupted=true"))
        self.assertIn("Interrupted", layout.install_status(model))

    def test_the_footer_offers_interrupting_while_running_and_leaving_after(self) -> None:
        model = started()
        self.assertIn("interrupt", layout.install_footer(model))

        feed(model, record("run_end", "status=0"))
        self.assertIn("return", layout.install_footer(model))


if __name__ == "__main__":
    unittest.main()
