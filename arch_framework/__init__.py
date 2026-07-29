"""Reproducible Arch Linux installer for Framework laptops.

The package layout mirrors archinstall so that anyone familiar with the
upstream installer can navigate this one, but the implementation is our own:
system commands are driven through :mod:`arch_framework.lib.command` rather
than through pyparted, and the TUI degrades to plain prompts when Textual is
unavailable.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
