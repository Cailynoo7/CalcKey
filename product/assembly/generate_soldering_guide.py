#!/usr/bin/env python3
"""Build a matching printable procedure and blank records; never edits hardware.

Dependency: reportlab==4.4.3. Run with the same PYTHONPATH as the wiring sheets.
CALCKEY_DIAGRAM_FONT may override the CJK TrueType font.
"""
import csv
import hashlib
import html
import io
import itertools
import json
import os
from pathlib import Path
import zipfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DIAGRAMS = ROOT / 'product/diagrams'
WIRING = ROOT / 'design/enclosure/source/wiring.json'
NETLIST = json.loads(WIRING.read_text())
WIRING_HASH = hashlib.sha256(WIRING.read_bytes()).hexdigest()
with (DIAGRAMS / 'soldering-map.csv').open(encoding='utf-8-sig', newline='') as f:
    KEYS = list(csv.DictReader(f))
assert len(KEYS) == 20
CONNECTIONS = NETLIST['connections']
def connected(a, ap, b, bp):
    return any(c['from'] == {'part': a, 'pin': ap} and c['to'] == {'part': b, 'pin': bp}
               for c in CONNECTIONS)

for n, k in enumerate(KEYS, 1):
    r, c = divmod(n - 1, 4)
    assert k['switch'] == f'SW{n:02}' and k['diode'] == f'D{n:02}'
    assert (int(k['row']), int(k['col'])) == (r, c)
    assert connected('MCU', f'GP{c+7}', k['switch'], '1')
    assert connected(k['switch'], '2', k['diode'], 'A')
    assert connected(k['diode'], 'K', 'MCU', f'GP{r+2}')

PIN = {'GP0':1, 'GP1':2, 'GP2':4, 'GP3':5, 'GP4':6, 'GP5':7,
       'GP6':9, 'GP7':10, 'GP8':11, 'GP9':12, 'GP10':14, 'GP11':15, '3V3':36, 'GND':38}
WIRES = [(f'R{i}', f'GP{i+2}', PIN[f'GP{i+2}'], f'R{i}行：四只二极管K') for i in range(5)]
WIRES += [(f'C{i}', f'GP{i+7}', PIN[f'GP{i+7}'], f'C{i}列：五个开关C触点及RPU{i}') for i in range(4)]
LCD_WIRES=[('/CS','GP11',15,'LCD P1 /CS'),('/WR','GP1',2,'LCD P2 /WR'),
           ('DATA','GP0',1,'LCD P3 DATA'),('3V3','3V3',36,'绝缘分支到四个上拉公共端和LCD P5 VDD'),
           ('GND','GND',38,'LCD P4 VSS')]
WIRES += LCD_WIRES
assert len(WIRES)==14
for name,gpio,physical,dest in LCD_WIRES:
    assert PIN[gpio]==physical

for c in range(4):
    assert connected('MCU', '3V3', f'RPU{c}', '1')
    assert connected(f'RPU{c}', '2', 'MCU', f'GP{c+7}')
for gpio,pad in [('GP11','P1 /CS'),('GP1','P2 /WR'),('GP0','P3 DATA'),('GND','P4 VSS'),('3V3','P5 VDD')]:
    assert connected('MCU',gpio,'LCD',pad)
assert len([c for c in CONNECTIONS if any(c[e]['part']=='LCD' for e in ['from','to'])])==5
assert not any(p['ref']=='OLED' for p in NETLIST['parts'])
DRAWING=json.loads((DIAGRAMS/'drawing-record.json').read_text())
assert DRAWING['wiring_sha256']==WIRING_HASH and DRAWING['pages']==4

PAGES = []
def page(title, subtitle):
    p = {'title': title, 'subtitle': subtitle, 'blocks': []}
    PAGES.append(p)
    return p['blocks']
def text(blocks, value): blocks.append(('p', value))
def heading(blocks, value): blocks.append(('h', value))
def table(blocks, headers, rows, widths): blocks.append(('table', headers, rows, widths))

