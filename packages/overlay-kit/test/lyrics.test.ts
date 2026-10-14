import assert from "node:assert/strict";
import test from "node:test";
import {
  activeLine,
  applyOverrides,
  collectWords,
  normalizeToken,
  parseMarkedText,
  resolveLyrics,
  wordsToLines,
} from "../src/lib/lyrics.js";
import type {AlignedWord, Alignment, LyricOptions} from "../src/lib/types.js";

const opts = {
  pauseGapSec: 0.8,
  maxLineChars: 20,
  maxWords: 4,
};

function word(text: string, start: number, end: number): AlignedWord {
  return {word: text, start, end};
}

test("normalizeToken strips punctuation and case", () => {
  assert.equal(normalizeToken("Humans."), "humans");
  assert.equal(normalizeToken("Xenobiologist,"), "xenobiologist");
});

test("parseMarkedText marks *spans* and keeps trailing punctuation", () => {
  const tokens = parseMarkedText("HELLO AGAIN, *HUMANS*.");
  assert.deepEqual(tokens, [
    {display: "HELLO", accent: false},
    {display: "AGAIN,", accent: false},
    {display: "HUMANS.", accent: true},
  ]);
  const multi = parseMarkedText("NO *HOPE FOR* THIS");
  assert.deepEqual(
    multi.map((token) => token.accent),
    [false, true, true, false],
  );
});

test("wordsToLines splits on pauses", () => {
  const lines = wordsToLines(
    [
      word("Hello", 0, 0.4),
      word("again,", 0.5, 0.9),
      word("humans.", 2.2, 2.8),
    ],
    opts,
  );
  assert.equal(lines.length, 2);
  assert.equal(lines[0].words.map((item) => item.text).join(" "), "Hello again,");
  assert.equal(lines[1].words[0].text, "humans.");
  assert.equal(lines[0].end, 0.9);
  assert.equal(lines[1].start, 2.2);
});

test("wordsToLines splits on max length and max words", () => {
  const tight = [
    word("alpha", 0, 0.2),
    word("bravo", 0.3, 0.5),
    word("charlie", 0.6, 0.8),
    word("delta", 0.9, 1.1),
    word("echo", 1.2, 1.4),
  ];
  const byWords = wordsToLines(tight, {...opts, maxLineChars: 80, maxWords: 2});
  assert.equal(byWords.length, 3);
  assert.deepEqual(
    byWords.map((line) => line.words.length),
    [2, 2, 1],
  );
  const byChars = wordsToLines(tight, {
    pauseGapSec: 5,
    maxLineChars: 12,
    maxWords: 10,
  });
  assert.ok(byChars.length >= 3);
  for (const line of byChars) {
    const text = line.words.map((item) => item.text).join(" ");
    assert.ok(text.length <= 12 || line.words.length === 1);
  }
});

test("accent words are case-insensitive and ignore punctuation", () => {
  const lines = wordsToLines(
    [word("Humans.", 0, 0.4), word("hope", 0.5, 0.8)],
    {...opts, pauseGapSec: 2, maxLineChars: 40},
    ["HUMANS"],
  );
  assert.equal(lines[0].words[0].accent, true);
  assert.equal(lines[0].words[1].accent, false);
});

test("manual overrides replace overlapping lines and keep *word* accents", () => {
  const words = [
    word("Hello", 0.1, 0.4),
    word("again,", 0.5, 0.9),
    word("humans.", 1.0, 1.4),
    word("Later", 5, 5.4),
  ];
  const auto = wordsToLines(words, {
    pauseGapSec: 0.8,
    maxLineChars: 40,
    maxWords: 8,
  });
  const lines = applyOverrides(
    auto,
    [{start: 0.1, end: 1.5, text: "HELLO AGAIN, *HUMANS*."}],
    words,
    ["hope"],
  );
  assert.equal(lines.length, 2);
  assert.equal(lines[0].words.map((item) => item.text).join(" "), "HELLO AGAIN, HUMANS.");
  assert.equal(lines[0].words[2].accent, true);
  assert.equal(lines[0].words[2].start, 1.0);
  assert.equal(lines[1].words[0].text, "Later");
});

test("overrides reject overlaps and still mark the accent list", () => {
  assert.throws(
    () =>
      applyOverrides(
        [],
        [
          {start: 0, end: 2, text: "ONE"},
          {start: 1, end: 3, text: "TWO"},
        ],
        [],
        [],
      ),
    /overlap/i,
  );
  const line = applyOverrides(
    [],
    [{start: 0, end: 1, text: "STILL HUMANS"}],
    [],
    ["humans"],
  );
  assert.equal(line[0].words[1].accent, true);
  assert.equal(line[0].words[0].accent, false);
});

test("collectWords flattens segments when the top-level list is absent", () => {
  const alignment: Alignment = {
    segments: [
      {
        text: "No hope.",
        start: 1,
        end: 2,
        words: [word("No", 1, 1.2), word("hope.", 1.3, 1.8)],
      },
    ],
  };
  const words = collectWords(alignment);
  assert.equal(words.map((item) => item.word).join(" "), "No hope.");
});

test("activeLine holds through a short pause and yields at the next line", () => {
  const lines = wordsToLines(
    [
      word("Hello", 0, 0.4),
      word("again", 0.5, 0.9),
      word("later", 3, 3.4),
    ],
    {...opts, pauseGapSec: 0.8, maxLineChars: 40},
  );
  assert.equal(activeLine(lines, 0.2, 0.5)?.words[0].text, "Hello");
  assert.equal(activeLine(lines, 1.2, 0.5)?.words[0].text, "Hello");
  assert.equal(activeLine(lines, 2.0, 0.5), null);
  assert.equal(activeLine(lines, 3.1, 0.5)?.words[0].text, "later");
});

test("resolveLyrics applies auto split then overrides", () => {
  const alignment: Alignment = {
    duration_sec: 8,
    words: [
      word("Galactic", 0, 0.4),
      word("intelligence.", 0.5, 1),
      word("Alone.", 3, 3.4),
    ],
  };
  const options: LyricOptions = {
    pauseGapSec: 0.8,
    maxLineChars: 40,
    maxWords: 6,
    holdSec: 0.5,
    overrides: [{start: 3, end: 3.5, text: "*ALONE*."}],
  };
  const lines = resolveLyrics(alignment, options, ["galactic"]);
  assert.equal(lines.length, 2);
  assert.equal(lines[0].words[0].accent, true);
  assert.equal(lines[1].words[0].text, "ALONE.");
  assert.equal(lines[1].words[0].accent, true);
});
