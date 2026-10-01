#!/usr/bin/env python3
"""Run the camera build of ltc_cb.c under unicorn and decode its output.

    python3 test_ltc_emu.py [seconds] [phase]

Maps the addresses the routine touches (state, ring bounds, live timecode, the
ring), calls `entry` once per simulated 1024-sample block with r0 stepping
through the ring as on the camera, and collects ch1 of the block it writes.
The simulated video timecode is the same model as test_ltc.c, so the two
outputs must be identical; the result is also decoded with ltcdump.
"""
import pathlib
import struct
import subprocess
import sys
import tempfile
import wave

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_SP

import build_ltc

HERE = pathlib.Path(__file__).resolve().parent
CODE = 0x46044000        # any address: the blob is position independent
LIVE_TC = 0xC31CC3F8
RING_PTRS = 0xC31D23EC
RING = 0x52B00580
RING_END = RING + 0x4000
K = 2
RET = 0x00010000
STACK = 0x45010000
FPS, RATE = 24, 48000
SPF = RATE // FPS


def tc_inc(tc):
    hh, mm, ss, ff = tc >> 24, tc >> 16 & 0xFF, tc >> 8 & 0xFF, tc & 0xFF
    ff += 1
    if ff >= FPS:
        ff, ss = 0, ss + 1
        if ss >= 60:
            ss, mm = 0, mm + 1
            if mm >= 60:
                mm, hh = 0, (hh + 1) % 24
    return hh << 24 | mm << 16 | ss << 8 | ff


def video_tc(sample, phase):
    """Timecode the simulated video shows at `sample`: starts at 01:00:00:00 and
    advances `phase` samples after each LTC frame start, as in test_ltc.c."""
    frames = sample // SPF + (1 if sample % SPF >= phase else 0)
    tc = 0x01000000
    for _ in range(frames):
        tc = tc_inc(tc)
    return tc


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    phase = int(sys.argv[2]) if len(sys.argv) > 2 else 700
    code, state_off = build_ltc.blob(k=K, fps=FPS)
    STATE = CODE + state_off

    uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    uc.mem_map(0x46040000, 0x10000)
    uc.mem_map(0xC31CC000, 0x7000)
    uc.mem_map(0x52B00000, 0x5000)
    uc.mem_map(RET, 0x1000)
    uc.mem_map(STACK - 0x10000, 0x10000)
    uc.mem_write(CODE, code)
    uc.mem_write(RING_PTRS, struct.pack('<II', RING, RING_END))


    out = bytearray()
    total = seconds * RATE
    r0 = RING
    for done in range(0, total, 1024):
        uc.mem_write(LIVE_TC, struct.pack('>I', video_tc(done, phase)))
        uc.reg_write(UC_ARM_REG_R0, r0)
        uc.reg_write(UC_ARM_REG_LR, RET)
        uc.reg_write(UC_ARM_REG_SP, STACK)
        uc.emu_start(CODE, RET, count=2_000_000)

        block = r0 + K * 0x1000
        if block >= RING_END:
            block -= RING_END - RING
        frames = uc.mem_read(block, 0x1000)
        for i in range(1024):
            out += frames[4 * i:4 * i + 2]
        r0 = r0 + 0x1000 if r0 + 0x1000 < RING_END else RING
    out = out[:total * 2]

    calls = struct.unpack('<I', uc.mem_read(STATE, 4))[0]
    print(f'{len(code)} bytes of code, {calls} calls')

    with tempfile.TemporaryDirectory() as tmp:
        emu_wav = pathlib.Path(tmp) / 'emu.wav'
        host_wav = pathlib.Path(tmp) / 'host.wav'
        with wave.open(str(emu_wav), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(bytes(out))

        exe = pathlib.Path(tmp) / 'test_ltc'
        subprocess.run(['cc', '-O2', '-o', str(exe), str(HERE / 'test_ltc.c')], check=True)
        subprocess.run([str(exe), str(host_wav), str(seconds), str(phase)], check=True)
        with wave.open(str(host_wav)) as w:
            host = w.readframes(w.getnframes())
        print('identical to host build' if host == bytes(out) else 'DIFFERS from host build')

        dump = subprocess.run(['ltcdump', '-f', '24', str(emu_wav)],
                              capture_output=True, text=True).stdout.splitlines()
        frames = [ln for ln in dump if ln and not ln.startswith('#')]
        breaks = sum(1 for ln in dump if 'DISCONTINUITY' in ln)
        print(f'ltcdump: {len(frames)} frames, {breaks} discontinuity markers')
        print('  first', frames[0].split('|')[0].strip())
        print('  last ', frames[-1].split('|')[0].strip())
    return 0 if host == bytes(out) and breaks <= 1 else 1


if __name__ == '__main__':
    sys.exit(main())
