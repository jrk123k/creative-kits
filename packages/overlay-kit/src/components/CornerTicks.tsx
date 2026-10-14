import type {CSSProperties} from "react";

const ARM = 11;
const STROKE = 2;

export const CornerTicks: React.FC<{color: string}> = ({color}) => {
  const tick = (extra: CSSProperties) => (
    <div
      style={{
        position: "absolute",
        width: ARM,
        height: ARM,
        ...extra,
      }}
    />
  );
  return (
    <>
      {tick({
        top: -1,
        left: -1,
        borderTop: `${STROKE}px solid ${color}`,
        borderLeft: `${STROKE}px solid ${color}`,
      })}
      {tick({
        top: -1,
        right: -1,
        borderTop: `${STROKE}px solid ${color}`,
        borderRight: `${STROKE}px solid ${color}`,
      })}
      {tick({
        bottom: -1,
        left: -1,
        borderBottom: `${STROKE}px solid ${color}`,
        borderLeft: `${STROKE}px solid ${color}`,
      })}
      {tick({
        bottom: -1,
        right: -1,
        borderBottom: `${STROKE}px solid ${color}`,
        borderRight: `${STROKE}px solid ${color}`,
      })}
    </>
  );
};