b = page('01  开工准备与读图', '目标：分段焊接、分段断电测量；本手册结束时仍不插USB、不烧录。')
text(b, '适用版本：Pico 2、5行×4列、20只1N4148、4只10kΩ外部列上拉、GDM0103/HT1621B八位LCD，3.3V版本；外接USB供电，无电池。配合四页焊接图使用。所有记录初始均为“待测”，文档检查不等于实物验收。')
heading(b, '1.1  先断开，再测量')
text(b, '拔掉电脑、充电器、调试器及其他外部连接。Pico、LCD和按键矩阵先彼此分离。若曾通电，先用直流电压档确认3V3—GND、LCD P5 VDD—P4 VSS无残余电压，再换Ω档、蜂鸣档或二极管档；不要用金属工具短接电容放电。')
text(b, '黑表笔插COM、红表笔插V/Ω孔，勿插电流孔。Ω档短接两表笔，记录稳定的表线基准电阻R0：____Ω。后文“直连低阻”指读数接近该基准且稳定；蜂鸣只能辅助判断。OL表示该量程未导通，不等于一次完整绝缘验收。')
heading(b, '1.2  核对材料和工具')
text(b, '电子件：20轴、20只DO-35玻璃封装1N4148（非W/WS贴片型）、4只10kΩ±1%电阻、Pico 2、已选3.3V GDM0103、五根LCD软线及四片0.15mm绝缘安装胶。布线用已选26AWG绝缘软线及内径2/3mm热缩管；先试套管能否跨过焊点并收紧，不能仅按标称内径认定适配。')
text(b, '工具：可调温烙铁、适配焊锡与电子助焊剂、吸锡带或吸锡器、剥线钳、斜口钳、尖嘴钳、镊子、放大镜、带二极管/电阻/蜂鸣档的万用表和受控热风工具。焊烟避开呼吸区；烙铁放回支架。温度按实际焊锡、助焊剂和器件工艺选择，不用一套固定温度覆盖所有焊点。')
heading(b, '1.3  图纸方向和电气编号')
text(b, '原图第1页为正面；第2页为底面，屏幕端仍向上，左右已镜像，不要再镜像一次。底面最上排从左到右是SW04、SW03、SW02、SW01，对应C3、C2、C1、C0。第3页Pico为元件面朝上、USB端向上；若翻到板背焊接，左右也相反。实装USB位于机身右侧，要以实物USB与针1对齐后读图；GPIO编号不等于物理针脚号。')
text(b, '每轴仅使用两个实际开关触点：项目定义一个为C（开关1，接列），另一个为A（开关2，接二极管A）。真实左右脚需用实物确认；塑料柱及其他未用脚不参与布线。固定连接为：列C → 开关 → 二极管A无环端 → K黑环端 → 行R。')

b = page('02  散件检查与首键试焊', '保持Pico、LCD、上拉电阻和行列总线均未连接。')
heading(b, '2.1  焊前逐件测量')
table(b, ['器件/档位', '操作', '应见结果'], [
    ['20个开关；Ω档', '两表笔夹住两个实际触点；松开、按下、松开各测一次。', '松开OL；按下接近表线基准，反复动作稳定。'],
    ['20只二极管；二极管档', '红笔接无环A，黑笔接黑环K；再交换表笔。', '正向有压降，常见约0.5–0.8V；反向OL。以本表与良品比较。'],
    ['4只10k；Ω档', '单独测两端，不接公共电源轨或主控。', '标称±1%范围9.9–10.1kΩ，结合仪表精度判断。']
], [100, 205, 218])
text(b, '把散件测值记入“元件检查表”。LCD焊线前、Pico接线前，分别记录其电源对地Ω档读数及是否随时间上升，供后面对照；真实电路没有统一的“必须OL/必须某Ω”门槛。')
heading(b, '2.2  先只做SW01＋D01')
text(b, '① 按面板实际方向放置并确认SW01位置与两个电触点，翻到底面仍保持屏幕端向上。检查轴已正确就位、活动不受阻；这一步是实物试装，不能由示意图代替。')
text(b, '② 先剪取并穿入合适热缩管，退到远离热源的位置。用钳子支撑二极管引脚再弯折，避免拿玻璃管体当杠杆；留出玻璃端附近的直线段，不紧贴管体急弯。黑环K暂时保留，供后面并入行线。')
text(b, '③ 轻微预上锡，将D01无环A端与SW01指定A触点连接。烙铁同时接触引脚与导体，让焊锡润湿两者，撤热后保持不动直至凝固。焊点应有连续润湿面、无裂纹和锡桥；无铅焊点不一定发亮。失败时先冷却、补助焊剂后返工，勿持续烘烤塑料面板或轴体。')
text(b, '④ 冷却后检查玻璃无裂纹、触点无松动。红表笔接SW01剩余C触点，黑表笔接D01黑环K：松开应OL，按下应出现单只二极管压降；按住并交换表笔应OL。此时若不符，先修好这一个键。')
text(b, '⑤ 首键通过后再做其余19键，方法相同。一键一检，先不并总线。确认后覆盖裸露A接头的套管，保留黑环可识别；K端随后接行线，不能提前封死接点。')
heading(b, '过关后再进行下一页')
text(b, '[ ] 20个开关和20只二极管已逐件测量；[ ] 4个电阻已测；[ ] 首键三态测试通过；[ ] 其余19个单键支路通过。记录不合格件编号，不将疑问带入后续布线。')

