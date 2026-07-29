"""Running install.sh and following what it does.

Only ever with ``--dry-run``. A real installation still hands over the terminal
to ``install.sh`` (see ``__main__.hand_over``), because it asks for a passphrase, a
typed device path and two passwords, and a full-screen interface cannot share a
terminal with a child that prompts. Keeping that path exactly as it was is what
lets the progress screen exist without touching lib/luks.sh or lib/users.sh.

The interface for the screen is small on purpose: call ``poll`` once per frame,
then draw ``model``.
"""

from __future__ import annotations

import codecs
import collections
import os
import re
import selectors
import signal
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from . import constraints
from .config import Configuration
from .events import Event, parse_line

DEFAULT_SCROLLBACK = 2000

#: The installer colours its output (lib/logging.sh). Drawn into a curses window
#: verbatim, those bytes are garbage on screen, so they come off on the way in.
_ESCAPES = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]|[\x00-\x08\x0b-\x1f\x7f]")


def strip_escapes(text: str) -> str:
    return _ESCAPES.sub("", text)


class Outcome(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()
    INTERRUPTED = auto()


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
    FAILED = auto()
    ROLLED_BACK = auto()
    #: Never reached. A run stopped on purpose (--partition) leaves tasks here,
    #: which is not the same as a task that failed.
    SKIPPED = auto()


@dataclass
class TaskView:
    index: int
    id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    phase: str | None = None
    duration: int | None = None
    failed_phase: str | None = None


class InstallModel:
    """What has happened so far, as a screen needs it."""

    def __init__(self, *, scrollback: int = DEFAULT_SCROLLBACK) -> None:
        self.tasks: list[TaskView] = []
        self.total = 0
        #: Everything the child printed, escape sequences removed. This is what a
        #: log pane shows: it includes the output of the commands the installer
        #: runs — pacstrap, sgdisk — which never passes through log_message and so
        #: is in no event.
        self.output: collections.deque[str] = collections.deque(maxlen=scrollback)
        #: The structured messages, level-tagged. Overlaps with `output` for
        #: anything the installer both logged and printed, but it starts earlier —
        #: before init_logging — and needs no escape-sequence handling, which makes
        #: it the right source for a one-line "currently doing" summary.
        self.log: collections.deque[str] = collections.deque(maxlen=scrollback)
        self.outcome = Outcome.PENDING
        self.exit_code: int | None = None
        self.interrupted = False
        self.rollback_happened = False
        self.stopped_after: str | None = None
        self.log_file: str | None = None
        self.state_file: str | None = None
        self.dry_run = False
        self._by_id: dict[str, TaskView] = {}

    # -- reading --------------------------------------------------------------

    @property
    def current(self) -> TaskView | None:
        return next(
            (task for task in self.tasks if task.status is TaskStatus.RUNNING), None
        )

    def progress(self) -> tuple[int, int]:
        """How much actually got done.

        Tasks that were never reached do not count: after a failure "1/2" would
        read as one task finished, which is the opposite of what happened.
        """
        done = sum(1 for task in self.tasks if task.status is TaskStatus.DONE)
        return done, self.total or len(self.tasks)

    @property
    def finished(self) -> bool:
        return self.outcome in {Outcome.SUCCESS, Outcome.FAILURE, Outcome.INTERRUPTED}

    # -- writing --------------------------------------------------------------

    def apply(self, event: Event) -> None:
        handler = getattr(self, f"_on_{event.kind}", None)
        if handler is not None:
            handler(event)

    def _task(self, event: Event) -> TaskView | None:
        return self._by_id.get(event.get("id"))

    def _on_run_begin(self, event: Event) -> None:
        self.outcome = Outcome.RUNNING
        self.dry_run = event.flag("dry_run")
        self.log_file = event.get("log_file") or None
        self.state_file = event.get("state_file") or None

    def _on_plan(self, event: Event) -> None:
        self.total = event.integer("total")

    def _on_plan_task(self, event: Event) -> None:
        task = TaskView(
            index=event.integer("index"), id=event.get("id"), name=event.get("name")
        )
        self.tasks.append(task)
        self._by_id[task.id] = task

    def _on_task_begin(self, event: Event) -> None:
        task = self._task(event)
        if task is None:
            # A run that emitted no plan (an older installer, or a partial
            # stream): better an incomplete list than no list.
            task = TaskView(
                index=event.integer("index"), id=event.get("id"), name=event.get("name")
            )
            self.tasks.append(task)
            self._by_id[task.id] = task
        self.total = self.total or event.integer("total")
        task.status = TaskStatus.RUNNING

    def _on_phase(self, event: Event) -> None:
        task = self._task(event)
        if task is not None:
            task.phase = event.get("phase")

    def _on_task_end(self, event: Event) -> None:
        task = self._task(event)
        if task is not None:
            task.status = TaskStatus.DONE
            task.phase = None
            task.duration = event.integer("duration")

    def _on_task_failed(self, event: Event) -> None:
        task = self._task(event)
        if task is not None:
            task.status = TaskStatus.FAILED
            task.failed_phase = event.get("phase")
            task.phase = None

    def _on_rollback_begin(self, event: Event) -> None:
        self.rollback_happened = True
        task = self._task(event)
        if task is not None and task.status is not TaskStatus.FAILED:
            task.status = TaskStatus.ROLLED_BACK

    def _on_rollback_end(self, event: Event) -> None:
        task = self._task(event)
        if task is not None and task.status is TaskStatus.DONE:
            task.status = TaskStatus.ROLLED_BACK

    def _on_interrupt(self, event: Event) -> None:
        self.interrupted = True

    def _on_log(self, event: Event) -> None:
        level = event.get("level")
        message = event.get("message")
        self.log.append(f"[{level}] {message}" if level else message)

    def _on_run_end(self, event: Event) -> None:
        self.interrupted = self.interrupted or event.flag("interrupted")
        self.rollback_happened = self.rollback_happened or event.flag("rolled_back")
        self.stopped_after = event.get("stopped_after") or None
        self.apply_child_exit(event.integer("status"))

    def apply_child_exit(self, code: int) -> None:
        """Settle the outcome from the child's status.

        The exit code is authoritative — a stream can be cut short — but the
        interrupt flag decides between "failed" and "you stopped it".
        """
        self.exit_code = code
        if code == 0:
            self.outcome = Outcome.SUCCESS
        elif code == 130 or self.interrupted:
            self.outcome = Outcome.INTERRUPTED
        else:
            self.outcome = Outcome.FAILURE

        for task in self.tasks:
            if task.status is TaskStatus.PENDING:
                task.status = TaskStatus.SKIPPED
            elif task.status is TaskStatus.RUNNING:
                task.status = (
                    TaskStatus.DONE if code == 0 else TaskStatus.FAILED
                )


@dataclass
class InstallRunner:
    """Spawns ``install.sh --dry-run`` and turns its two streams into a model."""

    project_root: Path
    #: Passed as install.sh's ``--config``, which *replaces* config/system.conf
    #: rather than adding to it. Leave unset for a normal run: the installer picks
    #: up config/generated.conf on top of its own defaults by itself.
    config_path: Path | None = None
    scrollback: int = DEFAULT_SCROLLBACK
    installer: Path | None = None
    environment: Mapping[str, str] | None = None
    extra_arguments: Sequence[str] = ()

    _model: InstallModel = field(init=False)
    _process: subprocess.Popen | None = field(init=False, default=None)
    _selector: selectors.BaseSelector | None = field(init=False, default=None)
    _event_read: int | None = field(init=False, default=None)
    _interrupts: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._model = InstallModel(scrollback=self.scrollback)
        self._buffers: dict[str, str] = {"events": "", "output": ""}
        self._decoders: dict[str, codecs.IncrementalDecoder] = {}
        self._closed: set[str] = set()

    # -- before starting ------------------------------------------------------

    @property
    def installer_path(self) -> Path:
        return self.installer or self.project_root / "install.sh"

    def preflight(self, config: Configuration | None = None) -> list[str]:
        """Everything that would make starting pointless, in the user's words.

        Reported rather than raised: this is called from a full-screen interface,
        where the old behaviour of printing and exiting leaves a black screen and a
        terminal in raw mode.
        """
        problems: list[str] = []

        if not self.installer_path.is_file():
            problems.append(f"install.sh not found at {self.installer_path}")

        if hasattr(os, "geteuid") and os.geteuid() != 0:
            problems.append(
                "install.sh must run as root. Quit and start this again with sudo."
            )

        if config is not None:
            for violation in constraints.blocking(config):
                problems.append(violation.message)

        return problems

    # -- running --------------------------------------------------------------

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("already started")

        event_read, event_write = os.pipe()
        environment = dict(self.environment or os.environ)
        environment["AFI_EVENT_FD"] = str(event_write)

        argv = ["bash", str(self.installer_path), "--dry-run"]
        if self.config_path is not None:
            argv += ["--config", str(self.config_path)]
        argv += list(self.extra_arguments)

        try:
            self._process = subprocess.Popen(  # noqa: S603
                argv,
                cwd=str(self.project_root),
                # Nothing to read from: the dry run answers no questions, and a
                # prompt that somehow appeared must fail loudly instead of
                # blocking forever on a terminal nobody can see.
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                # Interleaved deliberately: progress_failure, warn and error all
                # go to stderr, and the log pane wants them in order.
                stderr=subprocess.STDOUT,
                env=environment,
                pass_fds=(event_write,),
                # Its own session, so a Ctrl-C in the terminal does not reach the
                # child behind our back. Interrupting is a decision the interface
                # makes, once, explicitly.
                start_new_session=True,
                bufsize=0,
            )
        finally:
            # The parent's copy has to go, or the reader never sees end-of-file.
            os.close(event_write)

        self._event_read = event_read
        self._selector = selectors.DefaultSelector()
        self._selector.register(event_read, selectors.EVENT_READ, "events")
        assert self._process.stdout is not None
        self._selector.register(self._process.stdout, selectors.EVENT_READ, "output")
        for name in ("events", "output"):
            self._decoders[name] = codecs.getincrementaldecoder("utf-8")("replace")

    def poll(self, timeout: float | None = 0.05) -> list[Event]:
        """Read whatever is ready and fold it into the model."""
        if self._selector is None or self._process is None:
            return []

        events: list[Event] = []
        for key, _ in self._selector.select(timeout):
            name = key.data
            source = key.fileobj
            handle = source if isinstance(source, int) else source.fileno()
            try:
                chunk = os.read(handle, 65536)
            except OSError:
                chunk = b""

            if not chunk:
                self._close(name, key)
                continue

            # Chunked reads split multi-byte characters: lib/progress.sh prints
            # … ✔ ✘, so this is not hypothetical.
            text = self._decoders[name].decode(chunk)
            events.extend(self._absorb(name, text))

        self._settle()
        return events

    def _absorb(self, name: str, text: str) -> list[Event]:
        buffer = self._buffers[name] + text
        *lines, self._buffers[name] = buffer.split("\n")

        events: list[Event] = []
        for line in lines:
            if name == "events":
                event = parse_line(line)
                if event is not None:
                    self._model.apply(event)
                    events.append(event)
            else:
                self._model.output.append(strip_escapes(line.rstrip("\r")))
        return events

    def _close(self, name: str, key: selectors.SelectorKey) -> None:
        if name in self._closed:
            return
        self._closed.add(name)
        assert self._selector is not None
        self._selector.unregister(key.fileobj)

        # A last line with no newline is still a line: flush it by supplying the
        # newline the stream never got round to.
        if self._buffers[name]:
            self._absorb(name, "\n")

    def _settle(self) -> None:
        """Decide the outcome once both streams are done and the child has gone.

        Both conditions: descendants such as pacstrap inherit the event
        descriptor, so end-of-file can arrive after the process has exited, and
        the process can exit after its streams are drained.
        """
        if self._process is None:
            return
        if len(self._closed) < 2:
            return
        status = self._process.poll()
        if status is None:
            return
        if self._model.exit_code is None:
            self._model.apply_child_exit(status)

    def __iter__(self) -> Iterator[Event]:
        """Blocking iteration, for tests and headless use."""
        if self._process is None:
            self.start()
        while not self.finished:
            yield from self.poll(0.1)

    @property
    def model(self) -> InstallModel:
        return self._model

    @property
    def finished(self) -> bool:
        return self._model.finished

    def wait(self, timeout: float | None = None) -> int | None:
        if self._process is None:
            return None
        try:
            return self._process.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def interrupt(self) -> None:
        """Ask the installer to stop, the way Ctrl-C on a terminal would.

        SIGINT reaches the trap in lib/task.sh, so state_request_interrupt runs,
        the current task finishes its cleanup and rollback, and the run ends 130.
        Repeated requests escalate, because a child stuck in a syscall would
        otherwise leave the interface unable to do anything at all.
        """
        if self._process is None or self._process.poll() is not None:
            return

        self._interrupts += 1
        if self._interrupts == 1:
            signal_number = signal.SIGINT
        elif self._interrupts == 2:
            signal_number = signal.SIGTERM
        else:
            signal_number = signal.SIGKILL

        try:
            os.killpg(os.getpgid(self._process.pid), signal_number)
        except (ProcessLookupError, PermissionError):
            pass

    @property
    def escalations(self) -> int:
        return self._interrupts

    def close(self) -> None:
        """Release the pipes and reap the child.

        The model can be finished — run_end has arrived — a moment before the
        process is, so this waits briefly rather than leaving an unreaped child
        behind. A child still there after that is asked to stop: closing the
        interface must not silently leave a dry run going.
        """
        if self._selector is not None:
            self._selector.close()
            self._selector = None
        if self._event_read is not None:
            try:
                os.close(self._event_read)
            except OSError:
                pass
            self._event_read = None
        if self._process is not None:
            if self._process.poll() is None:
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.interrupt()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait()
            if self._process.stdout is not None:
                self._process.stdout.close()

    def __enter__(self) -> "InstallRunner":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def supported() -> bool:
    """Whether a child can be followed on this platform.

    ``pass_fds`` and reading pipes through a selector are POSIX; on Windows the
    configurator is a development tool and never installs anything.
    """
    return os.name == "posix" and sys.platform != "win32"
