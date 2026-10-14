import {CornerTicks} from "./CornerTicks";
import type {Colors, LocationLabel, Fonts} from "../lib/types";

export const LocationTag: React.FC<{
  location: LocationLabel;
  colors: Colors;
  fonts: Fonts;
}> = ({location, colors, fonts}) => {
  return (
    <div
      style={{
        position: "absolute",
        top: 62,
        left: 118,
        minWidth: 320,
        padding: "14px 18px 16px",
        background: colors.box,
        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.28)",
      }}
    >
      <CornerTicks color={colors.cyan} />
      <div
        style={{
          fontFamily: fonts.hud,
          fontWeight: 400,
          fontSize: 12,
          letterSpacing: "0.34em",
          color: colors.cyan,
          lineHeight: 1,
        }}
      >
        {location.kicker}
      </div>
      <div
        style={{
          marginTop: 8,
          width: 36,
          height: 1,
          background: colors.cyan,
          opacity: 0.85,
        }}
      />
      <div
        style={{
          marginTop: 8,
          fontFamily: fonts.hud,
          fontWeight: 700,
          fontSize: 26,
          letterSpacing: "0.06em",
          color: colors.white,
          lineHeight: 1.05,
          whiteSpace: "nowrap",
        }}
      >
        {location.title}
      </div>
      <div
        style={{
          marginTop: 6,
          fontFamily: fonts.hud,
          fontWeight: 400,
          fontSize: 13,
          letterSpacing: "0.18em",
          color: colors.grey,
          lineHeight: 1.2,
          whiteSpace: "nowrap",
        }}
      >
        {location.subtitle}
      </div>
    </div>
  );
};
