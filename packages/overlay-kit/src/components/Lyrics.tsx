import type {Colors, Fonts, LyricLine, LyricWord} from "../lib/types";

function fontSizeFor(line: LyricLine): number {
  const length = line.words.map((word) => word.text).join(" ").length;
  if (length > 46) return 68;
  if (length > 38) return 78;
  if (length > 28) return 92;
  return 112;
}

function wordColor(word: LyricWord, timeSec: number, colors: Colors): string {
  const sung = timeSec + 1e-4 >= word.start;
  if (!sung) return colors.dim;
  return word.accent ? colors.red : colors.white;
}

export const Lyrics: React.FC<{
  line: LyricLine;
  timeSec: number;
  colors: Colors;
  fonts: Fonts;
}> = ({line, timeSec, colors, fonts}) => {
  const fontSize = fontSizeFor(line);
  return (
    <div
      style={{
        position: "absolute",
        left: 100,
        right: 100,
        top: 690,
        height: 220,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontFamily: fonts.lyrics,
          fontWeight: 400,
          fontSize,
          lineHeight: 0.92,
          letterSpacing: "0.03em",
          textShadow: "0 2px 0 rgba(0,0,0,0.85), 0 10px 28px rgba(0,0,0,0.55)",
          maxWidth: 1700,
        }}
      >
        {line.words.map((word, index) => (
          <span
            key={`${word.start}-${index}`}
            style={{
              color: wordColor(word, timeSec, colors),
              marginLeft: index === 0 ? 0 : "0.22em",
              display: "inline-block",
            }}
          >
            {word.text.toUpperCase()}
          </span>
        ))}
      </div>
    </div>
  );
};
