/** Mission elapsed time as T+MM:SS.CC (centiseconds). Minutes may exceed 59. */
export function formatTimecode(elapsedSec: number): string {
  const safe = Number.isFinite(elapsedSec) ? Math.max(0, elapsedSec) : 0;
  const totalCenti = Math.round(safe * 100 + 1e-6);
  const centi = totalCenti % 100;
  const totalSec = Math.floor(totalCenti / 100);
  const seconds = totalSec % 60;
  const minutes = Math.floor(totalSec / 60);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `T+${pad(minutes)}:${pad(seconds)}.${pad(centi)}`;
}
