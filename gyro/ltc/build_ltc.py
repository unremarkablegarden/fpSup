"""Build the LTC blob: ltc_entry.S + ltc_cb.c, one position-independent piece
of code with its state block inside it.

The Base card carries it inside the gyro writer blob (`.incbin LTC_BLOB` in
gcsv_task.S, under WANT_LTC), so it lands in the pool with the writer.
gsup_boot then gives it an eight-byte cave veneer from the boot allocator and
writes a `b` to that veneer over the first word of the stock DspAudioDevice
callback (s_hook_b in writer_core.inc.S).  No arena address is fixed.

Used by build_base_card.py for the card, by test_ltc_emu.py, and by the USB
tool in ltc_hook/.
"""
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'fp_usb_shell'))
from armasm import assemble, symbols                            # noqa: E402

# The stock DspAudioDevice event-3 callback.  Its first word is replaced, so a
# re-registration of the callback (the monitor restarts when the menu closes)
# still reaches the blob.
SITE = 0xC01FF3A8
SITE_STOCK = 0xE1A0C000   # mov ip, r0

STATE_SIZE = 0x40
# struct ltc in ltc_core.h: byte offset of each field set here.
FIELDS = {'enable': 0x04, 'amplitude': 0x0C, 'k': 0x10, 'fps': 0x34, 'spb': 0x38, 'offset': 0x3C}

# Measured 2026-10-01 on the Ninja V: block +2 is the first clean one; 0x2000
# locks the MixPre-6 Aux In at about 75 % Ninja headphone volume.
DEFAULTS = {'enable': 1, 'amplitude': 0x2000, 'k': 2, 'fps': 24, 'offset': 0}

CFLAGS = ['-target', 'armv7-none-eabi', '-marm', '-mfloat-abi=soft', '-O2',
          '-ffreestanding', '-fno-builtin', '-fno-jump-tables', '-fno-pic',
          '-fno-unwind-tables', '-fno-asynchronous-unwind-tables']


def state(**overrides):
    """The state block's initial bytes: the defaults, spb derived from fps."""
    v = {**DEFAULTS, **overrides}
    v['spb'] = 48000 // v['fps'] // 80
    words = [0] * (STATE_SIZE // 4)
    for name, off in FIELDS.items():
        words[off // 4] = v[name]
    return struct.pack(f'<{len(words)}I', *words)


def blob(**overrides):
    """(code, state_offset): the assembled blob with its state filled in.

    ltc_cb.c goes through clang -S and is appended to ltc_entry.S, so armasm
    sees one .text section and resolves the one call itself.  Data, rodata or
    a call out of the C would be dropped or left unresolved, so any of them
    fails the build."""
    with tempfile.TemporaryDirectory() as tmp:
        c_s = pathlib.Path(tmp) / 'ltc_cb.s'
        subprocess.run(['clang', *CFLAGS, '-S', '-o', str(c_s), str(HERE / 'ltc_cb.c')],
                       check=True)
        c_text = c_s.read_text()
        bad = [ln for ln in c_text.splitlines()
               if re.match(r'\s*\.(data|bss|rodata)\b', ln)
               or re.match(r'\s*\.section\s+(?!"\.note\.GNU-stack")', ln)
               or re.match(r'\s*blx?\s', ln)]
        if bad:
            raise SystemExit('ltc_cb.c is not a single leaf routine:\n  ' + '\n  '.join(bad))
        src = pathlib.Path(tmp) / 'ltc_blob.s'
        src.write_text((HERE / 'ltc_entry.S').read_text() + '\n' + c_text)
        code = bytearray(assemble(src))
        at = symbols(src)
    if at.get('entry') != 0:
        raise SystemExit('ltc_entry.S must start the blob')
    off = at['ltc_state']
    code[off:off + STATE_SIZE] = state(**overrides)
    return bytes(code), off


_written = {}


def blob_file(**overrides):
    """The blob written to a temporary file, for `.incbin`.  One per process
    and parameter set."""
    key = tuple(sorted(overrides.items()))
    if key not in _written:
        code, _ = blob(**overrides)
        path = pathlib.Path(tempfile.mkdtemp(prefix='ltc_')) / 'ltc_blob.bin'
        path.write_bytes(code)
        _written[key] = path
    return _written[key]


def defines():
    """Assembler defines for the writer: include the blob and arm its site."""
    return ('WANT_LTC=1', f'LTC_SITE=0x{SITE:08X}', f'LTC_BLOB="{blob_file()}"')
