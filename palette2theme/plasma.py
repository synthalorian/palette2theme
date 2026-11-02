"""KDE Plasma colour scheme output — STUB, NOT IMPLEMENTED YET.

# ============================================================================
# TODO(plasma): write a KDE Plasma colour scheme (`<Name>.colors`, INI format)
# ============================================================================
#
# Planned output: ~/.local/share/color-schemes/<Name>.colors with
#   [General]            ColorScheme=<Name>, Name=<Name>
#   [ColorEffects:Disabled] / [ColorEffects:Inactive]
#   [Colors:Window]      BackgroundNormal=background, BackgroundAlternate=lighter_background,
#                        ForegroundNormal=foreground, ForegroundInactive=muted,
#                        ForegroundActive=accent, ForegroundLink=blue, ForegroundVisited=magenta,
#                        ForegroundNegative=red, ForegroundNeutral=yellow, ForegroundPositive=green,
#                        DecorationFocus=accent, DecorationHover=accent
#   [Colors:View] [Colors:Button] [Colors:Selection] [Colors:Tooltip]
#   [Colors:Complementary] [Colors:Header] [Colors:Header][Inactive]
#   [WM]                 activeBackground, activeForeground, inactiveBackground, ...
# Values are "r,g,b" decimal triples, not hex.
#
# Still to decide: Selection BackgroundNormal (accent vs `selection`), contrast rules for
# ForegroundNormal on Selection, and whether to emit a Plasma global theme / look-and-feel
# package around it. Tests: tests/test_plasma.py asserts this stub raises until then.
"""

from __future__ import annotations

from pathlib import Path

from .derive import Scheme

TODO_MESSAGE = ("--target plasma is not implemented yet (TODO: write a KDE Plasma .colors "
                "scheme; see palette2theme/plasma.py)")


def write_plasma_scheme(scheme: Scheme, name: str, out: str | Path) -> list[str]:
    """TODO(plasma): render `scheme` as a KDE colour scheme into `out`."""
    raise NotImplementedError(TODO_MESSAGE)
