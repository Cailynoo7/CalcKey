#!/usr/bin/env python3
"""Source-derived assembly illustrations, not PCB fabrication geometry.

Run with reportlab==4.4.3; on this workspace:
PYTHONPATH=.work/wiring-diagram-tools python3 product/matrix-assembly-diagrams/generate.py
"""
import csv
import hashlib
import html
import json
import os
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, landscape

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
W, H = 1680, 1188
INK, MUTED, BORDER = '#203346', '#647787', '#ccd9e1'
WHITE, LIGHT, PCB, GOLD = '#ffffff', '#edf4f7', '#dcefe4', '#c49942'
RED, BLUE, GND = '#c53849', '#246eae', '#354350'
COLORS = ['#92500e', '#b34266', '#7652a1', '#268060', '#7c7014',
          '#2370ad', '#197b8d', '#5668b1', '#744886', RED]
PIN = {'GP0': 1, 'GP1': 2, 'GP2': 4, 'GP3': 5, 'GP4': 6, 'GP5': 7,
       'GP6': 9, 'GP7': 10, 'GP8': 11, 'GP9': 12, 'GP10': 14, 'GP11': 15,
       'GND': 38, '3V3': 36}
J = [(f'J{i+1}', f'ROW{i}' if i < 5 else f'COL{i-5}', f'GP{i+2}', COLORS[i])
     for i in range(9)] + [('J10', 'V3V3', '3V3', RED)]
LCD = [('P1', '/CS', 'GP11', '#7652a1'), ('P2', '/WR', 'GP1', '#197b8d'),
       ('P3', 'DATA', 'GP0', BLUE), ('P4', 'VSS', 'GND', GND),
       ('P5', 'VDD', '3V3', RED)]
index_path = ROOT / 'manufacturing/matrix/release-index.json'
release_id = json.loads(index_path.read_text())['releases'][-1]['releaseId']
assert release_id == '17123bc08553010640eaa377912e790923ec95a26949b1e102fa73c7f9b2c727'
circuit_path = ROOT / f'manufacturing/matrix/releases/{release_id}/package/circuit.json'
circuit = json.loads(circuit_path.read_text())
wiring_path = ROOT / 'design/enclosure/source/wiring.json'
wiring = json.loads(wiring_path.read_text())
sc = {e['source_component_id']: e for e in circuit if e['type'] == 'source_component'}
pc = {sc[e['source_component_id']]['name']: e for e in circuit if e['type'] == 'pcb_component'}
sp = {e['source_port_id']: e for e in circuit if e['type'] == 'source_port'}
nets = {e['source_net_id']: e['name'] for e in circuit if e['type'] == 'source_net'}
port_net = {}
for e in circuit:
    if e['type'] == 'source_trace':
        assert len(e['connected_source_net_ids']) == 1
        for p in e['connected_source_port_ids']:
            port_net[p] = nets[e['connected_source_net_ids'][0]]

def ports(ref):
    return {str(sp[p['source_port_id']]['pin_number']): dict(p, net=port_net[p['source_port_id']])
            for p in circuit if p['type'] == 'pcb_port' and p['pcb_component_id'] == pc[ref]['pcb_component_id']}

board = next(e for e in circuit if e['type'] == 'pcb_board')
assert (board['width'], board['height'], board['thickness']) == (73, 96, 1.6)
layout = json.loads((ROOT / 'product/requirements.json').read_text())['requirements']['key_layout']['value']
KEYS = []
for n in range(1, 21):
    row, col = divmod(n-1, 4)
    sw, d = ports(f'SW{n}'), ports(f'D{n}')
    assert sw['1']['net'] == f'COL{col}'
    assert sw['2']['net'] == d['2']['net'] == f'KEY{n}'
    assert d['1']['net'] == f'ROW{row}'
    assert pc[f'SW{n}']['layer'] == 'top' and pc[f'D{n}']['layer'] == 'bottom'
    hole = next(e for e in circuit if e['type'] == 'pcb_hole' and
                e.get('pcb_component_id') == pc[f'SW{n}']['pcb_component_id'])
    assert abs(d['1']['x']-d['2']['x']-7.62) < 1e-6
    KEYS.append(dict(n=n, row=row, col=col, x=hole['x'], y=hole['y'], sw=sw, d=d,
                     label=layout[row][col]))
