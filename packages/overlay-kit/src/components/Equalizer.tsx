const BARS = 12;

function barLevels(spectrum: number[]): number[] {
  const usable = spectrum.length > 2 ? spectrum.slice(1) : spectrum;
  return Array.from({length: BARS}, (_, index) => {
    if (usable.length === 0) return 0.08;
    const start = Math.floor((index / BARS) * usable.length);
    const end = Math.max(
      start + 1,
      Math.floor(((index + 1) / BARS) * usable.length),
    );
    let peak = 0;
    for (let i = start; i < end && i < usable.length; i++) {
      peak = Math.max(peak, usable[i] ?? 0);
    }
    return Math.max(0.08, Math.min(1, Math.sqrt(peak)));
  });
}

export const Equalizer: React.FC<{spectrum: number[]; color: string}> = ({
  spectrum,
  color,
}) => {
  const levels = barLevels(spectrum);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        gap: 4,
        height: 34,
        marginTop: 12,
      }}
    >
      {levels.map((level, index) => (
        <div
          key={index}
          style={{
            width: 7,
            height: Math.round(3 + level * 31),
            background: color,
            boxShadow: `0 0 8px ${color}`,
            opacity: 0.35 + level * 0.65,
          }}
        />
      ))}
    </div>
  );
};
