import pcbConfig from "../pcb.config.json";

const mm = (value: number) => `${value}mm`;
const pcbRules = pcbConfig;

export const silkscreenRules = {
  minTextHeightMm: 1,
  minLineWidthMm: 0.15,
  minPadClearanceMm: 0.15,
  sourceTextFontSizeMm: 1.5,
} as const;

export function silkscreenTextProps() {
  return { fontSize: mm(silkscreenRules.sourceTextFontSizeMm) };
}

export function silkscreenGraphicProps() {
  return { strokeWidth: mm(silkscreenRules.minLineWidthMm) };
}

export type PcbNetClass = keyof typeof pcbRules.netClasses;
export type PcbNetRule = {
  class: PcbNetClass;
  nominalWidthMm?: number;
  minimumWidthMm?: number;
  clearanceMm?: number;
  rationale?: string;
  referencePlaneNet?: string;
  escape?: {
    widthMm: number;
    clearanceMm: number;
    maxLengthMm: number;
    componentRefs: string[];
    rationale: string;
  };
};

const netRules = pcbRules.nets as Record<string, PcbNetRule>;

export function ruleForNet(netName: string): PcbNetRule {
  const rule = netRules[netName];
  if (!rule) throw new Error(`Unclassified PCB net: ${netName}`);
  return rule;
}

export function boardPropsFromRules() {
  const manufacturing = pcbRules.manufacturing;
  const absoluteClearance = manufacturing.absoluteMinimumCopperClearanceMm;
  return {
    routingDisabled: true,
    // Layer count reaches the board here and nowhere else: tscircuit turns it
    // into pcb_board.num_layers, which is what gives the generated KiCad file
    // its layer table and its vias the right layer span.
    layers: manufacturing.layers,
    thickness: mm(manufacturing.finishedThicknessMm),
    defaultTraceWidth: mm(manufacturing.defaultTraceWidthMm),
    nominalTraceWidth: mm(manufacturing.defaultTraceWidthMm),
    minTraceWidth: mm(
      Math.min(
        manufacturing.absoluteMinimumTraceWidthMm,
        ...Object.values(pcbRules.netClasses).map((rule) => rule.minimumWidthMm),
        ...Object.values(netRules).flatMap((rule) => [
          rule.minimumWidthMm ?? pcbRules.netClasses[rule.class].minimumWidthMm,
          ...(rule.escape ? [rule.escape.widthMm] : []),
        ]),
      ),
    ),
    minTraceToPadEdgeClearance: mm(absoluteClearance),
    minPadEdgeToPadEdgeClearance: mm(absoluteClearance),
    minViaEdgeToPadEdgeClearance: mm(absoluteClearance),
    minViaHoleEdgeToViaHoleEdgeClearance: mm(absoluteClearance),
    minPlatedHoleDrillEdgeToDrillEdgeClearance: mm(absoluteClearance),
    minBoardEdgeClearance: mm(manufacturing.copperToBoardEdgeMm),
    minViaPadDiameter: mm(manufacturing.via.diameterMm),
    minViaHoleDiameter: mm(manufacturing.via.drillMm),
    pcbStyle: {
      viaPadDiameter: mm(manufacturing.via.diameterMm),
      viaHoleDiameter: mm(manufacturing.via.drillMm),
      silkscreenFontSize: mm(silkscreenRules.sourceTextFontSizeMm),
    },
  };
}

export function netPropsFor(netName: string) {
  const rule = ruleForNet(netName);
  const classRule = pcbRules.netClasses[rule.class];
  return {
    nominalTraceWidth: mm(rule.nominalWidthMm ?? classRule.nominalWidthMm),
    isPowerNet: rule.class === "power" || rule.class === "high_current",
    isGroundNet: rule.class === "ground",
  };
}

export function tracePropsFor(netName: string, options?: { useEscape?: boolean }) {
  const rule = ruleForNet(netName);
  const classRule = pcbRules.netClasses[rule.class];
  const width = options?.useEscape
    ? rule.escape?.widthMm
    : rule.nominalWidthMm ?? classRule.nominalWidthMm;
  if (width === undefined) throw new Error(`No declared escape rule for ${netName}`);
  return { width: mm(width) };
}

export function groundPourPropsFromRules() {
  if (!pcbRules.copperPours.enabled) return [];
  return Object.entries(netRules)
    .filter(([, rule]) => rule.class === "ground")
    .flatMap(([netName]) =>
      pcbRules.copperPours.groundLayers.map((layer) => ({
        name: `${netName}_POUR_${layer.toUpperCase()}`,
        connectsTo: `net.${netName}`,
        layer,
        clearance: mm(pcbRules.copperPours.clearanceMm),
        padMargin: mm(pcbRules.copperPours.padMarginMm),
        traceMargin: mm(pcbRules.copperPours.traceMarginMm),
        boardEdgeMargin: mm(pcbRules.copperPours.boardEdgeMarginMm),
        cutoutMargin: mm(pcbRules.copperPours.cutoutMarginMm),
        removeIslands: pcbRules.copperPours.removeIslands,
      })),
    );
}

export function keepoutPropsFromRules() {
  return pcbRules.keepouts.map((keepout) =>
    keepout.shape === "circle"
      ? {
          key: keepout.name,
          shape: "circle" as const,
          pcbX: keepout.xMm,
          pcbY: keepout.yMm,
          radius: mm(keepout.radiusMm),
          layers: [...keepout.layers],
          allowPlacements: true,
        }
      : {
          key: keepout.name,
          shape: "rect" as const,
          pcbX: keepout.xMm,
          pcbY: keepout.yMm,
          pcbRotation: keepout.rotationDeg ?? 0,
          width: mm(keepout.widthMm),
          height: mm(keepout.heightMm),
          layers: [...keepout.layers],
          allowPlacements: true,
        },
  );
}

export { pcbRules };
