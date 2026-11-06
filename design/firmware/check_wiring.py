#!/usr/bin/env python3
"""Check real firmware constants against all current LCD/matrix wiring nets."""
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
wiring=json.loads((ROOT/'design/enclosure/source/wiring.json').read_text())
config=(ROOT/'design/firmware/source/board_config.hpp').read_text()
connections=wiring['connections']
def linked(part,pin):
    return [c['from']['pin'] for c in connections
            if c['from']['part']=='MCU' and c['to']=={'part':part,'pin':pin}]
def pins(name):
    return [int(v) for v in re.search(name+r'=\{([0-9,]+)\}',config).group(1).split(',')]
rows,cols=pins('row_pins'),pins('column_pins')
lcd={name:int(re.search(r'lcd_'+name+r'=(\d+)',config).group(1)) for name in ['data','wr','cs']}
assert rows==[2,3,4,5,6] and cols==[7,8,9,10]
assert lcd=={'data':0,'wr':1,'cs':11}
assert len(set(rows+cols+list(lcd.values())))==12
for signal,terminal in [('data','P3 DATA'),('wr','P2 /WR'),('cs','P1 /CS')]:
    assert linked('LCD',terminal)==['GP'+str(lcd[signal])]
assert linked('LCD','P5 VDD')==['3V3']
assert linked('LCD','P4 VSS')==['GND']
assert len([c for c in connections if any(c[end]['part']=='LCD' for end in ['from','to'])])==5
assert not any(p['ref']=='OLED' for p in wiring['parts'])
for row in range(5):
    for col in range(4):
        n=row*4+col+1
        sw,diode=f'SW{n:02d}',f'D{n:02d}'
        assert linked(sw,'1')==[f'GP{cols[col]}']
        assert len([c for c in connections if c['from']=={'part':sw,'pin':'2'}
                    and c['to']=={'part':diode,'pin':'A'}])==1
        cathodes=[c for c in connections if c['from']=={'part':diode,'pin':'K'}]
        assert len(cathodes)==1 and cathodes[0]['to']=={'part':'MCU','pin':f'GP{rows[row]}'}
for col,pin in enumerate(cols):
    assert linked(f'RPU{col}','1')==['3V3']
    assert len([c for c in connections if c['from']=={'part':f'RPU{col}','pin':'2'}
                and c['to']=={'part':'MCU','pin':f'GP{pin}'}])==1
assert any(p.get('platform')=='raspberrypi/pico-2' for p in wiring['parts'])
print('PASS LCD GPIO/power/unused terminals, 20 switches/diodes and 4 pullups match wiring.json')
