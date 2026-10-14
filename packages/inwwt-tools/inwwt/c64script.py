"""Typed-text script for the C64 screen.

A script is plain text. Lines that start with ``.`` are directives.
Anything else is typed, including leading spaces. ``#`` starts a comment
when it is the first non-space character... no: a ``#`` only comments a
line when the line, stripped, starts with ``#``, so a BASIC line can still
contain a quote. Inline tokens use ``{...}``.

Directives::

    .cps 10            characters per second (the default delay)
    .delay 0.08        seconds before each character, instead of .cps
    .hold 0.4          pause
    .enter             carriage return
    .bs                backspace one (or .bs 3)
    .ready             ROM-style READY. (leading CR, the word, trailing CR)
    .boot              start from the power-on screen (the default)
    .noboot            start from an empty blue screen
    .rvs on            reverse video
    .col 14            text color, 0–15 or a palette name
    .charset upper     upper (graphics) or lower
    .cursor off        hide the cursor

Inline tokens, inside a typed line::

    {d:0.4}            one-shot delay before the next character
    {hold:0.2}         extra pause
    {typo:ONT:INT}     type ONT, pause, backspace, type INT
    {bs} {bs:2}        backspace
    {sc:65} {sc:0x41}  screen code, reverse if bit 7 is set
    {spade} {heart}    named PETSCII graphics (see c64font.PETSCII_NAMES)
    {rvs} {rvsoff}     toggle or set reverse
    {col:7}            text color
    {cr}               carriage return
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from inwwt.palette import NAMES
from inwwt.c64font import PETSCII_NAMES, ascii_to_screen

COLS = 40
ROWS = 25
TOKEN = re.compile(r"\{([^{}]+)\}")

# ROM strings from mist64/c64rom basic/init.s (FREMES / WORDS).
BANNER = "    **** COMMODORE 64 BASIC V2 ****"
RAM_PREFIX = " 64K RAM SYSTEM  "
RAM_BYTES = "38911"
RAM_SUFFIX = " BASIC BYTES FREE"
RAM_LINE = RAM_PREFIX + RAM_BYTES + RAM_SUFFIX
READY = "READY."


@dataclass
class Put:
    t: float
    row: int
    col: int
    code: int
    color: int


@dataclass
class ClearCell:
    t: float
    row: int
    col: int


@dataclass
class Scroll:
    t: float
    color: int


@dataclass
class SetCharset:
    t: float
    name: str


@dataclass
class Cursor:
    t: float
    row: int
    col: int


Op = Put | ClearCell | Scroll | Cursor | SetCharset


@dataclass
class Program:
    boot: bool
    cells: np.ndarray
    colors: np.ndarray
    cursor_row: int
    cursor_col: int
    ops: list[Op] = field(default_factory=list)
    duration: float = 0.0
    charset: str = "upper"

    def state_at(self, t: float) -> tuple[np.ndarray, np.ndarray, int, int, str]:
        cells = self.cells.copy()
        colors = self.colors.copy()
        row, col = self.cursor_row, self.cursor_col
        charset = self.charset
        for op in self.ops:
            if op.t > t:
                break
            if isinstance(op, Put):
                cells[op.row, op.col] = op.code
                colors[op.row, op.col] = op.color
            elif isinstance(op, ClearCell):
                cells[op.row, op.col] = 32
            elif isinstance(op, Scroll):
                cells[:-1] = cells[1:]
                cells[-1] = 32
                colors[:-1] = colors[1:]
                colors[-1] = op.color
            elif isinstance(op, Cursor):
                row, col = op.row, op.col
            elif isinstance(op, SetCharset):
                charset = op.name
        return cells, colors, row, col, charset


def _blank() -> tuple[np.ndarray, np.ndarray]:
    return np.full((ROWS, COLS), 32, dtype=np.uint8), np.full((ROWS, COLS), 14, dtype=np.uint8)


def boot_screen() -> tuple[np.ndarray, np.ndarray, int, int]:
    """Power-on screen. Cursor sits on the line under READY."""
    cells, colors = _blank()

    def write(row: int, text: str) -> None:
        for col, char in enumerate(text):
            cells[row, col] = ascii_to_screen(char, "upper")

    # Clear-screen, then a CR, so the banner is on row 1. See basic/init.s.
    write(1, BANNER)
    write(3, RAM_LINE)
    write(5, READY)
    return cells, colors, 6, 0


def _color_index(token: str) -> int:
    token = token.strip().lower()
    if token.isdigit():
        value = int(token)
        if not 0 <= value <= 15:
            raise ValueError(f"color {value} is outside 0–15")
        return value
    if token in NAMES:
        return NAMES.index(token)
    raise ValueError(f"unknown color {token!r}")


@dataclass
class _Compiler:
    cps: float = 8.0
    boot: bool = True
    charset: str = "upper"
    reverse: bool = False
    color: int = 14
    show_cursor: bool = True
    t: float = 0.0
    row: int = 0
    col: int = 0
    delay: float = 0.125
    oneshot: float | None = None
    ops: list[Op] = field(default_factory=list)

    def set_cps(self, cps: float) -> None:
        if cps <= 0:
            raise ValueError("cps must be positive")
        self.cps = cps
        self.delay = 1.0 / cps

    def consume(self) -> float:
        if self.oneshot is not None:
            delay = self.oneshot
            self.oneshot = None
            return delay
        return self.delay

    def mark_cursor(self) -> None:
        self.ops.append(Cursor(self.t, self.row, self.col))

    def carriage_return(self, timed: bool) -> None:
        if timed:
            self.t += self.consume()
        self.col = 0
        self.row += 1
        if self.row >= ROWS:
            self.ops.append(Scroll(self.t, self.color))
            self.row = ROWS - 1
        self.mark_cursor()

    def backspace(self, timed: bool) -> None:
        if timed:
            self.t += min(self.consume(), 0.06) if self.oneshot is None else self.consume()
        if self.col == 0:
            if self.row == 0:
                self.mark_cursor()
                return
            self.row -= 1
            self.col = COLS - 1
        else:
            self.col -= 1
        self.ops.append(ClearCell(self.t, self.row, self.col))
        self.mark_cursor()

    def put_code(self, code: int, timed: bool) -> None:
        if timed:
            self.t += self.consume()
        if self.reverse:
            code |= 0x80
        self.ops.append(Put(self.t, self.row, self.col, code & 0xFF, self.color))
        self.col += 1
        if self.col >= COLS:
            self.col = 0
            self.row += 1
            if self.row >= ROWS:
                self.ops.append(Scroll(self.t, self.color))
                self.row = ROWS - 1
        self.mark_cursor()

    def put_char(self, char: str, timed: bool = True) -> None:
        self.put_code(ascii_to_screen(char, self.charset), timed)

    def ready(self) -> None:
        self.t += self.delay
        self.carriage_return(timed=False)
        for char in READY:
            self.put_char(char, timed=False)
        self.carriage_return(timed=False)


def _parse_token(body: str, comp: _Compiler) -> None:
    body = body.strip()
    lower = body.lower()
    if lower in PETSCII_NAMES:
        comp.put_code(PETSCII_NAMES[lower], timed=True)
        return
    if lower in {"rvs", "rvson"}:
        comp.reverse = True
        return
    if lower == "rvsoff":
        comp.reverse = False
        return
    if lower in {"cr", "enter"}:
        comp.carriage_return(timed=True)
        return
    if lower == "bs":
        comp.backspace(timed=True)
        return
    if ":" not in body:
        raise ValueError(f"unknown script token {{{body}}}")
    head, rest = body.split(":", 1)
    head = head.strip().lower()
    if head in {"d", "wait"}:
        comp.oneshot = float(rest)
        return
    if head == "hold":
        comp.t += float(rest)
        comp.mark_cursor()
        return
    if head == "delay":
        comp.delay = float(rest)
        return
    if head == "cps":
        comp.set_cps(float(rest))
        return
    if head == "bs":
        for _ in range(int(rest)):
            comp.backspace(timed=True)
        return
    if head == "sc":
        code = int(rest, 0)
        if not 0 <= code <= 255:
            raise ValueError(f"screen code {code} is outside 0–255")
        comp.put_code(code, timed=True)
        return
    if head in {"col", "color"}:
        comp.color = _color_index(rest)
        return
    if head == "typo":
        wrong, right = rest.split(":", 1)
        for char in wrong:
            comp.put_char(char)
        comp.t += max(0.2, comp.delay * 2)
        comp.mark_cursor()
        for _ in wrong:
            comp.backspace(timed=True)
        for char in right:
            comp.put_char(char)
        return
    if head in PETSCII_NAMES:
        # {shade} has no argument; a name with a colon is a typo in the script.
        raise ValueError(f"PETSCII name {{{head}}} does not take an argument")
    raise ValueError(f"unknown script token {{{body}}}")


def _handle_directive(line: str, comp: _Compiler) -> None:
    parts = line[1:].split()
    if not parts:
        return
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None
    if name == "cps":
        comp.set_cps(float(arg or "0"))
    elif name == "delay":
        comp.delay = float(arg or "0")
    elif name in {"hold", "pause"}:
        comp.t += float(arg or "0")
        comp.mark_cursor()
    elif name == "enter":
        comp.carriage_return(timed=True)
    elif name in {"bs", "backspace"}:
        count = int(arg) if arg else 1
        for _ in range(count):
            comp.backspace(timed=True)
    elif name == "ready":
        comp.ready()
    elif name == "boot":
        comp.boot = True
    elif name == "noboot":
        comp.boot = False
    elif name == "rvs":
        comp.reverse = (arg or "on").lower() in {"on", "1", "true"}
    elif name in {"col", "color"}:
        comp.color = _color_index(arg or "")
    elif name == "charset":
        choice = (arg or "upper").lower()
        if choice not in {"upper", "lower"}:
            raise ValueError("charset must be upper or lower")
        comp.charset = choice
        comp.ops.append(SetCharset(comp.t, choice))
    elif name == "cursor":
        comp.show_cursor = (arg or "on").lower() in {"on", "1", "true"}
    else:
        raise ValueError(f"unknown directive .{name}")


def _type_line(text: str, comp: _Compiler) -> None:
    pos = 0
    for match in TOKEN.finditer(text):
        for char in text[pos : match.start()]:
            comp.put_char(char)
        _parse_token(match.group(1), comp)
        pos = match.end()
    for char in text[pos:]:
        comp.put_char(char)


def compile_script(source: str, *, cps: float = 8.0, boot: bool = True) -> Program:
    comp = _Compiler()
    comp.set_cps(cps)
    comp.boot = boot
    # Directives may flip boot before we freeze the initial screen, so scan
    # boot/noboot first, then compile events against that screen.
    for raw in source.splitlines():
        stripped = raw.strip()
        if stripped in {".boot", ".noboot"}:
            comp.boot = stripped == ".boot"
    if comp.boot:
        cells, colors, row, col = boot_screen()
    else:
        cells, colors = _blank()
        row, col = 0, 0
    initial_boot = comp.boot
    comp.row, comp.col = row, col
    comp.mark_cursor()
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("."):
            _handle_directive(stripped, comp)
            continue
        _type_line(raw.rstrip("\r\n"), comp)
    return Program(
        boot=initial_boot,
        cells=cells,
        colors=colors,
        cursor_row=row,
        cursor_col=col,
        ops=comp.ops,
        duration=comp.t,
        charset=comp.charset,
    )