for i, (ref, net, gpio, color) in enumerate(J):
    p = ports(ref)['1']
    assert p['net'] == net and pc[ref]['layer'] == 'bottom'
    assert abs(p['x']-(-27+6*i)) < 1e-6 and abs(p['y']+46.5) < 1e-6
for i in range(1, 5):
    p = ports(f'R{i}')
    assert p['1']['net'] == 'V3V3' and p['2']['net'] == f'COL{i-1}'
    assert pc[f'R{i}']['layer'] == 'bottom'
for pad, signal, gpio, color in LCD:
    con = [c for c in wiring['connections'] if c['to'] == {'part': 'LCD', 'pin': pad+' '+signal}]
    assert len(con) == 1 and con[0]['from'] == {'part': 'MCU', 'pin': gpio}
for i in range(5):
    assert any(c['from'] == {'part': f'D{4*i+1:02}', 'pin': 'K'} and
               c['to'] == {'part': 'MCU', 'pin': f'GP{i+2}'} for c in wiring['connections'])
for i in range(4):
    assert any(c['to'] == {'part': f'SW{i+1:02}', 'pin': '1'} and
               c['from'] == {'part': 'MCU', 'pin': f'GP{i+7}'} for c in wiring['connections'])

pdfmetrics.registerFont(TTFont('Guide', os.environ.get('CALCKEY_DIAGRAM_FONT',
                           '/System/Library/Fonts/Supplemental/Arial Unicode.ttf')))
pdf = canvas.Canvas(str(OUT / 'calckey-matrix-pcb-assembly.pdf'), pagesize=landscape(A3))
pdf.setTitle('CalcKey MATRIX A - PCB / Pico 2 / GDM0103 soldering illustrations')
pdf.setAuthor('CalcKey')

class Sheet:
    def __init__(self, number, title, subtitle):
        self.number = number
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 {W} {H}">',
                    '<title>'+html.escape(title)+'</title>',
                    '<desc>Source-derived assembly illustration; not a fabrication or 1:1 drilling template. PCB release '+release_id+'</desc>']
        pdf.saveState()
        pw, ph = landscape(A3)
        pdf.scale(pw/W, ph/H)
        self.rect(0, 0, W, H, WHITE, None)
        self.text(56, 66, title, 37)
        self.text(56, 110, subtitle, 21, MUTED)
        self.text(1624, 65, f'{number} / 4', 22, MUTED, 'end')
        self.line(56, 135, 1624, 135, BORDER)

    def line(self, x1, y1, x2, y2, color=INK, width=2):
        self.svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
        pdf.setStrokeColor(HexColor(color)); pdf.setLineWidth(width)
        pdf.line(x1, H-y1, x2, H-y2)

    def path(self, pts, color=INK, width=2):
        self.svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" stroke="{color}" stroke-width="{width}"/>')
        p = pdf.beginPath(); p.moveTo(pts[0][0], H-pts[0][1])
        for x, y in pts[1:]: p.lineTo(x, H-y)
        pdf.setStrokeColor(HexColor(color)); pdf.setLineWidth(width); pdf.drawPath(p)

    def rect(self, x, y, w, h, fill=WHITE, stroke=BORDER, radius=0):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill or "none"}" stroke="{stroke or "none"}" stroke-width="2"/>')
        if fill: pdf.setFillColor(HexColor(fill))
        if stroke: pdf.setStrokeColor(HexColor(stroke)); pdf.setLineWidth(2)
        pdf.roundRect(x, H-y-h, w, h, radius, stroke=int(bool(stroke)), fill=int(bool(fill)))

    def dot(self, x, y, color=INK, r=5, hole=False):
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{WHITE if hole else color}" stroke="{color}" stroke-width="2"/>')
        pdf.setFillColor(HexColor(WHITE if hole else color)); pdf.setStrokeColor(HexColor(color))
        pdf.setLineWidth(2); pdf.circle(x, H-y, r, fill=1, stroke=1)

    def text(self, x, y, text, size=20, color=INK, anchor='start'):
        text = str(text); width = pdfmetrics.stringWidth(text, 'Guide', size)
        left = x-(width if anchor == 'end' else width/2 if anchor == 'middle' else 0)
        assert 0 <= left and left+width <= W and 0 < y < H, (self.number, text, left, width, y)
        self.svg.append(f'<text x="{x}" y="{y}" font-family="Arial Unicode MS, PingFang SC, sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}">{html.escape(text)}</text>')
        pdf.setFillColor(HexColor(color)); pdf.setFont('Guide', size); pdf.drawString(left, H-y, text)

    def note(self, x, y, lines, size=21, gap=34, color=INK):
        for line in lines:
            self.text(x, y, line, size, color); y += gap

    def finish(self, name):
        self.line(56, 1137, 1624, 1137, BORDER)
        self.text(56, 1167, 'CalcKey · MATRIX A / Pico 2 / GDM0103 · 断开USB焊装 · 非1:1加工模板', 17, MUTED)
        self.text(1624, 1167, f'PCB 17123bc08553 · 2026-11-06 · {self.number}/4', 17, MUTED, 'end')
        self.svg.append('</svg>')
        (OUT / name).write_text('\n'.join(self.svg)+'\n')
        pdf.restoreState(); pdf.showPage()

