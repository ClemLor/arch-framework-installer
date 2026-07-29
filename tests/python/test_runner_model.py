"""Tests for the install model, fed hand-written protocol records.

No subprocess, no pipes, no platform assumptions: this is the coverage that runs
everywhere, including the Windows machine the project is developed on.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator.events import PROTOCOL_TAG, parse_line  # noqa: E402
from configurator.runner import InstallModel, Outcome, TaskStatus  # noqa: E402

TAB = "\t"

PLAN = [
    (1, "environment", "Environment"),
    (2, "storage", "GPT partitioning"),
    (3, "filesystem", "Btrfs layout"),
]


def record(kind: str, *fields: str) -> str:
    return TAB.join([PROTOCOL_TAG, kind, *fields])


def feed(model: InstallModel, *lines: str) -> None:
    for line in lines:
        event = parse_line(line)
        assert event is not None, line
        model.apply(event)


def planned(model: InstallModel) -> None:
    feed(model, record("run_begin", "dry_run=true", "log_file=logs/x.log"))
    feed(model, record("plan", f"total={len(PLAN)}"))
    for index, identifier, name in PLAN:
        feed(model, record("plan_task", f"index={index}", f"id={identifier}", f"name={name}"))


def succeed(model: InstallModel, identifier: str, index: int, duration: int = 2) -> None:
    feed(
        model,
        record("task_begin", f"index={index}", f"id={identifier}", "name=x"),
        record("phase", f"id={identifier}", "phase=validate"),
        record("phase", f"id={identifier}", "phase=execute"),
        record("task_end", f"index={index}", f"id={identifier}", f"duration={duration}"),
    )


class PlanTests(unittest.TestCase):
    def test_the_whole_plan_is_known_before_the_first_task(self) -> None:
        """The screen shows fifteen pending steps at once instead of growing a
        list, which is the difference between a plan and a log."""
        model = InstallModel()
        planned(model)

        self.assertEqual(model.total, 3)
        self.assertEqual([task.name for task in model.tasks], [row[2] for row in PLAN])
        self.assertTrue(all(task.status is TaskStatus.PENDING for task in model.tasks))
        self.assertTrue(model.dry_run)
        self.assertEqual(model.log_file, "logs/x.log")

    def test_a_task_with_no_plan_still_appears(self) -> None:
        model = InstallModel()
        feed(model, record("task_begin", "index=1", "total=9", "id=storage", "name=GPT"))

        self.assertEqual(len(model.tasks), 1)
        self.assertEqual(model.total, 9)


class ProgressTests(unittest.TestCase):
    def test_a_running_task_reports_its_phase(self) -> None:
        model = InstallModel()
        planned(model)
        feed(
            model,
            record("task_begin", "index=1", "id=environment", "name=Environment"),
            record("phase", "id=environment", "phase=verify"),
        )

        current = model.current
        assert current is not None
        self.assertEqual((current.id, current.phase), ("environment", "verify"))
        self.assertEqual(model.progress(), (0, 3))

    def test_a_finished_task_keeps_its_duration(self) -> None:
        model = InstallModel()
        planned(model)
        succeed(model, "environment", 1, duration=4)

        self.assertEqual(model.tasks[0].status, TaskStatus.DONE)
        self.assertEqual(model.tasks[0].duration, 4)
        self.assertIsNone(model.tasks[0].phase)
        self.assertEqual(model.progress(), (1, 3))

    def test_the_log_carries_level_and_message(self) -> None:
        model = InstallModel()
        feed(model, record("log", "level=WARN", "message=Signal INT received"))
        self.assertEqual(list(model.log), ["[WARN] Signal INT received"])

    def test_the_log_is_bounded(self) -> None:
        model = InstallModel(scrollback=10)
        for index in range(50):
            feed(model, record("log", "level=INFO", f"message=line {index}"))

        self.assertEqual(len(model.log), 10)
        self.assertEqual(model.log[-1], "[INFO] line 49")


class OutcomeTests(unittest.TestCase):
    def test_a_clean_run_succeeds(self) -> None:
        model = InstallModel()
        planned(model)
        for index, identifier, _ in PLAN:
            succeed(model, identifier, index)
        feed(model, record("run_end", "status=0", "interrupted=false", "rolled_back=false"))

        self.assertEqual(model.outcome, Outcome.SUCCESS)
        self.assertEqual(model.exit_code, 0)
        self.assertTrue(model.finished)
        self.assertEqual(model.progress(), (3, 3))

    def test_a_failure_names_the_phase_and_rolls_back(self) -> None:
        model = InstallModel()
        planned(model)
        succeed(model, "environment", 1)
        feed(
            model,
            record("task_begin", "index=2", "id=storage", "name=GPT partitioning"),
            record("phase", "id=storage", "phase=execute"),
            record("rollback_begin", "id=storage", "scope=partial"),
            record("rollback_end", "id=storage", "scope=partial", "status=0"),
            record("task_failed", "index=2", "id=storage", "phase=execute", "status=7"),
            record("run_end", "status=7", "interrupted=false", "rolled_back=true"),
        )

        self.assertEqual(model.outcome, Outcome.FAILURE)
        self.assertTrue(model.rollback_happened)
        self.assertEqual(model.tasks[1].status, TaskStatus.FAILED)
        self.assertEqual(model.tasks[1].failed_phase, "execute")
        # Never reached is not the same as failed.
        self.assertEqual(model.tasks[2].status, TaskStatus.SKIPPED)

    def test_an_interrupt_is_not_a_failure(self) -> None:
        model = InstallModel()
        planned(model)
        feed(
            model,
            record("task_begin", "index=1", "id=environment", "name=Environment"),
            record("interrupt", "signal=INT"),
            record("task_failed", "index=1", "id=environment", "phase=execute", "status=130"),
            record("run_end", "status=130", "interrupted=true", "rolled_back=false"),
        )

        self.assertEqual(model.outcome, Outcome.INTERRUPTED)
        self.assertTrue(model.interrupted)

    def test_a_run_stopped_on_purpose_says_so(self) -> None:
        """--partition stops after storage; the remaining tasks were not skipped
        by accident and must not be reported as an incomplete installation."""
        model = InstallModel()
        planned(model)
        succeed(model, "environment", 1)
        succeed(model, "storage", 2)
        feed(model, record("run_end", "status=0", "stopped_after=storage"))

        self.assertEqual(model.outcome, Outcome.SUCCESS)
        self.assertEqual(model.stopped_after, "storage")
        self.assertEqual(model.tasks[2].status, TaskStatus.SKIPPED)

    def test_a_stream_cut_short_is_settled_by_the_exit_code(self) -> None:
        model = InstallModel()
        planned(model)
        feed(model, record("task_begin", "index=1", "id=environment", "name=Environment"))
        model.apply_child_exit(1)

        self.assertEqual(model.outcome, Outcome.FAILURE)
        self.assertEqual(model.tasks[0].status, TaskStatus.FAILED)

    def test_an_interrupt_without_a_status_is_still_an_interrupt(self) -> None:
        model = InstallModel()
        planned(model)
        feed(model, record("interrupt", "signal=TERM"))
        model.apply_child_exit(1)

        self.assertEqual(model.outcome, Outcome.INTERRUPTED)

    def test_an_unknown_kind_changes_nothing(self) -> None:
        model = InstallModel()
        planned(model)
        feed(model, record("from_the_future", "field=value"))

        self.assertEqual(model.outcome, Outcome.RUNNING)


if __name__ == "__main__":
    unittest.main()