b = page('03  五行、四列的逐组焊接', '关键前提：本页及下一页测量时，还没装上拉、没接Pico、没接LCD。')
heading(b, '3.1  先并行线：只连接同一行的K黑环端')
table(b, ['行', '同一行四个二极管K', '留给主控的行引线'], [
    [f'R{r}', '、'.join(f'D{r*4+c+1:02}' for c in range(4)), f'GP{r+2}；物理针脚{PIN[f"GP{r+2}"]}']
    for r in range(5)
], [45, 263, 215])
text(b, '① 用短段绝缘软线依次连接该行四个K端，只有焊接处剥皮。每个焊点所需套管先穿好；不采用长段裸铜跨越其他网络。② 每完成一行，测四个K端之间直连低阻，并轻动线材检查读数稳定。③ 五行之间保持独立，所有键松开时，任意两行之间Ω档应OL。')
heading(b, '3.2  再并列线：连接每列剩下的C触点')
table(b, ['列', '同一列五个开关C触点', '留给主控的列引线'], [
    [f'C{c}', '、'.join(f'SW{r*4+c+1:02}' for r in range(5)), f'GP{c+7}；物理针脚{PIN[f"GP{c+7}"]}']
    for c in range(4)
], [45, 263, 215])
text(b, '① 同样使用绝缘短线分段连接。行列交叉处保留两根线各自的完整绝缘；若裸引脚可能碰到，给至少一侧完整套管或改变走线。图上无连接圆点的交叉不能焊在一起。② 每列五个C触点应直连低阻。③ 所有键松开，四列两两之间Ω档应OL。')
heading(b, '3.3  逐键检验，不能只做蜂鸣测试')
text(b, '全部其他键松开；按下一页逐键表：红笔接对应C列，黑笔接对应R行。松开目标键应OL；按下应有二极管压降；保持按下并换表笔应OL。每键记录三个读数，检查后释放该键再测下一个。')
text(b, '全部键松开，额外检查20组C—R组合均无导通；检查10组行—行和6组列—列均未短接。确认全部通过，再装四个上拉。这一阶段没有公共电源轨导致的列间通路。')

b = page('04  逐键测量位置速查', '仅适用于未装上拉、未接Pico/LCD的独立矩阵；所有其他键均松开。')
text(b, '二极管档三项：① 红C/黑R且松开＝OL；② 红C/黑R且按下＝正向压降；③ 红R/黑C且按下＝OL。逐键实际读数写入“20键检查表”，本表只定位，不代表已测。')
table(b, ['键号', '键帽', '二极管', '红笔C列', '黑笔R行', '状态'], [
    [k['switch'], k['label'], k['diode'], f'C{k["col"]}', f'R{k["row"]}', '待测'] for k in KEYS
], [64, 102, 67, 101, 101, 88])
text(b, '按键触点C/A是项目命名，不规定真实引脚朝向。电气通路必须经过这一个开关和这一个二极管，不能用锡桥绕过任一元件。通过后再收紧已完成接头的套管；留出后续接线位置。')

b = page('05  四个外部上拉与电阻复测', '上拉公共端暂时悬空，不接Pico 3V3、LCD或外部电源。')
heading(b, '5.1  每列一个10kΩ，不能省略或串错')
text(b, '① 把已单测的RPU0至RPU3分别接到C0至C3列。② 将四个电阻的另一端用绝缘导线并成“3V3上拉公共端”，标签写明3V3，但本阶段不接主控。③ 电阻本体与引脚不承担拉力；裸接头逐个套管，公共分支不能有外露铜丝。LCD使用三线GPIO写入，四个10k仅用于矩阵列上拉，不加到DATA、/WR或/CS。')
table(b, ['电阻', '列侧', '公共侧', '隔离状态Ω档预期'], [
    [f'RPU{c}', f'C{c} / GP{c+7}', '3V3上拉公共端', '9.9–10.1kΩ'] for c in range(4)
], [70, 135, 160, 158])
heading(b, '5.2  现在列与列约20kΩ是正常的')
text(b, '路径为：C0 → RPU0 10k → 公共端 → RPU1 10k → C1。即使不通电，四列已通过电阻相连，所以不能沿用“列间必须OL”的早期判断。按Ω档测六组列对：')
table(b, ['列对', '预期（两只±1%电阻之和）', '记录'], [
    [f'C{a} — C{c}', '约20kΩ；19.8–20.2kΩ', '待测'] for a, c in itertools.combinations(range(4), 2)
], [130, 280, 113])
text(b, '以上范围是元件公差的名义范围，应叠加万用表精度；接近边界先复核仪表及单件，不能武断判坏。远低于10k或20k时先查错值、锡桥；OL则查漏焊或断线。所有键松开时，行与行、行与列仍应无直接通路。')
heading(b, '5.3  主控连接前封存矩阵结果')
text(b, '[ ] 四只阻值及六组列间值记录完毕；[ ] 20键三态检查已通过；[ ] 套管覆盖裸接头并搭接完整线皮；[ ] 未残留剪下的引脚、锡渣；[ ] 所有电源仍断开。连接Pico后，芯片保护电路会影响这些阻值，不能原封不动套用本页范围。')

