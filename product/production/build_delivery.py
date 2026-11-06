"""Check the current design files and assemble a reproducible handoff ZIP.

Reads project deliverables only. Does not build CAD, compile, flash, power a
device, slice or contact a printer. A valid file inventory is not a bench test.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import struct
import zipfile

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


def main():
    models = read("product/production/model-manifest.json")
    receipt = read(models["source_receipt"])
    geometry = read("product/production/design-verification.json")
    require(models["revision"] == receipt["revision"] == geometry["revision"],
            "Model and verification revisions differ")
    require(geometry["geometry_evidence_revision"] == receipt["revision"],
            "Geometry checks refer to an older revision")
    require(models["export_id"] == receipt["exportId"], "Export identity mismatch")
    step = next(a for a in receipt["artifacts"] if a["role"] == "model/step")
    verify_hash(ROOT / step["path"], step["sha256"])
    require(step["sha256"] == models["source_step_sha256"], "STEP mismatch")
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
    require(interference["interference"] == 20, "Unexpected overlap inventory")
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
    require(len(geometry["measured_geometry"]["caps"]) == 20, "Missing cap checks")
    for cap in geometry["measured_geometry"]["caps"]:
        require(cap["valid"] and cap["solids"] == 1
                and cap["static_overlap_mm3"] == 0
                and cap["max_external_housing_overlap_mm3"] == 0,
                "Cap geometry check failed")

    expected = {"base", "top", "rear_foot_left", "rear_foot_right",
                "hinge_axle_left", "hinge_axle_right",
                "hinge_cap_left", "hinge_cap_right"}
    expected.update("key_%02d" % i for i in range(1, 21))
    require({m["object_id"] for m in models["meshes"]} == expected
            and len(models["meshes"]) == 28, "Incomplete printed parts")
    for mesh in models["meshes"]:
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
    items = {i["id"]: i for i in bom["items"]}
    require(len(items) == 26 and items["switches"]["quantity"] == 20
            and items["keycaps"]["quantity"] == 20, "Incorrect production quantities")
    require(not ({"keycap_fit_samples", "switch_fit_coupon"} & items.keys()),
            "Historical coupons included in production BOM")
    with (ROOT / "product/bom.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_items = {i["id"]: i for i in csv.DictReader(stream)}
    require(csv_items.keys() == items.keys(), "BOM CSV differs from JSON")
    for key, item in items.items():
        require(str(item["quantity"]) == csv_items[key]["quantity"],
                "CSV quantity mismatch: " + key)

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
    wiring_sha = digest(ROOT / "design/enclosure/source/wiring.json")
    drawing = read("product/diagrams/drawing-record.json")
    procedure = read("product/assembly/procedure-record.json")
    require(drawing["wiring_sha256"] == procedure["wiring_sha256"] == wiring_sha,
            "Drawing or procedure uses old wiring")
    for name, artifact in drawing["artifacts"].items():
        verify_hash(ROOT / "product/diagrams" / name, artifact["sha256"])
    for name, sha in procedure["files"].items():
        verify_hash(ROOT / "product/assembly" / name, sha)
    require(drawing["pages"] == 4 and procedure["pdf_pages"] == 9,
            "Incomplete electrical documents")

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
                 "product/production/README.md",
                 "product/production/generate_models.py",
                 "product/production/build_delivery.py",
                 "product/production/model-manifest.json",
                 "product/production/design-verification.json",
                 "product/production/print-plan.csv",
                 models["source_receipt"], step["path"]):
        add(path)
    for path in ("design/enclosure/source", "product/production/models",
                 "product/diagrams", "product/assembly", "design/firmware/source",
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
        "source_receipt": models["source_receipt"],
        "inventory_checks": {"printed_parts": 28, "bom_rows": 26,
                             "wiring_pdf_pages": 4, "procedure_pdf_pages": 9,
                             "firmware_version": "0.2.0",
                             "firmware_test_counts": firmware["host_test_counts"]},
        "limitations": geometry["limitations"],
        "physical_print_trial_skipped_by_user": True,
        "flashed": False, "printer_started": False, "hardware_tested": False,
        "files": files,
        "manifest_self_hash_excluded": True
    }
    manifest_path = OUT / "package-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    selected.add(manifest_path)
    target = ROOT / "product/calckey-complete-design.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(selected):
            archive.write(path, str(path.relative_to(ROOT)))
    with zipfile.ZipFile(target) as archive:
        require(archive.testzip() is None, "ZIP CRC failure")
        require(set(archive.namelist()) ==
                {str(p.relative_to(ROOT)) for p in selected}, "ZIP inventory mismatch")
    print("PASS current STEP, 28 closed STL meshes, 26 BOM rows, "
          "4-page wiring, 9-page procedure and v0.2.0 firmware hashes")
    print("ZIP entries:", len(selected), "bytes:", target.stat().st_size,
          "sha256:", digest(target))
    print("No flashing, printing, slicing or device contact performed.")


if __name__ == "__main__":
    main()
