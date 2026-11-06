#!/usr/bin/env python3
"""Randomized comparison of the real C++ decimal engine with Python decimal."""
import decimal
import os
import random
import subprocess
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
out = root / '.work/firmware-tests'
out.mkdir(parents=True, exist_ok=True)
src = root / 'design/firmware/source'
exe = out / 'decimal_cli'
subprocess.run([os.environ.get('CXX_HOST','clang++'), '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-g', '-I', str(src),
                str(src/'decimal.cpp'), str(Path(__file__).with_name('decimal_cli.cpp')),
                '-o', str(exe)], check=True)
rng = random.Random(2350)
cases = []
for _ in range(2500):
    def number():
        v = rng.randrange(-999999999999, 1000000000000)
        places = rng.randrange(0, 12)
        return format(decimal.Decimal(v).scaleb(-places), 'f')
    a, b = number(), number()
    op = rng.choice('+-*/')
    if op == '/' and decimal.Decimal(b) == 0:
        b = '1'
    cases.append((a, op, b))
result = subprocess.run([str(exe)], input=''.join(' '.join(c)+'\n' for c in cases),
                        text=True, capture_output=True, check=True)
lines = result.stdout.splitlines()
assert len(lines) == len(cases)
ctx = decimal.Context(prec=12, rounding=decimal.ROUND_HALF_UP, Emin=-99, Emax=99)
for case, answer in zip(cases, lines):
    a, op, b = case
    x, y = decimal.Decimal(a), decimal.Decimal(b)
    expected = {'+': ctx.add, '-': ctx.subtract, '*': ctx.multiply, '/': ctx.divide}[op](x,y)
    assert decimal.Decimal(answer) == expected, (case, answer, str(expected))
print('PASS 2500 seeded arithmetic cases against Python decimal (12 significant digits)')