def pad(s, x, y, square=False, scale=7, width=1.6, height=None, hole=0.8):
    height = width if height is None else height
    if square: s.rect(x-width*scale/2, y-height*scale/2, width*scale, height*scale, GOLD, None)
    else: s.dot(x, y, GOLD, width*scale/2)
    if hole: s.dot(x, y, INK, hole*scale/2)

def board_picture(s, x, y, back=False, scale=7):
    def pos(px, py): return x+(36.5-px if back else px+36.5)*scale, y+(48-py)*scale
    s.rect(x, y, 73*scale, 96*scale, PCB, '#709d89', 7)
    for k in KEYS:
        cx, cy = pos(k['x'], k['y'])
        if not back:
            s.rect(cx-7*scale, cy-7*scale, 14*scale, 14*scale, WHITE, '#84a998', 7)
            label = {'Backspace':'Bk', 'NumLock':'Num', 'MODE':'Mode', 'ENTER':'='}.get(k['label'], k['label'])
            s.text(cx, cy+2, label, 24, INK, 'middle')
            s.text(cx, cy+31, f'SW{k["n"]}', 16, MUTED, 'middle')
        else:
            s.dot(cx, cy, '#79998c', 2*scale, hole=True)
            for p in k['sw'].values():
                px, py = pos(p['x'], p['y']); pad(s, px, py, scale=scale, width=2.2, hole=1.5)
            s.text(cx-10, cy+35, f'SW{k["n"]}', 16, INK, 'end')
            d = k['d']; kx, ky = pos(d['1']['x'], d['1']['y']); ax, ay = pos(d['2']['x'], d['2']['y'])
            s.line(kx, ky, ax, ay, INK, 3)
            pad(s, kx, ky, True, scale); pad(s, ax, ay, False, scale)
            mid = (kx+ax)/2
            s.rect(mid-12, ky-7, 24, 14, '#daa371', '#976339', 3)
            s.rect(mid-9, ky-6, 4, 12, INK, None)
            s.text(mid, ky+27, f'D{k["n"]}', 16, INK, 'middle')
    if back:
        for i in range(1, 5):
            c = pc[f'R{i}']['center']; cx, cy = pos(c['x'], c['y'])
            for p in ports(f'R{i}').values():
                px, py = pos(p['x'], p['y']); s.rect(px-3.6, py-4.9, 7.2, 9.8, '#9caba8', None)
            s.rect(cx-4, cy-3.5, 8, 7, INK, None)
        for ref, net, gpio, color in J:
            p = ports(ref)['1']; px, py = pos(p['x'], p['y'])
            pad(s, px, py, True, scale, 4, 2, 0)
            s.text(px, py-13, ref, 16, color, 'middle')
    return pos