b = page('06  GDM0103五线直焊与四端悬空', '模块单独处理：3.3V版本，所有外部电源、Pico和矩阵仍断开。')
heading(b, '6.1  找P1标记，辨别显示面与背面')
text(b, '对照图纸第4页和厂商手册第7/8页：按图纸显示方向，显示面P1在左侧上端；保持上边朝上翻到底面后，P1在右侧上端。先以实物P1丝印和端子信号确认，不能靠线色、排针朝向或板上脚距猜。若订单/实物不是3.3V GDM0103，暂不连接Pico；不要用5V版直接替代。')
text(b, '本版为P1–P5五根软线直焊，不使用转接插座。先记录模块P5 VDD—P4 VSS的断电Ω档基准、初始及稳定趋势；该读数无统一OL或固定阻值门槛。把五根导线两端同时贴上LCD端子/Pico GPIO与物理针号标签。')
table(b, ['LCD端子', '功能', 'Pico去向', '焊后检查'], [
    ['P1', '/CS', 'GP11 / 物理15', 'P1焊盘到对应远端直连低阻'],
    ['P2', '/WR', 'GP1 / 物理2', 'P2焊盘到对应远端直连低阻'],
    ['P3', 'DATA', 'GP0 / 物理1', 'P3焊盘到对应远端直连低阻'],
    ['P4', 'VSS', 'GND / 物理38', 'P4焊盘到对应远端直连低阻'],
    ['P5', 'VDD', '3V3(OUT) / 物理36', 'P5焊盘到对应远端直连低阻'],
], [66, 61, 162, 234])
heading(b, '6.2  低位直焊，先测通后绝缘')
text(b, '① 本版不用直立排针；若模块已焊排针，支撑PCB、逐脚退锡，确认插脚自由后移除，不撬焊盘或玻璃。② 预穿套管、剥最少必要长度，逐根焊P1–P5，线根向板内低位折。焊点与首段软线突出板背≤1.5mm，实测记录；每根约150mm维护余量。③ 每焊一根，量该焊盘到已标注的线束远端直连低阻，轻动仍稳定；放大检查相邻焊盘无新增锡桥。确认后覆盖裸接头，线束在PCB以外另作应力释放。')
text(b, 'P6 /INT、P7 BL+、P8 BL-、P9 Ctrl不焊外部线、不并到3V3/GND、不相互短接。若有伸出金属端，分别套绝缘，不能只用一根大套管把四端裹在一起。NC只指外部不连接，不要求模块内部任意两脚测为OL，也不对玻璃电极或驱动器细脚直接探测。')
heading(b, '6.3  支架干装，最后再粘PCB')
text(b, '复测P5—P4电阻趋势，与焊前基准比较；持续新增近零值时保持断电并排查锡桥。先完成焊线与测量，再在四个PCB边缘座面贴0.15mm绝缘胶片；两侧承托带须无元件/裸铜，线根不占座面，玻璃与保护片不受压。若背面凸起或线头超出空间，先调整，不用胶或合盖螺钉强压。')

b = page('07  最后连接Pico 2', 'Pico元件面朝上、USB端向上读物理针号；焊接中不插USB。')
text(b, '先做九根行列信号引线，逐根标R0–R4/C0–C3，再做LCD五线与3V3分支。九根矩阵线各按原方案留约150mm柔性维护余量，实际折返沿空隙安放；“九根”不包括LCD五根线和上拉电源分支。')
table(b, ['网络', 'Pico信号', '物理针', '另一端'], [[a, g, str(p), dest] for a, g, p, dest in WIRES], [49, 85, 45, 344])
heading(b, '7.1  每根线都按同一动作完成')
text(b, '① 对照图第3页和实物针1方向，手指定位目标焊盘；不要按GP号数物理脚。② 先穿热缩管、剥最少必要长度，绞齐软线细股、轻微预上锡。③ 焊一根就测主控焊盘到远端接头的直连低阻，并检查邻脚锡桥；所有测量保持断电。④ 冷却后轻动线材，读数应稳定，确认后再完成绝缘。不要把锡桥是否发亮作为唯一检查。')
text(b, '物理36的3V3用绝缘分支分别接上拉公共端和LCD P5 VDD；物理38接LCD P4 VSS。矩阵行线不是GND，不要把五行并成地。使用3V3(OUT)，不改接5V VBUS或VSYS。绝缘分支不能靠焊锡形成长悬臂承受拉力。')
text(b, '本页14个Pico针脚全部核对后，在“主线与LCD检查表”填实际导通值、邻脚外观和状态。LCD五线直接测到P1–P5焊盘；P6–P9逐个填未接线/已绝缘外观结果，不拿模块内部阻值强求OL。')

