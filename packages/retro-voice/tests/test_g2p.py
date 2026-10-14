from retro_voice.g2p import parse_phoneme_string, pronounce


def test_sam_string_and_arpabet():
    sam = parse_phoneme_string("HEHLOW")
    assert [phone.name for phone in sam] == ["HH", "EH", "L", "OW"]
    arpabet = parse_phoneme_string("HH EH1 L OW0")
    assert [(phone.name, phone.stress) for phone in arpabet] == [
        ("HH", 0),
        ("EH", 1),
        ("L", 0),
        ("OW", 0),
    ]
    assert [phone.name for phone in parse_phoneme_string("OH UX NX")] == ["AO", "UW", "NG"]


def test_lexicon_and_rules():
    assert [phone.name for phone in pronounce("thought")] == ["TH", "AO", "T"]
    assert [phone.name for phone in pronounce("It's")] == ["IH", "T", "S"]
    assert [phone.name for phone in pronounce("like")] == ["L", "AY", "K"]
    assert [phone.name for phone in pronounce("ship")] == ["SH", "IH", "P"]
    assert pronounce("the")[1].stress == 0
    assert pronounce("a")[0].stress == 0