def pico(s, x, y, pitch=22):
    s.rect(x, y-28, 240, 20*pitch+30, '#d5eadc', '#648f76', 15)
    s.rect(x+84, y-50, 72, 48, '#d3dbe1', INK, 5)
    s.text(x+120, y-61, 'USB ↑', 23, INK, 'middle')
    s.text(x+120, y+18*pitch, 'Pico 2', 22, '#63846e', 'middle')
    active = {v:k for k,v in PIN.items()}
    for i in range(20):
        yy = y+i*pitch
        for xx, physical, side in [(x, i+1, 'left'), (x+240, 40-i, 'right')]:
            signal = active.get(physical, '')
            color = RED if physical == 36 else GND if physical == 38 else BLUE if signal else '#a1b6aa'
            s.dot(xx, yy, color, 5, hole=True)
            s.text(xx+(13 if side == 'left' else -13), yy+5, physical, 15, INK,
                   'start' if side == 'left' else 'end')
            if signal:
                label = '3V3 OUT' if signal == '3V3' else signal
                s.text(xx+(43 if side == 'left' else -43), yy+5, label, 16, color,
                       'start' if side == 'left' else 'end')
    return {n: (x, y+(n-1)*pitch) if n <= 20 else (x+240, y+(40-n)*pitch) for n in range(1,41)}

def page1():
    s = Sheet(1, '器件方向｜正反面对照', '两图均保持屏幕端朝上；右图已左右镜像，按实际底面焊装，不要再次镜像。')
    s.text(60, 194, 'A  按键面 / TOP', 27)
    s.text(650, 194, 'B  焊接底面 / BOTTOM', 27)
    for x in [60,650]: s.text(x+255, 230, '↑ 屏幕端 / 远端', 22, MUTED, 'middle')
    board_picture(s, 60, 250)
    board_picture(s, 650, 250, True)
    s.text(315, 959, '近端 ↓', 22, MUTED, 'middle')
    s.text(905, 959, '近端 ↓   J10 ← … → J1', 22, MUTED, 'middle')
    s.rect(1210, 180, 414, 810, LIGHT, None, 12)
    s.note(1230, 220, ['20 × KS-9 三脚红轴', 'SW1～20从正面插入。', '每轴仅焊两个金属触点；', '中心塑料柱孔不焊。'], 21)
    s.note(1230, 390, ['20 × 1N4148-TAP', '二极管在底面卧装。', '黑环 K → 方形 pad1。', '本图底面：黑环一律朝左。'], 21)
    s.note(1230, 560, ['4 × 10kΩ / 0805', 'R1～R4在远端中央。', '无极性；位置放大见第4页。'], 21)
    s.note(1230, 700, ['10 × 平面焊线点', 'J1～J10在近端底面。', '每点一根绝缘软线；', '不装直立排针或插座。'], 21)
    s.note(1230, 870, ['尺寸：73 × 96 × 1.6mm', '示意图省略走线和过孔。', '焊盘中心来自当前发布。'], 19, 30, MUTED)
    s.rect(56, 1009, 1568, 96, LIGHT, None, 10)
    s.text(78, 1044, '正面第一排：SW1 Num、SW2 /、SW3 *、SW4 Bk；底面第一排顺序相反。', 23)
    s.text(78, 1080, '单键电路：COL → 轴触点1 → 轴触点2 → 二极管 A → K（黑环）→ ROW。铜线已由PCB连接。', 22)
    s.finish('01-component-orientation.svg')