b = page('08  绝缘收尾与整机断电检查', '不插电脑、不插充电器；普通万用表检查，不使用高压绝缘表。')
heading(b, '8.1  每个接头和每个交叉处')
text(b, '① 确认焊点已测且冷却，再将套管推到位，覆盖裸铜并搭接两侧完整线皮；2/3mm管径以实际缩后贴合为准，松动或遮不全就换合适尺寸。② 使用受控热风逐处收缩，避开玻璃屏、排线、轴体和打印壳，不用明火。③ 玻璃二极管黑环仍可辨识；行列交叉保持绝缘，线材不磨在剪尖引脚上。④ 剪去尖锐多余脚，清走所有碎线、引脚和锡渣。')
heading(b, '8.2  直连网络与电源检查')
text(b, '逐根复查14个已用Pico针脚到目标接头的直连低阻，缓慢轻动导线，确认无间歇开路。对疑似邻脚锡桥先放大观察，再测阻值；主控与LCD已连接时，内部半导体会形成其他路径，不能要求任意不同网络都显示OL。')
text(b, 'Ω档量3V3—GND，记录初始值、约10秒后值及换表笔情况；这10秒仅用于观察趋势，不是统一电路指标。电容可能造成短暂蜂鸣或读数爬升，不能据此直接判短路。若持续接近表线短接值，保持断电，先断开LCD线束，再分离上拉电源支路、矩阵GPIO线，逐段与前面独立测量比较，定位新增低阻；不要用通电冒烟来定位。')
text(b, '连接主控后的列间电阻不必严格等于20k；二极管的在路反向读数也可能变化。怀疑某键时，先把矩阵的九根GPIO线及上拉公共电源端与主控/LCD完全隔离，再回到第3–5页对应测试状态，不在未知并联路径中直接判元件损坏。')
heading(b, '8.3  合盖前后各查一次')
text(b, '全部按键用手按到底，确认线束不进入活动区域；确认LCD玻璃边沿和板背焊线、USB口附近无受压线。底盖由手托住缓慢下放约30mm，检查各线仍有余量、接头不受拉，再折返收好。此余量用于维护，底盖完全拆离仍需断开手焊线。不要把线压在螺柱、壳边或折叠支脚活动路径里。')
text(b, '合盖时逐步贴合，遇阻先查线，不用螺丝强行压紧。盖好后再测3V3—GND并与合盖前比较，抽查轻动/按键时有无新增直连低阻或接触不良。新问题应开盖排查。')
heading(b, '断电检查完成签名（用户实测后填写）')
text(b, '[ ] 元件、20键、上拉、LCD五线和四个NC端、14主线记录齐全；[ ] 裸铜/交叉点已绝缘；[ ] 合盖无夹线；[ ] 无新增电源持续近零阻。操作者：____ 日期：____ 结果：待测 / 通过 / 待返工。检查结束仍保持断电，尚未进行烧录与功能验收。')

