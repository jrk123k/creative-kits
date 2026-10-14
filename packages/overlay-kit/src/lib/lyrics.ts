import type {
  AlignedWord,
  Alignment,
  LyricLine,
  LyricOptions,
  LyricOverride,
  LyricWord,
} from "./types";
import {TimelineError} from "./types";

export function normalizeToken(word: string): string {
  return word.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

export function parseMarkedText(
  input: string,
): Array<{display: string; accent: boolean}> {
  const marked = input.replace(/\*([^*]+)\*/g, (_all, inner: string) =>
    inner
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((word) => `\u0001${word}`)
      .join(" "),
  );
  return marked
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => {
      const accent = token.startsWith("\u0001");
      return {display: accent ? token.slice(1) : token, accent};
    });
}

export function collectWords(alignment: Alignment): AlignedWord[] {
  const source =
    alignment.words && alignment.words.length > 0
      ? alignment.words
      : (alignment.segments ?? []).flatMap((segment) => segment.words ?? []);

  const words: AlignedWord[] = [];
  for (const word of source) {
    if (!word || typeof word.word !== "string") {
      throw new TimelineError("Alignment word is missing a word string.");
    }
    if (typeof word.start !== "number" || typeof word.end !== "number") {
      throw new TimelineError(
        `Alignment word "${word.word}" is missing start/end times.`,
      );
    }
    if (!word.word.trim()) continue;
    words.push({
      word: word.word,
      start: word.start,
      end: word.end,
      confidence: word.confidence,
    });
  }
  words.sort((a, b) => a.start - b.start || a.end - b.end);
  return words;
}

function lineFromWords(
  words: AlignedWord[],
  accentWords: Set<string>,
): LyricLine {
  const lyricWords: LyricWord[] = words.map((word) => ({
    text: word.word,
    start: word.start,
    end: word.end,
    accent: accentWords.has(normalizeToken(word.word)),
  }));
  return {
    start: lyricWords[0].start,
    end: lyricWords[lyricWords.length - 1].end,
    words: lyricWords,
  };
}

export function wordsToLines(
  words: AlignedWord[],
  options: Pick<LyricOptions, "pauseGapSec" | "maxLineChars" | "maxWords">,
  accentWords: string[] = [],
): LyricLine[] {
  const accents = new Set(accentWords.map((word) => normalizeToken(word)));
  const sorted = [...words].sort((a, b) => a.start - b.start || a.end - b.end);
  const groups: AlignedWord[][] = [];
  let current: AlignedWord[] = [];

  const lengthOf = (group: AlignedWord[]) =>
    group.map((word) => word.word).join(" ").length;

  for (const word of sorted) {
    if (current.length === 0) {
      current.push(word);
      continue;
    }
    const previous = current[current.length - 1];
    const gap = word.start - previous.end;
    const nextLen = lengthOf([...current, word]);
    if (
      gap > options.pauseGapSec ||
      current.length >= options.maxWords ||
      nextLen > options.maxLineChars
    ) {
      groups.push(current);
      current = [word];
    } else {
      current.push(word);
    }
  }
  if (current.length > 0) groups.push(current);
  return groups.map((group) => lineFromWords(group, accents));
}

function isAccent(display: string, marked: boolean, accents: Set<string>): boolean {
  return marked || accents.has(normalizeToken(display));
}

export function lineFromOverride(
  override: LyricOverride,
  words: AlignedWord[],
  accentWords: string[],
): LyricLine {
  const marked = parseMarkedText(override.text);
  if (marked.length === 0) {
    throw new TimelineError(
      `Lyric override at ${override.start} has no words.`,
    );
  }
  const accents = new Set(accentWords.map((word) => normalizeToken(word)));
  const pool = words.filter(
    (word) => word.start >= override.start - 0.03 && word.start < override.end,
  );
  const poolStart = pool[0]?.start ?? override.start;
  const poolEnd = pool[pool.length - 1]?.end ?? override.end;
  const lyricWords: LyricWord[] = marked.map((token, index) => {
    let start: number;
    let end: number;
    if (pool.length === marked.length) {
      start = pool[index].start;
      end = pool[index].end;
    } else if (pool.length > 0) {
      const span = Math.max(0.05, poolEnd - poolStart);
      start = poolStart + (span * index) / marked.length;
      end = poolStart + (span * (index + 1)) / marked.length;
    } else {
      const span = Math.max(0.05, override.end - override.start);
      start = override.start + (span * index) / marked.length;
      end = override.start + (span * (index + 1)) / marked.length;
    }
    return {
      text: token.display,
      start,
      end,
      accent: isAccent(token.display, token.accent, accents),
    };
  });
  return {
    start: lyricWords[0].start,
    end: lyricWords[lyricWords.length - 1].end,
    words: lyricWords,
  };
}

function overlaps(line: LyricLine, override: LyricOverride): boolean {
  return line.start < override.end && line.end > override.start;
}

export function applyOverrides(
  lines: LyricLine[],
  overrides: LyricOverride[],
  words: AlignedWord[],
  accentWords: string[],
): LyricLine[] {
  const ordered = [...overrides].sort((a, b) => a.start - b.start);
  for (let i = 1; i < ordered.length; i++) {
    if (ordered[i].start < ordered[i - 1].end) {
      throw new TimelineError(
        `Lyric overrides overlap at ${ordered[i - 1].start} and ${ordered[i].start}.`,
      );
    }
  }
  const kept = lines.filter(
    (line) => !ordered.some((override) => overlaps(line, override)),
  );
  const replaced = ordered.map((override) =>
    lineFromOverride(override, words, accentWords),
  );
  return [...kept, ...replaced].sort((a, b) => a.start - b.start || a.end - b.end);
}

export function resolveLyrics(
  alignment: Alignment,
  options: LyricOptions,
  accentWords: string[],
): LyricLine[] {
  const words = collectWords(alignment);
  const auto = wordsToLines(words, options, accentWords);
  return applyOverrides(auto, options.overrides, words, accentWords);
}

export function activeLine(
  lines: LyricLine[],
  timeSec: number,
  holdSec: number,
): LyricLine | null {
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    const next = lines[index + 1];
    const windowEnd = next
      ? Math.min(line.end + holdSec, next.start)
      : line.end + holdSec;
    if (timeSec >= line.start && timeSec < windowEnd) return line;
  }
  return null;
}

export function alignmentDuration(
  alignment: Alignment,
  lines: LyricLine[],
  scenesEnd: number,
): number {
  const wordEnd = collectWords(alignment).reduce(
    (max, word) => Math.max(max, word.end),
    0,
  );
  const lineEnd = lines.reduce((max, line) => Math.max(max, line.end), 0);
  const declared =
    typeof alignment.duration_sec === "number" ? alignment.duration_sec : 0;
  return Math.max(declared, wordEnd, lineEnd, scenesEnd);
}
