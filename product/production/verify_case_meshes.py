"""Inspect real binary STL surfaces, connectivity and five tape passages."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from verify_mesh_features import triangles

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def topology(tris):
    parents = list(range(len(tris)))
    edges, owners, directions = Counter(), {}, Counter()
    collapsed = 0

    def find(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]
            x = parents[x]
        return x

    for i, tri in enumerate(tris):
        vertices = [tuple(round(c, 5) for c in v) for v in tri]
        if len(set(vertices)) < 3:
            collapsed += 1
        for j in range(3):
            a, b = vertices[j], vertices[(j+1) % 3]
            edge = tuple(sorted((a, b)))
            edges[edge] += 1
            directions[edge] += 1 if a < b else -1
            if edge in owners:
                parents[find(i)] = find(owners[edge])
            else:
                owners[edge] = i
    return {"triangles": len(tris), "collapsed_triangles_at_1e5mm": collapsed,
            "non_two_incidence_edges_at_1e5mm": sum(v != 2 for v in edges.values()),
            "inconsistent_edge_orientations": sum(v != 0 for v in directions.values()),
            "connected_surface_components": len({find(i) for i in range(len(tris))})}


def hits(tris, axis, point):
    u, v = [n for n in range(3) if n != axis]
    result = []
    for a, b, c in tris:
        d = (b[v]-c[v])*(a[u]-c[u]) + (c[u]-b[u])*(a[v]-c[v])
        if abs(d) < 1e-12:
            continue
        x = ((b[v]-c[v])*(point[u]-c[u]) + (c[u]-b[u])*(point[v]-c[v])) / d
        y = ((c[v]-a[v])*(point[u]-c[u]) + (a[u]-c[u])*(point[v]-c[v])) / d
        z = 1-x-y
        if min(x, y, z) >= -1e-8:
            result.append(x*a[axis] + y*b[axis] + z*c[axis])
    distinct = []
    for value in sorted(result):
        if not distinct or abs(value-distinct[-1]) > 1e-5:
            distinct.append(value)
    assert len(distinct) % 2 == 0, (axis, point, distinct)
    return distinct


def inside(tris, point):
    return sum(v < point[0] for v in hits(tris, 0, point)) % 2 == 1


def void_bounds(tris, axis, point):
    values = hits(tris, axis, point)
    assert sum(v < point[axis] for v in values) % 2 == 0, ("point in material", point)
    below = [x for x in values if x < point[axis]]
    above = [x for x in values if x > point[axis]]
    return (max(below) if below else -math.inf, min(above) if above else math.inf)


def to_print(row, x, y, z):
    rotation = row["local_print_rotation_deg"]
    assert rotation in ([0, 0, 0], [180, 0, 0])
    v = [x, y, z] if rotation == [0, 0, 0] else [x, -y, -z]
    return [a+b for a, b in zip(v, row["local_print_translation_mm"])]


def verify():
    model = json.loads((OUT / "model-manifest.json").read_text())
    previous = json.loads((OUT / "history/before-harness-model-manifest.json").read_text())
    old = {r["object_id"]: r for r in previous["meshes"]}
    current = {r["object_id"]: r for r in model["meshes"]}
    changed = sorted(n for n in current if current[n]["sha256"] != old[n]["sha256"])
    assert changed == ["base", "top"]
    report = {}
    centres = {"base": [(0, -29, 2.4), (0, 23, 2.4), (-26, 2, 2.4)],
               "top": [(-17, -55.7, 5.2), (17, -55.7, 5.2)]}
    for name in ("base", "top"):
        row = current[name]
        path = ROOT / row["file"]
        assert sha(path) == row["sha256"]
        tris = triangles(path)
        checks = topology(tris)
        assert checks["connected_surface_components"] == 1, (name, checks)
        assert all(checks[k] == 0 for k in ["collapsed_triangles_at_1e5mm",
                                          "non_two_incidence_edges_at_1e5mm", "inconsistent_edge_orientations"])
        vertices = [v for tri in tris for v in tri]
        low = [min(v[i] for v in vertices) for i in range(3)]
        high = [max(v[i] for v in vertices) for i in range(3)]
        size = [b-a for a, b in zip(low, high)]
        assert abs(low[2]) < 1e-4
        assert all(abs(a-b) < 0.03 for a, b in zip(size, row["bbox_mm"]))
        passages = []
        for x, y, z in centres[name]:
            centre = to_print(row, x+0.127, y+0.123, z+1.071)
            width = void_bounds(tris, 1, centre)
            height = void_bounds(tris, 2, centre)
            assert abs(width[1]-width[0]-10.6) < 0.025, (name, "width", width)
            assert abs(height[1]-height[0]-2) < 0.025, (name, "height", height)
            clear = []
            for yy in (-4.9, 0.123, 4.9):
                for zz in (0.45, 1.071, 1.55):
                    point = to_print(row, x+0.127, y+yy, z+zz)
                    bounds = void_bounds(tris, 0, point)
                    assert bounds[0] < x-8.2 and bounds[1] > x+8.2, (name, point, bounds)
                    clear.append({"y_local_offset_mm": yy, "z_local_offset_mm": zz,
                                  "span_mm": [x-8.2, x+8.2]})
            roof = to_print(row, x+0.127, y+0.123, z+2.8)
            leg = to_print(row, x+0.127, y+6.3, z+1.071)
            assert inside(tris, roof) and inside(tris, leg), (name, "missing roof or leg")
            passages.append({"root_centre_local_mm": [x, y, z], "width_from_stl_mm": width[1]-width[0],
                             "height_from_stl_mm": height[1]-height[0], "through_x_samples": clear,
                             "roof_and_leg_material_present": True})
        report[name] = {**checks, "bbox_from_stl_mm": size, "min_z_from_stl_mm": low[2],
                        "bridges": passages, "mesh_sha256": row["sha256"]}
    return {"revision": model["revision"], "export_id": model["export_id"],
            "source_receipt": model["current_binding"]["receipt"], "changed_meshes": changed,
            "unchanged_mesh_count": 26, "coordinate_rounding_mm": 1e-5, "results": report,
            "scope": "STL surface samples and connectivity, not print accuracy, tape holding force or full flexible-wire motion.",
            "printed": False, "powered": False, "flashed": False}


if __name__ == "__main__":
    result = verify()
    (OUT / "case-mesh-checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PASS two closed connected case meshes; five tape passages measured from STL; 26 other meshes unchanged.")
