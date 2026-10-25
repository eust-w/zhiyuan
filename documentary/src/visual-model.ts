export type TrajectoryState = {
  step: number;
  xy: number[];
  headingRad: number;
  distanceM: number;
  actionId: number | null;
  blocked: boolean;
};

export type Episode = {
  id: string;
  steps: number;
  targetXY: number[];
  trajectory: TrajectoryState[];
};

export const stateAtStep = (trajectory: TrajectoryState[], step: number) => {
  if (trajectory.length === 0) throw new Error("empty trajectory");
  let state = trajectory[0];
  for (const candidate of trajectory) {
    if (candidate.step > step) break;
    state = candidate;
  }
  return state;
};

// Both panels advance on the same action-step clock, not on wall-clock time.
export const stepForFrame = (
  frame: number,
  fps: number,
  durationSec: number,
  endStep: number,
) =>
  Math.min(
    endStep,
    Math.floor(
      (Math.max(0, frame) / Math.max(1, durationSec * fps - 1)) * endStep,
    ),
  );

export const pairedProjection = (
  episodes: Episode[],
  width: number,
  height: number,
  padding: number,
) => {
  const coordinates = episodes.flatMap((episode) => [
    episode.targetXY,
    ...episode.trajectory.map((state) => state.xy),
  ]);
  if (coordinates.length === 0) throw new Error("empty projection");
  const xs = coordinates.map((xy) => xy[0]);
  const ys = coordinates.map((xy) => xy[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const scale = Math.min(
    (width - padding * 2) / Math.max(1, maxX - minX),
    (height - padding * 2) / Math.max(1, maxY - minY),
  );
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  return {
    point: (xy: number[]) => [
      width / 2 + (xy[0] - centerX) * scale,
      height / 2 - (xy[1] - centerY) * scale,
    ],
    radius: (meters: number) => meters * scale,
  };
};
