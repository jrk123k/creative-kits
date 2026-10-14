import {CornerTicks} from "./CornerTicks";
import {Equalizer} from "./Equalizer";
import type {Colors, Fonts, StatusLine} from "../lib/types";

function toneColor(tone: StatusLine["tone"], colors: Colors): string {
  if (tone === "green") return colors.green;
  if (tone === "red") return colors.red;
  if (tone === "grey") return colors.grey;
  return colors.cyan;
}

export const StatusBlock: React.FC<{
  lines: StatusLine[];
  showStatus: boolean;
  showEqualizer: boolean;
  spectrum: number[];
  colors: Colors;
  fonts: Fonts;
}> = ({lines, showStatus, showEqualizer, spectrum, colors, fonts}) => {
  return (
    <div
      style={{
        position: "absolute",
        left: 118,
        bottom: 58,
        minWidth: 280,
        padding: "14px 16px 14px",
        background: colors.box,
        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.28)",
      }}
    >
      <CornerTicks color={colors.cyan} />
      {showStatus &&
        lines.map((line) => (
          <div
            key={`${line.label}-${line.value}`}
            style={{
              fontFamily: fonts.hud,
              fontWeight: 400,
              fontSize: 16,
              letterSpacing: "0.08em",
              lineHeight: 1.65,
              whiteSpace: "nowrap",
            }}
          >
            <span style={{color: colors.grey}}>{line.label}</span>
            <span style={{color: colors.cyan}}>{" > "}</span>
            <span style={{color: toneColor(line.tone, colors)}}>{line.value}</span>
          </div>
        ))}
      {showEqualizer && (
        <div style={{marginTop: showStatus ? 4 : 0}}>
          <div
            style={{
              fontFamily: fonts.hud,
              fontWeight: 400,
              fontSize: 11,
              letterSpacing: "0.28em",
              color: colors.cyan,
              lineHeight: 1,
            }}
          >
            EQ
          </div>
          <Equalizer spectrum={spectrum} color={colors.cyan} />
        </div>
      )}
    </div>
  );
};
