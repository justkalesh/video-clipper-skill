import React from "react";
import { Composition } from "remotion";
import { Clip, DEMO } from "./Clip";
import type { ClipProps } from "./Clip";

// One composition; every clip is rendered by passing its data file with --props.
export const Root: React.FC = () => (
  <Composition
    id="Clip"
    component={Clip}
    defaultProps={{ data: DEMO } as ClipProps}
    durationInFrames={DEMO.durationInFrames}
    fps={DEMO.fps}
    width={DEMO.width}
    height={DEMO.height}
    calculateMetadata={({ props }) => ({
      durationInFrames: props.data.durationInFrames,
      fps: props.data.fps,
      width: props.data.width,
      height: props.data.height,
    })}
  />
);
