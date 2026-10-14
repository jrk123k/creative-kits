"""Tiny Standard MIDI File reader and writer.

Reads format 0 and 1 files, follows the tempo map, and folds polyphony down
to a single vocal line (the highest sounding note). Nothing here is a
third-party MIDI library; the file layout is the published SMF specification.
"""

from __future__ import annotations

from dataclasses import dataclass

from retro_voice.notes import Note


class MidiError(ValueError):
    pass


def _vlq(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def _read_vlq(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    started = index
    while index < len(data):
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, index
        if index - started > 4:
            raise MidiError("corrupt MIDI variable-length quantity")
    raise MidiError("unexpected end of MIDI track")


@dataclass
class _RawNote:
    start_tick: int
    end_tick: int
    pitch: int
    velocity: int


def write_midi(
    path: str,
    notes: list[Note],
    tempo_bpm: float = 120.0,
    track_name: str = "vocal",
    ppq: int = 480,
) -> None:
    if tempo_bpm <= 0:
        raise ValueError("tempo must be positive")
    if ppq < 1 or ppq > 32767:
        raise ValueError("ppq out of range")
    us_per_quarter = int(round(60_000_000 / float(tempo_bpm)))
    events: list[tuple[int, int, bytes]] = []
    name = track_name.encode("ascii", "replace")[:80]
    events.append((0, 0, bytes([0xFF, 0x03, len(name)]) + name))
    events.append((0, 0, bytes([0xFF, 0x51, 0x03]) + us_per_quarter.to_bytes(3, "big")))
    for note in notes:
        if note.midi is None or note.dur_beats <= 0:
            continue
        start = int(round(note.start_beat * ppq))
        end = int(round((note.start_beat + note.dur_beats) * ppq))
        if end <= start:
            end = start + 1
        velocity = max(1, min(127, int(note.velocity)))
        events.append((start, 1, bytes([0x90, int(note.midi) & 0x7F, velocity])))
        events.append((end, 0, bytes([0x80, int(note.midi) & 0x7F, 0])))
    events.sort(key=lambda item: (item[0], item[1]))
    track = bytearray()
    previous = 0
    for tick, _order, payload in events:
        track += _vlq(tick - previous)
        track += payload
        previous = tick
    track += _vlq(0)
    track += bytes([0xFF, 0x2F, 0x00])
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big")
    header += (1).to_bytes(2, "big") + int(ppq).to_bytes(2, "big")
    body = b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)
    with open(path, "wb") as handle:
        handle.write(header + body)


def _parse_tracks(data: bytes) -> tuple[int, list[bytes]]:
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("not a Standard MIDI file")
    header_len = int.from_bytes(data[4:8], "big")
    fmt = int.from_bytes(data[8:10], "big")
    ntrks = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if fmt not in (0, 1):
        raise MidiError(f"MIDI format {fmt} is not supported")
    if division & 0x8000:
        raise MidiError("SMPTE MIDI division is not supported")
    if division <= 0:
        raise MidiError("MIDI file has no ticks per quarter")
    cursor = 8 + header_len
    tracks: list[bytes] = []
    while cursor + 8 <= len(data) and len(tracks) < ntrks:
        if data[cursor : cursor + 4] != b"MTrk":
            raise MidiError("expected MTrk chunk")
        length = int.from_bytes(data[cursor + 4 : cursor + 8], "big")
        start = cursor + 8
        end = start + length
        if end > len(data):
            raise MidiError("truncated MIDI track")
        tracks.append(data[start:end])
        cursor = end
    if not tracks:
        raise MidiError("MIDI file has no tracks")
    return division, tracks


def _track_events(track: bytes) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int]]]:
    """Return note events as (tick, kind, pitch, velocity) and tempo changes.

    kind 1 is note-on, kind 0 is note-off. Tempos are (tick, us_per_quarter).
    """
    index = 0
    tick = 0
    status = 0
    notes: list[tuple[int, int, int, int]] = []
    tempos: list[tuple[int, int]] = []
    while index < len(track):
        delta, index = _read_vlq(track, index)
        tick += delta
        if index >= len(track):
            break
        byte = track[index]
        if byte >= 0x80:
            status = byte
            index += 1
        elif status == 0:
            raise MidiError("MIDI running status used before a status byte")
        if status == 0xFF:
            if index >= len(track):
                break
            meta = track[index]
            index += 1
            length, index = _read_vlq(track, index)
            payload = track[index : index + length]
            index += length
            if meta == 0x2F:
                break
            if meta == 0x51 and len(payload) == 3:
                tempos.append((tick, int.from_bytes(payload, "big")))
            status = 0
            continue
        if status in (0xF0, 0xF7):
            length, index = _read_vlq(track, index)
            index += length
            status = 0
            continue
        kind = status & 0xF0
        needed = 1 if kind in (0xC0, 0xD0) else 2
        payload = track[index : index + needed]
        index += needed
        if len(payload) < needed:
            break
        if kind == 0x90:
            velocity = payload[1]
            if velocity == 0:
                notes.append((tick, 0, payload[0], 0))
            else:
                notes.append((tick, 1, payload[0], velocity))
        elif kind == 0x80:
            notes.append((tick, 0, payload[0], 0))
    return notes, tempos


