"""Compare named bots and voice ids in drafts with VOICE_BIBLE.md.

A draft that still lists Ledger as carina is a stale alias. A draft that gives
Harbor Ledger's voice is a mismatch. A voice the bible marks proposed is a
warning, not a lock. Lines that say "changed from" or "carina -> ara" are
history, and are not findings. The bible file itself is the reference, so it
is not scanned as a draft.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from continuity_checker.tables import parse_tables

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text"}
EXTRA_ALIASES = {}  # optional short aliases: {"nick": "FullName"}
_FROM = re.compile(
    r"(?i)\b(?:changed|swapped|swap|retired|formerly|previously)\s+from\s+['\"]?"
    r"([A-Za-z][A-Za-z0-9_-]*)"
)
_ARROW = re.compile(
    r"(?i)\b([A-Z][A-Za-z]+)\s+([A-Za-z][A-Za-z0-9_-]{1,})\s*(?:->|→)\s*([A-Za-z][A-Za-z0-9_-]{1,})\b"
)
_VOICE_FIELD = re.compile(
    r"(?i)\bvoiceId\b\s*[:=]\s*['\"]?([A-Za-z][A-Za-z0-9_-]*)['\"]?"
)
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")
_SLUG = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class BibleError(Exception):
    """VOICE_BIBLE.md could not be read as a bot / voiceId table."""


@dataclass(frozen=True)
class BotVoice:
    name: str
    voice_id: str
    status: str
    stale: tuple[str, ...]
    notes: str
    line: int


@dataclass
class VoiceBible:
    path: str
    bots: tuple[BotVoice, ...]

    def by_name(self, name: str) -> BotVoice | None:
        key = EXTRA_ALIASES.get(name.lower(), name.lower())
        for bot in self.bots:
            if bot.name.lower() == key:
                return bot
        return None

    def owner_of(self, voice_id: str) -> BotVoice | None:
        key = voice_id.lower()
        for bot in self.bots:
            if bot.voice_id.lower() == key:
                return bot
        return None

    def stale_owner(self, voice_id: str) -> BotVoice | None:
        key = voice_id.lower()
        for bot in self.bots:
            if key in {item.lower() for item in bot.stale}:
                return bot
        return None

    def known_voice(self, voice_id: str) -> bool:
        return self.owner_of(voice_id) is not None or self.stale_owner(voice_id) is not None


@dataclass(frozen=True)
class VoiceFinding:
    severity: str
    file: str
    line: int
    kind: str
    speaker: str
    bot: str
    voice_in_draft: str
    locked_voice_id: str
    message: str
    snippet: str
    suggested_fix: str

    def sort_key(self) -> tuple:
        order = {"error": 0, "warning": 1, "info": 2}
        return (order[self.severity], self.file, self.line, self.kind, self.speaker)


@dataclass
class VoiceReport:
    drafts_dir: str
    bible_path: str
    bible: VoiceBible
    files: list[str] = field(default_factory=list)
    findings: list[VoiceFinding] = field(default_factory=list)

    def by_severity(self) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts


def load_bible(path: Path) -> VoiceBible:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise BibleError(f"{path} is not UTF-8") from exc
    except OSError as exc:
        raise BibleError(str(exc)) from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    table = _bible_table(text, path)
    bots = _bots_from_table(table, path)
    _apply_arrows(text, bots)
    frozen = tuple(
        BotVoice(
            name=bot.name,
            voice_id=bot.voice_id,
            status=bot.status,
            stale=tuple(sorted(bot.stale, key=str.lower)),
            notes=bot.notes,
            line=bot.line,
        )
        for bot in bots
    )
    return VoiceBible(path=str(path), bots=frozen)


def check_drafts(drafts: Path, bible: VoiceBible) -> VoiceReport:
    """Scan drafts. The bible path is read once by load_bible and then skipped."""
    root = drafts.expanduser().resolve()
    report = VoiceReport(drafts_dir=str(drafts), bible_path=bible.path, bible=bible)
    bible_resolved = Path(bible.path).expanduser().resolve()
    files = _text_files(root)
    report.files = []
    for path in files:
        if path.resolve() == bible_resolved:
            continue
        rel = path.name if root.is_file() else path.relative_to(root).as_posix()
        report.files.append(rel)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.findings.append(
                VoiceFinding(
                    severity="error",
                    file=rel,
                    line=1,
                    kind="encoding",
                    speaker="",
                    bot="",
                    voice_in_draft="",
                    locked_voice_id="",
                    message="This draft is not valid UTF-8, so voices were not compared.",
                    snippet="",
                    suggested_fix="Save the file as UTF-8 and run the checker again.",
                )
            )
            continue
        report.findings.extend(check_text(text, rel, bible))
    report.findings = _dedupe(report.findings)
    report.findings.sort(key=lambda finding: finding.sort_key())
    return report


def check_text(text: str, file_label: str, bible: VoiceBible) -> list[VoiceFinding]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    findings: list[VoiceFinding] = []
    covered: list[tuple[int, int, int]] = []
    roster_lines: list[int] = []
    named: set[str] = set()
    heading = ""
    for number, line in enumerate(lines, start=1):
        match = _HEADING.match(line)
        if match:
            heading = match.group(1)
        assignments = _assignments(line, bible)
        if len([item for item in assignments if item[4]]) >= 3:
            roster_lines.append(number)
        for start, end, speaker, voice, known in assignments:
            if known:
                bot = bible.by_name(speaker)
                if bot is not None:
                    named.add(bot.name)
            finding = _judge(file_label, number, line, speaker, voice, bible)
            if finding is None:
                continue
            findings.append(finding)
            covered.append((number, start, end))
        for start, end, voice in _voice_fields(line):
            if any(number == row and not (end <= left or start >= right) for row, left, right in covered):
                continue
            speaker = _speaker_near(line, heading, bible)
            if speaker:
                finding = _judge(file_label, number, line, speaker, voice, bible)
            else:
                finding = _bare_voice(file_label, number, line, voice, bible)
            if finding is not None:
                findings.append(finding)
                covered.append((number, start, end))
        for start, end, voice in _stale_mentions(line, bible):
            if any(number == row and not (end <= left or start >= right) for row, left, right in covered):
                continue
            if _historical(line, start, voice):
                continue
            owner = bible.stale_owner(voice)
            assert owner is not None
            findings.append(
                VoiceFinding(
                    severity="warning",
                    file=file_label,
                    line=number,
                    kind="retired_mention",
                    speaker=owner.name,
                    bot=owner.name,
                    voice_in_draft=voice,
                    locked_voice_id=owner.voice_id,
                    message=(
                        f"{voice} is a retired voiceId ({owner.name} is now {owner.voice_id}). "
                        "This line still uses it without marking it as former."
                    ),
                    snippet=_snippet(line),
                    suggested_fix=(
                        f"If this is history, write 'formerly {voice}' or 'changed from {voice}'. "
                        f"If it is the current voice, use {owner.voice_id}."
                    ),
                )
            )
            covered.append((number, start, end))
        for bot in bible.bots:
            mention = re.compile(rf"(?i)(?<![A-Za-z0-9])({re.escape(bot.name)})(?![A-Za-z0-9])")
            for match in mention.finditer(line):
                token = match.group(1)
                owner = bible.owner_of(token)
                # "vega" may be Signal's voiceId and also overlap another bot name. A lowercase
                # token that belongs to someone else is the voice, not the bot.
                if (
                    owner is not None
                    and owner.name.lower() != bot.name.lower()
                    and token[:1].islower()
                ):
                    continue
                named.add(bot.name)
                break
            for alias, target in EXTRA_ALIASES.items():
                if target == bot.name.lower() and re.search(rf"(?i)\b{re.escape(alias)}\b", line):
                    named.add(bot.name)
    for number, cells in _voice_table_rows(text):
        speaker, voice = cells
        if not speaker or not voice:
            continue
        known = bible.by_name(speaker)
        if known is not None:
            named.add(known.name)
        finding = _judge(file_label, number, " | ".join(cells), speaker, voice, bible)
        if finding is not None:
            findings.append(finding)
    if roster_lines:
        findings.extend(_roster_gaps(file_label, roster_lines[0], named, bible))
    return _drop_shadowed_mentions(findings)


class _MutableBot:
    def __init__(self, name: str, voice_id: str, status: str, notes: str, line: int):
        self.name = name
        self.voice_id = voice_id
        self.status = status
        self.notes = notes
        self.line = line
        self.stale: set[str] = set()


def _bible_table(text: str, path: Path):
    for table in parse_tables(text):
        kinds = [_bible_header(cell) for cell in table.header]
        if "bot" in kinds and "voice" in kinds:
            return table
    raise BibleError(f"{path}: no table with Bot and voiceId columns")


def _bible_header(cell: str) -> str:
    name = re.sub(r"[*_`]", "", cell).strip().lower()
    if name in {"bot", "bots", "name", "speaker"}:
        return "bot"
    if "voice" in name:
        return "voice"
    if name == "notes":
        return "notes"
    return ""


def _bots_from_table(table, path: Path) -> list[_MutableBot]:
    kinds = [_bible_header(cell) for cell in table.header]
    bot_at = kinds.index("bot")
    voice_at = kinds.index("voice")
    notes_at = kinds.index("notes") if "notes" in kinds else None
    bots: list[_MutableBot] = []
    seen: set[str] = set()
    for line_no, cells in table.rows:
        name = _plain_token(cells[bot_at])
        voice = _first_slug(cells[voice_at])
        notes = cells[notes_at] if notes_at is not None and notes_at < len(cells) else ""
        if not name or not voice:
            raise BibleError(f"{path}: line {line_no} needs a bot name and a voiceId")
        if name.lower() in seen:
            raise BibleError(f"{path}: duplicate bot {name!r}")
        seen.add(name.lower())
        bot = _MutableBot(name, voice, _status(notes), notes.strip(), line_no)
        for match in _FROM.finditer(notes):
            token = match.group(1)
            if token.lower() != voice.lower():
                bot.stale.add(token)
        bots.append(bot)
    if not bots:
        raise BibleError(f"{path}: the voice table has no bots")
    return bots


def _apply_arrows(text: str, bots: list[_MutableBot]) -> None:
    by_name = {bot.name.lower(): bot for bot in bots}
    for match in _ARROW.finditer(text):
        bot = by_name.get(match.group(1).lower())
        if bot is None:
            continue
        old, new = match.group(2), match.group(3)
        if new.lower() == bot.voice_id.lower() and old.lower() != bot.voice_id.lower():
            bot.stale.add(old)


def _status(notes: str) -> str:
    proposed = re.search(r"(?i)\b(?:proposed|pending)\b", notes)
    locked = re.search(r"(?i)\b(?:locked|keeper)\b", notes)
    if proposed and not locked:
        return "proposed"
    return "locked"


def _assignments(line: str, bible: VoiceBible) -> list[tuple[int, int, str, str, bool]]:
    """Return start, end, speaker, voice, and whether the speaker is a bible bot."""
    names = _name_pattern(bible)
    patterns = [
        re.compile(rf"(?i)\b({names})(?:'s|’s)?\s*=\s*['\"]?([A-Za-z][A-Za-z0-9_-]*)['\"]?"),
        re.compile(
            rf"(?i)\b({names})(?:'s|’s)?\s+voice(?:\s*id)?\s*(?:is|=|:)\s*['\"]?"
            rf"([A-Za-z][A-Za-z0-9_-]*)['\"]?"
        ),
        re.compile(rf"(?i)\b({names})(?:'s|’s)?\s+as\s+['\"]([A-Za-z][A-Za-z0-9_-]*)['\"]"),
        re.compile(rf"(?i)\b({names})(?:'s|’s)?\s+as\s+([A-Za-z][A-Za-z0-9_-]*)\b"),
        re.compile(rf"(?i)\b({names})\s*/\s*([A-Za-z][A-Za-z0-9_-]*)\b"),
        re.compile(rf"(?i)\b({names})\s*\(\s*([A-Za-z][A-Za-z0-9_-]*)\s*\)"),
    ]
    loose = {3, 4, 5}
    found: list[tuple[int, int, str, str, bool]] = []
    occupied: list[tuple[int, int]] = []
    for index, pattern in enumerate(patterns):
        for match in pattern.finditer(line):
            start, end = match.span()
            if any(not (end <= left or start >= right) for left, right in occupied):
                continue
            speaker, voice = match.group(1), match.group(2)
            if index in loose and not bible.known_voice(voice):
                continue
            found.append((start, end, speaker, voice, True))
            occupied.append((start, end))
    speaker_re = re.compile(
        r"(?i)\b([A-Za-z][A-Za-z0-9'’_-]{2,})\s*=\s*['\"]?([A-Za-z][A-Za-z0-9_-]*)['\"]?"
    )
    for match in speaker_re.finditer(line):
        start, end = match.span()
        if any(not (end <= left or start >= right) for left, right in occupied):
            continue
        speaker, voice = match.group(1), match.group(2)
        if not bible.known_voice(voice):
            continue
        if bible.by_name(speaker) is not None:
            continue
        found.append((start, end, speaker, voice, False))
        occupied.append((start, end))
    found.sort()
    return found


def _name_pattern(bible: VoiceBible) -> str:
    names = [bot.name for bot in bible.bots]
    for alias, target in EXTRA_ALIASES.items():
        if any(bot.name.lower() == target for bot in bible.bots):
            names.append(alias)
    ordered = sorted(set(names), key=len, reverse=True)
    return "|".join(re.escape(name) for name in ordered)


def _voice_fields(line: str) -> list[tuple[int, int, str]]:
    return [(match.start(), match.end(), match.group(1)) for match in _VOICE_FIELD.finditer(line)]


def _speaker_near(line: str, heading: str, bible: VoiceBible) -> str:
    for source in (line, heading):
        for bot in sorted(bible.bots, key=lambda item: len(item.name), reverse=True):
            if re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(bot.name)}(?![A-Za-z0-9])", source):
                return bot.name
        for alias, target in EXTRA_ALIASES.items():
            if re.search(rf"(?i)\b{alias}\b", source) and bible.by_name(alias):
                return bible.by_name(alias).name  # type: ignore[union-attr]
    return ""


def _stale_mentions(line: str, bible: VoiceBible) -> list[tuple[int, int, str]]:
    stale = sorted({item for bot in bible.bots for item in bot.stale}, key=len, reverse=True)
    if not stale:
        return []
    pattern = re.compile(r"(?i)(?<![A-Za-z0-9])(" + "|".join(re.escape(item) for item in stale) + r")(?![A-Za-z0-9])")
    return [(match.start(1), match.end(1), match.group(1)) for match in pattern.finditer(line)]


def _historical(line: str, start: int, voice: str) -> bool:
    before = line[max(0, start - 48) : start]
    after = line[start + len(voice) : start + len(voice) + 6]
    if re.match(r"\s*(?:->|→)", after):
        return True
    return (
        re.search(
            r"(?i)\b(?:from|formerly|previously|retired|was|were|not|never|instead of|rather than)\s+['\"]?\s*$",
            before,
        )
        is not None
    )


def _voice_table_rows(text: str) -> list[tuple[int, tuple[str, str]]]:
    rows: list[tuple[int, tuple[str, str]]] = []
    for table in parse_tables(text):
        kinds = [_bible_header(cell) for cell in table.header]
        if "bot" not in kinds or "voice" not in kinds:
            continue
        bot_at = kinds.index("bot")
        voice_at = kinds.index("voice")
        for line_no, cells in table.rows:
            speaker = _plain_token(cells[bot_at]) if bot_at < len(cells) else ""
            voice = _first_slug(cells[voice_at]) if voice_at < len(cells) else ""
            rows.append((line_no, (speaker, voice)))
    return rows


def _judge(
    file_label: str,
    line_no: int,
    line: str,
    speaker: str,
    voice: str,
    bible: VoiceBible,
) -> VoiceFinding | None:
    bot = bible.by_name(speaker)
    vid = voice.lower()
    if bot is None:
        owner = bible.owner_of(voice) or bible.stale_owner(voice)
        if owner is None:
            return None
        if vid in {item.lower() for item in owner.stale}:
            message = (
                f"{speaker} is listed as {voice}, a retired voiceId. "
                f"{owner.name}'s locked voiceId is {owner.voice_id}."
            )
            kind = "stale_alias"
            fix = f"Replace {voice} with {owner.voice_id} if this is {owner.name}. Otherwise drop the retired id."
        else:
            message = f"{voice} is {owner.name}'s voiceId, not {speaker}'s."
            kind = "mismatch"
            fix = f"{owner.name} is locked to {owner.voice_id}. Do not assign that voiceId to {speaker}."
        return VoiceFinding(
            severity="error",
            file=file_label,
            line=line_no,
            kind=kind,
            speaker=speaker,
            bot=owner.name,
            voice_in_draft=voice,
            locked_voice_id=owner.voice_id,
            message=message,
            snippet=_snippet(line),
            suggested_fix=fix,
        )
    if vid == bot.voice_id.lower():
        if bot.status == "proposed":
            return VoiceFinding(
                severity="warning",
                file=file_label,
                line=line_no,
                kind="proposed",
                speaker=speaker,
                bot=bot.name,
                voice_in_draft=voice,
                locked_voice_id=bot.voice_id,
                message=f"{bot.name}'s voiceId {bot.voice_id} is still proposed, not locked.",
                snippet=_snippet(line),
                suggested_fix=(
                    f"Treat {bot.voice_id} as provisional until the program lead approves it and the client hears it. "
                    "Do not describe it as locked."
                ),
            )
        return None
    if vid in {item.lower() for item in bot.stale}:
        return VoiceFinding(
            severity="error",
            file=file_label,
            line=line_no,
            kind="stale_alias",
            speaker=speaker,
            bot=bot.name,
            voice_in_draft=voice,
            locked_voice_id=bot.voice_id,
            message=f"{bot.name} is listed as {voice}, a stale alias. Locked voiceId is {bot.voice_id}.",
            snippet=_snippet(line),
            suggested_fix=f"Replace {voice} with {bot.voice_id}.",
        )
    owner = bible.owner_of(voice)
    if owner is not None and owner.name.lower() != bot.name.lower():
        message = (
            f"{bot.name} is listed as {voice}, which belongs to {owner.name}. "
            f"Locked voiceId for {bot.name} is {bot.voice_id}."
        )
    else:
        message = f"{bot.name}'s locked voiceId is {bot.voice_id}, not {voice}."
    return VoiceFinding(
        severity="error",
        file=file_label,
        line=line_no,
        kind="mismatch",
        speaker=speaker,
        bot=bot.name,
        voice_in_draft=voice,
        locked_voice_id=bot.voice_id,
        message=message,
        snippet=_snippet(line),
        suggested_fix=f"Use {bot.voice_id} for {bot.name}.",
    )


def _bare_voice(file_label: str, line_no: int, line: str, voice: str, bible: VoiceBible) -> VoiceFinding | None:
    owner = bible.stale_owner(voice)
    if owner is None:
        return None
    return VoiceFinding(
        severity="warning",
        file=file_label,
        line=line_no,
        kind="retired_mention",
        speaker="",
        bot=owner.name,
        voice_in_draft=voice,
        locked_voice_id=owner.voice_id,
        message=(
            f"voiceId {voice} is retired. {owner.name}'s locked voiceId is {owner.voice_id}."
        ),
        snippet=_snippet(line),
        suggested_fix=f"Set the voiceId to {owner.voice_id}.",
    )


def _roster_gaps(file_label: str, line_no: int, named: set[str], bible: VoiceBible) -> list[VoiceFinding]:
    findings: list[VoiceFinding] = []
    for bot in bible.bots:
        if bot.name in named:
            continue
        if bot.status == "proposed":
            severity = "info"
            message = (
                f"This roster does not name {bot.name}. "
                f"The voice bible lists {bot.name} as {bot.voice_id} (proposed, not locked)."
            )
        else:
            severity = "warning"
            message = (
                f"This roster does not name {bot.name}. Locked voiceId is {bot.voice_id}."
            )
        findings.append(
            VoiceFinding(
                severity=severity,
                file=file_label,
                line=line_no,
                kind="roster_gap",
                speaker=bot.name,
                bot=bot.name,
                voice_in_draft="",
                locked_voice_id=bot.voice_id,
                message=message,
                snippet="",
                suggested_fix=f"Add {bot.name}={bot.voice_id} if this roster is meant to cover the board.",
            )
        )
    return findings


def _plain_token(cell: str) -> str:
    text = re.sub(r"[*_`]", "", cell).strip()
    match = re.match(r"([A-Za-z][A-Za-z0-9'’_-]*)", text)
    return match.group(1) if match else ""


def _first_slug(cell: str) -> str:
    text = re.sub(r"[*_`]", "", cell).strip()
    match = re.search(r"[A-Za-z][A-Za-z0-9_-]*", text)
    if not match or not _SLUG.fullmatch(match.group(0)):
        return ""
    return match.group(0)


def _snippet(line: str) -> str:
    text = re.sub(r"\s+", " ", line).strip()
    if len(text) <= 320:
        return text
    return text[:317].rstrip() + "..."


def _drop_shadowed_mentions(findings: list[VoiceFinding]) -> list[VoiceFinding]:
    """An assignment error already covers a retired id; do not also warn about the same word."""
    assigned = {
        (finding.file, finding.line, finding.voice_in_draft.lower())
        for finding in findings
        if finding.kind in {"stale_alias", "mismatch"}
    }
    return [
        finding
        for finding in findings
        if not (
            finding.kind == "retired_mention"
            and (finding.file, finding.line, finding.voice_in_draft.lower()) in assigned
        )
    ]


def _dedupe(findings: list[VoiceFinding]) -> list[VoiceFinding]:
    seen: set[tuple] = set()
    unique: list[VoiceFinding] = []
    for finding in findings:
        key = (finding.file, finding.line, finding.kind, finding.speaker.lower(), finding.voice_in_draft.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        found.append(path)
    found.sort()
    return found
