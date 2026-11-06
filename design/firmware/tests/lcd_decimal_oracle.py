#!/usr/bin/env python3
"""Independent Python decimal oracle for the 8-cell fixed-point display policy."""
import decimal as d
import os
import random
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[3]
out=root/'.work/firmware-tests'
source=root/'design/firmware/source'
exe=out/'lcd_decimal_cli'
subprocess.run([os.environ.get('CXX_HOST','clang++'),'-std=c++17','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined','-g','-I',str(source),str(source/'decimal.cpp'),
                str(Path(__file__).with_name('lcd_decimal_cli.cpp')),'-o',str(exe)],check=True)
ctx=d.Context(prec=12,rounding=d.ROUND_HALF_UP,Emin=-99,Emax=99)
rng=random.Random(1621)
cases=[]
boundaries=['0','-0','99999999','99999999.4999','99999999.5','-9999999',
            '-9999999.49999','-9999999.5','9.99999995','-9.9999995',
            '0.000000049999','0.00000005','-0.00000049999','-0.0000005',
            '0.99999995','-0.9999995','0.0000001','-0.000001']
cases.extend((a,'@','0') for a in boundaries)
cases.extend([('1','/','0'),('0','/','0'),('99999999','+','1'),
              ('99999999','*','99999999'),('0.1','+','0.2')])
def number():
    neg=rng.choice([True,False]); n=rng.randrange(0,10**(7 if neg else 8))
    places=rng.randrange(0,8)
    return ('-' if neg else '')+format(d.Decimal(n).scaleb(-places),'f')
for _ in range(3000): cases.append((number(),rng.choice('+-*/'),number()))
def expected(a,op,b):
    try:
        x,y=ctx.create_decimal(a),ctx.create_decimal(b)
        value=x if op=='@' else {'+':ctx.add,'-':ctx.subtract,'*':ctx.multiply,'/':ctx.divide}[op](x,y)
        if not value: return '0'
        cells=7 if value<0 else 8
        integer=max(1,value.copy_abs().adjusted()+1)
        if integer>cells:return 'Err'
        rounded=value.quantize(d.Decimal(1).scaleb(-(cells-integer)),rounding=d.ROUND_HALF_UP)
        if not rounded:return '0'
        if rounded.copy_abs()>=d.Decimal(10)**cells:return 'Err'
        text=format(rounded,'f')
        if '.' in text:text=text.rstrip('0').rstrip('.')
        assert len(text.replace('.',''))<=8
        return text
    except (d.DivisionByZero,d.InvalidOperation,d.Overflow):return 'Err'
result=subprocess.run([str(exe)],input=''.join(' '.join(c)+'\n' for c in cases),text=True,capture_output=True,check=True)
lines=result.stdout.splitlines()
assert len(lines)==len(cases)
for case,actual in zip(cases,lines):
    want=expected(*case)
    assert actual==want,(case,actual,want)
print(f'PASS {len(cases)} LCD signed/rounding/overflow cases against Python decimal')
