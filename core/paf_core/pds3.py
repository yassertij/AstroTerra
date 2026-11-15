"""Minimal PDS3 ODL label parser.

Handles what MOLA MEGDR and LOLA GDR labels use: KEY = VALUE pairs, quoted (multi-line) strings,
values with units (``3396.0 <KM>``), pointers (``^IMAGE``), parenthesised lists,
``{set}`` values spread over several lines,
``/* comments */``, and nested OBJECT / END_OBJECT blocks. Label text is only ever
parsed as data, never evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import LabelParseError

_UNIT_RE = re.compile(r"^(?P<num>[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)\s*<(?P<unit>[^>]+)>$")
_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str


class Label(dict):
    """A label block. Nested OBJECTs are stored under their object name (e.g. ``IMAGE``)."""

    def find(self, key: str) -> Any:
        """Return ``key`` from this block or the first nested block containing it, else None."""
        if key in self:
            return self[key]
        for v in self.values():
            if isinstance(v, Label):
                hit = v.find(key)
                if hit is not None:
                    return hit
        return None


def _convert(raw: str) -> Any:
    s = raw.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return " ".join(s[1:-1].split())
    m = _UNIT_RE.match(s)
    if m:
        return Quantity(float(m["num"]), m["unit"].strip().upper())
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s  # enumerated symbol, list, or date: keep as text


def _incomplete(value: str) -> bool:
    """True while a value has an open quote or an unclosed ( or { outside quotes."""
    depth, quoted = 0, False
    for ch in value:
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in "({":
            depth += 1
        elif not quoted and ch in ")}":
            depth -= 1
    return quoted or depth > 0


def parse_label_text(text: str) -> Label:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = text.splitlines()
    root = Label()
    stack: list[Label] = [root]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line == "END":
            break
        if "=" not in line:
            raise LabelParseError(f"Line {i}: expected KEY = VALUE, got {line[:60]!r}")
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        # Multi-line quoted strings, parenthesised lists and {set} values (LOLA labels
        # spread sets of quoted strings over several lines).
        while i < len(lines) and _incomplete(value):
            value += " " + lines[i].strip()
            i += 1
        if value.count('"') % 2 == 1:
            raise LabelParseError(f"Unterminated quoted string for {key}")
        if _incomplete(value):
            raise LabelParseError(f"Unbalanced brackets in value of {key}")
        if key == "OBJECT":
            block = Label()
            name = _convert(value)
            parent = stack[-1]
            if name in parent:
                existing = parent[name]
                parent[name] = existing + [block] if isinstance(existing, list) else [existing, block]
            else:
                parent[name] = block
            stack.append(block)
        elif key == "END_OBJECT":
            if len(stack) == 1:
                raise LabelParseError(f"Line {i}: END_OBJECT without OBJECT")
            stack.pop()
        else:
            stack[-1][key] = _convert(value)
    if len(stack) != 1:
        raise LabelParseError("Label ended inside an OBJECT block (missing END_OBJECT)")
    return root


def parse_label_file(path: Path) -> Label:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LabelParseError(f"{Path(path).name}: label is not ASCII text") from exc
    return parse_label_text(text)
