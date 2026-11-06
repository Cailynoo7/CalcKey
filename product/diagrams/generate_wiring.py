#!/usr/bin/env python3
"""Generate matching vector PDF/SVG wiring sheets from the existing netlist.

Dependency: reportlab==4.4.3; CALCKEY_DIAGRAM_FONT can select a CJK TrueType font.
No PCB is created, and the hardware netlist is never modified.
"""
import csv
import hashlib
import html
import json
import os
import re
import zipfile
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, landscape

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
W,H=1680,1188
INK='#203346'; MUTED='#5e6d7a'; BLUE='#2276ad'; RED='#bf3642'; GND='#343d49'
ROWS=['#b15a13','#b83e5c','#7552a1','#2c7954','#817112']
LIGHT='#edf3f7'; BORDER='#cfdae3'; WHITE='#ffffff'
FONT=Path(os.environ.get('CALCKEY_DIAGRAM_FONT','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('Guide',str(FONT)))
wiring_path=ROOT/'design/enclosure/source/wiring.json'
wiring_hash=hashlib.sha256(wiring_path.read_bytes()).hexdigest()
wiring=json.loads(wiring_path.read_text())
requirements=json.loads((ROOT/'product/requirements.json').read_text())
layout=requirements['requirements']['key_layout']['value']
connections=wiring['connections']
def to_net(part,pin):
    return [c for c in connections if c['to']=={'part':part,'pin':pin}]
def from_net(part,pin):
    return [c for c in connections if c['from']=={'part':part,'pin':pin}]
PIN={'GP0':1,'GP1':2,'GP2':4,'GP3':5,'GP4':6,'GP5':7,'GP6':9,
     'GP7':10,'GP8':11,'GP9':12,'GP10':14,'GP11':15,'3V3':36,'GND':38}
keys=[]
for row in range(5):
    for col in range(4):
        n=row*4+col+1; sw=f'SW{n:02}'; diode=f'D{n:02}'
        column=to_net(sw,'1'); series=from_net(sw,'2'); cathode=from_net(diode,'K')
        assert len(column)==len(series)==len(cathode)==1
        assert column[0]['from']=={'part':'MCU','pin':f'GP{col+7}'}
        assert series[0]['to']=={'part':diode,'pin':'A'}
        assert cathode[0]['to']=={'part':'MCU','pin':f'GP{row+2}'}
        keys.append({'row':row,'col':col,'switch':sw,'diode':diode,'label':layout[row][col],
                     'row_gpio':f'GP{row+2}','col_gpio':f'GP{col+7}'})
for col in range(4):
    assert to_net(f'RPU{col}','1')[0]['from']=={'part':'MCU','pin':'3V3'}
    assert from_net(f'RPU{col}','2')[0]['to']=={'part':'MCU','pin':f'GP{col+7}'}
LCD_WIRES=[('P1','/CS','GP11',15,'#7552a1'),('P2','/WR','GP1',2,'#107e85'),
           ('P3','DATA','GP0',1,BLUE),('P4','VSS','GND',38,GND),('P5','VDD','3V3',36,RED)]
for pad,signal,gpio,physical,color in LCD_WIRES:
    nets=to_net('LCD',pad+' '+signal)
    assert len(nets)==1 and nets[0]['from']=={'part':'MCU','pin':gpio}
    assert PIN[gpio]==physical
assert len([c for c in connections if any(c[e]['part']=='LCD' for e in ['from','to'])])==5
assert not any(p['ref']=='OLED' for p in wiring['parts'])
board_source=(ROOT/'design/firmware/source/board_config.hpp').read_text()
assert re.search(r'row_pins=\{2,3,4,5,6\}',board_source)
assert re.search(r'column_pins=\{7,8,9,10\}',board_source)
for name,pin in [('data',0),('wr',1),('cs',11)]:
    assert re.search(r'lcd_'+name+'='+str(pin)+r'\b',board_source)

pdf=canvas.Canvas(str(OUT/'calckey-wiring-guide.pdf'),pagesize=landscape(A3))
pdf.setTitle('CalcKey 20-key matrix, backside soldering and Pico 2 / GDM0103 LCD wiring')
pdf.setAuthor('CalcKey project')
class Sheet:
    def __init__(self,number,title,subtitle):
        self.number=number
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 {W} {H}">',
                  '<title>'+html.escape(title)+'</title>',
                  '<desc>Generated from CalcKey wiring.json. Illustrative wiring; not a drill or switch footprint template.</desc>']
        pdf.saveState();pw,ph=landscape(A3);pdf.scale(pw/W,ph/H)
        self.rect(0,0,W,H,WHITE,None)
        self.text(56,67,title,38)
        self.text(56,111,subtitle,21,MUTED)
        self.text(1620,66,f'{number} / 4',22,MUTED,'end')
        self.line(56,132,1624,132,BORDER,2)
    def line(self,x1,y1,x2,y2,color=INK,width=2):
        self.svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
        pdf.setStrokeColor(HexColor(color));pdf.setLineWidth(width);pdf.setLineCap(1);pdf.line(x1,H-y1,x2,H-y2)
    def path(self,pts,color=INK,width=2,fill=None):
        tag='polygon' if fill else 'polyline'
        coords=' '.join(f'{x},{y}' for x,y in pts)
        self.svg.append(f'<{tag} points="{coords}" fill="{fill or "none"}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')
        p=pdf.beginPath();p.moveTo(pts[0][0],H-pts[0][1])
        for x,y in pts[1:]:p.lineTo(x,H-y)
        if fill:p.close();pdf.setFillColor(HexColor(fill))
        pdf.setStrokeColor(HexColor(color));pdf.setLineWidth(width);pdf.drawPath(p,stroke=1,fill=int(bool(fill)))
    def rect(self,x,y,w,h,fill=WHITE,stroke=BORDER,r=0):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or "none"}" stroke="{stroke or "none"}" stroke-width="2"/>')
        if fill:pdf.setFillColor(HexColor(fill))
        if stroke:pdf.setStrokeColor(HexColor(stroke));pdf.setLineWidth(2)
        if r:pdf.roundRect(x,H-y-h,w,h,r,stroke=int(bool(stroke)),fill=int(bool(fill)))
        else:pdf.rect(x,H-y-h,w,h,stroke=int(bool(stroke)),fill=int(bool(fill)))
    def dot(self,x,y,color=INK,r=5,open=False):
        self.svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{WHITE if open else color}" stroke="{color}" stroke-width="2"/>')
        pdf.setFillColor(HexColor(WHITE if open else color));pdf.setStrokeColor(HexColor(color));pdf.setLineWidth(2);pdf.circle(x,H-y,r,stroke=1,fill=1)
    def text(self,x,y,text,size=20,color=INK,anchor='start'):
        text=str(text);width=pdfmetrics.stringWidth(text,'Guide',size)
        left=x-(width if anchor=='end' else width/2 if anchor=='middle' else 0)
        assert left>=0 and left+width<=W and 0<y<H,(self.number,text,left,width,y)
        self.svg.append(f'<text x="{x}" y="{y}" font-family="Arial Unicode MS, PingFang SC, Noto Sans CJK SC, sans-serif" font-size="{size}" fill="{color}" text-anchor="{anchor}">{html.escape(text)}</text>')
        pdf.setFillColor(HexColor(color));pdf.setFont('Guide',size);pdf.drawString(left,H-y,text)
    def paragraph(self,x,y,text,width=300,size=19,line_height=29):
        line=''
        for char in text:
            if char=='\n' or pdfmetrics.stringWidth(line+char,'Guide',size)>width:
                self.text(x,y,line,size);y+=line_height;line=''
                if char=='\n':continue
            line+=char
        if line:self.text(x,y,line,size);y+=line_height
        return y
    def finish(self,name):
        self.line(56,1138,1624,1138,BORDER,2)
        self.text(56,1169,'CalcKey · 现有GPIO / GDM0103 / 固件v0.2.0 · 仅接线示意，非1:1脚位或加工图',17,MUTED)
        self.text(1624,1169,f'图纸LCD-B  |  {self.number}/4',17,MUTED,'end')
        self.svg.append('</svg>');(OUT/name).write_text('\n'.join(self.svg)+'\n')
        pdf.restoreState();pdf.showPage()

