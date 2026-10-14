from retro_voice.cli import main
from retro_voice.audio import read_wav


def test_say_phonemes_and_bad_lyrics(tmp_path):
    spoken = tmp_path / "spoken.wav"
    assert main(["say", "It's not what we thought.", "-o", str(spoken), "--effects", "off"]) == 0
    audio, sr = read_wav(spoken)
    assert sr == 22050
    assert float(audio.std()) > 0.02

    phones = tmp_path / "phones.wav"
    code = main(["say", "--phonemes", "HEHLOW", "-o", str(phones), "--effects", "sam", "--pitch", "80"])
    assert code == 0
    phone_audio, _sr = read_wav(phones)
    assert float(phone_audio.std()) > 0.02

    missing = tmp_path / "nope.wav"
    assert main(["sing", "--midi", str(tmp_path / "missing.mid"), "--lyrics", "la", "-o", str(missing)]) == 1


def test_sing_score_cli(tmp_path):
    score = tmp_path / "tune.rvscore"
    score.write_text(
        "tempo 120\npitch 64\nmouth 128\nthroat 128\nspeed 72\n\nA4 2 la\n",
        encoding="utf-8",
    )
    out = tmp_path / "sung.wav"
    code = main(["sing", "--score", str(score), "-o", str(out), "--effects", "off", "--align"])
    assert code == 0
    audio, sr = read_wav(out)
    assert abs(len(audio) / sr - 1.0) < 0.02
