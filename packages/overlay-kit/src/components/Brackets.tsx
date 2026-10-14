import type {CSSProperties} from "react";

const ARM = 92;
const STROKE = 2;
const INSET = 34;

export const Brackets: React.FC<{color: string}> = ({color}) => {
  const base: CSSProperties = {
    position: "absolute",
    width: ARM,
    height: ARM,
    boxShadow: `0 0 10px ${color}`,
  };
  return (
    <>
      <div
        style={{
          ...base,
          top: INSET,
          left: INSET,
          borderTop: `${STROKE}px solid ${color}`,
          borderLeft: `${STROKE}px solid ${color}`,
        }}
      />
      <div
        style={{
          ...base,
          top: INSET,
          right: INSET,
          borderTop: `${STROKE}px solid ${color}`,
          borderRight: `${STROKE}px solid ${color}`,
        }}
      />
      <div
        style={{
          ...base,
          bottom: INSET,
          left: INSET,
          borderBottom: `${STROKE}px solid ${color}`,
          borderLeft: `${STROKE}px solid ${color}`,
        }}
      />
      <div
        style={{
          ...base,
          bottom: INSET,
          right: INSET,
          borderBottom: `${STROKE}px solid ${color}`,
          borderRight: `${STROKE}px solid ${color}`,
        }}
      />
    </>
  );
};