def page2():
    s = Sheet(2, 'J1～J10｜矩阵板到Pico 2', 'J是矩阵板焊点编号；GP是GPIO；“物理”是Pico针脚号。三者不能互换。')
    s.rect(56, 166, 1568, 150, LIGHT, None, 12)
    s.text(80, 200, '实际底面近端焊盘：屏幕端保持朝上，左 → 右', 23)
    for i in range(10):
        ref, net, gpio, color = J[9-i]; x = 155+i*145
        s.rect(x-32, 225, 64, 24, GOLD, color, 2)
        s.text(x, 278, ref, 23, color, 'middle')
        s.text(x, 300, net, 16, color, 'middle')
    s.text(75, 365, '逐根导线索引（下表按J1→J10排列）', 26)
    s.text(1310, 342, '元件面朝你 · USB朝上', 23, INK, 'middle')
    endpoints = pico(s, 1190, 440)
    for i, (ref, net, gpio, color) in enumerate(J):
        yy = 443+i*48
        s.rect(75, yy-25, 755, 43, LIGHT, None, 5)
        s.text(95, yy+4, ref, 24, color)
        s.text(180, yy+4, net, 23, color)
        s.text(335, yy+4, '→', 23, color)
        s.text(395, yy+4, '3V3 OUT' if gpio == '3V3' else gpio, 23, color)
        s.text(665, yy+4, f'物理 {PIN[gpio]}', 23, color)
        ex, ey = endpoints[PIN[gpio]]
        if ref == 'J10':
            s.path([(830,yy),(1035,yy),(1035,957),(1518,957),(1518,ey),(ex,ey)], color, 3)
            s.text(1300, 945, 'J10 → 3V3 OUT / 物理36', 19, RED, 'middle')
        else:
            turn = 935+i*17
            s.path([(830,yy),(turn,yy),(turn,ey),(ex,ey)], color, 3)
        s.dot(830, yy, color, 4)
    s.text(75, 967, '导线交叉无圆点＝不连接；按两端标签逐根核对。线色只是识别建议。', 20, MUTED)
    s.rect(56, 995, 1568, 111, LIGHT, None, 12)
    s.text(78, 1030, '矩阵板没有GND接点：J1～J5是扫描行，不能接地。J10只接3V3 OUT，不能接VBUS、VSYS或5V。', 22, RED)
    s.text(78, 1068, 'Pico为了读脚号画成USB朝上；实际装机USB朝机身右侧。翻到Pico背面焊接时左右会反转。', 22)
    s.finish('02-j1-j10-to-pico.svg')

def page3():
    s = Sheet(3, 'GDM0103｜端子方向与独立五线', '按厂家外形图显示方向定位P1；这是HT1621B三线写接口。LCD导线直接到Pico，不经过矩阵板。')
    for back, x in [(False,170),(True,950)]:
        s.text(x+265, 191, 'B  背面：保持上边朝上翻转' if back else 'A  正面：显示字符朝向你', 24, INK, 'middle')
        s.text(x+265, 228, '↑ 显示上边', 20, MUTED, 'middle')
        s.rect(x, 250, 530, 220, PCB, '#709d89', 9)
        if not back:
            s.rect(x+62, 284, 406, 127, '#d2dfc3', '#6c8464', 3)
            s.text(x+265, 362, '8 8 8 8 8 8 8 8', 37, '#506446', 'middle')
        else:
            s.text(x+265, 330, 'PCB背面', 26, MUTED, 'middle')
            s.text(x+265, 370, '仅示意端子；不画背面元件', 21, MUTED, 'middle')
        for i, signal in enumerate(['/CS','/WR','DATA','VSS','VDD','/INT']):
            px = x+530 if back else x; yy = 271+i*33
            color = LCD[i][3] if i < 5 else MUTED
            pad(s, px, yy, False, 7, 2, hole=1)
            s.text(px+(18 if back else -18), yy+6, f'P{i+1} {signal}', 18, color,
                   'start' if back else 'end')
        for i, signal in enumerate(['BL+','BL-','Ctrl']):
            px = x if back else x+530; yy = 286+i*55
            pad(s, px, yy, False, 7, 2, hole=1)
            s.text(px+(-18 if back else 18), yy+6, f'P{i+7} {signal}', 18, MUTED,
                   'end' if back else 'start')
    s.text(56, 513, '背面看：右侧自上而下P1～P6；左侧自上而下P7～P9。实物以P1丝印及厂家图共同核对。', 22)
    s.text(56, 553, 'P6 /INT、P7 BL+、P8 BL-、P9 Ctrl：分别绝缘不接；不加背光连线。', 22, MUTED)
    s.line(56, 587, 1624, 587, BORDER)
    for i, (pad_name, signal, gpio, color) in enumerate(LCD):
        yy = 642+i*68
        s.rect(80, yy-25, 470, 47, LIGHT, None, 7)
        s.text(103, yy+7, f'LCD {pad_name} · {signal}', 25, color)
        s.line(550, yy, 1105, yy, color, 4)
        s.text(828, yy-10, '独立软线 · 约150mm', 18, color, 'middle')
        s.dot(550, yy, color); s.dot(1105, yy, color)
        s.rect(1105, yy-25, 490, 47, LIGHT, None, 7)
        s.text(1128, yy+7, f'Pico 物理{PIN[gpio]} · '+('3V3 OUT' if gpio=='3V3' else gpio), 24, color)
    s.text(80, 1016, '同一3V3节点（圆点＝相连）', 22, RED)
    s.line(500, 979, 805, 979, RED, 4); s.dot(805, 979, RED, 6)
    s.path([(805,979),(805,956),(1060,956)], RED, 4)
    s.path([(805,979),(805,1011),(1060,1011)], RED, 4)
    s.text(490, 985, 'Pico 物理36', 22, RED, 'end')
    s.text(1080, 964, '矩阵 J10', 22, RED)
    s.text(1080, 1019, 'LCD P5 / VDD', 22, RED)
    s.rect(56, 1042, 1568, 64, LIGHT, None, 9)
    s.text(78, 1081, 'P1～P5低位直焊，不装直立排针；板背焊点/首段导线突出≤1.5mm。P4接GND/物理38。', 22)
    s.finish('03-lcd-orientation-and-wiring.svg')

