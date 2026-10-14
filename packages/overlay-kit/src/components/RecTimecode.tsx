import {useCurrentFrame, useVideoConfig} from "remotion";
import {CornerTicks} from "./CornerTicks";
import {formatTimecode} from "../lib/timecode";
import type {Colors, Fonts} from "../lib/types";

export const RecTimecode: React.FC<{
  offsetSec: number;
  songStartSec: number;
  camera: string;
  colors: Colors;
  fonts: Fonts;
}> = ({offsetSec, songStartSec, camera, colors, fonts}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const timecode = formatTimecode(offsetSec + Math.max(0, frame / fps - songStartSec));
  const blinkOn = Math.floor(frame / 15) % 2 === 0;

  return (
    <div
      style={{
        position: "absolute",
        top: 62,
        right: 118,
        minWidth: 360,
        padding: "14px 18px 16px",
        background: colors.box,
        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.28)",
        textAlign: "right",
      }}
    >
      <CornerTicks color={colors.cyan} />
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: 10,
          fontFamily: fonts.hud,
          fontWeight: 700,
          fontSize: 15,
          letterSpacing: "0.22em",
          color: colors.red,
          lineHeight: 1,
        }}
      >
        <div
          style={{
            width: 11,
            height: 11,
            borderRadius: 99,
            background: colors.red,
            opacity: blinkOn ? 1 : 0.18,
            boxShadow: blinkOn ? `0 0 10px ${colors.red}` : "none",
          }}
        />
        REC
      </div>
      <div
        style={{
          marginTop: 8,
          fontFamily: fonts.hud,
          fontWeight: 400,
          fontSize: 48,
          letterSpacing: "0.02em",
          color: colors.white,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {timecode}
      </div>
      <div
        style={{
          marginTop: 8,
          fontFamily: fonts.hud,
          fontWeight: 400,
          fontSize: 14,
          letterSpacing: "0.16em",
          color: colors.grey,
          lineHeight: 1.2,
        }}
      >
        {camera}
      </div>
    </div>
  );
};
