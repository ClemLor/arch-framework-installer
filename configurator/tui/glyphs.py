"""The characters the interface is drawn with.

Two sets, because the installer runs on the Linux console before any font is
configured. The Unicode set is deliberately tiny and limited to characters
``lib/progress.sh`` already prints on the ISO, so their coverage is proven rather
than assumed.

There is no box drawing here on purpose: horizontal rules are drawn with
``curses.ACS_HLINE``, which negotiates the terminal's own line-drawing set, and
panels are marked out with blank lines and reverse video. A missing glyph in a
border turns the whole frame into mojibake, and a border is the one thing that
adds no information.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Glyphs:
    ellipsis: str
    tick: str
    cross: str
    dot: str
    cursor: str
    check_on: str
    check_off: str
    check_locked: str
    radio_on: str
    radio_off: str


#: Brackets stay ASCII in both sets: they carry the state, and `[x]` is legible
#: everywhere.
ASCII = Glyphs(
    ellipsis="...",
    tick="*",
    cross="x",
    # Not "*": a task never reached would then carry the same mark as one that
    # finished, and the two mean opposite things.
    dot="-",
    cursor=">",
    check_on="[x]",
    check_off="[ ]",
    check_locked="[-]",
    radio_on="(*)",
    radio_off="( )",
)

UNICODE = Glyphs(
    ellipsis="…",
    tick="✔",
    cross="✘",
    dot="•",
    cursor=">",
    check_on="[x]",
    check_off="[ ]",
    check_locked="[-]",
    radio_on="(•)",
    radio_off="( )",
)


def glyphs_for(encoding: str | None, *, force_ascii: bool = False) -> Glyphs:
    """Pick a set from the terminal's encoding.

    ``force_ascii`` is what ``AFI_TUI_ASCII=1`` sets, for a console whose
    encoding claims UTF-8 while the loaded font has nothing to draw with.
    """
    if force_ascii or not encoding:
        return ASCII
    normalised = encoding.replace("-", "").replace("_", "").lower()
    return UNICODE if "utf8" in normalised else ASCII
