import {getAudioData, visualizeAudio} from "@remotion/media-utils";
import {useEffect, useRef, useState} from "react";
import {
  cancelRender,
  continueRender,
  delayRender,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
} from "remotion";
import type {MediaUtilsAudioData} from "@remotion/media-utils";
import {spectrumAtTime} from "./lib/spectrum";

const SAMPLES = 64;

export function useSongSpectrum(song: string): number[] {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const src = staticFile(song);
  const [audioData, setAudioData] = useState<MediaUtilsAudioData | null>(null);
  const handleRef = useRef<number | null>(null);

  useEffect(() => {
    const handle = delayRender(`Loading song audio ${song}`);
    handleRef.current = handle;
    let cancelled = false;
    getAudioData(src)
      .then((data) => {
        if (!cancelled) setAudioData(data);
      })
      .catch((error) => cancelRender(error));
    return () => {
      cancelled = true;
    };
  }, [song, src]);

  useEffect(() => {
    if (!audioData || handleRef.current === null) return;
    continueRender(handleRef.current);
    handleRef.current = null;
  }, [audioData]);

  if (!audioData) return new Array(SAMPLES).fill(0);
  return spectrumAtTime(frame / fps, audioData.durationInSeconds, SAMPLES, () =>
    visualizeAudio({
      fps,
      frame,
      audioData,
      numberOfSamples: SAMPLES,
      optimizeFor: "speed",
      smoothing: true,
    }),
  );
}