def diode(s,x,y,n,vertical=True):
    if vertical:
        s.rect(x-11,y,22,36,'#e2a06c','#8b572e',5)
        s.rect(x-10,y+25,20,6,'#1b2632',None)
        s.text(x+24,y+10,'A',17)
        s.text(x+24,y+35,'K',17)
        s.text(x-23,y+23,n,16,MUTED,'end')
    else:
        s.line(x-26,y+18,x,y+18,INK,3);s.line(x+100,y+18,x+130,y+18,INK,3)
        s.rect(x,y,100,36,'#e2a06c','#8b572e',8);s.rect(x+78,y+1,8,34,'#1b2632',None)
        s.text(x-34,y+24,'A',22,INK,'end');s.text(x+140,y+24,'K',22)

def matrix_page(back=False):
    number=2 if back else 1
    title='背面焊接图｜左右已镜像' if back else '20键矩阵｜正面布局与电气连接'
    subtitle='从键盘底面看，保持屏幕端朝上；C3在左、C0在右。焊点仅示意，不代表MX实际引脚位置。' if back else '从按键正面看：C0→C3、R0→R4。每键：列C → 开关SW → 二极管A → K色环 → 行R。'
    s=Sheet(number,title,subtitle)
    order=[3,2,1,0] if back else [0,1,2,3]
    s.text(56,186,'3V3 / P36',21,RED)
    s.line(200,177,1230,177,RED,4)
    for slot,col in enumerate(order):
        x=245+slot*260
        s.text(x+103,158,f'C{col}  GP{col+7} / P{PIN[f"GP{col+7}"]}',21,BLUE,'middle')
        s.dot(x,177,RED);s.line(x,177,x,194,RED,3)
        s.rect(x-10,194,20,44,WHITE,INK,0)
        s.text(x+25,211,f'RPU{col}',16,MUTED);s.text(x+25,235,'10kΩ',19,INK)
        s.line(x,238,x,972,BLUE,3)
    for row in range(5):
        y=270+row*140;bus=y+120;color=ROWS[row]
        s.text(56,bus-23,f'R{row}  GP{row+2}',23,color)
        s.text(56,bus+8,f'物理针脚 P{PIN[f"GP{row+2}"]}',17,MUTED)
        s.line(200,bus,1230,bus,WHITE,11);s.line(200,bus,1230,bus,color,4)
        for slot,col in enumerate(order):
            x=245+slot*260;k=keys[row*4+col]
            s.svg.append(f'<g id="{k["switch"]}" data-diode="{k["diode"]}" data-row="R{row}" data-col="C{col}">')
            s.text(x+111,y+18,k['label'],23)
            s.dot(x,y+51,BLUE)
            s.line(x,y+51,x+65,y+51,BLUE,3)
            s.dot(x+65,y+51,INK,4,True);s.dot(x+106,y+51,INK,4,True)
            s.line(x+65,y+51,x+101,y+35,INK,3)
            s.line(x+106,y+51,x+150,y+51,INK,3)
            s.text(x+83,y+78,k['switch'],15,MUTED,'middle')
            if back:
                s.text(x+54,y+35,'C',15,BLUE,'end');s.text(x+114,y+35,'A',15)
            s.line(x+150,y+51,x+150,y+80,INK,3)
            diode(s,x+150,y+80,k['diode'])
            s.line(x+150,y+116,x+150,bus,color,3);s.dot(x+150,bus,color)
            s.svg.append('</g>')
    s.rect(1283,177,341,852,LIGHT,None,14)
    x=1305
    if not back:
        s.text(x,217,'每键一只 1N4148',23)
        diode(s,x+49,255,'',False)
        s.text(x,333,'黑色色环 = 阴极 K',22)
        s.text(x,366,'色环端焊到 R 行总线',21,ROWS[0])
        s.paragraph(x,412,'无色环端A接开关。开关另一电触点接C列总线。')
        s.text(x,522,'交点怎么看',23)
        s.line(x+56,549,x+56,603,BLUE,3)
        s.line(x+20,577,x+105,577,WHITE,11);s.line(x+20,577,x+105,577,ROWS[0],4)
        s.text(x,635,'无圆点：跨过，不相连',20)
        s.line(x+56,666,x+56,724,BLUE,3);s.line(x+56,694,x+109,694,BLUE,3);s.dot(x+56,694,BLUE)
        s.text(x,757,'实心圆：同一网络焊接',20)
        s.paragraph(x,807,'每列各一只10k上拉。\n上拉接3V3，不接5V。\n每次只选中一行拉低；\n其余四行由固件置高阻。\n物理针脚编号详见第3页。')
    else:
        s.text(x,217,'屏幕 / 远端在上方',23)
        s.text(x,257,'此页已经左右翻转',23,BLUE)
        s.paragraph(x,301,'背面第一排从左到右：\nBackspace、×、÷、NumLock。\n不要再自行左右镜像。',size=20)
        s.text(x,449,'两个电触点这样分配',22)
        s.paragraph(x,493,'C触点：接同列所有开关。\nA触点：只接本键二极管。\n二极管K色环：接同行。',size=20)
        s.text(x,624,'焊脚位置仅为示意',22)
        s.paragraph(x,666,'MX开关的两个电触点本身无极性，按实物辨认后任选。图中C/A是电气分配，不规定左脚或右脚。不要把塑料定位柱当触点。',size=19)
        s.paragraph(x,841,'行列线交叉处要绝缘。\nSW与同号D逐键配对。\n矩阵9根主线各留约\n150mm柔性维护余量。',size=20)
    s.text(56,1033,'SW01～SW20、D01～D20编号在正反两页保持一致；全图共20只二极管、4只10k上拉。',21)
    s.text(56,1074,'走线可按空间调整；必须保持网络对应和色环方向。交叉线无实心圆点时不焊接，套管或绝缘层隔开。',21)
    s.finish('02-backside-soldering.svg' if back else '01-matrix-front.svg')

