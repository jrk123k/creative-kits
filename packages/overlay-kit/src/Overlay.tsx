import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import {Brackets} from "./components/Brackets";
import {LocationTag} from "./components/LocationTag";
import {Lyrics} from "./components/Lyrics";
import {RecTimecode} from "./components/RecTimecode";
import {StatusBlock} from "./components/StatusBlock";
import "./fonts";
import {activeLine} from "./lib/lyrics";
import {layerMotion, sceneAt, sceneGlitch, type LayerMotion} from "./lib/motion";
import type {ResolvedTimeline} from "./lib/types";
import {useSongSpectrum} from "./useSongSpectrum";

export type OverlayProps = {
  timeline: ResolvedTimeline;
};

const Layer: React.FC<{motion: LayerMotion; children: React.ReactNode}> = ({
  motion,
  children,
}) => {
  if (!motion.visible) return null;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity: motion.opacity,
        transform: `translate(${motion.jitterX}px, ${motion.jitterY}px)`,
      }}
    >
      {children}
    </div>
  );
};

export const Overlay: React.FC<OverlayProps> = ({timeline}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const timeSec = frame / fps;
  const scene = sceneAt(timeline.scenes, timeSec);
  const spectrum = useSongSpectrum(timeline.song);
  const glitch = sceneGlitch(timeline.scenes, timeSec);

  if (!scene) return <AbsoluteFill />;

  const motion = (layer: Parameters<typeof layerMotion>[2]) =>
    layerMotion(timeline.scenes, timeSec, layer, frame);

  const line = scene.layers.lyrics
    ? activeLine(timeline.lines, timeSec, timeline.holdSec)
    : null;
  const showStatus = scene.layers.status;
  const showEqualizer = scene.layers.equalizer;
  const statusMotion = motion("status");
  const equalizerMotion = motion("equalizer");
  const panelParts = [
    showStatus ? statusMotion : null,
    showEqualizer ? equalizerMotion : null,
  ].filter((item): item is LayerMotion => item !== null && item.visible);
  const panelMotion: LayerMotion =
    panelParts.length === 0
      ? {visible: false, opacity: 0, glitch: 0, jitterX: 0, jitterY: 0}
      : panelParts.reduce((current, item) =>
          item.glitch > current.glitch
            ? {...item, opacity: Math.max(item.opacity, current.opacity)}
            : {...current, opacity: Math.max(item.opacity, current.opacity)},
        );

  return (
    <AbsoluteFill>
      {glitch > 0.04 && (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 120 + ((frame * 53) % 760),
            height: 64,
            borderTop: `1px solid ${timeline.colors.cyan}`,
            borderBottom: `1px solid ${timeline.colors.cyan}`,
            opacity: 0.45 * glitch,
            transform: `translateX(${(frame % 2 === 0 ? 22 : -16) * glitch}px)`,
          }}
        />
      )}
      <Layer motion={motion("brackets")}>
        <Brackets color={timeline.colors.cyan} />
      </Layer>
      <Layer motion={motion("location")}>
        <LocationTag
          location={scene.location}
          colors={timeline.colors}
          fonts={timeline.fonts}
        />
      </Layer>
      <Layer motion={motion("rec")}>
        <RecTimecode
          offsetSec={timeline.timecodeOffsetSec}
          songStartSec={timeline.songStartSec}
          camera={scene.camera}
          colors={timeline.colors}
          fonts={timeline.fonts}
        />
      </Layer>
      {line && (
        <Layer motion={motion("lyrics")}>
          <Lyrics
            line={line}
            timeSec={timeSec}
            colors={timeline.colors}
            fonts={timeline.fonts}
          />
        </Layer>
      )}
      {(showStatus || showEqualizer) && (
        <Layer motion={statusMotion}>
          <StatusBlock
            lines={scene.status}
            showStatus={showStatus}
            showEqualizer={showEqualizer}
            spectrum={spectrum}
            colors={timeline.colors}
            fonts={timeline.fonts}
          />
        </Layer>
      )}
    </AbsoluteFill>
  );
};
