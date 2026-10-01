/* LTC on ch1 of the fp DSP monitor ring, which the fp sends out as HDMI audio.
 *
 * Reached from the stock DspAudioDevice event-3 callback (0xC01FF3A8), which
 * AUD_INT calls 48 times a second; ltc_entry.S passes r0 through and adds the
 * state block.  r0 is the DSP ring position, stepping 0x1000 per call.  Writing
 * the block at r0 + 2 * 0x1000 gave a clean tone on the Ninja; +0 was silent
 * and +1 dropped out (2026-10-01).
 *
 * Ring frames are 32 bits: ch1 in the low halfword, ch2 in the high one.  Only
 * ch1 is written; ch2 keeps the fp mic. */

#include "ltc_core.h"

#define LIVE_TC 0xC31CC3F8u   /* hh, mm, ss, ff; updated once per video frame */
#define RING    0xC31D23ECu   /* +0 ring start, +4 ring end */
#define BLOCK   0x1000u       /* bytes per call: 1024 stereo frames */

void ltc_run(uint32_t r0, struct ltc *s)
{
    s->calls++;
    s->last_r0 = r0;
    if (!s->enable || s->spb == 0)
        return;

    uint32_t start = *(volatile uint32_t *)RING;
    uint32_t end = *(volatile uint32_t *)(RING + 4);
    if (r0 < start || r0 >= end)
        return;

    uint32_t p = r0 + s->k * BLOCK;
    if (p >= end)
        p -= end - start;
    if (p + BLOCK > end)
        return;

    ltc_fill(s, (volatile int16_t *)p, 2, BLOCK / 4, (const volatile uint8_t *)LIVE_TC);
}