b = page('09  异常定位与记录说明', '先确认所处测试阶段，再解释读数；只返工定位到的支路。')
table(b, ['现象（隔离矩阵时）', '优先检查'], [
    ['按下时正向、反向都OL', '表笔接触；C/R接错；开关触点选错；断线/虚焊；二极管开路。单独复测开关和二极管。'],
    ['按下仅红R/黑C有压降', '该键二极管方向反了；核对无环A接开关、黑环K接行。'],
    ['按下双向接近零', '锡桥绕过二极管或二极管短路；拆开一端复测。'],
    ['松开仍有该键正向压降', '开关被旁路或触点卡住；所有其他键是否确实松开。'],
    ['整行/整列都测不到', '公共行/列引线断开；行列编号或底面方向认错。'],
    ['未装上拉时列间低阻', '列线误焊一起或裸铜交叉接触。'],
    ['装上拉后列间约20k', '正常：经两只10k串联；保持Pico/LCD隔离才使用此范围。'],
    ['最终电源持续近零阻', '保持断电，按LCD→上拉电源→矩阵GPIO顺序隔离，再与独立模块基准比较。']
], [180, 343])
heading(b, '记录表怎么填写')
text(b, '“元件检查表”记录20轴、20二极管、4电阻；“20键检查表”记录独立矩阵的三态；“上拉检查表”记录4只电阻和6组列对；“主线与LCD检查表”记录14个Pico去向、4个NC端的逐个外观检查；“阶段检查表”记录断电、电源基准、绝缘与合盖结果。填实际值和单位，状态改为通过/返工，别只填“响/不响”。')
text(b, '指南与记录由同一生成脚本制作，并核对20键、4上拉和LCD五线与现有接线记录一致。接线图第2页为已镜像底面示意，不是轴体脚位模板。原图纸与逐键焊接表随操作包附带。')
heading(b, '依据与适用边界')
text(b, '引脚与部件依据沿用现有图纸：Pico 2官方数据表PDF第5页；GDM0103厂商手册PDF第7页外形/朝向与第8页端子表；Vishay 1N4148数据表第1页黑环K。测量方法参照Fluke的二极管测试说明：断电、正反两向测，在路并联路径可能影响读数。URL与接线指纹见随附说明和生成记录。')
text(b, 'LCD低位直焊、边缘承托带、套管实际贴合、30mm开盖余量、按键活动和合盖检查均要在实物完成；当前不能据文档宣称已经通过。上电后的功耗、USB识别、20键键值、计算与显示功能，属于后续烧录联调，本次不执行。')

FONT = Path(os.environ.get('CALCKEY_DIAGRAM_FONT', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('Guide', str(FONT)))
STYLES = {
    'title': ParagraphStyle('title', fontName='Guide', fontSize=19, leading=26, textColor=colors.HexColor('#173c59'), spaceAfter=7, wordWrap='CJK'),
    'subtitle': ParagraphStyle('subtitle', fontName='Guide', fontSize=10, leading=15, textColor=colors.HexColor('#526979'), spaceAfter=12, wordWrap='CJK'),
    'h': ParagraphStyle('h', fontName='Guide', fontSize=12, leading=18, textColor=colors.HexColor('#1b608b'), spaceBefore=8, spaceAfter=5, wordWrap='CJK', keepWithNext=True),
    'p': ParagraphStyle('p', fontName='Guide', fontSize=10, leading=16, spaceAfter=8, wordWrap='CJK'),
    'cell': ParagraphStyle('cell', fontName='Guide', fontSize=9, leading=13, wordWrap='CJK'),
    'th': ParagraphStyle('th', fontName='Guide', fontSize=9, leading=13, textColor=colors.white, wordWrap='CJK'),
}
def para(s, style='p'): return Paragraph(html.escape(s), STYLES[style])
md = ['# CalcKey 逐步焊接、绝缘与断电检查', '',
      '使用状态：操作指南与空白记录；所有实物项目待测。沿用当前GPIO、20键布局和四页焊接图，不改固件，不进行烧录或上电。', '']
story = []
for i, p in enumerate(PAGES):
    if i: story.append(PageBreak())
    story.extend([para(p['title'], 'title'), para(p['subtitle'], 'subtitle')])
    md.extend(['## ' + p['title'], '', p['subtitle'], ''])
    for block in p['blocks']:
        if block[0] in ('p', 'h'):
            story.append(para(block[1], block[0]))
            md.extend([('### ' if block[0] == 'h' else '') + block[1], ''])
        else:
            _, headers, rows, widths = block
            # Usable A4 width is 523pt with margins36pt.
            assert sum(widths) == 523
            t = Table([[para(v, 'th') for v in headers]] + [[para(v, 'cell') for v in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1b608b')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#edf3f7'), colors.white]),
                ('GRID', (0,0), (-1,-1), .4, colors.HexColor('#c7d4de')),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 7), ('RIGHTPADDING', (0,0), (-1,-1), 7),
                ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.extend([t, Spacer(1, 9)])
            md += ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
            md += ['| ' + ' | '.join(row) + ' |' for row in rows]
            md += ['']

page_count = [0]
def footer(c, doc):
    page_count[0] = max(page_count[0], doc.page)
    c.setStrokeColor(colors.HexColor('#cfdae3')); c.line(36, 38, 559, 38)
    c.setFont('Guide', 8); c.setFillColor(colors.HexColor('#526979'))
    c.drawString(36, 25, 'CalcKey | 断电焊接检查指南 | 实物待测 | 接线指纹 ' + WIRING_HASH[:12])
    c.drawRightString(559, 25, str(doc.page))

pdf_path = OUT / 'calckey-soldering-procedure.pdf'
SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=36, rightMargin=36,
                  topMargin=35, bottomMargin=49, title='CalcKey 逐步焊接、绝缘与断电检查',
                  author='CalcKey project').build(story, onFirstPage=footer, onLaterPages=footer)
