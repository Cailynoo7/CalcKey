import {board, keys, wirePoints, primarySide, serviceSide, switchRotationDeg} from "./layout";
import {boardPropsFromRules, netPropsFor, pcbRules} from "./lib/replicator-pcb";

const SWITCH = "kicad:Button_Switch_Keyboard/SW_Cherry_MX_1.00u_Plate";
const DIODE = "kicad:Diode_THT/D_DO-35_SOD27_P7.62mm_Horizontal";
const RESISTOR = "kicad:Resistor_SMD/R_0805_2012Metric";
const WIREPAD = "kicad:Connector_Wire/SolderWirePad_1x01_SMD_2x4mm";

export default () => (
  <board width={board.width} height={board.height} thickness={board.thicknessMm}
    material="fr4" borderRadius="1mm" doubleSidedAssembly {...boardPropsFromRules()}>
    {Object.keys(pcbRules.nets).map(n => <net name={n} {...netPropsFor(n)} />)}
    {keys.map(k => (
      <>
        <chip name={"SW"+k.index} manufacturerPartNumber="KS-9H10B045NN-X14"
          footprint={SWITCH} layer={primarySide}
          pcbX={k.x-5.08} pcbY={k.y+2.54} pcbRotation={switchRotationDeg}
          pinLabels={{pin1:"A",pin2:"B"}} schSectionName={"Key "+k.index}
          connections={{A:"net.COL"+k.col, B:"net.KEY"+k.index}}
          cadModel={{
            stepUrl:"./source/models/ks9.step",
            modelOriginPosition:{x:49.9004975124378,y:-86.0696517412935,z:11.2},
            rotationOffset:{x:0,y:0,z:-90},
            // Imported footprint centre is pad-bounds centred, not shaft centred.
            // cadModel XY offset is in board axes; align native KS-9 centre column.
            positionOffset:{x:2.09,y:0.635,z:0},
            modelUnitToMmScale:1, modelBoardNormalDirection:"z+",
          }} />
        <diode name={"D"+k.index} manufacturerPartNumber="1N4148-TAP"
          footprint={DIODE} layer={serviceSide}
          pcbX={k.x+3.81} pcbY={k.y+7} pcbRotation={0}
          pinLabels={{pin1:"cathode",pin2:"anode"}}
          schSectionName={"Key "+k.index}
          connections={{anode:"net.KEY"+k.index,cathode:"net.ROW"+k.row}} />
      </>
    ))}
    {[0,1,2,3].map(c => (
      <resistor name={"R"+(c+1)} resistance="10k"
        manufacturerPartNumber="0805W8F1002T5E"
        footprint={RESISTOR} layer={serviceSide}
        pcbX={c%2===0 ? -2 : 2} pcbY={c<2 ? 44 : 46.3}
        schSectionName="Column pullups"
        connections={{pin1:"net.V3V3",pin2:"net.COL"+c}} />
    ))}
    {wirePoints.map(p => (
      <chip name={p.name} manufacturerPartNumber="26AWG-150mm-direct-solder-lead"
        footprint={WIREPAD} layer={serviceSide} pcbRotation={90}
        pcbX={p.x} pcbY={p.y} schSectionName={"Pico "+p.net}
        pinLabels={{pin1:p.net}} connections={{[p.net]:"net."+p.net}} />
    ))}
    <silkscreentext text="CalcKey MATRIX A" pcbX={0} pcbY={46.5} fontSize="1mm" />
  </board>
);