def board_page():
    s=Sheet(3,'Pico 2 与 GDM0103｜针脚和四个上拉','Pico为元件面朝上、USB端向上的顶视图；物理针脚Pxx不是GPIO的GPxx。全程断电，不烧录。')
    s.text(56,183,'A  Pico 2：14个实际使用的针脚',26)
    s.rect(495,224,210,681,'#deece7','#317063',18)
    s.rect(555,203,90,67,'#e2e7ec',INK,6);s.text(600,245,'USB',22,INK,'middle')
    s.text(600,481,'Pico 2',32,INK,'middle');s.text(600,523,'顶视图',22,INK,'middle')
    s.text(600,568,'USB口朝上',20,INK,'middle')
    left_used={1:('GP0 → LCD DATA',BLUE),2:('GP1 → LCD /WR','#107e85'),15:('GP11 → LCD /CS','#7552a1')}
    for row in range(5):left_used[PIN[f'GP{row+2}']]=(f'GP{row+2} → R{row}',ROWS[row])
    for col in range(4):left_used[PIN[f'GP{col+7}']]=(f'GP{col+7} → C{col}',BLUE)
    for i in range(20):
        y=285+i*30
        pin=i+1;active=pin in left_used;color=left_used[pin][1] if active else '#a9b7b5'
        s.rect(463,y-8,32,16,WHITE,color)
        if active:
            name,color=left_used[pin];s.line(340,y,463,y,color,3);s.text(66,y+7,f'P{pin:02}  {name}',21,color)
        else:s.text(453,y+6,str(pin),16,MUTED,'end')
        pin=40-i;active=pin in (36,38);color=RED if pin==36 else GND if pin==38 else '#a9b7b5'
        s.rect(705,y-8,32,16,WHITE,color);s.text(746,y-12 if active else y+6,str(pin),16,color)
        if active:
            s.line(737,y,841,y,color,3);s.dot(841,y,color)
            s.text(782,y-12,'3V3' if pin==36 else 'GND',19,color)
    s.text(56,925,'Pico焊接背面左右相反；实装USB在机身右侧。',17,MUTED)
    s.text(56,948,'其余针脚不接；LCD不用VBUS、VSYS或I²C上拉。',17,MUTED)
    s.rect(868,205,756,430,LIGHT,None,14)
    s.text(891,248,'B  GDM0103 / HT1621B · 3.3V版本',25)
    cols=[892,1062,1237,1450]
    for x,label in zip(cols,['LCD端子','信号','Pico信号','物理针脚']):s.text(x,294,label,20,MUTED)
    s.line(890,313,1600,313,BORDER,2)
    for i,(pad,signal,gpio,physical,color) in enumerate(LCD_WIRES):
        for x,label in zip(cols,[pad,signal,'3V3(OUT)' if gpio=='3V3' else gpio,f'P{physical}']):s.text(x,348+i*39,label,23,color)
    s.paragraph(892,550,'P6 /INT、P7 BL+、P8 BL−、P9 Ctrl分别绝缘不接。低位直焊P1–P5；端子方向见第4页。',width=700,size=19,line_height=27)
    s.text(892,679,'C  每列一个10kΩ，上端共接3V3 / P36',23)
    s.line(902,713,1585,713,RED,4)
    for col,x in enumerate([940,1130,1320,1510]):
        s.dot(x,713,RED);s.line(x,713,x,732,RED,3);s.rect(x-13,732,26,54,WHITE,INK)
        s.text(x+25,752,f'RPU{col}',16,MUTED);s.text(x+25,779,'10kΩ',18)
        s.line(x,786,x,822,BLUE,3);s.dot(x,822,BLUE)
        s.text(x,859,f'C{col} / GP{col+7}',21,BLUE,'middle');s.text(x,891,f'P{PIN[f"GP{col+7}"]}',20,MUTED,'middle')
    s.rect(56,957,755,171,LIGHT,None,12);s.rect(840,957,784,171,LIGHT,None,12)
    s.text(77,993,'焊接顺序',24)
    s.text(77,1026,'① 单键 → ② 成行/列并逐键检查 → ③ 四个上拉',20)
    s.text(77,1059,'④ LCD五线单独测通 → ⑤ 最后接Pico共14针',20)
    s.text(77,1092,'⑥ 绝缘、断电复查；仍不插USB、不烧录。',20)
    s.text(861,993,'测量必须分阶段',24)
    s.text(861,1026,'先独立矩阵三态；装上拉后列间约20kΩ正常。',20)
    s.text(861,1059,'接Pico/LCD后不能要求所有不同网络均为OL。',20)
    s.text(861,1092,'电源持续近零阻先分段排查；不以短暂蜂鸣判定。',20)
    s.finish('03-pico-lcd-pullups.svg')