def page4():
    s = Sheet(4, '焊装细节｜放大方向与断电核对', '全程断开USB；先测被动矩阵，合格后再焊Pico和LCD。这里没有填写任何实物测量结果。')
    s.rect(56, 168, 750, 332, LIGHT, None, 12)
    s.text(80, 211, 'A  底面二极管：黑环 → 左侧方形K焊盘', 26)
    s.line(135, 305, 710, 305, INK, 6)
    pad(s, 150, 305, True, 24, 2.7, hole=1)
    pad(s, 700, 305, False, 24, 2.7, hole=1)
    s.rect(290, 269, 260, 72, '#daa371', '#976339', 14)
    s.rect(311, 272, 20, 66, INK, None)
    s.text(150, 377, 'K / pad1 / ROW', 23, INK, 'middle')
    s.text(700, 377, 'A / pad2', 23, INK, 'middle')
    s.note(80, 432, ['黑环与PCB的K线、方形pad1相同侧；弯脚间距7.62mm。', '卧装于底面；从正面剪短多余引脚。'], 22, 33)
    s.rect(842, 168, 782, 332, LIGHT, None, 12)
    s.text(866, 211, 'B  远端中央R1～R4（底面放大）', 26)
    s.text(1110, 246, '↑ 屏幕端', 20, MUTED, 'middle')
    for i in range(1, 5):
        c = pc[f'R{i}']['center']; x=1110-c['x']*39; y=360-(c['y']-44)*34
        s.rect(x-26, y-15, 52, 30, INK, None, 2)
        s.rect(x-36, y-15, 15, 30, '#a7b9bc', None)
        s.rect(x+21, y-15, 15, 30, '#a7b9bc', None)
        s.text(x, y+43, f'R{i} / COL{i-1}', 18, INK, 'middle')
    s.note(1325, 280, ['0805贴片', '10kΩ ±1%', '无极性', '不换成轴向电阻'], 21, 39)
    s.text(866, 463, '每只一端接3V3、一端接对应列；焊好后查四处锡桥。', 22)
    s.text(56, 554, '焊装顺序', 27)
    steps = [('1', 'R与D', '先焊4只0805及20只二极管。'),
             ('2', '面板与轴', '轴扣入面板、坐平，再套PCB。'),
             ('3', '40个触点', '底面焊轴脚；中心塑料柱不焊。'),
             ('4', '15根线', '10根矩阵线＋5根LCD线。')]
    for i, (n, title, body) in enumerate(steps):
        x = 56+i*395
        s.rect(x, 582, 370, 130, LIGHT, None, 10)
        s.dot(x+29, 615, BLUE, 17); s.text(x+29, 622, n, 23, WHITE, 'middle')
        s.text(x+58, 622, title, 24)
        s.text(x+17, 670, body, 20)
    s.text(56, 762, '断电检查：先不连Pico和LCD，测矩阵；接线后再逐根对表查通断。', 25)
    checks = [
        ('4列上拉', 'J6/J7/J8/J9各对J10约10kΩ；列间约20kΩ可来自两个上拉。'),
        ('20键二极管', '逐键按下：红表笔接列J6～J9，黑表笔接行J1～J5，测正向压降。'),
        ('交换表笔', '按键保持按下再反测，应截止；在路有疑问时分离器件复测。'),
        ('15根导线', '逐根端到端通断；相邻裸焊点无桥接；J10/P5仅接3V3。'),
        ('绝缘与应力', 'P6～P9各自绝缘；线皮胶带固定，过孔处不留裸铜，不用焊盘承力。')]
    for i, (title, body) in enumerate(checks):
        yy = 809+i*49
        s.rect(56, yy-28, 1568, 45, LIGHT if i%2==0 else WHITE, None)
        s.rect(73, yy-16, 18, 18, WHITE, BORDER)
        s.text(106, yy, title, 21)
        s.text(293, yy, body, 21)
        s.text(1596, yy, '待测', 18, MUTED, 'end')
    s.text(56, 1100, '每根软线约150mm留维护余量，沿底盖平铺；避开USB、合盖柱和翻脚机构。只做断电检查，不烧录。', 21, MUTED)
    s.finish('04-details-and-unpowered-checks.svg')

