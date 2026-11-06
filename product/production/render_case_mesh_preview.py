"""Plot actual STL surfaces and clipped sections; no GUI, slicing or model edits."""
import json
import struct
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.work/production'
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ROOT/'product/production/model-manifest.json').read_text())
rows = {r['object_id']: r for r in manifest['meshes']}
fig, axes = plt.subplots(2, 2, figsize=(12, 10), facecolor='#f5f7fa',
                         gridspec_kw={'height_ratios': [3, 1.35]})
for column, name in enumerate(['base', 'top']):
    row = rows[name]
    data = (ROOT/row['file']).read_bytes()
    n = struct.unpack_from('<I', data, 80)[0]
    dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attr', '<u2')])
    tris = np.frombuffer(data, dtype=dtype, count=n, offset=84)['vertices'].astype(float)
    normal = np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0])
    visible = normal[:, 2] > 1e-8
    surface = tris[visible]
    heights = surface[:, :, 2].mean(axis=1)
    order = heights.argsort()
    shade = (heights-heights.min()) / max(np.ptp(heights), 1)
    colors = plt.get_cmap('Blues')(.25+.6*shade)
    ax = axes[0, column]
    ax.add_collection(PolyCollection(surface[order, :, :2], facecolors=colors[order],
                                      edgecolors='none', antialiaseds=False))
    ax.set(xlim=(-46, 46), ylim=(-67, 67), xlabel='X / mm', ylabel='Y / mm',
           title=('Bottom cover' if name == 'base' else 'Top shell')+' | STL print orientation')
    ax.set_aspect('equal')
    local = tris - np.array(row['local_print_translation_mm'])
    if row['local_print_rotation_deg'] == [180, 0, 0]:
        local[:, :, 1:] *= -1
    cut_x = .127 if name == 'base' else -16.873
    segments = []
    for tri in local:
        points = []
        for i in range(3):
            a, b = tri[i], tri[(i+1) % 3]
            if (a[0]-cut_x)*(b[0]-cut_x) < 0:
                u = (cut_x-a[0])/(b[0]-a[0])
                points.append(a+u*(b-a))
        if len(points) == 2:
            segments.append([points[0][1:], points[1][1:]])
    ax = axes[1, column]
    ax.add_collection(LineCollection(segments, colors='#164e63', linewidths=1.05))
    ax.set(xlim=(-39, -19) if name == 'base' else (-64, -47),
           ylim=(1.8, 7) if name == 'base' else (4.7, 10),
           xlabel='Local Y / mm', ylabel='Local Z / mm', title='Tape bridge section from STL triangles')
    ax.set_aspect('equal')
    ax.grid(alpha=.2)
fig.suptitle('CalcKey | Actual case STL surfaces and sections | no printing', fontsize=15)
fig.tight_layout(rect=(0, 0, 1, .96))
target = OUT/'case-mesh-preview.png'
fig.savefig(target, dpi=140, facecolor=fig.get_facecolor())
print(target.relative_to(ROOT))