def lcd_page():
    s=Sheet(4,'GDM0103｜正反面端子与五线直焊','按厂家外形图的显示方向示意；非1:1焊盘模板。先找P1丝印，再核对信号，不能按线色或脚距猜。')
    s.text(70,195,'A  显示面朝向你：P1在左侧上端',25)
    s.text(900,195,'B  保持上边朝上翻到背面：左右镜像',25)
    pins=[('/CS','#7552a1'),('/WR','#107e85'),('DATA',BLUE),('VSS',GND),('VDD',RED),('/INT',MUTED)]
    nc=[('BL+',MUTED),('BL−',MUTED),('Ctrl',MUTED)]
    for back,x in [(False,200),(True,960)]:
        s.rect(x,255,520,180,'#deece7','#317063',10)
        if not back:
            s.rect(x+73,286,374,91,'#d5e1c4','#687b67',3)
            s.text(x+260,343,'8 位 LCD 显示面',29,INK,'middle')
        else:
            s.text(x+260,328,'PCB背面：只示意端子顺序',24,INK,'middle')
            s.text(x+260,366,'不是背面元件或焊盘比例图',20,MUTED,'middle')
        for i,(signal,color) in enumerate(pins):
            yy=279+i*27
            px=x+520 if back else x
            s.rect(px-8,yy-6,16,12,'#d9b66c',color)
            if back:s.line(px+8,yy,px+28,yy,color);s.text(px+35,yy+6,f'P{i+1} {signal}',18,color)
            else:s.line(px-28,yy,px-8,yy,color);s.text(px-35,yy+6,f'P{i+1} {signal}',18,color,'end')
        for i,(signal,color) in enumerate(nc):
            yy=300+i*34;px=x if back else x+520
            s.rect(px-8,yy-6,16,12,'#d9b66c',color)
            if back:s.line(px-26,yy,px-8,yy,color);s.text(px-31,yy+6,f'P{i+7} {signal}',17,color,'end')
            else:s.line(px+8,yy,px+28,yy,color);s.text(px+33,yy+6,f'P{i+7} {signal}',17,color)
    s.text(70,485,'P6 /INT及P7–P9均不接；没有外部连线，端头逐个绝缘，不要求模块内部电路彼此OL。',21,MUTED)
    s.line(56,522,1624,522,BORDER,2)
    s.text(70,571,'C  五根实际导线：按标签直连，不装直立排针',27)
    for i,(pad,signal,gpio,physical,color) in enumerate(LCD_WIRES):
        yy=621+i*70
        s.rect(90,yy,470,47,LIGHT,color,8);s.rect(1120,yy,470,47,LIGHT,color,8)
        s.text(114,yy+31,f'Pico P{physical} · '+('3V3(OUT)' if gpio=='3V3' else gpio),23,color)
        s.line(560,yy+24,1120,yy+24,color,5)
        s.text(840,yy+13,signal,19,color,'middle')
        s.text(1144,yy+31,f'LCD {pad} · {signal}',23,color)
        s.dot(560,yy+24,color);s.dot(1120,yy+24,color)
    s.rect(56,1003,1568,113,LIGHT,None,12)
    s.text(78,1040,'焊点/首段导线突出板背≤1.5mm；朝板内低位折线，各留约150mm维护余量，接头逐个套管。',21)
    s.text(78,1076,'两侧PCB承托带需无元件/裸铜；先焊线与断电检查，再贴0.15mm绝缘胶片；勿用焊锡或胶压迫玻璃。',20)
    s.finish('04-lcd-front-back-wiring.svg')

