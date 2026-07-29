"""Where everything goes, decided without touching a terminal.

Every frame is computed from scratch by these functions and then handed to a very
thin drawing layer. That split is not tidiness: it is what makes a resize free
(there is no cached geometry to invalidate) and what makes the interface testable
on a machine with no curses at all.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .. import constraints, menu as menu_module
from ..config import Configuration
from .glyphs import Glyphs

if TYPE_CHECKING:  # pragma: no cover
    from ..runner import InstallModel, TaskStatus, TaskView

MIN_WIDTH = 60
MIN_HEIGHT = 16

#: Columns of indent for the line carrying a constraint violation.
ANNOTATION_INDENT = 4

TITLE = "Arch Framework Installer — configuration"


@dataclass(frozen=True)
class Row:
    """One setting, as the screen needs it."""

    key: str
    label: str
    value: str
    mandatory: bool
    annotation: str | None
    blocking: bool
    editable: bool
    help_text: str


def rows(menu: "menu_module.Menu", config: Configuration) -> list[Row]:
    """The settings list, annotated with the current violations.

    The tag words come from ``menu.tag`` so the two front-ends and the
    documentation cannot drift apart on what "BLOCKED" means.
    """
    violations = {v.field: v for v in constraints.evaluate(config)}

    result: list[Row] = []
    for entry in menu.entries:
        problem = violations.get(entry.key)
        result.append(
            Row(
                key=entry.key,
                label=entry.label,
                value=entry.preview(config),
                mandatory=entry.mandatory,
                annotation=(
                    None
                    if problem is None
                    else f"{menu_module.tag(problem)}: {problem.message}"
                ),
                blocking=bool(problem is not None and problem.blocking),
                editable=entry.edit is not None,
                help_text=entry.help_text,
            )
        )
    return result


def format_row(row: Row, *, width: int, glyphs: Glyphs, label_width: int) -> str:
    """``* Target disk ........ /dev/nvme0n1``, clipped to the width.

    The dotted fill is the text menu's idiom (menu.py), minus the number: the
    highlight says where you are, so a number would only be a second way to say
    it.
    """
    marker = "*" if row.mandatory else " "
    label = f"{row.label} ".ljust(label_width + 2, ".")
    return truncate(f"{marker} {label} {row.value}", width, glyphs)


def truncate(text: str, width: int, glyphs: Glyphs) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= len(glyphs.ellipsis):
        return text[:width]
    return text[: width - len(glyphs.ellipsis)] + glyphs.ellipsis


@dataclass(frozen=True)
class Line:
    """A drawable line, and which row it belongs to.

    ``row`` is what keeps a violation attached to its setting: scrolling must not
    be allowed to show the label and hide the reason it is blocked.
    """

    text: str
    style: str  # "row" | "blocked" | "note"
    row: int | None


def lay_out(rows_: list[Row], *, width: int, glyphs: Glyphs) -> list[Line]:
    label_width = max((len(row.label) for row in rows_), default=0)

    lines: list[Line] = []
    for index, row in enumerate(rows_):
        lines.append(
            Line(
                format_row(row, width=width, glyphs=glyphs, label_width=label_width),
                "row",
                index,
            )
        )
        if row.annotation is None:
            continue
        style = "blocked" if row.blocking else "note"
        for piece in wrap(row.annotation, width - ANNOTATION_INDENT):
            lines.append(Line(" " * ANNOTATION_INDENT + piece, style, index))
    return lines


def first_visible(
    lines: list[Line], *, selected_row: int, height: int, previous_top: int = 0
) -> int:
    """Which line to start drawing at.

    Scrolls only as far as it must, so moving the selection does not make the
    whole list jump, and includes the selected row's annotation lines in what has
    to stay visible.
    """
    if height <= 0 or not lines:
        return 0

    owned = [i for i, line in enumerate(lines) if line.row == selected_row]
    if not owned:
        return max(0, min(previous_top, len(lines) - height))

    top = max(0, min(previous_top, max(0, len(lines) - height)))
    first, last = owned[0], owned[-1]

    # The annotation is given up before the label is: a reason with no visible
    # setting is worse than a setting whose reason needs one keypress to reach.
    if last - first + 1 > height:
        last = first + height - 1

    if first < top:
        top = first
    elif last >= top + height:
        top = last - height + 1
    return max(0, top)


def wrap(text: str, width: int) -> list[str]:
    """Break text to a width, surviving widths and tokens no wrapper expects."""
    if width <= 0:
        return []
    if width == 1:
        return list(text.replace(" ", "")) or [""]
    pieces = textwrap.wrap(
        text, width=width, break_long_words=True, break_on_hyphens=False
    )
    return pieces or [""]


def status_lines(menu: "menu_module.Menu", config: Configuration) -> list[str]:
    """What stands between the user and a working installation."""
    problems = constraints.blocking(config)
    missing = menu_module.unanswered(menu, config)

    lines: list[str] = []
    if problems:
        lines.append(f"{len(problems)} blocking problem(s) above.")
    if missing:
        lines.append(f"Unanswered and required: {', '.join(missing)}")
    if not lines:
        lines.append("Ready to install.")
    return lines


def footer(*, dry_run: bool = False) -> str:
    """The keys, with Install saying which of the two it is.

    A dry run keeps the screen and shows the tasks; a real installation hands the
    terminal to install.sh, which asks questions this interface cannot carry. A
    user expecting the first and getting the second reads it as a bug, so the key
    says so before it is pressed.
    """
    install = "i install (dry run)" if dry_run else "i install (real, on the terminal)"
    return f"^v move   Enter edit   s save   {install}   q quit      * = required"


def too_small(width: int, height: int) -> str | None:
    """The message to show instead of a cramped, misleading frame."""
    if width >= MIN_WIDTH and height >= MIN_HEIGHT:
        return None
    return (
        f"Terminal too small: need {MIN_WIDTH}x{MIN_HEIGHT}, have {width}x{height}."
    )


# ------------------------------------------------------------------------------
# The installation screen
# ------------------------------------------------------------------------------


def status_mark(status: "TaskStatus", glyphs: Glyphs) -> str:
    """One character per task state.

    Deliberately the same tick and cross ``lib/progress.sh`` prints, so the
    screen and the log it replaces read alike.
    """
    from ..runner import TaskStatus

    return {
        TaskStatus.PENDING: " ",
        TaskStatus.RUNNING: glyphs.cursor,
        TaskStatus.DONE: glyphs.tick,
        TaskStatus.FAILED: glyphs.cross,
        TaskStatus.ROLLED_BACK: glyphs.cross,
        TaskStatus.SKIPPED: glyphs.dot,
    }.get(status, " ")


def task_line(task: "TaskView", *, width: int, glyphs: Glyphs, total: int) -> str:
    from ..runner import TaskStatus

    detail = ""
    if task.status is TaskStatus.RUNNING and task.phase:
        detail = task.phase
    elif task.status is TaskStatus.DONE and task.duration is not None:
        detail = f"{task.duration}s"
    elif task.status is TaskStatus.FAILED and task.failed_phase:
        detail = f"failed in {task.failed_phase}"
    elif task.status is TaskStatus.ROLLED_BACK:
        detail = "rolled back"
    elif task.status is TaskStatus.SKIPPED:
        detail = "not reached"

    label = f"{task.name} ".ljust(28, ".")
    text = f" {status_mark(task.status, glyphs)} [{task.index:>02}/{total:>02}] {label} {detail}"
    return truncate(text.rstrip(), width, glyphs)


def install_lines(model: "InstallModel", *, width: int, glyphs: Glyphs) -> list[Line]:
    from ..runner import TaskStatus

    total = model.total or len(model.tasks)
    styles = {
        TaskStatus.RUNNING: "selected",
        TaskStatus.FAILED: "blocked",
        TaskStatus.ROLLED_BACK: "blocked",
        TaskStatus.SKIPPED: "note",
    }
    return [
        Line(
            task_line(task, width=width, glyphs=glyphs, total=total),
            styles.get(task.status, "row"),
            index,
        )
        for index, task in enumerate(model.tasks)
    ]


def install_header(model: "InstallModel") -> str:
    done, total = model.progress()
    kind = "dry run" if model.dry_run else "installation"
    return f"Arch Framework Installer — {kind}   {done}/{total}"


def install_status(model: "InstallModel") -> str:
    """The one line that says where things stand."""
    from ..runner import Outcome

    if model.outcome is Outcome.SUCCESS:
        if model.stopped_after:
            return f"Stopped after {model.stopped_after}, as asked. Nothing failed."
        return "Finished. Nothing failed."
    if model.outcome is Outcome.FAILURE:
        failed = next((t for t in model.tasks if t.failed_phase), None)
        where = f" at {failed.name} ({failed.failed_phase})" if failed else ""
        rolled = " Rolled back what had run." if model.rollback_happened else ""
        return f"Failed{where}.{rolled}"
    if model.outcome is Outcome.INTERRUPTED:
        return "Interrupted. Cleanup and rollback ran."
    current = model.current
    if current is not None:
        return f"{current.name}: {current.phase or 'starting'}"
    return "Starting…" if model.tasks else "Waiting for the installer…"


def install_footer(model: "InstallModel") -> str:
    if model.finished:
        return "Enter or q to return"
    return "c interrupt   ^v scroll the log"


@dataclass
class LineEditor:
    """A single-line text field.

    Hand-rolled rather than ``curses.textpad.Textbox`` for two reasons: an empty
    buffer has to mean "keep the current value", exactly as the text prompt does,
    and a pure editor can be tested without a terminal.
    """

    buffer: str = ""
    cursor: int = 0
    offset: int = 0

    def __post_init__(self) -> None:
        self.cursor = len(self.buffer)

    def apply(self, symbol: str) -> None:
        if symbol == "LEFT":
            self.cursor = max(0, self.cursor - 1)
        elif symbol == "RIGHT":
            self.cursor = min(len(self.buffer), self.cursor + 1)
        elif symbol == "HOME":
            self.cursor = 0
        elif symbol == "END":
            self.cursor = len(self.buffer)
        elif symbol == "BACKSPACE":
            if self.cursor > 0:
                self.buffer = (
                    self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                )
                self.cursor -= 1
        elif symbol == "DC":
            if self.cursor < len(self.buffer):
                self.buffer = (
                    self.buffer[: self.cursor] + self.buffer[self.cursor + 1 :]
                )
        elif symbol == "^U":
            self.buffer = ""
            self.cursor = 0
        elif len(symbol) == 1 and symbol.isprintable():
            self.buffer = (
                self.buffer[: self.cursor] + symbol + self.buffer[self.cursor :]
            )
            self.cursor += 1

    def window(self, width: int) -> tuple[str, int]:
        """The visible slice and the cursor's column within it."""
        if width <= 0:
            return "", 0
        if self.cursor < self.offset:
            self.offset = self.cursor
        elif self.cursor >= self.offset + width:
            self.offset = self.cursor - width + 1
        self.offset = max(0, min(self.offset, max(0, len(self.buffer) - width + 1)))
        return self.buffer[self.offset : self.offset + width], self.cursor - self.offset
