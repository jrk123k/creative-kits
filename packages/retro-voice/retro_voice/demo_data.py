"""Placeholder duet for It's Not What We Thought...

Eight bars at 100 BPM. The lead holds "thought" across two notes near the end
(the lone hyphen). The harmony answers underneath with a different preset.
"""

from __future__ import annotations

BPM = 100
BARS = 8

LEAD_NOTES = [
    ("C4", 1), ("E4", 1), ("G4", 1), ("E4", 1),
    ("A4", 2), ("G4", 1), ("E4", 1),
    ("F4", 1), ("A4", 1), ("C5", 2),
    ("B4", 1), ("G4", 1), ("E4", 2),
    ("D4", 1), ("F4", 1), ("A4", 1), ("G4", 1),
    ("E4", 2), ("D4", 1), ("C4", 1),
    ("E4", 1), ("G4", 1), ("A4", 2),
    ("G4", 1), ("E4", 1), ("D4", 1), ("C4", 1),
]

LEAD_LYRICS = (
    "It's not what we thought to-night a tin voice in the wires "
    "sang what we wrote on the bench it's not what we thought - friend"
)

HARMONY_NOTES = [
    ("A3", 2), ("C4", 2),
    ("E4", 2), ("C4", 2),
    ("D4", 2), ("F4", 2),
    ("E4", 4),
    ("F4", 1), ("E4", 1), ("C4", 2),
    ("B3", 2), ("A3", 2),
    ("C4", 2), ("B3", 2),
    ("A3", 4),
]

HARMONY_LYRICS = "we know it's not what we thought sing it back hold on it's not true"

SPOKEN = [
    ("sam", "It's not what we thought."),
    ("bright", "A clean room robot voice, built for the late show."),
    ("deep", "Pitch, mouth, and throat, all under your hand."),
]
