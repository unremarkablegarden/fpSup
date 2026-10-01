/* SMPTE LTC encoder, shared by the camera routine (ltc_cb.c) and the host
 * test (test_ltc.c).
 *
 * Output is 48 kHz.  At 24 fps that is 2000 samples per frame and 25 per bit;
 * the host writes fps and samples-per-bit into the state block so the camera
 * code needs no division.  Bit layout is the 24/30 fps one: the polarity bit is
 * bit 27.  25 fps moves it to bit 59 and is not handled.
 *
 * Freestanding: no libc, no division, no tables, so the compiled code is one
 * .text section that runs from any address. */

#ifndef LTC_CORE_H
#define LTC_CORE_H

#include <stdint.h>

/* Lives at STATE on the camera; offsets are part of the host interface
 * (hook.py). */
struct ltc {
    uint32_t calls;       /* +00 callback count */
    uint32_t enable;      /* +04 0 = leave the ring alone */
    uint32_t last_r0;     /* +08 */
    uint32_t amplitude;   /* +0C peak, 16-bit sample units */
    uint32_t k;           /* +10 block written = r0 + k * 0x1000 */
    int32_t  level;       /* +14 current output, +amplitude or -amplitude */
    uint32_t bit;         /* +18 bit being sent, 0..79 */
    uint32_t sub;         /* +1C sample within the bit, 0..spb-1 */
    uint32_t tc;          /* +20 frame being sent, hh<<24 | mm<<16 | ss<<8 | ff */
    uint32_t have_tc;     /* +24 */
    uint32_t word[3];     /* +28 the 80-bit frame, bit n at word[n >> 5] bit n & 31 */
    uint32_t fps;         /* +34 */
    uint32_t spb;         /* +38 samples per bit, 48000 / fps / 80 */
    uint32_t offset;      /* +3C frames added to the live timecode */
};

static inline uint32_t tc_inc(uint32_t tc, uint32_t fps)
{
    uint32_t hh = tc >> 24, mm = (tc >> 16) & 0xFF, ss = (tc >> 8) & 0xFF, ff = tc & 0xFF;
    if (++ff >= fps) {
        ff = 0;
        if (++ss >= 60) {
            ss = 0;
            if (++mm >= 60) {
                mm = 0;
                if (++hh >= 24)
                    hh = 0;
            }
        }
    }
    return hh << 24 | mm << 16 | ss << 8 | ff;
}

static inline void put(uint32_t *word, uint32_t pos, uint32_t value, uint32_t n)
{
    for (uint32_t i = 0; i < n; i++, pos++)
        if (value >> i & 1)
            word[pos >> 5] |= 1u << (pos & 31);
}

/* Units into pos, tens into tens_pos.  Values are below 60, so the tens are
 * counted by subtraction rather than divided. */
static inline void put_bcd(uint32_t *word, uint32_t pos, uint32_t tens_pos,
                           uint32_t tens_bits, uint32_t v)
{
    uint32_t tens = 0;
    while (v >= 10) {
        v -= 10;
        tens++;
    }
    put(word, pos, v, 4);
    put(word, tens_pos, tens, tens_bits);
}

static inline void build_word(struct ltc *s)
{
    uint32_t *w = s->word;
    uint32_t tc = s->tc;
    w[0] = w[1] = w[2] = 0;
    put_bcd(w, 0, 8, 2, tc & 0xFF);              /* frames */
    put_bcd(w, 16, 24, 3, (tc >> 8) & 0xFF);     /* seconds */
    put_bcd(w, 32, 40, 3, (tc >> 16) & 0xFF);    /* minutes */
    put_bcd(w, 48, 56, 2, tc >> 24);             /* hours */
    w[2] = 0xBFFC;                               /* sync word, bits 64..79 */

    /* Polarity bit 27: make the count of ones even, so every frame starts on
     * the same signal level. */
    uint32_t ones = 0;
    for (uint32_t i = 0; i < 80; i++)
        ones += w[i >> 5] >> (i & 31) & 1;
    if (ones & 1)
        w[0] |= 1u << 27;
}

/* The frame to send next.  The live value is read at every LTC frame start;
 * audio and video frames have the same nominal rate but an arbitrary phase, so
 * near a boundary the read can land either side of the video frame change.
 * One frame of disagreement is therefore accepted and the count continues;
 * anything else resyncs to the live value.  Assumes Free Run timecode: with a
 * stopped timecode the output alternates between two values. */
static inline void start_frame(struct ltc *s, const volatile uint8_t *live_tc)
{
    uint32_t live = (uint32_t)live_tc[0] << 24 | (uint32_t)live_tc[1] << 16 |
                    (uint32_t)live_tc[2] << 8 | live_tc[3];
    for (uint32_t i = 0; i < s->offset; i++)
        live = tc_inc(live, s->fps);

    if (s->have_tc) {
        uint32_t next = tc_inc(s->tc, s->fps);
        s->tc = (live == next || live == s->tc) ? next : live;
    } else {
        s->tc = live;
        s->have_tc = 1;
    }
    build_word(s);
}

/* Biphase mark: a transition at the start of every bit, and a second one half
 * way through a 1.  Writes n samples to out[0], out[stride], ... */
static inline void ltc_fill(struct ltc *s, volatile int16_t *out, uint32_t stride,
                            uint32_t n, const volatile uint8_t *live_tc)
{
    uint32_t half = s->spb >> 1;
    if (s->level == 0)
        s->level = (int32_t)s->amplitude;

    for (uint32_t i = 0; i < n; i++, out += stride) {
        if (s->sub == 0) {
            if (s->bit == 0)
                start_frame(s, live_tc);
            s->level = -s->level;
        } else if (s->sub == half && (s->word[s->bit >> 5] >> (s->bit & 31) & 1)) {
            s->level = -s->level;
        }
        *out = (int16_t)s->level;

        if (++s->sub >= s->spb) {
            s->sub = 0;
            if (++s->bit >= 80)
                s->bit = 0;
        }
    }
}

#endif