def _monophonic(events: list[tuple[int, int, int, int]]) -> list[_RawNote]:
    # Group by tick. Note-offs happen before note-ons inside a tick.
    buckets: dict[int, list[tuple[int, int, int]]] = {}
    for tick, kind, pitch, velocity in events:
        buckets.setdefault(tick, []).append((kind, pitch, velocity))
    active: dict[int, int] = {}
    spans: list[_RawNote] = []
    current: int | None = None
    span_start = 0
    for tick in sorted(buckets):
        if tick > span_start and current is not None:
            spans.append(_RawNote(span_start, tick, current, active.get(current, 96)))
        for kind, pitch, velocity in sorted(buckets[tick], key=lambda item: item[0]):
            if kind == 0:
                active.pop(pitch, None)
            else:
                active[pitch] = velocity
        current = max(active) if active else None
        span_start = tick
    cleaned: list[_RawNote] = []
    for span in spans:
        if span.end_tick > span.start_tick:
            cleaned.append(span)
    return cleaned


def _initial_bpm(tempos: list[tuple[int, int]]) -> float:
    us = 500_000
    for tick, value in tempos:
        if tick == 0:
            us = value
            break
    if tempos and all(tick != 0 for tick, _us in tempos):
        us = tempos[0][1]
    if us <= 0:
        us = 500_000
    return 60_000_000 / us


def _tick_to_seconds(tick: int, tempos: list[tuple[int, int]], ppq: int) -> float:
    points = list(tempos)
    if not points or points[0][0] != 0:
        points.insert(0, (0, 500_000))
    seconds = 0.0
    for index, (start, us) in enumerate(points):
        nxt = points[index + 1][0] if index + 1 < len(points) else None
        if nxt is None or tick <= nxt:
            return seconds + (tick - start) * (us / 1_000_000) / ppq
        seconds += (nxt - start) * (us / 1_000_000) / ppq
    return seconds


def read_midi_notes(
    path: str,
    track: int | None = None,
    tempo_bpm: float | None = None,
) -> tuple[list[Note], float]:
    """Return monophonic notes on a beat grid and the BPM used to place them.

    With ``tempo_bpm`` set, tick positions are beats (ticks / PPQ) played at
    that constant tempo, which is how a duet locks to a drum machine.

    Without it, a single tempo map entry becomes that constant BPM. A file
    with tempo changes is followed in real time and then warped back onto the
    initial BPM so sample positions still match the file's clock.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    ppq, tracks = _parse_tracks(data)
    chosen: list[tuple[int, int, int, int]] = []
    tempos: list[tuple[int, int]] = []
    if track is None:
        for blob in tracks:
            notes, found = _track_events(blob)
            if found and not tempos:
                tempos = found
            elif found:
                tempos.extend(found)
            if notes and not chosen:
                chosen = notes
        if not chosen:
            # A later track may hold the only notes; scan all and prefer the
            # one with the most note-ons.
            best: list[tuple[int, int, int, int]] = []
            for blob in tracks:
                notes, found = _track_events(blob)
                ons = [item for item in notes if item[1] == 1]
                if len(ons) > len([item for item in best if item[1] == 1]):
                    best = notes
            chosen = best
    else:
        if track < 0 or track >= len(tracks):
            raise MidiError(f"MIDI track {track} is out of range (file has {len(tracks)})")
        chosen, local_tempos = _track_events(tracks[track])
        for blob in tracks:
            _notes, found = _track_events(blob)
            tempos.extend(found)
        if not tempos:
            tempos = local_tempos
    if not chosen:
        raise MidiError(f"no notes found in {path}")
    tempos = sorted(tempos, key=lambda item: item[0])
    # Merge duplicate tempo ticks from several tracks: the last one wins.
    merged: dict[int, int] = {}
    for tick, us in tempos:
        merged[tick] = us
    tempos = sorted(merged.items())
    raw = _monophonic(chosen)
    if not raw:
        raise MidiError(f"no sounding notes in {path}")
    file_bpm = _initial_bpm(tempos)
    multi = len(tempos) > 1
    bpm = float(tempo_bpm) if tempo_bpm else file_bpm
    if bpm <= 0:
        raise ValueError("tempo must be positive")
    notes: list[Note] = []
    if tempo_bpm or not multi:
        for item in raw:
            notes.append(
                Note(
                    midi=item.pitch,
                    start_beat=item.start_tick / ppq,
                    dur_beats=(item.end_tick - item.start_tick) / ppq,
                    velocity=item.velocity or 96,
                )
            )
    else:
        for item in raw:
            start_sec = _tick_to_seconds(item.start_tick, tempos, ppq)
            end_sec = _tick_to_seconds(item.end_tick, tempos, ppq)
            notes.append(
                Note(
                    midi=item.pitch,
                    start_beat=start_sec * bpm / 60.0,
                    dur_beats=max(1e-4, (end_sec - start_sec) * bpm / 60.0),
                    velocity=item.velocity or 96,
                )
            )
    return notes, bpm


def describe_notes(notes: list[Note]) -> str:
    return ", ".join(f"{note.name}" if note.midi is not None else "rest" for note in notes[:12])
