"""One end-to-end run of the full-screen interface on a pseudo-terminal.

Gated behind AFI_TUI_PTY=1 and not part of the default suite: a terminal test that
flakes in CI gets disabled and then deleted, and the behaviour it would cover is
already pinned by test_tui_layout.py without a terminal. What this adds is proof
that the whole thing initialises, draws and exits on a real tty — worth having,
worth running deliberately.

    AFI_TUI_PTY=1 python3 -m unittest tests.python.test_tui_pty
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "devices.json"

if not os.environ.get("AFI_TUI_PTY"):  # pragma: no cover
    raise unittest.SkipTest("set AFI_TUI_PTY=1 to run the pty test")
if os.name != "posix" or importlib.util.find_spec("_curses") is None:  # pragma: no cover
    raise unittest.SkipTest("needs a POSIX pty and _curses")

import pty  # noqa: E402
import select  # noqa: E402


def drive(
    keys: bytes,
    timeout: float = 20.0,
    arguments: tuple[str, ...] = (),
    after: bytes | None = None,
) -> tuple[int, bytes]:
    """Run the configurator on a pty, type keys at it, return (status, output)."""
    environment = dict(os.environ)
    environment.update(
        {
            "TERM": "xterm",
            "AFI_DEVICES_FIXTURE": str(FIXTURE),
            "LINES": "30",
            "COLUMNS": "100",
            "PYTHONPATH": str(ROOT),
        }
    )

    pid, master = pty.fork()
    if pid == 0:  # pragma: no cover - child
        os.chdir(ROOT)
        os.execvpe(
            sys.executable,
            [
                sys.executable,
                "-m",
                "configurator",
                "--tui",
                "--config",
                "/dev/null",
                *arguments,
            ],
            environment,
        )

    output = bytearray()
    os.write(master, keys)
    sent_after = after is None
    while True:
        ready, _, _ = select.select([master], [], [], timeout)
        if not ready:
            break
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)

        # Sent only once the menu is actually up: a key delivered during start-up
        # would be testing the import sequence, not the interface.
        if not sent_after and b"Target disk" in bytes(output):
            os.write(master, after or b"")
            sent_after = True

    _, status = os.waitpid(pid, 0)
    os.close(master)
    return os.waitstatus_to_exitcode(status), bytes(output)


class PtyTests(unittest.TestCase):
    def test_quitting_writes_nothing_and_exits_130(self) -> None:
        status, output = drive(b"jjq")
        self.assertEqual(status, 130)
        self.assertIn(b"Target disk", output)

    def test_the_screen_shows_the_settings_and_the_footer(self) -> None:
        _, output = drive(b"q")
        self.assertIn(b"install", output)
        self.assertIn(b"required", output)

    def test_ctrl_c_on_the_menu_does_not_leave_a_traceback(self) -> None:
        """Ctrl-C has to end the session the way q does, not by unwinding through
        curses and printing a stack trace over a half-restored terminal."""
        status, output = drive(b"", after=b"\x03")
        self.assertEqual(status, 130)
        self.assertNotIn(b"Traceback", output)


if __name__ == "__main__":
    unittest.main()
