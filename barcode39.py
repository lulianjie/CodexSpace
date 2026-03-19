"""Offline Code 39 barcode generator used by the desktop label printer.

Pattern data is based on the standard Code 39 narrow/wide encoding.
Only the standard Code 39 character set is supported.
"""

from __future__ import annotations

from dataclasses import dataclass


class BarcodeError(ValueError):
    pass


@dataclass
class Barcode39:
    modules: list[tuple[bool, int]]
    total_units: int
    text: str


NARROW = 1
WIDE = 3
INTERCHAR_GAP = 1

PATTERNS: dict[str, tuple[int, ...]] = {
    " ": (1, 3, 3, 1, 1, 1, 3, 1, 1),
    "$": (1, 3, 1, 3, 1, 3, 1, 1, 1),
    "%": (1, 1, 1, 3, 1, 3, 1, 3, 1),
    "*": (1, 3, 1, 1, 3, 1, 3, 1, 1),
    "+": (1, 3, 1, 1, 1, 3, 1, 3, 1),
    "-": (1, 3, 1, 1, 1, 1, 3, 1, 3),
    ".": (3, 3, 1, 1, 1, 1, 3, 1, 1),
    "/": (1, 3, 1, 3, 1, 1, 1, 3, 1),
    "0": (1, 1, 1, 3, 3, 1, 3, 1, 1),
    "1": (3, 1, 1, 3, 1, 1, 1, 1, 3),
    "2": (1, 1, 3, 3, 1, 1, 1, 1, 3),
    "3": (3, 1, 3, 3, 1, 1, 1, 1, 1),
    "4": (1, 1, 1, 3, 3, 1, 1, 1, 3),
    "5": (3, 1, 1, 3, 3, 1, 1, 1, 1),
    "6": (1, 1, 3, 3, 3, 1, 1, 1, 1),
    "7": (1, 1, 1, 3, 1, 1, 3, 1, 3),
    "8": (3, 1, 1, 3, 1, 1, 3, 1, 1),
    "9": (1, 1, 3, 3, 1, 1, 3, 1, 1),
    "A": (3, 1, 1, 1, 1, 3, 1, 1, 3),
    "B": (1, 1, 3, 1, 1, 3, 1, 1, 3),
    "C": (3, 1, 3, 1, 1, 3, 1, 1, 1),
    "D": (1, 1, 1, 1, 3, 3, 1, 1, 3),
    "E": (3, 1, 1, 1, 3, 3, 1, 1, 1),
    "F": (1, 1, 3, 1, 3, 3, 1, 1, 1),
    "G": (1, 1, 1, 1, 1, 3, 3, 1, 3),
    "H": (3, 1, 1, 1, 1, 3, 3, 1, 1),
    "I": (1, 1, 3, 1, 1, 3, 3, 1, 1),
    "J": (1, 1, 1, 1, 3, 3, 3, 1, 1),
    "K": (3, 1, 1, 1, 1, 1, 1, 3, 3),
    "L": (1, 1, 3, 1, 1, 1, 1, 3, 3),
    "M": (3, 1, 3, 1, 1, 1, 1, 3, 1),
    "N": (1, 1, 1, 1, 3, 1, 1, 3, 3),
    "O": (3, 1, 1, 1, 3, 1, 1, 3, 1),
    "P": (1, 1, 3, 1, 3, 1, 1, 3, 1),
    "Q": (1, 1, 1, 1, 1, 1, 3, 3, 3),
    "R": (3, 1, 1, 1, 1, 1, 3, 3, 1),
    "S": (1, 1, 3, 1, 1, 1, 3, 3, 1),
    "T": (1, 1, 1, 1, 3, 1, 3, 3, 1),
    "U": (3, 3, 1, 1, 1, 1, 1, 1, 3),
    "V": (1, 3, 3, 1, 1, 1, 1, 1, 3),
    "W": (3, 3, 3, 1, 1, 1, 1, 1, 1),
    "X": (1, 3, 1, 1, 3, 1, 1, 1, 3),
    "Y": (3, 3, 1, 1, 3, 1, 1, 1, 1),
    "Z": (1, 3, 3, 1, 3, 1, 1, 1, 1),
}


SUPPORTED = set(PATTERNS) - {"*"}


def make_barcode(text: str) -> Barcode39:
    normalized = text.strip().upper()
    if not normalized:
        raise BarcodeError("资产编码不能为空")
    unsupported = sorted({char for char in normalized if char not in SUPPORTED})
    if unsupported:
        raise BarcodeError(f"条形码不支持这些字符：{' '.join(unsupported)}")

    encoded = f"*{normalized}*"
    modules: list[tuple[bool, int]] = []
    total_units = 0
    for index, char in enumerate(encoded):
        pattern = PATTERNS[char]
        is_bar = True
        for width in pattern:
            modules.append((is_bar, width))
            total_units += width
            is_bar = not is_bar
        if index < len(encoded) - 1:
            modules.append((False, INTERCHAR_GAP))
            total_units += INTERCHAR_GAP

    return Barcode39(modules=modules, total_units=total_units, text=normalized)
