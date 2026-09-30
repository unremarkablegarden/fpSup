#!/usr/bin/env python3
"""Print what a trace card recorded: every traced RAM word that changed, when.

    trace_decode.py H001_580.GYR [--max-changes 40]

A trace .GYR is a normal v1.14 .GYR (20-byte header, 8-byte records) with
extra tag 0x10 records from trace_diff.S: x = region << 12 | word index,
y = value low half, z = value high half.  Time is the gyro sample count before
the record times the header's period.

The first record of each word in a log is its baseline (trace_diff dumps every
word after a take opens).  Words that changed more than --max-changes times are
counted, not listed: those are timers and counters, not REC state.
"""
import argparse
import collections
import struct
import sys

MAGIC = 0x9F5BEB0D
TAG_GYRO = 0
TAG_TRACE = 0x10
TAG_MARK = 0x11
TAG_MARK_LR = 0x12

# Same as trace_diff.S MKn_SITE.
MARKS = {
    0: 'HDMI connect FUN_c04a6720',
    1: 'FUN_c04a6a20 (HdmiRecStop caller)',
    2: 'recorder +0x50 set',
    3: 'recorder +0x54',
    4: 'recorder +0x58',
    5: 'recorder +0x5c get',
    6: 'key post (a = key code)',
    7: 'capture setter (a = captureState+0x220, b = +0x230)',
}

# Same table as trace_diff.S.
REGIONS = {
    0: (0xC3033834, 'state'),       # FUN_c00178d8(); +0x18 = captureState base
    1: (0xC3464980, 'lens'),        # lens data, FUN_c03341c8
    2: (0xC307CD80, 'lenscal'),     # calibration block, DIST_FOCAL at +0x70
    3: (0xC3464B80, 'lens2'),       # lens data, continued
}


def label(key):
    region, idx = key >> 12, key & 0xFFF
    base, name = REGIONS.get(region, (0, f'r{region}'))
    addr = base + idx * 4
    extra = f'  (captureState+0x{addr - 0xC303384C:X})' if region == 0 and addr >= 0xC303384C else ''
    return f'0x{addr:08X}  {name}+0x{idx * 4:03X}{extra}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gyr')
    ap.add_argument('--max-changes', type=int, default=40)
    a = ap.parse_args()

    data = open(a.gyr, 'rb').read()
    magic, period_ps = struct.unpack_from('<II', data)
    if magic != MAGIC:
        sys.exit(f'not a v1.14 .GYR (magic 0x{magic:08X})')
    period = period_ps / 1e12

    base = {}
    changes = collections.defaultdict(list)
    marks = []
    gyro = 0
    for off in range(20, len(data) - 7, 8):
        x, y, tag, z = struct.unpack_from('<HHhH', data, off)
        if tag == TAG_GYRO:
            gyro += 1
        elif tag == TAG_TRACE:
            value = z << 16 | y
            if x not in base:
                base[x] = value
            else:
                changes[x].append((gyro * period, value))
        elif tag == TAG_MARK:
            marks.append([gyro * period, x, y, z, None])
        elif tag == TAG_MARK_LR and marks and marks[-1][1] == x:
            marks[-1][4] = z << 16 | y

    print(f'{a.gyr}: {gyro * period:.2f} s of gyro, {len(base)} words traced, '
          f'{len(changes)} changed after baseline')
    counts = collections.Counter(m[1] for m in marks)
    print('\nmarkers: ' + (', '.join(f'{i} {MARKS.get(i, "?")}: {n}'
                                      for i, n in sorted(counts.items())) or 'none'))
    for t, i, r0, r1, lr in marks:
        if counts[i] <= a.max_changes or i in (6, 7):
            caller = f'  from 0x{lr:08X}' if lr else ''
            print(f'    {t:9.3f} s  mark {i}  a 0x{r0:04X}  b 0x{r1:04X}{caller}  {MARKS.get(i, "?")}')
    noisy = []
    for key in sorted(changes):
        ch = changes[key]
        if len(ch) > a.max_changes:
            noisy.append((key, len(ch)))
            continue
        print(f'\n{label(key)}  baseline 0x{base[key]:08X}')
        for t, v in ch:
            print(f'    {t:9.3f} s  0x{v:08X}  ({v})')
    if noisy:
        print(f'\nnoisy (> {a.max_changes} changes), not listed:')
        for key, n in noisy:
            print(f'  {label(key)}  {n}')


if __name__ == '__main__':
    main()