page1(); page2(); page3(); page4(); pdf.save()

with (OUT/'soldering-map.csv').open('w', encoding='utf-8-sig', newline='') as f:
    out = csv.writer(f)
    out.writerow(['部件', '焊点', '信号', 'Pico信号', 'Pico物理脚号', '说明'])
    for ref, net, gpio, color in J:
        out.writerow(['矩阵PCB', ref, net, '3V3 OUT' if gpio=='3V3' else gpio, PIN[gpio], '26AWG约150mm；底面平面直焊'])
    for pad_name, signal, gpio, color in LCD:
        out.writerow(['GDM0103', pad_name, signal, '3V3 OUT' if gpio=='3V3' else gpio, PIN[gpio], '约150mm；直接到Pico'])
    for pad_name, signal in [('P6','/INT'),('P7','BL+'),('P8','BL-'),('P9','Ctrl')]:
        out.writerow(['GDM0103', pad_name, signal, 'NC', '', '分别绝缘，不接外部线'])
with (OUT/'unpowered-check-record.csv').open('w', encoding='utf-8-sig', newline='') as f:
    out = csv.writer(f)
    out.writerow(['项目', '红表笔', '黑表笔', '条件', '预期', '实测', '结果'])
    for col in range(4): out.writerow([f'COL{col}上拉',f'J{col+6}','J10','Pico/LCD未连接','约10kΩ','','待测'])
    for k in KEYS:
        for reverse in [False, True]:
            a,b=f'J{k["col"]+6}',f'J{k["row"]+1}'
            out.writerow([f'SW{k["n"]}/D{k["n"]}', b if reverse else a, a if reverse else b,
                          '对应按键按下；Pico/LCD未连接', '截止' if reverse else '二极管正向压降','','待测'])
    for ref, net, gpio, color in J:
        out.writerow([f'{ref}导线', ref, f'Pico物理{PIN[gpio]}', '断电', '端到端通断','','待测'])
    for pad_name, signal, gpio, color in LCD:
        out.writerow([f'LCD {pad_name}导线', f'LCD {pad_name}', f'Pico物理{PIN[gpio]}', '断电','端到端通断','','待测'])

inputs = [circuit_path, wiring_path, ROOT/'design/firmware/source/board_config.hpp',
          ROOT/'product/references/rp-008299-ds.pdf', ROOT/'product/references/gdm0103-specification.pdf']
record = dict(pcb_release=release_id, pcb_dimensions_mm=[73,96,1.6],
              source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
              checked=dict(key_branches=20, pullups=4, matrix_leads=10, lcd_leads=5, lcd_nc=4,
                           rear_view='mirror X, retain far/LCD edge at top', diode_cathode_in_rear_view='left',
                           footprint_coordinates='from immutable released circuit.json'),
              sources=[dict(url='https://pip.raspberrypi.com/documents/RP-008299-DS',pdf_page=5),
                       dict(url='https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf',pdf_pages=[7,8])],
              physical_tests='not performed; all check record fields left pending', firmware_action='none')
(OUT/'source-checks.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print('Generated four A3 vector PDF pages, four SVGs, wiring CSV and unpowered test record.')
print('Verified 20 key branches, 4 pullups, 10 matrix leads and 5 LCD leads against release and wiring source.')