matrix_page();matrix_page(True);board_page();lcd_page();pdf.save()
assert hashlib.sha256(wiring_path.read_bytes()).hexdigest()==wiring_hash
with (OUT/'soldering-map.csv').open('w',encoding='utf-8-sig',newline='') as f:
    fields=['switch','label','diode','row','row_gpio','row_physical_pin','col','col_gpio','col_physical_pin','diode_anode','diode_cathode']
    writer=csv.DictWriter(f,fields);writer.writeheader()
    for k in keys:
        row=dict(k);row.update(row_physical_pin=PIN[k['row_gpio']],col_physical_pin=PIN[k['col_gpio']],diode_anode=k['switch']+'.2',diode_cathode=f'R{k["row"]}')
        writer.writerow(row)
with (OUT/'lcd-wiring-map.csv').open('w',encoding='utf-8-sig',newline='') as f:
    fields=['lcd_pad','signal','pico_gpio','pico_physical_pin','external_connection','evidence']
    writer=csv.DictWriter(f,fields);writer.writeheader()
    for pad,signal,gpio,physical,color in LCD_WIRES:
        writer.writerow(dict(lcd_pad=pad,signal=signal,pico_gpio=gpio,pico_physical_pin=physical,
                             external_connection='低位直焊',evidence='GDM0103 PDF p7/8; Pico2 PDF p5'))
    for pad,signal in [('P6','/INT'),('P7','BL+'),('P8','BL-'),('P9','Ctrl')]:
        writer.writerow(dict(lcd_pad=pad,signal=signal,pico_gpio='',pico_physical_pin='',
                             external_connection='不接外部线，分别绝缘',evidence='GDM0103 PDF p7/8'))
