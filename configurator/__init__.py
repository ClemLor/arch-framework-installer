"""Configuration front-end for the Bash installer.

Deliberately narrow: it edits settings and writes ``config/generated.conf``. It
never partitions, formats, or writes to a target system — ``install.sh`` does
all of that, and remains the only implementation of it.

No third-party dependencies, so it runs on the Arch ISO's Python as shipped.
"""

__all__ = ["config", "constraints", "devices", "menu"]
