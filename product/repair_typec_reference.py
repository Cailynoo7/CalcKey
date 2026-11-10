"""Repair the incoming Waveshare reference, not the enclosure CAD source.

Only the previously isolated USB shell leaf is converted to equivalent NURBS.
All validation happens in memory before --write permits a derived reference.
The enclosure itself is imported/built/published by the CAD Workbench only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from build123d import Compound, Solid, Location
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message, Message_Gravity
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'product/references/type-c-controllers/waveshare-rp2350-plus.step'
OUTPUT = SOURCE.with_name('waveshare-rp2350-plus-nurbs-repaired.step')
SOURCE_HASH = '650977cc5a1bbeaab4eabdefd3f547642a1c34a5a8e5cbf49ac6f8b575c979f4'


def roundtrip(shape):
    writer = STEPControl_Writer()
    assert writer.Transfer(shape.wrapped, STEPControl_AsIs) == IFSelect_RetDone
    stream = io.BytesIO()
    assert writer.WriteStream(stream) == IFSelect_RetDone
    stream.seek(0)
    reader = STEPControl_Reader()
    assert reader.ReadStream('reference-memory-check', stream) == IFSelect_RetDone
    assert reader.TransferRoots()
    return Compound(reader.OneShape())


def measure(shape):
    volume, area = GProp_GProps(), GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, volume, 1e-10, True, False)
    BRepGProp.SurfaceProperties_s(shape.wrapped, area, 1e-10, False)
    return {'volume_mm3': volume.Mass(), 'area_mm2': area.Mass()}


def diff_volume(shape):
    if shape is None:
        return 0.0
    return sum(abs(s.volume) for s in shape.solids())


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--write', action='store_true')
    opts = args.parse_args()
    for printer in Message.DefaultMessenger_s().Printers():
        printer.SetTraceLevel(Message_Gravity.Message_Fail)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_HASH
    doc = TDocStd_Document(TCollection_ExtendedString('MDTV-XCAF'))
    reader = STEPCAFControl_Reader()
    assert reader.ReadFile(str(SOURCE)) == IFSelect_RetDone
    assert reader.Transfer(doc)
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    tool.GetFreeShapes(roots)
    assert roots.Length() == 1
    original = Compound(tool.GetShape_s(roots.Value(1)))
    original_solids = list(original.solids())
    print('Original invalid solids:', [i for i,s in enumerate(original_solids) if not s.is_valid], flush=True)
    # Match the measured native-coordinate USB solid, never rely on its index.
    expected_min = (6.3200468666, 44.9619288762, -0.6104783362)
    expected_max = (14.6600469132, 52.0119174132, 2.9495217840)
    matches = [s for s in original_solids if
               max(abs(a-b) for a,b in zip(s.bounding_box().min, expected_min)) < 1e-4
               and max(abs(a-b) for a,b in zip(s.bounding_box().max, expected_max)) < 1e-4]
    assert len(matches) == 1, ('USB leaf match count', len(matches))
    target = matches[0]
    labels = TDF_LabelSequence()
    tool.GetShapes(labels)
    parts = []
    for i in range(1, labels.Length()+1):
        label = labels.Value(i)
        if not tool.IsSimpleShape_s(label):
            continue
        shape = tool.GetShape_s(label)
        if shape.IsPartner(target.wrapped):
            parts.append((label, shape))
    if not parts:
        label = tool.FindShape(target.wrapped, True)
        assert not label.IsNull(), 'No XCAF label for the USB leaf'
        if tool.IsReference_s(label):
            referred = TDF_Label()
            assert tool.GetReferredShape_s(label, referred)
            label = referred
        parts = [(label, tool.GetShape_s(label))]
    assert len(parts) == 1, ('USB XCAF leaf match count', len(parts))
    label, leaf = parts[0]
    print('Target label simple/reference:', tool.IsSimpleShape_s(label), tool.IsReference_s(label), 'leaf solids', len(Compound(leaf).solids()), flush=True)
    # Heal/convert after the complete factory instance transformation, just as
    # the validated Workbench object sees it; local-only conversion is unstable.
    source_leaf = target.fix()
    assert source_leaf.is_valid
    converted = Solid(BRepBuilderAPI_NurbsConvert(source_leaf.wrapped, True).Shape())
    assert converted.is_valid
    before, after = measure(source_leaf), measure(converted)
    assert abs(before['volume_mm3']-after['volume_mm3']) < 1e-5, (before, after)
    assert abs(before['area_mm2']-after['area_mm2']) < 1e-5, (before, after)
    converted_local = converted.located(Location())
    tool.SetShape(label, converted_local.wrapped)
    tool.UpdateAssemblies()
    repaired = Compound(tool.GetShape_s(roots.Value(1)))
    print('Repaired invalid solids:', [i for i,s in enumerate(repaired.solids()) if not s.is_valid], 'count', len(repaired.solids()), flush=True)
    assert repaired.is_valid and len(repaired.solids()) == len(original_solids)
    unaffected = sum(1 for a,b in zip(original_solids, repaired.solids())
                     if not a.wrapped.IsPartner(target.wrapped) and a.wrapped.IsSame(b.wrapped))
    assert unaffected == len(original_solids)-1, unaffected
    first, second = roundtrip(repaired), None
    assert first.is_valid
    second = roundtrip(first)
    assert second.is_valid and len(second.solids()) == len(original_solids)
    bound_delta = max(abs(a-b) for before_bound, after_bound in
                      [(original.bounding_box().min, second.bounding_box().min),
                       (original.bounding_box().max, second.bounding_box().max)]
                      for a,b in zip(before_bound, after_bound))
    assert bound_delta < 1e-6, bound_delta
    lost, gained = diff_volume(source_leaf.cut(converted)), diff_volume(converted.cut(source_leaf))
    assert lost < 1e-6 and gained < 1e-6, (lost, gained)
    result = {'method': 'Only USB shell leaf: fix topology then exact analytic-to-NURBS conversion; retain XCAF names/colors/assembly labels',
              'source_sha256': SOURCE_HASH, 'source': str(SOURCE.relative_to(ROOT)),
              'source_leaf_high_precision': before, 'repaired_leaf_high_precision': after,
              'source_minus_repaired_mm3': lost, 'repaired_minus_source_mm3': gained,
              'maximum_board_bbox_coordinate_delta_mm': bound_delta,
              'solids': len(original_solids), 'roundtrip_valid': [True, True],
              'unchanged_other_solids': unaffected,
              'cad_source_replayed': False, 'written': False}
    if opts.write:
        writer = STEPCAFControl_Writer()
        writer.SetColorMode(True)
        writer.SetNameMode(True)
        writer.SetLayerMode(True)
        assert writer.Transfer(doc)
        stream = io.BytesIO()
        assert writer.Writer().WriteStream(stream) == IFSelect_RetDone
        content = stream.getvalue()
        check = STEPControl_Reader()
        assert check.ReadStream('derived-reference-file-check', io.BytesIO(content)) == IFSelect_RetDone
        assert check.TransferRoots()
        assert Compound(check.OneShape()).is_valid
        OUTPUT.write_bytes(content)
        result.update(written=True, output=str(OUTPUT.relative_to(ROOT)), output_sha256=hashlib.sha256(content).hexdigest())
        (ROOT / 'product/type-c-reference-repair.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
