import {Composition} from "remotion";
import {Overlay, type OverlayProps} from "./Overlay";
import type {ResolvedTimeline} from "./lib/types";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Overlay"
      component={Overlay}
      durationInFrames={30}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{timeline: undefined as unknown as ResolvedTimeline}}
      calculateMetadata={({props}) => {
        if (!props.timeline) {
          throw new Error(
            "Missing timeline props. Run `npm run props` and render with --props=out/props.json.",
          );
        }
        if (
          props.timeline.fps !== 30 ||
          props.timeline.width !== 1920 ||
          props.timeline.height !== 1080
        ) {
          throw new Error(
            `Overlay kit only renders 1080p30. Got ${props.timeline.width}x${props.timeline.height} @ ${props.timeline.fps}fps.`,
          );
        }
        return {
          durationInFrames: props.timeline.durationInFrames,
          fps: 30,
          width: 1920,
          height: 1080,
          props,
        };
      }}
    />
  );
};

export type {OverlayProps};
