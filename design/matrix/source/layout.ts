export const board = {
  width: "73mm",
  height: "96mm",
  enclosureY: -14,
  thicknessMm: 1.6,
  topLocalZMm: 16,
};

export const primarySide = "top";
export const serviceSide = "bottom";
export const pitchMm = 19.05;
export const keys = Array.from({ length: 20 }, (_, i) => ({
  index: i + 1, row: Math.floor(i / 4), col: i % 4,
  x: ((i % 4) - 1.5) * pitchMm,
  y: 24.6 - Math.floor(i / 4) * pitchMm - board.enclosureY,
}));
// KiCad Plate footprint: centre at native (-2.54, -5.08) in Y-up.
// +90 degrees maps its terminal positions to the measured KS-9 orientation.
export const switchRotationDeg = 90;
export const wireNets = ["ROW0","ROW1","ROW2","ROW3","ROW4",
  "COL0","COL1","COL2","COL3","V3V3"];
export const wirePoints = wireNets.map((net, i) => ({
  name: "J" + (i + 1), net, x: (i - 4.5) * 6, y: -60.5 - board.enclosureY,
}));

export const placement = {
  origin: { x: 0, y: 0 },
};

export const OPENING_ROTATION_DEG = {
  up: 0,
  left: 90,
  down: 180,
  right: 270,
} as const;

export type OpeningDirection = keyof typeof OPENING_ROTATION_DEG;

/** Rotation (deg) to apply when a footprint's native opening differs from the target opening. */
export function rotationForOpening(
  nativeOpening: OpeningDirection,
  targetOpening: OpeningDirection,
): number {
  return (
    (OPENING_ROTATION_DEG[targetOpening] - OPENING_ROTATION_DEG[nativeOpening] + 360) % 360
  );
}

export type XY = { x: number; y: number };
