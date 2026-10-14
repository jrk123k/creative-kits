from retro_voice.midi_io import read_midi_notes, write_midi
from retro_voice.notes import Note, beats_to_samples, midi_hz, parse_pitch


def test_note_names_and_sample_grid():
    assert parse_pitch("A4") == 69
    assert parse_pitch("C4") == 60
    assert parse_pitch("Bb3") == 58
    assert parse_pitch("rest") is None
    assert abs(midi_hz(69) - 440.0) < 1e-9
    assert beats_to_samples(1, 100, 22050) == 13230
    assert beats_to_samples(32, 100, 22050) == 423360


def test_midi_roundtrip_and_monophonic_policy(tmp_path):
    path = tmp_path / "line.mid"
    notes = [
        Note(60, 0, 1, velocity=80),
        Note(64, 1, 1, velocity=100),
        Note(67, 2.5, 1.5, velocity=90),
    ]
    write_midi(path, notes, tempo_bpm=100, track_name="lead")
    read_back, bpm = read_midi_notes(path, tempo_bpm=100)
    assert abs(bpm - 100) < 1e-6
    assert [note.midi for note in read_back] == [60, 64, 67]
    assert abs(read_back[0].start_beat - 0) < 1e-9
    assert abs(read_back[1].start_beat - 1) < 1e-9
    assert abs(read_back[2].start_beat - 2.5) < 1e-6
    assert abs(read_back[2].dur_beats - 1.5) < 1e-6

    chord = tmp_path / "chord.mid"
    write_midi(
        chord,
        [Note(60, 0, 2), Note(67, 0, 2), Note(64, 2, 1)],
        tempo_bpm=120,
    )
    mono, _bpm = read_midi_notes(chord)
    assert [note.midi for note in mono] == [67, 64]
    assert abs(mono[0].dur_beats - 2) < 1e-6

    overlap = tmp_path / "overlap.mid"
    write_midi(overlap, [Note(60, 0, 2), Note(64, 1, 1)], tempo_bpm=100)
    folded, _bpm = read_midi_notes(overlap, tempo_bpm=100)
    assert [(note.midi, note.start_beat, note.dur_beats) for note in folded] == [
        (60, 0.0, 1.0),
        (64, 1.0, 1.0),
    ]
