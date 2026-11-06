"""Check the current design files and assemble a reproducible handoff ZIP.

Reads project deliverables only. Does not build CAD, compile, flash, power a
device, slice or contact a printer. A valid file inventory is not a bench test.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import struct
import shutil
import zipfile
from verify_mesh_features import verify as verify_mesh_features

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def canonical_values(value):
    # Replicator canonical JSON uses JSON numbers: 2.0 and 2 have one identity.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k:canonical_values(v) for k,v in value.items()}
    if isinstance(value, list):
        return [canonical_values(v) for v in value]
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_hash(path, expected):
    require(path.is_file(), "Missing file: " + str(path))
    require(digest(path) == expected, "Changed file: " + str(path))


def mesh_volume(path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    require(len(data) == 84 + 50 * count, "Invalid binary STL")
    volume = 0.0
    for i in range(count):
        v = struct.unpack_from("<12fH", data, 84 + 50 * i)
        ax, ay, az, bx, by, bz, cx, cy, cz = v[3:12]
        volume += (ax * (by * cz - bz * cy)
                   + ay * (bz * cx - bx * cz)
                   + az * (bx * cy - by * cx)) / 6
    return volume


def main(check_only=False):
    models = read("product/production/model-manifest.json")
    binding = models["current_binding"]
    receipt = read(binding["receipt"])
    geometry = read("product/production/design-verification.json")
    require(binding["revision"] == receipt["revision"] == geometry["revision"],
            "Model and verification revisions differ")
    require(binding["export_id"] == receipt["exportId"] == geometry["export_id"],
            "Export identity mismatch")
    step = next(a for a in receipt["artifacts"] if a["role"] == "model/step")
    verify_hash(ROOT / step["path"], step["sha256"])
    require(step["sha256"] == binding["step_sha256"], "STEP mismatch")
    design = read("design/enclosure/source/design.json")
    for target in design["targets"]:
        for cell in target["cells"]:
            verify_hash(ROOT / cell["path"],
                        receipt["sourceHashes"][target["id"] + "/" + cell["id"]])
    for asset_hash in receipt["assetHashes"].values():
        # The managed design retains each immutable asset under its hash.
        matches = list((ROOT / "design/enclosure/source/assets").glob(asset_hash + ".*"))
        require(bool(matches), "Missing CAD asset: " + asset_hash)
        require(any(digest(p) == asset_hash for p in matches), "CAD asset changed")
    interference = receipt["interference"]["counts"]
    require(all(interference[k] == 0 for k in ("undeclared", "over_budget", "undetermined")),
            "Unresolved CAD overlap")
    require(interference["interference"] == 1, "Unexpected overlap inventory")
    overlap = receipt["interference"]["overlaps"][0]
    require({overlap['a'], overlap['b']} == {'matrix_pcb', 'top'}
            and overlap['verdict'] == 'declared'
            and overlap['maxDepthMm'] <= overlap['budgetMm'],
            "Unexpected matrix/plate fit")
    state = receipt["stateManifest"]
    verify_hash(ROOT / state["brief"]["path"], state["brief"]["sha256"])
    requirement = state["requirement"]
    # The CAD record stores a derived contract identity, not the raw JSON hash.
    # The Workbench validates that identity; inventory raw bytes separately.
    contract = read(requirement["artifactContractPath"])
    require(any(d["design_id"] == receipt["designId"]
                and "step" in d["required_formats"]
                for d in contract["cad"]["designs"]),
            "Current contract does not require this STEP design")
    for evidence in requirement["inputs"]:
        verify_hash(ROOT / evidence["path"], evidence["sha256"])
    reuse = read("product/production/mesh-reuse-evidence.json")
    verify_hash(ROOT / reuse["original_receipt_copy"], reuse["original_receipt_sha256"])
    verify_hash(ROOT / reuse["original_mesh_manifest"], reuse["original_mesh_manifest_sha256"])
    original_receipt = read(reuse["original_receipt_copy"])
    original_geometry = read(reuse["original_geometry_record"])
    require(original_geometry['revision'] == original_receipt['revision'],
            'Historical geometry provenance mismatch')
    keycap_geometry = read('product/keycap-usability-verification.json')
    require(keycap_geometry['revision'] == receipt['revision']
            and keycap_geometry['export_id'] == receipt['exportId'], 'Keycap checks use another handoff')
    caps = keycap_geometry['measured_geometry']['caps']
    require(len(caps) == 20 and all(c['valid'] and c['solids']==1
            and c['added_outside_blank_mm3']==0 and c['removed_min_z_mm']>=6.6499 for c in caps),
            'Current cap geometry checks failed')
    require(verify_mesh_features() == read('product/production/mesh-feature-checks.json'),
            'Actual STL feature checks differ from recorded results')

    expected = {"base", "top", "rear_foot_left", "rear_foot_right",
                "hinge_axle_left", "hinge_axle_right",
                "hinge_cap_left", "hinge_cap_right"}
    expected.update("key_%02d" % i for i in range(1, 21))
    require({m["object_id"] for m in models["meshes"]} == expected
            and len(models["meshes"]) == 28, "Incomplete printed parts")
    transforms = {o['id']: o['transform'] for o in design['objects']}
    for mesh in models["meshes"]:
        name = mesh['object_id']
        require(mesh['shape_sha256'] == receipt['shapeHashes'][name]
                and mesh['object_transform'] == transforms[name], 'Mesh shape/placement binding differs: '+name)
        if mesh['derivation']['method'] == 'reuse_unchanged_shape':
            require(not name.startswith('key_') and receipt['shapeHashes'][name] == original_receipt['shapeHashes'][name],
                    'Reused mesh geometry changed: ' + name)
            require(transforms[name] == reuse['original_printed_transforms'][name],
                    'Reused mesh placement changed: ' + name)
        else:
            require(name.startswith('key_') and mesh['derivation']['method'] == 'step_tessellation'
                    and mesh['derivation']['receipt'] == binding['receipt']
                    and mesh['derivation']['step_sha256'] == step['sha256'], 'Keycap STL uses an older STEP: '+name)
        path = ROOT / mesh["file"]
        verify_hash(path, mesh["sha256"])
        require(path.stat().st_size == mesh["bytes"], "Mesh size mismatch")
        require(mesh["non_two_incidence_edges_at_1e5mm"] == 0
                and mesh["collapsed_triangles_at_1e5mm"] == 0,
                "Mesh edge/triangle defect")
        require(abs(mesh["min_z_mm"]) < 1e-5 and mesh["units"] == "mm",
                "Mesh coordinate mismatch")
        require(abs(mesh_volume(path) - mesh["volume_mm3"]) <
                max(0.2, mesh["volume_mm3"] * 0.01),
                "Mesh orientation or volume differs from STEP: " + mesh["object_id"])
    require({p.stem for p in (OUT / "models").glob("*.stl")} == expected,
            "Unexpected STL files in production directory")
    with (OUT / "print-plan.csv").open(encoding="utf-8-sig", newline="") as stream:
        plan = list(csv.DictReader(stream))
    require({r["object_id"] for r in plan} == expected and len(plan) == 28,
            "Print plan does not match models")

    bom = read("product/bom.json")
    values = {k:v['value'] for k,v in read('product/requirements.json')['requirements'].items()}
    requirements_digest = hashlib.sha256(json.dumps(canonical_values(values),sort_keys=True,ensure_ascii=False,
                                separators=(',',':')).encode()).hexdigest()
    require(bom['requirements_digest'] == requirements_digest, 'BOM requirement values changed')
    items = {i["id"]: i for i in bom["items"]}
    require(len(items) == 28 and items["switches"]["quantity"] == 20
            and items["keycaps"]["quantity"] == 20, "Incorrect production quantities")
    require(items['matrix_pcb_board']['quantity'] == 1
            and items['signal_wire']['quantity'] == 10
            and items['lcd_signal_wire']['quantity'] == 5
            and items['matrix_diodes']['mpn'] == '1N4148-TAP'
            and items['column_pullups']['mpn'] == '0805W8F1002T5E',
            'Matrix PCB BOM identity/quantity mismatch')
    require(not ({"keycap_fit_samples", "switch_fit_coupon"} & items.keys()),
            "Historical coupons included in production BOM")
    with (ROOT / "product/bom.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_items = {i["id"]: i for i in csv.DictReader(stream)}
    require(csv_items.keys() == items.keys(), "BOM CSV differs from JSON")
    for key, item in items.items():
        require(str(item["quantity"]) == csv_items[key]["quantity"],
                "CSV quantity mismatch: " + key)
        require(item['name'] == csv_items[key]['name'], 'CSV identity mismatch: '+key)
    selection = read('product/component-selection.json')
    require(selection['selected_components'] == bom['items'], 'Selection differs from production BOM')

    firmware_dir = ROOT / "design/firmware/release/v0.2.0"
    firmware = read("design/firmware/release/v0.2.0/verification.json")
    for path, sha in firmware["source_hashes"].items():
        verify_hash(ROOT / path, sha)
    for name, artifact in firmware["artifacts"].items():
        verify_hash(firmware_dir / name, artifact["sha256"])
        require((firmware_dir / name).stat().st_size == artifact["bytes"],
                "Firmware size mismatch")
    require(all(c["exit_code"] == 0 for c in firmware["commands"]),
            "Firmware build or test failure")
    require(firmware["host_test_counts"] == [93, 47270, 2500, 3023],
            "Firmware test inventory mismatch")
    require(not firmware["flashed"] and not firmware["hardware_tested"],
            "Incorrect hardware-test declaration")
    pcb_id = read('manufacturing/matrix/release-index.json')['releases'][-1]['releaseId']
    pcb_dir = ROOT / 'manufacturing/matrix/releases' / pcb_id
    pcb_release = json.loads((pcb_dir / 'release-manifest.json').read_text())
    require(all(s['status'] == 'ready' for s in pcb_release['sections']),
            'PCB release has blocked deliverables')
    for artifact in pcb_release['package']:
        verify_hash(pcb_dir / 'package' / artifact['path'], artifact['sha256'])
    pcb_geometry = read('product/matrix-pcb-verification.json')
    compatible = pcb_geometry['current_assembly_binding']
    require(pcb_geometry['pcb_release_id'] == pcb_id
            and compatible['cad_revision'] == receipt['revision']
            and compatible['cad_export_id'] == receipt['exportId'],
            'PCB/CAD evidence mismatch')
    baseline = read(compatible['baseline_receipt'])
    require(baseline['revision'] == pcb_geometry['cad_revision'], 'PCB evidence baseline changed')
    for name in compatible['unchanged_objects']:
        require(receipt['shapeHashes'][name] == baseline['shapeHashes'][name],
                'PCB/case object differs from retained inspection: '+name)
    # Imported source bytes must be the released assembly, not a lookalike.
    pcb_step = next(a for a in pcb_release['package'] if a['path'] == 'assembly.step')
    require(pcb_step['sha256'] in receipt['assetHashes'].values(), 'CAD PCB STEP binding mismatch')
    drawing = read('product/matrix-assembly-diagrams/source-checks.json')
    require(drawing['pcb_release'] == pcb_id, 'Assembly drawings use another PCB release')
    for path, sha in drawing['source_hashes'].items(): verify_hash(ROOT/path, sha)
    with (ROOT/'product/matrix-assembly-diagrams/soldering-map.csv').open(encoding='utf-8-sig',newline='') as f:
        wire_map = list(csv.DictReader(f))
    require(len(wire_map) == 19, 'Expected 15 wires and 4 NC terminals')
    with (ROOT/'product/matrix-assembly-diagrams/unpowered-check-record.csv').open(encoding='utf-8-sig',newline='') as f:
        physical_checks = list(csv.DictReader(f))
    require(len(physical_checks) == 59 and all(r['实测']=='' and r['结果']=='待测' for r in physical_checks),
            'Empty physical-test template must remain pending')
    shopping = read('product/purchasing/matrix/hand-assembly-shopping.json')
    require(shopping['source_bom_sha256'] == digest(ROOT/'product/bom.json')
            and shopping['source_requirements_sha256'] == digest(ROOT/'product/requirements.json')
            and shopping['pcb_release_id'] == pcb_id, 'Purchasing sources changed')
    covered = {i for row in shopping['items'] for i in row['bom_item_ids'].split(',')}
    require(covered == items.keys() and len(shopping['items']) == 27, 'Purchasing coverage mismatch')
    with (ROOT/'product/purchasing/matrix/hand-assembly-shopping.csv').open(encoding='utf-8-sig',newline='') as f:
        shopping_csv = list(csv.DictReader(f))
    require(len(shopping_csv) == len(shopping['items']), 'Shopping CSV inventory mismatch')
    for a,b in zip(shopping_csv,shopping['items']):
        require(all(str(b[k]) == v for k,v in a.items()), 'Shopping CSV differs from JSON')
    procurement = read('product/purchasing/matrix/procurement-record.json')
    for entry in procurement['files']:
        verify_hash(ROOT/'product/purchasing/matrix'/entry['name'], entry['sha256'])
    # The bare-board ZIP is emitted by pcb.export, never synthesized here.
    fabrication_source = ROOT/'.work/pcb/matrix/release/packages/fabrication.zip'
    fabrication_copy = OUT/'matrix-fabrication.zip'
    if not fabrication_copy.exists() and not check_only:
        require(fabrication_source.is_file(), 'Re-emit fabrication section before packaging')
        shutil.copyfile(fabrication_source, fabrication_copy)
    fab_files = next(s['files'] for s in pcb_release['sections'] if s['id']=='fabrication')
    order = read('product/purchasing/matrix/pcb-order-parameters.json')
    require(order['pcb_release_id'] == pcb_id, 'Order parameters use another PCB')
    require(order['fabrication_package']['path'] == 'product/production/matrix-fabrication.zip',
            'Fabrication purchasing path must survive outside cache')
    verify_hash(fabrication_copy, order['fabrication_package']['sha256'])
    with zipfile.ZipFile(fabrication_copy) as fab:
        require(fab.testzip() is None, 'Fabrication ZIP CRC failure')
        expected_fab = {'manufacturing/'+p for p in fab_files}
        actual_fab = {p for p in fab.namelist() if p.startswith('manufacturing/')}
        require(expected_fab == actual_fab, 'Fabrication ZIP file inventory mismatch')
        for name in fab_files:
            require(hashlib.sha256(fab.read('manufacturing/'+name)).hexdigest() ==
                    digest(pcb_dir/'package'/name), 'Fabrication bytes differ from release')

    selected = set()

    def add(path):
        path = ROOT / path
        require(path.is_file(), "Missing delivery input: " + str(path))
        selected.add(path)

    def tree(path):
        for file in (ROOT / path).rglob("*"):
            if (file.is_file() and "__pycache__" not in file.parts
                    and file.name != ".DS_Store" and file.suffix != ".pyc"):
                selected.add(file)

    for path in ("README.md", "project.manifest.json", "design/assembly.json",
                 "design/enclosure/README.md", "product/README.md",
                 "product/requirements.json", "product/constraints.json",
                 "product/contract.json", "product/bom.json", "product/bom.csv",
                 "product/component-selection.json",
                 "product/bring-up-checklist.md",
                 "product/lcd-upgrade.md",
                 "product/calckey-firmware-v0.2.0.zip",
                 "product/production/README.md",
                 "product/production/generate_models.py",
                 "product/production/verify_mesh_features.py",
                 "product/production/render_mesh_preview.py",
                 "product/production/sync_delivery_records.py",
                 "product/production/mesh-feature-checks.json",
                 "product/production/build_delivery.py",
                 "product/production/mesh-reuse-evidence.json",
                 "product/production/matrix-fabrication.zip",
                 "product/production/model-manifest.json",
                 "product/production/design-verification.json",
                 "product/production/print-plan.csv",
                 "product/matrix-pcb-verification.json",
                 "product/keycap-usability-verification.json",
                 "manufacturing/matrix/release-index.json",
                 binding["receipt"], step["path"]):
        add(path)
    for path in ("design/enclosure/source", "product/production/models",
                 "product/matrix-assembly-diagrams", "product/purchasing/matrix",
                 "product/production/history", "design/matrix",
                 "manufacturing/matrix/releases/"+pcb_id,
                 "design/firmware/source",
                 "design/firmware/tests", "design/firmware/release/v0.2.0"):
        tree(path)
    for path in ("README.md", "bootstrap.py", "build.py", "check_wiring.py",
                 "dependencies.lock.json"):
        add("design/firmware/" + path)
    for path in ("gdm0103-specification.pdf", "ht1621-v340.pdf",
                 "rp-008299-ds.pdf", "vishay-1n4148.pdf",
                 "eda-keypad-reference.md",
                 "gateron-ks9/KS-9 Switch KS-9H10B045NN-X14-FB.stp"):
        add("product/references/" + path)
    # The exact switch STEP is already present in the managed CAD assets.
    files = [{"file": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
              "sha256": digest(p)} for p in sorted(selected)]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "revision": receipt["revision"], "export_id": receipt["exportId"],
        "source_receipt": binding["receipt"],
        "pcb_release_id": pcb_id, "pcb_build_id": pcb_release['buildId'],
        "inventory_checks": {"printed_parts": 28, "new_keycap_meshes":20, "unchanged_other_meshes":8, "bom_rows": 28,
                             "shopping_rows": 27, "matrix_leads": 10, "lcd_leads": 5,
                             "wire_installed_m": 2.25, "wire_purchase_default_m": 3,
                             "wiring_pdf_pages": 4, "unpowered_record_rows": 59,
                             "fabrication_files": len(fab_files),
                             "firmware_version": "0.2.0",
                             "firmware_test_counts": firmware["host_test_counts"]},
        "limitations": geometry["limitations"],
        "physical_print_trial_skipped_by_user": True,
        "flashed": False, "powered": False, "printer_started": False, "hardware_tested": False,
        "files": files,
        "manifest_self_hash_excluded": True
    }
    manifest_path = OUT / "package-manifest.json"
    target = ROOT / "product/calckey-complete-design.zip"
    if check_only:
        existing = read('product/production/package-manifest.json')
        require(existing['files'] == files, 'Published package manifest is stale')
        require(existing['export_id'] == receipt['exportId']
                and existing['pcb_release_id'] == pcb_id, 'Package binding stale')
        expected_files = {str(p.relative_to(ROOT)) for p in selected} | {'product/production/package-manifest.json'}
        with zipfile.ZipFile(target) as archive:
            require(archive.testzip() is None, 'Complete ZIP CRC failure')
            require(set(archive.namelist()) == expected_files, 'Complete ZIP inventory mismatch')
            for name in expected_files:
                require(hashlib.sha256(archive.read(name)).hexdigest() == digest(ROOT/name),
                        'ZIP bytes differ from current delivery: '+name)
        print('PASS independent ZIP inventory, all file hashes and CRC; current CAD/PCB/firmware bindings.')
        print('No device contact performed.')
        return
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    selected.add(manifest_path)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(selected):
            archive.write(path, str(path.relative_to(ROOT)))
    with zipfile.ZipFile(target) as archive:
        require(archive.testzip() is None, "ZIP CRC failure")
        require(set(archive.namelist()) ==
                {str(p.relative_to(ROOT)) for p in selected}, "ZIP inventory mismatch")
    print("PASS current STEP and PCB release, 28 closed STL meshes, 28 BOM rows, "
          "27 shopping rows, 15 wires, 4-page PCB wiring, 59 pending checks and v0.2.0 firmware hashes")
    print("ZIP entries:", len(selected), "bytes:", target.stat().st_size,
          "sha256:", digest(target))
    print("No flashing, printing, slicing or device contact performed.")


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    main(ap.parse_args().check_only)
