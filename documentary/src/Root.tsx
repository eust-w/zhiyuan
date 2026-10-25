import { Composition } from "remotion";
import { DocumentarySample } from "./Composition";

export const RemotionRoot = () => (
  <Composition
    id="DocumentarySample"
    component={DocumentarySample}
    durationInFrames={2340}
    fps={30}
    width={1920}
    height={1080}
  />
);