assert page_count[0] == len(PAGES), f'Unexpected page overflow: {page_count[0]} != {len(PAGES)}'
(OUT / 'soldering-procedure.md').write_text('\n'.join(md), encoding='utf-8')

def csvfile(name, fields, rows):
    path=OUT/name
    key=next((k for k in ['id','switch','item','check'] if k in fields))
    if path.exists():
        with path.open(encoding='utf-8-sig',newline='') as f: old={r[key]:r for r in csv.DictReader(f)}
        keep=['actual','reading_1','reading_2','released_actual','pressed_forward_actual',
              'pressed_reverse_actual','continuity_actual','wire_color','operator','date','appearance']
        for row in rows:
            prev=old.get(row[key])
            if prev:
                filled=any(prev.get(k) for k in keep) or prev.get('status','待测')!='待测'
                if filled:
                    for k in keep+['status','notes']:
                        if k in fields and prev.get(k):row[k]=prev[k]
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

raw = []
for k in KEYS:
    raw += [dict(id=k['switch'], type='开关', isolated='未焊散件', expected='松开OL；按下直连低阻', reading_1='', reading_2='', status='待测', notes=''),
            dict(id=k['diode'], type='1N4148', isolated='未焊散件', expected='红A黑K有压降；反向OL', reading_1='', reading_2='', status='待测', notes='')]
raw += [dict(id=f'RPU{c}', type='10k±1%', isolated='未焊散件', expected='9.9–10.1kΩ＋仪表误差', reading_1='', reading_2='', status='待测', notes='') for c in range(4)]
csvfile('component-check-record.csv', ['id','type','isolated','expected','reading_1','reading_2','status','notes'], raw)

keyrows = []
for k in KEYS:
    keyrows.append(dict(switch=k['switch'], label=k['label'], diode=k['diode'],
        red=f'C{k["col"]}', black=f'R{k["row"]}',
        condition='不接Pico/LCD/上拉；其余键松开', released_expected='OL', released_actual='',
        pressed_forward_expected='单只二极管正向压降', pressed_forward_actual='',
        pressed_reverse_expected='OL（交换表笔）', pressed_reverse_actual='', status='待测', notes=''))
csvfile('key-check-record.csv', list(keyrows[0]), keyrows)

resistors = [dict(item=f'RPU{c}', points=f'C{c}—上拉公共端', condition='Pico/LCD/电源均不接；上拉已装', expected='9.9–10.1kΩ＋仪表误差', actual='', status='待测', notes='') for c in range(4)]
resistors += [dict(item=f'C{a}—C{c}', points=f'C{a}—C{c}', condition='Pico/LCD/电源均不接；上拉已装', expected='19.8–20.2kΩ＋仪表误差', actual='', status='待测', notes='') for a,c in itertools.combinations(range(4),2)]
csvfile('pullup-check-record.csv', list(resistors[0]), resistors)

wire_rows = [dict(item=a, pico_gpio=g, pico_physical_pin=p, endpoint=dest,
                 wire_color='', continuity_expected='直连低阻且轻动稳定', continuity_actual='',
                 appearance='', status='待测', notes='') for a,g,p,dest in WIRES]
for pad,signal in [('P6','/INT'),('P7','BL+'),('P8','BL-'),('P9','Ctrl')]:
    wire_rows.append(dict(item=f'LCD NC-{pad}',pico_gpio='',pico_physical_pin='',
        endpoint=f'LCD {pad} {signal}：不接外部线，端头单独绝缘',wire_color='',
        continuity_expected='不适用：外观核对无新增外部连接',continuity_actual='',appearance='',
        status='待测',notes='不要求模块内部端子之间均为OL'))
csvfile('wire-check-record.csv', list(wire_rows[0]), wire_rows)

stages = [
    ('01', '全部外部电源/调试器断开；DC档确认无残压'),
    ('01', '万用表表笔短接基准R0（Ω）'),
    ('02', 'Pico单独3V3—GND基准：初始/稳定读数与变化'),
    ('02', 'LCD焊线前P5 VDD—P4 VSS基准：初始/稳定读数与变化'),
    ('02', 'SW01+D01首键三态通过；其余19个单键支路通过'),
    ('03', '五行各四个K端直连低阻；行与行10组隔离'),
    ('03', '四列各五个C触点直连低阻；列与列6组隔离（未装上拉）'),
    ('03', '全松开20组C—R均OL（无上拉/主控/LCD）'),
    ('04', '20键三态实测记录齐全'),
    ('05', '4个上拉＋6组列对实测记录齐全'),
    ('06', 'LCD焊线后电源阻值与原基准比较'),
    ('06', 'LCD五根导线逐根实测；P6–P9分别绝缘；板背突出≤1.5mm'),
    ('07', 'Pico 14针逐根复核；GPIO/物理针号无混淆'),
    ('08', '全部接头套管/交叉绝缘；无裸股、尖脚、锡渣'),
    ('08', '整机合盖前3V3—GND：初始/约10秒/换表笔'),
    ('08', '按键到底无干涉；底盖下放约30mm无线材受拉'),
    ('08', '合盖后电源阻值与合盖前对照；无夹线'),
    ('08', '检查结束保持断电；没有烧录或上电功能验收'),
]
csvfile('stage-check-record.csv', ['stage','check','actual','status','operator','date','notes'],
        [dict(stage=s, check=x, actual='', status='待测', operator='', date='', notes='') for s,x in stages])

