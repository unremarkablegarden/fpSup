/* Entry and state block of the LTC blob.  build_ltc.py appends the compiled
 * ltc_cb.c after this and assembles the two as one file, so the blob runs from
 * any address: the state is found pc-relatively, and the call to ltc_run is
 * resolved within the blob.
 *
 *   +0x00  entry      called with r0 = DSP ring position
 *   +0x10  ltc_state  struct ltc (ltc_core.h), 0x40 bytes, initial values
 *                     written in by build_ltc.py
 *   +0x50  ltc_run    ltc_cb.c */

.syntax unified
.arm
.text

.global entry
entry:
    push    {r4, lr}                    @ even count: the stack stays 8-aligned
    adr     r1, ltc_state
    bl      ltc_run
    pop     {r4, pc}

ltc_state:
    .space  0x40