readme="""# CalcKey GDM0103 LCD接线焊接图（LCD-B / 固件v0.2.0）

交付四页A3横向矢量PDF、4张可编辑SVG、20键映射CSV和9端子LCD对照CSV。本版替换旧OLED图，适用于现有Pico 2、GDM0103/HT1621B的3.3V版本和20键矩阵，不改变硬件网络、固件或CAD。全程断电，不烧录。

1. 第1页：按键正面，20键、逐键1N4148和四个10k上拉。
2. 第2页：屏幕端向上的底面焊接视图，左右已镜像；开关电触点C/A是项目分配，不是实际机械脚位。
3. 第3页：Pico 2元件面/USB向上、14个已用物理针脚、LCD五线和四个上拉。
4. 第4页：GDM0103显示面与背面端子镜像、五根导线逐一对照及低位焊接说明。LCD P1–P9与Pico物理P1–P40分别标注，不能混用。

LCD：P1 /CS→GP11/物理15；P2 /WR→GP1/物理2；P3 DATA→GP0/物理1；P4 VSS→GND/物理38；P5 VDD→3V3(OUT)/物理36。P6 /INT、P7 BL+、P8 BL-、P9 Ctrl分别绝缘，不接外部线。三线写入，不是I²C；无Grove座改装、无四芯OLED线、无背光连线。NC不表示模块内部所有端子间都必须测为OL。

矩阵：列C→开关→二极管无环A→黑环K→行R。每列一只10k上拉到3V3；行不是GND。无实心圆点的行列交叉不连接，保持绝缘。Pico上拉电源端与LCD VDD共用3V3；不接VBUS、VSYS。线色只用于图示分类，实际靠端子标签核对。

LCD不装直立排针，P1–P5低位直焊；板背焊点/首段软线突出≤1.5mm，朝内折。矩阵九根主线与LCD五线各留约150mm维护余量。四处PCB边缘托架用0.15mm绝缘胶片，实物先确认空白承托带；先焊线检查，后粘PCB，不挤玻璃。无悬空焊点靠拉线承力，底盖完全分离仍需断开焊线。

配合更新后的九页A4断电焊接指南和五张空白实测表。散件/独立矩阵/加上拉/连接模块后的测量条件不同；不能在接Pico/LCD后要求列间严格20k或所有网络OL。所有实物项目仍待测，本图不是PCB或钻孔模板。

依据：Pico 2官方数据表PDF第5页图2（https://pip.raspberrypi.com/documents/RP-008299-DS）；厂商署名GDM0103手册PDF第7页外形/端子朝向、第8页针表（https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf）；Vishay 1N4148 PDF第1页黑环K（https://www.vishay.com/docs/81857/1n4148.pdf）。生成时核对现有wiring.json和真实board_config.hpp的矩阵、LCD DATA/WR/CS常量。

重新生成：reportlab==4.4.3，CALCKEY_DIAGRAM_FONT可选中文TrueType字体；默认macOS Arial Unicode。脚本只生成文档，不写接线、器件清单或固件。
"""
(OUT/'README.md').write_text(readme)
manifest={'version':'LCD-B','firmware':'0.2.0','display':'GDM0103 / HT1621B 3.3V',
          'wiring_sha256':wiring_hash,'firmware_config_sha256':hashlib.sha256(board_source.encode()).hexdigest(),
          'keys':20,'diodes':20,'column_pullups':4,'lcd_connected_pads':5,'lcd_nc_pads':4,'pico_used_pins':14,'pages':4,
          'netlist_checks':'20 branches, 4 pullups, 5 LCD nets, 4 NC pads and actual firmware constants matched',
          'physical_assembly_tested':False,'flashed':False,'artifacts':{}}
for item in sorted(OUT.iterdir()):
    if item.suffix in ('.pdf','.svg','.csv','.md'):
        manifest['artifacts'][item.name]={'bytes':item.stat().st_size,'sha256':hashlib.sha256(item.read_bytes()).hexdigest()}
(OUT/'drawing-record.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(ROOT/'product/calckey-wiring-guide.zip','w',zipfile.ZIP_DEFLATED) as z:
    for item in sorted(OUT.iterdir()):
        if item.is_file():z.write(item,'CalcKey-Wiring/'+item.name)
print('Generated 4-page GDM0103 A3 PDF, 4 SVGs, 20-key and LCD CSVs; current package replaced.')
print('Electrical graph checks passed; wiring.json unchanged:',wiring_hash)
