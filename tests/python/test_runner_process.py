"""Tests for the runner against fake installers.

Real subprocesses, real pipes, no disks: the fixtures emit the same protocol
lib/events.sh does. POSIX only, because pass_fds and a selector over pipes are.
"""

from __future__ import annotations

import shutil
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from configurator.runner import (  # noqa: E402
    InstallRunner,
    Outcome,
    TaskStatus,
    supported,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def runner_for(name: str, **kwargs: object) -> InstallRunner:
    return InstallRunner(
        project_root=ROOT, installer=FIXTURES / name, **kwargs  # type: ignore[arg-type]
    )


def drain(runner: InstallRunner, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while not runner.finished and time.monotonic() < deadline:
        runner.poll(0.05)
    if not runner.finished:
        runner.interrupt()
        raise AssertionError("the fake installer did not finish")


@unittest.skipUnless(supported() and shutil.which("bash"), "needs POSIX and bash")
class RunnerTests(unittest.TestCase):
    def test_a_successful_run(self) -> None:
        with runner_for("fake_installer_ok.sh") as runner:
            drain(runner)
            model = runner.model

        self.assertEqual(model.outcome, Outcome.SUCCESS)
        self.assertEqual(model.exit_code, 0)
        self.assertEqual([task.name for task in model.tasks], ["First task", "Second task"])
        self.assertTrue(all(task.status is TaskStatus.DONE for task in model.tasks))
        self.assertEqual(model.progress(), (2, 2))
        self.assertTrue(model.dry_run)

    def test_the_child_output_reaches_the_log_pane(self) -> None:
        """Including a multi-byte character, which chunked reads will split."""
        with runner_for("fake_installer_ok.sh") as runner:
            drain(runner)
            output = "\n".join(runner.model.output)

        self.assertIn("task alpha", output)
        self.assertIn("✔", output)
        self.assertNotIn("�", output)

    def test_escape_sequences_do_not_reach_the_screen(self) -> None:
        """The installer colours its output; drawn verbatim into curses those
        bytes are garbage."""
        with runner_for("fake_installer_fail.sh") as runner:
            drain(runner)
            output = "\n".join(runner.model.output)

        self.assertNotIn("\x1b", output)

    def test_a_failing_run_keeps_the_exit_code_and_the_rollback(self) -> None:
        with runner_for("fake_installer_fail.sh") as runner:
            drain(runner)
            model = runner.model

        self.assertEqual(model.outcome, Outcome.FAILURE)
        self.assertEqual(model.exit_code, 7)
        self.assertTrue(model.rollback_happened)
        self.assertEqual(model.tasks[0].failed_phase, "execute")
        self.assertEqual(model.tasks[1].status, TaskStatus.SKIPPED)
        # stderr is interleaved into the same pane, in order.
        self.assertIn("something went wrong", "\n".join(model.output))

    def test_interrupting_reaches_the_child(self) -> None:
        """The child is in its own session, so this only works if the runner
        signals the process group deliberately — which is the point."""
        with runner_for("fake_installer_interrupt.sh") as runner:
            deadline = time.monotonic() + 20
            while "ready" not in "\n".join(runner.model.output):
                runner.poll(0.05)
                if time.monotonic() > deadline:
                    raise AssertionError("the fake installer never started")

            runner.interrupt()
            drain(runner)
            model = runner.model

        self.assertEqual(model.outcome, Outcome.INTERRUPTED)
        self.assertEqual(model.exit_code, 130)
        self.assertTrue(model.interrupted)

    def test_repeated_interrupts_escalate(self) -> None:
        with runner_for("fake_installer_interrupt.sh") as runner:
            runner.poll(0.2)
            runner.interrupt()
            runner.interrupt()
            runner.interrupt()
            drain(runner)

            self.assertEqual(runner.escalations, 3)
            self.assertTrue(runner.finished)

    def test_a_flood_neither_deadlocks_nor_grows_without_bound(self) -> None:
        with runner_for("fake_installer_flood.sh", scrollback=500) as runner:
            drain(runner, timeout=120.0)
            model = runner.model

        self.assertEqual(model.outcome, Outcome.SUCCESS)
        self.assertEqual(len(model.log), 500)
        self.assertEqual(len(model.output), 500)

    def test_a_missing_installer_is_reported_not_raised(self) -> None:
        runner = InstallRunner(project_root=ROOT, installer=ROOT / "no-such-file.sh")
        problems = runner.preflight()
        self.assertTrue(any("no-such-file.sh" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