SOURCES = [
    ('Pico 2物理针脚：官方数据表PDF第5页图2', 'https://pip.raspberrypi.com/documents/RP-008299-DS'),
    ('GDM0103厂商手册PDF第7/8页：端子及方向', 'https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf'),
    ('Vishay 1N4148黑环K：PDF第1页', 'https://www.vishay.com/docs/81857/1n4148.pdf'),
    ('Fluke：断电与二极管正反向测量/在路影响', 'https://www.fluke.com/en-gb/learn/blog/digital-multimeters/how-to-test-diodes'),
    ('Kester FAQ：工艺温度取决于焊接材料', 'https://www.kester.com/knowledge-base/faq'),
]
readme = '# CalcKey GDM0103断电焊接操作包（LCD-B / 固件v0.2.0）\n\n'
readme += f'提供{page_count[0]}页A4打印指南、同内容Markdown和5张可填写CSV记录表。CSV以UTF-8 BOM编码，所有实物状态均为“待测”。配合4页A3接线图；操作包中附有该PDF、四张SVG、逐键表及9端子LCD对照表。\n\n'
readme += '顺序：断电与散件检查 → 单键试焊 → 行列总线 → 20键隔离测量 → 四个上拉 → LCD端子识别/五线直焊/四端绝缘 → Pico最后接入 → 绝缘与合盖断电复查。\n\n'
readme += '先做独立矩阵三态测试，再接主控。装上拉后，独立矩阵列间约20kΩ正常；接主控/LCD后不再强求该阻值或任意网络OL。二极管用二极管档确认，蜂鸣不代替正反向测试。详细表笔位置、条件和返工定位见指南。\n\n'
readme += '本操作包不改接线、器件、固件或外壳，也未完成任何实物焊接、绝缘或测量；不执行烧录或通电。依赖安装位置不固定时，设置PYTHONPATH指向含reportlab的环境，再运行generate_soldering_guide.py；版本reportlab==4.4.3，字体可用CALCKEY_DIAGRAM_FONT指定中文TrueType。\n\n'
readme += '## 依据\n\n' + '\n'.join(f'- {name}：{url}' for name,url in SOURCES) + '\n'
(OUT / 'README.md').write_text(readme, encoding='utf-8')

deliverables = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'procedure-record.json')
record = {'title':'CalcKey GDM0103 soldering, insulation and unpowered checks', 'version':'LCD-B', 'firmware':'0.2.0',
          'wiring_sha256':WIRING_HASH, 'pdf_pages':page_count[0],
          'key_branches_checked':len(KEYS), 'external_pullups_checked':4, 'pico_pins_checked':len(WIRES),
          'record_rows':{'components':len(raw),'keys':len(keyrows),'pullups_and_pairs':len(resistors),'wires_and_lcd_nc':len(wire_rows),'stages':len(stages)},
          'physical_assembly_tested':False, 'flashed':False, 'lcd_connected_pads':5, 'lcd_nc_pads':4, 'physical_record_initial_status':'待测',
          'sources':[{'title':n,'url':u} for n,u in SOURCES],
          'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in deliverables}}
(OUT / 'procedure-record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
package = ROOT / 'product/calckey-soldering-procedure.zip'
with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):
        if p.is_file(): z.write(p, 'assembly/' + p.name)
    for name in ['calckey-wiring-guide.pdf','01-matrix-front.svg','02-backside-soldering.svg','03-pico-lcd-pullups.svg','04-lcd-front-back-wiring.svg','soldering-map.csv','lcd-wiring-map.csv','README.md','drawing-record.json']:
        z.write(DIAGRAMS/name, 'wiring-reference/' + name)
print(json.dumps({'pdf_pages':page_count[0], 'record_rows':record['record_rows'], 'package_entries':len(zipfile.ZipFile(package).namelist()), 'wiring_sha256':WIRING_HASH}, ensure_ascii=False))
